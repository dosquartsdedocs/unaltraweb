from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from unaltraweb_mcp import artifact_publication as pub, artifact_transports, original_archive as intake, practice_editions
from original_archive_fixtures import ArchiveFixture
import test_artifact_publication as providers


class OriginalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f = ArchiveFixture(self)

    def plan(self):
        return intake.plan(self.f.root, self.f.control, self.f.sha)

    def snapshot(self):
        return intake.snapshot(self.f.root, self.f.control, self.f.sha, self.plan()["plan_sha256"])

    def test_readonly_stable_no_pdf_original_seal_or_execution(self):
        f = self.f
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in f.root.rglob("*") if path.is_file()}
        with patch.object(artifact_transports, "connect", side_effect=AssertionError("No auth/network")), \
                patch.object(practice_editions, "provider_command", side_effect=AssertionError("No GIS")), \
                patch.object(practice_editions.practice_pdf, "build", side_effect=AssertionError("No PDF")):
            first, second = self.plan(), self.plan()
        self.assertEqual(first, second)
        self.assertFalse(first["publishes"] or first["network"] or first["credentials_resolved"])
        plan = first["plan"]
        self.assertEqual(plan["checks"]["zip"]["files"], 7)
        self.assertEqual(plan["truth"]["classification_origin"], "caller-selection-not-original-seal")
        self.assertFalse(plan["truth"]["pdf_required"] or plan["truth"]["approved_by_admission"] or plan["truth"]["full_offline_qualified"])
        self.assertEqual(plan["specification"]["classification"]["full_offline"], "requires-network")
        self.assertFalse(any(name.endswith(".pdf") for name in plan["checks"]["zip"]["observed_members"]))
        self.assertEqual(len(plan["checks"]["checksums"]), 2)
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in f.root.rglob("*") if path.is_file()})
        self.assertFalse((f.root / "must-not-execute").exists())

    def test_plan_snapshot_stage_private_native_readback_preserves_original_bytes_and_truth(self):
        f = self.f
        archive_before = (f.root / f.path).read_bytes()
        request_before = (f.root / f.control).read_bytes()
        admitted = self.snapshot()
        self.assertEqual(json.loads((f.root / admitted["receipt"]).read_bytes())["kind"], intake.KIND)
        root = f.root / admitted["snapshot"]
        self.assertEqual((root / "files/original-starter.zip").read_bytes(), archive_before)
        self.assertEqual(root.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in root.rglob("*") if path.is_file()))
        _, sha = f.route(admitted)
        staged = pub.stage(f.root, pub.CONFIG, sha, "starter", "sandbox/artifacts/starter/archive")
        metadata = json.loads(staged["metadata"])
        self.assertEqual(metadata["classification"]["role"], "unknown")
        self.assertEqual(metadata["classification"]["language"], "unknown")
        self.assertFalse(metadata["approved_by_admission"] or metadata["native_reopen_verified"] or metadata["scientific_validation_performed"] or metadata["public_edition"])
        self.assertEqual(staged["manifest"]["native"]["format"], "unaltraweb-original-private-archive-v1")
        for value in ("assets/", "context/", "starter/README", "build.py", "PRIVATE_", "wms.example", "original_inputs"):
            self.assertNotIn(value, staged["metadata"])
        client = providers.MemoryS3()
        connector = lambda selected, *args: artifact_transports.S3(selected["destination"], client, profile=selected["storage_profile"], layout=selected["delivery_layout"], anonymous=providers.Anonymous())
        first = pub.transfer(f.root, pub.CONFIG, sha, "starter", staged["stage"], staged["manifest_sha256"], connector=connector)
        verified = pub.transfer(f.root, pub.CONFIG, sha, "starter", staged["stage"], staged["manifest_sha256"], connector=connector, verify_only=True)
        self.assertTrue(first["verified"] and verified["verified"])
        self.assertFalse(first["remote_metadata_created"] or verified["publication_performed"])
        self.assertEqual(set(client.objects), {"originals/original-starter.zip"})
        self.assertEqual(client.objects["originals/original-starter.zip"]["Body"], archive_before)
        self.assertEqual((f.root / f.path).read_bytes(), archive_before)
        self.assertEqual((f.root / f.control).read_bytes(), request_before)
        self.assertFalse((f.root / "must-not-execute").exists())

    def test_private_role_classification_does_not_become_original_student_or_teacher_seal(self):
        f = self.f
        admitted = self.snapshot()
        config, sha = f.route(admitted)
        original = copy.deepcopy(config)
        for mutation in ("student", "teacher", "public", "named-v1", "pdf", "bucket"):
            config = copy.deepcopy(original)
            route = config["artifacts"]["starter"]
            if mutation in {"student", "teacher", "public"}:
                route["audience"] = mutation
            elif mutation == "named-v1":
                route["delivery_layout"] = mutation
            elif mutation == "pdf":
                route["format"] = mutation
            else:
                config["publication"]["targets"]["s4"]["bucket"] = "another-course"
            f.write(pub.CONFIG, pub.canonical(config))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pub.plan(f.root, pub.CONFIG, f.pin(pub.CONFIG)["sha256"], "starter")

    def test_known_caller_role_language_is_explicit_classification_only(self):
        f = self.f
        f.request["classification"].update(role="teacher", language="ca", human_approval="caller-reported")
        f.save()
        admitted = self.snapshot()
        config, _ = f.route(admitted)
        config["artifacts"]["starter"]["audience"] = "teacher"
        f.write(pub.CONFIG, pub.canonical(config))
        planned = pub.plan(f.root, pub.CONFIG, f.pin(pub.CONFIG)["sha256"], "starter")
        value = json.loads(planned["metadata"])
        self.assertFalse(value["approved_by_admission"])
        self.assertEqual(value["classification_origin"], "caller-selection-not-original-seal")

    def test_invalid_claim_language_or_extra_worker_fields_cannot_forge_lineage(self):
        f = self.f
        original = copy.deepcopy(f.request)
        for mutation in ("approval", "offline", "language", "worker", "purpose", "repo"):
            f.request = copy.deepcopy(original)
            if mutation == "approval":
                f.request["classification"]["human_approval"] = "approved"
            elif mutation == "offline":
                f.request["classification"]["full_offline"] = "qualified"
            elif mutation == "language":
                f.request["classification"]["language"] = "en"
            elif mutation == "worker":
                f.request["pdf_receipt"] = "invented/receipt.json"
            elif mutation == "purpose":
                f.request["purpose"] = "public-edition"
            else:
                f.request["consumer_repository"]["repository"] = "example/other"
            f.save()
            with self.subTest(mutation=mutation), self.assertRaises(Exception):
                self.plan()

    def test_changed_request_source_evidence_or_expected_plan_is_refused(self):
        f = self.f
        reviewed = self.plan()
        for source in (f.control, f.path, "context/provenance.md"):
            path = f.root / source
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(source=source), self.assertRaises(Exception):
                intake.snapshot(f.root, f.control, f.sha, reviewed["plan_sha256"])
            path.write_bytes(original)
            self.assertFalse((f.root / f.request["snapshot"]).exists())
        with self.assertRaises(pub.ArtifactPolicyError) as error:
            intake.snapshot(f.root, f.control, f.sha, "0" * 64)
        self.assertEqual(error.exception.code, "original-archive-reviewed-plan")

    def test_member_checksum_origin_and_crc_corruption_are_refused_without_repacking(self):
        f = self.f
        f.request["member_references"][0]["sha256"] = "0" * 64
        f.save()
        with self.assertRaises(pub.ArtifactPolicyError):
            self.plan()
        f.request["member_references"] = []
        f.request["checksums"][0]["base"] = "wrong-root"
        f.save()
        with self.assertRaises(pub.ArtifactPolicyError):
            self.plan()
        f.request["checksums"] = []
        original = (f.root / f.path).read_bytes()
        # Preserve the ZIP directory but corrupt an original STORED payload.
        raw = original.replace(b"PRIVATE_ORIGINAL_PROVENANCE", b"BROKEN__ORIGINAL_PROVENANCE", 1)
        self.assertNotEqual(raw, original)
        f.write(f.path, raw)
        f.request["archive"] = f.pin(f.path)
        f.save()
        with self.assertRaises(zipfile.BadZipFile):
            self.plan()

    def test_zip_unsafe_path_link_or_duplicate_uses_existing_bounded_verifier(self):
        f = self.f
        for kind in ("path", "link", "duplicate"):
            output = io.BytesIO()
            info = zipfile.ZipInfo("../outside" if kind == "path" else "starter/file")
            if kind == "link":
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(info, b"synthetic")
                if kind == "duplicate":
                    with self.assertWarns(UserWarning):
                        archive.writestr("starter/file", b"again")
            f.write(f.path, output.getvalue())
            f.request.update(archive=f.pin(f.path), member_references=[], checksums=[])
            f.save()
            with self.subTest(kind=kind), self.assertRaises(Exception):
                self.plan()

    def test_source_snapshot_symlinks_and_no_clobber_are_refused(self):
        f = self.f
        admitted = self.snapshot()
        original = (f.root / admitted["receipt"]).read_bytes()
        with self.assertRaises(pub.ArtifactPolicyError):
            self.snapshot()
        self.assertEqual((f.root / admitted["receipt"]).read_bytes(), original)
        f.request["snapshot"] = "sandbox/original-archives/link/trial"
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (f.root / "sandbox/original-archives/link").symlink_to(Path(outside.name), target_is_directory=True)
        f.save()
        with self.assertRaises(Exception):
            self.plan()
        self.assertEqual(list(Path(outside.name).iterdir()), [])
        f.request["snapshot"] = "sandbox/original-archives/fresh/trial"
        f.save()
        (f.root / f.path).unlink()
        (f.root / f.path).symlink_to(f.root / f.control)
        with self.assertRaises(Exception):
            self.plan()

    def test_snapshot_lineage_truth_and_neighbour_refusals(self):
        f = self.f
        admitted = self.snapshot()
        config, sha = f.route(admitted)
        base = f.root / admitted["snapshot"]
        group = json.loads((base / "admission.json").read_bytes())
        group["plan"]["truth"]["approved_by_admission"] = True
        group["plan_sha256"] = pub.digest(pub.canonical(group["plan"]))
        raw = pub.canonical(group)
        f.write(admitted["snapshot"] + "/admission.json", raw)
        f.write(admitted["receipt"], pub.canonical(intake.output_receipt(admitted["snapshot"], pub.digest(raw), f.request["archive_id"])))
        config["artifacts"]["starter"]["receipt_sha256"] = f.pin(admitted["receipt"])["sha256"]
        f.write(pub.CONFIG, pub.canonical(config))
        with self.assertRaises(pub.ArtifactPolicyError) as error:
            pub.plan(f.root, pub.CONFIG, f.pin(pub.CONFIG)["sha256"], "starter")
        self.assertEqual(error.exception.code, "original-archive-lineage")

    def test_snapshot_is_self_contained_and_collision_never_overwrites_original(self):
        f = self.f
        admitted = self.snapshot()
        _, sha = f.route(admitted)
        planned = pub.plan(f.root, pub.CONFIG, sha, "starter")
        shutil.rmtree(f.root / "assets")
        shutil.rmtree(f.root / "context")
        self.assertEqual(pub.plan(f.root, pub.CONFIG, sha, "starter"), planned)
        staged = pub.stage(f.root, pub.CONFIG, sha, "starter", "sandbox/artifacts/starter/source-gone")
        client = providers.MemoryS3()
        client.objects["originals/original-starter.zip"] = {"Body": b"other original object", "ContentType": "application/zip"}
        before = copy.deepcopy(client.objects)
        with self.assertRaises(pub.TransferFailure):
            pub.transfer(f.root, pub.CONFIG, sha, "starter", staged["stage"], staged["manifest_sha256"], connector=lambda selected,*args: artifact_transports.S3(selected["destination"], client, profile=selected["storage_profile"], layout=selected["delivery_layout"], anonymous=providers.Anonymous()))
        self.assertEqual(client.objects, before)
        self.assertFalse(client.puts)

    def test_cli_success_and_safe_refusal_diagnostics(self):
        f = self.f
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            status = intake.main(["plan", "--project", str(f.root), "--request", f.control, "--sha256", f.sha])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(stdout.getvalue())["read_only"])
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            status = intake.main(["snapshot", "--project", str(f.root), "--request", f.control, "--sha256", f.sha, "--expected-plan-sha256", "0" * 64])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "original-archive-reviewed-plan")
        for value in ("PRIVATE_", "build.py", "wms.example", str(f.root)):
            self.assertNotIn(value, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
