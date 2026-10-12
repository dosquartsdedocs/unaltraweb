#!/usr/bin/env python3
"""Explicit offline preparation of the approved #101 practice-PDF source slice.

Produces a local candidate, never a release or registry publication. The source
archive is taken from an exact committed revision; no W1 worktree files enter it.
The prepared public controller/PDF images and existing host build dependencies
are required. Normal consumer launch/build commands do not invoke this script.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0"
BASE = "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6"
BASE_ID = "sha256:f0e7915527fa68a67448287e131ec431aeae902b8269856e4e219e67faade146"
PDF = "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b"
PDF_ID = "sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa"
APPROVED_PDF_SHA256 = "c92ec8a0937e9c9c735171d889e5bbca19b7ccd9ccbe8d33da2b6c0e49f9a245"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while piece := source.read(1024*1024):
            digest.update(piece)
    return digest.hexdigest()


def run(command, *, environment=None, timeout=300, log=None):
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout)
    if log is not None:
        Path(log).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stdout[-12000:]}\n{result.stderr[-12000:]}")
    return result.stdout


def image(reference, expected=None):
    value = json.loads(run(["docker", "image", "inspect", reference]))[0]
    if expected and value["Id"] != expected:
        raise RuntimeError("Prepared image differs from the expected immutable configuration ID")
    if "@sha256:" in reference and reference not in (value.get("RepoDigests") or []):
        raise RuntimeError("Prepared image does not retain the selected repository digest")
    if (value["Os"], value["Architecture"]) != ("linux", "amd64"):
        raise RuntimeError("This candidate acceptance selects Linux/amd64")
    return {"reference": reference, "image_id": value["Id"], "repo_digests": value.get("RepoDigests") or [],
            "source_revision": (value["Config"].get("Labels") or {}).get("org.opencontainers.image.revision"),
            "size": value["Size"], "os": value["Os"], "architecture": value["Architecture"]}


def export_image(identifier, destination):
    """Stream a bounded Docker-save archive; never buffer image layers in RAM."""
    process = subprocess.Popen(["docker", "image", "save", identifier], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    total, deadline = 0, time.monotonic()+600
    watchdog = threading.Timer(600, process.kill)
    watchdog.daemon = True
    watchdog.start()
    try:
        with destination.open("xb") as raw, gzip.GzipFile(fileobj=raw, filename="", mode="wb", compresslevel=1, mtime=0) as output:
            while piece := process.stdout.read(1024*1024):
                total += len(piece)
                if total > 8*1024**3 or time.monotonic() > deadline:
                    raise RuntimeError("Image archive exceeds its preparation budget")
                output.write(piece)
        process.stdout.close()
        error = process.stderr.read(32768).decode(errors="replace")
        if process.wait(timeout=10):
            raise RuntimeError("Docker image export failed: " + error)
    except BaseException:
        process.kill()
        process.wait()
        raise
    finally:
        watchdog.cancel()
        process.stdout.close()
        process.stderr.close()
    return {"path": destination.name, "sha256": sha256(destination), "bytes": destination.stat().st_size,
            "uncompressed_bytes": total, "format": "docker-save-gzip"}


def prepare(output):
    if Path(run(["git", "rev-parse", "--show-toplevel"]).strip()) != ROOT:
        raise RuntimeError("Candidate preparation requires the authoritative factory checkout")
    output = Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / "tmp"):
        raise RuntimeError("Use a new, non-symlink candidate directory under the factory tmp/")
    if os.path.lexists(output):
        raise FileExistsError("Candidate destination already exists: " + str(output))
    if any(importlib.util.find_spec(name) is None for name in ("setuptools", "wheel", "pip")):
        raise RuntimeError("Prepare host setuptools/wheel/pip explicitly before this offline build")
    base, pdf = image(BASE, BASE_ID), image(PDF, PDF_ID)
    output.mkdir(parents=True, exist_ok=False)
    packages = output / "packages"
    packages.mkdir()
    archive = output / "source.tar.gz"
    run(["git", "archive", "--format=tar.gz", "--output", str(archive), SOURCE])
    if archive.stat().st_size > 128*1024**2:
        raise RuntimeError("Approved source archive exceeds the preparation bound")
    epoch = run(["git", "show", "-s", "--format=%ct", SOURCE]).strip()
    environment = {**os.environ, "PIP_NO_INDEX": "1", "SOURCE_DATE_EPOCH": epoch, "PYTHONHASHSEED": "0", "TZ": "UTC"}
    run([sys.executable, "-m", "pip", "wheel", str(archive), "--no-index", "--no-deps", "--no-build-isolation",
         "--wheel-dir", str(packages)], environment=environment, log=output / "wheel-build.log")
    wheels = list(packages.glob("*.whl"))
    if len(wheels) != 1 or wheels[0].name != "unaltraweb_mcp-0.7.1-py3-none-any.whl":
        raise RuntimeError("Unexpected candidate wheel inventory")
    dockerfile = ROOT / "packaging/practice-candidate/Dockerfile"
    shutil.copyfile(dockerfile, output / "Dockerfile")
    (output / ".dockerignore").write_text("*\n!Dockerfile\n!source.tar.gz\n!packages/\n!packages/*.whl\n")
    if shutil.disk_usage(output).free < base["size"] + 1024**3:
        raise RuntimeError("Insufficient free space for the bounded portable image export")
    run(["docker", "build", "--pull=false", "--network", "none", "--build-arg", "BASE_MCP_IMAGE=" + BASE,
                 "--build-arg", "SOURCE_SHA=" + SOURCE, "--iidfile", str(output / "image.id"),
                 "--file", str(output / "Dockerfile"), str(output)], timeout=600, log=output / "image-build.log")
    identifier = (output / "image.id").read_text().strip()
    candidate_image = image(identifier, identifier)
    if candidate_image["source_revision"] != SOURCE:
        raise RuntimeError("Built controller does not identify the approved source")
    exported = export_image(identifier, output / "controller.docker.tar.gz")
    contract = json.loads(run(["git", "show", SOURCE + ":src/unaltraweb_mcp/component-contract.json"]))
    checker_files = ("__init__.py", "distribution.py", "component-contract.schema.json", "artifact_imports.py",
                     "artifact_handoff_v1.py", "artifact-handoff-v1.schema.json", "letter_bundle.py", "pdf_probe.py", "processes.py")
    checker_hashes = {name: hashlib.sha256(run(["git", "show", SOURCE + ":src/unaltraweb_mcp/" + name]).encode()).hexdigest()
                      for name in checker_files}
    template_paths = ["scripts/manual/templates/practice.tex", "scripts/manual/templates/manual.tex",
                      "scripts/manual/filters/practice-layout.lua", "scripts/manual/filters/practice-finish.lua"]
    templates = {name: hashlib.sha256(run(["git", "show", SOURCE + ":" + name]).encode()).hexdigest() for name in template_paths}
    manifest = {"kind": "unaltraweb.practice-pdf-candidate", "schema_version": 1, "published": False,
                "candidate_id": "practice-pdf-98-" + SOURCE[:12], "source_revision": SOURCE,
                "package_version": "0.7.1", "version_note": "Post-release source candidate; select by these hashes, never as the published 0.7.1 wheel/image",
                "approved_review_pdf_sha256": APPROVED_PDF_SHA256, "template_hashes": templates,
                "source_archive": {"path": archive.name, "sha256": sha256(archive), "bytes": archive.stat().st_size},
                "wheel": {"path": "packages/" + wheels[0].name, "sha256": sha256(wheels[0]), "bytes": wheels[0].stat().st_size},
                "controller": candidate_image, "controller_base": base, "controller_archive": exported, "pdf_worker": pdf,
                "consumer_integration": contract["consumer_integration"], "checker_files": checker_hashes,
                "preparation": {"network": "none", "implicit_pull": False, "builder_sha256": sha256(__file__), "dockerfile_sha256": sha256(dockerfile)}}
    (output / "candidate.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (output / "install-requirements.txt").write_text(f"{wheels[0].resolve().as_uri()} --hash=sha256:{manifest['wheel']['sha256']}\n")
    print(json.dumps({"ok": True, "candidate": str(output / "candidate.json"), "candidate_sha256": sha256(output / "candidate.json"),
                      "controller_image_id": identifier, "wheel_sha256": manifest["wheel"]["sha256"]}, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.output)
