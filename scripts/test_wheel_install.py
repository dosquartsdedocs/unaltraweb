#!/usr/bin/env python3
"""Build and exercise a clean, factory-free unaltraweb-mcp wheel install."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != expected:
        raise RuntimeError(
            f"Command returned {completed.returncode}, expected {expected}: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}"
        )
    return completed


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="unaltraweb-wheel-") as raw_temp:
        temp = Path(raw_temp)
        wheel_dir = temp / "dist"
        wheel_dir.mkdir()
        env = os.environ.copy()
        env["PIP_NO_INDEX"] = "1"
        run(
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir)],
            cwd=ROOT,
            env=env,
        )
        wheels = list(wheel_dir.glob("unaltraweb_mcp-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected one wheel, found: {wheels}")
        with zipfile.ZipFile(wheels[0]) as archive:
            names = archive.namelist()
        forbidden_roots = {"docs", "scripts", "_layouts", "_includes", "_sass"}
        leaked = []
        for name in names:
            parts = Path(name).parts
            if not parts or parts[0] != "unaltraweb_mcp":
                continue
            package_parts = parts[1:]
            if package_parts and (package_parts[0] in forbidden_roots or package_parts[0] in {"mcp-factory.yml", "Dockerfile", "Makefile"}):
                leaked.append(name)
        if leaked:
            raise RuntimeError(f"Factory assets leaked into wheel: {leaked}")
        required = [
            "unaltraweb_mcp/component-contract.json",
            "unaltraweb_mcp/component-contract.schema.json",
            "unaltraweb_mcp/scaffolds/common/Makefile.tmpl",
            "unaltraweb_mcp/scaffolds/profiles/unaltremanual/_bibliography/manual.bib",
            "unaltraweb_mcp/scaffolds/profiles/unaltreprojecte/_bibliography/papers.bib",
            "unaltraweb_mcp/scaffolds/profiles/unaltreselfie/_bibliography/papers.bib",
        ]
        missing = [name for name in required if name not in names]
        if missing:
            raise RuntimeError(f"Wheel is missing modular package assets: {missing}")

        environment = temp / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin/python"
        cli = environment / "bin/unaltraweb-mcp"
        run([str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])], cwd=temp, env=env)
        version = run([str(cli), "version"], cwd=temp).stdout.strip()
        doctor = json.loads(run([str(cli), "doctor"], cwd=temp).stdout)
        if not doctor["ok"] or doctor["mode"] != "wheel" or not doctor["limited"]:
            raise RuntimeError(f"Unexpected clean wheel doctor result: {doctor}")

        site = temp / "site"
        created = json.loads(run([str(cli), "--project", str(site), "new-web", "--site-profile", "unaltredocs"], cwd=temp).stdout)
        if not created["ok"]:
            raise RuntimeError(f"new-web failed from clean wheel: {created}")
        if not (site / ".unaltraweb/scaffold.json").is_file():
            raise RuntimeError("new-web did not install the package scaffold baseline")
        detected = json.loads(run([str(cli), "--project", str(site), "mcp", "detect-site"], cwd=temp).stdout)
        if not detected["is_unaltraweb_site"]:
            raise RuntimeError(f"package-only inspection failed from clean wheel: {detected}")
        project_doctor = json.loads(run([str(cli), "doctor", "--project", str(site)], cwd=temp).stdout)
        if not project_doctor["ok"] or project_doctor["project"]["profile"] != "unaltredocs":
            raise RuntimeError(f"project doctor failed from clean wheel: {project_doctor}")
        site_doctor = json.loads(run([str(cli), "--project", str(site), "mcp", "site-doctor"], cwd=temp).stdout)
        if not site_doctor["ok"] or not site_doctor["offline"]:
            raise RuntimeError(f"site doctor failed from clean wheel: {site_doctor}")
        source = json.loads(run([str(cli), "--project", str(site), "mcp", "site-source-read", "--path", "_pages/en/index.md"], cwd=temp).stdout)
        source_dry_run = json.loads(run([
            str(cli), "--project", str(site), "mcp", "site-source-write",
            "--path", "_pages/en/index.md", "--content", source["content"] + "\nWheel source test.\n",
            "--expected-sha256", source["sha256"],
        ], cwd=temp).stdout)
        if not source_dry_run["dry_run"] or (site / "_pages/en/index.md").read_text(encoding="utf-8") != source["content"]:
            raise RuntimeError(f"wheel source dry-run mutated content: {source_dry_run}")
        scaffold = json.loads(run([str(cli), "--project", str(site), "mcp", "scaffold-sync"], cwd=temp).stdout)
        if not scaffold["ok"] or not scaffold["dry_run"]:
            raise RuntimeError(f"wheel scaffold sync dry-run failed: {scaffold}")

        factory_error = run([str(cli), "--project", str(site), "mcp", "prompts"], cwd=temp, expected=1)
        if "requires the unaltraweb factory checkout" not in factory_error.stderr:
            raise RuntimeError(f"Factory-required command did not fail clearly: {factory_error.stderr}")
        print(json.dumps({"ok": True, "version": version, "wheel": wheels[0].name, "mode": doctor["mode"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
