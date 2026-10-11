from __future__ import annotations

import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("practice_candidate_preparation", ROOT / "scripts/prepare_practice_candidate.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
from scripts import export_practice_runtime_archives as archives


class PracticeCandidateTests(unittest.TestCase):
    def test_candidate_source_is_the_approved_slice_not_the_current_branch(self):
        self.assertEqual(candidate.SOURCE, "d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0")
        self.assertEqual(candidate.APPROVED_PDF_SHA256, "c92ec8a0937e9c9c735171d889e5bbca19b7ccd9ccbe8d33da2b6c0e49f9a245")

    def test_wrong_prepared_image_and_wrong_platform_are_refused(self):
        observed = {"Id": "sha256:" + "1"*64, "RepoDigests": [candidate.BASE], "Os": "linux", "Architecture": "amd64",
                    "Size": 1234, "Config": {"Labels": {"org.opencontainers.image.revision": "a"*40}}}
        with patch.object(candidate, "run", return_value=json.dumps([observed])):
            with self.assertRaisesRegex(RuntimeError, "expected immutable"):
                candidate.image(candidate.BASE, "sha256:" + "2"*64)
        observed["Architecture"] = "arm64"
        with patch.object(candidate, "run", return_value=json.dumps([observed])):
            with self.assertRaisesRegex(RuntimeError, "Linux/amd64"):
                candidate.image(candidate.BASE)

    def test_existing_candidate_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="practice-candidate-unit-") as temporary:
            target = Path(temporary)
            (target / "keep.txt").write_text("retained")
            with patch.object(candidate, "run", return_value=str(ROOT)), patch.object(candidate, "image", return_value={}):
                with self.assertRaises(FileExistsError):
                    candidate.prepare(target)
            self.assertEqual((target / "keep.txt").read_text(), "retained")

    def test_outside_or_symlinked_candidate_path_is_refused(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="practice-candidate-unit-") as temporary:
            base = Path(temporary)
            target = base / "actual"
            target.mkdir()
            (base / "alias").symlink_to(target, target_is_directory=True)
            with patch.object(candidate, "run", return_value=str(ROOT)), patch.object(candidate, "image", return_value={}):
                for path in (base / "alias/new", ROOT.parent / "outside-candidate"):
                    with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, "non-symlink"):
                        candidate.prepare(path)
            self.assertEqual(list(target.iterdir()), [])

    def image_archive(self, path, source, *, tags=None):
        config = json.dumps({"os": "linux", "architecture": "amd64", "config": {
            "Labels": {"org.opencontainers.image.revision": source}}}).encode()
        identity = "sha256:" + hashlib.sha256(config).hexdigest()
        manifest = [{"Config": "config.json", "RepoTags": tags or [], "Layers": ["layer.tar"]}]
        with tarfile.open(path, "w:gz") as archive:
            for name, raw in (("config.json", config), ("manifest.json", json.dumps(manifest).encode()), ("layer.tar", b"opaque fixture layer")):
                entry = tarfile.TarInfo(name)
                entry.size = len(raw)
                archive.addfile(entry, io.BytesIO(raw))
        return identity

    def test_archive_checks_config_identity_own_producer_and_no_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "image.tar.gz"
            identity = self.image_archive(path, "b"*40)
            self.assertEqual(archives.verify_archive(path, identity, "b"*40)["source_revision"], "b"*40)
            for wrong_id, wrong_source in (("sha256:"+"a"*64, "b"*40), (identity, "c"*40)):
                with self.assertRaises(ValueError):
                    archives.verify_archive(path, wrong_id, wrong_source)
            self.image_archive(path, "b"*40, tags=["example:latest"])
            with self.assertRaisesRegex(ValueError, "tag aliases"):
                archives.verify_archive(path, identity, "b"*40)

    def test_runtime_export_reuses_controller_and_preserves_pdf_producer(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="runtime-archives-unit-") as temporary:
            base = Path(temporary)
            original = base / "retained.tar.gz"
            controller_id = self.image_archive(original, "c"*40)
            pdf_source = "b"*40
            pdf_fixture = base / "pdf-fixture.tar.gz"
            pdf_id = self.image_archive(pdf_fixture, pdf_source)
            pdf_ref = "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:"+"a"*64
            contract = {"consumer_integration": {"manual_pdf_image": pdf_ref}, "deployment_contract": {
                "manual_pdf_workers": [{"reference": pdf_ref, "producer_sha": pdf_source}]}}
            def inspect(reference, expected):
                return {"reference": reference, "image_id": expected, "source_revision": "c"*40 if expected == controller_id else pdf_source,
                        "size": 4096, "os": "linux", "architecture": "amd64", "repo_digests": [reference] if "@" in reference else []}
            def export(identifier, destination):
                self.assertEqual(identifier, pdf_id)
                destination.write_bytes(pdf_fixture.read_bytes())
                return {"path": destination.name, "sha256": archives.sha256(destination), "bytes": destination.stat().st_size, "format": "docker-save-gzip"}
            with patch.object(archives, "distribution_contract", return_value=contract), patch.object(archives, "image", side_effect=inspect), \
                    patch.object(archives, "export_image", side_effect=export) as exporter:
                result = archives.prepare(base/"delivery", controller_id, controller_id, "c"*40, pdf_id,
                                          controller_archive=original, controller_archive_sha256=archives.sha256(original))
                exporter.assert_called_once()
                self.assertEqual(result["images"]["manual_pdf"]["image"]["source_revision"], pdf_source)
                self.assertEqual((base/"delivery/controller.docker.tar.gz").read_bytes(), original.read_bytes())
                before = {path.name: path.read_bytes() for path in (base/"delivery").iterdir()}
                with self.assertRaises(FileExistsError):
                    archives.prepare(base/"delivery", controller_id, controller_id, "c"*40, pdf_id)
                self.assertEqual({path.name: path.read_bytes() for path in (base/"delivery").iterdir()}, before)
            with patch.object(archives, "distribution_contract", return_value=contract), \
                    patch.object(archives, "image", return_value={"source_revision": "c"*40}), \
                    patch.object(archives, "export_image") as exporter, self.assertRaisesRegex(ValueError, "own producer"):
                archives.prepare(base/"wrong-producer", controller_id, controller_id, "c"*40, pdf_id)
            exporter.assert_not_called()
            self.assertFalse((base/"wrong-producer").exists())
