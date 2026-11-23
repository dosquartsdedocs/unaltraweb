from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_artifact_publication as fixtures
from unaltraweb_mcp import artifact_attempts as evidence, artifact_publication as artifacts, artifact_transports as transports


class FailingS3(fixtures.MemoryS3):
    def __init__(self, *, part=False, abort=False, create=False, complete=False, readback=False):
        super().__init__()
        self.fail_part, self.fail_abort, self.lose_create = part, abort, create
        self.lose_complete, self.fail_readback = complete, readback
        self.creates = self.part_requests = self.completions = 0
        self.after_create = None
        self.before_create = None

    def create_multipart_upload(self, **kwargs):
        self.creates += 1
        if self.before_create:
            self.before_create(kwargs)
        value = super().create_multipart_upload(**kwargs)
        if self.after_create:
            self.after_create()
        if self.lose_create:
            raise fixtures.SDKError("RequestTimeout")
        return value

    def upload_part(self, **kwargs):
        self.part_requests += 1
        if self.fail_part:
            raise fixtures.SDKError("SECRET-SENTINEL SENSITIVE-TEACHER-DATA")
        return super().upload_part(**kwargs)

    def abort_multipart_upload(self, **kwargs):
        super().abort_multipart_upload(**kwargs)
        if self.fail_abort:
            raise fixtures.SDKError("RequestTimeout SECRET-SENTINEL")

    def complete_multipart_upload(self, **kwargs):
        self.completions += 1
        super().complete_multipart_upload(**kwargs)
        if self.lose_complete:
            raise fixtures.SDKError("RequestTimeout SECRET-SENTINEL")

    def get_object(self, **kwargs):
        if self.fail_readback and kwargs["Key"] in self.objects:
            raise fixtures.SDKError("RequestTimeout SECRET-SENTINEL")
        return super().get_object(**kwargs)


class AttemptEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ArtifactPublicationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.prepared = self.fixture.stage()
        self.stores = []

    def run_transfer(self, client, *, verify_only=False):
        def connect(publication, *args):
            store = transports.S3(publication["destination"], client, anonymous=fixtures.Anonymous(), profile=publication["storage_profile"])
            self.stores.append(store)
            return store
        with patch.object(transports, "MULTIPART_THRESHOLD", 64), patch.object(transports, "PART_BYTES", 256):
            return self.fixture.transfer(self.prepared, connect, verify_only=verify_only)

    def inspect(self, pointer):
        return evidence.inspect(self.root, pointer["path"], pointer["intent_sha256"], pointer["events_sha256"])

    def failure(self, client):
        with self.assertRaises(evidence.TransferFailure) as error:
            self.run_transfer(client)
        self.assertNotIn("SECRET-SENTINEL", str(error.exception))
        self.assertNotIn("SENSITIVE-TEACHER-DATA", str(error.exception))
        pointer = error.exception.attempt
        observed = self.inspect(pointer)
        for path in (self.root / pointer["path"]).iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b"SECRET-SENTINEL", path.read_bytes())
            self.assertNotIn(b"SENSITIVE-TEACHER-DATA", path.read_bytes())
            self.assertNotIn(b"synthetic sealed fixture", path.read_bytes())
        self.assertEqual((self.root / pointer["path"]).stat().st_mode & 0o777, 0o700)
        return pointer, observed

    def test_part_failure_retains_exact_tuple_and_only_acknowledged_abort(self):
        client = FailingS3(part=True)
        def before(request):
            attempt = self.stores[-1].attempt
            intent = json.loads((self.root / attempt.path / "intent.json").read_bytes())
            events = [json.loads(line) for line in (self.root / attempt.path / "events.jsonl").read_bytes().splitlines()]
            self.assertEqual(events[-1]["phase"], "create-requested")
            self.assertEqual(intent["configuration"]["sha256"], self.fixture.sha)
            self.assertEqual(intent["stage"]["manifest_sha256"], self.prepared["manifest_sha256"])
            self.assertEqual((request["Bucket"], request["Key"]), (intent["destination"]["bucket"], intent["objects"][0]["key"]))
        client.before_create = before
        pointer, observed = self.failure(client)
        phases = [row["phase"] for row in observed["events"]]
        self.assertEqual(phases[-3:], ["abort-requested", "abort-acknowledged", "failed"])
        upload = next(row["data"]["owned_upload"] for row in observed["events"] if row["phase"] == "upload-observed")
        self.assertEqual(client.aborted, [{"Bucket": upload["bucket"], "Key": upload["key"], "UploadId": upload["upload_id"]}])
        self.assertEqual((client.creates, client.part_requests, client.completions), (1, 1, 0))
        self.assertEqual(pointer["phase"], "failed")
        self.assertFalse(observed["recovery_performed"])
        self.assertFalse(any("cleanup_verified" in row["data"] for row in observed["events"]))

    def test_failed_abort_keeps_owned_tuple_and_uncertain_phase(self):
        client = FailingS3(part=True, abort=True)
        _, observed = self.failure(client)
        phases = [row["phase"] for row in observed["events"]]
        self.assertIn("abort-uncertain", phases)
        self.assertNotIn("abort-acknowledged", phases)
        upload = next(row["data"]["owned_upload"] for row in observed["events"] if row["phase"] == "abort-uncertain")
        self.assertEqual(upload, {"bucket": "tigit", "key": observed["intent"]["objects"][0]["key"], "upload_id": "owned-attempt"})
        self.assertEqual(len(client.aborted), 1)

    def test_lost_create_response_has_no_invented_id_or_abort(self):
        client = FailingS3(create=True)
        _, observed = self.failure(client)
        self.assertIn("create-uncertain", [row["phase"] for row in observed["events"]])
        self.assertEqual(observed["owned_uploads_observed"], {})
        self.assertFalse(any("owned_upload" in row["data"] for row in observed["events"]))
        self.assertEqual((client.creates, client.part_requests, client.completions, client.aborted), (1, 0, 0, []))

    def test_uncertain_completion_preserves_final_bytes_for_readonly_inspection(self):
        client = FailingS3(complete=True)
        _, observed = self.failure(client)
        key = observed["intent"]["objects"][0]["key"]
        self.assertIn("completion-uncertain", [row["phase"] for row in observed["events"]])
        self.assertNotIn("complete-acknowledged", [row["phase"] for row in observed["events"]])
        self.assertEqual(client.aborted, [])
        self.assertEqual(client.objects[key]["Body"], (self.root / self.prepared["source"]).read_bytes())
        before = copy.deepcopy(client.objects)
        with self.assertRaises(evidence.TransferFailure) as verified:
            self.run_transfer(client, verify_only=True)  # Metadata remains absent; never repair it here.
        check = self.inspect(verified.exception.attempt)
        self.assertTrue(any(row["phase"] == "object-verified" and row["data"]["key"] == key for row in check["events"]))
        self.assertFalse(verified.exception.attempt["remote_mutation_requested"])
        self.assertEqual(client.objects, before)
        self.assertEqual((client.creates, client.completions), (1, 1))

    def test_readback_failure_retains_completed_owned_upload_without_abort(self):
        client = FailingS3(readback=True)
        _, observed = self.failure(client)
        phases = [row["phase"] for row in observed["events"]]
        self.assertIn("complete-acknowledged", phases)
        self.assertIn("readback-uncertain", phases)
        self.assertEqual(client.aborted, [])
        self.assertTrue(observed["owned_uploads_observed"])

    def test_intent_or_event_tampering_blocks_mutation_and_inspection(self):
        for name in ("intent.json", "events.jsonl"):
            client = FailingS3()
            def policy(**kwargs):
                attempt = self.stores[-1].attempt
                path = self.root / attempt.path / name
                path.write_bytes(path.read_bytes() + b" ")
                raise fixtures.SDKError("NoSuchBucketPolicy")
            with self.subTest(name=name), patch.object(client, "get_bucket_policy", side_effect=policy), self.assertRaises(evidence.TransferFailure) as error:
                self.run_transfer(client)
            self.assertFalse(error.exception.attempt["evidence_intact"])
            self.assertEqual((client.creates, client.part_requests, client.aborted, client.puts), (0, 0, [], []))
            with self.assertRaises(evidence.EvidenceError):
                self.inspect(error.exception.attempt)

    def test_source_binding_change_after_owned_id_is_recorded_stops_further_mutation(self):
        client = FailingS3()
        def change():
            path = self.root / self.fixture.config
            path.write_bytes(path.read_bytes() + b" ")
        client.after_create = change
        _, observed = self.failure(client)
        self.assertTrue(observed["owned_uploads_observed"])
        self.assertIn("binding-changed", [row["phase"] for row in observed["events"]])
        self.assertEqual((client.creates, client.part_requests, client.completions, client.aborted), (1, 0, 0, []))

    def test_staged_source_change_after_create_does_not_upload_changed_teacher_bytes(self):
        client = FailingS3()
        row = self.prepared["manifest"]["files"][0]
        client.after_create = lambda: (self.root / self.prepared["stage"] / row["path"]).write_bytes(b"SENSITIVE-TEACHER-DATA")
        _, observed = self.failure(client)
        self.assertTrue(observed["owned_uploads_observed"])
        self.assertIn("binding-changed", [row["phase"] for row in observed["events"]])
        self.assertEqual((client.creates, client.part_requests, client.aborted, client.objects), (1, 0, [], {}))

    def test_destination_binding_change_cannot_redirect_a_mutating_request(self):
        client = FailingS3()
        def policy(**kwargs):
            self.stores[-1].target["bucket"] = "unrelated-bucket"
            raise fixtures.SDKError("NoSuchBucketPolicy")
        with patch.object(client, "get_bucket_policy", side_effect=policy):
            _, observed = self.failure(client)
        self.assertEqual(observed["intent"]["destination"]["bucket"], "tigit")
        self.assertEqual((client.creates, client.part_requests, client.puts), (0, 0, []))

    def test_attempt_namespace_symlink_cannot_escape_workspace(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.root / evidence.ROOT).symlink_to(Path(outside.name), target_is_directory=True)
        client = FailingS3()
        with self.assertRaises(OSError):
            self.run_transfer(client)
        self.assertEqual(list(Path(outside.name).iterdir()), [])
        self.assertEqual((client.creates, client.part_requests, client.puts), (0, 0, []))

    def test_successful_repeat_preserves_product_and_uploads_no_journal(self):
        client = FailingS3()
        stage = self.root / self.prepared["stage"]
        original = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in stage.iterdir()}
        first = self.run_transfer(client)
        mutations = (client.creates, client.part_requests, client.completions)
        second = self.run_transfer(client)
        self.assertFalse(second["publication_performed"])
        self.assertFalse(second["local_attempt"]["remote_mutation_requested"])
        self.assertNotEqual(first["local_attempt"]["path"], second["local_attempt"]["path"])
        self.assertEqual(mutations, (client.creates, client.part_requests, client.completions))
        self.assertEqual({path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in stage.iterdir()}, original)
        self.assertEqual(len(client.objects), 4)
        self.assertFalse(any("artifact-attempts" in key or "intent.json" in key or "events.jsonl" in key for key in client.objects))
        self.assertEqual(self.inspect(second["local_attempt"])["events"][-1]["phase"], "verified")

    def test_cli_error_and_local_inspection_expose_only_safe_failure_metadata(self):
        client = FailingS3(part=True, abort=True)
        def connect(publication, *args):
            store = transports.S3(publication["destination"], client, profile=publication["storage_profile"], anonymous=fixtures.Anonymous())
            self.stores.append(store)
            return store
        args = ["publish", "--project", str(self.root), "--sha256", self.fixture.sha, "--artifact", "student-data",
                "--stage", self.prepared["stage"], "--manifest-sha256", self.prepared["manifest_sha256"], "--auth-file", "/synthetic/not-read.json"]
        with patch.object(transports, "connect", side_effect=connect), patch.object(transports, "MULTIPART_THRESHOLD", 64), \
                patch.object(transports, "PART_BYTES", 256), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            code = artifacts.main(args)
        self.assertEqual(code, 1)
        self.assertNotIn("SECRET-SENTINEL", stderr.getvalue())
        self.assertNotIn("SENSITIVE-TEACHER-DATA", stderr.getvalue())
        result = json.loads(stderr.getvalue())
        pointer = result["local_attempt"]
        self.assertEqual(result["phase"], "abort-uncertain")
        with patch("sys.stdout", new_callable=io.StringIO) as stdout, patch.object(transports, "connect", side_effect=AssertionError("Local inspection cannot connect")):
            inspected = artifacts.main(["inspect-attempt", "--project", str(self.root), "--attempt", pointer["path"],
                "--intent-sha256", pointer["intent_sha256"], "--attempt-sha256", pointer["events_sha256"]])
        self.assertEqual(inspected, 0)
        self.assertTrue(json.loads(stdout.getvalue())["local_only"])
        for path in ("../escape", self.prepared["stage"], pointer["path"] + "/../escape"):
            with self.assertRaises((ValueError, RuntimeError)):
                evidence.inspect(self.root, path, pointer["intent_sha256"], pointer["events_sha256"])

    @unittest.skipUnless(importlib.util.find_spec("botocore"), "optional public S3 SDK is absent")
    def test_native_sdk_part_and_abort_failures_retain_exact_observed_upload(self):
        import botocore.session
        from botocore.config import Config
        from botocore.stub import ANY, Stubber
        target = self.prepared["publication"]["destination"]
        client = botocore.session.get_session().create_client("s3", endpoint_url=target["endpoint"], region_name=target["region"],
            aws_access_key_id="synthetic-id", aws_secret_access_key="synthetic-secret", config=Config(retries={"total_max_attempts": 1}))
        store = transports.S3(target, client, profile="authenticated-private-v1", anonymous=fixtures.Anonymous())
        self.fixture.bind_evidence(self.prepared, store)
        row = self.prepared["manifest"]["files"][0]
        content = (self.root / self.prepared["stage"] / row["path"]).read_bytes()
        key = store.key(self.prepared["manifest"], self.prepared["manifest_sha256"], row)
        with Stubber(client) as stub:
            stub.add_response("create_multipart_upload", {"UploadId": "observed-native-id"}, {"Bucket": "tigit", "Key": key,
                "ContentType": row["media_type"], "ContentDisposition": transports.disposition(row)})
            stub.add_client_error("upload_part", service_error_code="AccessDenied", service_message="SECRET-SENTINEL SENSITIVE-TEACHER-DATA",
                expected_params={"Bucket": "tigit", "Key": key, "UploadId": "observed-native-id", "PartNumber": 1, "Body": ANY, "ContentLength": min(256, len(content))})
            stub.add_client_error("abort_multipart_upload", service_error_code="RequestTimeout", service_message="SECRET-SENTINEL",
                expected_params={"Bucket": "tigit", "Key": key, "UploadId": "observed-native-id"})
            with patch.object(transports, "MULTIPART_THRESHOLD", 64), patch.object(transports, "PART_BYTES", 256), self.assertRaises(evidence.TransferFailure) as error:
                store.put(key, row, io.BytesIO(content))
            observed = self.inspect(error.exception.attempt)
            self.assertEqual(observed["owned_uploads_observed"], {key: "observed-native-id"})
            self.assertIn("abort-uncertain", [entry["phase"] for entry in observed["events"]])
            self.assertNotIn("SECRET-SENTINEL", str(error.exception))
            stub.assert_no_pending_responses()
        client.close()


if __name__ == "__main__":
    unittest.main()
