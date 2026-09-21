from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from unaltraweb_mcp import manual_pdf_preview, site_tools


FACTORY = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((FACTORY / "mcp-factory.yml").read_text(encoding="utf-8"))
POLICIES = {item["path"]: item for item in MANIFEST["workspace_rule"]["path_policies"]}
PROFILES = tuple(site_tools.PROFILE_CONTRACTS)


def git(project: Path, *args: str) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", LC_ALL="C")
    return subprocess.run(
        ["git", "-C", str(project), *args], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout


def index_sources(project: Path) -> None:
    paths = [path for path, policy in POLICIES.items() if policy["git"] == "versioned" and (project / path).exists()]
    git(project, "add", "--", ".gitignore", *paths)


def initialize_git(project: Path) -> None:
    git(project, "init", "--quiet", "--initial-branch=policy-fixture")
    index_sources(project)
    git(project, "-c", "user.name=Policy Fixture", "-c", "user.email=policy@example.test",
        "commit", "--quiet", "-m", "Initialize policy fixture")


def snapshot(project: Path) -> dict:
    """Read state without refreshing the index; atime is deliberately excluded."""
    root_info = project.stat()
    state = {
        "root": {"mode": root_info.st_mode, "inode": root_info.st_ino, "mtime_ns": root_info.st_mtime_ns},
        "head": git(project, "rev-parse", "HEAD").decode(),
        "index": git(project, "ls-files", "--stage", "-z").decode(),
        "status": git(project, "status", "--porcelain=v1", "--untracked-files=all").decode(),
        "worktrees": git(project, "worktree", "list", "--porcelain", "-z").decode(),
        "paths": {},
    }
    # Includes .git/index bytes, refs, reflogs and every ignored/editorial path.
    for path in sorted(project.rglob("*")):
        info = path.lstat()
        record = {"mode": info.st_mode, "inode": info.st_ino, "mtime_ns": info.st_mtime_ns}
        if stat.S_ISREG(info.st_mode):
            record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif stat.S_ISLNK(info.st_mode):
            record["target"] = os.readlink(path)
        state["paths"][path.relative_to(project).as_posix()] = record
    return state


def preserved_files(project: Path) -> None:
    """Opaque sentinels, not forged valid receipts: workspace-check cannot parse/clean them."""
    paths = [
        "tmp/manual-release/v2026.09/reviewed-evidence.txt",
        ".cache/scimago/scimagojr.csv",
        ".cache/unaltraweb/manual-pdf-publication-intent.json",
        ".cache/unaltraweb/manual-pdf-publication.json",
        ".cache/unaltraweb/manual-pdf-preview.json",
        ".cache/unaltraweb/manual-pdf-preview.lock",
        ".cache/unaltraweb/manual-pdf-preview-recovery/author-edit.backup",
        ".unaltraweb/computations.lock.json",
        ".unaltraweb/receipts/diavisuals.json",
        ".unaltraweb/receipts/vegavisuals.json",
        "assets/figure.edited.svg",
        "assets/page.capture.png",
        "assets/page.capture.svg",
        "assets/page.capture.edited.svg",
    ]
    for relative in paths:
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"Preserve these exact bytes: {relative}\n".encode())


class WorkspacePolicyContractTests(unittest.TestCase):
    def test_manifest_is_literal_minimal_and_preserves_recovery_ownership(self) -> None:
        rule = MANIFEST["workspace_rule"]
        self.assertEqual(MANIFEST["schema_version"], 1)
        self.assertEqual((rule["binding"], rule["consumer_root"], rule["allowed_external_writes"]), ("consumer", ".", []))
        self.assertTrue(POLICIES)
        self.assertEqual(len(POLICIES), len(rule["path_policies"]))
        self.assertEqual(MANIFEST["transport"]["env"]["MCP_CONSUMER_WORKSPACE"], "${workspaceFolder}")
        for path, policy in POLICIES.items():
            with self.subTest(path=path):
                self.assertEqual(set(policy), {"path", "type", "role", "git", "cleanup"})
                self.assertFalse(Path(path).is_absolute())
                self.assertNotIn("..", Path(path).parts)
                self.assertFalse(re.search(r"[\x00-\x1f*?\[\]{}$]", path))
                self.assertIn(policy["type"], {"file", "directory"})
                self.assertIn(policy["git"], {"ignored", "versioned", "consumer"})
                self.assertIn(policy["cleanup"], {"disposable", "explicit", "never"})
                self.assertTrue(policy["role"])
        for path in (manual_pdf_preview.RECEIPT_PATH, manual_pdf_preview.PUBLICATION_INTENT_PATH,
                     manual_pdf_preview.PUBLICATION_RECEIPT_PATH, manual_pdf_preview.LOCK_PATH,
                     manual_pdf_preview.RECOVERY_PATH):
            self.assertEqual(POLICIES[path.as_posix()]["git"], "ignored")
            self.assertEqual(POLICIES[path.as_posix()]["cleanup"], "explicit")
        self.assertEqual(POLICIES["tmp"]["cleanup"], "explicit")
        self.assertEqual(POLICIES[".cache/scimago"]["cleanup"], "explicit")
        for path in ("assets", ".unaltraweb", ".cache", ".vegavisuals.yml", ".vegavisuals.lock.json",
                     ".unaltraweb/receipts/diavisuals.json", ".unaltraweb/receipts/vegavisuals.json"):
            self.assertNotIn(path, POLICIES)

    def test_all_official_scaffolds_cover_optional_paths_and_provider_caches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uw-policies-") as temporary:
            for profile in PROFILES:
                with self.subTest(profile=profile):
                    project = Path(temporary) / profile
                    self.assertTrue(site_tools.new_web(project, site_profile_value=profile)["ok"])
                    initialize_git(project)
                    for path, policy in POLICIES.items():
                        if policy["git"] == "ignored":
                            argument = path + ("/" if policy["type"] == "directory" else "")
                            git(project, "check-ignore", "--quiet", "--no-index", "--", argument)
                            self.assertEqual(git(project, "ls-files", "--", path), b"")
                    for path in (".cache/diavisuals/", ".cache/vegavisuals/"):
                        git(project, "check-ignore", "--quiet", "--no-index", "--", path)
                    self.assertEqual((project / ".unaltraweb/computations.yml").exists(), profile == "unaltremanual")
                    self.assertFalse((project / ".vegavisuals.yml").exists())
                    before = snapshot(project)
                    planned = site_tools.scaffold_sync(project)
                    self.assertTrue(planned["ok"], planned)
                    self.assertFalse(planned["manifest_update"])
                    self.assertEqual(planned["creates"] + planned["updates"], [])
                    self.assertEqual(snapshot(project), before)

    def test_sync_preserves_customizations_recovery_and_a_new_managed_collision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uw-sync-policy-") as temporary:
            project = Path(temporary)
            site_tools.new_web(project, site_profile_value="unaltremanual")
            initialize_git(project)
            with (project / ".gitignore").open("a") as stream:
                stream.write("\n/private-notes/\n")
            with (project / "Makefile").open("a") as stream:
                stream.write("\n# consumer customization\n")
            (project / "_pages/en/index.md").write_text("Author-owned prose.\n", encoding="utf-8")
            preserved_files(project)
            collision = Path(".unaltraweb/new-control.txt")
            (project / collision).write_text("Unmanaged local artefact\n", encoding="utf-8")
            proposed = site_tools._managed_scaffold_payloads(project)
            proposed[collision] = b"New package control\n"
            before = snapshot(project)
            # Model a later package adding a managed path to an existing baseline.
            with patch.object(site_tools, "SCAFFOLD_MANAGED_PATHS", [*site_tools.SCAFFOLD_MANAGED_PATHS, collision]), patch.object(
                site_tools, "_managed_scaffold_payloads", return_value=proposed,
            ):
                for options in ({}, {"dry_run": False, "confirm_sync": True}):
                    result = site_tools.scaffold_sync(project, **options)
                    self.assertFalse(result["ok"])
                    self.assertFalse(result["applied"])
                    self.assertEqual({item["path"] for item in result["conflicts"]}, {".gitignore", "Makefile", str(collision)})
                    self.assertEqual(snapshot(project), before)


@unittest.skipUnless(os.environ.get("UNALTRAWEB_FACTORY_MANAGER") and os.environ.get("UNALTRAWEB_FACTORIES_DIR"),
                     "set explicit central manager and discovery paths for integration tests")
class CentralWorkspacePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manager_path = Path(os.environ["UNALTRAWEB_FACTORY_MANAGER"])
        # Load the real manager without creating __pycache__ in its read-only checkout.
        cls.manager = types.ModuleType("uw_policy_manager_test")
        cls.manager.__file__ = str(manager_path)
        exec(compile(manager_path.read_bytes(), str(manager_path), "exec"), cls.manager.__dict__)
        cls.discovery = Path(os.environ["UNALTRAWEB_FACTORIES_DIR"]).resolve()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="uw-central-policy-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        site_tools.new_web(self.project, site_profile_value="unaltremanual")
        initialize_git(self.project)

    def check_workspace(self, expected_code: int = 0, project: Path | None = None) -> dict:
        project = project or self.project
        before = snapshot(project)
        output = io.StringIO()
        executed = []
        original_popen = subprocess.Popen

        def read_only_git(argv, *args, **kwargs):
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(argv[:3], ["git", "-C", str(project)])
            remainder = argv[3:]
            command = remainder[1] if remainder[0] == "--literal-pathspecs" else remainder[0]
            self.assertIn(command, {"rev-parse", "check-ignore", "ls-files"})
            self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")
            executed.append(command)
            return original_popen(argv, *args, **kwargs)

        with contextlib.redirect_stdout(output), patch.object(
            self.manager, "run_factory_command", side_effect=AssertionError("provider command executed"),
        ), patch.object(subprocess, "Popen", side_effect=read_only_git):
            code = self.manager.main([
                "workspace-check", "--dir", str(self.discovery), "--factory", "unaltraweb",
                "--workspace", str(project), "--json",
            ])
        result = json.loads(output.getvalue())
        self.assertEqual(snapshot(project), before, "workspace-check mutated the live fixture")
        self.assertEqual(code, expected_code, result)
        self.assertEqual(result["summary"]["factory_count"], 3)
        self.assertEqual(result["summary"]["dependency_factory_count"], 2)
        self.assertEqual([item["factory"] for item in result["results"]], ["diavisuals", "vegavisuals", "unaltraweb"])
        for item in result["results"]:
            self.assertEqual((item["binding"], item["resolved_root"]), ("consumer", str(project)))
        self.assertTrue(executed)
        return result

    @staticmethod
    def observation(result: dict, path: str) -> dict:
        return next(item for item in result["resolved_paths"] if item["factory"] == "unaltraweb" and item["declared_path"] == path)

    def test_closure_and_absent_optional_paths_in_every_profile(self) -> None:
        for profile in PROFILES:
            with self.subTest(profile=profile):
                project = self.project / profile
                site_tools.new_web(project, site_profile_value=profile)
                initialize_git(project)
                result = self.check_workspace(project=project)
                self.assertEqual(self.observation(result, ".unaltraweb/computations.yml")["exists"], profile == "unaltremanual")

    def test_direct_inherited_and_absent_directory_ignore_rules(self) -> None:
        result = self.check_workspace()
        self.assertEqual(self.observation(result, "_site")["ignore_match"]["pattern"], "_site/")
        self.assertFalse(self.observation(result, "_site")["exists"])
        self.assertEqual(self.observation(result, ".cache/scimago")["ignore_match"]["pattern"], ".cache/")
        self.assertFalse(self.observation(result, ".cache/scimago")["exists"])
        (self.project / "_site").mkdir()
        (self.project / "_site/index.html").write_text("Build output", encoding="utf-8")
        self.check_workspace()

    def test_ignored_path_rejects_indexed_descendants(self) -> None:
        (self.project / "_site").mkdir()
        (self.project / "_site/index.html").write_text("Tracked by mistake", encoding="utf-8")
        git(self.project, "add", "-f", "--", "_site/index.html")
        result = self.check_workspace(1)
        self.assertIn("ignored-path-versioned", self.observation(result, "_site")["finding_codes"])

    def test_missing_ignore_coverage_is_a_finding_even_when_absent(self) -> None:
        path = self.project / ".gitignore"
        path.write_text(path.read_text().replace("_site/\n", ""), encoding="utf-8")
        result = self.check_workspace(1)
        self.assertIn("path-not-ignored", self.observation(result, "_site")["finding_codes"])

    def test_versioned_paths_present_absent_untracked_and_ignored(self) -> None:
        for path, policy in POLICIES.items():
            if policy["git"] != "versioned":
                continue
            with self.subTest(path=path):
                target = self.project / path
                original = target.read_bytes()
                self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "versioned")
                git(self.project, "rm", "--cached", "--", path)
                result = self.check_workspace(1)
                self.assertIn("versioned-path-untracked", self.observation(result, path)["finding_codes"])
                target.unlink()
                self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "absent")
                target.write_bytes(original)
                git(self.project, "add", "--", path)
        with (self.project / ".gitignore").open("a") as stream:
            stream.write("\n/_config.yml\n")
        result = self.check_workspace(1)
        self.assertIn("versioned-path-ignored", self.observation(result, "_config.yml")["finding_codes"])

    def test_consumer_policy_is_informative_for_every_git_state(self) -> None:
        path = ".unaltraweb/computations.lock.json"
        target = self.project / path
        self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "absent")
        target.write_text("{}\n", encoding="utf-8")
        self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "untracked")
        git(self.project, "add", "--", path)
        self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "versioned")
        git(self.project, "rm", "--cached", "--", path)
        with (self.project / ".gitignore").open("a") as stream:
            stream.write(f"\n/{path}\n")
        self.assertEqual(self.observation(self.check_workspace(), path)["git_state"], "ignored")

    def test_recovery_receipts_and_edited_outputs_survive_read_only_check(self) -> None:
        preserved_files(self.project)
        result = self.check_workspace()
        self.assertTrue(self.observation(result, str(manual_pdf_preview.RECOVERY_PATH))["exists"])
        self.assertEqual(self.observation(result, str(manual_pdf_preview.RECOVERY_PATH))["cleanup"], "explicit")


if __name__ == "__main__":
    unittest.main()
