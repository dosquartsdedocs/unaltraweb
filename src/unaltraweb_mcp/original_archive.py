"""NEW private byte/provenance admission of one genuine original ZIP, without PDF.

Classification/limitations are caller selections, never original/native approval.
Original scripts, README and metadata are DATA. No execution/render/provider call.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sys
import uuid
import zipfile

from . import __version__, artifact_handoff_v1 as h, manual_pdf_preview as fs
from .artifact_publication import ArtifactPolicyError, canonical, consumer_repository, digest, shape
from .editorial_sources import yaml_mapping
from .retained_intake import opened, pin

ROOT = "sandbox/original-archives"
SCHEMA = "original-private-archive-v1.schema.json"
KIND = "unaltraweb-original-private-archive-receipt"
LIMIT = 1024**2
TRUTH = {"classification_origin": "caller-selection-not-original-seal", "byte_admission": "new-byte-crc-reference-check",
         "approved_by_admission": False, "native_reopen_verified": False, "scientific_validation_performed": False,
         "full_offline_qualified": False, "public_edition": False, "pdf_required": False, "scripts_executed": False}


def require(condition, code):
    if not condition:
        raise ArtifactPolicyError("original-archive-" + code, "Original private archive admission refused; inspect the exact selected pins, references and classification")


def copies(request, control):
    rows = [{"source": control["path"], "path": "local/request/" + Path(control["path"]).name, "sha256": control["sha256"], "bytes": control["bytes"]},
            {"source": request["archive"]["path"], "path": "files/" + Path(request["archive"]["path"]).name,
             "sha256": request["archive"]["sha256"], "bytes": request["archive"]["bytes"]}]
    for item in request["evidence"]:
        require(item["id"] != "request", "reserved-evidence-id")
        row = item["file"]
        rows.append({"source": row["path"], "path": "local/" + item["id"] + "/" + Path(row["path"]).name, "sha256": row["sha256"], "bytes": row["bytes"]})
    h.unique_paths([row["path"] for row in rows])
    require(sum(row["bytes"] for row in rows if row["path"].startswith("local/")) <= 8 * LIMIT, "metadata-budget")
    return rows


def inspect_zip(workspace, archive_pin, request, evidence):
    from .practice_editions import check_zip_directory, verify_zip_inventory
    with opened(workspace, archive_pin["path"]) as source:
        check_zip_directory(source)
        with zipfile.ZipFile(source) as archive:
            report = verify_zip_inventory(archive, None)
            members = report["observed_members"]
            require(bool(members), "empty")
            for row in request["member_references"]:
                h.safe_path(row["path"])
                require(row["path"] in members and row["sha256"] == members[row["path"]]["sha256"], "member-reference")
            checks = []
            for ref in request["checksums"]:
                if ref["base"]:
                    h.safe_path(ref["base"])
                if ref["source"] == "member":
                    require(ref["path"] in members and members[ref["path"]]["bytes"] <= LIMIT, "checksum-reference")
                    raw = archive.read(ref["path"])
                else:
                    require(ref["path"] in evidence, "checksum-reference")
                    raw = evidence[ref["path"]]
                sums = {}
                for line in raw.decode("utf-8").splitlines():
                    match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
                    require(match is not None, "checksum-format")
                    name = h.join(ref["base"], h.safe_path(match[2]))
                    h.safe_path(name)
                    require(name not in sums, "checksum-duplicate")
                    sums[name] = match[1]
                if ref["scope"] == "members":
                    require(bool(sums) and all(name in members and members[name]["sha256"] == sha for name, sha in sums.items()), "checksum-members")
                    count = len(sums)
                else:
                    require(sums.get(request["archive"]["path"]) == request["archive"]["sha256"], "checksum-archive")
                    count = 1
                checks.append({**ref, "declared_entries": len(sums), "checked_entries": count, "verification": "bytes-only-not-native-certificate"})
    return {"zip": report, "member_references": request["member_references"], "checksums": checks}


def plan(project: Path, request_path: str, sha256: str):
    fs._require_git_root(project)
    tracked, ignored = fs._git_state(project, Path(h.safe_path(request_path)))
    require(tracked and not ignored, "versioned-request")
    with closing(h.Workspace(str(project))) as workspace:
        actual, size, raw = workspace.read(request_path, LIMIT, collect=True)
        require(actual == sha256, "request-pin")
        request = h.parse_json(raw)
        shape(request, SCHEMA)
        repository = consumer_repository(project, request["consumer_repository"])
        destination = Path(h.safe_path(request["snapshot"]))
        require(destination.as_posix().startswith(ROOT + "/") and len(destination.parts) >= 4, "snapshot-namespace")
        fs._require_generated_path(project, destination, label="Original private archive")
        try:
            parent = fs._open_directory(workspace.fd, destination.parent)
        except FileNotFoundError:
            parent = None
        if parent is not None:
            try:
                try:
                    os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    require(False, "create-only")
            finally:
                os.close(parent)
        config_sha, _, raw = workspace.read("_config.yml", LIMIT, collect=True)
        site = yaml_mapping(raw.decode())
        from .practice_pdf import private_path_issues
        require(not private_path_issues(site), "privacy")
        language = request["classification"]["language"]
        require(language == "unknown" or language in (site.get("languages") or [site.get("default_lang") or site.get("lang") or "en"]), "language-selection")
        archive_pin = request["archive"]
        require(archive_pin["path"].endswith(".zip") and archive_pin["bytes"] > 0, "zip-selection")
        pin(workspace, archive_pin)
        evidence = {}
        for item in request["evidence"]:
            require(item["id"] not in evidence, "evidence-duplicate")
            row = item["file"]
            require(row["path"].endswith((".md", ".markdown", ".txt", ".json")) or Path(row["path"]).name == "SHA256SUMS", "metadata-selection")
            evidence[item["id"]] = pin(workspace, row, collect=True, limit=LIMIT)
            if row["path"].endswith(".json"):
                h.parse_json(evidence[item["id"]])
        control = {"path": request_path, "sha256": sha256, "bytes": size}
        rows = copies(request, control)
        checks = inspect_zip(workspace, archive_pin, request, evidence)
        workspace.recheck()
    from .runtime_identity import fingerprint
    code = fingerprint(Path(__file__).parent)
    require(code["available"], "producer-code")
    payload = {"kind": "unaltraweb-original-private-archive-plan", "schema_version": 1, "purpose": "private-archive",
               "request": control, "specification": request, "consumer_repository": repository, "site_config_sha256": config_sha,
               "copies": rows, "checks": checks, "truth": dict(TRUTH),
               "producer": {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + code["sha256"]}}
    require(len(canonical(payload)) <= 4 * LIMIT, "admission-budget")
    return {"ok": True, "read_only": True, "network": False, "credentials_resolved": False, "publishes": False,
            "plan_sha256": digest(canonical(payload)), "plan": payload}


def output_receipt(destination, admission_sha, identifier):
    return {"kind": KIND, "schema_version": 1, "purpose": "private-archive", "archive_id": identifier,
            "admission": {"path": destination + "/admission.json", "sha256": admission_sha}}


def snapshot(project, request_path, sha256, expected_plan_sha256):
    from .practice_editions import _copy_selected, write_new
    from .manual_release import _install_new_directory
    prepared = plan(project, request_path, sha256)
    require(prepared["plan_sha256"] == expected_plan_sha256, "reviewed-plan")
    payload = prepared["plan"]
    request = payload["specification"]
    relative = Path(request["snapshot"])
    admission = {"kind": "unaltraweb-original-private-archive-admission", "schema_version": 1, "purpose": "private-archive",
                 "snapshot": relative.as_posix(), "plan_sha256": expected_plan_sha256, "plan": payload}
    content = canonical(admission)
    admission_sha = digest(content)
    receipt = canonical(output_receipt(relative.as_posix(), admission_sha, request["archive_id"]))
    with closing(h.Workspace(str(project))) as workspace:
        parent = fs._open_directory(workspace.fd, relative.parent, create=True)
        name = ".archive-" + uuid.uuid4().hex
        os.mkdir(name, 0o700, dir_fd=parent)
        directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            for row in payload["copies"]:
                path = Path(row["path"])
                folder = fs._open_directory(directory, path.parent, create=True)
                try:
                    fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                    with os.fdopen(fd, "wb") as target:
                        _copy_selected(workspace, row, target)
                        target.flush()
                        os.fsync(target.fileno())
                    os.fsync(folder)
                finally:
                    os.close(folder)
            write_new(directory, "admission.json", content)
            write_new(directory, "receipt.json", receipt)
            require(plan(project, request_path, sha256) == prepared, "inputs-changed")
            fs._require_generated_path(project, relative, label="Original private archive")
            check = fs._open_directory(workspace.fd, relative.parent)
            try:
                require(fs._identity(os.fstat(check)) == fs._identity(os.fstat(parent)), "parent-changed")
            finally:
                os.close(check)
            os.fsync(directory)
            _install_new_directory(parent, name, relative.name)
            os.fsync(parent)
        finally:
            os.close(directory)
            os.close(parent)
    receipt_path = relative.as_posix() + "/receipt.json"
    with closing(h.Workspace(str(project))) as workspace:
        artifact(workspace, project, receipt_path, digest(receipt))
    return {"ok": True, "publishes": False, "snapshot": relative.as_posix(), "plan_sha256": expected_plan_sha256,
            "admission_sha256": admission_sha, "receipt": receipt_path, "receipt_sha256": digest(receipt), "truth": dict(TRUTH),
            "classification": request["classification"]}


def artifact(workspace, project, path, expected):
    actual, _, raw = workspace.read(path, LIMIT, collect=True)
    require(actual == expected, "receipt-pin")
    receipt = h.parse_json(raw)
    require(set(receipt) == {"kind", "schema_version", "purpose", "archive_id", "admission"} and receipt["kind"] == KIND
            and type(receipt["schema_version"]) is int and receipt["schema_version"] == 1 and receipt["purpose"] == "private-archive", "receipt-format")
    base = Path(path).parent.as_posix()
    require(base.startswith(ROOT + "/") and path == base + "/receipt.json" and receipt["admission"]["path"] == base + "/admission.json", "receipt-namespace")
    fs._require_generated_path(project, Path(base), label="Original private archive admission")
    group_sha, _, raw = workspace.read(base + "/admission.json", 8 * LIMIT, collect=True)
    require(group_sha == receipt["admission"]["sha256"], "admission-pin")
    group = h.parse_json(raw)
    require(group.get("kind") == "unaltraweb-original-private-archive-admission" and type(group.get("schema_version")) is int
            and group["schema_version"] == 1 and group.get("purpose") == "private-archive" and group.get("snapshot") == base, "admission-format")
    payload, request = group["plan"], group["plan"]["specification"]
    shape(request, SCHEMA)
    require(digest(canonical(payload)) == group["plan_sha256"] and payload["truth"] == TRUTH
            and request["snapshot"] == base and request["archive_id"] == receipt["archive_id"], "lineage")
    expected_copies = copies(request, payload["request"])
    require(expected_copies == payload["copies"], "copy-lineage")
    for row in expected_copies:
        pin(workspace, {"path": base + "/" + row["path"], "sha256": row["sha256"], "bytes": row["bytes"]})
    control = expected_copies[0]
    _, _, raw_request = workspace.read(base + "/" + control["path"], LIMIT, collect=True)
    require(h.parse_json(raw_request) == request and digest(raw_request) == payload["request"]["sha256"], "request-lineage")
    require(all(payload["consumer_repository"].get(key) == value for key, value in request["consumer_repository"].items()), "repository-lineage")
    evidence = {}
    for item in request["evidence"]:
        row = next(row for row in expected_copies if row["path"].startswith("local/" + item["id"] + "/"))
        require(item["id"] not in evidence, "evidence-lineage")
        _, _, evidence[item["id"]] = workspace.read(base + "/" + row["path"], LIMIT, collect=True)
    source = base + "/files/" + Path(request["archive"]["path"]).name
    checks = inspect_zip(workspace, {**request["archive"], "path": source}, request, evidence)
    require(checks == payload["checks"], "member-lineage")
    require(receipt == output_receipt(base, group_sha, request["archive_id"]), "receipt-lineage")
    files, _ = workspace.inventory(base)
    require(files == {"admission.json", "receipt.json", *[row["path"] for row in expected_copies]}, "snapshot-inventory")
    workspace.recheck()
    return {"source": source, "row": {"path": Path(source).name, "sha256": request["archive"]["sha256"], "bytes": request["archive"]["bytes"]},
            "classification": request["classification"], "archive_id": request["archive_id"], "consumer_repository": payload["consumer_repository"], "truth": dict(TRUTH)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "snapshot"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.operation == "plan":
            require(not args.expected_plan_sha256, "plan-options")
            result = plan(args.project, args.request, args.sha256)
        else:
            require(args.expected_plan_sha256, "reviewed-plan-required")
            result = snapshot(args.project, args.request, args.sha256, args.expected_plan_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except ArtifactPolicyError as exc:
        print(json.dumps({"ok": False, "publishes": False, "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError, StopIteration, RuntimeError, h.HandoffError, zipfile.BadZipFile):
        print(json.dumps({"ok": False, "publishes": False, "error": {"code": "original-archive-refused", "message": "Original archive operation refused; inspect exact pins and local evidence"}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
