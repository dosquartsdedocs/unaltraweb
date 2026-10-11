#!/usr/bin/env python3
"""Explicit offline successor build: approved base + exact owner source overlays.

No commit, publication, source worktree copy or runtime allocation is performed.
The GIS domain code is installed only from the selected hash-bound producer wheel.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

from prepare_practice_candidate import ROOT, SOURCE, BASE, BASE_ID, PDF, PDF_ID, image, run, sha256, export_image

OVERLAYS = (
    "Makefile", "mcp-factory.yml", "pyproject.toml",
    "src/unaltraweb_mcp/practice_editions.py", "src/unaltraweb_mcp/practice-edition-v1.schema.json",
    "src/unaltraweb_mcp/practice_pdf.py", "src/unaltraweb_mcp/editorial_sources.py",
    "src/unaltraweb_mcp/site_tools.py", "src/unaltraweb_mcp/mcp_server.py", "src/unaltraweb_mcp/cli.py",
    "src/unaltraweb_mcp/component-contract.json",
    "scripts/manual/render_practice.py",
)
TRANSFER = Path("/tmp/opencode/practice32-qgis-0.6.0rc1-round32-r2")
GIS_SHA = "82f2c6772fa8bb9aaae08237494af72df7e103038643fd6dfcdcd6f1ac45ed5f"


def prepare(output, gis_wheel, gis_sha, profiles=("qgis-practice-v1",)):
    if not profiles or len(profiles) != len(set(profiles)) or set(profiles) - {"qgis-practice-v1", "qgis-practice-v2"}:
        raise ValueError("Select explicit supported producer profiles")
    output = output.absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / "tmp") or output.exists():
        raise ValueError("Select a new confined candidate directory under tmp/")
    if sha256(gis_wheel) != gis_sha:
        raise ValueError("Producer wheel differs from the selected SHA-256")
    base, pdf = image(BASE, BASE_ID), image(PDF, PDF_ID)
    output.mkdir(parents=True, exist_ok=False)
    packages = output / "packages"
    packages.mkdir()
    original = output / "approved-source.tar.gz"
    run(["git", "archive", "--format=tar.gz", "--output", str(original), SOURCE])
    epoch = int(run(["git", "show", "-s", "--format=%ct", SOURCE]).strip())
    changes = {}
    for name in OVERLAYS:
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2*1024*1024:
            raise ValueError("Unsafe candidate overlay: " + name)
        changes[name] = path.read_bytes()
    source = output / "source.tar.gz"
    with original.open("rb") as raw_source, tarfile.open(fileobj=raw_source, mode="r:gz") as previous, \
            source.open("xb") as raw_dest, gzip.GzipFile(fileobj=raw_dest, mode="wb", filename="", mtime=0) as compressed, \
            tarfile.open(fileobj=compressed, mode="w|") as snapshot:
        for member in previous:
            if member.name not in changes:
                snapshot.addfile(member, previous.extractfile(member) if member.isfile() else None)
        for name, raw in sorted(changes.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(raw), 0o644, epoch
            snapshot.addfile(info, io.BytesIO(raw))
    source_sha = sha256(source)
    env = {**os.environ, "PIP_NO_INDEX": "1", "SOURCE_DATE_EPOCH": str(epoch), "PYTHONHASHSEED": "0", "TZ": "UTC"}
    run([sys.executable, "-m", "pip", "wheel", str(source), "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(packages)],
        environment=env, log=output / "wheel-build.log")
    web_wheel = next(packages.glob("unaltraweb_mcp-*.whl"))
    shutil.copyfile(gis_wheel, packages / gis_wheel.name)
    dockerfile = ROOT / "packaging/practice-editions-candidate/Dockerfile"
    shutil.copyfile(dockerfile, output / "Dockerfile")
    (output / ".dockerignore").write_text("*\n!Dockerfile\n!source.tar.gz\n!packages/\n!packages/*.whl\n")
    run(["docker", "build", "--pull=false", "--network", "none", "--build-arg", "BASE_MCP_IMAGE="+BASE,
         "--build-arg", "SOURCE_SNAPSHOT_SHA256="+source_sha, "--iidfile", str(output / "image.id"), str(output)],
        timeout=600, log=output / "image-build.log")
    identifier = (output / "image.id").read_text().strip()
    actual = image(identifier, identifier)
    if actual["source_revision"] != "sha256:"+source_sha:
        raise ValueError("Candidate source identity differs")
    schema = json.loads(run(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--entrypoint", "unaltracaptura-qgis", identifier, "practice-schema"]))
    profile_records = {}
    for profile in profiles:
        observed = schema if profile == "qgis-practice-v1" else json.loads(run([
            "docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--entrypoint", "unaltracaptura-qgis", identifier,
            "practice-schema", "--profile", profile]))
        if observed.get("profile") != profile or observed.get("ok") is not True:
            raise ValueError("Installed producer did not identify the requested domain profile")
        profile_records[profile] = {"package": observed["installed_package"], "schema_sha256": observed["schema_sha256"]}
    archive = export_image(identifier, output / "controller.docker.tar.gz")
    contract = json.loads(changes["src/unaltraweb_mcp/component-contract.json"])
    manifest = {"kind": "unaltraweb.practice-editions-candidate", "schema_version": 1, "published": False,
        "source_base": SOURCE, "source_snapshot_sha256": source_sha,
        "overlays": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(changes.items())},
        "version_note": "Unpublished hash-bound successor; package metadata remains 0.7.1 and is not the published 0.7.1 artifact",
        "controller": actual, "controller_archive": archive, "controller_base": base, "pdf_worker": pdf,
        "web_wheel": {"path": "packages/"+web_wheel.name, "sha256": sha256(web_wheel)},
        "gis_wheel": {"path": "packages/"+gis_wheel.name, "sha256": gis_sha},
        "gis_verifier": {"package": schema["installed_package"], "schema_sha256": schema["schema_sha256"]},
        "gis_profiles": profile_records,
        "composition_schema_sha256": sha256(ROOT / "src/unaltraweb_mcp/practice-edition-v1.schema.json"),
        "consumer_integration": contract["consumer_integration"],
        "builder_sha256": sha256(__file__), "dockerfile_sha256": sha256(dockerfile)}
    (output / "candidate.json").write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n")
    (output / "install-requirements.txt").write_text(f"{web_wheel.as_uri()} --hash=sha256:{sha256(web_wheel)}\n")
    print(json.dumps({"ok": True, "candidate": str(output / "candidate.json"), "sha256": sha256(output / "candidate.json"), "image_id": identifier}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gis-wheel", type=Path, default=TRANSFER / "unaltracaptura_qgis-0.6.0rc1-py3-none-any.whl")
    parser.add_argument("--gis-sha256", default=GIS_SHA)
    parser.add_argument("--gis-profile", action="append", choices=["qgis-practice-v1", "qgis-practice-v2"])
    args = parser.parse_args()
    prepare(args.output, args.gis_wheel, args.gis_sha256, args.gis_profile or ["qgis-practice-v1"])
