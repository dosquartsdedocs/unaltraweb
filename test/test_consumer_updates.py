from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import cli, site_tools


def files(project: Path) -> dict[str, bytes]:
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for path in project.rglob("*") if path.is_file() and not path.is_symlink()}


class ConsumerUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def create(self, name: str = "site", *, profile: str = "unaltreselfie", version: str | None = None) -> Path:
        project = self.root / name
        replacements = site_tools._common_scaffold_replacements()
        if version is not None:
            replacements.update({
                "GEM_VERSION": version,
                "MCP_IMAGE": "ghcr.io/dosquartsdedocs/unaltraweb-mcp:" + version,
                "CORE_SHA": "1" * 40,
                "MANUAL_PDF_IMAGE": "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:" + "2" * 64,
            })
        # Render a previous package's integration pins through official creation;
        # its baseline is produced by new_web, never fabricated by the updater.
        with patch.object(site_tools, "_common_scaffold_replacements", return_value=replacements):
            created = site_tools.new_web(project, site_profile_value=profile)
        self.assertTrue(created["ok"], created)
        return project

    def test_context_inspection_is_offline_and_current_in_all_profiles(self) -> None:
        for profile in site_tools.PROFILE_CONTRACTS:
            with self.subTest(profile=profile):
                project = self.create(profile, profile=profile)
                before = files(project)
                with patch.object(site_tools, "run_process", side_effect=AssertionError("executed a process")), patch(
                    "urllib.request.urlopen", side_effect=AssertionError("used the network"),
                ):
                    update = site_tools.site_context(project)["update_status"]
                self.assertEqual(update["state"], "current")
                self.assertTrue(update["offline"])
                self.assertFalse(update["update_available"])
                self.assertFalse(update["can_apply"])
                self.assertEqual(files(project), before)

    def test_upgrade_preserves_local_ignores_content_and_original_baseline(self) -> None:
        project = self.create(version="0.3.0")
        ignore = project / ".gitignore"
        original_manifest = json.loads((project / site_tools.SCAFFOLD_MANIFEST_PATH).read_text())
        ignore.write_text(ignore.read_text() + "\n/private-notes/\n", encoding="utf-8")
        ignore_inode = ignore.stat().st_ino
        home = project / "_pages/en/index.md"
        home.write_text(home.read_text() + "\nOwn editorial material.\n", encoding="utf-8")
        before = files(project)

        update = site_tools.site_context(project)["update_status"]

        self.assertTrue(update["update_available"])
        self.assertTrue(update["newer_version_available"])
        self.assertTrue(update["can_apply"])
        self.assertEqual(update["current_versions"]["mcp_version"], "0.3.0")
        self.assertEqual(update["preserved"], [".gitignore"])
        self.assertEqual(files(project), before)
        with self.assertRaisesRegex(RuntimeError, "confirm_sync"):
            site_tools.scaffold_sync(project, dry_run=False, expected_plan_sha256=update["plan_sha256"])
        self.assertEqual(files(project), before)

        applied = site_tools.scaffold_sync(project, **update["apply_arguments"])

        self.assertTrue(applied["applied"])
        self.assertEqual(ignore.read_bytes(), before[".gitignore"])
        self.assertEqual(ignore.stat().st_ino, ignore_inode)
        self.assertEqual(home.read_bytes(), before["_pages/en/index.md"])
        manifest = json.loads((project / site_tools.SCAFFOLD_MANIFEST_PATH).read_text())
        self.assertEqual(manifest["files"][".gitignore"], original_manifest["files"][".gitignore"])
        self.assertEqual({item["path"] for item in applied["updates"]},
                         {"Makefile", "Gemfile", "Gemfile.lock", ".github/workflows/deploy.yml"})
        self.assertEqual(site_tools.site_context(project)["update_status"]["state"], "current_customized")

        # A later upstream ignore change must still conflict with the local rule.
        payloads = site_tools._managed_scaffold_payloads(project)
        payloads[Path(".gitignore")] += b"\n/new-package-output/\n"
        with patch.object(site_tools, "_managed_scaffold_payloads", return_value=payloads):
            later = site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True)
        self.assertFalse(later["applied"])
        self.assertEqual([item["path"] for item in later["conflicts"]], [".gitignore"])
        self.assertEqual(ignore.read_bytes(), before[".gitignore"])

    def test_plans_are_repeatable_and_output_bytes_do_not_depend_on_an_agent(self) -> None:
        first = self.create("first", version="0.3.0")
        second = self.create("second", version="0.3.0")
        for project in (first, second):
            with (project / ".gitignore").open("a") as stream:
                stream.write("\n/private-notes/\n")
        before = files(first)
        with patch.object(site_tools, "utc_now", return_value="2026-01-01T00:00:00+00:00"):
            first_context = site_tools.site_context(first)
        with patch.object(site_tools, "utc_now", return_value="2026-02-01T00:00:00+00:00"):
            repeated_context = site_tools.site_context(first)
        self.assertNotEqual(first_context["generated_at"], repeated_context["generated_at"])
        self.assertEqual(first_context["update_status"], repeated_context["update_status"])
        self.assertEqual(files(first), before)
        plan = site_tools.scaffold_sync(first)
        self.assertEqual(plan, site_tools.scaffold_sync(first))
        self.assertEqual(plan["plan_sha256"], first_context["update_status"]["plan_sha256"])

        home = first / "_pages/en/index.md"
        home.write_bytes(home.read_bytes() + b"\nUnrelated editorial revision.\n")
        edited_home = home.read_bytes()
        self.assertEqual(site_tools.scaffold_sync(first), plan)
        other = site_tools.scaffold_sync(second)
        self.assertNotEqual(plan["plan_sha256"], other["plan_sha256"])
        for project, reviewed in ((first, plan), (second, other)):
            result = site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True,
                                              expected_plan_sha256=reviewed["plan_sha256"])
            self.assertTrue(result["applied"])
        for path in [*site_tools.SCAFFOLD_MANAGED_PATHS, site_tools.SCAFFOLD_MANIFEST_PATH]:
            self.assertEqual((first / path).read_bytes(), (second / path).read_bytes(), str(path))
        self.assertEqual(home.read_bytes(), edited_home)

    def test_actual_local_upstream_conflict_blocks_whole_upgrade(self) -> None:
        project = self.create(version="0.3.0")
        with (project / "Makefile").open("a") as stream:
            stream.write("\nmanual-pdf-sync:\n\t@true\n")
        before = files(project)
        update = site_tools.site_context(project)["update_status"]
        self.assertEqual(update["state"], "conflicts")
        self.assertFalse(update["can_apply"])
        self.assertEqual(update["apply_arguments"], {})
        self.assertEqual({item["path"] for item in update["conflicts"]}, {"Makefile"})
        applied = site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True)
        self.assertFalse(applied["applied"])
        self.assertEqual(files(project), before)

    def test_same_version_scaffold_refresh_is_not_claimed_as_newer_release(self) -> None:
        project = self.create()
        payloads = site_tools._managed_scaffold_payloads(project)
        payloads[Path("Makefile")] += b"\n# package maintenance\n"
        with patch.object(site_tools, "_managed_scaffold_payloads", return_value=payloads):
            update = site_tools.site_context(project)["update_status"]
            self.assertTrue(update["update_available"])
            self.assertFalse(update["newer_version_available"])
            self.assertTrue(site_tools.scaffold_sync(project, **update["apply_arguments"])["applied"])

    def test_older_mcp_cannot_downgrade_consumer(self) -> None:
        project = self.create(version="99.0.0")
        before = files(project)
        update = site_tools.site_context(project)["update_status"]
        self.assertEqual(update["state"], "newer_consumer")
        self.assertFalse(update["update_available"])
        self.assertFalse(update["can_apply"])
        result = site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True)
        self.assertFalse(result["applied"])
        self.assertIn("newer-consumer-version", {item.get("code") for item in result["conflicts"]})
        self.assertEqual(files(project), before)

    def test_custom_version_override_is_not_silently_treated_as_current(self) -> None:
        project = self.create()
        makefile = project / "Makefile"
        makefile.write_text(makefile.read_text().replace(site_tools.component_reference("mcp"),
                           "ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0"), encoding="utf-8")
        before = files(project)
        update = site_tools.site_context(project)["update_status"]
        self.assertEqual(update["state"], "conflicts")
        self.assertFalse(update["can_apply"])
        self.assertIn("custom-version-pin", {item.get("code") for item in update["conflicts"]})
        self.assertTrue(update["update_available"])
        self.assertTrue(update["newer_version_available"])
        self.assertEqual(files(project), before)

    def test_approval_is_invalidated_by_consumer_package_config_or_baseline_change(self) -> None:
        for change in ("consumer", "package", "config", "baseline"):
            with self.subTest(change=change):
                project = self.create(change, version="0.3.0")
                plan = site_tools.scaffold_sync(project)
                payloads = site_tools._managed_scaffold_payloads(project)
                if change == "package":
                    payloads[Path("Makefile")] += b"\n# new package revision\n"
                else:
                    path = {"consumer": ".gitignore", "config": "_config.yml", "baseline": str(site_tools.SCAFFOLD_MANIFEST_PATH)}[change]
                    with (project / path).open("a") as stream:
                        stream.write("\n" if change == "baseline" else "\n# changed since review\n")
                before = files(project)
                with patch.object(site_tools, "_managed_scaffold_payloads", return_value=payloads):
                    with self.assertRaisesRegex(RuntimeError, "plan changed since review"):
                        site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True, expected_plan_sha256=plan["plan_sha256"])
                self.assertEqual(files(project), before)

    def test_approval_cannot_be_reused_in_another_consumer(self) -> None:
        first = self.create("first", version="0.3.0")
        second = self.create("second", version="0.3.0")
        plan = site_tools.scaffold_sync(first)
        with self.assertRaisesRegex(RuntimeError, "plan changed since review"):
            site_tools.scaffold_sync(second, dry_run=False, confirm_sync=True, expected_plan_sha256=plan["plan_sha256"])
        with self.assertRaises(ValueError):
            site_tools.scaffold_sync(second, expected_plan_sha256="not-a-digest")

    def test_preserved_file_races_abort_or_roll_back_without_overwriting_edit(self) -> None:
        phases = ("_recheck_scaffold_sync", "_recheck_scaffold_sync_before_manifest", "_verify_scaffold_sync_committed")
        for phase in phases:
            with self.subTest(phase=phase):
                project = self.create(phase, version="0.3.0")
                ignore = project / ".gitignore"
                ignore.write_text(ignore.read_text() + "\n/private-notes/\n", encoding="utf-8")
                before = files(project)
                original = getattr(site_tools, phase)

                def race(root_fd, plan):
                    ignore.write_text("Concurrent author edit\n", encoding="utf-8")
                    return original(root_fd, plan)

                with patch.object(site_tools, phase, side_effect=race):
                    with self.assertRaisesRegex(RuntimeError, "Preserved managed file changed"):
                        site_tools.scaffold_sync(project, dry_run=False, confirm_sync=True)
                before[".gitignore"] = b"Concurrent author edit\n"
                self.assertEqual(files(project), before)
                self.assertFalse(list(project.rglob(".unaltraweb-scaffold-*")))

    def test_missing_baseline_and_symlinks_are_reported_without_overwrite(self) -> None:
        project = self.create()
        baseline = project / site_tools.SCAFFOLD_MANIFEST_PATH
        baseline.unlink()
        self.assertEqual(site_tools.site_context(project)["update_status"]["state"], "unavailable")
        outside = self.root / "outside.json"
        outside.write_text("Author-owned bytes", encoding="utf-8")
        baseline.symlink_to(outside)
        self.assertEqual(site_tools.site_context(project)["update_status"]["state"], "unavailable")
        self.assertEqual(outside.read_text(), "Author-owned bytes")

    def test_cli_applies_only_the_explicitly_confirmed_reviewed_plan(self) -> None:
        project = self.create(version="0.3.0")
        before = files(project)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["--project", str(project), "mcp", "scaffold-sync"]), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(files(project), before)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["--project", str(project), "mcp", "scaffold-sync", "--apply", "--confirm-sync",
                                       "--expected-plan-sha256", plan["plan_sha256"]]), 0)
        self.assertTrue(json.loads(output.getvalue())["applied"])


if __name__ == "__main__":
    unittest.main()
