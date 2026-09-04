#!/usr/bin/env python3
"""Build and exercise a clean, factory-free unaltraweb-mcp wheel install."""

from __future__ import annotations

import json
import os
import shutil
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
        source = temp / "source"
        shutil.copytree(
            ROOT,
            source,
            ignore=shutil.ignore_patterns(
                ".git",
                "build",
                "dist",
                "*.egg-info",
                "_site",
                "tmp",
                "__pycache__",
                "*.pyc",
            ),
        )
        wheel_dir = temp / "dist"
        wheel_dir.mkdir()
        env = os.environ.copy()
        env["PIP_NO_INDEX"] = "1"
        run(
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir)],
            cwd=source,
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
            "unaltraweb_mcp/calibre_import.py",
            "unaltraweb_mcp/component-contract.json",
            "unaltraweb_mcp/component-contract.schema.json",
            "unaltraweb_mcp/manual_release.py",
            "unaltraweb_mcp/scaffolds/common/AGENTS.md.tmpl",
            "unaltraweb_mcp/scaffolds/common/Makefile.tmpl",
            "unaltraweb_mcp/scaffolds/common/README.md.tmpl",
            "unaltraweb_mcp/scaffolds/common/.gitignore.tmpl",
            "unaltraweb_mcp/scaffolds/common/.unaltraweb/docker-mount.sh",
            "unaltraweb_mcp/scaffolds/common/root.html.tmpl",
            "unaltraweb_mcp/scaffolds/profiles/unaltremanual/computations.yml.tmpl",
            "unaltraweb_mcp/scaffolds/profiles/unaltremanual/_bibliography/manual.bib",
            "unaltraweb_mcp/scaffolds/profiles/unaltreprojecte/_bibliography/papers.bib",
            "unaltraweb_mcp/scaffolds/profiles/unaltreselfie/_bibliography/papers.bib",
            "unaltraweb_mcp/scaffolds/common/.github/pull_request_template.md",
            "unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml",
        ]
        missing = [name for name in required if name not in names]
        if missing:
            raise RuntimeError(f"Wheel is missing modular package assets: {missing}")
        if "unaltraweb_mcp/scaffolds/common/.gitignore" in names:
            raise RuntimeError("Wheel contains the retired static common .gitignore")

        environment = temp / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin/python"
        cli = environment / "bin/unaltraweb-mcp"
        run([str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])], cwd=temp, env=env)
        version = run([str(cli), "version"], cwd=temp).stdout.strip()
        doctor = json.loads(run([str(cli), "doctor"], cwd=temp).stdout)
        if not doctor["ok"] or doctor["mode"] != "wheel" or not doctor["limited"]:
            raise RuntimeError(f"Unexpected clean wheel doctor result: {doctor}")

        profiles = {
            "unaltreselfie": ("Personal academic or professional site.", "`_posts/` and `_news/`"),
            "unaltreprojecte": ("Research project, group, infrastructure, or output site.", "`_data/team.yml`"),
            "unaltremanual": ("Book-like manual, course, or teaching site.", "`_chapters/<lang>/`"),
            "unaltredocs": ("Technical or operational documentation portal.", "`_documentation/<lang>/`"),
        }
        sites: dict[str, Path] = {}
        for profile, (description, profile_path) in profiles.items():
            profile_site = temp / f"site-{profile}"
            created = json.loads(run([
                str(cli), "--project", str(profile_site), "new-web", "--site-profile", profile,
                "--title", f"Wheel {profile}",
            ], cwd=temp).stdout)
            if not created["ok"]:
                raise RuntimeError(f"new-web failed for {profile} from clean wheel: {created}")
            readme = (profile_site / "README.md").read_text(encoding="utf-8")
            pr_template = (profile_site / ".github/pull_request_template.md").read_text(encoding="utf-8")
            if not readme.startswith("# GitHub Web Editing Workflow\n"):
                raise RuntimeError(f"generated {profile} README is not editor-first")
            required_guidance = [
                f"**`{profile}`** profile: {description}",
                f"## Editable Content For `{profile}`",
                profile_path,
                "only one active editor per file",
                "Never edit or commit directly to `main`",
                "Draft pull request",
                "Starts the deploy workflow manually",
            ]
            missing_guidance = [value for value in required_guidance if value not in readme]
            if missing_guidance:
                raise RuntimeError(f"generated {profile} README is missing guidance: {missing_guidance}")
            if f"Wheel {profile}" in readme:
                raise RuntimeError(f"generated {profile} README interpolated the user-controlled title")
            if any(f"`{known_profile}`" not in readme for known_profile in profiles):
                raise RuntimeError(f"generated {profile} README does not explain all profiles")
            if "one task on one branch" not in pr_template or "Required local checks and renders pass" not in pr_template:
                raise RuntimeError(f"generated {profile} pull request template lacks coordination checks")
            combined_guidance = readme + pr_template
            forbidden = ["${{", "secrets.", "GITHUB_TOKEN", "id-token:", "contents: write", "on:\n  push:"]
            if any(value in combined_guidance for value in forbidden):
                raise RuntimeError(f"generated {profile} editor guidance exposes workflow or secret internals")
            auto_publish = ["publishes automatically", "deploys automatically", "automatic deployment"]
            if any(value in combined_guidance.lower() for value in auto_publish):
                raise RuntimeError(f"generated {profile} editor guidance implies automatic publication")
            if profile == "unaltremanual":
                manual_markers = [
                    "`latest` is a manual-only deployment",
                    "Pushing or merging to `main` does not publish the manual",
                    "are generated for deployment and are not versioned",
                    "`vYYYY.MM(.N)`",
                    "Release checks reject `legacy/` or `sandbox/`",
                ]
                if any(value not in readme for value in manual_markers):
                    raise RuntimeError("generated unaltremanual README lacks release-channel guidance")
            elif "## unaltremanual Publishing Channels" in readme:
                raise RuntimeError(f"generated {profile} README contains unaltremanual-only release guidance")
            ignore_lines = (profile_site / ".gitignore").read_text(encoding="utf-8").splitlines()
            expects_manual_outputs = profile == "unaltremanual"
            if ("/assets/pdf/manual-en.pdf" in ignore_lines) != expects_manual_outputs or ("/assets/img/manual-cover-en.png" in ignore_lines) != expects_manual_outputs:
                raise RuntimeError(f"generated {profile} .gitignore has incorrect manual output scope")
            if "*.pdf" in ignore_lines or "*.png" in ignore_lines:
                raise RuntimeError(f"generated {profile} .gitignore ignores arbitrary publication assets")
            sites[profile] = profile_site

        site = sites["unaltredocs"]
        if not (site / ".unaltraweb/scaffold.json").is_file():
            raise RuntimeError("new-web did not install the package scaffold baseline")

        manual_site = temp / "manual-site"
        manual_created = json.loads(run([str(cli), "--project", str(manual_site), "new-web", "--site-profile", "unaltremanual"], cwd=temp).stdout)
        if not manual_created["ok"]:
            raise RuntimeError(f"manual new-web failed from clean wheel: {manual_created}")
        for required_path in [
            "AGENTS.md",
            "README.md",
            "_pages/index.html",
            "_chapters/en/.gitkeep",
            "assets/quarto/.gitkeep",
            "assets/img/generated/.gitkeep",
        ]:
            if not (manual_site / required_path).is_file():
                raise RuntimeError(f"manual new-web did not create {required_path}")
        computation_config = (manual_site / ".unaltraweb/computations.yml").read_text(encoding="utf-8")
        contract = json.loads((ROOT / "src/unaltraweb_mcp/component-contract.json").read_text(encoding="utf-8"))
        for component_id in ["compute_python", "compute_r"]:
            if contract["components"][component_id]["reference"] not in computation_config:
                raise RuntimeError(f"new-web did not select the {component_id} worker from the component contract")
        manual_doctor = json.loads(run([str(cli), "doctor", "--project", str(manual_site)], cwd=temp).stdout)
        if not {"compute_python", "compute_r"}.issubset(manual_doctor["selected_components"]):
            raise RuntimeError(f"manual project doctor did not select both computation workers: {manual_doctor}")
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
