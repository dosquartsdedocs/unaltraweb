from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DistributedLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launcher = self.root / "installed profile"
        (self.launcher / "scripts").mkdir(parents=True)
        for name in ("bootstrap", "cleanup", "project-id"):
            shutil.copyfile(ROOT / f"scripts/unaltraweb-mcp-{name}.sh", self.launcher / f"scripts/unaltraweb-mcp-{name}.sh")
        shutil.copyfile(ROOT / "scripts/unaltraweb-docker-mount.sh", self.launcher / "scripts/unaltraweb-docker-mount.sh")
        shutil.copyfile(ROOT / "packaging/launcher/Makefile", self.launcher / "Makefile")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "docker.jsonl"
        docker = self.bin / "docker"
        docker.write_text(
            "#!/usr/bin/env python3\nimport json,os,sys\n"
            "with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "if sys.argv[1:3] == ['image','inspect']:\n"
            "    if os.environ.get('MISSING') == '1': sys.exit(1)\n"
            "    if '{{.Id}}' in sys.argv: print('sha256:'+'a'*64)\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        self.env = {key: value for key, value in os.environ.items() if key not in {
            "MCP_CONSUMER_WORKSPACE", "MCP_PROJECT_ID", "UNALTRAWEB_PROJECT", "MCP_RELEASE_IMAGE", "UNALTRAWEB_MCP_IMAGE",
        }}
        self.env.update(PATH=f"{self.bin}:{self.env['PATH']}", CALLS=str(self.log), UNALTRAWEB_DOCKER_SOCKET="/absent-test-socket")

    def run_make(self, target: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["make", "--silent", "--no-print-directory", "-C", str(self.launcher), target, *args],
                              env=self.env, capture_output=True, text=True, check=False)

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_native_preparation_matches_source_post_release_selection(self) -> None:
        result = self.run_make("mcp-build")
        self.assertEqual(result.returncode, 0, result.stderr)
        # A newly recorded candidate receipt must not advance launchers before
        # the explicit post-release selection change.
        selected = next(line.split(" ?= ", 1)[1] for line in (ROOT / "Makefile").read_text().splitlines()
                        if line.startswith("MCP_RELEASE_IMAGE ?= "))
        self.assertEqual(self.calls(), [["image", "inspect", "--format", "{{.Id}}", selected]])
        self.assertIn(selected, (ROOT / "scripts/unaltraweb-mcp-bootstrap.sh").read_text())

    def test_check_requires_preparation_without_build_or_pull(self) -> None:
        self.env["MISSING"] = "1"
        result = self.run_make("mcp-check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Run --prepare first", result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_check_and_smoke_run_local_id_without_consumer_or_socket(self) -> None:
        for target in ("mcp-check", "mcp-smoke"):
            result = self.run_make(target, "MCP_RELEASE_IMAGE=fixture:isolated")
            self.assertEqual(result.returncode, 0, result.stderr)
            command = self.calls()[-1]
            self.assertEqual(command[0], "run")
            self.assertIn("sha256:" + "a" * 64, command)
            self.assertNotIn("--mount", command)
            self.assertIn("none", command)

    def test_relocated_stdio_preserves_hostile_path_and_cleanup_identity(self) -> None:
        project = self.root / 'consumer, "quoted" $literal'
        project.mkdir()
        self.env["MCP_CONSUMER_WORKSPACE"] = str(project)
        result = self.run_make("mcp-stdio")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = self.calls()[-1]
        mounts = [next(csv.reader([run[i + 1]])) for i, arg in enumerate(run) if arg == "--mount"]
        self.assertEqual(mounts, [
            ["type=bind", f"source={project}", "target=/workspace"],
            ["type=bind", f"source={project}", f"target={project}"],
        ])
        project_label = next(arg for arg in run if arg.startswith("io.context.mcp-project="))
        result = self.run_make("mcp-down")
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in self.calls()[-2:]:
            self.assertIn(f"label={project_label}", command)
            self.assertIn("label=io.context.mcp-factory=unaltraweb", command)

    def test_native_transport_rejects_make_workspace_assignment(self) -> None:
        marker = self.root / "expanded"
        result = self.run_make("mcp-stdio", f"MCP_CONSUMER_WORKSPACE=$(shell touch {marker})")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be inherited", result.stderr)
        self.assertFalse(marker.exists())
        self.assertFalse(self.log.exists())

    def test_missing_consumer_does_not_start_docker(self) -> None:
        result = self.run_make("mcp-stdio")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_owner_smoke_refuses_to_reuse_an_existing_fixture(self) -> None:
        project = self.root / "existing-consumer"
        project.mkdir()
        sentinel = project / "authored.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        result = subprocess.run([
            "make", "--silent", "--no-print-directory", "-C", str(ROOT), "mcp-smoke-prebuilt",
            f"MCP_SMOKE_PROJECT={project}", "MCP_IMAGE=fixture:isolated",
        ], env=self.env, capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "preserve\n")
        self.assertEqual(len(self.calls()), 1, "Only the consumer-free stdio smoke may run")
