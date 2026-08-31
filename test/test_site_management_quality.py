from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import site_tools
from unaltraweb_mcp.processes import run_process


class SiteManagementQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "site"
        site_tools.new_web(self.project, site_profile_value="unaltreselfie", title="Quality site")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_site_source_allowed_path_matrix_and_content_validation(self) -> None:
        valid = {
            "_pages/new.md": "---\ntitle: New\n---\nText\n",
            "_documentation/guide.html": "<p>Guide</p>\n",
            "_data/items.yml": "items: []\n",
            "_data/items.json": '{"items": []}\n',
            "_data/items.csv": "name,value\na,1\n",
            "context/policy.markdown": "# Policy\n",
        }
        for path, content in valid.items():
            with self.subTest(path=path):
                result = site_tools.site_source_write(self.project, path, content, create_only=True)
                self.assertTrue(result["ok"])
                self.assertTrue(result["dry_run"])

        invalid = [
            "Makefile",
            "Gemfile",
            ".github/workflows/deploy.yml",
            "_layouts/page.html",
            "_plugins/unsafe.rb",
            "_sass/theme.scss",
            "_bibliography/references.bib",
            "assets/image.svg",
            "_site/index.html",
            "tmp/output.md",
            "_data/script.py",
            "context/settings.yml",
            "../outside.md",
            "/tmp/outside.md",
        ]
        for path in invalid:
            with self.subTest(path=path), self.assertRaises(ValueError):
                site_tools.site_source_write(self.project, path, "text", create_only=True)

        with self.assertRaises(ValueError):
            site_tools.site_source_write(self.project, "_data/bad.json", "{", create_only=True)
        with self.assertRaises(ValueError):
            site_tools.site_source_write(self.project, "_data/bad.yml", "key: [", create_only=True)
        with self.assertRaises(ValueError):
            site_tools.site_source_write(self.project, "_pages/nul.md", "bad\x00value", create_only=True)

    def test_site_source_dry_run_cas_apply_and_delete(self) -> None:
        path = "_pages/en/index.md"
        before = site_tools.site_source_read(self.project, path)
        proposed = before["content"] + "\nUpdated.\n"

        dry_run = site_tools.site_source_write(
            self.project,
            path,
            proposed,
            expected_sha256=before["sha256"],
        )
        self.assertTrue(dry_run["diff"]["text"])
        self.assertEqual(site_tools.site_source_read(self.project, path)["sha256"], before["sha256"])

        applied = site_tools.site_source_write(
            self.project,
            path,
            proposed,
            expected_sha256=before["sha256"],
            dry_run=False,
        )
        self.assertEqual(site_tools.site_source_read(self.project, path)["sha256"], applied["sha256"])
        with self.assertRaises(RuntimeError):
            site_tools.site_source_write(
                self.project,
                path,
                proposed + "again\n",
                expected_sha256=before["sha256"],
                dry_run=False,
            )

        created = site_tools.site_source_write(
            self.project,
            "_pages/en/delete-me.md",
            "---\ntitle: Delete me\n---\n",
            create_only=True,
            dry_run=False,
        )
        delete_dry_run = site_tools.site_source_delete(
            self.project,
            "_pages/en/delete-me.md",
            expected_sha256=created["sha256"],
        )
        self.assertTrue(delete_dry_run["dry_run"])
        with self.assertRaises(RuntimeError):
            site_tools.site_source_delete(
                self.project,
                "_pages/en/delete-me.md",
                expected_sha256=created["sha256"],
                dry_run=False,
            )
        site_tools.site_source_delete(
            self.project,
            "_pages/en/delete-me.md",
            expected_sha256=created["sha256"],
            dry_run=False,
            confirm_delete=True,
        )
        self.assertFalse((self.project / "_pages/en/delete-me.md").exists())
        config_hash = site_tools.site_source_read(self.project, "_config.yml")["sha256"]
        with self.assertRaises(ValueError):
            site_tools.site_source_delete(self.project, "_config.yml", expected_sha256=config_hash)

    def test_site_source_rejects_symlinks_and_raced_updates(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        (self.project / "_pages/link.md").symlink_to(outside)
        with self.assertRaises(RuntimeError):
            site_tools.site_source_read(self.project, "_pages/link.md")

        path = "_pages/en/index.md"
        before = site_tools.site_source_read(self.project, path)
        original = site_tools._atomic_site_source_write

        def race(root_fd, relative, content, *, create_only, expected_sha256):
            (self.project / relative).write_text("raced\n", encoding="utf-8")
            return original(
                root_fd,
                relative,
                content,
                create_only=create_only,
                expected_sha256=expected_sha256,
            )

        with patch("unaltraweb_mcp.site_tools._atomic_site_source_write", side_effect=race):
            with self.assertRaisesRegex(RuntimeError, "changed after preflight"):
                site_tools.site_source_write(
                    self.project,
                    path,
                    before["content"] + "new\n",
                    expected_sha256=before["sha256"],
                    dry_run=False,
                )
        self.assertEqual((self.project / path).read_text(encoding="utf-8"), "raced\n")
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_site_source_write_rolls_back_directory_fsync_failures(self) -> None:
        path = "_pages/en/index.md"
        before = site_tools.site_source_read(self.project, path)
        original_fsync = os.fsync

        def fail_directory_fsync(file_descriptor):
            if stat.S_ISDIR(os.fstat(file_descriptor).st_mode):
                raise OSError("simulated directory fsync failure")
            return original_fsync(file_descriptor)

        with patch("unaltraweb_mcp.site_tools.os.fsync", side_effect=fail_directory_fsync):
            with self.assertRaisesRegex(OSError, "simulated directory fsync failure"):
                site_tools.site_source_write(
                    self.project,
                    path,
                    before["content"] + "changed\n",
                    expected_sha256=before["sha256"],
                    dry_run=False,
                )
        self.assertEqual(site_tools.site_source_read(self.project, path)["sha256"], before["sha256"])

        created_path = "_pages/en/fsync-failure.md"
        with patch("unaltraweb_mcp.site_tools.os.fsync", side_effect=fail_directory_fsync):
            with self.assertRaisesRegex(OSError, "simulated directory fsync failure"):
                site_tools.site_source_write(
                    self.project,
                    created_path,
                    "new source\n",
                    create_only=True,
                    dry_run=False,
                )
        self.assertFalse((self.project / created_path).exists())

    def test_site_source_detects_final_window_update_and_delete_edits(self) -> None:
        path = "_pages/en/index.md"
        before = site_tools.site_source_read(self.project, path)
        original_link = os.link
        update_raced = False

        def race_update(source, destination, *args, **kwargs):
            nonlocal update_raced
            if destination == "index.md" and not update_raced:
                update_raced = True
                backup = next((self.project / "_pages/en").glob(".unaltraweb-source-backup-*"))
                backup.write_text("final-window edit\n", encoding="utf-8")
            return original_link(source, destination, *args, **kwargs)

        with patch("unaltraweb_mcp.site_tools.os.link", side_effect=race_update):
            with self.assertRaisesRegex(RuntimeError, "final update window"):
                site_tools.site_source_write(
                    self.project,
                    path,
                    before["content"] + "proposed\n",
                    expected_sha256=before["sha256"],
                    dry_run=False,
                )
        self.assertEqual((self.project / path).read_text(encoding="utf-8"), "final-window edit\n")

        delete_path = "_pages/en/delete-race.md"
        created = site_tools.site_source_write(
            self.project,
            delete_path,
            "delete baseline\n",
            create_only=True,
            dry_run=False,
        )
        delete_raced = False

        def race_delete(source, destination, *args, **kwargs):
            nonlocal delete_raced
            if str(destination).endswith("-audit") and not delete_raced:
                delete_raced = True
                tombstone = next((self.project / "_pages/en").glob(".unaltraweb-source-delete-*"))
                tombstone.write_text("delete-window edit\n", encoding="utf-8")
            return original_link(source, destination, *args, **kwargs)

        with patch("unaltraweb_mcp.site_tools.os.link", side_effect=race_delete):
            with self.assertRaisesRegex(RuntimeError, "final delete window"):
                site_tools.site_source_delete(
                    self.project,
                    delete_path,
                    expected_sha256=created["sha256"],
                    dry_run=False,
                    confirm_delete=True,
                )
        self.assertEqual((self.project / delete_path).read_text(encoding="utf-8"), "delete-window edit\n")

    def test_site_source_rejects_special_oversize_and_non_strict_data(self) -> None:
        fifo = self.project / "_pages/fifo.md"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, "regular file"):
            site_tools.site_source_read(self.project, "_pages/fifo.md")

        oversize = self.project / "_pages/oversize.md"
        with oversize.open("wb") as stream:
            stream.truncate(site_tools.SITE_SOURCE_MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "byte limit"):
            site_tools.site_source_read(self.project, "_pages/oversize.md")

        with self.assertRaisesRegex(ValueError, "non-finite"):
            site_tools.site_source_write(self.project, "_data/nonfinite.json", '{"value": NaN}\n', create_only=True)
        with self.assertRaisesRegex(ValueError, "duplicate YAML key"):
            site_tools.site_source_write(self.project, "_data/duplicate.yml", "value: one\nvalue: two\n", create_only=True)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            site_tools.site_source_write(self.project, "_data/duplicate.json", '{"value": 1, "value": 2}\n', create_only=True)

    def test_profile_prune_empty_directory_cleanup_never_follows_symlinks(self) -> None:
        project = self.root / "prune-site"
        outside = self.root / "outside-content"
        (outside / "empty").mkdir(parents=True)
        project.mkdir()
        (project / "_pages").symlink_to(outside, target_is_directory=True)
        (project / "_posts").mkdir()
        (project / "_posts/outside").symlink_to(outside, target_is_directory=True)
        (project / "_chapters/empty/deep").mkdir(parents=True)
        (project / "_config.yml").write_text(
            "theme: unaltraweb\nunaltraweb:\n  site_profile: unaltreselfie\n",
            encoding="utf-8",
        )

        result = site_tools.profile_prune(project, dry_run=False, confirm_prune=True)

        self.assertTrue(result["ok"])
        self.assertEqual(set(result["empty_dirs_removed"]), {"_chapters/empty/deep", "_chapters/empty"})
        self.assertTrue((project / "_pages").is_symlink())
        self.assertTrue((project / "_posts/outside").is_symlink())
        self.assertTrue((outside / "empty").is_dir())

        protected = outside / "protected.md"
        protected.write_text("---\nprofiles: [unaltremanual]\n---\nProtected\n", encoding="utf-8")
        raced_plan = {
            "project": str(project),
            "site_profile": "unaltreselfie",
            "candidate_count": 1,
            "candidates": [{"path": "_posts/outside/protected.md", "profiles": ["unaltremanual"], "title": ""}],
            "kept_profiled_count": 0,
            "kept_profiled_sample": [],
            "unprofiled_count": 0,
            "unprofiled_sample": [],
            "rule": "test plan",
        }
        with patch("unaltraweb_mcp.site_tools.profile_prune_plan", return_value=raced_plan):
            confined = site_tools.profile_prune(project, dry_run=False, confirm_prune=True)
        self.assertEqual(confined["deleted"], [])
        self.assertEqual(confined["skipped"][0]["path"], "_posts/outside/protected.md")
        self.assertTrue(protected.is_file())

    def test_scaffold_sync_updates_baseline_files_and_never_overwrites_conflicts(self) -> None:
        original_payloads = site_tools._managed_scaffold_payloads()
        updated_payloads = dict(original_payloads)
        updated_payloads[Path("Makefile")] += b"\n# package update\n"

        with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated_payloads):
            dry_run = site_tools.scaffold_sync(self.project)
            self.assertEqual([item["path"] for item in dry_run["updates"]], ["Makefile"])
            self.assertFalse(dry_run["applied"])
            applied = site_tools.scaffold_sync(self.project, dry_run=False, confirm_sync=True)
            self.assertTrue(applied["applied"])
        self.assertTrue((self.project / "Makefile").read_bytes().endswith(b"# package update\n"))

        conflict_site = self.root / "conflict"
        site_tools.new_web(conflict_site)
        (conflict_site / "Makefile").write_text("locally edited\n", encoding="utf-8")
        gemfile_before = (conflict_site / "Gemfile").read_bytes()
        with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated_payloads):
            conflict = site_tools.scaffold_sync(conflict_site, dry_run=False, confirm_sync=True)
        self.assertFalse(conflict["ok"])
        self.assertFalse(conflict["applied"])
        self.assertEqual((conflict_site / "Makefile").read_text(encoding="utf-8"), "locally edited\n")
        self.assertEqual((conflict_site / "Gemfile").read_bytes(), gemfile_before)

    def test_scaffold_sync_creates_only_new_missing_managed_paths(self) -> None:
        manifest_path = self.project / ".unaltraweb/scaffold.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].pop(".gitignore")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (self.project / ".gitignore").unlink()

        result = site_tools.scaffold_sync(self.project, dry_run=False, confirm_sync=True)

        self.assertTrue(result["applied"])
        self.assertEqual([item["path"] for item in result["creates"]], [".gitignore"])
        self.assertEqual((self.project / ".gitignore").read_bytes(), site_tools._managed_scaffold_payloads()[Path(".gitignore")])

    def test_scaffold_sync_rechecks_every_target_before_applying(self) -> None:
        payloads = site_tools._managed_scaffold_payloads()
        updated = dict(payloads)
        updated[Path("Makefile")] += b"\n# update one\n"
        updated[Path("Gemfile")] += b"\n# update two\n"
        gemfile_before = (self.project / "Gemfile").read_bytes()
        original_recheck = site_tools._recheck_scaffold_sync

        def race(root_fd, plan):
            (self.project / "Makefile").write_text("raced local edit\n", encoding="utf-8")
            return original_recheck(root_fd, plan)

        with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated), patch(
            "unaltraweb_mcp.site_tools._recheck_scaffold_sync",
            side_effect=race,
        ):
            with self.assertRaisesRegex(RuntimeError, "changed after scaffold_sync preflight"):
                site_tools.scaffold_sync(self.project, dry_run=False, confirm_sync=True)

        self.assertEqual((self.project / "Makefile").read_text(encoding="utf-8"), "raced local edit\n")
        self.assertEqual((self.project / "Gemfile").read_bytes(), gemfile_before)

    def test_scaffold_sync_rolls_back_all_files_and_manifest_on_apply_failure(self) -> None:
        payloads = site_tools._managed_scaffold_payloads()
        updated = dict(payloads)
        updated[Path("Makefile")] += b"\n# transaction one\n"
        updated[Path("Gemfile")] += b"\n# transaction two\n"
        before = {
            path: (self.project / path).read_bytes()
            for path in [Path("Makefile"), Path("Gemfile"), site_tools.SCAFFOLD_MANIFEST_PATH]
        }
        original_commit = site_tools._commit_staged_managed_write

        def fail_second(staged, *, expected_sha256=""):
            if staged["relative"] == Path("Gemfile"):
                raise RuntimeError("injected second-file failure")
            return original_commit(staged, expected_sha256=expected_sha256)

        with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated), patch(
            "unaltraweb_mcp.site_tools._commit_staged_managed_write",
            side_effect=fail_second,
        ):
            with self.assertRaisesRegex(RuntimeError, "injected second-file failure"):
                site_tools.scaffold_sync(self.project, dry_run=False, confirm_sync=True)

        for path, content in before.items():
            self.assertEqual((self.project / path).read_bytes(), content)
        self.assertFalse(list(self.project.rglob(".unaltraweb-scaffold-*")))

    def test_scaffold_sync_preserves_a_final_window_local_edit(self) -> None:
        payloads = site_tools._managed_scaffold_payloads()
        updated = dict(payloads)
        updated[Path("Makefile")] += b"\n# proposed package update\n"
        manifest_before = (self.project / site_tools.SCAFFOLD_MANIFEST_PATH).read_bytes()
        original_link = os.link
        raced = False

        def race_managed_update(source, destination, *args, **kwargs):
            nonlocal raced
            if destination == "Makefile" and not raced:
                raced = True
                backup = next(self.project.glob(".unaltraweb-scaffold-backup-*"))
                backup.write_text("final managed edit\n", encoding="utf-8")
            return original_link(source, destination, *args, **kwargs)

        with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated), patch(
            "unaltraweb_mcp.site_tools.os.link",
            side_effect=race_managed_update,
        ):
            with self.assertRaisesRegex(RuntimeError, "final scaffold_sync window"):
                site_tools.scaffold_sync(self.project, dry_run=False, confirm_sync=True)

        self.assertEqual((self.project / "Makefile").read_text(encoding="utf-8"), "final managed edit\n")
        self.assertEqual((self.project / site_tools.SCAFFOLD_MANIFEST_PATH).read_bytes(), manifest_before)

    def test_scaffold_sync_rechecks_unchanged_and_adopted_files_before_manifest_commit(self) -> None:
        for state, target_name in [("unchanged", "Gemfile"), ("adopted", ".gitignore")]:
            with self.subTest(state=state):
                project = self.root / f"final-recheck-{state}"
                site_tools.new_web(project)
                manifest_path = project / site_tools.SCAFFOLD_MANIFEST_PATH
                if state == "adopted":
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["files"].pop(target_name)
                    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                manifest_before = manifest_path.read_bytes()
                makefile_before = (project / "Makefile").read_bytes()
                payloads = site_tools._managed_scaffold_payloads()
                updated = dict(payloads)
                updated[Path("Makefile")] += b"\n# package transaction\n"
                original_verify = site_tools._verify_applied_managed_transaction
                raced = False

                def race_before_manifest(applied):
                    nonlocal raced
                    original_verify(applied)
                    if not raced:
                        raced = True
                        (project / target_name).write_text(f"raced {state}\n", encoding="utf-8")

                with patch("unaltraweb_mcp.site_tools._managed_scaffold_payloads", return_value=updated), patch(
                    "unaltraweb_mcp.site_tools._verify_applied_managed_transaction",
                    side_effect=race_before_manifest,
                ):
                    with self.assertRaisesRegex(RuntimeError, "before scaffold_sync manifest commit"):
                        site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True)

                self.assertEqual((project / target_name).read_text(encoding="utf-8"), f"raced {state}\n")
                self.assertEqual((project / "Makefile").read_bytes(), makefile_before)
                self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_new_web_publishes_scaffold_manifest_last(self) -> None:
        project = self.root / "manifest-last"
        created: list[Path] = []
        original_create = site_tools._create_scaffold_file

        def record(root_fd, relative, content):
            created.append(relative)
            return original_create(root_fd, relative, content)

        with patch("unaltraweb_mcp.site_tools._create_scaffold_file", side_effect=record):
            site_tools.new_web(project)

        self.assertEqual(created[-1], site_tools.SCAFFOLD_MANIFEST_PATH)

    def test_site_doctor_is_strict_offline_and_inventories_overrides(self) -> None:
        (self.project / "_layouts").mkdir()
        (self.project / "_layouts/custom.html").write_text("custom\n", encoding="utf-8")

        result = site_tools.site_doctor(self.project)

        self.assertTrue(result["ok"], result["findings"])
        self.assertTrue(result["offline"])
        self.assertTrue(result["read_only"])
        self.assertIn("_layouts/custom.html", result["checks"]["core_overrides"]["files"])
        self.assertIn("UW-SITE-SCAFFOLD-DRIFT", {item["code"] for item in result["findings"]})

        (self.project / "_config.yml").write_text("title: one\ntitle: two\n", encoding="utf-8")
        invalid = site_tools.site_doctor(self.project)
        self.assertFalse(invalid["ok"])
        parse = next(item for item in invalid["findings"] if item["code"] == "UW-SITE-CONFIG-PARSE")
        self.assertEqual(parse["severity"], "error")

    def test_companion_gate_requires_a_verifiable_provider_receipt(self) -> None:
        source = self.project / "charts/example.vl.json"
        output = self.project / "assets/charts/example.svg"
        data = self.project / "assets/charts/example.csv"
        extra = self.project / "assets/charts/extra.csv"
        source.parent.mkdir(parents=True)
        output.parent.mkdir(parents=True)
        source.write_text('{"data": {"url": "assets/charts/example.csv"}, "mark": "bar"}\n', encoding="utf-8")
        output.write_text("<svg/>\n", encoding="utf-8")
        data.write_text("value\n1\n", encoding="utf-8")
        extra.write_text("label\na\n", encoding="utf-8")
        (self.project / ".vegavisuals.yml").write_text(
            "inputs:\n  - assets/charts/extra.csv\nvisualizations:\n  - source: charts/example.vl.json\n    output: assets/charts/example.svg\n",
            encoding="utf-8",
        )

        missing = site_tools.visualization_status(self.project, self.root)
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["receipt"]["state"], "missing")

        inputs = site_tools._companion_input_paths(self.project, "vegavisuals")
        self.assertIn(source, inputs)
        selected = site_tools.component("vegavisuals")
        receipt = {
            "schema_version": 1,
            "provider": "vegavisuals",
            "provider_version": selected["version"],
            "release": selected["release"],
            "request_sha256": site_tools._companion_request_sha256(self.project, "vegavisuals", inputs),
            "ok": True,
            "inputs": [{"path": "assets/charts/extra.csv", "sha256": site_tools._source_hash(extra.read_bytes())}],
            "artifacts": [{"path": "assets/charts/example.svg", "sha256": site_tools._source_hash(output.read_bytes())}],
        }
        receipt_path = self.project / ".unaltraweb/receipts/vegavisuals.json"
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        omitted = site_tools.visualization_status(self.project, self.root)
        self.assertFalse(omitted["ok"])
        self.assertEqual(omitted["receipt"]["state"], "mismatch")
        receipt["inputs"].append({"path": "assets/charts/example.csv", "sha256": site_tools._source_hash(data.read_bytes())})
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertTrue(site_tools.visualization_status(self.project, self.root)["ok"])

        data.write_text("value\n2\n", encoding="utf-8")
        stale_data = site_tools.visualization_status(self.project, self.root)
        self.assertFalse(stale_data["ok"])
        self.assertEqual(stale_data["receipt"]["state"], "invalid")
        data.write_text("value\n1\n", encoding="utf-8")

        source.write_text('{"mark": "line"}\n', encoding="utf-8")
        stale = site_tools.visualization_status(self.project, self.root)
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["receipt"]["state"], "mismatch")
        with patch("unaltraweb_mcp.site_tools.run_make") as run_make:
            blocked = site_tools.build_site(self.project, self.root)
        self.assertFalse(blocked["ok"])
        run_make.assert_not_called()

    def test_vegavisuals_dependency_discovery_rejects_unverifiable_urls_and_deep_specs(self) -> None:
        source = self.project / "assets/charts/unsafe.vl.json"
        source.parent.mkdir(parents=True)
        (self.project / ".vegavisuals.yml").write_text(
            "visualizations:\n  - source: assets/charts/unsafe.vl.json\n    output: assets/charts/unsafe.svg\n",
            encoding="utf-8",
        )
        cases = {
            "remote": {"data": {"url": "https://example.org/data.csv"}, "mark": "bar"},
            "dynamic": {"data": {"url": {"signal": "dataset"}}, "mark": "bar"},
            "escaping": {"data": {"url": "../outside.csv"}, "mark": "bar"},
        }
        for name, specification in cases.items():
            with self.subTest(name=name):
                source.write_text(json.dumps(specification), encoding="utf-8")
                status = site_tools.visualization_status(self.project, self.root)
                self.assertFalse(status["ok"])
                self.assertEqual(status["receipt"]["state"], "invalid")

        specification: dict[str, object] = {"data": {"url": "assets/charts/data.csv"}}
        for _ in range(site_tools.COMPANION_JSON_MAX_DEPTH + 1):
            specification = {"layer": [specification]}
        source.write_text(json.dumps(specification), encoding="utf-8")
        deep = site_tools.visualization_status(self.project, self.root)
        self.assertFalse(deep["ok"])
        self.assertIn("inspection limit", deep["receipt"]["error"])

    def test_site_check_requires_fresh_diagrams_and_exact_diavisuals_receipt(self) -> None:
        source = self.project / "assets/diagrams/flow.mmd"
        output = Path(str(source) + ".svg")
        source.parent.mkdir(parents=True)
        source.write_text("flowchart LR\n  A --> B\n", encoding="utf-8")
        output.write_text("<svg/>\n", encoding="utf-8")

        with patch("unaltraweb_mcp.site_tools.manual_computation_status", return_value={"ok": True}), patch(
            "unaltraweb_mcp.site_tools.web_capture_status", return_value={"ok": True}
        ):
            missing = site_tools.site_check(self.project, self.root)
        self.assertFalse(missing["ok"])
        self.assertFalse(missing["diagrams"]["ok"])
        self.assertEqual(missing["diagrams"]["receipt"]["state"], "missing")

        sources = site_tools._companion_input_paths(self.project, "diavisuals")
        selected = site_tools.component("diavisuals")
        receipt = {
            "schema_version": 1,
            "provider": "diavisuals",
            "provider_version": selected["version"],
            "release": selected["release"],
            "request_sha256": site_tools._companion_request_sha256(self.project, "diavisuals", sources),
            "ok": True,
            "inputs": [],
            "artifacts": [{"path": "assets/diagrams/flow.mmd.svg", "sha256": site_tools._source_hash(output.read_bytes())}],
        }
        receipt_path = self.project / ".unaltraweb/receipts/diavisuals.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with patch("unaltraweb_mcp.site_tools.manual_computation_status", return_value={"ok": True}), patch(
            "unaltraweb_mcp.site_tools.web_capture_status", return_value={"ok": True}
        ):
            verified = site_tools.site_check(self.project, self.root)
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["diagrams"]["ok"])

        output_mtime = output.stat().st_mtime_ns
        os.utime(source, ns=(output_mtime + 1_000_000, output_mtime + 1_000_000))
        with patch("unaltraweb_mcp.site_tools.manual_computation_status", return_value={"ok": True}), patch(
            "unaltraweb_mcp.site_tools.web_capture_status", return_value={"ok": True}
        ):
            stale = site_tools.site_check(self.project, self.root)
        self.assertFalse(stale["ok"])
        self.assertTrue(stale["diagrams"]["receipt"]["ok"])
        self.assertEqual(stale["diagrams"]["sources"][0]["state"], "stale")
        source_mtime = source.stat().st_mtime_ns
        os.utime(output, ns=(source_mtime + 1_000_000, source_mtime + 1_000_000))

        receipt["inputs"] = [{"path": "assets/diagrams/flow.mmd", "sha256": site_tools._source_hash(source.read_bytes())}]
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        with patch("unaltraweb_mcp.site_tools.manual_computation_status", return_value={"ok": True}), patch(
            "unaltraweb_mcp.site_tools.web_capture_status", return_value={"ok": True}
        ):
            extra_input = site_tools.site_check(self.project, self.root)
        self.assertFalse(extra_input["ok"])
        self.assertEqual(extra_input["diagrams"]["receipt"]["state"], "mismatch")

    def test_html_audit_covers_local_quality_without_fetching_external_links(self) -> None:
        site = self.project / "_site"
        (site / "about").mkdir(parents=True)
        (site / "assets").mkdir()
        (site / "assets/app.js").write_text("", encoding="utf-8")
        (site / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Home</title><script src="/assets/app.js"></script></head>'
            '<body><a href="/about/#team">About</a><a href="https://example.com/x">External</a>'
            '<img src="/assets/app.js" alt=""></body></html>',
            encoding="utf-8",
        )
        (site / "about/index.html").write_text(
            '<!doctype html><html lang="en"><head><title>About</title></head><body><h1 id="team">Team</h1></body></html>',
            encoding="utf-8",
        )

        clean = site_tools.html_audit(self.project)
        self.assertTrue(clean["ok"], clean["findings"])
        self.assertEqual(clean["external_fetches"], 0)
        self.assertEqual(clean["external_links"][0]["url"], "https://example.com/x")

        (site / "index.html").write_text(
            '<html><head><title></title></head><body><div id="same"></div><div id="same"></div>'
            '<img src="/missing.png"><a href="/about/#missing">Bad</a>{{ unresolved }}</body></html>',
            encoding="utf-8",
        )
        broken = site_tools.html_audit(self.project)
        codes = {finding["code"] for finding in broken["findings"]}
        self.assertFalse(broken["ok"])
        self.assertTrue({"UW-HTML-DUPLICATE-ID", "UW-HTML-UNRESOLVED-LIQUID", "UW-HTML-IMG-ALT", "UW-HTML-TITLE", "UW-HTML-LANG", "UW-HTML-INTERNAL-TARGET", "UW-HTML-FRAGMENT"}.issubset(codes))
        doctor = site_tools.site_doctor(self.project)
        self.assertFalse(doctor["ok"])
        self.assertIn("UW-SITE-HTML-AUDIT", {finding["code"] for finding in doctor["findings"]})

    def test_html_audit_and_doctor_fail_explicitly_for_missing_or_unknown_required_state(self) -> None:
        missing = site_tools.html_audit(self.project)
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["findings"][0]["code"], "UW-HTML-SITE-MISSING")

        source = self.project / "_chapters/example.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("print('example')\n", encoding="utf-8")
        doctor = site_tools.site_doctor(self.project)
        self.assertFalse(doctor["ok"])
        freshness = next(finding for finding in doctor["findings"] if finding["code"] == "UW-SITE-COMPUTATIONS-FRESHNESS")
        self.assertEqual(freshness["severity"], "error")

    def test_bounded_process_runner_times_out_process_group_and_caps_output(self) -> None:
        timed = run_process(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout_seconds=0.1,
        )
        self.assertTrue(timed.timed_out)
        self.assertEqual(timed.returncode, 124)

        output = run_process(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 10000); sys.stderr.write('y' * 10000)"],
            timeout_seconds=2,
            output_limit=128,
        )
        self.assertEqual(output.returncode, 0)
        self.assertEqual(len(output.stdout.encode()), 128)
        self.assertEqual(len(output.stderr.encode()), 128)
        self.assertTrue(output.stdout_truncated)
        self.assertTrue(output.stderr_truncated)

    def test_timed_out_worker_cleanup_is_scoped_to_invocation_labels(self) -> None:
        timed_out = site_tools.ProcessResult(
            args=["make"], returncode=124, stdout="", stderr="timeout", timed_out=True,
            stdout_truncated=False, stderr_truncated=False,
        )
        listed = site_tools.ProcessResult(
            args=["docker"], returncode=0, stdout="a" * 64 + "\n", stderr="", timed_out=False,
            stdout_truncated=False, stderr_truncated=False,
        )
        removed = site_tools.ProcessResult(
            args=["docker"], returncode=0, stdout="", stderr="", timed_out=False,
            stdout_truncated=False, stderr_truncated=False,
        )
        with patch("unaltraweb_mcp.site_tools.run_process", side_effect=[timed_out, listed, removed]) as run:
            result = site_tools.run_factory_make(
                self.root / "factory",
                self.project,
                "manual-compute-render",
                timeout_seconds=0.1,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["worker_cleanup"]["removed"], ["a" * 64])
        make_env = run.call_args_list[0].kwargs["env"]
        self.assertEqual(make_env["UNALTRAWEB_WORKER_ROLE"], "computation")
        list_command = run.call_args_list[1].args[0]
        self.assertEqual(list_command[:3], ["docker", "ps", "-aq"])
        for label in [
            site_tools.WORKER_FACTORY_LABEL,
            site_tools.WORKER_ROLE_LABEL,
            site_tools.WORKER_PROJECT_LABEL,
            site_tools.WORKER_TOKEN_LABEL,
        ]:
            self.assertTrue(any(label in value for value in list_command))
        self.assertEqual(run.call_args_list[2].args[0], ["docker", "rm", "-f", "a" * 64])

    def test_http_check_uses_only_owned_preview_origin_and_rejects_hostile_scope(self) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/base/en/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.9"}}},
        }
        with patch("unaltraweb_mcp.site_tools._preview_inspect", return_value=info), patch(
            "unaltraweb_mcp.site_tools._http_probe",
            return_value={"origin": "http://172.17.0.9:4000", "ok": True, "checks": [], "redirects_followed": 0},
        ) as probe:
            result = site_tools.http_check(self.project, paths=["/base/en/", "/assets/app.css"], timeout_seconds=1)
        self.assertTrue(result["owned"])
        probe.assert_called_once_with(
            "http://172.17.0.9:4000",
            ["/base/en/", "/assets/app.css"],
            timeout_seconds=1,
        )

        for hostile in ["https://example.com/", "//example.com/x", "/../secret", "/%2e%2e/secret", "/safe#fragment"]:
            with self.subTest(path=hostile), self.assertRaises(ValueError):
                site_tools.http_check(self.project, paths=[hostile])
        with self.assertRaises(ValueError):
            site_tools.http_check(self.project, paths=[f"/{index}" for index in range(21)])
        with self.assertRaises(ValueError):
            site_tools.http_check(self.project, paths=["/"], timeout_seconds=10)

    def test_private_http_probe_disables_proxies_and_bounds_response_reads(self) -> None:
        class Response:
            status = 200
            reason = "OK"

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size):
                self.requested = size
                return b"x" * size

        response = Response()

        class Opener:
            def open(self, url, timeout):
                self.url = url
                self.timeout = timeout
                return response

        opener = Opener()
        with patch("unaltraweb_mcp.site_tools.urllib.request.build_opener", return_value=opener) as build_opener:
            result = site_tools._http_probe("http://127.0.0.1:4000", ["/health"], timeout_seconds=1)

        self.assertTrue(result["ok"])
        self.assertEqual(response.requested, site_tools.HTTP_RESPONSE_MAX_BYTES + 1)
        self.assertTrue(result["checks"][0]["response_truncated"])
        self.assertEqual(build_opener.call_args.args[0].proxies, {})

    @patch("unaltraweb_mcp.site_tools.run_make", return_value={"ok": True, "returncode": 0, "stdout": "", "stderr": ""})
    def test_build_site_includes_html_audit_after_success(self, _run_make) -> None:
        site = self.project / "_site"
        site.mkdir()
        (site / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Built</title></head><body></body></html>',
            encoding="utf-8",
        )

        result = site_tools.build_site(self.project, Path("/opt/unaltraweb"))

        self.assertTrue(result["ok"])
        self.assertTrue(result["html_audit"]["ok"])


if __name__ == "__main__":
    unittest.main()
