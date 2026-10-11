from __future__ import annotations

import copy
from contextlib import closing, ExitStack
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

from unaltraweb_mcp import practice_editions as editions, artifact_handoff_v1 as h, site_tools, cli
from unaltraweb_mcp.editorial_sources import digest


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def report(self):
        files = [{"id": "initial", "path": "payload/projects/start.qgz", "kind": "output", "role": "initial-project",
                  "ownership": "producer", "sha256": "a"*64, "bytes": 10},
                 {"id": "data", "path": "payload/data/start.gpkg", "kind": "output", "role": "initial-data",
                  "ownership": "producer", "sha256": "b"*64, "bytes": 20}]
        return {"files": files}, {"profile": "qgis-practice-v1", "selected": ["initial"],
                "closure": [{**files[0], "depends_on": ["data"]}, {**files[1], "depends_on": []}]}

    def test_explicit_closure_preserved_and_missing_dependency_is_not_filtered(self):
        manifest, report = self.report()
        self.assertEqual(editions.validate_closure(report, manifest, ["initial"], "alumnat"), report["closure"])
        report["closure"].pop()
        with self.assertRaisesRegex(ValueError, "dependency is missing"):
            editions.validate_closure(report, manifest, ["initial"], "alumnat")

    def test_resolved_or_reconstruction_files_never_leak_to_student(self):
        for role, kind in (("resolved-data", "output"), ("source", "input"), ("control", "evidence")):
            manifest, report = self.report()
            manifest["files"][1].update(role=role, kind=kind)
            report["closure"][1].update(role=role, kind=kind)
            with self.subTest(role=role), self.assertRaises(ValueError):
                editions.validate_closure(report, manifest, ["initial"], "alumnat")
        manifest, report = self.report()
        with self.assertRaisesRegex(ValueError, "teacher-only"):
            editions.validate_closure(report, manifest, ["initial"], "alumnat", ["initial"])

    def test_producer_result_cannot_change_hash_or_expand_selection(self):
        manifest, report = self.report()
        report["closure"][1]["sha256"] = "c"*64
        with self.assertRaisesRegex(ValueError, "common inventory"):
            editions.validate_closure(report, manifest, ["initial"], "docent")
        manifest, report = self.report()
        report["selected"] = ["other"]
        with self.assertRaisesRegex(ValueError, "requested explicit selection"):
            editions.validate_closure(report, manifest, ["initial"], "docent")

    def test_native_profile_keeps_font_sidecars_and_requires_its_own_profile(self):
        manifest, report = self.report()
        report["profile"] = "qgis-practice-v2"
        manifest["files"][0]["role"] = report["closure"][0]["role"] = "map-svg"
        manifest["files"][1]["path"] = report["closure"][1]["path"] = "payload/data/fonts/font.ttf"
        rows = editions.validate_closure(report, manifest, ["initial"], "docent", profile="qgis-practice-v2")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["path"], "payload/data/fonts/font.ttf")
        with self.assertRaisesRegex(ValueError, "requested explicit selection"):
            editions.validate_closure(report, manifest, ["initial"], "docent", profile="qgis-practice-v1")
        with self.assertRaisesRegex(ValueError, "teacher-only"):
            editions.validate_closure(report, manifest, ["initial"], "alumnat", ["initial"], profile="qgis-practice-v2")

    def test_v2_identity_requests_v2_schema_and_refuses_v1_pin(self):
        expected = {"package": "unaltracaptura-qgis", "version": "0.6.0rc2", "revision": "sha256:"+"a"*64,
                    "schema_sha256": "b"*64, "wheel_sha256": "c"*64}
        observed = {"ok": True, "profile": "qgis-practice-v2", "schema_sha256": "b"*64,
                    "installed_package": {"name": expected["package"], "version": expected["version"], "revision": expected["revision"]}}
        installed = SimpleNamespace(returncode=0, stdout_truncated=False,
                                    stdout=json.dumps({"archive_info": {"hashes": {"sha256": "c"*64}}}))
        with patch.object(editions, "provider_command", return_value=observed) as provider, patch.object(editions, "run_process", return_value=installed):
            self.assertEqual(editions.verifier_identity(self.root, expected, "qgis-practice-v2")["profile"], "qgis-practice-v2")
            provider.assert_called_once_with(self.root, ["practice-schema", "--profile", "qgis-practice-v2"])
            with self.assertRaisesRegex(ValueError, "identity/schema"):
                editions.verifier_identity(self.root, {**expected, "schema_sha256": "d"*64}, "qgis-practice-v2")
        with patch.object(editions, "provider_command", return_value={**observed, "profile": "qgis-practice-v1"}):
            with self.assertRaisesRegex(ValueError, "identity/schema"):
                editions.verifier_identity(self.root, expected, "qgis-practice-v2")
    def test_zip_contains_exact_files_and_no_control_or_receipt(self):
        (self.root / "data").mkdir()
        (self.root / "data/source.bin").write_bytes(b"opaque domain bytes")
        entries = [{"source": "data/source.bin", "destination": "payload/data/source.bin", "sha256": digest(b"opaque domain bytes"), "bytes": 19}]
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        result = editions.zip_files(self.root, fd, "edition.zip", entries)
        with zipfile.ZipFile(self.root / "edition.zip") as archive:
            self.assertEqual(archive.namelist(), ["payload/data/source.bin"])
            self.assertEqual(archive.read(archive.namelist()[0]), b"opaque domain bytes")
        self.assertEqual(result["sha256"], digest((self.root / "edition.zip").read_bytes()))
        with self.assertRaises(FileExistsError):
            editions.zip_files(self.root, fd, "edition.zip", entries)

    def test_zip_symlink_traversal_alias_and_hash_drift_are_refused(self):
        (self.root / "original").write_bytes(b"safe")
        (self.root / "link").symlink_to(self.root / "original")
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        for index, source in enumerate(("link", "../outside", "original")):
            row = {"source": source, "destination": "payload/safe", "sha256": "a"*64, "bytes": 4}
            with self.subTest(source=source), self.assertRaises((OSError, ValueError, h.HandoffError)):
                editions.zip_files(self.root, fd, f"case{index}.zip", [row])
        row = {"source": "original", "destination": "payload/a", "sha256": digest(b"safe"), "bytes": 4}
        with self.assertRaises(h.HandoffError):
            editions.zip_files(self.root, fd, "alias.zip", [row, {**row, "destination": "payload/A"}])

    def test_public_cli_requires_explicit_absolute_consumer(self):
        with patch.dict(os.environ, {}, clear=True):
            for arguments in (["mcp", "manual-practice-compose", "--config", "edition.yml"],
                              ["--project", ".", "mcp", "manual-practice-compose", "--config", "edition.yml"]):
                with self.assertRaisesRegex(ValueError, "absolute consumer"):
                    cli.main(arguments)

    def test_schema_inventory_parity(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        declaration = yaml.safe_load((root / "mcp-factory.yml").read_bytes())
        inventory = site_tools.list_tools()
        self.assertIn("manual_practice_compose", inventory["tools"])
        self.assertEqual(set(inventory["tools"]), set(declaration["mcp"]["required_tools"]))
        self.assertEqual(set(inventory["resources"]), set(declaration["mcp"]["resources"]))

    def test_editable_svg_uses_only_explicit_relative_resources_and_recipients(self):
        folder = self.root / "_practices/demo"
        folder.mkdir(parents=True)
        raw = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"><g inkscape:label="Editable"><image href="icon.png"/></g></svg>'
        (folder / "poster.svg").write_bytes(raw)
        (folder / "icon.png").write_bytes(b"selected fixture bytes")
        (folder / "private.py").write_text("private control")
        declaration = {"path": "_practices/demo/poster.svg", "sha256": digest(raw), "destination": "resources/poster.svg",
                       "role": "editable-infographic", "recipients": ["docent"], "dependencies": [
                           {"path": "_practices/demo/icon.png", "sha256": digest(b"selected fixture bytes"), "destination": "resources/icon.png"}]}
        with closing(h.Workspace(str(self.root))) as workspace:
            rows = editions.author_resources(workspace, [declaration])
        self.assertEqual(rows["alumnat"], [])
        self.assertEqual({row["destination"] for row in rows["docent"]}, {"resources/poster.svg", "resources/icon.png"})
        for mutation in ("missing", "broken-mapping", "script", "unreferenced"):
            changed = copy.deepcopy(declaration)
            if mutation == "missing":
                changed["dependencies"] = []
            elif mutation == "broken-mapping":
                changed["dependencies"][0]["destination"] = "resources/moved.png"
            else:
                (folder / "extra.png").write_bytes(b"extra")
                path = "private.py" if mutation == "script" else "extra.png"
                changed["dependencies"].append({"path": "_practices/demo/"+path, "sha256": digest((folder/path).read_bytes()), "destination": "resources/"+path})
            with self.subTest(mutation=mutation), closing(h.Workspace(str(self.root))) as workspace, self.assertRaises(ValueError):
                editions.author_resources(workspace, [changed])

    def composition_fixture(self):
        manifest, report = self.report()
        manifest["producer"] = {"name": "unaltracaptura-qgis"}
        for row in manifest["files"]:
            path = self.root / "sandbox/gis" / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("opaque fixture " + row["id"]).encode()
            path.write_bytes(raw)
            row.update(sha256=digest(raw), bytes=len(raw))
        report["closure"] = [{**row, "depends_on": ["data"] if row["id"] == "initial" else []} for row in manifest["files"]]
        report.update(ok=True, bundle={"sha256": "a"*64}, activity="fixture", job="retained-fixture")
        spec = {"schema_version": 1, "kind": "unaltraweb-practice-edition", "slug": "fixture", "version": "r1", "language": "ca",
                "gis": {"bundle": "sandbox/gis/bundle.json", "sha256": "a"*64, "verifier": {
                    "package": "unaltracaptura-qgis", "version": "0.6.0rc2", "revision": "sha256:"+"b"*64,
                    "schema_sha256": "c"*64, "wheel_sha256": "d"*64}},
                "selection": {who: ["initial"] for who in editions.RECIPIENTS}, "readings": {}}
        sealed = {}
        for who in editions.RECIPIENTS:
            source = f"practiques/fixture/ca/{who}/LLEGIU-ME.md"
            path = self.root / source
            path.parent.mkdir(parents=True)
            path.write_text("---\ntitle: Fixture\ncontent_status: draft\n---\nReading " + who)
            spec["readings"][who] = {"source": source, "approved_sha256": digest(path.read_bytes())}
            pdf = f"sandbox/readings/{who}.pdf"
            (self.root/pdf).parent.mkdir(parents=True, exist_ok=True)
            (self.root/pdf).write_bytes(b"%PDF-1.4\nsealed fixture " + who.encode())
            receipt = pdf + ".receipt.json"
            (self.root/receipt).write_text(json.dumps({"renderer": {"reference": "fixture-worker"}, "portable_links": {},
                "effective_source": {}, "original_inputs": {source: digest(path.read_bytes())}, "factory_inputs": {}}))
            sealed[source] = {"ok": True, "state": "current", "pdf": pdf, "receipt": receipt}
        (self.root/"_config.yml").write_text("{}")
        (self.root/"edition.json").write_text(json.dumps(spec))

        def build(project, factory, source, version, **kwargs):
            return {**sealed[source], "portable_links": {"targets": kwargs["portable_targets"]}}

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(editions, "privacy_preflight"))
        stack.enter_context(patch.object(editions.fs, "_require_generated_path"))
        stack.enter_context(patch.object(editions, "verifier_identity", return_value={"profile": "qgis-practice-v1"}))
        stack.enter_context(patch.object(editions, "provider_command", return_value=report))
        stack.enter_context(patch.object(editions.handoff.Verifier, "bundle", return_value=(manifest, {}, {})))
        stack.enter_context(patch.object(editions.handoff, "check"))
        stack.enter_context(patch.object(editions, "active_runtime", return_value=None))
        builder = stack.enter_context(patch.object(editions.practice_pdf, "build", side_effect=build))
        return builder, sealed

    def test_composition_publishes_same_sealed_pdf_inside_and_beside_zip(self):
        builder, sealed = self.composition_fixture()
        result = editions.compose(self.root, self.root, "edition.json")
        directory = self.root / result["path"]
        self.assertEqual(len(list(directory.iterdir())), 9)
        self.assertEqual([call.kwargs.get("dry_run", False) for call in builder.call_args_list], [True, True, False, False])
        for who, package in result["packages"].items():
            with self.subTest(recipient=who):
                pdf = package["pdf"]
                raw = (directory/pdf["path"]).read_bytes()
                self.assertEqual(pdf["path"], package["path"].removesuffix(".zip") + ".pdf")
                self.assertEqual(digest(raw), pdf["sha256"])
                with zipfile.ZipFile(directory/package["path"]) as archive:
                    self.assertEqual(archive.read("LLEGIU-ME.pdf"), raw)
                    self.assertFalse(any(name.endswith("receipt.json") for name in archive.namelist()))
                proof_bytes = (directory/pdf["receipt"]).read_bytes()
                self.assertEqual(digest(proof_bytes), pdf["receipt_sha256"])
                proof = json.loads(proof_bytes)
                self.assertEqual(proof["recipient"], who)
                self.assertEqual(proof["sealed_source"]["sha256"], digest(raw))
                self.assertEqual((self.root/proof["sealed_source"]["path"]).read_bytes(), raw)
                self.assertEqual(proof["edition_receipt"]["sha256"], digest((directory/package["receipt"]).read_bytes()))
                self.assertEqual(proof["zip"]["sha256"], digest((directory/package["path"]).read_bytes()))
        before = {path.name: path.read_bytes() for path in directory.iterdir()}
        with self.assertRaisesRegex(ValueError, "already exists"):
            editions.compose(self.root, self.root, "edition.json")
        self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, before)
        self.assertEqual(builder.call_count, 4)

    def test_pdf_delivery_failure_does_not_publish_a_partial_edition(self):
        self.composition_fixture()
        original = editions.write_new
        def fail_pdf_receipt(directory, name, raw):
            if name.endswith(".pdf.receipt.json"):
                raise OSError("fixture receipt failure")
            return original(directory, name, raw)
        with patch.object(editions, "write_new", side_effect=fail_pdf_receipt), self.assertRaisesRegex(OSError, "fixture receipt"):
            editions.compose(self.root, self.root, "edition.json")
        self.assertFalse((self.root/"dist/practiques/fixture/r1/ca").exists())
        self.assertTrue(list((self.root/"dist/practiques/fixture/r1").glob(".candidate-ca-*")))

    def test_dry_run_does_not_copy_or_render_delivery_pdf(self):
        builder, _ = self.composition_fixture()
        result = editions.compose(self.root, self.root, "edition.json", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse((self.root/"dist").exists())
        self.assertEqual([call.kwargs["dry_run"] for call in builder.call_args_list], [True, True])

    def test_independent_pdf_copy_refuses_clobber_symlinks_and_changed_bytes(self):
        raw = b"%PDF-1.4\nsealed bytes"
        (self.root/"source.pdf").write_bytes(raw)
        row = {"source": "source.pdf", "sha256": digest(raw), "bytes": len(raw)}
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, fd)
        result = editions.copy_pdf(self.root, fd, "delivery.pdf", row)
        self.assertEqual(result["sha256"], digest(raw))
        with self.assertRaises(FileExistsError):
            editions.copy_pdf(self.root, fd, "delivery.pdf", row)
        (self.root/"alias.pdf").symlink_to(self.root/"source.pdf")
        with self.assertRaises(OSError):
            editions.copy_pdf(self.root, fd, "from-alias.pdf", {**row, "source": "alias.pdf"})
        with self.assertRaises((ValueError, h.HandoffError)):
            editions.copy_pdf(self.root, fd, "../outside.pdf", row)
        with self.assertRaisesRegex(ValueError, "changed during copying"):
            editions.copy_pdf(self.root, fd, "wrong-hash.pdf", {**row, "sha256": "0"*64})
        self.assertEqual((self.root/"delivery.pdf").read_bytes(), raw)
