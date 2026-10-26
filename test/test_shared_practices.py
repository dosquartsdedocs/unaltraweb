from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp import shared_jobs, site_tools
from test_practice_pdf import PracticePdfFixture

ROOT = Path(__file__).resolve().parents[1]


class SharedBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "consumer"
        self.project.mkdir()
        service = self.root / "service"
        service.mkdir(mode=0o700)
        self.context = {"kind": "unaltraweb.shared-job-context", "schema_version": 1, "workspace": str(self.project),
            "service_root": str(service), "docker_endpoint": "unix://" + str(self.root / "docker.sock"), "daemon_id": "fixture-daemon",
            "registry_id": "a" * 32, "job_id": "b" * 32, "task_id": "c" * 32, "owner_id": "d" * 32,
            "pdf_image": "sha256:" + "1" * 64, "worker_user": "1000:1000"}
        self.path = self.root / "selected.json"
        self.path.write_text(json.dumps(self.context))
        self.path.chmod(0o600)

    def test_no_selection_does_not_import_sdk_initialize_or_call_a_manager(self):
        with patch.dict(os.environ, {}, clear=True), patch("unaltraweb_mcp.runtime_identity.active_runtime", return_value=None), \
                patch.object(shared_jobs, "sdk", side_effect=AssertionError("No implicit runtime")):
            result = shared_jobs.job_storage(self.project, {})
        self.assertEqual(result["error"]["code"], "shared-runtime-unconfigured")
        self.assertEqual(list(self.project.iterdir()), [])

    def test_private_binding_is_explicit_and_consumer_cannot_override_it(self):
        self.assertEqual(shared_jobs.load_context(self.project, str(self.path)), self.context)
        for changed in ({"workspace": str(self.root)}, {"pdf_image": "mutable:latest"},
                        {"service_root": str(self.project)}, {"unknown": True}, {"worker_user": "$(id)"}):
            with self.subTest(changed=changed):
                self.path.write_text(json.dumps({**self.context, **changed}))
                with self.assertRaises(ValueError):
                    shared_jobs.load_context(self.project, str(self.path))
        self.path.write_text(json.dumps(self.context))
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            shared_jobs.load_context(self.project, str(self.path))

    def test_native_control_forwards_exact_cas_and_busy_changed_response(self):
        calls = []
        busy = {"ok": False, "changed": True, "state": {"phase": "draining"}, "error": {"code": "storage-busy"}}
        class Client:
            def __init__(self, root):
                self.root = root
            def job_storage(self, workspace, provider, request):
                calls.append((workspace, provider, request))
                return busy
        request = {"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "quiesce",
                   "registry_id": "a" * 32, "job_id": "b" * 32, "expected_revision": 7, "expected_epoch": 3}
        with patch.object(shared_jobs, "sdk", return_value=(Client, None)):
            bound = shared_jobs.BoundJob(self.context)
            self.assertEqual(bound.control(request), busy)
            self.assertEqual(calls, [(str(self.project), "unaltraweb", request)])
            self.assertIsNot(calls[0][2], request)
            with self.assertRaisesRegex(ValueError, "another selected"):
                bound.control({**request, "job_id": "e" * 32})
            self.assertEqual(len(calls), 1)

    def test_operator_timeout_is_bounded_and_does_not_accept_boolean_or_string(self):
        for timeout in (1, 2, 5, 900):
            self.path.write_text(json.dumps({**self.context, "worker_timeout_seconds": timeout}))
            self.assertEqual(shared_jobs.load_context(self.project, str(self.path))["worker_timeout_seconds"], timeout)
        for timeout in (True, False, 0, -1, 901, "2", 2.5, None):
            with self.subTest(timeout=timeout):
                self.path.write_text(json.dumps({**self.context, "worker_timeout_seconds": timeout}))
                with self.assertRaisesRegex(ValueError, "Worker timeout"):
                    shared_jobs.load_context(self.project, str(self.path))

    def test_provider_copy_and_published_pins_are_exact(self):
        self.assertEqual(shared_jobs.PROVIDER.read_bytes(), (ROOT / "mcp-job-storage.json").read_bytes())
        contract = shared_jobs.runtime_contract()
        self.assertEqual(contract["version"], "0.1.0a7")
        self.assertEqual(contract["wheel"]["sha256"], "539ee0eb5d68657ca4615e78d37889ea06b6f81052fb816e9f7721ca8753e92c")
        self.assertEqual(contract["code_sha256"], "9c3317ce859f82fe85d978ab72ba19cf818bc2aa969d601f9e346cb129b3f464")
        self.assertFalse(contract["implicit_prepare"])
        managed = json.loads((ROOT / "gacontext/component.json").read_bytes())
        self.assertEqual(managed["revision"], 2)

    def test_explicit_shared_edition_cannot_fall_back_to_host_staging(self):
        with patch.object(shared_jobs, "selected", return_value=self.context), \
                patch("unaltraweb_mcp.practice_editions.compose", side_effect=AssertionError("No silent legacy fallback")):
            result = site_tools.manual_practice_compose(self.project, ROOT, "edition.json")
        self.assertEqual(result["code"], "shared-edition-unconfigured")
        self.assertFalse(result["publishes"])

    def test_domain_bundle_is_accepted_by_the_unchanged_common_wire_verifier(self):
        from unaltraweb_mcp.shared_practice_worker import file_record
        from unaltraweb_mcp import artifact_handoff_v1
        records = []
        for number, (name, raw) in enumerate((("payload/request.json", b'{"operation":"synthetic"}'),
                                              ("payload/results/README.pdf", b"structural fixture; not a native PDF claim"))):
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            records.append(file_record(number, name, raw))
        value = {"kind": "mcp-artifact-bundle", "schema_version": 1, "request": "request", "files": records, "dependencies": [],
                 "producer": {"name": "unaltraweb", "version": "0.7.3", "revision": "sha256:" + "a" * 64,
                              "runtimes": [{"name": "pdf", "revision": "sha256:" + "b" * 64}]}}
        raw = json.dumps(value).encode()
        (self.project / "bundle.json").write_bytes(raw)
        self.assertTrue(artifact_handoff_v1.check(str(self.project), "bundle", "bundle.json", hashlib.sha256(raw).hexdigest())["ok"])


class SharedDomainPreparationTests(PracticePdfFixture):
    def test_renderer_keeps_entered_command_and_child_diagnostics_in_protected_log(self):
        spec = importlib.util.spec_from_file_location("shared_pdf_log_test", ROOT / "scripts/manual/render_practice.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        source, output = self.project / "prepared", self.project / "scratch"
        source.mkdir()
        output.mkdir()
        (source / "request.json").write_text(json.dumps({"basename": "LLEGIU-ME", "filters": [
            "practice-layout.lua", "code-blocks.lua", "figure-captions.lua", "practice-finish.lua"]}))
        command = [sys.executable, "-c", "import os; os.write(2, b'child diagnostic\\n'); raise SystemExit(3)"]
        protected = self.project / "recovery.log"
        with protected.open("xb") as log, patch.object(renderer, "effective_source",
                side_effect=lambda request, stream: renderer.run(command, stream)):
            with self.assertRaises(subprocess.CalledProcessError):
                renderer.main(source=source, output=output, log_stream=log)
            self.assertFalse(log.closed)
        recorded = protected.read_bytes()
        self.assertEqual(json.loads(recorded.splitlines()[0]), {"command": command})
        self.assertIn(b"child diagnostic\n", recorded)
        self.assertFalse((output / "render.log").exists())

    def test_explicit_volume_resource_root_keeps_originals_and_typography(self):
        image = self.project / "assets/picture.png"
        image.parent.mkdir()
        image.write_bytes(b"owned fixture bytes")
        self.source.write_text(self.source.read_text() + "\n![Map](assets/picture.png)\n")
        before = self.source.read_bytes()
        legacy = self.plan()
        shared = self.plan(source_root="/work/scratch/source")
        self.assertEqual(shared["original_inputs"], legacy["original_inputs"])
        self.assertEqual(shared["files"]["practice.tex"], legacy["files"]["practice.tex"])
        self.assertTrue(all(v.startswith("/work/scratch/source/") for v in shared["metadata"]["practice-assets"].values()))
        self.assertEqual(self.source.read_bytes(), before)
        self.assertNotEqual(legacy["fingerprint"], shared["fingerprint"])

    def test_invalid_shared_binding_fails_before_legacy_make_or_render(self):
        with patch.object(shared_jobs, "selected", side_effect=shared_jobs.SharedError("shared-workspace-mismatch", "other consumer")), \
                patch.object(site_tools, "run_factory_make") as legacy:
            result = site_tools.manual_practice_pdf_build(self.project, ROOT, self.source.relative_to(self.project).as_posix(), "v1")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "shared-workspace-mismatch")
        legacy.assert_not_called()
