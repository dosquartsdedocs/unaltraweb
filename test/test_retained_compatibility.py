from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from unaltraweb_mcp import artifact_publication as publication, artifact_transports, retained_intake as intake
import test_retained_intake as original_fixtures
import test_artifact_publication as transports
from retained_manifest_fixtures import file_root_readings


class RetainedCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.case = original_fixtures.RetainedIntakeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        file_root_readings(self.case)

    def test_representative_original_unchanged_through_complete_private_native_path(self):
        case = self.case
        original_request = (case.root / case.request_path).read_bytes()
        original_manifest = (case.root / case.manifest_path).read_bytes()
        requested = copy.deepcopy(case.request)
        # No teacher/case payload is required, even with their opaque rows retained.
        teacher = case.manifest["reading_receipts"][1]
        shutil.rmtree(case.root / teacher["job"])
        for name in ("LLEGIU-ME-docent.pdf", "retained-handoff-docent.zip"):
            (case.root / case.base / name).unlink()
        with patch.object(artifact_transports, "connect", side_effect=AssertionError("No real storage/auth")):
            planned = case.plan()
            self.assertEqual(case.plan(), planned)
            admitted = intake.snapshot(case.root, case.request_path, case.sha, planned["plan_sha256"])
        payload = planned["plan"]
        self.assertNotIn("run", payload["handoff"])
        self.assertEqual(payload["original_declarations"]["run"], {"present": False, "value": None})
        self.assertEqual(payload["original_declarations"]["local_candidate"], {"present": False, "value": None})
        self.assertFalse(payload["claims"]["human_approved"] or payload["claims"]["publishes"])
        ref = payload["original_references"]["alumnat"]
        self.assertEqual(ref["family"], "file-root-reading-receipts-v1")
        self.assertEqual(ref["reading_pointer"], "/reading_receipts/0")
        self.assertEqual(ref["source_sha256_origin"]["document"], "original-worker-receipt")
        self.assertEqual(ref["source_sha256"], requested["sources"][0]["sha256"])
        self.assertEqual(payload["package_checks"]["alumnat"]["worker"]["reading_source_bytes"], "fresh-exact-path")
        self.assertEqual(case.pin(case.request_path)["sha256"], case.sha)
        _, sha = case.routes(admitted)
        client = transports.MemoryS3()
        for identifier in admitted["receipts"]:
            staged = publication.stage(case.root, publication.CONFIG, sha, identifier, "sandbox/artifacts/" + identifier + "/representative")
            output = staged["manifest"]["files"][0]
            self.assertEqual((case.root / staged["stage"] / output["path"]).read_bytes(), (case.root / case.base / output["path"]).read_bytes())
            sidecar = staged["metadata"].encode()
            data = json.loads(sidecar)
            self.assertIsNone(data["local_candidate"])
            self.assertFalse(data["original_publishes"] or data["human_approved"] or data["approved_by_intake"] or data["public_edition"])
            for body in (b"PRIVATE_", b"sandbox/", b"practiques/", b"reading_receipts", b"command", b"stdout", b"renderer"):
                self.assertNotIn(body, sidecar)
            connector = lambda pub, *args: artifact_transports.S3(pub["destination"], client, profile=pub["storage_profile"], anonymous=transports.Anonymous())
            result = publication.transfer(case.root, publication.CONFIG, sha, identifier, staged["stage"], staged["manifest_sha256"], connector=connector)
            self.assertTrue(result["verified"])
            verified = publication.transfer(case.root, publication.CONFIG, sha, identifier, staged["stage"], staged["manifest_sha256"], connector=connector, verify_only=True)
            self.assertFalse(verified["publication_performed"] or verified["local_attempt"]["remote_mutation_requested"])
            self.assertTrue(all(row["access"]["public_url"] is None for row in result["files"]))
        self.assertEqual(len(client.objects), 8)
        self.assertEqual(original_request, (case.root / case.request_path).read_bytes())
        self.assertEqual(original_manifest, (case.root / case.manifest_path).read_bytes())
        self.assertFalse((case.root / "never-execute").exists())
        self.assertEqual((case.root / admitted["snapshot"] / "local/manifest/manifest.json").read_bytes(), original_manifest)

    def test_original_run_and_optional_claim_absence_or_explicit_values_stay_original(self):
        case = self.case
        for value in (None, "original-run-not-snapshot-label"):
            case.manifest["run"] = value
            case.refresh()
            plan = case.plan()["plan"]
            self.assertEqual(plan["handoff"]["run"], value)
            self.assertEqual(plan["original_declarations"]["run"], {"present": True, "value": value})
            self.assertNotEqual(plan["handoff"]["run"], Path(case.request["snapshot"]).name)
        del case.manifest["run"]
        case.request["sources"] = []
        case.refresh()
        plan = case.plan()["plan"]
        self.assertNotIn("run", plan["handoff"])
        self.assertIsNone(plan["claims"]["local_candidate"])
        self.assertFalse(plan["claims"]["publishes"])
        self.assertEqual(plan["package_checks"]["alumnat"]["worker"]["reading_source_bytes"], "inherited-reference-only")
        admitted = case.snapshot()
        _, sha = case.routes(admitted)
        self.assertTrue(publication.plan(case.root, publication.CONFIG, sha, "alumnat-guide")["ok"])

    def test_conflicting_aliases_partial_families_and_selected_row_ambiguity_are_refused(self):
        case = self.case
        original = copy.deepcopy(case.manifest)
        for wrong in ("alias", "partial-family", "duplicate", "conflicting-duplicate", "missing"):
            case.manifest = copy.deepcopy(original)
            if wrong == "alias":
                case.manifest["packages"][0]["archive"] = "other.zip"
            elif wrong == "partial-family":
                case.manifest["packages"][0]["reading_source"] = case.manifest["reading_receipts"][0]["source"]
            elif wrong == "missing":
                case.manifest["reading_receipts"] = case.manifest["reading_receipts"][1:]
            else:
                duplicate = copy.deepcopy(case.manifest["reading_receipts"][0])
                if wrong == "conflicting-duplicate":
                    duplicate["source"] = "different/source.md"
                case.manifest["reading_receipts"].append(duplicate)
            case.refresh()
            with self.subTest(wrong=wrong), self.assertRaises(intake.RetainedIntakeError) as raised:
                case.plan()
            self.assertIn(raised.exception.code, {"retained-archive-reference", "retained-manifest-format", "retained-reading-ambiguous"})
        case.manifest = copy.deepcopy(original)
        case.manifest["packages"][0]["archive"] = case.manifest["packages"][0]["file"]
        case.refresh()
        self.assertTrue(case.plan()["ok"])

    def test_strict_worker_source_pdf_recipient_language_bindings_have_safe_codes(self):
        case = self.case
        original = copy.deepcopy(case.manifest)
        for key, value, code in (("role", "docent", "retained-recipient-mismatch"), ("audience", "docent", "retained-recipient-mismatch"),
            ("language", "es", "retained-language-mismatch"), ("source", "PRIVATE_WRONG_SOURCE", "retained-source-reference"),
            ("receipt", "sandbox/other/receipt.json", "retained-worker-reference"), ("receipt_sha256", "0" * 64, "retained-worker-reference"),
            ("pdf", "sandbox/other/outputs/LLEGIU-ME.pdf", "retained-reading-reference"), ("pdf_sha256", "0" * 64, "retained-reading-reference"),
            ("job", "sandbox/other", "retained-reading-reference")):
            case.manifest = copy.deepcopy(original)
            case.manifest["reading_receipts"][0][key] = value
            case.refresh()
            with self.subTest(key=key), self.assertRaises(intake.RetainedIntakeError) as raised:
                case.plan()
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn("PRIVATE_", str(raised.exception))
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                status = intake.main(["plan", "--project", str(case.root), "--request", case.request_path, "--sha256", case.sha])
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], code)
            for body in ("PRIVATE_", "command", "stdout", "renderer", str(case.root)):
                self.assertNotIn(body, stderr.getvalue())

    def test_corrupt_selected_bytes_or_source_worker_references_cannot_be_resealed(self):
        case = self.case
        reviewed = case.plan()
        path = case.root / case.request["sources"][0]["path"]
        before = path.read_bytes()
        path.write_bytes(before + b"changed")
        with self.assertRaises(intake.RetainedIntakeError) as raised:
            intake.snapshot(case.root, case.request_path, case.sha, reviewed["plan_sha256"])
        self.assertEqual(raised.exception.code, "retained-input-changed")
        path.write_bytes(before)
        row = case.request["packages"][0]
        worker = json.loads((case.root / row["pdf_receipt"]["path"]).read_bytes())
        worker["original_inputs"].clear()
        case.write(row["pdf_receipt"]["path"], publication.canonical(worker))
        row["pdf_receipt"] = case.pin(row["pdf_receipt"]["path"])
        case.manifest["reading_receipts"][0]["receipt_sha256"] = row["pdf_receipt"]["sha256"]
        case.refresh()
        with self.assertRaises(intake.RetainedIntakeError) as raised:
            case.plan()
        self.assertEqual(raised.exception.code, "retained-source-reference")

    def test_original_reference_origin_and_declarations_are_verified_after_snapshot(self):
        case = self.case
        admitted = case.snapshot()
        base = case.root / admitted["snapshot"]
        original = json.loads((base / "admission.json").read_bytes())
        for field in ("original_references", "original_declarations"):
            group = copy.deepcopy(original)
            group["plan"][field] = {}
            group["plan_sha256"] = publication.digest(publication.canonical(group["plan"]))
            raw = publication.canonical(group)
            (base / "admission.json").write_bytes(raw)
            selected = admitted["receipts"]["alumnat-guide"]
            receipt = intake.output_receipt(admitted["snapshot"], publication.digest(raw), "alumnat-guide")
            case.write(selected["path"], publication.canonical(receipt))
            with intake.closing(intake.h.Workspace(str(case.root))) as workspace, self.assertRaises(intake.RetainedIntakeError) as raised:
                intake.artifact(workspace, case.root, selected["path"], case.pin(selected["path"])["sha256"])
            self.assertEqual(raised.exception.code, "retained-admission-lineage")

    def test_legacy_admission_and_original_stage_identity_survive_upgrade(self):
        case = original_fixtures.RetainedIntakeTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.manifest["publishes"] = False
        case.refresh()
        admitted = case.snapshot()
        base = case.root / admitted["snapshot"]
        group = json.loads((base / "admission.json").read_bytes())
        # Frozen PR134 admission shape: old package-local refs/run, no additive
        # reference/declaration projection. Original byte/receipt contracts stay v1.
        for key in ("original_references", "original_declarations"):
            del group["plan"][key]
        del group["plan"]["claims"]["publishes"]
        group["plan_sha256"] = publication.digest(publication.canonical(group["plan"]))
        raw = publication.canonical(group)
        (base / "admission.json").write_bytes(raw)
        for identifier, row in admitted["receipts"].items():
            case.write(row["path"], publication.canonical(intake.output_receipt(admitted["snapshot"], publication.digest(raw), identifier)))
            row["sha256"] = case.pin(row["path"])["sha256"]
        _, sha = case.routes(admitted)
        staged = publication.stage(case.root, publication.CONFIG, sha, "alumnat-guide", "sandbox/artifacts/alumnat-guide/legacy")
        metadata = (case.root / staged["stage"] / "artifact.json").read_bytes()
        self.assertNotIn(b"original_publishes", metadata)
        manifest = staged["manifest"]
        manifest["producer"]["revision"] = "sha256:" + "a" * 64
        raw = publication.canonical(manifest)
        case.write(staged["stage"] + "/product.json", raw)
        retained = publication.plan(case.root, publication.CONFIG, sha, "alumnat-guide", staged=staged["stage"], manifest_sha256=publication.digest(raw))
        self.assertEqual(retained["manifest"], manifest)
        self.assertEqual(retained["manifest_sha256"], publication.digest(raw))
        self.assertEqual((case.root / staged["stage"] / "artifact.json").read_bytes(), metadata)


if __name__ == "__main__":
    unittest.main()
