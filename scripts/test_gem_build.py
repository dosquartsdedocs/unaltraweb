#!/usr/bin/env python3
"""Build the gem without network access and inspect its packaged contract files."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unaltraweb_mcp.docker_mount import docker_bind_mount


CONTRACT = json.loads((ROOT / "src/unaltraweb_mcp/component-contract.json").read_text(encoding="utf-8"))
RUNTIME_IMAGE = str(CONTRACT["components"]["runtime"]["reference"])


def run(command: list[str], *, cwd: Path = ROOT, expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def build(output: Path, *, source: Path = ROOT) -> str:
    if shutil.which("ruby") and shutil.which("gem"):
        run(["gem", "build", "unaltraweb.gemspec", "--output", str(output)], cwd=source)
        return "local-ruby"
    if not shutil.which("docker"):
        raise RuntimeError("Gem smoke requires local RubyGems or Docker with the selected runtime image.")
    inspected = subprocess.run(
        ["docker", "image", "inspect", RUNTIME_IMAGE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if inspected.returncode != 0:
        raise RuntimeError(f"Gem smoke requires the already-local runtime image {RUNTIME_IMAGE}; it never pulls implicitly.")
    run([
        "docker", "run", "--rm", "--network", "none",
        "--mount", docker_bind_mount(source, "/repo", readonly=True),
        "--mount", docker_bind_mount(output.parent, "/out"), "-w", "/repo",
        RUNTIME_IMAGE, "gem", "build", "unaltraweb.gemspec", "--output", f"/out/{output.name}",
    ])
    return "docker-runtime"


def inspect_gem(path: Path) -> None:
    editorial_files = ["scripts/editorial_check.py", "src/unaltraweb_mcp/editorial.py", "src/unaltraweb_mcp/editorial_sources.py"]
    inspection_files = editorial_files + ["scripts/image_background_check.py", "src/unaltraweb_mcp/image_backgrounds.py",
                                          "src/unaltraweb_mcp/image_probe.py", "src/unaltraweb_mcp/processes.py"]
    with tarfile.open(path, mode="r") as package:
        data_member = package.extractfile("data.tar.gz")
        if data_member is None:
            raise RuntimeError("Built gem has no data.tar.gz payload.")
        with tarfile.open(fileobj=io.BytesIO(data_member.read()), mode="r:gz") as payload:
            names = set(payload.getnames())
            editorial_bytes = {name: payload.extractfile(name).read() for name in inspection_files}
    required = {
        "LICENSE",
        "README.md",
        "_data/i18n/ca.yml",
        "_data/i18n/en.yml",
        "_data/i18n/es.yml",
        "_plugins/bibliography_profiles.rb",
        "_plugins/code_blocks.rb",
        "_plugins/content_search_index.rb",
        "_plugins/figure_captions.rb",
        "_plugins/manual_release_metadata.rb",
        "_plugins/reproducible_build_time.rb",
        "assets/js/content-search-match.js",
        "assets/js/content-search.js",
        "_config.yml",
        "Makefile",
        "requirements.txt",
        "lib/unaltraweb/version.rb",
        "scripts/manual/build_pdf.py",
        "scripts/manual/filters/bibliography.lua",
        "scripts/manual/filters/code-blocks.lua",
        "scripts/manual/filters/figure-captions.lua",
        "scripts/manual/publish_release.sh",
        "scripts/manual/verify_release_assets.py",
        "scripts/unaltraweb-docker-mount.sh",
        "scripts/unaltraweb-mcp-cleanup.sh",
        "scripts/unaltraweb-mcp-project-id.sh",
        "src/unaltraweb_mcp/component-contract.json",
        "src/unaltraweb_mcp/component-contract.schema.json",
        "src/unaltraweb_mcp/docker_mount.py",
        *inspection_files,
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Built gem is missing required files: {missing}")
    unexpected_data = sorted(name for name in names if name.startswith("_data/") and not name.startswith("_data/i18n/"))
    if unexpected_data:
        raise RuntimeError(f"Built gem contains non-runtime data files: {unexpected_data}")
    # Exercise only the actual gem payload with isolated Python: no factory,
    # wheel, inherited PYTHONPATH, source checkout or MCP dependency may help.
    with tempfile.TemporaryDirectory(prefix="unaltraweb-gem-editorial-") as temporary:
        core = Path(temporary) / "core"
        for name, content in editorial_bytes.items():
            target = core / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        site = Path(temporary) / "site"
        (site / "_pages/en").mkdir(parents=True)
        (site / "_config.yml").write_text("unaltraweb:\n  site_profile: unaltreselfie\n", encoding="utf-8")
        page = site / "_pages/en/about.md"
        page.write_text("I study spatial data.\n", encoding="utf-8")
        command = [sys.executable, "-I", str(core / editorial_files[0]), "--project", str(site)]
        if not json.loads(run(command, cwd=site).stdout)["ok"]:
            raise RuntimeError("Gem-native editorial check rejected publication copy.")
        page.write_text("As requested, I have added the biography.\n", encoding="utf-8")
        if json.loads(run(command, cwd=site, expected=1).stdout)["ok"]:
            raise RuntimeError("Gem-native editorial gate accepted chat-dependent copy.")
        (site / "assets").mkdir()
        (site / "assets/test.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><circle cx="5" cy="5" r="2" fill="blue"/></svg>', encoding="utf-8")
        image_command = [sys.executable, "-I", str(core / "scripts/image_background_check.py"), "--project", str(site), "--source", "assets/test.svg"]
        inspection = json.loads(run(image_command, cwd=site).stdout)
        if not inspection["ok"] or inspection["images"][0]["state"] != "transparent" or not inspection["warnings"]:
            raise RuntimeError(f"Gem-native SVG background inspection failed: {inspection}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="unaltraweb-gem-") as raw_temp:
        output = Path(raw_temp) / "unaltraweb.gem"
        runner = build(output)
        inspect_gem(output)
        archive_source = Path(raw_temp) / "source-archive"
        shutil.copytree(
            ROOT,
            archive_source,
            ignore=shutil.ignore_patterns(".git", "_site", "tmp", ".jekyll-cache", "__pycache__", "*.pyc"),
        )
        archive_output = Path(raw_temp) / "unaltraweb-source-archive.gem"
        build(archive_output, source=archive_source)
        inspect_gem(archive_output)
        print(json.dumps({"ok": True, "runner": runner, "gem": output.name}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
