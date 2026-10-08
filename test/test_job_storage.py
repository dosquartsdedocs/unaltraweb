from __future__ import annotations

import copy
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp.job_storage import contract
from unaltraweb_mcp.job_storage.registry import Registry
from unaltraweb_mcp.job_storage.manager import provider


def provider_document():
    return {"kind": "gacontext.job-storage-provider", "schema_version": 1,
            "contract": contract.CONTRACT, "provider": "unaltraweb", "storage_tool": "job_storage",
            "job_root": "/work", "scratch_root": "/work/scratch",
            "path_policies": [{"path": path, "type": "directory", "role": role, "cleanup": cleanup}
                              for path, (role, cleanup) in contract.POLICIES.items()],
            "limits": {"max_scratch_bytes": 1024**3, "max_retained_bytes": 1024**3,
                       "max_entries": 10000, "max_jobs": 4, "min_free_bytes": 1024**3,
                       "monitor_interval_seconds": 2, "quota_enforcement": "monitored"}}


def state_document():
    state = {"kind": "gacontext.job-storage-state", "schema_version": 1, "contract": contract.CONTRACT,
             "registry_id": "1"*32, "job_id": "2"*32, "binding_id": "3"*32, "provider": "unaltraweb",
             "provider_sha256": contract.sha256(contract.canonical(provider_document())), "daemon_id": "test-daemon-001",
             "revision": 7, "epoch": 2, "observed_at": "2026-10-07T12:00:00Z", "phase": "open", "activity": "idle",
             "limits": provider_document()["limits"], "leases_complete": True, "leases": [], "volumes": [],
             "products": [{"id": "6"*32, "bundle_sha256": "a"*64, "disposition": "pending", "decision": None}],
             "holds": [], "protected_inventory": {"state": "verified", "tree_sha256": "b"*64, "unresolved_entries": 0}}
    for identifier, role in (("4"*32, "scratch"), ("5"*32, "retained")):
        volume = {"id": identifier, "name": "gacontext-job-" + identifier, "role": role,
                  "daemon_id": state["daemon_id"], "driver": "local", "created_at": "2026-10-07T11:59:00Z",
                  "marker_sha256": "c"*64, "state": "verified", "observed_at": state["observed_at"],
                  "attachments_complete": True, "attachments": [], "bytes": 0}
        volume["labels"] = contract.labels(state, volume)
        state["volumes"].append(volume)
    return state


class StorageContractTests(unittest.TestCase):
    def test_source_companion_installed_provider_and_native_inventory_agree(self):
        from unaltraweb_mcp import site_tools
        import yaml
        root = Path(__file__).resolve().parents[1]
        declared = (root / "mcp-job-storage.json").read_bytes()
        value, digest, installed = provider()
        self.assertEqual(declared, installed)
        self.assertEqual(digest, contract.sha256(declared))
        self.assertEqual(value, site_tools.job_storage_provider())
        manifest = yaml.safe_load((root / "mcp-factory.yml").read_bytes())
        inventory = site_tools.list_tools()
        self.assertIn(value["storage_tool"], inventory["tools"])
        self.assertEqual(set(manifest["mcp"]["required_tools"]), set(inventory["tools"]))
        self.assertEqual(set(manifest["mcp"]["resources"]), set(inventory["resources"]))

    def test_hook_rejects_workspace_override_before_constructing_an_authority(self):
        from unaltraweb_mcp import site_tools
        request = {"kind": "gacontext.job-storage-request", "schema_version": 1, "registry_id": "1"*32,
                   "job_id": "2"*32, "operation": "status", "workspace": "/other-consumer"}
        with patch("unaltraweb_mcp.job_storage.manager.Manager") as manager:
            result = site_tools.job_storage(Path.cwd(), request)
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], "invalid-storage-contract")
            manager.assert_not_called()

    def test_cli_dispatch_preserves_the_exact_request_and_selected_consumer(self):
        from unaltraweb_mcp import cli
        request = {"kind": "gacontext.job-storage-request", "schema_version": 1, "registry_id": "1"*32,
                   "job_id": "2"*32, "operation": "quiesce", "expected_revision": 7, "expected_epoch": 2}
        with patch("unaltraweb_mcp.site_tools.job_storage", return_value=state_document()) as hook, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(["--project", str(Path.cwd()), "mcp", "job-storage", "--request-json", json.dumps(request)]), 0)
        hook.assert_called_once_with(Path.cwd(), request)
        self.assertEqual(json.loads(output.getvalue()), state_document())

    def test_pinned_schema_bytes_and_independent_schema_validation(self):
        self.assertEqual(contract.SCHEMA_SHA256, contract.sha256(contract.SCHEMA_PATH.read_bytes()))
        for value in (provider_document(), state_document()):
            self.assertEqual(value, contract.validate(value))
        try:
            import jsonschema
        except ImportError:
            return
        validator = jsonschema.Draft202012Validator(contract.schema(), format_checker=jsonschema.FormatChecker())
        for value in (provider_document(), state_document()):
            validator.validate(value)

    def test_boolean_version_unknown_fields_and_unsafe_root_policies_are_rejected(self):
        for patch in ({"schema_version": True}, {"job_root": "/consumer"}, {"volume_name": "caller-choice"}):
            with self.subTest(patch=patch), self.assertRaises(contract.StorageError):
                contract.validate({**provider_document(), **patch})
        value = provider_document()
        value["path_policies"][0]["cleanup"] = "on-release"
        with self.assertRaises(contract.StorageError):
            contract.validate(value)

    def test_shape_validation_does_not_confer_observation_or_release_authority(self):
        value = state_document()
        value["volumes"][0]["bytes"] = None
        self.assertIsNone(contract.validate(value)["volumes"][0]["bytes"])
        for field, mutation in (("name", "gacontext-job-"+"0"*32), ("daemon_id", "different-daemon")):
            changed = copy.deepcopy(value)
            changed["volumes"][0][field] = mutation
            with self.subTest(field=field), self.assertRaises(contract.StorageError):
                contract.validate(changed)
        changed = copy.deepcopy(value)
        changed["phase"] = "released"
        with self.assertRaises(contract.StorageError):
            contract.validate(changed)

    def test_request_cas_and_no_mount_command_or_workspace_override(self):
        state = state_document()
        request = {"kind": "gacontext.job-storage-request", "schema_version": 1,
                   "operation": "status", "registry_id": state["registry_id"], "job_id": state["job_id"]}
        contract.check_request(request, state)
        for field in ("expected_revision", "command", "volume", "workspace"):
            with self.subTest(field=field), self.assertRaises(contract.StorageError):
                contract.validate({**request, field: 7})
        mutation = {**request, "operation": "quiesce", "expected_revision": 7, "expected_epoch": 2}
        contract.check_request(mutation, state)
        with self.assertRaises(contract.StorageError) as error:
            contract.check_request({**mutation, "expected_epoch": 1}, state)
        self.assertEqual("storage-revision-conflict", error.exception.code)
        with self.assertRaises(contract.StorageError):
            contract.check_request({**mutation, "operation": "seal"}, {**state, "activity": "busy"})
        contract.check_request(mutation, {**state, "activity": "busy"})

    def test_read_binding_can_deliver_after_scratch_retirement_but_not_during_release(self):
        state = state_document()
        state["phase"] = "closed"
        state["volumes"][0]["state"] = "absent"
        state["leases"] = [{"id": "7"*32, "kind": "transfer", "state": "active"}]
        binding = {"kind": "gacontext.job-storage-binding", "schema_version": 1,
                   **{key: state[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id", "epoch")},
                   "lease_id": "7"*32, "access": "read-only", "job_root": "/work",
                   "mounts": [{key: state["volumes"][1][key] for key in ("id", "name", "role", "marker_sha256")}]}
        contract.check_binding(binding, state)
        with self.assertRaises(contract.StorageError):
            contract.check_binding(binding, {**state, "phase": "releasing"})
        with self.assertRaises(contract.StorageError):
            contract.check_binding({**binding, "access": "read-write"}, state)

    def test_archive_and_bundle_digests_are_separate_and_paths_confined(self):
        value = {"kind": "gacontext.job-product-retention", "schema_version": 1,
                 "registry_id": "1"*32, "job_id": "2"*32, "product_id": "3"*32,
                 "receiver_binding_id": "4"*32, "bundle_sha256": "a"*64,
                 "destination": {"path": ".unaltraweb/artifacts/demo/bundle.zip", "format": "zip", "content_sha256": "b"*64},
                 "domain_profile": "diagram-v1", "domain_check_sha256": "c"*64, "verified_at": "2026-10-07T12:00:00Z"}
        contract.validate(value)
        with self.assertRaises(contract.StorageError):
            contract.validate({**value, "destination": {**value["destination"], "format": "directory"}})
        for path in ("../escape", "/absolute", ".git/data", "a\\b"):
            with self.subTest(path=path), self.assertRaises(contract.StorageError):
                contract.validate({**value, "destination": {**value["destination"], "path": path}})

    def test_bounded_json_and_utc_observations(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b" "*(contract.MAX_DOCUMENT+1)):
            with self.subTest(raw=raw[:30]), self.assertRaises(contract.StorageError):
                contract.parse(raw)
        self.assertTrue(contract.fresh("2026-10-07T12:00:00Z", "2026-10-07T12:00:30Z"))
        self.assertFalse(contract.fresh("2026-10-07T12:00:00Z", "2026-10-07T12:00:31Z"))
        self.assertFalse(contract.fresh("2026-10-07T12:00:01Z", "2026-10-07T12:00:00Z"))
        with self.assertRaises(contract.StorageError):
            contract.timestamp("2026-10-07T12:00:00+00:00")
        self.assertEqual(contract.canonical({"b": 2, "a": "é"}), b'{\n  "a": "\\u00e9",\n  "b": 2\n}\n')


class StorageRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "registry"

    def initialize(self):
        with Registry(self.root).locked(write=True, create=True, daemon_id="test-daemon-001") as registry:
            return copy.deepcopy(registry.record)

    def test_observation_neither_initializes_nor_changes_metadata(self):
        with self.assertRaises(FileNotFoundError):
            with Registry(self.root).locked():
                pass
        self.assertFalse(self.root.exists())
        original = self.initialize()
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.iterdir()}
        with Registry(self.root).locked() as registry:
            self.assertEqual(original, registry.record)
            with self.assertRaises(contract.StorageError):
                registry.write("not-authorized.json", {})
        after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.iterdir()}
        self.assertEqual(before, after)

    def test_other_controller_cannot_take_the_write_lock(self):
        self.initialize()
        with Registry(self.root).locked(write=True):
            with self.assertRaises(contract.StorageError) as error:
                with Registry(self.root).locked(write=True):
                    pass
            self.assertEqual("storage-registry-busy", error.exception.code)

    def test_copied_registry_does_not_adopt_ownership(self):
        self.initialize()
        copied = self.root.with_name("copied")
        shutil.copytree(self.root, copied)
        with self.assertRaises(contract.StorageError):
            with Registry(copied).locked():
                pass

    def test_symlink_and_hardlink_are_not_registry_members(self):
        self.initialize()
        original = self.root / "registry.json"
        (self.root / "linked.json").symlink_to(original)
        with Registry(self.root).locked() as registry:
            with self.assertRaises(contract.StorageError):
                registry.read("linked.json")
        (self.root / "linked.json").unlink()
        os.link(original, self.root / "hardlink.json")
        with self.assertRaises(contract.StorageError):
            with Registry(self.root).locked():
                pass

    def test_daemon_change_and_world_readable_state_are_refused(self):
        self.initialize()
        with self.assertRaises(contract.StorageError):
            with Registry(self.root).locked(daemon_id="another-daemon"):
                pass
        (self.root / "registry.json").chmod(0o644)
        with self.assertRaises(contract.StorageError):
            with Registry(self.root).locked():
                pass

    def test_atomic_updates_and_create_only_collisions(self):
        self.initialize()
        with Registry(self.root).locked(write=True) as registry:
            registry.write("jobs/" + "1"*32 + ".json", {"revision": 1}, create_only=True)
            with self.assertRaises(contract.StorageError):
                registry.write("jobs/" + "1"*32 + ".json", {"revision": 2}, create_only=True)
            self.assertEqual({"revision": 1}, registry.read("jobs/" + "1"*32 + ".json"))
            registry.save_registry()
            self.assertEqual(2, registry.read("registry.json")["revision"])
