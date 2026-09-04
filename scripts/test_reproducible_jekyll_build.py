#!/usr/bin/env python3
"""Prove deterministic Jekyll output with the packaged core and fixed epoch."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("DOCKER_IMAGE", "ghcr.io/dosquartsdedocs/unaltraweb:0.3.0")
SELECTOR = "v2026.09"
EPOCH = "946684800"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")
    return completed


def docker_build(site: Path, destination: str, epoch: str) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            "HOME=/tmp",
            "-e",
            "BUNDLE_GEMFILE=/site/Gemfile.local",
            "-e",
            "JEKYLL_ENV=production",
            "-e",
            "LANG=C.UTF-8",
            "-e",
            "LC_ALL=C.UTF-8",
            "-e",
            f"SOURCE_DATE_EPOCH={epoch}",
            "-e",
            "TZ=UTC",
            "-e",
            f"UNALTRAWEB_MANUAL_RELEASE_SELECTOR={SELECTOR}",
            "--mount",
            f"type=bind,src={ROOT},dst=/core,readonly",
            "--mount",
            f"type=bind,src={site},dst=/site",
            "--workdir",
            "/site",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            "umask 022; bundle lock --local && bundle check && "
            "bundle exec jekyll build --config /core/_config.yml,/site/_config.yml "
            f"--destination /site/{destination} --disable-disk-cache",
        ],
        check=False,
    )


def tree_inventory(root: Path) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
            raise RuntimeError(f"Unexpected output type in reproducibility fixture: {relative}")
        if path.is_dir():
            result[relative + "/"] = {"mode": stat.S_IMODE(metadata.st_mode), "type": "directory"}
        else:
            content = path.read_bytes()
            result[relative] = {
                "mode": stat.S_IMODE(metadata.st_mode),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "type": "file",
            }
    return result


def set_source_mtime(site: Path, timestamp: int) -> None:
    for path in site.rglob("*"):
        if not path.is_dir() and not any(part.startswith("_site-") for part in path.parts):
            os.utime(path, (timestamp, timestamp))


def write_fixture(site: Path) -> None:
    (site / "_posts").mkdir(parents=True)
    (site / "Gemfile.local").write_text(
        'source "https://rubygems.org"\ngem "unaltraweb", path: "/core"\n',
        encoding="utf-8",
    )
    (site / "_config.yml").write_text(
        "title: Reproducible manual\n"
        "url: https://example.invalid\n"
        "baseurl: ''\n"
        "lang: en\n"
        "default_lang: en\n"
        "languages: [en]\n"
        "theme: unaltraweb\n"
        "plugins: [unaltraweb]\n"
        "last_updated: true\n"
        "exclude: [_site-a, _site-b, _site-invalid]\n"
        "unaltraweb:\n"
        "  site_profile: unaltremanual\n"
        "  manual:\n"
        "    pdf:\n"
        "      enabled: false\n",
        encoding="utf-8",
    )
    (site / "index.md").write_text(
        "---\ntitle: Manual\n---\n{% include footer.liquid %}\n",
        encoding="utf-8",
    )
    (site / "_posts/1999-12-31-reviewed.md").write_text(
        "---\ntitle: Reviewed\ndate: 1999-12-31 12:00:00 +0000\n---\nReviewed post.\n",
        encoding="utf-8",
    )
    (site / "manual.pdf").write_bytes(b"reviewed static file\n")


def main() -> int:
    inspected = run(["docker", "image", "inspect", IMAGE], check=False)
    if inspected.returncode != 0:
        raise RuntimeError(f"Reproducibility check requires the already-local runtime image {IMAGE}; it never pulls implicitly.")

    with tempfile.TemporaryDirectory(prefix="unaltraweb-reproducible-site-") as raw:
        site = Path(raw).resolve()
        write_fixture(site)
        set_source_mtime(site, 978307200)
        first = docker_build(site, "_site-a", EPOCH)
        if first.returncode != 0:
            raise RuntimeError(first.stderr.strip() or first.stdout.strip())

        set_source_mtime(site, 1893456000)
        second = docker_build(site, "_site-b", EPOCH)
        if second.returncode != 0:
            raise RuntimeError(second.stderr.strip() or second.stdout.strip())

        first_inventory = tree_inventory(site / "_site-a")
        second_inventory = tree_inventory(site / "_site-b")
        if first_inventory != second_inventory:
            differing = sorted(set(first_inventory) | set(second_inventory))
            differing = [path for path in differing if first_inventory.get(path) != second_inventory.get(path)]
            raise RuntimeError("Fixed-epoch Jekyll builds differ: " + ", ".join(differing[:12]))

        expected_marker = json.dumps(
            {"channel": "stable", "schema_version": 1, "selector": SELECTOR},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        marker = (site / "_site-a/manual-release.json").read_text(encoding="utf-8")
        if marker != expected_marker:
            raise RuntimeError("manual-release.json was not preserved as canonical JSON.")
        index = (site / "_site-a/index.html").read_text(encoding="utf-8")
        if "2000" not in index or "January 1, 2000" not in index:
            raise RuntimeError("Footer does not use the fixed build time.")
        feed = (site / "_site-a/feed.xml").read_text(encoding="utf-8")
        if "2000-01-01T00:00:00+00:00" not in feed:
            raise RuntimeError("Feed does not use the fixed build time.")

        invalid = docker_build(site, "_site-invalid", "not-an-epoch")
        if invalid.returncode == 0 or "SOURCE_DATE_EPOCH" not in (invalid.stderr + invalid.stdout):
            raise RuntimeError("Malformed SOURCE_DATE_EPOCH did not fail the Jekyll build.")

    print(json.dumps({"image": IMAGE, "ok": True, "selector": SELECTOR}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
