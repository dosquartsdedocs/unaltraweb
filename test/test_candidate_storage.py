from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import candidate_storage as storage
import test_release_assets as native


class SDKError(Exception):
    def __init__(self, code, status=403):
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}
        super().__init__("SECRET-SENTINEL must not appear in diagnostics")


class SyntheticS3:
    """S3 API double, no sockets/credentials; exercises real streaming adapter."""
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.failures = []
        self.corrupt = None
        self.versioning = {}
        self.public_block = {key: True for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")}
        self.rules = [{"ID": "expire-candidates", "Status": "Enabled", "Filter": {"Prefix": "web-candidates/"}, "Expiration": {"Days": 14}}]

    def get_bucket_lifecycle_configuration(self, **kwargs):
        self.calls.append(("lifecycle", kwargs))
        return {"Rules": self.rules}

    def get_bucket_versioning(self, **kwargs):
        return self.versioning

    def get_public_access_block(self, **kwargs):
        return {"PublicAccessBlockConfiguration": self.public_block}

    def put_object(self, **kwargs):
        self.calls.append(("put", {key: value for key, value in kwargs.items() if key != "Body"}))
        if self.failures:
            raise self.failures.pop(0)
        key = (kwargs["Bucket"], kwargs["Key"])
        if key in self.objects:
            raise SDKError("PreconditionFailed", 412)
        content = kwargs["Body"].read()
        if len(content) != kwargs["ContentLength"]:
            raise AssertionError("wrong upload byte count")
        self.objects[key] = content
        return {}

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        key = (kwargs["Bucket"], kwargs["Key"])
        if key not in self.objects:
            raise SDKError("NoSuchKey", 404)
        value = self.objects[key]
        if kwargs["Key"].endswith(self.corrupt or "\0"):
            value = (b"x" if value[:1] != b"x" else b"y") + value[1:]
        return {"Body": io.BytesIO(value), "ContentLength": len(value)}


class CandidateStorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = native.ReleaseAssetVerificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.binding = storage.identity(self.fixture.repository, self.fixture.selector, self.fixture.reviewed_sha, "123", "2")
        self.github = copy.deepcopy(storage.DEFAULT_POLICY)
        self.s3 = {"schema_version": 1, "release_candidate": {"transport": "s3-private", "retention_days": 14, "s3": {
            "profile": "s3", "endpoint_url": "https://s3.example.invalid", "region": "example-1", "bucket": "project-private",
            "prefix": "web-candidates", "addressing_style": "path", "lifecycle_rule_id": "expire-candidates"}}}
        self.now = 1_800_000_000

    def sealed(self, selection, name="sealed"):
        package = self.root / name
        sha = storage.seal(self.fixture.assets, package, selection, self.binding, now=self.now)
        return package, sha

    def test_same_native_package_bytes_and_verifier_across_both_transports(self):
        for transport, selection in (("github", self.github), ("s3", self.s3)):
            with self.subTest(transport=transport):
                package, sha = self.sealed(selection, transport)
                received = self.root / (transport + "-received")
                if transport == "github":
                    shutil.copytree(package, received)  # Actions v4 directory transfer
                else:
                    client = SyntheticS3()
                    storage.s3_upload(package, selection, self.binding, sha, client=client, now=self.now)
                    storage.s3_download(received, selection, self.binding, sha, (package / storage.ENVELOPE).stat().st_size, client=client, now=self.now)
                    self.assertTrue(all("/123/2/" in key for _, key in client.objects))
                    self.assertEqual(len(client.objects), 6)
                    self.assertTrue(all(call[1]["IfNoneMatch"] == "*" and "ACL" not in call[1] for call in client.calls if call[0] == "put"))
                storage.verify(received, selection, self.binding, sha, now=self.now)
                native.verify_release_assets.compare_asset_directories(self.fixture.assets, received / "release-assets")
                args = self.fixture.arguments()
                args.assets = received / "release-assets"
                self.assertTrue(native.verify_release_assets.verify(args)["ok"])
                self.assertEqual((self.fixture.assets / "publication.json").read_bytes(), (args.assets / "publication.json").read_bytes())

    def test_default_policy_is_github_without_sdk_or_credentials(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(storage, "sdk_client", side_effect=AssertionError("unexpected S3")):
            self.assertEqual(storage.project_policy(self.root), self.github)
            package, sha = self.sealed(self.github)
            self.assertEqual(storage.verify(package, self.github, self.binding, sha, now=self.now)["identity"], self.binding)

    def test_fail_closed_for_absent_corrupt_size_policy_or_build_mismatch(self):
        package, sha = self.sealed(self.github)
        for change in ("absent", "corrupt", "size", "extra", "policy", "run", "attempt", "source", "sha"):
            with self.subTest(change=change):
                received = self.root / ("bad-" + change)
                shutil.copytree(package, received)
                selection, binding, expected = copy.deepcopy(self.github), self.binding.copy(), sha
                pdf = received / "release-assets/manual-en.pdf"
                if change == "absent":
                    pdf.unlink()
                elif change == "corrupt":
                    pdf.write_bytes(b"bad\n")
                elif change == "size":
                    pdf.write_bytes(b"pdf\nmore")
                elif change == "extra":
                    (received / "release-assets/unlisted.pdf").write_bytes(b"unknown")
                elif change == "policy":
                    selection["release_candidate"]["retention_days"] = 7
                elif change == "run":
                    binding["run_id"] = "124"
                elif change == "attempt":
                    binding["run_attempt"] = "1"
                elif change == "source":
                    binding["source_sha"] = "9" * 40
                else:
                    expected = "0" * 64
                with self.assertRaises(storage.StorageError):
                    storage.verify(received, selection, binding, expected, now=self.now)

    def test_immutable_outputs_and_symlinks_are_refused(self):
        package, _ = self.sealed(self.github)
        with self.assertRaises(storage.StorageError):
            storage.seal(self.fixture.assets, package, self.github, self.binding, now=self.now)
        (self.root / "alias").symlink_to(package, target_is_directory=True)
        with self.assertRaises(storage.StorageError):
            storage.seal(self.fixture.assets, self.root / "alias/new", self.github, self.binding, now=self.now)
        pdf = self.fixture.assets / "manual-en.pdf"
        pdf.unlink()
        pdf.symlink_to(self.fixture.site / "assets/pdf/manual-en.pdf")
        with self.assertRaises(storage.StorageError):
            self.sealed(self.github, "symlink-payload")

    def test_retention_expiry_refuses_both_transports_without_reselecting(self):
        for selection in (self.github, self.s3):
            with self.subTest(selection=selection["release_candidate"]["transport"]):
                package, sha = self.sealed(selection, selection["release_candidate"]["transport"])
                with self.assertRaisesRegex(storage.StorageError, "retention"):
                    storage.verify(package, selection, self.binding, sha, now=self.now + 14 * 86400)
                if selection == self.s3:
                    client = SyntheticS3()
                    storage.s3_upload(package, selection, self.binding, sha, client=client, now=self.now)
                    client.calls.clear()
                    with self.assertRaisesRegex(storage.StorageError, "retention"):
                        storage.s3_download(self.root / "expired", selection, self.binding, sha, (package / storage.ENVELOPE).stat().st_size, client=client, now=self.now + 14 * 86400)
                    self.assertTrue(all(call[1]["Key"].endswith(storage.ENVELOPE) for call in client.calls if call[0] == "get"))
        for days in (0, 15, True, "14"):
            invalid = copy.deepcopy(self.github)
            invalid["release_candidate"]["retention_days"] = days
            with self.assertRaises(storage.StorageError):
                storage.policy(invalid)

    def test_s3_lifecycle_is_required_and_never_mutated(self):
        package, sha = self.sealed(self.s3)
        for mutation in ("absent", "disabled", "public-prefix", "unbounded", "versioned", "public"):
            with self.subTest(mutation=mutation):
                client = SyntheticS3()
                if mutation == "absent":
                    client.rules = []
                elif mutation == "disabled":
                    client.rules[0]["Status"] = "Disabled"
                elif mutation == "public-prefix":
                    client.rules[0]["Filter"] = {"Prefix": "public/"}
                elif mutation == "unbounded":
                    client.rules[0]["Expiration"] = {"Days": 365}
                elif mutation == "versioned":
                    client.versioning = {"Status": "Enabled"}
                else:
                    client.public_block["BlockPublicPolicy"] = False
                with self.assertRaisesRegex(storage.StorageError, "lifecycle|expiration|public-access"):
                    storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
                self.assertEqual(client.objects, {})
        client = SyntheticS3()
        client.versioning = {"Status": "Enabled"}
        client.rules[0]["NoncurrentVersionExpiration"] = {"NoncurrentDays": 14}
        storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)

    def test_s3_absent_corrupt_auth_error_and_no_overwrite(self):
        package, sha = self.sealed(self.s3)
        client = SyntheticS3()
        with self.assertRaises(storage.StorageError):
            storage.s3_download(self.root / "absent", self.s3, self.binding, sha, 123, client=client, now=self.now)
        client.failures = [SDKError("AccessDenied")]
        with self.assertRaises(storage.StorageError) as error:
            storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
        self.assertNotIn("SECRET-SENTINEL", str(error.exception))
        self.assertEqual(len([item for item in client.calls if item[0] == "put"]), 1)
        storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
        before = copy.deepcopy(client.objects)
        with self.assertRaises(storage.StorageError):
            storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
        self.assertEqual(before, client.objects)
        client.corrupt = "manual-en.pdf"
        with self.assertRaisesRegex(storage.StorageError, "SHA-256"):
            storage.s3_download(self.root / "corrupt", self.s3, self.binding, sha, (package / storage.ENVELOPE).stat().st_size, client=client, now=self.now)
        self.assertFalse((self.root / "corrupt").exists())

    def test_transient_failures_retry_at_most_three_times(self):
        package, sha = self.sealed(self.s3)
        client = SyntheticS3()
        client.failures = [SDKError("SlowDown", 503), SDKError("InternalError", 500)]
        with patch.object(storage.time, "sleep"):
            storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
        self.assertEqual(len([item for item in client.calls if item[0] == "put"]), 8)
        client = SyntheticS3()
        client.failures = [SDKError("SlowDown", 503)] * 5
        with patch.object(storage.time, "sleep"), self.assertRaises(storage.StorageError):
            storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
        self.assertEqual(len([item for item in client.calls if item[0] == "put"]), 3)

    def test_s4_is_only_an_s3_profile_and_credentials_never_use_host_defaults(self):
        selection = copy.deepcopy(self.s3)
        selection["release_candidate"]["s3"]["profile"] = "s4"
        self.assertEqual(storage.policy(selection)["release_candidate"]["transport"], "s3-private")
        with patch.dict(os.environ, {"AWS_PROFILE": "personal-host"}, clear=True), self.assertRaisesRegex(storage.StorageError, "CI credentials"):
            storage.sdk_client(selection)

    def test_strict_policy_rejects_credentials_new_artifact_classes_and_public_endpoints(self):
        invalids = []
        for field, value in (("endpoint_url", "http://public.invalid"), ("endpoint_url", "https://key:secret@example.invalid"), ("prefix", "../public"), ("profile", "mega"), ("access_key", "secret")):
            value_policy = copy.deepcopy(self.s3)
            value_policy["release_candidate"]["s3"][field] = value
            invalids.append(value_policy)
        invalids.append({**self.github, "publication.json": {}})
        for value in invalids:
            with self.subTest(value=value), self.assertRaises(storage.StorageError):
                storage.policy(value)
        with self.assertRaises(storage.StorageError):
            storage.decode(b'{"schema_version":1,"schema_version":1}')

    def test_package_schema_scaffold_and_optional_sdk_are_distributed(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "src/unaltraweb_mcp/artifact-storage-v1.schema.json").read_bytes())
        self.assertEqual(schema["properties"]["schema_version"], {"const": 1})
        self.assertFalse(schema["additionalProperties"])
        scaffold = root / "src/unaltraweb_mcp/scaffolds/common/.unaltraweb/artifact-storage.json"
        self.assertEqual(storage.policy(json.loads(scaffold.read_bytes())), self.github)
        metadata = (root / "pyproject.toml").read_text()
        self.assertIn('artifact-storage = ["boto3==1.40.75"', metadata)
        self.assertIn('"artifact-storage-v1.schema.json"', metadata)
        self.assertIn('"scaffolds/common/.unaltraweb/*.json"', metadata)

    @unittest.skipUnless(importlib.util.find_spec("boto3"), "optional pinned S3 SDK is not installed")
    def test_real_public_sdk_model_accepts_create_only_streaming_requests_without_network(self):
        from botocore.stub import ANY, Stubber

        package, sha = self.sealed(self.s3)
        with patch.dict(os.environ, {"UNALTRAWEB_S3_ACCESS_KEY_ID": "synthetic-ci-id", "UNALTRAWEB_S3_SECRET_ACCESS_KEY": "synthetic-ci-secret"}, clear=True):
            client = storage.sdk_client(self.s3)
        envelope = storage.verify(package, self.s3, self.binding, sha, now=self.now)
        bucket = "project-private"
        prefix = "web-candidates/release_candidate/example/manual/v2026.09/" + self.fixture.reviewed_sha + "/123/2/"
        with Stubber(client) as stub:
            stub.add_response("get_public_access_block", {"PublicAccessBlockConfiguration": SyntheticS3().public_block}, {"Bucket": bucket})
            stub.add_response("get_bucket_lifecycle_configuration", {"Rules": SyntheticS3().rules}, {"Bucket": bucket})
            stub.add_response("get_bucket_versioning", {}, {"Bucket": bucket})
            for name, record in [*envelope["files"].items(), (storage.ENVELOPE, storage.file_record(package / storage.ENVELOPE))]:
                content = (package / storage.ENVELOPE if name == storage.ENVELOPE else package / "release-assets" / name).read_bytes()
                stub.add_response("put_object", {}, {"Bucket": bucket, "Key": prefix + name, "Body": ANY,
                                                   "ContentLength": len(content), "IfNoneMatch": "*", "Metadata": {"sha256": record["sha256"]}})
                stub.add_response("get_object", {"Body": io.BytesIO(content), "ContentLength": len(content)}, {"Bucket": bucket, "Key": prefix + name})
            storage.s3_upload(package, self.s3, self.binding, sha, client=client, now=self.now)
            stub.assert_no_pending_responses()


if __name__ == "__main__":
    unittest.main()
