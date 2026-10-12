#!/usr/bin/env python3
"""Export two prepared images for the hub's existing Docker-save loader.

No build, pull, load, retag, installation or resource manager is implemented here.
The existing bounded exporter is reused; PDF provenance comes from its own BOM
record rather than the controller's source commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts.prepare_practice_candidate import export_image, image, sha256
from unaltraweb_mcp.distribution import distribution_contract
from unaltraweb_mcp.runtime_lifecycle import IMAGE_ID, immutable_reference


def verify_archive(path, expected_id, expected_source):
    """Inspect only Docker-save metadata/config; never extract or load layers."""
    with tarfile.open(path, "r:gz") as archive:
        records = archive.getmembers()
        by_name = {entry.name: entry for entry in records}
        if len(records) != len(by_name) or len(records) > 10000:
            raise ValueError("Docker-save archive inventory is ambiguous or excessive")
        def small_json(name):
            entry = by_name.get(name)
            if entry is None or not entry.isfile() or entry.size > 2*1024*1024:
                raise ValueError("Docker-save metadata is missing or invalid")
            with archive.extractfile(entry) as stream:
                raw = stream.read()
            return json.loads(raw), raw
        manifest, _ = small_json("manifest.json")
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise ValueError("Expected one immutable image per Docker-save archive")
        item = manifest[0]
        if item.get("RepoTags"):
            raise ValueError("Export by configuration ID only; archive must not reassign tag aliases")
        config, raw = small_json(item.get("Config"))
        if "sha256:" + hashlib.sha256(raw).hexdigest() != expected_id:
            raise ValueError("Docker-save config bytes differ from the expected image ID")
        if config.get("config", {}).get("Labels", {}).get("org.opencontainers.image.revision") != expected_source:
            raise ValueError("Docker-save image producer differs from its own expected source")
        if (config.get("os"), config.get("architecture")) != ("linux", "amd64"):
            raise ValueError("Archive must retain the selected Linux/amd64 platform")
        for name in item.get("Layers", []):
            if name not in by_name or not by_name[name].isfile():
                raise ValueError("Docker-save layer is missing")
    return {"config_id": expected_id, "source_revision": expected_source, "repo_tags": []}


def write_new(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare(output, controller_reference, controller_id, controller_source, pdf_id, *, controller_archive=None, controller_archive_sha256=None):
    output = Path(output).absolute()
    if (output.resolve() != output or not any(output.is_relative_to(root) for root in (ROOT / "tmp", Path("/tmp/opencode")))
            or not output.parent.is_dir()):
        raise ValueError("Select a new non-symlink export directory under factory tmp/ or /tmp/opencode/")
    if os.path.lexists(output):
        raise FileExistsError("Runtime archive delivery already exists")
    if not immutable_reference(controller_reference) or not IMAGE_ID.fullmatch(controller_id) or not IMAGE_ID.fullmatch(pdf_id):
        raise ValueError("Select immutable image references and full expected configuration IDs")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|sha256:[0-9a-f]{64})", controller_source):
        raise ValueError("Controller source must be its exact Git or sealed snapshot identity")
    if bool(controller_archive) != bool(controller_archive_sha256):
        raise ValueError("Reusing a controller archive requires its exact SHA-256")
    contract = distribution_contract()
    pdf_reference = contract["consumer_integration"]["manual_pdf_image"]
    producers = [row["producer_sha"] for row in contract["deployment_contract"]["manual_pdf_workers"] if row["reference"] == pdf_reference]
    if len(producers) != 1:
        raise ValueError("Selected PDF needs one provider-owned producer record")
    selected = {"controller": image(controller_reference, controller_id), "manual_pdf": image(pdf_reference, pdf_id)}
    if selected["controller"]["source_revision"] != controller_source or selected["manual_pdf"]["source_revision"] != producers[0]:
        raise ValueError("Prepared controller/PDF does not match its own producer")
    if controller_archive:
        controller_archive = Path(controller_archive)
        if controller_archive.is_symlink() or sha256(controller_archive) != controller_archive_sha256:
            raise ValueError("Retained controller archive hash differs")
        verify_archive(controller_archive, controller_id, controller_source)
    if shutil.disk_usage(output.parent).free < sum(item["size"] for item in selected.values()) + 256*1024*1024:
        raise RuntimeError("Insufficient space for the bounded archive export")
    output.mkdir(mode=0o755)
    exported = {}
    for role, observed in selected.items():
        destination = output / ("controller.docker.tar.gz" if role == "controller" else "manual-pdf.docker.tar.gz")
        if role == "controller" and controller_archive:
            with controller_archive.open("rb") as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target, 1024*1024)
                target.flush()
                os.fsync(target.fileno())
            if sha256(destination) != controller_archive_sha256:
                raise ValueError("Copied controller archive differs")
            record = {"path": destination.name, "sha256": controller_archive_sha256, "bytes": destination.stat().st_size,
                      "format": "docker-save-gzip", "reused_exact_bytes": True}
        else:
            record = export_image(observed["image_id"], destination)
        archive_identity = verify_archive(destination, observed["image_id"], observed["source_revision"])
        exported[role] = {"archive": record, "image": observed, "archive_identity": archive_identity,
                          "offline_selection": {"reference": observed["image_id"], "expected_image_id": observed["image_id"]}}
    manifest = {"schema_version": 1, "kind": "unaltraweb-practice-runtime-archives", "published": False, "images": exported,
                "loading": "Existing hub H2 Docker-save loader; no Web loader or alias mutation",
                "digest_note": "Registry digests are pre-export observations, not a claim that docker load restores RepoDigests."}
    write_new(output / "runtime-archives.json", manifest)
    files = [{"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(output.iterdir())]
    write_new(output / "ready.json", {"schema_version": 1, "kind": "unaltraweb-runtime-archives-ready", "ready": True,
                                      "manifest": "runtime-archives.json", "files": files, "published": False})
    for row in files:
        if sha256(output / row["path"]) != row["sha256"]:
            raise ValueError("Runtime archive delivery changed before handoff")
    return {"ok": True, "ready": str(output / "ready.json"), "sha256": sha256(output / "ready.json"), "images": exported}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controller-image", required=True)
    parser.add_argument("--controller-id", required=True)
    parser.add_argument("--controller-source", required=True)
    parser.add_argument("--pdf-id", required=True)
    parser.add_argument("--controller-archive", type=Path)
    parser.add_argument("--controller-archive-sha256")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.controller_image, args.controller_id, args.controller_source, args.pdf_id,
                             controller_archive=args.controller_archive, controller_archive_sha256=args.controller_archive_sha256), indent=2))
