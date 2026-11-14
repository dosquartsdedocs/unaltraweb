from __future__ import annotations

import copy
import importlib.util
import io
import json
import unittest
from unittest.mock import patch
import zipfile

from unaltraweb_mcp import artifact_attempts as evidence, artifact_publication as publication, artifact_transports as transports
import test_retained_intake as fixtures
import test_artifact_publication as providers
import test_artifact_attempts as failures
from zip_only_fixtures import flat_routes, zip_only_intake


class FlatArtifactStorageTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.RetainedIntakeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        zip_only_intake(self.case)
        self.admitted = self.case.snapshot()
        self.config, self.sha = flat_routes(self.case, self.admitted)

    def save(self):
        self.case.write(publication.CONFIG, publication.canonical(self.config))
        self.sha = self.case.pin(publication.CONFIG)["sha256"]

    def stage(self, identifier="alumnat-packet", run="one"):
        return publication.stage(self.case.root, publication.CONFIG, self.sha, identifier, "sandbox/artifacts/" + identifier + "/" + run)

    def transfer(self, staged, client, *, verify_only=False, stores=None):
        def connector(pub, *args):
            store = transports.S3(pub["destination"], client, profile=pub["storage_profile"], layout=pub.get("delivery_layout", "named-v1"), anonymous=providers.Anonymous())
            if stores is not None:
                stores.append(store)
            return store
        return publication.transfer(self.case.root, publication.CONFIG, self.sha, staged["artifact_id"], staged["stage"], staged["manifest_sha256"], connector=connector, verify_only=verify_only)

    def inspect(self, pointer):
        return evidence.inspect(self.case.root, pointer["path"], pointer["intent_sha256"], pointer["events_sha256"])

    def test_zip_only_originals_plain_keys_private_readback_and_local_metadata(self):
        case, client = self.case, providers.MemoryS3()
        original = {item["pdf"]["path"]: (case.root / item["pdf"]["path"]).read_bytes() for item in case.request["packages"]}
        snapshot_files = {path.name for path in (case.root / self.admitted["snapshot"] / "files").iterdir()}
        self.assertEqual(snapshot_files, {"retained-handoff.zip", "retained-handoff-docent.zip"})
        for identifier, receipt in self.admitted["receipts"].items():
            planned = publication.plan(case.root, publication.CONFIG, self.sha, identifier)
            self.assertFalse(planned["credentials_resolved"] or planned["publication_performed"])
            staged = self.stage(identifier)
            output = staged["manifest"]["files"][0]
            key = "practiques/ca/" + output["path"]
            self.assertEqual(planned["delivery"]["remote_keys"], [key])
            self.assertEqual({path.name for path in (case.root / staged["stage"]).iterdir()}, {output["path"], "product.json", "artifact.json", "delivery.json"})
            first = self.transfer(staged, client)
            repeated = self.transfer(staged, client, verify_only=True)
            self.assertTrue(first["verified"] and repeated["verified"])
            self.assertEqual(first["layout"], "files-v1")
            self.assertFalse(first["remote_metadata_created"] or first["remote_deletes"] or first["full_remote_metadata_restoration"] or first["catalogue_updated"])
            self.assertTrue(first["local_inventory_required_for_fetch"])
            self.assertFalse(repeated["publication_performed"] or repeated["local_attempt"]["remote_mutation_requested"])
            self.assertEqual(len(first["files"]), 1)
            remote = client.objects[key]
            self.assertEqual(remote["Body"], (case.root / case.base / output["path"]).read_bytes())
            self.assertEqual((remote["ContentType"], remote["ContentDisposition"]), ("application/zip", transports.disposition(output)))
            self.assertIsNone(first["files"][0]["access"]["public_url"])
            self.assertFalse(first["files"][0]["access"]["anonymous_probe_performed"])
            intent = self.inspect(first["local_attempt"])["intent"]
            self.assertEqual(intent["delivery_layout"], "files-v1")
            self.assertEqual([item["key"] for item in intent["objects"]], [key])
            with zipfile.ZipFile(io.BytesIO(remote["Body"])) as archive:
                selected = next(item for item in case.request["packages"] if item["recipient"] == receipt["recipient"])
                self.assertEqual(archive.read(selected["reading_member"]), original[selected["pdf"]["path"]])
        self.assertEqual(set(client.objects), {"practiques/ca/retained-handoff.zip", "practiques/ca/retained-handoff-docent.zip"})
        self.assertEqual(len(client.puts), 2)
        self.assertFalse(any(name.endswith((".pdf", ".json", ".jsonl")) or "/named/" in name or "/manifests/" in name for name in client.objects))
        for path, before in original.items():
            self.assertEqual((case.root / path).read_bytes(), before)

    def test_explicit_v3_private_capability_repository_and_teacher_boundaries(self):
        original = copy.deepcopy(self.config)
        for wrong in ("old-version", "missing-layout", "unknown-layout", "anonymous", "public", "github", "bucket", "teacher"):
            self.config = copy.deepcopy(original)
            row = self.config["artifacts"]["docent-packet" if wrong == "teacher" else "alumnat-packet"]
            if wrong == "old-version":
                self.config["schema_version"] = 2
            elif wrong == "missing-layout":
                del row["delivery_layout"]
            elif wrong == "unknown-layout":
                row["delivery_layout"] = "guess-flat"
            elif wrong == "anonymous":
                row["storage_profile"] = "anonymous-delivery-v1"
            elif wrong == "public":
                self.config["publication"]["targets"]["s4"]["visibility"] = "public"
            elif wrong == "github":
                row.update(target="github", storage_profile="anonymous-delivery-v1")
            elif wrong == "bucket":
                self.config["publication"]["targets"]["s4"]["bucket"] = "neighbour"
            else:
                row["audience"] = "student"
            self.save()
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                publication.plan(self.case.root, publication.CONFIG, self.sha, "docent-packet" if wrong == "teacher" else "alumnat-packet")

    def test_named_stage_cannot_be_silently_flattened_and_product_identity_stays_native(self):
        for row in self.config["artifacts"].values():
            row["delivery_layout"] = "named-v1"
        self.save()
        named = self.stage(run="named")
        directory = self.case.root / named["stage"]
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.iterdir()}
        self.assertEqual(len(before), 3)
        for row in self.config["artifacts"].values():
            row["delivery_layout"] = "files-v1"
        self.save()
        with patch.object(transports, "connect") as connect, self.assertRaisesRegex(ValueError, "layout"):
            publication.transfer(self.case.root, publication.CONFIG, self.sha, "alumnat-packet", named["stage"], named["manifest_sha256"])
        connect.assert_not_called()
        flat = self.stage(run="files")
        self.assertEqual(flat["manifest_sha256"], named["manifest_sha256"])
        self.assertEqual({path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.iterdir()}, before)
        self.config["artifacts"]["alumnat-packet"]["delivery_layout"] = "named-v1"
        self.save()
        with self.assertRaisesRegex(ValueError, "layout"):
            publication.plan(self.case.root, publication.CONFIG, self.sha, "alumnat-packet", staged=flat["stage"], manifest_sha256=flat["manifest_sha256"])

    def test_missing_corrupt_or_header_collision_is_refused_without_replacement(self):
        staged, client = self.stage(), providers.MemoryS3()
        with self.assertRaises(evidence.TransferFailure) as missing:
            self.transfer(staged, client, verify_only=True)
        self.assertFalse(client.puts or missing.exception.attempt["remote_mutation_requested"])
        self.transfer(staged, client)
        original = copy.deepcopy(client.objects)
        key = next(iter(original))
        for wrong in ("bytes", "headers", "public-acl", "access-denied"):
            client.objects = copy.deepcopy(original)
            if wrong == "bytes":
                client.objects[key]["Body"] = b"different existing original must not be overwritten"
            elif wrong == "headers":
                client.objects[key]["ContentType"] = "text/plain"
            before = copy.deepcopy(client.objects)
            patches = []
            if wrong == "public-acl":
                patches.append(patch.object(client, "get_object_acl", return_value={"Grants": [{"Grantee": {"URI": "http://acs.amazonaws.com/groups/global/AllUsers"}}]}))
            if wrong == "access-denied":
                patches.append(patch.object(client, "get_object", side_effect=providers.SDKError("AccessDenied")))
            with self.subTest(wrong=wrong):
                for item in patches:
                    item.start()
                try:
                    with self.assertRaises(evidence.TransferFailure) as refused:
                        self.transfer(staged, client)
                    self.assertFalse(refused.exception.attempt["remote_mutation_requested"])
                finally:
                    for item in patches:
                        item.stop()
            self.assertEqual(client.objects, before)
            self.assertEqual(len(client.puts), 1)

    def test_stage_seal_metadata_or_output_tamper_refused_before_credentials(self):
        staged = self.stage()
        for name in ("delivery.json", "artifact.json", "product.json", staged["manifest"]["files"][0]["path"]):
            path = self.case.root / staged["stage"] / name
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(name=name), patch.object(transports, "connect") as connect, self.assertRaises(ValueError):
                publication.transfer(self.case.root, publication.CONFIG, self.sha, staged["artifact_id"], staged["stage"], staged["manifest_sha256"])
            connect.assert_not_called()
            path.write_bytes(original)

    def test_conditional_create_race_never_overwrites_or_retries(self):
        staged, client = self.stage(), providers.MemoryS3()
        def raced(**kwargs):
            self.assertEqual(kwargs["IfNoneMatch"], "*")
            client.objects[kwargs["Key"]] = {"Body": b"other actor's private object"}
            raise providers.SDKError("PreconditionFailed SECRET-SENTINEL")
        with patch.object(client, "put_object", side_effect=raced) as put, self.assertRaises(evidence.TransferFailure) as refused:
            self.transfer(staged, client)
        self.assertEqual(put.call_count, 1)
        self.assertEqual(next(iter(client.objects.values()))["Body"], b"other actor's private object")
        inspected = self.inspect(refused.exception.attempt)
        self.assertIn("put-uncertain", [row["phase"] for row in inspected["events"]])
        self.assertEqual([row["key"] for row in inspected["intent"]["objects"]], ["practiques/ca/retained-handoff.zip"])
        self.assertNotIn("SECRET-SENTINEL", str(refused.exception))

    def test_flat_uncertain_completion_can_be_inspected_verified_without_replay(self):
        staged, client = self.stage(), failures.FailingS3(complete=True)
        with patch.object(transports, "MULTIPART_THRESHOLD", 64), patch.object(transports, "PART_BYTES", 128), self.assertRaises(evidence.TransferFailure) as failure:
            self.transfer(staged, client)
        observed = self.inspect(failure.exception.attempt)
        key = "practiques/ca/retained-handoff.zip"
        self.assertEqual(observed["owned_uploads_observed"], {key: "owned-attempt"})
        self.assertIn("completion-uncertain", [row["phase"] for row in observed["events"]])
        self.assertFalse(client.aborted)
        before = (client.creates, client.part_requests, client.completions)
        result = self.transfer(staged, client, verify_only=True)
        self.assertTrue(result["verified"])
        self.assertFalse(result["publication_performed"] or result["local_attempt"]["remote_mutation_requested"])
        self.assertEqual((client.creates, client.part_requests, client.completions), before)
        self.assertEqual(set(client.objects), {key})

    def test_flat_evidence_layout_config_or_seal_change_stops_owned_mutation(self):
        staged = self.stage()
        for wrong in ("layout", "config", "seal", "events"):
            client, stores = failures.FailingS3(), []
            changed, original = None, None
            def change():
                nonlocal changed, original
                if wrong == "layout":
                    stores[-1].layout = "named-v1"
                else:
                    changed = self.case.root / (publication.CONFIG if wrong == "config" else staged["stage"] + "/delivery.json" if wrong == "seal" else stores[-1].attempt.path + "/events.jsonl")
                    original = changed.read_bytes()
                    changed.write_bytes(original + b" ")
            client.after_create = change
            with self.subTest(wrong=wrong), patch.object(transports, "MULTIPART_THRESHOLD", 64), self.assertRaises(evidence.TransferFailure):
                self.transfer(staged, client, stores=stores)
            self.assertEqual((client.part_requests, client.completions, client.puts, client.aborted), (0, 0, [], []))
            if changed is not None and wrong != "events":
                changed.write_bytes(original)

    @unittest.skipUnless(importlib.util.find_spec("botocore"), "optional public S3 SDK is absent")
    def test_native_sdk_flat_conditional_put_exact_headers_acl_and_single_key(self):
        import botocore.session
        from botocore.stub import ANY, Stubber
        staged = self.stage()
        target, row = staged["publication"]["destination"], staged["manifest"]["files"][0]
        client = botocore.session.get_session().create_client("s3", endpoint_url=target["endpoint"], region_name=target["region"], aws_access_key_id="synthetic", aws_secret_access_key="synthetic")
        key = "practiques/ca/" + row["path"]
        raw = (self.case.root / staged["stage"] / row["path"]).read_bytes()
        with Stubber(client) as stub:
            stub.add_response("get_bucket_acl", {"Grants": []}, {"Bucket": "course"})
            stub.add_client_error("get_bucket_policy", service_error_code="NoSuchBucketPolicy", expected_params={"Bucket": "course"})
            stub.add_client_error("get_object", service_error_code="NoSuchKey", expected_params={"Bucket": "course", "Key": key})
            stub.add_response("put_object", {}, {"Bucket": "course", "Key": key, "Body": ANY, "ContentLength": len(raw), "ContentType": "application/zip", "ContentDisposition": transports.disposition(row), "IfNoneMatch": "*"})
            stub.add_response("get_object", {"Body": io.BytesIO(raw), "ContentLength": len(raw), "ContentType": "application/zip", "ContentDisposition": transports.disposition(row)}, {"Bucket": "course", "Key": key})
            stub.add_response("get_object_acl", providers.MemoryS3().get_object_acl(), {"Bucket": "course", "Key": key})
            self.assertTrue(self.transfer(staged, client)["verified"])
            stub.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
