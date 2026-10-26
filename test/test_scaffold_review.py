import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from unaltraweb_mcp import cli, scaffold_review, site_tools
import test_consumer_updates as helpers


class ScaffoldReviewTests(unittest.TestCase):
    create = helpers.ConsumerUpdateTests.create

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def conflict(self, name="site"):
        replacements = site_tools._common_scaffold_replacements()
        replacements.update(GEM_VERSION="0.5.0", WHEEL_VERSION="0.5.0", MCP_IMAGE="ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.5.0",
                            CORE_SHA="1" * 40, SITE_DEPLOY_WORKFLOW_SHA="2" * 40)
        render = site_tools._render_scaffold_template
        def older(path, values):
            result = render(path, values)
            return result + b"\n/old-cache/\n" if path.name == ".gitignore.tmpl" else result
        with patch.object(site_tools, "_common_scaffold_replacements", return_value=replacements), \
                patch.object(site_tools, "_render_scaffold_template", side_effect=older):
            project = self.create(name, profile="unaltremanual")
        local = project / ".gitignore"
        local.write_bytes(local.read_bytes() + b"\n/dist/*\n!/dist/public/\n/.unaltracaptura-qgis/jobs/\n/.unaltracaptura-qgis/probes/\n/.unaltracaptura-qgis/render-locks/\n/.unaltracaptura-qgis/runtime/\n")
        for path in scaffold_review.PINS:
            target = project / path
            target.write_bytes(target.read_bytes() + b"\n  local-audit:\n    runs-on: ubuntu-latest\n    steps:\n      - run: test -f _config.yml\n")
        return project

    def review(self, plan, ignore="keep"):
        choices = {".gitignore": ignore, **{name: "pins-only" for name in scaffold_review.PINS}}
        rows = [{key: value for key, value in row.items() if key != "content"} | {"reason": "Preserve local rules and controls; update reviewed pins"}
                for row in plan["resolution_options"] if choices.get(row["path"]) == row["mode"]]
        return {"schema_version": 1, "kind": "unaltraweb-scaffold-review", "base_plan_sha256": plan["plan_sha256"], "files": rows}

    def test_real_conflicts_resolve_and_next_plan_reports_customization(self):
        project = self.conflict()
        before = helpers.files(project)
        initial = site_tools.scaffold_sync(project)
        self.assertEqual({row["path"] for row in initial["conflicts"]}, set(scaffold_review.MODES))
        review = self.review(initial)
        self.assertEqual(len(review["files"]), 3)
        resolved = site_tools.scaffold_sync(project, review=review)
        self.assertTrue(resolved["ok"], resolved)
        self.assertNotEqual(resolved["plan_sha256"], initial["plan_sha256"])
        self.assertEqual(helpers.files(project), before)
        result = site_tools.scaffold_sync(project, review=review, dry_run=False, confirm_sync=True, expected_plan_sha256=resolved["plan_sha256"])
        self.assertTrue(result["applied"])
        self.assertEqual((project / ".gitignore").read_bytes(), before[".gitignore"])
        for path in scaffold_review.PINS:
            self.assertIn(b"local-audit:", (project / path).read_bytes())
        later = site_tools.scaffold_sync(project)
        self.assertTrue(later["ok"])
        self.assertFalse(later["manifest_update"])
        self.assertEqual(set(later["preserved"]), set(scaffold_review.MODES))
        self.assertEqual(site_tools.consumer_update_status(project)["state"], "current_customized")
        self.assertEqual(set(later["reviewed_resolutions"]), set(scaffold_review.MODES))
        self.assertEqual(later["target"]["core_gem_version"], later["current_versions"]["gem_version"])

    def test_prepend_preserves_real_git_ignore_priority_and_negations(self):
        project = self.conflict()
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        candidates = ["dist/public/keep.txt", "dist/private/file.txt", ".unaltracaptura-qgis/jobs/job.json"]
        def ignored(path):
            return subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", path], cwd=project).returncode == 0
        before = {name: ignored(name) for name in candidates}
        original = (project / ".gitignore").read_bytes()
        initial = site_tools.scaffold_sync(project)
        review = self.review(initial, "prepend-package")
        resolved = site_tools.scaffold_sync(project, review=review)
        site_tools.scaffold_sync(project, review=review, dry_run=False, confirm_sync=True, expected_plan_sha256=resolved["plan_sha256"])
        self.assertTrue((project / ".gitignore").read_bytes().endswith(original))
        self.assertEqual({name: ignored(name) for name in candidates}, before)
        self.assertFalse(before["dist/public/keep.txt"])

    def test_review_and_resolved_plan_reject_all_changed_inputs(self):
        for mutation in ("local", "baseline", "config", "payload", "result", "reason"):
            with self.subTest(mutation=mutation):
                project = self.conflict(mutation)
                initial = site_tools.scaffold_sync(project)
                review = self.review(initial)
                resolved = site_tools.scaffold_sync(project, review=review)
                payloads = site_tools._managed_scaffold_payloads(project)
                if mutation == "payload":
                    payloads[Path(".gitignore")] += b"\n/new-output/\n"
                elif mutation in {"local", "baseline", "config"}:
                    target = {"local": ".gitignore", "baseline": ".unaltraweb/scaffold.json", "config": "_config.yml"}[mutation]
                    with (project / target).open("ab") as stream:
                        stream.write(b"\n" if mutation == "baseline" else b"\n# changed\n")
                elif mutation == "result":
                    review["files"][0]["result_sha256"] = "0" * 64
                else:
                    review["files"][0]["reason"] = "New decision after review"
                before = helpers.files(project)
                with patch.object(site_tools, "_managed_scaffold_payloads", return_value=payloads):
                    with self.assertRaises((ValueError, RuntimeError)):
                        site_tools.scaffold_sync(project, review=review, dry_run=False, confirm_sync=True, expected_plan_sha256=resolved["plan_sha256"])
                self.assertEqual(helpers.files(project), before)

    def test_review_requires_resolved_cas_and_cannot_cross_projects_or_paths(self):
        first, second = self.conflict("first"), self.conflict("second")
        review = self.review(site_tools.scaffold_sync(first))
        with self.assertRaisesRegex(RuntimeError, "expected_plan"):
            site_tools.scaffold_sync(first, review=review, dry_run=False, confirm_sync=True)
        with self.assertRaisesRegex(ValueError, "stale"):
            site_tools.scaffold_sync(second, review=review)
        for path in ("../outside", "_config.yml", ".unaltraweb/scaffold.json"):
            bad = copy.deepcopy(review)
            bad["files"][0]["path"] = path
            with self.assertRaises(ValueError):
                site_tools.scaffold_sync(first, review=bad)
        bad = copy.deepcopy(review)
        bad["files"][0]["content"] = "arbitrary replacement"
        with self.assertRaises(ValueError):
            site_tools.scaffold_sync(first, review=bad)

    def test_required_workflow_controls_cannot_be_discarded(self):
        project = self.conflict()
        path = project / ".github/workflows/deploy.yml"
        path.write_text(path.read_text().replace("    needs: validate\n", ""))
        plan = site_tools.scaffold_sync(project)
        self.assertNotIn(".github/workflows/deploy.yml", {row["path"] for row in plan["resolution_options"]})
        review = self.review(plan)
        self.assertFalse(site_tools.scaffold_sync(project, review=review)["ok"])

    def test_required_job_cannot_be_disabled_by_an_extra_condition(self):
        project = self.conflict()
        path = project / ".github/workflows/source-checks.yml"
        path.write_text(path.read_text().replace("  public-sources:\n", "  public-sources:\n    if: false\n"))
        plan = site_tools.scaffold_sync(project)
        self.assertNotIn(".github/workflows/source-checks.yml", {row["path"] for row in plan["resolution_options"]})

    def test_rollback_uses_existing_transaction_for_resolved_bytes(self):
        project = self.conflict()
        review = self.review(site_tools.scaffold_sync(project), "prepend-package")
        resolved = site_tools.scaffold_sync(project, review=review)
        before = helpers.files(project)
        with patch.object(site_tools, "_recheck_scaffold_sync_before_manifest", side_effect=RuntimeError("injected precommit failure")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                site_tools.scaffold_sync(project, review=review, dry_run=False, confirm_sync=True, expected_plan_sha256=resolved["plan_sha256"])
        self.assertEqual(helpers.files(project), before)

    def test_symlink_conflict_has_no_resolution_and_changes_nothing(self):
        project = self.conflict()
        outside = self.root / "outside"
        outside.write_text("original external bytes")
        (project / ".gitignore").unlink()
        (project / ".gitignore").symlink_to(outside)
        plan = site_tools.scaffold_sync(project)
        self.assertNotIn(".gitignore", {row["path"] for row in plan["resolution_options"]})
        self.assertFalse(site_tools.scaffold_sync(project, review=self.review(plan))["ok"])
        self.assertEqual(outside.read_text(), "original external bytes")

    def test_concurrent_author_edit_is_preserved_with_recovery_backup(self):
        project = self.conflict()
        review = self.review(site_tools.scaffold_sync(project), "prepend-package")
        resolved = site_tools.scaffold_sync(project, review=review)
        original_manifest = (project / site_tools.SCAFFOLD_MANIFEST_PATH).read_bytes()
        original_ignore = (project / ".gitignore").read_bytes()
        before_manifest = site_tools._recheck_scaffold_sync_before_manifest
        def race(root_fd, plan):
            (project / ".gitignore").write_bytes(b"# concurrent author edit\n")
            before_manifest(root_fd, plan)
        with patch.object(site_tools, "_recheck_scaffold_sync_before_manifest", side_effect=race):
            with self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
                site_tools.scaffold_sync(project, review=review, dry_run=False, confirm_sync=True, expected_plan_sha256=resolved["plan_sha256"])
        self.assertEqual((project / ".gitignore").read_bytes(), b"# concurrent author edit\n")
        self.assertEqual((project / site_tools.SCAFFOLD_MANIFEST_PATH).read_bytes(), original_manifest)
        backups = list(project.glob(".unaltraweb-scaffold-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original_ignore)

    def test_public_cli_accepts_the_same_reviewed_transaction(self):
        project = self.conflict()
        review = self.review(site_tools.scaffold_sync(project))
        args = ["--project", str(project), "mcp", "scaffold-sync", "--review-json", json.dumps(review)]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(args), 0)
        resolved = json.loads(output.getvalue())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(args + ["--apply", "--confirm-sync", "--expected-plan-sha256", resolved["plan_sha256"]]), 0)
        self.assertTrue(json.loads(output.getvalue())["applied"])
