"""Explicit, pinned input hydration before freshness checks; never render or publish.

The immutable-github-files-v1 adapter accepts the existing TIGIT resource
inventory shape. It interprets data, never a consumer preparer/command. Domain
preparation, workbooks and GIS execution remain with their original owners.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote
import urllib.request
import uuid

from . import artifact_handoff_v1 as h, manual_pdf_preview as fs
from .editorial_sources import Reader, canonical, digest, yaml_mapping
from .manual_release import _install_new_directory

SCHEMA = Path(__file__).with_name("input-preparation-v1.schema.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _source(project, reader, path, expected):
    h.safe_path(path)
    tracked, ignored = fs._git_state(project, Path(path))
    require(tracked and not ignored, "Preparation controls/manifests must be versioned, non-ignored sources")
    raw = reader.read(path)
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) and digest(raw) == expected,
            "Preparation source differs from its reviewed SHA-256")
    return raw


def inventory(value):
    fields = {"schema_version", "kind", "version", "source_commit", "source_prefix", "source_url", "snapshot", "files"}
    require(isinstance(value, dict) and set(value) == fields and type(value["schema_version"]) is int and value["schema_version"] == 1,
            "Unsupported immutable-github-files-v1 resource manifest")
    require(all(isinstance(value[key], str) for key in fields - {"schema_version", "files"}), "Resource manifest metadata must be strings")
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,79}", value["kind"]) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value["version"]), "Invalid resource provenance kind/version")
    require(re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]), "Resource origin must be a full immutable Git commit")
    prefix = value["source_prefix"]
    require(prefix.endswith("/"), "Immutable source_prefix must end with a slash")
    h.safe_path(prefix[:-1])
    origin = re.fullmatch(r"https://raw\.githubusercontent\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/([0-9a-f]{40})/(.+/)", value["source_url"])
    require(origin and origin[3] == value["source_commit"] and origin[4] == quote(prefix, safe="/-._~")
            and all(part not in {".", ".."} for part in origin.groups()[:2]), "Resource URL must bind that exact public GitHub commit/prefix")
    h.safe_path(value["snapshot"])
    require(value["snapshot"].startswith("sandbox/practiques/") and len(Path(value["snapshot"]).parts) >= 4,
            "Input snapshots must stay beneath ignored sandbox/practiques/<slug>/<run>")
    files = value["files"]
    require(isinstance(files, list) and 1 <= len(files) <= 512, "Resource files must be a bounded explicit inventory")
    for row in files:
        require(isinstance(row, dict) and set(row) == {"path", "sha256", "bytes"}, "Resource file requires path, SHA-256 and bytes")
        h.safe_path(row["path"])
        require(row["path"] != "input-preparation.json", "Resource collides with the preparation receipt")
        require(isinstance(row["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                and type(row["bytes"]) is int and 0 < row["bytes"] <= h.MAX_FILE_BYTES, "Invalid bounded resource SHA-256/size")
    h.unique_paths([row["path"] for row in files])
    require(sum(row["bytes"] for row in files) <= h.MAX_TOTAL_BYTES, "Input snapshot exceeds the total byte budget")
    return value


def load(project, config, expected):
    fs._require_git_root(project)
    with Reader(project) as reader:
        raw = _source(project, reader, config, expected)
        value = yaml_mapping(raw.decode())
        rules = h.parse_json(SCHEMA.read_bytes())
        h.check_shape(value, rules, rules["$defs"])
        site = yaml_mapping(reader.text("_config.yml"))
        resources = []
        for item in value["resources"]:
            resource_raw = _source(project, reader, item["manifest"], item["sha256"])
            resources.append({"declaration": item, "inventory": inventory(yaml_mapping(resource_raw.decode()))})
    if resources:
        excluded, included = site.get("exclude", []), site.get("include", [])
        require(isinstance(excluded, list) and isinstance(included, list), "Jekyll include/exclude must be lists")
        require({"practiques", "sandbox", "dist"} <= {item.rstrip("/") for item in excluded if isinstance(item, str)},
                "Preparation requires private practiques/sandbox/dist Jekyll exclusions")
        for item in included:
            if isinstance(item, str):
                require(item != "." and not any(fnmatch.fnmatchcase(root, item.strip("/").split("/")[0])
                        or fnmatch.fnmatchcase(root + "/input.csv", item) for root in ("practiques", "sandbox", "dist")),
                        "Jekyll include exposes prepared/private inputs")
        h.unique_paths([item["inventory"]["snapshot"] for item in resources])
        require(sum(row["bytes"] for item in resources for row in item["inventory"]["files"]) <= h.MAX_TOTAL_BYTES,
                "Preparation exceeds the total byte budget")
        for item in resources:
            fs._require_generated_path(project, Path(item["inventory"]["snapshot"]), label="Prepared inputs")
    return resources


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Pinned input preparation refuses redirects and fallback origins")


def fetch(url):
    # No cookies, tokens or private hub/host credential lookup.
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(urllib.request.Request(url, headers={"Accept-Encoding": "identity"}), timeout=30)


def _snapshot_current(workspace, resource):
    try:
        with workspace.directory(resource["snapshot"]):
            pass
    except FileNotFoundError:
        return False
    for row in resource["files"]:
        actual, size, _ = workspace.read(resource["snapshot"] + "/" + row["path"], h.MAX_FILE_BYTES)
        require((actual, size) == (row["sha256"], row["bytes"]), "Existing input snapshot is incomplete or changed; preserve it and select a new run")
    return True


def prepare(project: Path, config: str, sha256: str, *, allow_fetch=False, check_only=False, opener=fetch):
    require(project.is_absolute(), "Input preparation requires an explicit absolute project root")
    resources = load(project, config, sha256)
    result = {"ok": True, "publishes": False, "renders": False, "schema_version": 1, "snapshots": []}
    with closing(h.Workspace(str(project))) as workspace:
        # Preflight every existing snapshot before acquiring any missing input.
        current = [_snapshot_current(workspace, item["inventory"]) for item in resources]
        if not all(current):
            require(allow_fetch and not check_only, "Prepared inputs are absent; pass explicit --fetch before freshness checks")
        for item, exists in zip(resources, current):
            resource = item["inventory"]
            path = Path(resource["snapshot"])
            if not exists:
                parent = fs._open_directory(workspace.fd, path.parent, create=True)
                stage_name = ".inputs-" + uuid.uuid4().hex
                os.mkdir(stage_name, mode=0o700, dir_fd=parent)
                stage = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    for row in resource["files"]:
                        relative = Path(row["path"])
                        folder = fs._open_directory(stage, relative.parent, create=True)
                        try:
                            target_fd = os.open(relative.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                        finally:
                            os.close(folder)
                        with os.fdopen(target_fd, "wb") as output, closing(opener(resource["source_url"] + quote(row["path"], safe="/-._~"))) as response:
                            hasher, size = hashlib.sha256(), 0
                            while piece := response.read(65536):
                                size += len(piece)
                                require(size <= row["bytes"], "Fetched input exceeds its pinned byte count")
                                hasher.update(piece)
                                output.write(piece)
                            require((hasher.hexdigest(), size) == (row["sha256"], row["bytes"]), "Fetched input SHA-256/size differs; no fallback")
                            output.flush()
                            os.fsync(output.fileno())
                    receipt = canonical({"schema_version": 1, "kind": "unaltraweb-input-preparation-receipt", "publishes": False,
                                         "config": {"path": config, "sha256": sha256}, "manifest": item["declaration"], "inventory": resource})
                    fd = os.open("input-preparation.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stage)
                    with os.fdopen(fd, "wb") as output:
                        output.write(receipt)
                        output.flush()
                        os.fsync(output.fileno())
                    require(load(project, config, sha256) == resources, "Preparation controls changed during acquisition")
                    fs._require_generated_path(project, path, label="Prepared inputs")
                    check_parent = fs._open_directory(workspace.fd, path.parent)
                    try:
                        require(fs._identity(os.fstat(parent)) == fs._identity(os.fstat(check_parent)), "Preparation parent changed")
                    finally:
                        os.close(check_parent)
                    _install_new_directory(parent, stage_name, path.name)
                    os.fsync(parent)
                finally:
                    # Partial attempts are retained; no cleanup permission is implied.
                    os.close(stage)
                    os.close(parent)
            result["snapshots"].append({"path": path.as_posix(), "state": "current" if exists else "prepared",
                                       "files": len(resource["files"]), "bytes": sum(row["bytes"] for row in resource["files"])})
        workspace.recheck()
    # New bytes are independently read back with descriptor-relative validation.
    with closing(h.Workspace(str(project))) as workspace:
        require(all(_snapshot_current(workspace, item["inventory"]) for item in resources), "Prepared input readback failed")
        workspace.recheck()
    require(load(project, config, sha256) == resources, "Preparation controls changed before completion")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(not (args.fetch and args.check), "Select --fetch or --check, not both")
        result = prepare(args.project, args.config, args.sha256, allow_fetch=args.fetch, check_only=args.check)
    except (ValueError, OSError, RuntimeError, h.HandoffError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "publishes": False}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
