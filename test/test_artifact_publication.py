from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from unaltraweb_mcp import artifact_publication as artifacts, artifact_transports as transports, practice_editions
from test_practice_tabular import TabularEditionTests


class SDKError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}
        super().__init__("synthetic provider error; SECRET-SENTINEL")


class Response:
    def __init__(self, status=200, *, data=None, raw=b"", headers=None):
        self.status_code, self.headers = status, headers or {}
        self.content = json.dumps(data).encode() if data is not None else raw
        self.raw = io.BytesIO(self.content)
        self.value = data

    def json(self):
        return self.value

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Anonymous:
    def __init__(self, public=None):
        self.public, self.calls = public, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.public is None:
            return Response(403)
        return Response(raw=self.public(url))

    def close(self):
        pass


class MemoryS3:
    def __init__(self):
        self.objects, self.puts, self.multipart, self.aborted = {}, [], {}, []
        self.corrupt = False

    def get_bucket_acl(self, **kwargs):
        return {"Grants": []}

    def get_bucket_policy(self, **kwargs):
        raise SDKError("NoSuchBucketPolicy")

    def get_object(self, **kwargs):
        key = kwargs["Key"]
        if key not in self.objects:
            raise SDKError("NoSuchKey")
        row = self.objects[key]
        content = row["Body"] + (b"corrupt" if self.corrupt else b"")
        return {**row, "Body": io.BytesIO(content), "ContentLength": len(content)}

    def put_object(self, **kwargs):
        if kwargs["Key"] in self.objects:
            raise SDKError("PreconditionFailed")
        assert kwargs["IfNoneMatch"] == "*"
        assert "ACL" not in kwargs
        self.puts.append(kwargs["Key"])
        self.objects[kwargs["Key"]] = {**kwargs, "Body": kwargs["Body"].read()}

    def create_multipart_upload(self, **kwargs):
        self.multipart = {**kwargs, "parts": []}
        return {"UploadId": "owned-attempt"}

    def upload_part(self, **kwargs):
        self.multipart["parts"].append(kwargs["Body"])
        return {"ETag": "opaque-etag-" + str(kwargs["PartNumber"])}

    def complete_multipart_upload(self, **kwargs):
        assert kwargs["IfNoneMatch"] == "*"
        self.objects[kwargs["Key"]] = {**self.multipart, "Body": b"".join(self.multipart["parts"])}

    def abort_multipart_upload(self, **kwargs):
        self.aborted.append(kwargs)

    def close(self):
        pass


class MemoryGitHub:
    def __init__(self):
        self.objects, self.assets, self.posts = {}, [], 0
        self.private = False

    def request(self, method, url, **kwargs):
        if method == "POST":
            self.posts += 1
            name = url.split("?name=", 1)[1]
            content = kwargs["data"].read()
            row = {"id": len(self.assets) + 1, "name": name, "size": len(content)}
            self.assets.append(row)
            self.objects[row["id"]] = content
            return Response(201, data=row)
        if "/releases/assets/" in url:
            return Response(raw=self.objects[int(url.rsplit("/", 1)[1])])
        if "/assets?" in url:
            return Response(data=self.assets)
        if "/releases/tags/" in url:
            return Response(data={"id": 99, "draft": False})
        return Response(data={"private": self.private})

    def public(self, url):
        name = url.rsplit("/", 1)[1]
        return self.objects[next(row["id"] for row in self.assets if row["name"] == name)]

    def close(self):
        pass


class ArtifactPublicationTests(unittest.TestCase):
    def setUp(self):
        fixture = TabularEditionTests()
        self.addCleanup(fixture.doCleanups)
        self.root, _, _ = fixture.fixture("ca")
        with patch.object(practice_editions.practice_pdf, "build", side_effect=fixture.renderer(self.root)):
            self.edition = practice_editions.compose(self.root, self.root, "edition.json")
        self.config = artifacts.CONFIG
        self.selection = {
            "kind": "unaltraweb.practice-artifact-storage", "schema_version": 1,
            "publication": {"kind": "gacontext.publication-policy", "schema_version": 1,
                "project_id": "synthetic-course", "default_target": "github", "targets": {
                    "github": {"driver": "github-release", "repository": "example/manual", "release": "practices-2026",
                               "visibility": "public", "audiences": ["public", "student"], "auth_ref": "project-ci"},
                    "s4": {"driver": "s3", "endpoint": "https://s3.example.invalid", "region": "example-1",
                           "bucket": "private-practices", "prefix": "practices/v1", "visibility": "private",
                           "audiences": ["student", "teacher", "private"], "auth_ref": "course-s4"}}},
            "artifacts": {}}
        for artifact, who, format, target in (("student-guide", "alumnat", "pdf", "github"),
                                              ("student-data", "alumnat", "zip", "s4"),
                                              ("teacher-data", "docent", "zip", "s4")):
            packet = self.edition["packages"][who]
            self.selection["artifacts"][artifact] = {"target": target, "audience": "teacher" if who == "docent" else "student",
                "receipt": self.edition["path"] + "/" + packet["receipt"], "receipt_sha256": packet["receipt_sha256"], "format": format}
        self.write_config()

    def write_config(self):
        path = self.root / self.config
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(artifacts.canonical(self.selection))
        self.sha = artifacts.digest(path.read_bytes())
        subprocess.run(["git", "-C", str(self.root), "add", self.config], check=True)

    def plan(self, name="student-data"):
        return artifacts.plan(self.root, self.config, self.sha, name)

    def stage(self, name="student-data", run="r1"):
        destination = "sandbox/artifacts/" + name + "/" + run
        return artifacts.stage(self.root, self.config, self.sha, name, destination)

    def transfer(self, prepared, connector, *, verify_only=False):
        return artifacts.transfer(self.root, self.config, self.sha, prepared["artifact_id"], prepared["stage"],
                                  prepared["manifest_sha256"], verify_only=verify_only, connector=connector)

    def test_same_project_routes_each_artifact_independently_without_credentials(self):
        with patch.object(transports, "connect", side_effect=AssertionError("Planning cannot access credentials")):
            plans = {name: self.plan(name) for name in self.selection["artifacts"]}
        self.assertEqual(plans["student-guide"]["publication"]["target_name"], "github")
        self.assertEqual(plans["student-data"]["publication"]["target_name"], "s4")
        self.assertEqual(plans["teacher-data"]["manifest"]["audience"], "teacher")
        self.assertFalse((self.root / "sandbox/artifacts").exists())

    def test_destination_change_keeps_manifest_identity_and_preserves_prior_stage(self):
        first = self.stage()
        before = (self.root / first["stage"] / "product.json").read_bytes()
        self.selection["artifacts"]["student-data"]["target"] = "github"
        self.write_config()
        second = self.stage(run="r2")
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertNotEqual(first["publication"], second["publication"])
        self.assertEqual((self.root / second["stage"] / "product.json").read_bytes(), before)
        self.assertEqual((self.root / first["stage"] / "product.json").read_bytes(), before)

    def test_stage_contains_only_selected_native_bytes_and_source_free_metadata(self):
        for name in self.selection["artifacts"]:
            prepared = self.stage(name)
            directory = self.root / prepared["stage"]
            output = prepared["manifest"]["files"][0]
            self.assertEqual((directory / output["path"]).read_bytes(), (self.root / prepared["source"]).read_bytes())
            self.assertEqual({path.name for path in directory.iterdir()}, {"product.json", "artifact.json", output["path"]})
            self.assertNotIn(b"sandbox/", (directory / "artifact.json").read_bytes())
            self.assertNotIn(b"original_inputs", (directory / "artifact.json").read_bytes())
            self.assertEqual((directory / "product.json").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(Exception):
            self.stage()

    def test_teacher_cannot_be_public_even_with_explicit_reclassification(self):
        route = self.selection["artifacts"]["teacher-data"]
        route.update(target="github", audience="student")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "Teacher"):
            self.plan("teacher-data")
        self.selection["publication"]["targets"]["github"]["audiences"].append("teacher")
        route["audience"] = "teacher"
        self.write_config()
        with self.assertRaisesRegex(ValueError, "Public targets"):
            self.plan("teacher-data")

    def test_stale_receipts_output_bytes_controls_unknown_targets_and_symlinks_refused(self):
        original = copy.deepcopy(self.selection)
        for mutation in ("receipt", "target", "fields", "sha"):
            self.selection = copy.deepcopy(original)
            route = self.selection["artifacts"]["student-data"]
            if mutation == "receipt":
                route["receipt_sha256"] = "0" * 64
            elif mutation == "target":
                route["target"] = "fallback"
            elif mutation == "fields":
                route["fallback"] = "github"
            self.write_config()
            if mutation == "sha":
                self.sha = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(Exception):
                self.plan()
        self.selection = original
        self.write_config()
        prepared = self.plan()
        source = self.root / prepared["source"]
        source.write_bytes(b"changed native output")
        with self.assertRaisesRegex(ValueError, "native seal"):
            self.plan()
        source.unlink()
        source.symlink_to(self.root / "edition.json")
        with self.assertRaises(Exception):
            self.plan()

    def test_both_actual_adapters_verify_bytes_and_no_clobber_without_cloud(self):
        s3, github = MemoryS3(), MemoryGitHub()
        for name in ("student-data", "student-guide"):
            prepared = self.stage(name)
            def connector(publication, project, auth):
                target = publication["destination"]
                return transports.S3(target, s3, anonymous=Anonymous()) if target["driver"] == "s3" else transports.GitHub(target, "synthetic-token", session=github, anonymous=Anonymous(github.public))
            first = self.transfer(prepared, connector)
            self.assertTrue(first["verified"])
            self.assertFalse(first["catalogue_updated"])
            repeat = self.transfer(prepared, connector, verify_only=True)
            self.assertTrue(all(row["reused"] for row in repeat["files"]))
            self.assertFalse(repeat["publication_performed"])
        self.assertEqual(len(s3.puts), 4)  # output, metadata, named + canonical manifest
        self.assertEqual(github.posts, 3)
        self.assertEqual(sum(row["name"].startswith("product-") for row in github.assets), 1)

    def test_actual_repository_visibility_is_checked_before_any_upload(self):
        prepared = self.stage("student-guide")
        github = MemoryGitHub()
        github.private = True
        connector = lambda publication, *args: transports.GitHub(publication["destination"], "synthetic-token",
            session=github, anonymous=Anonymous(github.public))
        with self.assertRaisesRegex(ValueError, "visibility"):
            self.transfer(prepared, connector)
        self.assertEqual(github.posts, 0)

    def test_public_s3_requires_prefix_policy_bytes_and_download_headers(self):
        prepared = self.plan()
        client = MemoryS3()
        target = {**prepared["publication"]["destination"], "visibility": "public", "audiences": ["student"]}
        content = b"public synthetic packet"
        row = {"path": "packet.zip", "bytes": len(content), "sha256": artifacts.digest(content), "media_type": "application/zip"}
        store = transports.S3(target, client, anonymous=Anonymous())
        with self.assertRaisesRegex(ValueError, "selected-prefix"):
            store.preflight()
        policy = {"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::private-practices/practices/v1/*"}]}
        with patch.object(client, "get_bucket_policy", return_value={"Policy": json.dumps(policy)}):
            store.preflight()
        key = store.key(prepared["manifest"], prepared["manifest_sha256"], row)
        def anonymous(url, **kwargs):
            stored = client.objects[key]
            return Response(raw=stored["Body"], headers={"Content-Type": stored["ContentType"], "Content-Disposition": stored["ContentDisposition"]})
        with patch.object(store.anonymous, "get", side_effect=anonymous):
            result = store.transfer(prepared["manifest"], prepared["manifest_sha256"], row, io.BytesIO(content), write=True)
        self.assertTrue(result["access"]["anonymous_read_verified"])
        self.assertIn("packet.zip", result["access"]["public_url"])
        with patch.object(store.anonymous, "get", return_value=Response(raw=content)), self.assertRaisesRegex(ValueError, "headers"):
            store.transfer(prepared["manifest"], prepared["manifest_sha256"], row, io.BytesIO(content), write=False)

    def test_corruption_missing_objects_and_permission_errors_never_fall_back(self):
        prepared = self.stage()
        client = MemoryS3()
        target = prepared["publication"]["destination"]
        connector = lambda *args: transports.S3(target, client, anonymous=Anonymous())
        with self.assertRaisesRegex(ValueError, "absent"):
            self.transfer(prepared, connector, verify_only=True)
        self.assertFalse(client.puts)
        self.transfer(prepared, connector)
        before = copy.deepcopy(client.objects)
        client.corrupt = True
        with self.assertRaises(ValueError):
            self.transfer(prepared, connector)
        self.assertEqual(client.objects, before)
        with patch.object(client, "get_object", side_effect=SDKError("AccessDenied")), self.assertRaises(RuntimeError):
            self.transfer(prepared, connector)

    def test_anonymous_read_leak_is_not_a_successful_private_delivery(self):
        prepared = self.stage()
        client = MemoryS3()
        target = prepared["publication"]["destination"]
        connector = lambda *args: transports.S3(target, client, anonymous=Anonymous(lambda url: b"public leak"))
        with self.assertRaisesRegex(ValueError, "anonymous GET"):
            self.transfer(prepared, connector)
        self.assertEqual(len(client.puts), 1)

    def test_stage_mutation_rejected_before_credentials_are_resolved(self):
        prepared = self.stage()
        (self.root / prepared["stage"] / "unselected.txt").write_bytes(b"do not publish")
        with patch.object(transports, "connect") as connect, self.assertRaisesRegex(ValueError, "Unexpected"):
            artifacts.transfer(self.root, self.config, self.sha, "student-data", prepared["stage"], prepared["manifest_sha256"])
        connect.assert_not_called()

    def test_preflight_cannot_swap_a_staged_file_before_upload(self):
        prepared = self.stage()
        client = MemoryS3()
        target = prepared["publication"]["destination"]
        store = transports.S3(target, client, anonymous=Anonymous())
        original = store.preflight
        def changed():
            original()
            row = prepared["manifest"]["files"][0]
            (self.root / prepared["stage"] / row["path"]).write_bytes(b"unselected replacement")
        with patch.object(store, "preflight", side_effect=changed), self.assertRaisesRegex(ValueError, "transfer descriptor"):
            self.transfer(prepared, lambda *args: store)
        self.assertFalse(client.puts)

    def test_private_bucket_rejects_wildcard_principal_lists_and_notprincipal(self):
        prepared = self.plan()
        client = MemoryS3()
        store = transports.S3(prepared["publication"]["destination"], client, anonymous=Anonymous())
        for grant in ({"Principal": {"AWS": ["arn:aws:iam::123456789012:root", "*"]}},
                      {"NotPrincipal": {"AWS": "arn:aws:iam::123456789012:root"}}):
            policy = {"Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*", **grant}]}
            with patch.object(client, "get_bucket_policy", return_value={"Policy": json.dumps(policy)}), self.assertRaisesRegex(ValueError, "public grants"):
                store.preflight()
        self.assertFalse(client.puts)

    def test_shared_contract_bytes_are_pinned_and_scaffold_is_unconfigured(self):
        package = Path(artifacts.__file__).parent
        for name, sha in {"product-publication-v1.schema.json": "b75a43fb755f650a20690b03920830eb42f4638b4bb315575ae26e3043139ef0",
                          "publication-policy-v1.schema.json": "3bff0bfba6be332ef1b4cbfb7d01bee7e8edfe3251dbfed4a8c5c0b89a620d34"}.items():
            self.assertEqual(artifacts.digest((package / name).read_bytes()), sha)
        scaffold = json.loads((package / "scaffolds/common/.unaltraweb/practice-artifacts.json").read_bytes())
        self.assertIsNone(scaffold["publication"])
        self.assertEqual(scaffold["artifacts"], {})

    def test_auth_binding_is_private_and_destination_bound_before_any_network(self):
        plan = self.plan()
        binding = self.root / "private-auth.json"
        binding.write_text(json.dumps({"kind": "gacontext.publication-auth", "schema_version": 1, "project_id": "synthetic-course",
            "bindings": {"course-s4": {"driver": "s3", "destination_sha256": "0" * 64,
                "access_key_env": "SYNTHETIC_KEY", "secret_key_env": "SYNTHETIC_SECRET"}}}))
        binding.chmod(0o600)
        with patch.dict(os.environ, {"AWS_PROFILE": "ambient-not-authority"}, clear=True), self.assertRaisesRegex(ValueError, "exact destination"):
            transports.connect(plan["publication"], "synthetic-course", binding)
        binding.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "0600"):
            transports.connect(plan["publication"], "synthetic-course", binding)

    def test_factory_make_facade_passes_arguments_without_make_or_shell_execution(self):
        factory = Path(__file__).resolve().parents[1]
        arguments = ["make", "--silent", "--no-print-directory", "-C", str(factory), "practice-artifact-plan",
                     "PYTHON=" + sys.executable, "PRACTICE_ARTIFACT_SHA256=" + self.sha]
        environment = {**os.environ, "MCP_CONSUMER_WORKSPACE": str(self.root)}
        result = subprocess.run([*arguments, "PRACTICE_ARTIFACT_ID=student-data"], env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["publication"]["target_name"], "s4")
        marker = self.root / "must-not-execute"
        for value in ("$(shell touch " + str(marker) + ")", "student-data'; touch " + str(marker) + "; #"):
            refused = subprocess.run([*arguments, "PRACTICE_ARTIFACT_ID=" + value], env=environment, text=True, capture_output=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertFalse(marker.exists())

    def test_multipart_is_conditional_and_aborts_only_its_own_failed_upload(self):
        prepared = self.plan()
        client = MemoryS3()
        store = transports.S3(prepared["publication"]["destination"], client, anonymous=Anonymous())
        content = b"synthetic multipart data"
        row = {"path": "packet.zip", "bytes": len(content), "sha256": artifacts.digest(content), "media_type": "application/zip"}
        with patch.object(transports, "MULTIPART_THRESHOLD", 8), patch.object(transports, "PART_BYTES", 8):
            store.transfer(prepared["manifest"], prepared["manifest_sha256"], row, io.BytesIO(content), write=True)
            self.assertEqual(next(iter(client.objects.values()))["Body"], content)
            with patch.object(client, "upload_part", side_effect=SDKError("AccessDenied")), self.assertRaises(SDKError):
                store.put("another-exact-key", row, io.BytesIO(content))
        self.assertEqual(client.aborted, [{"Bucket": "private-practices", "Key": "another-exact-key", "UploadId": "owned-attempt"}])

    @unittest.skipUnless(importlib.util.find_spec("botocore"), "optional public S3 SDK is absent")
    def test_real_sdk_model_accepts_streamed_conditional_write_and_exact_readback(self):
        import botocore.session
        from botocore.config import Config
        from botocore.stub import ANY, Stubber
        prepared = self.plan()
        target = prepared["publication"]["destination"]
        client = botocore.session.get_session().create_client("s3", endpoint_url=target["endpoint"], region_name=target["region"],
            aws_access_key_id="synthetic", aws_secret_access_key="synthetic", config=Config(retries={"total_max_attempts": 1}))
        store = transports.S3(target, client, anonymous=Anonymous())
        raw = b"synthetic native ZIP bytes"
        row = {"path": "packet.zip", "bytes": len(raw), "sha256": artifacts.digest(raw), "media_type": "application/zip"}
        key = store.key(prepared["manifest"], prepared["manifest_sha256"], row)
        with Stubber(client) as stub:
            stub.add_response("get_bucket_acl", {"Grants": []}, {"Bucket": target["bucket"]})
            stub.add_client_error("get_bucket_policy", service_error_code="NoSuchBucketPolicy", expected_params={"Bucket": target["bucket"]})
            stub.add_client_error("get_object", service_error_code="NoSuchKey", expected_params={"Bucket": target["bucket"], "Key": key})
            stub.add_response("put_object", {}, {"Bucket": target["bucket"], "Key": key, "Body": ANY, "ContentLength": len(raw),
                "ContentType": row["media_type"], "ContentDisposition": transports.disposition(row), "IfNoneMatch": "*"})
            stub.add_response("get_object", {"Body": io.BytesIO(raw), "ContentLength": len(raw), "ContentType": row["media_type"],
                "ContentDisposition": transports.disposition(row)}, {"Bucket": target["bucket"], "Key": key})
            store.preflight()
            self.assertTrue(store.transfer(prepared["manifest"], prepared["manifest_sha256"], row, io.BytesIO(raw), write=True)["verified"])
            stub.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
