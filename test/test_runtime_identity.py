from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp import __version__
from unaltraweb_mcp.runtime_identity import RuntimeIdentity


class LiveIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.project = root / "private consumer"
        self.project.mkdir()
        self.package = root / "package"
        self.package.mkdir()
        (self.package / "engine.py").write_text("# retained startup code\n")
        (self.package / "component-contract.json").write_text(json.dumps({"release": {"version": __version__}}))
        patcher = patch("unaltraweb_mcp.runtime_lifecycle.inspect_image", return_value={"state": "missing", "observed_image_id": None})
        patcher.start()
        self.addCleanup(patcher.stop)

    def runtime(self, **env):
        return RuntimeIdentity(self.project, self.package, environment=env, package_root=self.package)

    def test_live_process_and_startup_identity_are_stable_not_current_metadata(self):
        runtime = self.runtime()
        before = runtime.observe()
        self.assertEqual(before["process"]["pid"], os.getpid())
        self.assertEqual(before["package"]["loaded_version"], __version__)
        (self.package / "component-contract.json").write_text(json.dumps({"release": {"version": "99.0.0"}}))
        after = runtime.observe()
        self.assertEqual(before["instance_id"], after["instance_id"])
        self.assertEqual(before["started_at"], after["started_at"])
        self.assertEqual(before["package"]["loaded_revision"], after["package"]["loaded_revision"])
        self.assertEqual(after["package"]["loaded_version"], __version__)
        self.assertEqual(after["package"]["current_version"], "99.0.0")
        self.assertTrue(after["package"]["drift"])
        self.assertNotEqual(runtime.instance_id, self.runtime().instance_id)

    def test_consumer_content_is_never_read(self):
        (self.project / "secret.json").write_text('{"private": "never report this"}')
        runtime = self.runtime()
        original = Path.iterdir
        def guarded(path):
            if path == self.project:
                raise AssertionError("Consumer inventory is not identity")
            return original(path)
        with patch.object(Path, "iterdir", guarded):
            result = runtime.observe()
        self.assertNotIn("never report this", json.dumps(result))
        self.assertEqual(result["binding"]["consumer"], str(self.project))

    def test_secret_environment_values_are_not_inspected_or_retained(self):
        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key == "SECRET_TOKEN":
                    raise AssertionError("Identity must not read arbitrary environment values")
                return super().__getitem__(key)
        values = GuardedEnvironment(SECRET_TOKEN="private")
        runtime = RuntimeIdentity(self.project, self.package, environment=values, package_root=self.package)
        self.assertNotIn("SECRET_TOKEN", runtime.env)

    def test_legacy_receipt_points_are_exact_not_ranges(self):
        from unaltraweb_mcp.companion_compatibility import accepts_receipt
        selected = {"version": "0.5.1", "release": "v0.5.1"}
        self.assertTrue(accepts_receipt("vegavisuals", "0.4.0", "v0.4.0", selected))
        self.assertTrue(accepts_receipt("vegavisuals", "0.5.1", "v0.5.1", selected))
        self.assertFalse(accepts_receipt("vegavisuals", "0.5.0", "v0.5.0", selected))
        self.assertFalse(accepts_receipt("vegavisuals", "0.4.0", "v0.5.1", selected))
        self.assertFalse(accepts_receipt("vegavisuals", {}, "v0.5.1", selected))

    def test_current_code_symlinks_are_unavailable_not_followed(self):
        secret = self.project / "secret.json"
        secret.write_text('{"release": {"version": "private identity"}}')
        runtime = self.runtime()
        contract = self.package / "component-contract.json"
        contract.unlink()
        contract.symlink_to(secret)
        value = runtime.observe()
        self.assertFalse(value["package"]["current"]["available"])
        self.assertIsNone(value["package"]["current_version"])
        self.assertNotIn("private identity", json.dumps(value))

    def test_startup_worker_and_consumer_mapping_are_fixed(self):
        env = {"MANUAL_PDF_IMAGE": "sha256:" + "1" * 64}
        runtime = self.runtime(**env)
        env["MANUAL_PDF_IMAGE"] = "wrong:later"
        with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_ROOT": "/wrong", "MANUAL_PDF_IMAGE": "wrong:later"}):
            value = runtime.observe()
        self.assertEqual(value["binding"]["daemon_host_project"], str(self.project))
        self.assertEqual(runtime.workers["manual_pdf"]["reference"], "sha256:" + "1" * 64)

    def test_busy_drain_refuses_new_work_and_does_not_claim_release(self):
        runtime = self.runtime()
        self.assertFalse(runtime.drain()["ok"])
        with runtime.job("build_site"):
            self.assertEqual(runtime.observe()["lifecycle"]["state"], "busy")
            with self.assertRaisesRegex(RuntimeError, "busy"):
                with runtime.job("another"):
                    pass
            result = runtime.drain(True)
            self.assertEqual(result["active_operations"], 1)
            self.assertFalse(result["resources_released"])
            with self.assertRaisesRegex(RuntimeError, "active"):
                runtime.close()
        with self.assertRaisesRegex(RuntimeError, "draining"):
            with runtime.job("new_web"):
                pass
        runtime.close()

    def test_namespace_container_mapping_is_observed_not_pid_equality(self):
        session = "a" * 32
        image = "sha256:" + "b" * 64
        runtime = self.runtime(UNALTRAWEB_RUNTIME_SESSION=session, UNALTRAWEB_MCP_IMAGE=image, UNALTRAWEB_EXPECTED_IMAGE_ID=image)
        container = {"id": "c" * 64, "image_id": image, "factory": "unaltraweb", "role": "stdio",
                     "project_id": runtime.project_id, "session_id": session, "daemon_init_pid": os.getpid() + 10000,
                     "mounts": [{"Source": str(self.project), "Destination": str(self.project)}]}
        with patch("unaltraweb_mcp.runtime_lifecycle.inspect_container", return_value=container):
            result = runtime.observe()
        self.assertEqual(result["runtime"]["container"]["state"], "matched")
        self.assertNotEqual(result["runtime"]["container"]["daemon_init_pid"], result["process"]["pid"])
        container["image_id"] = "sha256:" + "0" * 64
        with patch("unaltraweb_mcp.runtime_lifecycle.inspect_container", return_value=container):
            self.assertEqual(runtime.observe()["runtime"]["container"]["state"], "mismatch")
