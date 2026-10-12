from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from scripts import check_practice_verifier_runtime as checker
from unaltraweb_mcp import practice_verifier as bridge
from unaltraweb_mcp import site_tools
from unaltraweb_mcp.artifact_handoff_v1 import HandoffError
from unaltraweb_mcp.distribution import distribution_contract


def process(stdout="", **changes):
    return SimpleNamespace(**{**dict(stdout=stdout, stderr="", returncode=0, timed_out=False,
                                     stdout_truncated=False, stderr_truncated=False), **changes})


class VerifierDaemon:
    """Bounded daemon double: allocation and the create reply are independent."""
    cid = "a" * 64

    def __init__(self, fixture, reply, *, allocate=True):
        self.fixture, self.reply, self.allocate = fixture, reply, allocate
        self.containers, self.calls = {}, []
        self.inventory_reply = self.inspect_reply = self.remove_reply = None
        self.inspect_changes = {}
        self.keep_removed = False
        self.start_reply = process(json.dumps(fixture.schema()))

    def run(self, command, *, timeout_seconds, output_limit=128 * 1024, **kwargs):
        assert 0 < timeout_seconds <= 300 and 0 < output_limit <= 1024 * 1024
        assert len(self.calls) < 24, "Unbounded Docker retry"
        self.calls.append((list(command), timeout_seconds))
        operation = command[1]
        if operation == "create":
            if self.allocate:
                self.containers[self.cid] = self.fixture.owned_worker(self.cid)
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply
        if operation == "start":
            self.containers.pop(command[-1], None)  # Model --rm after attach exits.
            return self.start_reply
        if operation == "ps":
            if self.inventory_reply is not None:
                return self.inventory_reply
            return process(self.cid if self.cid in self.containers else "")
        if operation == "container" and command[2] == "inspect":
            if self.inspect_reply is not None:
                return self.inspect_reply
            info = self.containers.get(command[-1])
            return (process(json.dumps({**info, **self.inspect_changes})) if info is not None else
                    process(returncode=1, stderr="Error: No such container: " + command[-1]))
        if operation == "rm":
            if self.remove_reply is not None:
                return self.remove_reply
            if not self.keep_removed:
                for cid in command[3:]:
                    self.containers.pop(cid, None)
            return process()
        raise AssertionError("Unexpected Docker operation: " + repr(command))


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
        self.token = "c" * 32
        self.enter_patch(patch.object(bridge.uuid, "uuid4", return_value=SimpleNamespace(hex=self.token)))

    def enter_patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def schema(self, profile="qgis-practice-v2"):
        provider = self.contract["provider"]
        return {"ok": True, "profile": profile, "schema_sha256": self.contract["profiles"][profile],
                "installed_package": {"name": provider["name"], "version": provider["version"], "revision": provider["installed_revision"]}}

    def owned_worker(self, cid):
        return {"id": cid, "image_id": self.image, "factory": "unaltraweb", "role": "practice-verifier",
                "project_id": hashlib.sha256(str(self.project).encode()).hexdigest()[:16], "worker_token": self.token,
                "session_id": os.environ.get("UNALTRAWEB_RUNTIME_SESSION", ""), "running": False, "status": "created"}

    @contextmanager
    def daemon(self, reply, **kwargs):
        daemon = VerifierDaemon(self, reply, **kwargs)
        with patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                patch.object(bridge, "run_process", side_effect=daemon.run), \
                patch.object(bridge.lifecycle, "run_process", side_effect=daemon.run), \
                patch.object(site_tools, "run_process", side_effect=daemon.run):
            yield daemon

    def test_missing_or_mismatched_private_image_blocks_without_acquisition(self):
        for state in ("missing", "mismatch", "unknown"):
            with self.subTest(state=state), patch.object(bridge.lifecycle, "inspect_image", return_value={"state": state}), \
                    patch.object(bridge, "run_process") as run, self.assertRaisesRegex(RuntimeError, "hub preparation"):
                bridge.call(self.project, "schema", profile="qgis-practice-v2")
            run.assert_not_called()

    def test_check_runs_only_inside_private_image_with_readonly_mount_and_native_limits(self):
        cid = "a"*64
        report = {"ok": True, "profile": "qgis-practice-v2", "closure": []}
        with self.daemon(process(cid + "\n")) as daemon:
            daemon.start_reply = process(json.dumps(report))
            result = bridge.call(self.project, "check", bundle="sandbox/bundle.json", sha256="b"*64, selected=["initial-project"])
        create = daemon.calls[0][0]
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
        self.assertEqual(next(timeout for cmd, timeout in daemon.calls if cmd[1] == "start"), 120)
        self.assertEqual(result["result"], report)
        self.assertTrue(result["origin"]["execution"]["cleanup"]["resources_released"])
        self.assertIsNone(result["origin"]["controller"]["source_revision"])

    def test_schema_has_no_consumer_mount_and_keeps_release_wheel_separate(self):
        with self.daemon(process(VerifierDaemon.cid)) as daemon:
            value = bridge.call(self.project, "schema", profile="qgis-practice-v2")
        self.assertNotIn("--mount", daemon.calls[0][0])
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
                patch.object(bridge.lifecycle, "inspect_container", side_effect=[self.owned_worker(cid), None]), \
                patch.object(bridge, "run_process", side_effect=[process(cid), process(returncode=124, timed_out=True)]), \
                patch("unaltraweb_mcp.site_tools._cleanup_timed_out_workers", return_value={"ok": True, "removed": [cid], "resources_released": True}) as cleanup, \
                self.assertRaisesRegex(RuntimeError, "exceeded its bound"):
            bridge.call(self.project, "schema", profile="qgis-practice-v2")
        self.assertEqual(cleanup.call_args.kwargs["role"], "practice-verifier")
        self.assertRegex(cleanup.call_args.kwargs["token"], r"^[0-9a-f]{32}$")
        self.assertEqual(cleanup.call_args.kwargs["expected_image_id"], self.image)
        self.assertEqual(cleanup.call_args.kwargs["session_id"], "")

    def test_truncated_output_or_unconfirmed_teardown_cannot_pass(self):
        for truncated, left in ((True, None), (False, {"id": "a"*64})):
            with self.subTest(truncated=truncated, left=left), \
                    patch.object(bridge.lifecycle, "inspect_image", return_value=self.observed), \
                    patch.object(bridge.lifecycle, "inspect_container", side_effect=[self.owned_worker("a"*64), left]), \
                    patch.object(site_tools, "_cleanup_timed_out_workers", return_value={"ok": True, "resources_released": True}), \
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

    def test_create_timeout_after_allocation_removes_only_the_owned_never_started_container(self):
        for session in ("", "d" * 32):
            with self.subTest(session=session), patch.dict(os.environ, {"UNALTRAWEB_RUNTIME_SESSION": session}), \
                    self.daemon(process(VerifierDaemon.cid, returncode=124, timed_out=True)) as daemon:
                with self.assertRaisesRegex(RuntimeError, "Cannot start"):
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertEqual(daemon.containers, {})
                self.assertFalse(any(cmd[1] == "start" for cmd, _ in daemon.calls))
                self.assertEqual([cmd for cmd, _ in daemon.calls if cmd[1] == "rm"], [["docker", "rm", "-f", daemon.cid]])
                inventory = next(cmd for cmd, _ in daemon.calls if cmd[1] == "ps")
                self.assertIn("label=io.context.mcp-worker-token=" + self.token, inventory)
                if session:
                    self.assertIn("label=io.context.mcp-session=" + session, inventory)

    def test_create_malformed_truncated_and_lost_replies_still_clean_the_allocated_container(self):
        replies = [process("not-a-cid"), process(""), process(VerifierDaemon.cid, stdout_truncated=True),
                   process(VerifierDaemon.cid, stderr_truncated=True), OSError("create transport lost")]
        for reply in replies:
            with self.subTest(reply=reply), self.daemon(reply) as daemon:
                with self.assertRaises((RuntimeError, OSError)):
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertEqual(daemon.containers, {})
                self.assertFalse(any(cmd[1] == "start" for cmd, _ in daemon.calls))
                self.assertTrue(any(cmd[1] == "container" for cmd, _ in daemon.calls))

    def test_create_failure_before_allocation_observes_absence_without_removal(self):
        with self.daemon(process(returncode=125, stderr="create refused before allocation"), allocate=False) as daemon:
            with self.assertRaisesRegex(RuntimeError, "create refused before allocation"):
                bridge.call(self.project, "schema", profile="qgis-practice-v2")
        self.assertTrue(any(cmd[1] == "ps" for cmd, _ in daemon.calls))
        self.assertFalse(any(cmd[1] in {"rm", "start"} for cmd, _ in daemon.calls))
        self.assertEqual(daemon.containers, {})

    def test_create_cleanup_failure_is_reported_as_unconfirmed_not_hidden_by_primary_error(self):
        for removal in (process(returncode=1, stderr="removal denied"), process(timed_out=True),
                        process(stdout_truncated=True), process(stderr_truncated=True), None):
            with self.subTest(removal=removal), self.daemon(process(VerifierDaemon.cid, timed_out=True)) as daemon:
                daemon.remove_reply = removal
                daemon.keep_removed = removal is None
                with self.assertRaisesRegex(RuntimeError, "teardown is unconfirmed") as caught:
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertIn("Cannot start", str(caught.exception.__context__))
                self.assertIn(daemon.cid, daemon.containers)

    def test_create_recovery_refuses_changed_ownership_image_session_or_daemon_cid(self):
        changes = {"factory": "foreign", "role": "other", "project_id": "f" * 16, "worker_token": "e" * 32,
                   "session_id": "f" * 32, "image_id": "sha256:" + "b" * 64, "id": "b" * 64}
        for key, value in changes.items():
            with self.subTest(field=key), self.daemon(process(VerifierDaemon.cid, timed_out=True)) as daemon:
                daemon.inspect_changes = {key: value}
                with self.assertRaisesRegex(RuntimeError, "teardown is unconfirmed"):
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertFalse(any(cmd[1] in {"rm", "start"} for cmd, _ in daemon.calls))
                self.assertIn(daemon.cid, daemon.containers)

    def test_create_recovery_docker_errors_and_unknown_absence_are_not_cleanup_success(self):
        observations = [process(returncode=1, stderr="daemon unavailable"), process(timed_out=True),
                        process(stdout_truncated=True), process(stderr_truncated=True), process("not-an-id")]
        for observation in observations:
            with self.subTest(inventory=observation), self.daemon(process("malformed")) as daemon:
                daemon.inventory_reply = observation
                with self.assertRaisesRegex(RuntimeError, "teardown is unconfirmed"):
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertFalse(any(cmd[1] == "rm" for cmd, _ in daemon.calls))
        for observation in (process(returncode=1, stderr="dial unix /docker.sock: no such file or directory"),
                            process("{}", stderr_truncated=True), process("[]"), process("invalid-json")):
            with self.subTest(inspect=observation), self.daemon(process("malformed")) as daemon:
                daemon.inspect_reply = observation
                with self.assertRaisesRegex(RuntimeError, "teardown is unconfirmed"):
                    bridge.call(self.project, "schema", profile="qgis-practice-v2")
                self.assertFalse(any(cmd[1] == "rm" for cmd, _ in daemon.calls))

    def test_create_reply_cannot_start_or_remove_a_foreign_cid(self):
        foreign = "b" * 64
        with self.daemon(process(foreign)) as daemon:
            daemon.containers[foreign] = {**self.owned_worker(foreign), "factory": "foreign"}
            with self.assertRaisesRegex(RuntimeError, "unverified|foreign"):
                bridge.call(self.project, "schema", profile="qgis-practice-v2")
            self.assertEqual(set(daemon.containers), {foreign})
            self.assertFalse(any(cmd[1] == "start" for cmd, _ in daemon.calls))
            self.assertEqual([cmd for cmd, _ in daemon.calls if cmd[1] == "rm"], [["docker", "rm", "-f", daemon.cid]])

    def test_reopen_positive_keeps_native_request_limits_mounts_and_exact_absence(self):
        with tempfile.TemporaryDirectory() as sockets:
            socket = Path(sockets) / "docker.sock"
            socket.touch()  # Fake endpoint; every Docker operation below is doubled.
            with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_SOCKET": str(socket)}), self.daemon(process(VerifierDaemon.cid)) as daemon:
                native = {"ok": True, "projects": {"initial-project": {"fixture": "native-result"}}}
                daemon.start_reply = process(json.dumps(native))
                result = bridge.call(self.project, "reopen", bundle="bundle/bundle.json", sha256="b" * 64,
                                     selected=["initial-project"], output="new-proof/reopen.json")
                self.assertEqual(result["result"], native)
                self.assertTrue(result["origin"]["execution"]["cleanup"]["resources_released"])
                self.assertEqual(daemon.containers, {})
                create = daemon.calls[0][0]
                self.assertEqual(create[create.index("--network") + 1], "none")
                self.assertEqual(create[create.index("--pull") + 1], "never")
                self.assertEqual(create[-11:], ["practice-reopen", "--workspace", str(self.project), "--path", "bundle/bundle.json",
                                              "--sha256", "b" * 64, "--select", "initial-project", "--output", "new-proof/reopen.json"])
                execution = result["origin"]["execution"]
                self.assertEqual((execution["cpus"], execution["memory_mib"], execution["pids"], execution["timeout_seconds"]), (2, 4096, 512, 300))
                self.assertEqual(execution["mounts"], [
                    {"source": str(self.project), "target": str(self.project), "readonly": False},
                    {"source": str(socket), "target": "/var/run/docker.sock", "readonly": False}])
