from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PreparedLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "consumer"
        self.project.mkdir()
        (self.project / "author.txt").write_text("preserve")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        script = self.bin / "docker"
        script.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as stream: stream.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    if os.environ.get("MISSING") == "1" and not Path(os.environ["PREPARED"]).exists():
        print("No such image", file=sys.stderr); sys.exit(1)
    print("sha256:" + "1" * 64)
elif args[0] == "pull":
    Path(os.environ["PREPARED"]).touch()
elif args[:2] == ["container", "inspect"]:
    print("foreign|preview|" + os.environ.get("PROJECT_ID", ""))
elif args[:2] == ["ps", "-aq"] and os.environ.get("FOREIGN") == "1":
    print("a" * 64)
''')
        script.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.bin) + ":" + os.environ["PATH"],
                    "CALLS": str(self.log), "PREPARED": str(self.root / "prepared"),
                    "UNALTRAWEB_JOB_STORAGE_STATE": str(self.root / "registry"),
                    "UNALTRAWEB_JOB_STORAGE_HOST_STATE": str(self.root / "registry")}
        for key in ("UNALTRAWEB_EXPECTED_IMAGE_ID", "UNALTRAWEB_DOCKER_ROOT", "UNALTRAWEB_MANAGED_RUNTIME", "MCP_CONSUMER_WORKSPACE", "MCP_PROJECT_ID"):
            self.env.pop(key, None)

    def run_launcher(self, *args, **env):
        return subprocess.run(["/bin/sh", str(ROOT / "scripts/unaltraweb-mcp-bootstrap.sh"),
            "--project", str(self.project), "--host-project", str(self.project), *args],
            env={**self.env, **env}, capture_output=True, text=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_missing_ordinary_launch_never_prepares(self):
        result = self.run_launcher("--image", "missing:explicit", "--expected-image-id", "sha256:" + "1" * 64, MISSING="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not prepared", result.stderr)
        self.assertTrue(all(call[:2] == ["image", "inspect"] for call in self.calls()))
        self.assertEqual((self.project / "author.txt").read_text(), "preserve")
        self.assertEqual(len(list(self.project.iterdir())), 1)

    def test_wrong_explicit_identity_is_not_a_fallback_request(self):
        result = self.run_launcher("--image", "retained:alias", "--expected-image-id", "sha256:" + "2" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)
        self.assertFalse(any(call[0] in {"run", "pull", "build", "tag"} for call in self.calls()))

    def test_managed_mutable_selection_needs_expected_identity(self):
        result = self.run_launcher("--image", "unverified:alias", "--managed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("require --expected", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_only_explicit_preparation_may_pull(self):
        result = self.run_launcher("--image", "prepared:release", "--prepare", MISSING="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sha256:" + "1" * 64)
        self.assertEqual([c[0] for c in self.calls()], ["image", "pull", "image"])

    def test_launch_uses_pull_never_exact_image_and_session_ownership(self):
        result = self.run_launcher("--image", "sha256:" + "1" * 64, "--session-id", "a" * 32, "--offline")
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = next(c for c in self.calls() if c[0] == "run")
        self.assertEqual(launch[launch.index("--pull") + 1], "never")
        self.assertEqual(launch[launch.index("--network") + 1], "none")
        self.assertIn("io.context.mcp-session=" + "a" * 32, launch)
        self.assertIn("UNALTRAWEB_MANAGED_RUNTIME=1", launch)
        self.assertIn("sha256:" + "1" * 64, launch)
        self.assertIn("UNALTRAWEB_JOB_STORAGE_STATE=/var/lib/unaltraweb-job-storage", launch)
        self.assertEqual((self.root / "registry").stat().st_mode & 0o777, 0o700)

    def test_storage_registry_inside_consumer_or_symlink_is_refused(self):
        for path in (self.project / "registry", self.root / "linked-registry"):
            if path.name == "linked-registry":
                path.symlink_to(self.project, target_is_directory=True)
            result = self.run_launcher("--image", "sha256:" + "1"*64, "--storage-state", str(path))
            self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(any(call[0] == "run" for call in self.calls()))

    def test_workspace_cleanup_refuses_foreign_inspected_ownership(self):
        result = subprocess.run(["/bin/sh", str(ROOT / "scripts/unaltraweb-mcp-cleanup.sh"), "--project", str(self.project)],
            env={**self.env, "FOREIGN": "1"}, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown container ownership", result.stderr)
        self.assertFalse(any(c[0] == "rm" for c in self.calls()))

    def test_unrelated_inherited_daemon_mapping_is_not_selected(self):
        result = subprocess.run(["/bin/sh", str(ROOT / "scripts/unaltraweb-mcp-bootstrap.sh"), "--project", str(self.project),
            "--image", "sha256:" + "1" * 64], env={**self.env, "UNALTRAWEB_DOCKER_ROOT": "/foreign"},
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another or unknown workspace", result.stderr)
        self.assertFalse(any(c[0] == "run" for c in self.calls()))
