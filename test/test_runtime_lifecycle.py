from __future__ import annotations

import copy
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

    def exited_resource(self):
        return {**self.resource("stdio", running=False, cid=self.parent),
                "status": "exited", "daemon_init_pid": 0, "image_id": "sha256:" + "e" * 64,
                "mounts": [
                    {"Type": "bind", "Source": self.project, "Destination": self.project,
                     "RW": True, "Mode": "", "Propagation": "rprivate",
                     "Extra": {"flags": ["first", "second"]}},
                    {"Type": "bind", "Source": "/run/docker.sock", "Destination": "/var/run/docker.sock",
                     "RW": True, "Mode": "", "Propagation": "rprivate"},
                ]}

    def reap_exited(self, before, current, *, removal=None, remains=False):
        removal = removal or SimpleNamespace(returncode=0, timed_out=False, stdout_truncated=False,
                                             stderr_truncated=False)
        with patch.object(lifecycle, "session_networks", return_value=[]), \
                patch.object(lifecycle, "session_containers", side_effect=[[before], []]), \
                patch.object(lifecycle, "inspect_container", side_effect=[before, current, current if remains else None]) as inspect, \
                patch.object(lifecycle, "docker", return_value=removal) as docker:
            value = self.status(reap=True)
        return value, docker, inspect

    def test_exited_mount_order_is_irrelevant_without_losing_duplicate_records(self):
        before = self.exited_resource()
        before["mounts"].append(copy.deepcopy(before["mounts"][0]))
        current = copy.deepcopy(before)
        current["mounts"] = [current["mounts"][1], current["mounts"][2], current["mounts"][0]]
        originals = copy.deepcopy((before, current))
        value, docker, inspect = self.reap_exited(before, current)
        self.assertTrue(value["ok"], value)
        self.assertEqual(value["state"], "stopped")
        self.assertTrue(value["resources_released"])
        docker.assert_called_once_with(["rm", self.parent])
        self.assertEqual(inspect.call_count, 3, "Exact CID absence must be checked after removal")
        self.assertEqual((before, current), originals, "Comparison must not rewrite observations")

    def test_exited_mount_record_changes_are_refused(self):
        changes = {
            "Source": "/tmp/other-consumer", "Destination": "/different-target", "Type": "volume",
            "RW": False, "Mode": "ro", "Propagation": "shared", "Name": "new-field",
            "Extra": {"flags": ["second", "first"]},
        }
        for key, changed in changes.items():
            with self.subTest(field=key):
                before = self.exited_resource()
                current = copy.deepcopy(before)
                current["mounts"][0][key] = changed
                value, docker, _ = self.reap_exited(before, current)
                self.assertFalse(value["resources_released"])
                self.assertIn("changed during recovery", value["error"])
                docker.assert_not_called()
        for change in ("field-removed", "boolean-type", "duplicate-added", "record-removed", "multiplicity-changed"):
            with self.subTest(change=change):
                before = self.exited_resource()
                before["mounts"].append(copy.deepcopy(before["mounts"][0]))
                current = copy.deepcopy(before)
                if change == "field-removed":
                    del current["mounts"][0]["Propagation"]
                elif change == "boolean-type":
                    current["mounts"][0]["RW"] = 1
                elif change == "duplicate-added":
                    current["mounts"].append(copy.deepcopy(current["mounts"][0]))
                elif change == "record-removed":
                    current["mounts"].pop()
                else:
                    current["mounts"][2] = copy.deepcopy(current["mounts"][1])
                value, docker, _ = self.reap_exited(before, current)
                self.assertIn("changed during recovery", value["error"])
                docker.assert_not_called()

    def test_exited_identity_and_state_changes_are_refused(self):
        changes = {"id": "f" * 64, "factory": "other", "role": "manual-pdf", "project_id": "0" * 16,
                   "session_id": "0" * 32, "running": True, "status": "running", "daemon_init_pid": 123,
                   "image_id": "sha256:" + "f" * 64, "additional_observation": "changed"}
        for key, changed in changes.items():
            with self.subTest(field=key):
                before = self.exited_resource()
                current = copy.deepcopy(before)
                current[key] = changed
                value, docker, _ = self.reap_exited(before, current)
                self.assertIn("changed during recovery", value["error"])
                docker.assert_not_called()

    def test_exited_malformed_mount_observation_is_refused(self):
        for mounts in (None, {}, ["not-a-record"]):
            with self.subTest(mounts=mounts):
                before = self.exited_resource()
                current = copy.deepcopy(before)
                before["mounts"] = current["mounts"] = mounts
                value, docker, _ = self.reap_exited(before, current)
                self.assertFalse(value["ok"])
                self.assertFalse(value["resources_released"])
                docker.assert_not_called()

    def test_exited_removal_failure_is_distinct_from_changed_identity(self):
        for failure in ({"returncode": 1}, {"returncode": 124, "timed_out": True},
                        {"stdout_truncated": True}, {"stderr_truncated": True}):
            with self.subTest(failure=failure):
                observation = self.exited_resource()
                result = SimpleNamespace(**{**dict(returncode=0, timed_out=False, stdout_truncated=False,
                                                   stderr_truncated=False), **failure})
                value, docker, _ = self.reap_exited(observation, copy.deepcopy(observation), removal=result)
                self.assertFalse(value["resources_released"])
                self.assertIn("removal failed", value["error"])
                self.assertNotIn("changed", value["error"])
                docker.assert_called_once_with(["rm", self.parent])

    def test_exited_removal_success_requires_exact_cid_absence(self):
        observation = self.exited_resource()
        value, docker, _ = self.reap_exited(observation, copy.deepcopy(observation), remains=True)
        self.assertFalse(value["resources_released"])
        self.assertIn("removal is not confirmed", value["error"])
        docker.assert_called_once_with(["rm", self.parent])

    def test_exited_disappearance_before_removal_needs_no_rm(self):
        value, docker, _ = self.reap_exited(self.exited_resource(), None)
        self.assertTrue(value["resources_released"])
        docker.assert_not_called()
