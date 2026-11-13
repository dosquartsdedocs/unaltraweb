from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from pypdf import PdfWriter

from unaltraweb_mcp import artifact_publication as publication, artifact_transports, retained_intake as intake, practice_editions
import test_artifact_publication as transport_fixtures


class RetainedIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "remote", "add", "origin", "git@github.com:example/course.git"], check=True)
        self.write(".gitignore", b"sandbox/\ndist/\n")
        self.write("_config.yml", publication.canonical({"lang": "ca", "languages": ["ca"], "exclude": ["practiques/", "sandbox/", "dist/", "context/"],
            "unaltraweb": {"site_profile": "unaltremanual"}}))
        self.base = "dist/practiques/retained-handoff/ca"
        self.manifest_path = self.base + "/manifest.json"
        self.request_path = ".unaltraweb/retained-intake.json"
        self.manifest = {"activity": "different-activity", "version": "current-r1", "run": "original-run-label", "packages": [],
            "proof": "sandbox/practiques/older-run/not-present.json", "proof_sha256": "a" * 64,
            "moodle_statement_sha256": "b" * 64, "human_approved": False, "exact_historical_bundle": False, "local_candidate": True}
        self.request = {"kind": "unaltraweb.retained-private-intake", "schema_version": 1, "purpose": "private-archive",
            "consumer_repository": {"remote": "origin", "host": "github.com", "repository": "example/course"},
            "handoff": {"slug": "retained-handoff", "activity": "different-activity", "language": "ca", "manifest": {}},
            "snapshot": "sandbox/retained-handoffs/retained-handoff/pilot-1", "packages": [], "evidence": [], "sources": []}
        for who in ("alumnat", "docent"):
            pdf = "LLEGIU-ME" + ("-docent" if who == "docent" else "") + ".pdf"
            archive = "retained-handoff" + ("-docent" if who == "docent" else "") + ".zip"
            source = f"practiques/different-activity/ca/{who}/LLEGIU-ME.md"
            self.write(source, ("# PRIVATE_READING_BODY_" + who + "\n").encode())
            writer, output = PdfWriter(), io.BytesIO()
            writer.add_blank_page(width=400, height=300)
            writer.add_metadata({"/Title": "PRIVATE_PDF_BODY_" + who})
            writer.write(output)
            raw = output.getvalue()
            self.write(self.base + "/" + pdf, raw)
            member = "original-zip-root/LLEGIU-ME.pdf"
            members = {member: raw, "original-zip-root/resources/data.csv": ("SYNTHETIC_DATA_" + who).encode()}
            zipped = io.BytesIO()
            with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name, body in members.items():
                    target.writestr(name, body)
            self.write(self.base + "/" + archive, zipped.getvalue())
            receipt = f"sandbox/practiques/different-activity/worker-{who}/receipt.json"
            worker = {"kind": "private-practice-pdf", "schema_version": 1, "source": source, "fingerprint": "c" * 64,
                "effective_source": {"markdown": "outputs/source.effective.md", "markdown_sha256": "d" * 64},
                "factory_inputs": {"scripts/manual/templates/practice.tex": "e" * 64}, "renderer": {"reference": "retained-unverified-image"},
                "original_inputs": {source: self.pin(source)["sha256"]}, "artifacts": {"outputs/LLEGIU-ME.pdf": publication.digest(raw)}}
            self.write(receipt, publication.canonical(worker))
            self.manifest["packages"].append({"recipient": who, "archive": archive, "sha256": self.pin(self.base + "/" + archive)["sha256"],
                "members": {name: publication.digest(body) for name, body in members.items()}, "reading_source": source,
                "reading_sha256": self.pin(source)["sha256"], "pdf_receipt": receipt, "pdf_receipt_sha256": self.pin(receipt)["sha256"]})
            self.request["packages"].append({"recipient": who, "archive": self.pin(self.base + "/" + archive), "pdf": self.pin(self.base + "/" + pdf),
                "pdf_receipt": self.pin(receipt), "pdf_artifact": "outputs/LLEGIU-ME.pdf", "reading_member": member,
                "selected": [{"id": who + "-guide", "format": "pdf"}, {"id": who + "-packet", "format": "zip"}]})
            self.request["sources"].append(self.pin(source))
        self.write("context/current-handoff.json", publication.canonical({"proof": "context/stronger-proof.json", "note": "PRIVATE_LOCAL_PROOF_BODY"}))
        self.write("context/stronger-proof.json", publication.canonical({"exact_zip_claim": "inherited", "native_run": "not-reexecuted"}))
        self.request["evidence"] = [{"role": "current-handoff", "file": self.pin("context/current-handoff.json")},
                                    {"role": "proof", "file": self.pin("context/stronger-proof.json")}]
        self.refresh()

    def write(self, path, raw):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    def pin(self, path):
        raw = (self.root / path).read_bytes()
        return {"path": path, "sha256": publication.digest(raw), "bytes": len(raw)}

    def refresh(self):
        self.write(self.manifest_path, publication.canonical(self.manifest))
        self.request["handoff"]["manifest"] = self.pin(self.manifest_path)
        checksum_path = self.base + "/SHA256SUMS"
        names = [self.manifest_path, *[item[key]["path"] for item in self.request["packages"] for key in ("archive", "pdf")]]
        self.write(checksum_path, "".join(self.pin(name)["sha256"] + "  " + Path(name).name + "\n" for name in names).encode())
        self.request["evidence"] = [row for row in self.request["evidence"] if row["role"] != "checksums"] + [{"role": "checksums", "file": self.pin(checksum_path)}]
        self.save_request()

    def save_request(self):
        self.write(self.request_path, publication.canonical(self.request))
        self.sha = self.pin(self.request_path)["sha256"]
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore", "_config.yml", self.request_path, "practiques"], check=True)

    def plan(self):
        return intake.plan(self.root, self.request_path, self.sha)

    def snapshot(self):
        return intake.snapshot(self.root, self.request_path, self.sha, self.plan()["plan_sha256"])

    def routes(self, admitted):
        config = {"kind": "unaltraweb.practice-artifact-storage", "schema_version": 2, "consumer_repository": self.request["consumer_repository"],
            "publication": {"kind": "gacontext.publication-policy", "schema_version": 1, "project_id": "private-course", "default_target": "s4", "targets": {
                "s4": {"driver": "s3", "endpoint": "https://s3.example.invalid", "region": "synthetic-1", "bucket": "course", "prefix": "private/v1",
                       "visibility": "private", "audiences": ["student", "teacher", "private", "public"], "auth_ref": "explicit-project-binding"},
                "github": {"driver": "github-release", "repository": "example/course", "release": "existing-products", "visibility": "public", "audiences": ["student", "public"], "auth_ref": "project-ci"}}},
            "artifacts": {}}
        for identifier, row in admitted["receipts"].items():
            config["artifacts"][identifier] = {"target": "s4", "audience": "teacher" if row["recipient"] == "docent" else "student",
                "storage_profile": "authenticated-private-v1", "receipt": row["path"], "receipt_sha256": row["sha256"], "format": row["format"]}
        path = publication.CONFIG
        self.write(path, publication.canonical(config))
        subprocess.run(["git", "-C", str(self.root), "add", path], check=True)
        return config, self.pin(path)["sha256"]

    def test_plan_is_readonly_stable_explicit_and_calls_no_runtime_or_transport(self):
        before = {path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        with patch.object(artifact_transports, "connect", side_effect=AssertionError("No auth/transport")), \
                patch.object(practice_editions, "provider_command", side_effect=AssertionError("No GIS")), \
                patch.object(practice_editions.practice_pdf, "inspect_image", side_effect=AssertionError("No runtime selection")):
            first, second = self.plan(), self.plan()
        self.assertEqual(first, second)
        self.assertNotEqual(first["plan"]["handoff"]["slug"], first["plan"]["handoff"]["activity"])
        self.assertFalse(first["publishes"] or first["credentials_resolved"] or first["network"])
        self.assertEqual(first["plan"]["claims"]["human_approved"], False)
        self.assertEqual(first["plan"]["claims"]["references"]["proof"]["state"], "inherited-unresolved")
        self.assertEqual(first["plan"]["package_checks"]["alumnat"]["zip"]["member_content_hashes"], "freshly-checked")
        self.assertFalse((self.root / self.request["snapshot"]).exists())
        after = {path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_snapshot_copies_only_selected_originals_and_local_evidence_preserving_alias_and_false(self):
        self.request["packages"][0]["selected"] = [{"id": "only-student-guide", "format": "pdf"}]
        self.request["packages"][1]["selected"] = [{"id": "only-teacher-packet", "format": "zip"}]
        self.save_request()
        original = {path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
                    for path in self.root.rglob("*") if path.is_file() and ".git" not in path.parts}
        admitted = self.snapshot()
        base = self.root / admitted["snapshot"]
        self.assertEqual({path.name for path in (base / "files").iterdir()}, {"LLEGIU-ME.pdf", "retained-handoff-docent.zip"})
        for name in ("LLEGIU-ME.pdf", "retained-handoff-docent.zip"):
            self.assertEqual((base / "files" / name).read_bytes(), (self.root / self.base / name).read_bytes())
        with zipfile.ZipFile(base / "files/retained-handoff-docent.zip") as archive:
            self.assertIn("original-zip-root/LLEGIU-ME.pdf", archive.namelist())
        for name, before in original.items():
            path = self.root / name
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino), before)
        group = json.loads((base / "admission.json").read_bytes())
        self.assertFalse(group["plan"]["claims"]["human_approved"] or group["plan"]["claims"]["approved_by_intake"])
        self.assertTrue(any(row["source"].endswith("current-handoff.json") for row in group["plan"]["copies"]))
        self.assertFalse(any(row["source"].endswith(".md") for row in group["plan"]["copies"]))
        self.assertEqual(base.stat().st_mode & 0o777, 0o700)
        for path in base.rglob("*"):
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        for row in admitted["receipts"].values():
            value = json.loads((self.root / row["path"]).read_bytes())
            self.assertEqual(value["kind"], intake.KIND)
            self.assertNotEqual(value["kind"], "unaltraweb-practice-edition-receipt")

    def test_unknown_approval_hash_without_path_and_unselected_source_bytes_stay_honest(self):
        del self.manifest["human_approved"]
        del self.manifest["proof"]
        self.request["sources"] = []
        self.refresh()
        planned = self.plan()["plan"]
        self.assertIsNone(planned["claims"]["human_approved"])
        self.assertIsNone(planned["claims"]["references"]["proof"]["path"])
        self.assertEqual(planned["claims"]["references"]["proof"]["state"], "inherited-unresolved")
        self.assertEqual(planned["package_checks"]["alumnat"]["worker"]["reading_source_bytes"], "inherited-reference-only")
        self.assertEqual(planned["validation"]["native_scientific"], "not-performed")
        self.assertFalse((self.root / self.base / "sealed.json").exists())
        admitted = self.snapshot()
        _, sha = self.routes(admitted)
        published = publication.plan(self.root, publication.CONFIG, sha, "alumnat-guide")
        self.assertIsNone(json.loads(published["metadata"])["human_approved"])

    def test_private_archive_stage_and_readback_export_no_local_sources_or_claims_of_approval(self):
        admitted = self.snapshot()
        _, sha = self.routes(admitted)
        client = transport_fixtures.MemoryS3()
        for identifier in ("alumnat-guide", "docent-packet"):
            planned = publication.plan(self.root, publication.CONFIG, sha, identifier)
            metadata = json.loads(planned["metadata"])
            self.assertEqual(metadata["handoff_slug"], "retained-handoff")
            self.assertEqual(metadata["activity"], "different-activity")
            self.assertFalse(metadata["human_approved"] or metadata["approved_by_intake"] or metadata["public_edition"])
            staged = publication.stage(self.root, publication.CONFIG, sha, identifier, "sandbox/artifacts/" + identifier + "/one")
            directory = self.root / staged["stage"]
            output = staged["manifest"]["files"][0]
            self.assertEqual((directory / output["path"]).read_bytes(), (self.root / planned["source"]).read_bytes())
            for path in (directory / "artifact.json", directory / "product.json"):
                for private in (b"sandbox/", b"dist/practiques", b"context/", b"original_inputs", b"reading_source", b"renderer", b"PRIVATE_"):
                    self.assertNotIn(private, path.read_bytes())
            connector = lambda pub, *args: artifact_transports.S3(pub["destination"], client, profile=pub["storage_profile"], anonymous=transport_fixtures.Anonymous())
            result = publication.transfer(self.root, publication.CONFIG, sha, identifier, staged["stage"], staged["manifest_sha256"], connector=connector)
            self.assertTrue(result["verified"])
            verified = publication.transfer(self.root, publication.CONFIG, sha, identifier, staged["stage"], staged["manifest_sha256"], connector=connector, verify_only=True)
            self.assertFalse(verified["publication_performed"] or verified["local_attempt"]["remote_mutation_requested"])
        self.assertEqual(len(client.objects), 8)
        self.assertFalse(any("local/" in key or "admission.json" in key or "receipt.json" in key for key in client.objects))

    def test_public_target_profile_or_recipient_laundering_is_refused(self):
        admitted = self.snapshot()
        config, _ = self.routes(admitted)
        original = copy.deepcopy(config)
        for wrong in ("github", "public-audience", "teacher-to-student", "format"):
            config = copy.deepcopy(original)
            row = config["artifacts"]["docent-guide" if wrong == "teacher-to-student" else "alumnat-guide"]
            if wrong == "github":
                row.update(target="github", storage_profile="anonymous-delivery-v1")
            elif wrong == "public-audience":
                row["audience"] = "public"
            elif wrong == "teacher-to-student":
                row["audience"] = "student"
            else:
                row["format"] = "zip"
            self.write(publication.CONFIG, publication.canonical(config))
            with self.subTest(wrong=wrong), self.assertRaises(Exception):
                publication.plan(self.root, publication.CONFIG, self.pin(publication.CONFIG)["sha256"], "docent-guide" if wrong == "teacher-to-student" else "alumnat-guide")

    def test_changed_source_request_output_or_evidence_cannot_apply_old_plan(self):
        reviewed = self.plan()
        for name in (self.request_path, self.request["sources"][0]["path"], self.request["packages"][0]["pdf"]["path"], "context/current-handoff.json"):
            path = self.root / name
            raw = path.read_bytes()
            path.write_bytes(raw + b"changed")
            with self.subTest(path=name), self.assertRaises(Exception):
                intake.snapshot(self.root, self.request_path, self.sha, reviewed["plan_sha256"])
            self.assertFalse((self.root / self.request["snapshot"]).exists())
            path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "reviewed digest"):
            intake.snapshot(self.root, self.request_path, self.sha, "0" * 64)

    def test_recipient_id_and_selected_source_conflicts_are_refused(self):
        original = copy.deepcopy(self.request)
        for wrong in ("recipient", "id", "archive", "worker-key", "reading-member", "source-hash", "script"):
            self.request = copy.deepcopy(original)
            if wrong == "recipient":
                self.request["packages"][0]["recipient"] = "docent"
            elif wrong == "id":
                self.request["packages"][1]["selected"][0]["id"] = self.request["packages"][0]["selected"][0]["id"]
            elif wrong == "archive":
                self.request["packages"][0]["archive"] = self.request["packages"][1]["archive"]
            elif wrong == "worker-key":
                self.request["packages"][0]["pdf_artifact"] = "../outside.pdf"
            elif wrong == "reading-member":
                self.request["packages"][0]["reading_member"] = "unselected-root/README.pdf"
            elif wrong == "source-hash":
                self.request["sources"][0]["sha256"] = "0" * 64
            else:
                self.request["command"] = "a script must never execute"
            self.save_request()
            with self.subTest(wrong=wrong), self.assertRaises(Exception):
                self.plan()
            self.assertFalse((self.root / self.request["snapshot"]).exists())

    def test_original_worker_and_zip_member_corruption_are_not_resealed(self):
        package = self.request["packages"][0]
        receipt_path = self.root / package["pdf_receipt"]["path"]
        original = receipt_path.read_bytes()
        value = json.loads(original)
        value["artifacts"][package["pdf_artifact"]] = "0" * 64
        receipt_path.write_bytes(publication.canonical(value))
        package["pdf_receipt"] = self.pin(package["pdf_receipt"]["path"])
        self.manifest["packages"][0]["pdf_receipt_sha256"] = package["pdf_receipt"]["sha256"]
        self.refresh()
        with self.assertRaisesRegex(ValueError, "worker output seal"):
            self.plan()
        receipt_path.write_bytes(original)
        package["pdf_receipt"] = self.pin(package["pdf_receipt"]["path"])
        self.manifest["packages"][0]["pdf_receipt_sha256"] = package["pdf_receipt"]["sha256"]
        key = next(name for name in self.manifest["packages"][0]["members"] if name.endswith("data.csv"))
        self.manifest["packages"][0]["members"][key] = "0" * 64
        self.refresh()
        with self.assertRaisesRegex(ValueError, "ZIP member differs"):
            self.plan()

    def test_zip_paths_links_duplicates_and_expanded_limits_use_shared_verifier(self):
        for wrong in ("path", "symlink", "duplicate", "directory-path", "budget"):
            out = io.BytesIO()
            info = zipfile.ZipInfo("../escape" if wrong == "path" else "root//" if wrong == "directory-path" else "root/data.csv")
            if wrong == "symlink":
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(out, "w") as target:
                target.writestr(info, b"synthetic-data")
                if wrong == "duplicate":
                    with self.assertWarns(UserWarning):
                        target.writestr("root/data.csv", b"duplicate")
            with zipfile.ZipFile(io.BytesIO(out.getvalue())) as archive:
                if wrong == "budget":
                    with patch.object(intake.h, "MAX_TOTAL_BYTES", 4), self.assertRaises(Exception):
                        practice_editions.verify_zip_inventory(archive, {info.filename: publication.digest(b"synthetic-data")})
                else:
                    with self.subTest(wrong=wrong), self.assertRaises(Exception):
                        practice_editions.verify_zip_inventory(archive, {info.filename: publication.digest(b"synthetic-data")})

    def test_untrusted_zip_directory_allocation_is_bounded_before_parsing(self):
        source = (self.root / self.request["packages"][0]["archive"]["path"]).read_bytes()
        marker = source.rfind(b"PK\x05\x06")
        for wrong in ("count", "directory-size", "zip64-end", "trailing"):
            raw = bytearray(source)
            if wrong == "count":
                struct.pack_into("<HH", raw, marker + 8, 10001, 10001)
            elif wrong == "directory-size":
                struct.pack_into("<L", raw, marker + 12, 32 * 1024**2)
            elif wrong == "zip64-end":
                raw = raw[:marker] + b"PK\x06\x07" + bytes(16) + raw[marker:]
            else:
                raw.extend(b"not-declared-in-comment")
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                practice_editions.check_zip_directory(io.BytesIO(raw))

    def test_snapshot_no_clobber_symlink_and_changed_during_copy_preserve_originals(self):
        reviewed = self.plan()
        from unaltraweb_mcp import practice_editions as copier
        original_copy = copier._copy_selected
        def change(workspace, row, target):
            original_copy(workspace, row, target)
            if row["path"].startswith("files/"):
                path = self.root / "context/current-handoff.json"
                path.write_bytes(path.read_bytes() + b" ")
        with patch.object(copier, "_copy_selected", side_effect=change), self.assertRaises(Exception):
            intake.snapshot(self.root, self.request_path, self.sha, reviewed["plan_sha256"])
        self.assertFalse((self.root / self.request["snapshot"]).exists())
        self.request["evidence"][0]["file"] = self.pin("context/current-handoff.json")
        self.save_request()
        admitted = self.snapshot()
        before = (self.root / admitted["snapshot"] / "admission.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "create-only"):
            self.snapshot()
        self.assertEqual((self.root / admitted["snapshot"] / "admission.json").read_bytes(), before)
        self.request["snapshot"] = "sandbox/retained-handoffs/link/pilot"
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.root / "sandbox/retained-handoffs/link").symlink_to(Path(outside.name), target_is_directory=True)
        self.save_request()
        with self.assertRaises((OSError, RuntimeError)):
            self.plan()
        self.assertEqual(list(Path(outside.name).iterdir()), [])

    def test_admission_can_plan_original_bytes_after_hot_handoff_sources_are_gone(self):
        admitted = self.snapshot()
        _, sha = self.routes(admitted)
        planned = publication.plan(self.root, publication.CONFIG, sha, "alumnat-packet")
        shutil.rmtree(self.root / self.base)
        shutil.rmtree(self.root / "practiques")
        shutil.rmtree(self.root / "sandbox/practiques")
        shutil.rmtree(self.root / "context")
        self.assertEqual(publication.plan(self.root, publication.CONFIG, sha, "alumnat-packet"), planned)

    def test_tampered_admission_evidence_output_or_extra_neighbour_is_refused(self):
        admitted = self.snapshot()
        _, sha = self.routes(admitted)
        base = self.root / admitted["snapshot"]
        for path in (base / "files/LLEGIU-ME.pdf", base / "local/worker-alumnat/receipt.json", base / "admission.json"):
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(path=path.name), self.assertRaises(Exception):
                publication.plan(self.root, publication.CONFIG, sha, "alumnat-guide")
            path.write_bytes(original)
        (base / "neighbour-private.md").write_text("Never export this body")
        with self.assertRaisesRegex(ValueError, "neighbouring"):
            publication.plan(self.root, publication.CONFIG, sha, "alumnat-guide")

    def test_editorial_state_cannot_be_relabelled_without_original_manifest_lineage(self):
        admitted = self.snapshot()
        config, _ = self.routes(admitted)
        path = self.root / admitted["snapshot"] / "admission.json"
        group = json.loads(path.read_bytes())
        group["plan"]["claims"]["human_approved"] = True
        group["plan_sha256"] = publication.digest(publication.canonical(group["plan"]))
        path.write_bytes(publication.canonical(group))
        row = config["artifacts"]["alumnat-guide"]
        receipt_path = self.root / row["receipt"]
        receipt = json.loads(receipt_path.read_bytes())
        receipt["admission"]["sha256"] = publication.digest(path.read_bytes())
        receipt_path.write_bytes(publication.canonical(receipt))
        row["receipt_sha256"] = publication.digest(receipt_path.read_bytes())
        self.write(publication.CONFIG, publication.canonical(config))
        with self.assertRaisesRegex(ValueError, "approval lineage"):
            publication.plan(self.root, publication.CONFIG, self.pin(publication.CONFIG)["sha256"], "alumnat-guide")

    def test_cli_discovery_local_plan_and_explicit_repository_or_purpose_refusal(self):
        with patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                patch.object(artifact_transports, "connect", side_effect=AssertionError("No auth/transport")):
            status = intake.main(["plan", "--project", str(self.root), "--request", self.request_path, "--sha256", self.sha])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue())["plan_sha256"], self.plan()["plan_sha256"])
        self.assertFalse((self.root / self.request["snapshot"]).exists())
        for key, value in (("purpose", "public-download"), ("consumer_repository", {"remote": "origin", "host": "github.com", "repository": "example/unrelated"})):
            original = copy.deepcopy(self.request[key])
            self.request[key] = value
            self.save_request()
            with self.subTest(key=key), self.assertRaises(Exception):
                self.plan()
            self.request[key] = original
            self.save_request()


if __name__ == "__main__":
    unittest.main()
