#!/usr/bin/env python3
"""Build the gem without network access and inspect its packaged contract files."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "src/unaltraweb_mcp/component-contract.json").read_text(encoding="utf-8"))
RUNTIME_IMAGE = str(CONTRACT["components"]["runtime"]["reference"])


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def build(output: Path) -> str:
    if shutil.which("ruby") and shutil.which("gem"):
        run(["gem", "build", "unaltraweb.gemspec", "--output", str(output)])
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
        "-v", f"{ROOT}:/repo:ro", "-v", f"{output.parent}:/out:rw", "-w", "/repo",
        RUNTIME_IMAGE, "gem", "build", "unaltraweb.gemspec", "--output", f"/out/{output.name}",
    ])
    return "docker-runtime"


def inspect_gem(path: Path) -> None:
    with tarfile.open(path, mode="r") as package:
        data_member = package.extractfile("data.tar.gz")
        if data_member is None:
            raise RuntimeError("Built gem has no data.tar.gz payload.")
        with tarfile.open(fileobj=io.BytesIO(data_member.read()), mode="r:gz") as payload:
            names = set(payload.getnames())
    required = {
        "_plugins/bibliography_profiles.rb",
        "_plugins/content_search_index.rb",
        "assets/js/content-search-match.js",
        "assets/js/content-search.js",
        "lib/unaltraweb/version.rb",
        "src/unaltraweb_mcp/component-contract.json",
        "src/unaltraweb_mcp/component-contract.schema.json",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Built gem is missing required files: {missing}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="unaltraweb-gem-") as raw_temp:
        output = Path(raw_temp) / "unaltraweb.gem"
        runner = build(output)
        inspect_gem(output)
        print(json.dumps({"ok": True, "runner": runner, "gem": output.name}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
