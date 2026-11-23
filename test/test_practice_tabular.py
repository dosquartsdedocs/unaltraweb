from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from unaltraweb_mcp import practice_editions as editions, practice_pdf
from unaltraweb_mcp.editorial_sources import digest


class TabularEditionTests(unittest.TestCase):
    def fixture(self, language):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        (root / ".gitignore").write_text("sandbox/\ndist/\n")
        labels = json.loads((Path(__file__).parent / "practices" / (language + ".json")).read_bytes())
        (root / "_config.yml").write_text(json.dumps({"lang": language, "languages": [language], "exclude": ["practiques/", "sandbox/", "dist/"],
            "unaltraweb": {"site_profile": "unaltremanual"}}))
        spec = {"schema_version": 2, "kind": "unaltraweb-practice-edition", "mode": "tabular", "slug": "table-demo", "version": "r1",
                "language": language, "materials": [], "readings": {}, "selection": {"alumnat": ["initial"], "docent": ["initial", "resolved"]}}
        for key, role, recipients in (("initial", "initial-data", ["alumnat", "docent"]), ("resolved", "resolved-workbook", ["docent"])):
            extension = ".csv" if key == "initial" else ".xlsx"
            path = f"sandbox/practiques/table-demo/inputs/{key}{extension}"
            raw = (b"name,value\nSynthetic,10\n" if key == "initial" else b"synthetic opaque workbook; no semantic validation claimed")
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(raw)
            spec["materials"].append({"id": key, "path": path, "destination": "resources/" + key + extension,
                "role": role, "sha256": digest(raw), "bytes": len(raw), "recipients": recipients})
        for who in editions.RECIPIENTS:
            source = f"practiques/table-demo/{language}/{who}/{labels['basename']}.md"
            raw = (f"---\ntitle: {labels['student_title'] if who == 'alumnat' else labels['teacher_title']}\nlang: {language}\ncontent_status: draft\n---\n\nSynthetic fixture.\n").encode()
            (root / source).parent.mkdir(parents=True)
            (root / source).write_bytes(raw)
            spec["readings"][who] = {"source": source, "approved_sha256": digest(raw)}
        (root / "edition.json").write_text(json.dumps(spec))
        subprocess.run(["git", "-C", str(root), "add", "_config.yml", ".gitignore", "edition.json", "practiques"], check=True)
        return root, spec, labels

    def renderer(self, root):
        def build(project, factory, source, version, **kwargs):
            who = Path(source).parent.name
            paths = {"targets": kwargs["portable_targets"]}
            if kwargs.get("dry_run"):
                return {"portable_links": paths}
            pdf = f"sandbox/practiques/table-demo/pdf-{who}.pdf"
            raw = b"%PDF-1.4\nsynthetic sealed fixture " + who.encode()
            (root / pdf).write_bytes(raw)
            receipt = pdf + ".receipt.json"
            fingerprint = digest(source.encode())
            record = {"schema_version": 1, "kind": "private-practice-pdf", "fingerprint": fingerprint,
                "artifacts": {Path(pdf).name: digest(raw)}, "renderer": {"reference": "synthetic-native-pdf-worker"},
                "portable_links": paths, "effective_source": {}, "original_inputs": {source: digest((root / source).read_bytes())}, "factory_inputs": {}}
            (root / receipt).write_text(json.dumps(record))
            return {"ok": True, "pdf": pdf, "pdf_sha256": digest(raw), "receipt": receipt, "receipt_sha256": digest((root / receipt).read_bytes()),
                    "fingerprint": fingerprint, "portable_links": paths}
        return build

    def test_ca_es_en_pairs_preserve_names_seals_selection_and_no_gis_execution(self):
        for language in ("ca", "es", "en"):
            with self.subTest(language=language):
                root, spec, labels = self.fixture(language)
                with patch.object(editions, "provider_command", side_effect=AssertionError("No GIS invocation")), \
                        patch.object(editions, "verifier_identity", side_effect=AssertionError("No GIS runtime")), \
                        patch.object(editions.practice_pdf, "build", side_effect=self.renderer(root)):
                    result = editions.compose(root, Path(__file__).resolve().parents[1], "edition.json")
                self.assertFalse(result["publishes"])
                self.assertIsNone(result["gis"])
                self.assertIsNone(result["gis_verifier"])
                directory = root / result["path"]
                for who, packet in result["packages"].items():
                    stem = "table-demo" + ("-docent" if who == "docent" else "") + "-r1-" + language
                    self.assertEqual(packet["path"], stem + ".zip")
                    self.assertEqual(packet["pdf"]["path"], stem + ".pdf")
                    pdf = (directory / packet["pdf"]["path"]).read_bytes()
                    with zipfile.ZipFile(directory / packet["path"]) as archive:
                        self.assertEqual(archive.read(labels["basename"] + ".pdf"), pdf)
                        self.assertEqual("resources/resolved.xlsx" in archive.namelist(), who == "docent")
                        self.assertFalse(any(name.endswith("receipt.json") or name.startswith(("sources/", "payload/sources/")) for name in archive.namelist()))
                    proof = json.loads((directory / packet["pdf"]["receipt"]).read_bytes())
                    self.assertEqual(proof["sealed_source"]["sha256"], digest(pdf))
                with self.assertRaisesRegex(ValueError, "already exists"):
                    editions.compose(root, root, "edition.json")

    def test_teacher_data_hash_size_script_and_gis_forgery_are_rejected(self):
        for mutation in ("recipient", "hash", "size", "script", "gis"):
            root, spec, _ = self.fixture("ca")
            if mutation == "recipient":
                spec["selection"]["alumnat"].append("resolved")
            elif mutation in {"hash", "size"}:
                spec["materials"][0]["sha256" if mutation == "hash" else "bytes"] = "0" * 64 if mutation == "hash" else 1
            elif mutation == "script":
                spec["materials"][0]["path"] = "practiques/table-demo/prepare.py"
            else:
                spec["gis"] = {"bundle": "fake"}
            (root / "edition.json").write_text(json.dumps(spec))
            with self.subTest(mutation=mutation), patch.object(editions.practice_pdf, "build") as renderer, self.assertRaises(Exception):
                editions.compose(root, root, "edition.json", dry_run=True)
            renderer.assert_not_called()
            self.assertFalse((root / "dist").exists())

    def test_existing_gis_schema_is_unchanged_and_v2_requires_explicit_mode(self):
        root, spec, _ = self.fixture("en")
        legacy = editions.schema()
        self.assertEqual(legacy["properties"]["schema_version"]["const"], 1)
        self.assertIn("gis", legacy["required"])
        del spec["mode"]
        (root / "edition.json").write_text(json.dumps(spec))
        with self.assertRaises(Exception):
            editions.load_config(root, "edition.json")
        self.assertEqual(editions.schema(2)["properties"]["mode"]["const"], "tabular")


if __name__ == "__main__":
    unittest.main()
