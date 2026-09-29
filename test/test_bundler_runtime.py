from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp import bundler_runtime as bundles


class BundlerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "consumer"
        self.project.mkdir()
        self.core = Path(self.temp.name) / "core"
        for name in ("unaltraweb.gemspec", "lib/unaltraweb/version.rb", "src/unaltraweb_mcp/component-contract.json"):
            path = self.core / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("core\n")
        self.runtime = "0.4"
        self.resolutions = []
        self.checker = patch.object(bundles, "checked", side_effect=self.checked)
        self.checker.start()
        self.addCleanup(self.checker.stop)

    def checked(self, command, *, cwd, env):
        if command[0] == "ruby":
            return json.dumps({"runtime": self.runtime})
        if command == ["bundle", "lock", "--local"]:
            self.resolutions.append(self.runtime)
            Path(env["BUNDLE_GEMFILE"] + ".lock").write_text(f"resolved-for-{self.runtime}\n")
        else:
            self.assertEqual(command, ["bundle", "check"])
        return ""

    def test_populated_runtime_roundtrip_preserves_legacy_and_author_locks(self):
        (self.project / "tmp").mkdir()
        paths = [self.project / name for name in ("Gemfile", "Gemfile.lock", "tmp/Gemfile.local", "tmp/Gemfile.local.lock")]
        for path in paths:
            path.write_text("author or retained legacy content\n")
        before = {path: path.read_bytes() for path in paths}
        first = bundles.prepare(self.project, self.core)
        self.runtime = "0.5"
        second = bundles.prepare(self.project, self.core)
        self.assertNotEqual(first, second)
        self.runtime = "0.4"
        self.assertEqual(bundles.prepare(self.project, self.core), first)
        self.assertEqual(self.resolutions, ["0.4", "0.5"])
        self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_modified_cache_lock_is_preserved_and_rejected(self):
        gemfile = bundles.prepare(self.project, self.core)
        lock = gemfile.with_name("Gemfile.lock")
        lock.write_text("author edited this generated cache\n")
        with self.assertRaisesRegex(RuntimeError, "was modified"):
            bundles.prepare(self.project, self.core)
        self.assertEqual(lock.read_text(), "author edited this generated cache\n")
        self.assertEqual(len(self.resolutions), 1)

    def test_symlink_cache_ancestor_never_receives_writes(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.project / "tmp").symlink_to(outside)
        with self.assertRaises(OSError):
            bundles.prepare(self.project, self.core)
        self.assertEqual(list(outside.iterdir()), [])

    def legacy_makefile(self):
        makefile = self.project / "Makefile"
        makefile.write_text("LOCAL_GEMFILE := tmp/Gemfile.local\nbuild-native:\n\t@true\n")
        baseline = self.project / ".unaltraweb/scaffold.json"
        baseline.parent.mkdir()
        baseline.write_text(json.dumps({"files": {"Makefile": bundles.digest(makefile.read_bytes())}}))

    def test_unchanged_legacy_makefile_gets_invocation_copy_not_retained_lock(self):
        self.legacy_makefile()
        args = bundles.legacy_make_args(self.project, self.core)
        relative = args[0].split("=", 1)[1]
        self.assertTrue(relative.startswith("tmp/unaltraweb-bundle/run-"))
        invocation = self.project / relative
        self.assertTrue(invocation.with_name("Gemfile.lock").is_file())
        invocation.with_name("Gemfile.lock").write_text("changed by historical make\n")
        self.assertNotEqual(args, bundles.legacy_make_args(self.project, self.core))
        self.assertEqual(self.resolutions, ["0.4"])

    def test_custom_makefile_is_not_overridden(self):
        self.legacy_makefile()
        with (self.project / "Makefile").open("a") as stream:
            stream.write("# Author customization\n")
        self.assertEqual(bundles.legacy_make_args(self.project, self.core), [])
        self.assertEqual(self.resolutions, [])

    def test_explicit_author_gemfile_uses_existing_frozen_lock(self):
        for name in ("custom.rb", "custom.rb.lock"):
            (self.project / name).write_text("preserve\n")
        with patch.object(bundles.os, "execvpe") as execute:
            self.assertEqual(bundles.main(["--project", str(self.project), "--core", str(self.core), "--gemfile", "custom.rb", "--", "bundle", "exec", "true"]), 0)
        self.assertEqual(execute.call_args.args[2]["BUNDLE_FROZEN"], "true")
        self.assertEqual(self.resolutions, [])
        self.assertEqual((self.project / "custom.rb.lock").read_text(), "preserve\n")

    def test_configuration_changes_select_new_cache_without_recording_secrets(self):
        first = bundles.prepare(self.project, self.core)
        with patch.dict(os.environ, {"BUNDLE_RUBYGEMS__ORG": "private-token"}):
            second = bundles.prepare(self.project, self.core)
        self.assertNotEqual(first, second)
        self.assertNotIn("private-token", second.with_name("receipt.json").read_text())

    def test_generated_execution_can_complete_checksums_only_in_private_copy(self):
        with patch.object(bundles.os, "execvpe") as execute:
            bundles.main(["--project", str(self.project), "--core", str(self.core), "--", "bundle", "exec", "true"])
        env = execute.call_args.args[2]
        private = Path(env["BUNDLE_GEMFILE"])
        self.assertTrue(private.parent.name.startswith("run-"))
        private.with_name("Gemfile.lock").write_text("checksums completed by Bundler\n")
        cached = bundles.prepare(self.project, self.core)
        self.assertEqual(cached.with_name("Gemfile.lock").read_text(), "resolved-for-0.4\n")
        self.assertNotIn("BUNDLE_LOCKFILE_CHECKSUMS", env)
