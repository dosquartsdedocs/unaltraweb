from __future__ import annotations

import copy
import io
import json
import unittest
from unittest.mock import patch
import zipfile

from unaltraweb_mcp import artifact_publication as pub, artifact_transports as transport, retained_intake as intake
import test_retained_intake as fixtures
import test_artifact_publication as providers
from retained_variant_fixtures import VARIANTS, variant
from zip_only_fixtures import flat_routes


class RetainedVariantTests(unittest.TestCase):
    def fixture(self, kind):
        case = fixtures.RetainedIntakeTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        variant(case, kind)
        return case

    def test_all_three_original_shapes_complete_zip_only_private_pipeline(self):
        for kind in VARIANTS:
            with self.subTest(kind=kind):
                case = self.fixture(kind)
                request = (case.root / case.request_path).read_bytes()
                manifest = (case.root / case.manifest_path).read_bytes()
                planned = case.plan()
                self.assertEqual(planned, case.plan())
                admitted = case.snapshot()
                self.assertEqual((case.root / admitted["snapshot"] / "local/manifest/manifest.json").read_bytes(), manifest)
                _, sha = flat_routes(case, admitted)
                client = providers.MemoryS3()
                for item in case.request["packages"]:
                    who = item["recipient"]
                    ref = planned["plan"]["original_references"][who]
                    self.assertEqual(ref["source_sha256"], next(row["sha256"] for row in case.request["sources"] if row["path"] == ref["source"]))
                    self.assertEqual(ref["source_sha256_origin"]["document"], "original-worker-receipt")
                    self.assertEqual(ref["delivered_pdf_sha256"], item["pdf"]["sha256"])
                    if kind == "reading-pdf-hash":
                        declared = ref["original_field_origins"]["reading_hash"]
                        self.assertEqual((declared["value"], declared["semantics"]), (item["pdf"]["sha256"], "delivered-pdf"))
                        self.assertNotEqual(declared["value"], ref["source_sha256"])
                    else:
                        self.assertFalse(ref["original_field_origins"]["reading_hash"]["present"])
                        self.assertTrue(ref["worker_reference_origin"].endswith("/reading_receipt"))
                    staged = pub.stage(case.root, pub.CONFIG, sha, who + "-packet", "sandbox/artifacts/" + who + "/variant")
                    connector = lambda selected,*args: transport.S3(selected["destination"], client, profile=selected["storage_profile"], layout=selected["delivery_layout"], anonymous=providers.Anonymous())
                    for verify in (False, True):
                        receipt = pub.transfer(case.root, pub.CONFIG, sha, who + "-packet", staged["stage"], staged["manifest_sha256"], connector=connector, verify_only=verify)
                        self.assertTrue(receipt["verified"])
                        self.assertFalse(receipt["remote_metadata_created"])
                        if verify:
                            self.assertFalse(receipt["publication_performed"])
                    body = client.objects["practiques/ca/" + item["archive"]["path"].split("/")[-1]]["Body"]
                    self.assertEqual(body, (case.root / item["archive"]["path"]).read_bytes())
                    with zipfile.ZipFile(io.BytesIO(body)) as archive:
                        self.assertEqual(archive.read(item["reading_member"]), (case.root / item["pdf"]["path"]).read_bytes())
                    for value in ("reading_receipt", "reading_sha256", "original_inputs", "practiques/", "sandbox/", "build.py", "PRIVATE_"):
                        self.assertNotIn(value, staged["metadata"])
                self.assertEqual(len(client.objects), 2)
                self.assertEqual((case.root / case.request_path).read_bytes(), request)
                self.assertEqual((case.root / case.manifest_path).read_bytes(), manifest)
                self.assertFalse((case.root / "never-execute").exists())

    def test_conflicting_role_recipient_aliases_and_duplicate_packages_refuse_safely(self):
        for wrong in ("conflict", "unknown", "duplicate"):
            case = self.fixture("role-reading-receipt")
            original = case.manifest["packages"][0]
            if wrong == "conflict":
                original["recipient"] = "docent"
            elif wrong == "unknown":
                original["role"] = "private-body-not-a-role"
            else:
                case.manifest["packages"][1]["role"] = original["role"]
            case.refresh()
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                case.plan()
            self.assertFalse((case.root / case.request["snapshot"]).exists())
        case = self.fixture("role-reading-receipt")
        for original in case.manifest["packages"]:
            original["recipient"] = original["role"]
        case.refresh()
        refs = case.plan()["plan"]["original_references"]
        self.assertEqual(refs["alumnat"]["original_field_origins"]["recipient"], ["/packages/0/recipient", "/packages/0/role"])

    def test_conflicting_worker_pointer_and_hash_aliases_never_choose_a_fallback(self):
        for key in ("pdf_receipt", "reading_receipt", "pdf_receipt_sha256", "reading_receipt_sha256", "receipt_sha256"):
            case = self.fixture("recipient-receipt-sha")
            case.manifest["packages"][0][key] = "sandbox/other/receipt.json" if key.endswith("receipt") else "0" * 64
            case.refresh()
            with self.subTest(key=key), self.assertRaises(intake.RetainedIntakeError) as error:
                case.plan()
            self.assertEqual(error.exception.code, "retained-worker-reference")
        case = self.fixture("recipient-receipt-sha")
        original = case.manifest["packages"][0]
        original["pdf_receipt"] = original["reading_receipt"]
        original["pdf_receipt_sha256"] = original["receipt_sha256"]
        original["reading_receipt_sha256"] = original["receipt_sha256"]
        case.refresh()
        self.assertEqual(len(case.plan()["plan"]["original_references"]["alumnat"]["original_field_origins"]["worker_sha256"]), 3)

    def test_pdf_hash_never_becomes_markdown_or_an_unknown_reading_hash(self):
        case = self.fixture("reading-pdf-hash")
        case.manifest["packages"][0]["reading_sha256"] = "0" * 64
        case.refresh()
        with self.assertRaises(intake.RetainedIntakeError) as error:
            case.plan()
        self.assertEqual(error.exception.code, "retained-reading-hash-reference")
        case = self.fixture("reading-pdf-hash")
        source = case.request["sources"][0]
        case.write(source["path"], (case.root / case.request["packages"][0]["pdf"]["path"]).read_bytes())
        case.request["sources"][0] = case.pin(source["path"])
        case.save_request()
        with self.assertRaises(intake.RetainedIntakeError) as error:
            case.plan()
        self.assertEqual(error.exception.code, "retained-source-reference")
        case = self.fixture("reading-pdf-hash")
        item = case.request["packages"][0]
        worker = json.loads((case.root / item["pdf_receipt"]["path"]).read_bytes())
        worker["original_inputs"][worker["source"]] = item["pdf"]["sha256"]
        case.write(item["pdf_receipt"]["path"], pub.canonical(worker))
        item["pdf_receipt"] = case.pin(item["pdf_receipt"]["path"])
        case.manifest["packages"][0]["pdf_receipt_sha256"] = item["pdf_receipt"]["sha256"]
        case.refresh()
        with self.assertRaises(intake.RetainedIntakeError) as error:
            case.plan()
        self.assertEqual(error.exception.code, "retained-reading-hash-reference")

    def test_modified_reference_projection_and_original_bytes_refused_later_in_stage(self):
        case = self.fixture("reading-pdf-hash")
        admitted = case.snapshot()
        config, _ = flat_routes(case, admitted)
        path = case.root / admitted["snapshot"] / "admission.json"
        group = json.loads(path.read_bytes())
        group["plan"]["original_references"]["alumnat"]["original_field_origins"]["reading_hash"]["semantics"] = "markdown-source"
        group["plan_sha256"] = pub.digest(pub.canonical(group["plan"]))
        raw = pub.canonical(group)
        path.write_bytes(raw)
        for identifier, row in admitted["receipts"].items():
            case.write(row["path"], pub.canonical(intake.output_receipt(admitted["snapshot"], pub.digest(raw), identifier)))
            config["artifacts"][identifier]["receipt_sha256"] = case.pin(row["path"])["sha256"]
        case.write(pub.CONFIG, pub.canonical(config))
        with self.assertRaises(intake.RetainedIntakeError) as error:
            pub.stage(case.root, pub.CONFIG, case.pin(pub.CONFIG)["sha256"], "alumnat-packet", "sandbox/artifacts/changed/projection")
        self.assertEqual(error.exception.code, "retained-admission-lineage")
        case = self.fixture("role-reading-receipt")
        planned = case.plan()
        item = case.request["packages"][0]
        case.write(item["pdf_receipt"]["path"], b"changed ORIGINAL worker bytes")
        with self.assertRaises(intake.RetainedIntakeError):
            intake.snapshot(case.root, case.request_path, case.sha, planned["plan_sha256"])

    def test_old_canonical_and_root_projections_stay_exact(self):
        case = fixtures.RetainedIntakeTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        refs = case.plan()["plan"]["original_references"]
        item = case.request["packages"][0]
        self.assertEqual(refs["alumnat"], {"family": "package-local-reading-v1", "package_pointer": "/packages/0", "archive_fields": ["archive"],
            "reading_pointer": "/packages/0", "source": case.manifest["packages"][0]["reading_source"], "source_sha256": case.request["sources"][0]["sha256"],
            "source_sha256_origin": {"document": "original-manifest", "pointer": "/packages/0/reading_sha256"},
            "worker_reference_origin": "/packages/0/pdf_receipt", "worker_receipt": item["pdf_receipt"], "pdf_artifact": item["pdf_artifact"],
            "reading_member": item["reading_member"], "recipient": "alumnat", "language": "ca"})
        admitted = case.snapshot()
        _, sha = flat_routes(case, admitted)
        staged = pub.stage(case.root, pub.CONFIG, sha, "alumnat-packet", "sandbox/artifacts/old/canonical")
        before = {path.name: path.read_bytes() for path in (case.root / staged["stage"]).iterdir()}
        verified = pub.plan(case.root, pub.CONFIG, sha, "alumnat-packet", staged=staged["stage"], manifest_sha256=staged["manifest_sha256"])
        self.assertEqual(verified["manifest_sha256"], staged["manifest_sha256"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in (case.root / staged["stage"]).iterdir()})

    def test_safe_diagnostics_do_not_dump_unsafe_script_or_original_bodies(self):
        case = self.fixture("role-reading-receipt")
        case.manifest["packages"][0]["receipt_sha256"] = "SECRET-SENTINEL"
        case.refresh()
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            status = intake.main(["plan", "--project", str(case.root), "--request", case.request_path, "--sha256", case.sha])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "retained-worker-reference")
        for value in ("SECRET-SENTINEL", "build.py", "PRIVATE_", str(case.root)):
            self.assertNotIn(value, stderr.getvalue())
        self.assertFalse((case.root / "never-execute").exists())


if __name__ == "__main__":
    unittest.main()
