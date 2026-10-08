from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from unaltraweb_mcp import runtime_lifecycle as lifecycle


class SessionLifecycleTests(unittest.TestCase):
    def test_unlabelled_local_image_retains_exact_identity_without_claiming_provenance(self):
        image_id = "sha256:" + "a" * 64
        observed = {"id": image_id, "repo_digests": [], "source_revision": None,
                    "os": "linux", "architecture": "amd64"}
        with patch.object(lifecycle, "_inspect", return_value=observed):
            result = lifecycle.inspect_image("unaltraweb-manual-pdf:dev", image_id)
            self.assertEqual("matched", result["state"])
            self.assertEqual(image_id, result["observed_image_id"])
            self.assertIsNone(result["source_revision"])
            self.assertEqual("mismatch", lifecycle.inspect_image("unaltraweb-manual-pdf:dev", "sha256:" + "b" * 64)["state"])

    def test_missing_daemon_socket_is_not_container_absence(self):
        result = SimpleNamespace(returncode=1, stdout="", stderr="dial unix /missing/docker.sock: no such file or directory",
                                 timed_out=False, stdout_truncated=False, stderr_truncated=False)
        with patch.object(lifecycle, "docker", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                lifecycle.inspect_container("a" * 64)

    def setUp(self):
        self.project = "/tmp/d0-consumer"
        self.project_id = hashlib.sha256(self.project.encode()).hexdigest()[:16]
        self.session = "a" * 32
        self.parent = "b" * 64

    def resource(self, role, *, running=True, cid=None):
        return {"id": cid or "c" * 64, "factory": "unaltraweb", "role": role, "project_id": self.project_id,
                "session_id": self.session, "running": running}

    def status(self, **kwargs):
        return lifecycle.session_status(self.project, self.session, self.parent, **kwargs)

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers")
    @patch.object(lifecycle, "inspect_container")
    def test_live_backend_is_not_removed_by_reap(self, inspect, resources, networks):
        parent = self.resource("stdio", cid=self.parent)
        inspect.return_value = parent
        resources.return_value = [parent, self.resource("preview")]
        with patch.object(lifecycle, "docker", side_effect=AssertionError("must not stop a live backend")):
            value = self.status(reap=True)
        self.assertEqual(value["state"], "connected")
        self.assertFalse(value["resources_released"])

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers")
    @patch.object(lifecycle, "inspect_container", return_value=None)
    def test_orphan_running_job_is_preserved(self, inspect, resources, networks):
        resources.return_value = [self.resource("manual-pdf")]
        with patch.object(lifecycle, "docker", side_effect=AssertionError("must preserve a busy job")):
            value = self.status(reap=True)
        self.assertEqual(value["state"], "busy")
        self.assertFalse(value["resources_released"])

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers")
    @patch.object(lifecycle, "inspect_container", return_value=None)
    def test_storage_workers_require_their_private_manager_even_when_stopped(self, inspect, resources, networks):
        for running in (True, False):
            resources.return_value = [self.resource("job-storage", running=running)]
            with patch.object(lifecycle, "docker", side_effect=AssertionError("W1 journal must own recovery")):
                value = self.status(reap=True)
            self.assertTrue(value["ok"], value)
            self.assertEqual(value["state"], "busy" if running else "orphaned")
            self.assertFalse(value["resources_released"])

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers", return_value=[])
    @patch.object(lifecycle, "inspect_container", return_value=None)
    def test_absence_is_required_for_release(self, inspect, resources, networks):
        self.assertTrue(self.status()["resources_released"])
        inspect.side_effect = RuntimeError("daemon unavailable")
        self.assertEqual(self.status()["state"], "unknown")
        self.assertFalse(self.status()["resources_released"])

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers")
    @patch.object(lifecycle, "inspect_container", return_value=None)
    def test_foreign_identity_is_not_cleanup_authority(self, inspect, resources, networks):
        foreign = self.resource("preview")
        foreign["session_id"] = "d" * 32
        resources.return_value = [foreign]
        with patch.object(lifecycle, "docker", side_effect=AssertionError("foreign removal")):
            self.assertFalse(self.status(reap=True)["ok"])

    @patch.object(lifecycle, "session_networks", return_value=[])
    @patch.object(lifecycle, "session_containers")
    @patch.object(lifecycle, "inspect_container", return_value=None)
    def test_only_exact_orphan_idle_resources_are_recovered(self, inspect, resources, networks):
        preview = self.resource("preview")
        resources.side_effect = [[preview], []]
        with patch.object(lifecycle, "remove_idle_container") as remove:
            value = self.status(reap=True)
        remove.assert_called_once_with(preview["id"], self.project_id, self.session)
        self.assertTrue(value["resources_released"])
