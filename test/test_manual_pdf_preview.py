from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import manual_pdf_preview


class ManualPdfPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name).resolve()
        (self.project / ".gitignore").write_text(
            ".cache/\n"
            "tmp/\n"
            "/assets/pdf/manual-en.pdf\n"
            "/assets/img/manual-cover-en.png\n"
            "/assets/pdf/manual-ca.pdf\n"
            "/assets/img/manual-cover-ca.png\n",
            encoding="utf-8",
        )
        (self.project / "_config.yml").write_text("title: Preview test\n", encoding="utf-8")
        self._git("init", "--quiet")
        self._git("config", "user.email", "preview@example.test")
        self._git("config", "user.name", "Preview Test")
        self._git("add", ".gitignore", "_config.yml")
        self._git("commit", "--quiet", "-m", "Initialize preview fixture")
        self.status = self._write_generated(b"pdf-one\n", b"cover-one\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.project), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @staticmethod
    def _signature(content: bytes) -> dict[str, object]:
        return {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}

    def _write_generated(self, pdf: bytes, cover: bytes) -> dict[str, object]:
        generated = self.project / "tmp/manual-pdf/en"
        generated.mkdir(parents=True, exist_ok=True)
        (generated / "manual-en.pdf").write_bytes(pdf)
        (generated / "manual-cover-en.png").write_bytes(cover)
        (generated / "manifest.json").write_text(
            json.dumps({
                "language": "en",
                "fingerprint": "f" * 64,
                "pdf": "tmp/manual-pdf/en/manual-en.pdf",
                "cover": "tmp/manual-pdf/en/manual-cover-en.png",
                "public_pdf": "assets/pdf/manual-en.pdf",
                "public_cover": "assets/img/manual-cover-en.png",
                "release_selector": "latest",
                "artifacts": {
                    "pdf": self._signature(pdf),
                    "cover": self._signature(cover),
                }
            }),
            encoding="utf-8",
        )
        return {
            "language": "en",
            "fresh": True,
            "ready_to_publish": True,
            "release_selector": "latest",
            "generated_pdf": "tmp/manual-pdf/en/manual-en.pdf",
            "generated_cover": "tmp/manual-pdf/en/manual-cover-en.png",
            "published_pdf": "assets/pdf/manual-en.pdf",
            "published_cover": "assets/img/manual-cover-en.png",
        }

    def _prepare(self) -> dict[str, object]:
        return manual_pdf_preview.prepare(
            self.project,
            [self.status],
            expected_config_sha256=manual_pdf_preview.config_sha256(self.project),
        )

    def test_prepare_stages_ignored_untracked_files_and_writes_receipt(self) -> None:
        result = self._prepare()

        self.assertTrue(result["ok"])
        self.assertFalse(result["publishes"])
        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-one\n")
        self.assertEqual((self.project / "assets/img/manual-cover-en.png").read_bytes(), b"cover-one\n")
        receipt = json.loads((self.project / manual_pdf_preview.RECEIPT_PATH).read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(len(receipt["artifacts"]), 2)
        self.assertEqual(self._git("ls-files", "--", "assets/pdf/manual-en.pdf").stdout, "")
        ignored = subprocess.run(
            ["git", "-C", str(self.project), "check-ignore", "--quiet", "--no-index", "--", "assets/pdf/manual-en.pdf"],
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)

    def test_prepare_is_idempotent_and_replaces_only_receipt_owned_files(self) -> None:
        self._prepare()
        first_receipt = json.loads((self.project / manual_pdf_preview.RECEIPT_PATH).read_text(encoding="utf-8"))

        second = self._prepare()
        self.assertTrue(second["ok"])
        second_receipt = json.loads((self.project / manual_pdf_preview.RECEIPT_PATH).read_text(encoding="utf-8"))
        self.assertNotEqual(
            [item["inode"] for item in first_receipt["artifacts"]],
            [item["inode"] for item in second_receipt["artifacts"]],
        )

        self.status = self._write_generated(b"pdf-two\n", b"cover-two\n")
        third = self._prepare()
        self.assertTrue(third["ok"])
        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-two\n")

    def test_prepare_leaves_current_published_files_unclaimed(self) -> None:
        for source, destination in [
            ("tmp/manual-pdf/en/manual-en.pdf", "assets/pdf/manual-en.pdf"),
            ("tmp/manual-pdf/en/manual-cover-en.png", "assets/img/manual-cover-en.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())
        self.status["published_current"] = True

        result = self._prepare()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "published-current")
        self.assertEqual(result["receipt"], "")
        self.assertFalse((self.project / manual_pdf_preview.RECEIPT_PATH).exists())
        self.assertEqual(manual_pdf_preview.clean(self.project)["state"], "absent")
        self.assertTrue((self.project / "assets/pdf/manual-en.pdf").is_file())

    def test_prepare_replaces_a_verified_previous_public_generation(self) -> None:
        for source, destination in [
            ("tmp/manual-pdf/en/manual-en.pdf", "assets/pdf/manual-en.pdf"),
            ("tmp/manual-pdf/en/manual-cover-en.png", "assets/img/manual-cover-en.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())
        previous = manual_pdf_preview.matching_public_languages(self.project, [self.status])
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        self.status["_replaceable_previous_public"] = previous["en"]

        result = self._prepare()

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "staged")
        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-new\n")
        planned = manual_pdf_preview.clean(self.project)
        cleaned = manual_pdf_preview.clean(
            self.project,
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256=planned["receipt_sha256"],
        )
        self.assertTrue(cleaned["ok"])
        self.assertFalse((self.project / "assets/pdf/manual-en.pdf").exists())

    def test_publication_provenance_survives_removal_of_draft_artifacts(self) -> None:
        for source, destination in [
            ("tmp/manual-pdf/en/manual-en.pdf", "assets/pdf/manual-en.pdf"),
            ("tmp/manual-pdf/en/manual-cover-en.png", "assets/img/manual-cover-en.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())
        self.status["published_current"] = True
        provenance = manual_pdf_preview.record_publication(self.project, [self.status])
        self.assertEqual(provenance["artifacts"], 2)
        (self.project / "tmp/manual-pdf/en/manual-en.pdf").unlink()
        (self.project / "tmp/manual-pdf/en/manual-cover-en.png").unlink()

        previous = manual_pdf_preview.known_publication_languages(self.project, [self.status])
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        self.status["_replaceable_previous_public"] = previous["en"]
        result = self._prepare()

        self.assertTrue(result["ok"])
        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-new\n")

    def test_publication_intent_recovers_provenance_after_interrupted_publication(self) -> None:
        self.status["ready_to_publish"] = True
        intent = manual_pdf_preview.begin_publication(self.project, [self.status])
        self.assertEqual(intent["artifacts"], 2)
        target = self.project / "assets/pdf/manual-en.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((self.project / "tmp/manual-pdf/en/manual-en.pdf").read_bytes())
        (self.project / "tmp/manual-pdf/en/manual-en.pdf").unlink()
        (self.project / "tmp/manual-pdf/en/manual-cover-en.png").unlink()

        previous = manual_pdf_preview.known_publication_languages(self.project, [self.status])
        self.assertEqual(set(previous["en"]), {"pdf"})
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        self.status["_replaceable_previous_public"] = previous["en"]

        result = self._prepare()

        self.assertTrue(result["ok"])
        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-new\n")
        self.assertEqual((self.project / "assets/img/manual-cover-en.png").read_bytes(), b"cover-new\n")

    def test_publication_receipt_must_match_confirmed_intent(self) -> None:
        self.status["ready_to_publish"] = True
        intent = manual_pdf_preview.begin_publication(self.project, [self.status])
        self.status = self._write_generated(b"different-pdf\n", b"different-cover\n")
        self.status["published_current"] = True
        for source, destination in [
            ("tmp/manual-pdf/en/manual-en.pdf", "assets/pdf/manual-en.pdf"),
            ("tmp/manual-pdf/en/manual-cover-en.png", "assets/img/manual-cover-en.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "does not match the confirmed"):
            manual_pdf_preview.record_publication(
                self.project,
                [self.status],
                expected_intent_sha256=intent["sha256"],
            )

        self.assertTrue((self.project / manual_pdf_preview.PUBLICATION_INTENT_PATH).is_file())
        self.assertFalse((self.project / manual_pdf_preview.PUBLICATION_RECEIPT_PATH).exists())

    def test_language_specific_publication_preserves_other_recovery_intents(self) -> None:
        self.status["ready_to_publish"] = True
        manual_pdf_preview.begin_publication(self.project, [self.status])
        generated = self.project / "tmp/manual-pdf/ca"
        generated.mkdir(parents=True)
        (generated / "manual-ca.pdf").write_bytes(b"ca-pdf\n")
        (generated / "manual-cover-ca.png").write_bytes(b"ca-cover\n")
        ca_status = {
            "language": "ca",
            "ready_to_publish": True,
            "published_current": True,
            "generated_pdf": "tmp/manual-pdf/ca/manual-ca.pdf",
            "generated_cover": "tmp/manual-pdf/ca/manual-cover-ca.png",
            "published_pdf": "assets/pdf/manual-ca.pdf",
            "published_cover": "assets/img/manual-cover-ca.png",
        }
        intent = manual_pdf_preview.begin_publication(self.project, [ca_status])
        for source, destination in [
            ("tmp/manual-pdf/ca/manual-ca.pdf", "assets/pdf/manual-ca.pdf"),
            ("tmp/manual-pdf/ca/manual-cover-ca.png", "assets/img/manual-cover-ca.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())

        result = manual_pdf_preview.record_publication(
            self.project,
            [ca_status],
            expected_intent_sha256=intent["sha256"],
        )
        remaining = json.loads(
            (self.project / manual_pdf_preview.PUBLICATION_INTENT_PATH).read_text(encoding="utf-8")
        )

        self.assertTrue(result["intent_retained"])
        self.assertEqual({entry["language"] for entry in remaining["artifacts"]}, {"en"})

    def test_unchanged_published_cover_remains_unclaimed(self) -> None:
        for source, destination in [
            ("tmp/manual-pdf/en/manual-en.pdf", "assets/pdf/manual-en.pdf"),
            ("tmp/manual-pdf/en/manual-cover-en.png", "assets/img/manual-cover-en.png"),
        ]:
            target = self.project / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.project / source).read_bytes())
        previous = manual_pdf_preview.matching_public_languages(self.project, [self.status])
        cover = self.project / "assets/img/manual-cover-en.png"
        cover_inode = cover.stat().st_ino
        self.status = self._write_generated(b"pdf-new\n", b"cover-one\n")
        self.status["_replaceable_previous_public"] = previous["en"]

        result = self._prepare()
        receipt = json.loads((self.project / manual_pdf_preview.RECEIPT_PATH).read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual([entry["kind"] for entry in receipt["artifacts"]], ["pdf"])
        self.assertEqual(cover.stat().st_ino, cover_inode)
        planned = manual_pdf_preview.clean(self.project)
        manual_pdf_preview.clean(
            self.project,
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256=planned["receipt_sha256"],
        )
        self.assertTrue(cover.is_file())

    def test_prepare_refuses_unmanaged_existing_file(self) -> None:
        destination = self.project / "assets/pdf/manual-en.pdf"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"unmanaged\n")

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "unmanaged or changed"):
            self._prepare()

        self.assertEqual(destination.read_bytes(), b"unmanaged\n")
        self.assertFalse((self.project / "assets/img/manual-cover-en.png").exists())

    def test_prepare_refuses_tracked_destination(self) -> None:
        destination = self.project / "assets/pdf/manual-en.pdf"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"tracked\n")
        self._git("add", "-f", "assets/pdf/manual-en.pdf")

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "must not be tracked"):
            self._prepare()

        self.assertEqual(destination.read_bytes(), b"tracked\n")

    def test_prepare_refuses_nonignored_destination_before_writing(self) -> None:
        self.status["published_pdf"] = "assets/public/manual-en.pdf"
        manifest_path = self.project / "tmp/manual-pdf/en/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["public_pdf"] = "assets/public/manual-en.pdf"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "must be ignored"):
            self._prepare()

        self.assertFalse((self.project / "assets/public/manual-en.pdf").exists())
        self.assertFalse((self.project / "assets/img/manual-cover-en.png").exists())

    def test_prepare_ignores_ambient_git_repository_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(self.project / "missing-git-dir"),
                "GIT_INDEX_FILE": str(self.project / "alternate-index"),
                "GIT_WORK_TREE": str(self.project / "missing-work-tree"),
            },
        ):
            result = self._prepare()

        self.assertTrue(result["ok"])

    def test_project_directory_lock_survives_visible_lock_replacement(self) -> None:
        with manual_pdf_preview.project_lock(self.project):
            visible_lock = self.project / manual_pdf_preview.LOCK_PATH
            visible_lock.unlink()
            visible_lock.write_text("replacement\n", encoding="utf-8")
            root_fd = os.open(self.project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(root_fd)

    def test_prepare_rejects_stale_manifest_and_changed_configuration(self) -> None:
        (self.project / "tmp/manual-pdf/en/manual-en.pdf").write_bytes(b"changed after manifest\n")
        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "no longer matches"):
            self._prepare()

        digest = manual_pdf_preview.config_sha256(self.project)
        (self.project / "_config.yml").write_text("title: Changed\n", encoding="utf-8")
        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "configuration changed"):
            manual_pdf_preview.prepare(self.project, [self.status], expected_config_sha256=digest)

    def test_prepare_revalidates_a_source_changed_during_copy(self) -> None:
        source = self.project / "tmp/manual-pdf/en/manual-en.pdf"
        source_inode = source.stat().st_ino
        real_read = os.read
        source_reads = 0

        def read_file(descriptor, size):
            nonlocal source_reads
            chunk = real_read(descriptor, size)
            if os.fstat(descriptor).st_ino == source_inode and chunk:
                source_reads += 1
                if source_reads == 2:
                    source.write_bytes(b"changed during copy\n")
            return chunk

        with patch("unaltraweb_mcp.manual_pdf_preview.os.read", side_effect=read_file):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "changed while it was (?:copied|staged)"):
                self._prepare()

        self.assertFalse((self.project / "assets/pdf/manual-en.pdf").exists())
        self.assertFalse((self.project / manual_pdf_preview.RECEIPT_PATH).exists())

    def test_clean_defaults_to_dry_run_then_removes_exact_owned_files(self) -> None:
        self._prepare()

        planned = manual_pdf_preview.clean(self.project)
        self.assertTrue(planned["ok"])
        self.assertTrue(planned["dry_run"])
        self.assertEqual(planned["state"], "planned")
        self.assertTrue((self.project / "assets/pdf/manual-en.pdf").is_file())

        cleaned = manual_pdf_preview.clean(
            self.project,
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256=planned["receipt_sha256"],
        )
        self.assertTrue(cleaned["ok"])
        self.assertFalse(cleaned["publishes"])
        self.assertEqual(cleaned["state"], "cleaned")
        self.assertFalse((self.project / "assets/pdf/manual-en.pdf").exists())
        self.assertFalse((self.project / "assets/img/manual-cover-en.png").exists())
        self.assertFalse((self.project / manual_pdf_preview.RECEIPT_PATH).exists())

    def test_clean_preserves_modified_or_replaced_files_and_receipt(self) -> None:
        self._prepare()
        pdf = self.project / "assets/pdf/manual-en.pdf"
        replacement = pdf.with_name("replacement.pdf")
        replacement.write_bytes(pdf.read_bytes())
        os.replace(replacement, pdf)
        receipt_sha256 = hashlib.sha256(
            (self.project / manual_pdf_preview.RECEIPT_PATH).read_bytes()
        ).hexdigest()

        result = manual_pdf_preview.clean(
            self.project,
            dry_run=False,
            confirm_clean=True,
            expected_receipt_sha256=receipt_sha256,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "conflict")
        self.assertTrue(pdf.is_file())
        self.assertTrue((self.project / "assets/img/manual-cover-en.png").is_file())
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())

    def test_clean_preserves_a_file_whose_mode_changed(self) -> None:
        self._prepare()
        pdf = self.project / "assets/pdf/manual-en.pdf"
        pdf.chmod(0o600)

        result = manual_pdf_preview.clean(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "conflict")
        self.assertTrue(pdf.is_file())
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())

    def test_clean_preserves_a_file_with_a_new_hard_link(self) -> None:
        self._prepare()
        pdf = self.project / "assets/pdf/manual-en.pdf"
        alias = self.project / "assets/pdf/manual-en-alias.pdf"
        os.link(pdf, alias)

        result = manual_pdf_preview.clean(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "conflict")
        self.assertTrue(pdf.is_file())
        self.assertTrue(alias.is_file())

    def test_clean_preserves_a_file_with_changed_extended_attributes(self) -> None:
        if not hasattr(os, "setxattr"):
            self.skipTest("extended attributes are unavailable")
        self._prepare()
        pdf = self.project / "assets/pdf/manual-en.pdf"
        try:
            os.setxattr(pdf, "user.unaltraweb-preview-test", b"edited")
        except OSError as exc:
            if exc.errno in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM}:
                self.skipTest("the test filesystem does not support user extended attributes")
            raise

        result = manual_pdf_preview.clean(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "conflict")
        self.assertTrue(pdf.is_file())

    def test_clean_confirmation_is_bound_to_reviewed_receipt(self) -> None:
        self._prepare()
        planned = manual_pdf_preview.clean(self.project)

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "expected_receipt_sha256"):
            manual_pdf_preview.clean(self.project, dry_run=False, confirm_clean=True)

        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        self._prepare()
        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "changed after the reviewed"):
            manual_pdf_preview.clean(
                self.project,
                dry_run=False,
                confirm_clean=True,
                expected_receipt_sha256=planned["receipt_sha256"],
            )
        self.assertTrue((self.project / "assets/pdf/manual-en.pdf").is_file())

    def test_cleanup_quarantines_before_validating_a_raced_replacement(self) -> None:
        self._prepare()
        planned = manual_pdf_preview.clean(self.project)
        destination = self.project / "assets/pdf/manual-en.pdf"
        real_replace = os.replace
        raced = False

        def replace(source, target, *args, **kwargs):
            nonlocal raced
            if not raced and source == destination.name and ".preview-clean-" in str(target):
                replacement = destination.with_name("raced.pdf")
                replacement.write_bytes(b"concurrent user file\n")
                real_replace(replacement, destination)
                raced = True
            return real_replace(source, target, *args, **kwargs)

        with patch("unaltraweb_mcp.manual_pdf_preview.os.replace", side_effect=replace):
            result = manual_pdf_preview.clean(
                self.project,
                dry_run=False,
                confirm_clean=True,
                expected_receipt_sha256=planned["receipt_sha256"],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(destination.read_bytes(), b"concurrent user file\n")
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())

    def test_cleanup_preserves_an_in_place_edit_before_unlink(self) -> None:
        self._prepare()
        planned = manual_pdf_preview.clean(self.project)
        destination = self.project / "assets/pdf/manual-en.pdf"
        real_stat = os.stat
        raced = False

        def stat_path(path, *args, **kwargs):
            nonlocal raced
            if not raced and ".preview-clean-" in str(path) and kwargs.get("dir_fd") is not None:
                (destination.parent / str(path)).write_bytes(b"concurrent quarantined edit\n")
                raced = True
            return real_stat(path, *args, **kwargs)

        with patch("unaltraweb_mcp.manual_pdf_preview.os.stat", side_effect=stat_path):
            result = manual_pdf_preview.clean(
                self.project,
                dry_run=False,
                confirm_clean=True,
                expected_receipt_sha256=planned["receipt_sha256"],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(destination.read_bytes(), b"concurrent quarantined edit\n")
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())

    def test_cleanup_does_not_report_an_unlinked_quarantine_after_fsync_failure(self) -> None:
        self._prepare()
        planned = manual_pdf_preview.clean(self.project)
        real_unlink = os.unlink
        real_fsync = os.fsync
        quarantine_deleted = False

        def unlink(path, *args, **kwargs):
            nonlocal quarantine_deleted
            result = real_unlink(path, *args, **kwargs)
            if ".preview-clean-" in str(path):
                quarantine_deleted = True
            return result

        def fsync(descriptor):
            if quarantine_deleted:
                raise OSError("directory fsync failed")
            return real_fsync(descriptor)

        with patch("unaltraweb_mcp.manual_pdf_preview.os.unlink", side_effect=unlink), patch(
            "unaltraweb_mcp.manual_pdf_preview.os.fsync",
            side_effect=fsync,
        ):
            result = manual_pdf_preview.clean(
                self.project,
                dry_run=False,
                confirm_clean=True,
                expected_receipt_sha256=planned["receipt_sha256"],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["recovery_paths"], [])
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())

    def test_real_publication_worker_requires_the_controller_lock(self) -> None:
        self.status["ready_to_publish"] = True
        intent = manual_pdf_preview.begin_publication(self.project, [self.status])

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "controller project lock"):
            manual_pdf_preview.validate_publication_worker(self.project, intent["sha256"])

        with manual_pdf_preview.project_lock(self.project):
            result = manual_pdf_preview.validate_publication_worker(self.project, intent["sha256"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["languages"], ["en"])

    def test_prepare_does_not_overwrite_a_file_created_during_install(self) -> None:
        self._prepare()
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        destination = self.project / "assets/pdf/manual-en.pdf"
        real_link = os.link
        raced = False

        def link(source, target, *args, **kwargs):
            nonlocal raced
            if not raced and target == destination.name and kwargs.get("dst_dir_fd") is not None:
                destination.write_bytes(b"concurrent install file\n")
                raced = True
            return real_link(source, target, *args, **kwargs)

        with patch("unaltraweb_mcp.manual_pdf_preview.os.link", side_effect=link):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "preserved previous files for recovery"):
                self._prepare()

        self.assertEqual(destination.read_bytes(), b"concurrent install file\n")
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())
        self.assertTrue(any((self.project / manual_pdf_preview.RECOVERY_PATH).iterdir()))

    def test_prepare_does_not_adopt_a_replacement_after_install(self) -> None:
        destination = self.project / "assets/pdf/manual-en.pdf"
        real_unlink = os.unlink
        replaced_inode = 0

        def unlink(path, *args, **kwargs):
            nonlocal replaced_inode
            result = real_unlink(path, *args, **kwargs)
            if replaced_inode == 0 and ".preview-" in str(path) and kwargs.get("dir_fd") is not None:
                replacement = destination.with_name("same-content-replacement.pdf")
                replacement.write_bytes(b"pdf-one\n")
                replaced_inode = replacement.stat().st_ino
                os.replace(replacement, destination)
            return result

        with patch("unaltraweb_mcp.manual_pdf_preview.os.unlink", side_effect=unlink):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "differs from its generated source"):
                self._prepare()

        self.assertEqual(destination.read_bytes(), b"pdf-one\n")
        self.assertEqual(destination.stat().st_ino, replaced_inode)
        self.assertFalse((self.project / manual_pdf_preview.RECEIPT_PATH).exists())

    def test_no_replace_restore_preserves_a_substituted_source(self) -> None:
        parent_fd = os.open(self.project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        source = self.project / "restore-source"
        destination = self.project / "restore-destination"
        source.write_bytes(b"managed backup\n")
        real_link = os.link

        def link(*args, **kwargs):
            result = real_link(*args, **kwargs)
            replacement = self.project / "restore-replacement"
            replacement.write_bytes(b"concurrent replacement\n")
            os.replace(replacement, source)
            return result

        try:
            with patch("unaltraweb_mcp.manual_pdf_preview.os.link", side_effect=link):
                with self.assertRaisesRegex(OSError, "Rollback source changed"):
                    manual_pdf_preview._move_noreplace(
                        source.name,
                        destination.name,
                        source_fd=parent_fd,
                        destination_fd=parent_fd,
                    )
        finally:
            os.close(parent_fd)

        self.assertEqual(source.read_bytes(), b"concurrent replacement\n")
        self.assertEqual(destination.read_bytes(), b"managed backup\n")

    def test_cross_filesystem_recovery_preserves_a_substituted_source(self) -> None:
        root_fd = os.open(self.project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        parent = self.project / "assets/pdf"
        parent.mkdir(parents=True)
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        backup = parent / "cross-device-backup"
        backup.write_bytes(b"managed backup\n")
        real_replace = os.replace
        real_stat = os.stat
        replaced = False

        def replace(*_args, **_kwargs):
            raise OSError(errno.EXDEV, "cross-device link")

        def stat_path(path, *args, **kwargs):
            nonlocal replaced
            if not replaced and path == backup.name and kwargs.get("dir_fd") == parent_fd:
                replacement = self.project / "cross-device-replacement"
                replacement.write_bytes(b"concurrent replacement\n")
                real_replace(replacement, backup)
                replaced = True
            return real_stat(path, *args, **kwargs)

        try:
            with patch("unaltraweb_mcp.manual_pdf_preview.os.replace", side_effect=replace), patch(
                "unaltraweb_mcp.manual_pdf_preview.os.stat",
                side_effect=stat_path,
            ):
                with self.assertRaisesRegex(OSError, "Backup changed") as raised:
                    manual_pdf_preview._stash_backup(
                        root_fd,
                        parent_fd,
                        backup.name,
                        Path("assets/pdf/manual-en.pdf"),
                    )
        finally:
            os.close(parent_fd)
            os.close(root_fd)

        self.assertEqual(backup.read_bytes(), b"concurrent replacement\n")
        recovered = list((self.project / manual_pdf_preview.RECOVERY_PATH).iterdir())
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_bytes(), b"managed backup\n")
        self.assertEqual(
            raised.exception.recovery_paths,
            [recovered[0].relative_to(self.project).as_posix()],
        )

    def test_cross_filesystem_recovery_preserves_source_when_target_is_replaced(self) -> None:
        root_fd = os.open(self.project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        parent = self.project / "assets/pdf"
        parent.mkdir(parents=True)
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        backup = parent / "cross-device-target-backup"
        backup.write_bytes(b"managed backup\n")
        real_replace = os.replace
        real_stat = os.stat
        replaced = False

        def replace(*_args, **_kwargs):
            raise OSError(errno.EXDEV, "cross-device link")

        def stat_path(path, *args, **kwargs):
            nonlocal replaced
            if (
                not replaced
                and str(path).endswith(".backup")
                and kwargs.get("dir_fd") not in {None, parent_fd}
            ):
                recovery = self.project / manual_pdf_preview.RECOVERY_PATH / str(path)
                replacement = recovery.with_name("recovery-replacement")
                replacement.write_bytes(b"concurrent recovery replacement\n")
                real_replace(replacement, recovery)
                replaced = True
            return real_stat(path, *args, **kwargs)

        try:
            with patch("unaltraweb_mcp.manual_pdf_preview.os.replace", side_effect=replace), patch(
                "unaltraweb_mcp.manual_pdf_preview.os.stat",
                side_effect=stat_path,
            ):
                with self.assertRaisesRegex(OSError, "Backup changed") as raised:
                    manual_pdf_preview._stash_backup(
                        root_fd,
                        parent_fd,
                        backup.name,
                        Path("assets/pdf/manual-en.pdf"),
                    )
        finally:
            os.close(parent_fd)
            os.close(root_fd)

        self.assertEqual(backup.read_bytes(), b"managed backup\n")
        recovered = list((self.project / manual_pdf_preview.RECOVERY_PATH).iterdir())
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_bytes(), b"concurrent recovery replacement\n")
        self.assertEqual(raised.exception.recovery_paths, [backup.relative_to(self.project).as_posix()])

    def test_cross_filesystem_recovery_reports_copy_after_directory_fsync_failure(self) -> None:
        root_fd = os.open(self.project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        parent = self.project / "assets/pdf"
        parent.mkdir(parents=True)
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        backup = parent / "cross-device-fsync-backup"
        backup.write_bytes(b"managed backup\n")
        (self.project / manual_pdf_preview.RECOVERY_PATH).mkdir(parents=True)
        real_fsync = os.fsync

        def replace(*_args, **_kwargs):
            raise OSError(errno.EXDEV, "cross-device link")

        def fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("recovery directory fsync failed")
            return real_fsync(descriptor)

        try:
            with patch("unaltraweb_mcp.manual_pdf_preview.os.replace", side_effect=replace), patch(
                "unaltraweb_mcp.manual_pdf_preview.os.fsync",
                side_effect=fsync,
            ):
                with self.assertRaisesRegex(OSError, "retained files") as raised:
                    manual_pdf_preview._stash_backup(
                        root_fd,
                        parent_fd,
                        backup.name,
                        Path("assets/pdf/manual-en.pdf"),
                    )
        finally:
            os.close(parent_fd)
            os.close(root_fd)

        self.assertFalse(backup.exists())
        recovered = list((self.project / manual_pdf_preview.RECOVERY_PATH).iterdir())
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_bytes(), b"managed backup\n")
        self.assertEqual(
            raised.exception.recovery_paths,
            [recovered[0].relative_to(self.project).as_posix()],
        )

    def test_prepare_rollback_does_not_overwrite_a_concurrent_edit(self) -> None:
        self._prepare()
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        destination = self.project / "assets/pdf/manual-en.pdf"

        def fail_receipt(*_args, **_kwargs):
            destination.write_bytes(b"concurrent edit\n")
            raise OSError("receipt write failed")

        with patch("unaltraweb_mcp.manual_pdf_preview._atomic_write", side_effect=fail_receipt):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "preserved previous files for recovery"):
                self._prepare()

        self.assertEqual(destination.read_bytes(), b"concurrent edit\n")
        self.assertTrue((self.project / manual_pdf_preview.RECEIPT_PATH).is_file())
        self.assertTrue(any((self.project / manual_pdf_preview.RECOVERY_PATH).iterdir()))

    def test_prepare_rollback_keeps_the_previous_receipt_usable(self) -> None:
        self._prepare()
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")

        with patch("unaltraweb_mcp.manual_pdf_preview._atomic_write", side_effect=OSError("receipt write failed")):
            with self.assertRaisesRegex(OSError, "receipt write failed"):
                self._prepare()

        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-one\n")
        planned = manual_pdf_preview.clean(self.project)
        self.assertTrue(planned["ok"])
        self.assertEqual(planned["state"], "planned")

    def test_prepare_rollback_preserves_an_edit_before_final_unlink(self) -> None:
        self._prepare()
        self.status = self._write_generated(b"pdf-new\n", b"cover-new\n")
        destination = self.project / "assets/pdf/manual-en.pdf"
        real_stat = os.stat
        raced = False

        def stat_path(path, *args, **kwargs):
            nonlocal raced
            if (
                not raced
                and ".preview-rollback-" in str(path)
                and "manual-en.pdf" in str(path)
                and kwargs.get("dir_fd") is not None
            ):
                (destination.parent / str(path)).write_bytes(b"rollback concurrent edit\n")
                raced = True
            return real_stat(path, *args, **kwargs)

        with patch("unaltraweb_mcp.manual_pdf_preview._atomic_write", side_effect=OSError("receipt write failed")), patch(
            "unaltraweb_mcp.manual_pdf_preview.os.stat",
            side_effect=stat_path,
        ):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "preserved previous files for recovery"):
                self._prepare()

        self.assertEqual(destination.read_bytes(), b"rollback concurrent edit\n")

    def test_prepare_keeps_staged_files_when_receipt_commit_already_happened(self) -> None:
        real_atomic_write = manual_pdf_preview._atomic_write

        def commit_then_fail(*args, **kwargs):
            real_atomic_write(*args, **kwargs)
            raise OSError("post-commit failure")

        with patch("unaltraweb_mcp.manual_pdf_preview._atomic_write", side_effect=commit_then_fail):
            with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "receipt was committed"):
                self._prepare()

        self.assertEqual((self.project / "assets/pdf/manual-en.pdf").read_bytes(), b"pdf-one\n")
        self.assertEqual((self.project / "assets/img/manual-cover-en.png").read_bytes(), b"cover-one\n")
        planned = manual_pdf_preview.clean(self.project)
        self.assertTrue(planned["ok"])

    def test_early_rollback_preserves_an_in_place_concurrent_edit(self) -> None:
        destination = self.project / "assets/pdf/manual-en.pdf"
        relative = Path("assets/pdf/manual-en.pdf")
        real_record = manual_pdf_preview._record_descriptor
        records = 0

        def record(descriptor, path):
            nonlocal records
            if path == relative:
                records += 1
            if path == relative and records == 2:
                destination.write_bytes(b"early concurrent edit\n")
                raise OSError("installed record failed")
            return real_record(descriptor, path)

        with patch("unaltraweb_mcp.manual_pdf_preview._record_descriptor", side_effect=record):
            with self.assertRaisesRegex(OSError, "installed record failed"):
                self._prepare()

        self.assertEqual(destination.read_bytes(), b"early concurrent edit\n")
        self.assertFalse((self.project / manual_pdf_preview.RECEIPT_PATH).exists())

    def test_clean_fails_closed_for_malformed_receipt(self) -> None:
        receipt = self.project / manual_pdf_preview.RECEIPT_PATH
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text('{"schema_version": 1, "schema_version": 2}\n', encoding="utf-8")

        with self.assertRaisesRegex(manual_pdf_preview.ManualPdfPreviewError, "duplicate key"):
            manual_pdf_preview.clean(self.project)

    def test_clean_without_receipt_is_a_noop_even_before_git_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = manual_pdf_preview.clean(Path(temporary), dry_run=False, confirm_clean=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "absent")
        self.assertFalse(result["publishes"])


if __name__ == "__main__":
    unittest.main()
