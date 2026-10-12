from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from unaltraweb_mcp import source_checks as ci, site_tools
from unaltraweb_mcp.artifact_handoff_v1 import HandoffError
from scripts.validate_workflows import load_workflow_text


def blob(value="a"):
    return {"mode": "100644", "kind": "blob", "object": value*40}


class SourcePolicyTests(unittest.TestCase):
    def test_policy_is_strict_data_with_no_executable_fields_or_escaped_roots(self):
        valid = ci.default_policy("unaltremanual")
        self.assertEqual(ci.policy(json.dumps(valid).encode()), valid)
        for mutation in ({"commands": ["run-private-model"]}, {"data_roots": ["../outside"]},
                         {"public_roots": [".git"]}, {"practice_roots": ["practiques", "practiques"]},
                         {"allow_empty_public_sources": 1}, {"allow_empty_public_sources": True}):
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, HandoffError)):
                ci.policy(json.dumps({**valid, **mutation}).encode())
        with self.assertRaises(HandoffError):
            ci.policy(b'{"schema_version":1,"schema_version":1}')

    def test_unchanged_legacy_is_preserved_but_new_or_changed_data_is_refused(self):
        policy = ci.effective_policy(ci.default_policy("unaltremanual"))
        base = {"_practices/old/map.pdf": blob(), "_practices/old/data.gpkg": blob("b")}
        head = {**base, "_practices/new/data.gpkg": blob("c"), "practiques/new/result.zip": blob("d"),
                "sandbox/model/output.json": blob("e"), "_practices/old/data.gpkg": blob("f"),
                "practiques/new/alias.json": {**blob("2"), "mode": "120000"}}
        for name in ("README.md", "edition.json", "recipe.yml", "analysis.py", "route.model3", "style.qml"):
            head["practiques/new/"+name] = blob("1")
        result = ci.conservation_inventory(base, head, policy)
        self.assertEqual([row["path"] for row in result["legacy_unchanged"]], ["_practices/old/map.pdf"])
        self.assertEqual({row["path"] for row in result["violations"]}, {
            "_practices/new/data.gpkg", "practiques/new/result.zip", "sandbox/model/output.json", "_practices/old/data.gpkg", "practiques/new/alias.json"})
        self.assertEqual(ci.conservation_inventory(base, {}, policy)["state"], "pass")

    def test_policy_change_cannot_hide_same_pr_data_or_drop_coverage_requirement(self):
        baseline = ci.default_policy("unaltremanual")
        baseline["data_roots"].append("activity-inputs")
        current = {**ci.default_policy("unaltremanual"), "public_roots": [],
                   "allow_empty_public_sources": True, "empty_reason": "Planned transition"}
        selected = ci.effective_policy(current, baseline)
        self.assertIn("activity-inputs", selected["data_roots"])
        self.assertIn("_chapters", selected["public_roots"])
        self.assertFalse(selected["allow_empty_public_sources"])
        result = ci.conservation_inventory({}, {"activity-inputs/table.json": blob()}, selected)
        self.assertEqual(result["state"], "fail")


class SourceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.policy = ci.default_policy("unaltremanual")
        self.head = {"_config.yml": blob(), "_chapters/en/one.md": blob(), "_chapters/en/draft.md": blob()}
        self.profile = {"profile": "unaltremanual", "manual_source_quality": {"figure_typography": {
            "references": [{"source": "private-map.svg", "state": "unverified"}]}}}
        self.prose = {"sources": ["_config.yml", "_chapters/en/one.md"], "coverage": {
            "skipped": [{"path": "_chapters/en/draft.md", "reason": "not published in this profile"}], "unsupported_languages": []}}

    def test_real_coverage_keeps_exclusions_and_unverified_figures_explicit(self):
        result = ci.coverage(self.head, self.policy, self.profile, self.prose)
        self.assertEqual(result["covered"], ["_chapters/en/one.md"])
        self.assertEqual(result["excluded"], self.prose["coverage"]["skipped"])
        self.assertEqual(len(result["figures_unverified"]), 1)
        self.assertEqual(result["state"], "checked_with_limits")

    def test_config_only_or_unreported_missing_source_is_not_a_pass(self):
        for prose in ({"sources": ["_config.yml"], "coverage": {"skipped": []}},
                      {**self.prose, "coverage": {"skipped": []}}):
            with self.subTest(prose=prose):
                self.assertEqual(ci.coverage(self.head, self.policy, self.profile, prose)["state"], "fail")
        empty = ci.coverage({"_config.yml": blob()}, self.policy, self.profile, {"sources": ["_config.yml"]})
        self.assertTrue(any("unexpectedly empty" in issue for issue in empty["issues"]))

    def test_explicit_empty_scope_is_declared_not_checked(self):
        selected = {**self.policy, "allow_empty_public_sources": True, "empty_reason": "Public material not authored yet"}
        result = ci.coverage({"_config.yml": blob()}, selected, self.profile, {"sources": ["_config.yml"]})
        self.assertEqual(result["state"], "empty_declared")
        self.assertEqual(result["covered"], [])

    def test_wrong_profile_untracked_sources_and_unknown_language_are_reported(self):
        result = ci.coverage(self.head, self.policy, {"profile": "unaltreselfie"}, self.prose)
        self.assertEqual(result["state"], "fail")
        prose = copy.deepcopy(self.prose)
        prose["sources"].append("_pages/untracked.md")
        self.assertEqual(ci.coverage(self.head, self.policy, self.profile, prose)["untracked_checker_sources"], ["_pages/untracked.md"])
        prose = copy.deepcopy(self.prose)
        prose["coverage"]["unsupported_languages"] = ["xx"]
        self.assertEqual(ci.coverage(self.head, self.policy, self.profile, prose)["unsupported_languages"], ["xx"])


class SourceRunnerTests(unittest.TestCase):
    def test_checker_is_readonly_networkless_and_never_receives_a_docker_socket(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, reports = root/"project", root/"reports"
            project.mkdir()
            reports.mkdir()
            def run(arguments, selected_project, **kwargs):
                self.assertEqual(selected_project, project)
                self.assertEqual(arguments[-2:], ["mcp", "profile-check"])
                self.assertIn("-I", arguments)
                self.assertIn("unaltraweb_mcp.cli", arguments)
                self.assertIn("--read-only", arguments)
                self.assertEqual(arguments[arguments.index("--network")+1], "none")
                self.assertEqual(arguments[arguments.index("--pull")+1], "never")
                mounts = [arguments[i+1] for i, value in enumerate(arguments) if value == "--mount"]
                self.assertEqual(len(mounts), 1)
                self.assertIn("readonly", mounts[0])
                self.assertFalse(any("docker.sock" in value for value in arguments))
                Path(arguments[arguments.index("--cidfile")+1]).write_text("a"*64)
                return SimpleNamespace(returncode=0, timed_out=False, stdout_truncated=False, stderr_truncated=False,
                                       stdout='{"ok":false,"issues":["fixture failure"]}', stderr="")
            with patch.object(ci, "command", side_effect=run), patch.object(ci, "session_status", return_value={"resources_released": True}):
                result = ci.checker(project, reports, ci.CHECKER_IMAGE, "profile-check")
            self.assertEqual(result["state"], "fail", "Exit zero cannot mask a checker ok:false result")

    def test_git_policy_and_reports_do_not_execute_project_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, reports = root/"project", root/"reports"
            project.mkdir()
            (project/"policy.py").write_text("raise RuntimeError('project code must never execute')")
            entries = {ci.POLICY_PATH: blob("b"), "_config.yml": blob(), "_chapters/en/one.md": blob()}
            raw_policy = json.dumps(ci.default_policy("unaltremanual"))
            def git(selected, *args):
                self.assertEqual(selected, project)
                if args == ("rev-parse", "--show-toplevel"):
                    return str(project)
                if args == ("rev-parse", "HEAD"):
                    return "c"*40
                if args[0] == "cat-file":
                    return raw_policy
                self.assertIn(args[0], {"merge-base", "diff"})
                return ""
            def checked(project, reports, image, name):
                if name == "profile-check":
                    value = {"ok": True, "profile": "unaltremanual"}
                elif name == "prose-check":
                    value = {"ok": True, "sources": ["_config.yml", "_chapters/en/one.md"], "coverage": {"skipped": []}}
                else:
                    value = {"content_count": 1, "status_field": "content_status", "status_counts": {"draft": 1}, "records_sample": []}
                return {"state": "observed" if name == "content-approval-inventory" else "pass", "report": value}
            with patch.object(ci, "git", side_effect=git), patch.object(ci, "tree", return_value=entries), \
                    patch.object(ci, "verify_tree_files"), patch.object(ci, "checker", side_effect=checked):
                result = ci.check(project, "a"*40, reports)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["drafts"]["status_counts"], {"draft": 1})
            self.assertTrue(result["drafts"]["sample_is_partial"])
            self.assertTrue(all(row["state"] == "not_run" for row in result["not_run"].values()))
            self.assertTrue((reports/"summary.json").is_file())
            self.assertEqual(list(project.iterdir()), [project/"policy.py"])
            with self.assertRaises(ValueError):
                ci.check(project, "a"*40, project/"reports")

    def test_bad_baseline_fails_with_not_run_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/"project"
            project.mkdir()
            with patch.object(ci, "checker") as checker:
                result = ci.check(project, "HEAD~1", root/"reports")
            self.assertFalse(result["ok"])
            self.assertEqual(result["coverage"]["state"], "not_run")
            checker.assert_not_called()

    def test_dirty_or_symlinked_checked_sources_fail_without_git_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root/"source.md"
            raw = b"Public source\n"
            path.write_bytes(raw)
            entries = {"source.md": {**blob(), "object": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}}
            with patch.object(ci, "git", side_effect=AssertionError("No Git filters or project code")):
                ci.verify_tree_files(root, entries, ["source.md"])
                path.write_bytes(raw + b"Modified\n")
                with self.assertRaisesRegex(ValueError, "Git snapshot"):
                    ci.verify_tree_files(root, entries, ["source.md"])
                path.unlink()
                path.symlink_to(root/"outside.md")
                with self.assertRaises((OSError, HandoffError)):
                    ci.verify_tree_files(root, entries, ["source.md"])


class SourceScaffoldTests(unittest.TestCase):
    def test_common_control_is_identical_and_policy_is_site_owned_for_all_profiles(self):
        controls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile in ("unaltremanual", "unaltremanual", "unaltremanual", "unaltreselfie", "unaltreprojecte", "unaltredocs"):
                project = root/str(len(controls))
                site_tools.new_web(project, site_profile_value=profile, title=f"Fixture {len(controls)}")
                path = project/".github/workflows/source-checks.yml"
                controls.append(path.read_bytes())
                manifest = json.loads((project/site_tools.SCAFFOLD_MANIFEST_PATH).read_bytes())
                self.assertIn(".github/workflows/source-checks.yml", manifest["files"])
                self.assertNotIn(ci.POLICY_PATH, manifest["files"])
                self.assertEqual(ci.policy((project/ci.POLICY_PATH).read_bytes())["profile"], profile)
                self.assertFalse(list(project.rglob("source-checks.yml.tmpl")))
            self.assertEqual(len(set(controls)), 1)
            workflow = load_workflow_text(controls[0].decode())
            self.assertIn("pull_request", workflow["on"])
            self.assertNotIn("pull_request_target", workflow["on"])
            self.assertEqual(workflow["permissions"], {"contents": "read"})
            steps = workflow["jobs"]["public-sources"]["steps"]
            self.assertFalse(any("secrets." in str(step) or "deploy-pages" in str(step) for step in steps))
            self.assertFalse(any("uses" in job for job in workflow["jobs"].values()))
            for step in steps:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^actions/(checkout|setup-python|upload-artifact)@[0-9a-f]{40}$")
            checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
            self.assertIs(checkout["with"]["persist-credentials"], False)
            self.assertIn("python", str(steps))
            self.assertIn("-I -m unaltraweb_mcp.source_checks", controls[0].decode())
            self.assertIn(ci.CHECKER_IMAGE, controls[0].decode())

    def test_custom_policy_is_preserved_and_custom_control_conflicts_on_upstream_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)/"site"
            site_tools.new_web(project, site_profile_value="unaltremanual")
            policy_path = project/ci.POLICY_PATH
            authored = ci.default_policy("unaltremanual")
            authored["data_roots"].append("activity-data")
            policy_path.write_text(json.dumps(authored))
            control = project/".github/workflows/source-checks.yml"
            control.write_bytes(control.read_bytes() + b"\n# local customization\n")
            payloads = site_tools._managed_scaffold_payloads(project)
            payloads[Path(".github/workflows/source-checks.yml")] += b"\n# reviewed package update\n"
            with patch.object(site_tools, "_managed_scaffold_payloads", return_value=payloads):
                result = site_tools.scaffold_sync(project)
            self.assertFalse(result["ok"])
            self.assertIn(".github/workflows/source-checks.yml", {row["path"] for row in result["conflicts"]})
            self.assertEqual(json.loads(policy_path.read_text()), authored)
            self.assertTrue(control.read_bytes().endswith(b"# local customization\n"))
