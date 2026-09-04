from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from unaltraweb_mcp import manual_release, site_tools


def write_markdown(path: Path, *, status: str = "approved") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "title: Chapter\n"
        "lang: en\n"
        "ref: chapter\n"
        f"content_status: {status}\n"
        "---\n\n"
        "Publishable manual body.\n",
        encoding="utf-8",
    )


class ManualReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name).resolve()
        config = {
            "theme": "unaltraweb",
            "lang": "en",
            "default_lang": "en",
            "languages": ["en"],
            "unaltraweb": {
                "site_profile": "unaltremanual",
                "manual": {
                    "collection": "chapters",
                    "pdf": {
                        "enabled": True,
                        "languages": ["en"],
                        "output": "assets/pdf/manual-{lang}.pdf",
                        "cover_output": "assets/img/manual-cover-{lang}.png",
                    },
                },
            },
        }
        (self.project / "_config.yml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        write_markdown(self.project / "_chapters/en/chapter.md")
        (self.project / "assets/pdf").mkdir(parents=True)
        (self.project / "assets/img").mkdir(parents=True)
        (self.project / "assets/pdf/manual-en.pdf").write_bytes(b"current pdf")
        (self.project / "assets/img/manual-cover-en.png").write_bytes(b"current cover")
        generated = self.project / "tmp/manual-pdf/en"
        generated.mkdir(parents=True)
        (generated / "manual-en.pdf").write_bytes(b"current pdf")
        (generated / "manual-cover-en.png").write_bytes(b"current cover")
        site = self.project / "_site"
        (site / "assets/pdf").mkdir(parents=True)
        (site / "assets/img").mkdir(parents=True)
        (site / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Manual</title></head><body></body></html>\n',
            encoding="utf-8",
        )
        (site / "assets/pdf/manual-en.pdf").write_bytes(b"current pdf")
        (site / "assets/img/manual-cover-en.png").write_bytes(b"current cover")
        self.pdf_status = {
            "ok": True,
            "configuration_ok": True,
            "ready_to_publish": True,
            "published_current": True,
            "languages": [
                {
                    "language": "en",
                    "generated_pdf": "tmp/manual-pdf/en/manual-en.pdf",
                    "generated_cover": "tmp/manual-pdf/en/manual-cover-en.png",
                    "published_pdf": "assets/pdf/manual-en.pdf",
                    "published_cover": "assets/img/manual-cover-en.png",
                    "fresh": True,
                    "ready_to_publish": True,
                    "published_current": True,
                    "release_selector": "latest",
                    "release_channel": "latest",
                }
            ],
        }
        self.stable_identity = {"commit": "a" * 40, "source_date_epoch": "1788393600"}
        self.site_build_image = "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:" + "b" * 64
        self.site_build_image_patch = patch.dict(
            os.environ,
            {"UNALTRAWEB_MCP_IMAGE_REFERENCE": self.site_build_image},
        )
        self.site_build_image_patch.start()
        self.addCleanup(self.site_build_image_patch.stop)
        self.stable_identity_patch = patch(
            "unaltraweb_mcp.manual_release.stable_source_identity",
            return_value=self.stable_identity,
        )
        self.stable_identity_patch.start()
        self.addCleanup(self.stable_identity_patch.stop)
        self.tracked_sources_patch = patch(
            "unaltraweb_mcp.manual_release._tracked_source_paths",
            return_value={"Makefile", "_config.yml", "_chapters/en/chapter.md"},
        )
        self.tracked_sources_patch.start()
        self.addCleanup(self.tracked_sources_patch.stop)
        self.set_release_selector("latest")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def set_release_selector(self, selector: str, *, draft: bool = False) -> None:
        channel = "latest" if selector == "latest" else "stable"
        marker = {"channel": channel, "schema_version": 1, "selector": selector}
        (self.project / "_site/manual-release.json").write_text(
            json.dumps(marker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        pdf = self.project / "tmp/manual-pdf/en/manual-en.pdf"
        cover = self.project / "tmp/manual-pdf/en/manual-cover-en.png"
        manifest = {
            "language": "en",
            "draft": draft,
            "release_selector": selector,
            "release_channel": channel,
            "fingerprint": "0" * 64,
            "pdf": "tmp/manual-pdf/en/manual-en.pdf",
            "cover": "tmp/manual-pdf/en/manual-cover-en.png",
            "public_pdf": "assets/pdf/manual-en.pdf",
            "public_cover": "assets/img/manual-cover-en.png",
            "artifacts": {
                "pdf": {"sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "size": pdf.stat().st_size},
                "cover": {"sha256": hashlib.sha256(cover.read_bytes()).hexdigest(), "size": cover.stat().st_size},
            },
        }
        (self.project / "tmp/manual-pdf/en/manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.pdf_status["languages"][0]["release_selector"] = selector
        self.pdf_status["languages"][0]["release_channel"] = channel
        manual_release.write_site_build_receipt(self.project, selector)

    def tree_inventory(self) -> dict[str, str]:
        inventory: dict[str, str] = {}
        for root, directories, files in os.walk(self.project, followlinks=False):
            root_path = Path(root)
            for name in sorted(directories):
                path = root_path / name
                relative = path.relative_to(self.project).as_posix()
                inventory[relative + "/"] = "symlink" if path.is_symlink() else "directory"
            for name in sorted(files):
                path = root_path / name
                relative = path.relative_to(self.project).as_posix()
                inventory[relative] = "symlink" if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest()
        return inventory

    def test_selector_contract_rejects_injection_and_invalid_versions(self) -> None:
        for selector in ["latest", "v2026.01", "v2026.12.1", "v0000.09.42"]:
            self.assertEqual(manual_release.validate_selector(selector), selector)
        for selector in ["latest;touch /tmp/pwn", " latest", "latest\n", "v2026.00", "v2026.13", "v2026.09.0", "v2026.09.01", "v26.09"]:
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                manual_release.validate_selector(selector)

    def test_source_fingerprint_excludes_only_top_level_runtime_trees_and_public_pdf(self) -> None:
        original = manual_release.source_snapshot(self.project)["sha256"]
        (self.project / "sandbox").mkdir()
        (self.project / "sandbox/.git").mkdir()
        (self.project / "sandbox/ignored.md").write_text("ignored\n", encoding="utf-8")
        nested = self.project / "legacy"
        nested.mkdir(parents=True)
        (nested / ".git").mkdir()
        (nested / "ignored.md").write_text("ignored\n", encoding="utf-8")
        (self.project / "tmp/ignored.txt").write_text("ignored\n", encoding="utf-8")
        (self.project / "vendor/bundle").mkdir(parents=True)
        (self.project / "vendor/bundle/cached-gem").write_text("ignored\n", encoding="utf-8")
        (self.project / "_site/ignored.txt").write_text("ignored\n", encoding="utf-8")
        (self.project / "assets/pdf/manual-en.pdf").write_bytes(b"generated replacement")
        (self.project / "assets/img/manual-cover-en.png").write_bytes(b"generated replacement")

        self.assertEqual(manual_release.source_snapshot(self.project)["sha256"], original)

        nested_source = self.project / "visible-nested-repository"
        (nested_source / ".git").mkdir(parents=True)
        (nested_source / "source.md").write_text("included nested source\n", encoding="utf-8")
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "nested VCS metadata"):
            manual_release.source_snapshot(self.project)
        (nested_source / "source.md").unlink()
        (nested_source / ".git").rmdir()
        nested_source.rmdir()

        nested_cache = self.project / "assets/cache/site.css"
        nested_cache.parent.mkdir()
        nested_cache.write_text("included nested cache\n", encoding="utf-8")
        self.assertNotEqual(manual_release.source_snapshot(self.project)["sha256"], original)
        nested_cache.unlink()
        nested_cache.parent.rmdir()

        (self.project / "visible-source.txt").write_text("included\n", encoding="utf-8")
        self.assertNotEqual(manual_release.source_snapshot(self.project)["sha256"], original)

    def test_source_and_site_fingerprints_use_canonical_modes(self) -> None:
        source_before = manual_release.source_snapshot(self.project)["sha256"]
        site_before = manual_release.site_snapshot(self.project)["sha256"]

        os.chmod(self.project / "_chapters/en/chapter.md", 0o600)
        os.chmod(self.project / "_site/index.html", 0o700)
        os.chmod(self.project / "_site/assets", 0o700)

        self.assertEqual(manual_release.source_snapshot(self.project)["sha256"], source_before)
        self.assertEqual(manual_release.site_snapshot(self.project)["sha256"], site_before)

    def test_receipt_detects_stale_source_and_site(self) -> None:
        self.assertTrue(manual_release.site_build_receipt_status(self.project)["ok"])
        (self.project / "_chapters/en/chapter.md").write_text("changed source\n", encoding="utf-8")
        source_stale = manual_release.site_build_receipt_status(self.project)
        self.assertFalse(source_stale["ok"])
        self.assertEqual(source_stale["state"], "stale")

        write_markdown(self.project / "_chapters/en/chapter.md")
        manual_release.write_site_build_receipt(self.project, "latest")
        (self.project / "_site/index.html").write_text("tampered site\n", encoding="utf-8")
        site_stale = manual_release.site_build_receipt_status(self.project)
        self.assertFalse(site_stale["ok"])
        self.assertEqual(site_stale["state"], "stale")

    def test_receipt_and_pdf_are_bound_to_one_release_selector(self) -> None:
        wrong_selector = manual_release.release_status(self.project, "v2026.09", self.pdf_status)

        self.assertFalse(wrong_selector["ready"])
        self.assertTrue(wrong_selector["html_audit"]["skipped"])
        self.assertIn("UW-RELEASE-BUILD-RECEIPT", {item["code"] for item in wrong_selector["issues"]})

        self.set_release_selector("v2026.09")
        stale_pdf_status = json.loads(json.dumps(self.pdf_status))
        stale_pdf_status["languages"][0]["release_selector"] = "latest"
        stale_pdf_status["languages"][0]["release_channel"] = "latest"
        status = manual_release.release_status(self.project, "v2026.09", stale_pdf_status)
        self.assertFalse(status["ready"])
        self.assertIn("UW-RELEASE-PDF-SELECTOR", {item["code"] for item in status["issues"]})

    def test_status_and_check_are_read_only_and_check_requires_candidate(self) -> None:
        before = self.tree_inventory()

        status = manual_release.release_status(self.project, "latest", self.pdf_status)
        checked = manual_release.release_check(self.project, "latest", self.pdf_status)

        self.assertTrue(status["ok"])
        self.assertTrue(status["ready"])
        self.assertEqual(status["candidate"]["state"], "absent")
        self.assertFalse(checked["ok"])
        self.assertEqual(self.tree_inventory(), before)
        self.assertFalse((self.project / "tmp/manual-release").exists())

    def test_pdf_status_and_site_copy_must_be_current(self) -> None:
        stale = json.loads(json.dumps(self.pdf_status))
        stale["languages"][0]["published_current"] = False
        self.assertFalse(manual_release.release_status(self.project, "latest", stale)["ready"])

        (self.project / "_site/assets/pdf/manual-en.pdf").write_bytes(b"different site pdf")
        manual_release.write_site_build_receipt(self.project, "latest")
        mismatch = manual_release.release_status(self.project, "latest", self.pdf_status)
        self.assertFalse(mismatch["ready"])
        self.assertIn("differs", " ".join(item["message"] for item in mismatch["issues"]))

    def test_prepare_defaults_to_dry_run_and_real_prepare_requires_confirmation(self) -> None:
        result = manual_release.release_prepare(self.project, "latest", self.pdf_status)

        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["prepared"])
        self.assertFalse((self.project / "tmp/manual-release").exists())
        with self.assertRaisesRegex(RuntimeError, "confirm_prepare=True"):
            manual_release.release_prepare(self.project, "latest", self.pdf_status, dry_run=False)

    def test_prepare_builds_verified_layout_and_detects_tampering(self) -> None:
        prepared = manual_release.release_prepare(
            self.project,
            "latest",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )

        candidate = self.project / "tmp/manual-release/latest"
        self.assertTrue(prepared["ok"])
        self.assertTrue((candidate / "site/index.html").is_file())
        self.assertEqual((candidate / "pdf/manual-en.pdf").read_bytes(), b"current pdf")
        self.assertTrue((candidate / "release-manifest.json").is_file())
        sums = (candidate / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sums, sorted(sums, key=lambda line: line.split("  ", 1)[1]))
        self.assertTrue(manual_release.release_check(self.project, "latest", self.pdf_status)["ok"])

        (candidate / "site/index.html").write_text("tampered\n", encoding="utf-8")
        checked = manual_release.release_check(self.project, "latest", self.pdf_status)
        self.assertFalse(checked["ok"])
        self.assertEqual(checked["candidate"]["state"], "tampered")

        replaced = manual_release.release_prepare(
            self.project,
            "latest",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )
        self.assertTrue(replaced["ok"])
        self.assertNotEqual((candidate / "site/index.html").read_text(encoding="utf-8"), "tampered\n")

    def test_stable_candidate_is_idempotent_but_immutable_when_changed(self) -> None:
        self.set_release_selector("v2026.09")
        first = manual_release.release_prepare(
            self.project,
            "v2026.09",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )
        second = manual_release.release_prepare(
            self.project,
            "v2026.09",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )

        self.assertTrue(first["prepared"])
        self.assertTrue(second["ok"])
        self.assertTrue(second["idempotent"])
        candidate_file = self.project / "tmp/manual-release/v2026.09/site/index.html"
        candidate_file.write_text("changed stable candidate\n", encoding="utf-8")
        immutable = manual_release.release_prepare(
            self.project,
            "v2026.09",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )
        self.assertFalse(immutable["ok"])
        self.assertIn("no-clobber", immutable["error"])
        self.assertEqual(candidate_file.read_text(encoding="utf-8"), "changed stable candidate\n")

    def test_stable_candidate_appearing_after_staging_is_not_exchanged(self) -> None:
        selector = "v2026.09"
        self.set_release_selector(selector)
        target = self.project / "tmp/manual-release" / selector
        evidence = b"concurrently prepared stable evidence\n"
        original_stage = manual_release._stage_candidate

        def stage_then_publish_evidence(*args, **kwargs):
            staged = original_stage(*args, **kwargs)
            target.mkdir()
            (target / "evidence.bin").write_bytes(evidence)
            return staged

        with patch("unaltraweb_mcp.manual_release._stage_candidate", side_effect=stage_then_publish_evidence):
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "destination appeared during installation"):
                manual_release.release_prepare(
                    self.project,
                    selector,
                    self.pdf_status,
                    dry_run=False,
                    confirm_prepare=True,
                )

        self.assertEqual(list(target.iterdir()), [target / "evidence.bin"])
        self.assertEqual((target / "evidence.bin").read_bytes(), evidence)
        self.assertFalse(any(path.name.startswith(".prepare-") for path in target.parent.iterdir()))

    def test_stable_requires_no_drafts_and_default_language_approval(self) -> None:
        self.set_release_selector("latest", draft=True)
        self.assertTrue(manual_release.release_status(self.project, "latest", self.pdf_status)["ready"])
        self.set_release_selector("v2026.09.1", draft=True)
        stable = manual_release.release_status(self.project, "v2026.09.1", self.pdf_status)
        self.assertFalse(stable["ready"])
        self.assertIn("UW-RELEASE-STABLE-DRAFT", {item["code"] for item in stable["issues"]})

        self.set_release_selector("v2026.09.1", draft=False)
        write_markdown(self.project / "_chapters/en/chapter.md", status="draft")
        manual_release.write_site_build_receipt(self.project, "v2026.09.1")
        unapproved = manual_release.release_status(self.project, "v2026.09.1", self.pdf_status)
        self.assertFalse(unapproved["ready"])
        self.assertIn("UW-RELEASE-STABLE-APPROVAL", {item["code"] for item in unapproved["issues"]})

    def test_prepare_rejects_symlinked_release_root_without_writing_outside(self) -> None:
        outside_temp = tempfile.TemporaryDirectory()
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        (self.project / "tmp/manual-release").symlink_to(outside, target_is_directory=True)

        result = manual_release.release_prepare(
            self.project,
            "latest",
            self.pdf_status,
            dry_run=False,
            confirm_prepare=True,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["candidate"]["state"], "unsafe")
        self.assertEqual(list(outside.iterdir()), [])

    def test_receipt_write_rejects_symlinked_parent_without_writing_outside(self) -> None:
        outside_temp = tempfile.TemporaryDirectory()
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        receipt_parent = self.project / "tmp/.unaltraweb"
        (receipt_parent / "site-build.json").unlink()
        receipt_parent.rmdir()
        receipt_parent.symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(manual_release.ManualReleaseError, "confined destination"):
            manual_release.write_site_build_receipt(self.project)

        self.assertEqual(list(outside.iterdir()), [])

    def test_stage_swap_cannot_redirect_candidate_writes_outside(self) -> None:
        outside_temp = tempfile.TemporaryDirectory()
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        original_write = manual_release._write_new_file_at
        swapped = False

        def swap_stage(parent_fd: int, name: str, content: bytes, mode: int = 0o644) -> None:
            nonlocal swapped
            if not swapped:
                root = self.project / "tmp/manual-release"
                stage = next(path for path in root.iterdir() if path.name.startswith(".prepare-"))
                stage.rename(root / ".detached-stage")
                stage.symlink_to(outside, target_is_directory=True)
                swapped = True
            original_write(parent_fd, name, content, mode)

        with patch("unaltraweb_mcp.manual_release._write_new_file_at", side_effect=swap_stage):
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "Candidate path|changed before installation"):
                manual_release.release_prepare(
                    self.project,
                    "latest",
                    self.pdf_status,
                    dry_run=False,
                    confirm_prepare=True,
                )

        self.assertTrue(swapped)
        self.assertEqual(list(outside.iterdir()), [])

    def test_release_inputs_reject_symlinks_special_files_traversal_and_duplicate_names(self) -> None:
        (self.project / "_site/link").symlink_to("index.html")
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "symlinks"):
            manual_release.write_site_build_receipt(self.project)
        (self.project / "_site/link").unlink()

        fifo = self.project / "_site/fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "special files"):
            manual_release.write_site_build_receipt(self.project)
        fifo.unlink()

        (self.project / "_site/A.txt").write_text("A\n", encoding="utf-8")
        (self.project / "_site/a.txt").write_text("a\n", encoding="utf-8")
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "duplicate"):
            manual_release.write_site_build_receipt(self.project)
        (self.project / "_site/A.txt").unlink()
        (self.project / "_site/a.txt").unlink()

        config = yaml.safe_load((self.project / "_config.yml").read_text(encoding="utf-8"))
        config["unaltraweb"]["manual"]["pdf"]["output"] = "../manual-{lang}.pdf"
        (self.project / "_config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "traversal"):
            manual_release.source_snapshot(self.project)

    def test_status_rejects_symlinked_site_root_without_traversing_it(self) -> None:
        outside_temp = tempfile.TemporaryDirectory()
        self.addCleanup(outside_temp.cleanup)
        outside = Path(outside_temp.name)
        (outside / "index.html").write_text("outside\n", encoding="utf-8")
        shutil_site = self.project / "_site"
        for path in sorted(shutil_site.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        shutil_site.rmdir()
        shutil_site.symlink_to(outside, target_is_directory=True)

        status = manual_release.release_status(self.project, "latest", self.pdf_status)

        self.assertFalse(status["ok"])
        self.assertTrue(status["html_audit"]["skipped"])
        self.assertEqual((outside / "index.html").read_text(encoding="utf-8"), "outside\n")

    def test_site_snapshot_rejects_legacy_and_sandbox_output(self) -> None:
        for root in ["legacy", "sandbox"]:
            with self.subTest(root=root):
                path = self.project / "_site" / root
                path.mkdir()
                (path / "old.md").write_text("legacy\n", encoding="utf-8")
                with self.assertRaisesRegex(manual_release.ManualReleaseError, "release-forbidden"):
                    manual_release.site_snapshot(self.project)
                (path / "old.md").unlink()
                path.rmdir()

        metadata = self.project / "_site/assets/private/.git"
        metadata.mkdir(parents=True)
        (metadata / "config").write_text("private metadata\n", encoding="utf-8")
        with self.assertRaisesRegex(manual_release.ManualReleaseError, "release-forbidden"):
            manual_release.site_snapshot(self.project)

    @patch("unaltraweb_mcp.site_tools.run_make", return_value={"ok": True, "returncode": 0, "stdout": "", "stderr": ""})
    def test_successful_build_and_html_audit_write_current_receipt(self, _run_make) -> None:
        (self.project / "Makefile").write_text("build-native:\n\t@true\n", encoding="utf-8")

        result = site_tools.build_site(self.project, Path("/opt/unaltraweb"))

        self.assertTrue(result["ok"])
        self.assertTrue(result["html_audit"]["ok"])
        self.assertEqual(result["site_build_receipt"]["path"], "tmp/.unaltraweb/site-build.json")
        receipt = json.loads((self.project / "tmp/.unaltraweb/site-build.json").read_text(encoding="utf-8"))
        self.assertNotIn("generated_at", receipt)
        self.assertEqual(receipt["selector"], "latest")
        self.assertTrue(manual_release.site_build_receipt_status(self.project)["ok"])

    @patch("unaltraweb_mcp.site_tools.run_make", return_value={"ok": True, "returncode": 0, "stdout": "", "stderr": ""})
    def test_stable_build_uses_reviewed_commit_time_and_records_identity(self, run_make) -> None:
        (self.project / "Makefile").write_text("build-native:\n\t@true\n", encoding="utf-8")
        self.set_release_selector("v2026.09")

        result = site_tools.build_site(
            self.project,
            Path("/opt/unaltraweb"),
            release_selector="v2026.09",
        )

        self.assertTrue(result["ok"])
        environment = run_make.call_args.kwargs["env"]
        self.assertEqual(environment["SOURCE_DATE_EPOCH"], self.stable_identity["source_date_epoch"])
        self.assertEqual(environment["TZ"], "UTC")
        self.assertEqual(environment["UNALTRAWEB_RENDER_DIAGRAMS"], "0")
        receipt = result["site_build_receipt"]["receipt"]
        self.assertEqual(receipt["site_build_image"], self.site_build_image)
        self.assertEqual(receipt["source_commit"], self.stable_identity["commit"])
        self.assertEqual(receipt["source_date_epoch"], self.stable_identity["source_date_epoch"])

    def test_build_receipt_rejects_source_changed_during_build(self) -> None:
        (self.project / "Makefile").write_text("build-native:\n\t@true\n", encoding="utf-8")

        def mutate_source(*_args, **_kwargs):
            (self.project / "_chapters/en/chapter.md").write_text("changed during build\n", encoding="utf-8")
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

        with patch("unaltraweb_mcp.site_tools.run_make", side_effect=mutate_source):
            result = site_tools.build_site(self.project, Path("/opt/unaltraweb"))

        self.assertFalse(result["ok"])
        self.assertIn("changed while the site was being built", result["error"])


class StableSourceIdentityTests(unittest.TestCase):
    def test_identity_uses_clean_worktree_head_and_commit_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw).resolve()
            environment = {
                **os.environ,
                "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
                "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
            }
            subprocess.run(["git", "init", "-b", "main", str(project)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
            (project / "manual.md").write_text("reviewed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", "manual.md"], check=True)
            subprocess.run(
                ["git", "-C", str(project), "commit", "-m", "Reviewed manual"],
                check=True,
                env=environment,
                stdout=subprocess.DEVNULL,
            )

            identity = manual_release.stable_source_identity(project)
            self.assertRegex(identity["commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(identity["source_date_epoch"], "946684800")

            (project / "manual.md").write_text("unreviewed\n", encoding="utf-8")
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "clean Git checkout"):
                manual_release.stable_source_identity(project)

    def test_tracked_snapshot_ignores_empty_directories_and_rejects_ambient_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw).resolve()
            subprocess.run(["git", "init", "-b", "main", str(project)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
            (project / "_config.yml").write_text(
                "unaltraweb:\n  site_profile: unaltremanual\n  manual:\n    pdf:\n      enabled: false\n",
                encoding="utf-8",
            )
            (project / ".gitignore").write_text("/ignored/\n", encoding="utf-8")
            (project / "manual.md").write_text("reviewed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(project), "commit", "-m", "Reviewed sources"],
                check=True,
                stdout=subprocess.DEVNULL,
            )

            original = manual_release.source_snapshot(project, tracked_only=True)["sha256"]
            (project / "empty-directory").mkdir()
            self.assertEqual(manual_release.source_snapshot(project, tracked_only=True)["sha256"], original)

            (project / "ignored").mkdir()
            (project / "ignored/cache.txt").write_text("ambient\n", encoding="utf-8")
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "filesystem-only files"):
                manual_release.source_snapshot(project, tracked_only=True)
            (project / "ignored/cache.txt").unlink()
            (project / "ignored").rmdir()

            subprocess.run(["git", "-C", str(project), "update-index", "--skip-worktree", "manual.md"], check=True)
            (project / "manual.md").write_text("hidden worktree change\n", encoding="utf-8")
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "reviewed Git blob"):
                manual_release.source_snapshot(project, tracked_only=True)
            subprocess.run(["git", "-C", str(project), "update-index", "--no-skip-worktree", "manual.md"], check=True)
            (project / "manual.md").write_text("reviewed\n", encoding="utf-8")

            (project / ".gitattributes").write_text("manual.md filter=lfs\n", encoding="utf-8")
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "clean/smudge filters"):
                manual_release.source_snapshot(project, tracked_only=True)
            (project / ".gitattributes").unlink()

            staged_blob = subprocess.run(
                ["git", "-C", str(project), "hash-object", "-w", "--stdin"],
                input="staged but unreviewed\n",
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", str(project), "update-index", "--cacheinfo", "100644", staged_blob, "manual.md"],
                check=True,
            )
            with self.assertRaisesRegex(manual_release.ManualReleaseError, "index does not exactly match"):
                manual_release.source_snapshot(project, tracked_only=True)


if __name__ == "__main__":
    unittest.main()
