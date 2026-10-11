from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from scripts import check_practice_verifier_runtime as checker
from unaltraweb_mcp import practice_verifier as bridge
from unaltraweb_mcp.artifact_handoff_v1 import HandoffError
from unaltraweb_mcp.distribution import distribution_contract


def process(stdout="", **changes):
    return SimpleNamespace(**{**dict(stdout=stdout, stderr="", returncode=0, timed_out=False,
                                    stdout_truncated=False, stderr_truncated=False), **changes})


class PrivateVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.contract = bridge.runtime_contract()
        self.image = self.contract["controller"]["image_id"]
        self.observed = {"state": "matched", "reference": self.image, "expected_image_id": self.image,
                         "observed_image_id": self.image, "os": "linux", "architecture": "amd64",
                         "source_revision": None, "registry_digests": []}
        self.env = self.enter_patch(patch.dict(os.environ, {}, clear=True))
        self.enter_patch(patch("unaltraweb_mcp.runtime_identity.active_runtime", return_value=None))

    def enter_patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def schema(self, profile="qgis-practice-v2"):
        provider = self.contract["provider"]
        return {"ok": True, "profile": profile, "schema_sha256": self.contract["profiles"][profile],
                "installed_package": {"name": provider["name"], "version": provider["version"], "revision": provider["installed_revision"]}}

    def test_missing_or_mismatched_private_image_blocks_without_acquisition(self):
        for state in ("missing", "mismatch", "unknown"):
            with self.subTest(state=state), patch.object(bridge.lifecycle, "inspect_image", return_value={"state": state}), \
                    patch.object(bridge, "run_process") as run, self.assertRaisesRegex(RuntimeError, "hub preparation"):
                bridge.call(self.project, "schema", profile="qgis-practice-v2")
            run.assert_not_called()

    def test_check_runs_only_inside_private_image_with_readonly_mount_and_native_limits(self):
        cid = "a"*64
        report = {"ok": True, "profile": "qgis-practice-v2", "closure": []}
        with patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                patch.object(bridge.lifecycle, "inspect_container", return_value=None), \
                patch.object(bridge, "run_process", side_effect=[process(cid+"\n"), process(json.dumps(report))]) as run:
            result = bridge.call(self.project, "check", bundle="sandbox/bundle.json", sha256="b"*64, selected=["initial-project"])
        create = run.call_args_list[0].args[0]
        self.assertEqual(create[:2], ["docker", "create"])
        self.assertEqual(create[create.index("--pull")+1], "never")
        self.assertEqual(create[create.index("--network")+1], "none")
        for flag, expected in (("--cpus", "2"), ("--memory", "4g"), ("--pids-limit", "512")):
            self.assertEqual(create[create.index(flag)+1], expected)
        self.assertIn("--read-only", create)
        self.assertIn(self.image, create)
        self.assertIn("-I", create)
        self.assertIn("veure_qgis_mcp.cli", create)
        self.assertFalse(any("docker.sock" in value or "TOKEN=" in value or "pip" == value for value in create))
        mounts = [create[index+1] for index, value in enumerate(create) if value == "--mount"]
        self.assertEqual(len(mounts), 1)
        self.assertIn("readonly", mounts[0])
        self.assertEqual(run.call_args_list[1].kwargs["timeout_seconds"], 120)
        self.assertEqual(result["result"], report)
        self.assertTrue(result["origin"]["execution"]["cleanup"]["resources_released"])
        self.assertIsNone(result["origin"]["controller"]["source_revision"])

    def test_schema_has_no_consumer_mount_and_keeps_release_wheel_separate(self):
        with patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                patch.object(bridge.lifecycle, "inspect_container", return_value=None), \
                patch.object(bridge, "run_process", side_effect=[process("a"*64), process(json.dumps(self.schema()))]) as run:
            value = bridge.call(self.project, "schema", profile="qgis-practice-v2")
        self.assertNotIn("--mount", run.call_args_list[0].args[0])
        self.assertNotIn("direct_url", json.dumps(value))
        self.assertNotEqual(value["result"]["installed_package"]["revision"], value["origin"]["release"]["practice_producer_revision"])
        self.assertIn("not a local wheel-install observation", value["origin"]["release"]["basis"])

    def test_wrong_native_schema_or_source_is_refused(self):
        for key, bad in (("schema_sha256", "0"*64), ("profile", "qgis-practice-v1")):
            value = self.schema()
            value[key] = bad
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "accepted image contract"):
                bridge.validate_schema_identity(value, self.contract, "qgis-practice-v2")
        value = self.schema()
        value["installed_package"]["revision"] = self.contract["release"]["practice_producer_revision"]
        with self.assertRaises(ValueError):
            bridge.validate_schema_identity(value, self.contract, "qgis-practice-v2")

    def test_timeout_uses_existing_exact_worker_cleanup_and_is_not_success(self):
        cid = "a"*64
        with patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                patch.object(bridge.lifecycle, "inspect_container", side_effect=[{"id": cid}, None]), \
                patch.object(bridge, "run_process", side_effect=[process(cid), process(returncode=124, timed_out=True)]), \
                patch("unaltraweb_mcp.site_tools._cleanup_timed_out_workers", return_value={"ok": True, "removed": [cid]}) as cleanup, \
                self.assertRaisesRegex(RuntimeError, "exceeded its bound"):
            bridge.call(self.project, "schema", profile="qgis-practice-v2")
        self.assertEqual(cleanup.call_args.kwargs["role"], "practice-verifier")
        self.assertRegex(cleanup.call_args.kwargs["token"], r"^[0-9a-f]{32}$")

    def test_truncated_output_or_unconfirmed_teardown_cannot_pass(self):
        for truncated, left in ((True, None), (False, {"id": "a"*64})):
            with self.subTest(truncated=truncated, left=left), \
                    patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                    patch.object(bridge.lifecycle, "inspect_container", side_effect=[None, left]), \
                    patch.object(bridge, "run_process", side_effect=[process("a"*64), process(json.dumps(self.schema()), stdout_truncated=truncated)]), \
                    self.assertRaises(RuntimeError):
                bridge.call(self.project, "schema", profile="qgis-practice-v2")

    def test_operation_and_consumer_mapping_cannot_select_arbitrary_execution(self):
        with patch.object(bridge, "run_process") as run:
            for request in (("exec", {}), ("check", {"bundle": "../secret", "sha256": "a"*64, "selected": ["x"]}),
                            ("check", {"bundle": "bundle.json", "sha256": "a"*64, "selected": ["--help"]})):
                with self.subTest(request=request), self.assertRaises((ValueError, HandoffError)):
                    bridge.call(self.project, request[0], **request[1])
            with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_ROOT": "/different-consumer"}), self.assertRaisesRegex(ValueError, "another or unknown"):
                bridge.call(self.project, "schema", profile="qgis-practice-v1")
        run.assert_not_called()

    def test_reopen_requires_prepared_engine_and_is_explicitly_separate_from_readonly_check(self):
        with patch.object(bridge.lifecycle, "inspect_image", side_effect=[self.observed, {"state": "missing"}]), \
                patch.object(bridge, "run_process") as run, self.assertRaisesRegex(RuntimeError, "engine is not prepared"):
            bridge.call(self.project, "reopen", bundle="bundle/bundle.json", sha256="a"*64,
                        selected=["initial-project"], output="new-proof")
        run.assert_not_called()

    def test_operator_override_cannot_silently_select_another_implementation(self):
        with patch.dict(os.environ, {bridge.IMAGE_ENV: "mutable:latest"}), patch.object(bridge, "run_process") as run, \
                self.assertRaisesRegex(ValueError, "accepted prepared-image"):
            bridge.call(self.project, "schema", profile="qgis-practice-v1")
        run.assert_not_called()

    def test_public_check_is_metadata_only_and_private_checks_are_explicit_not_run(self):
        self.assertEqual(checker.publication_errors(distribution_contract()), [])
        stdout = io.StringIO()
        with patch.object(bridge, "call", side_effect=AssertionError("Public CI must not execute private code")), redirect_stdout(stdout):
            self.assertEqual(checker.main([]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["private_checks"]["state"], "not_run")
