"""Closed practice artifacts, routed individually to GitHub Releases or S3/S4.

Adopts gaContExt product/publication v1. Destination selection is outside product
identity. Native practice receipts remain private; only selected output bytes
and a source-free metadata sidecar travel. Planning never resolves credentials.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid

from . import __version__, artifact_handoff_v1 as h, manual_pdf_preview as fs
from .editorial_sources import strict_json

CONFIG = ".unaltraweb/practice-artifacts.json"
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE = 2 * 1024**3 - 1


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    # Exact gaContExt v1 canonical representation, including its final newline.
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def shape(value, name):
    rules = strict_json(Path(__file__).with_name(name).read_text())
    h.check_shape(value, rules, rules.get("$defs", {}))
    return rules


def publication_policy(value):
    rules = shape(value, "publication-policy-v1.schema.json")
    targets = value["targets"]
    require(1 <= len(targets) <= 32 and value["default_target"] in targets, "Invalid publication targets/default")
    for name, target in targets.items():
        require(TOKEN.fullmatch(name), "Invalid publication target name")
        driver = target.get("driver") if isinstance(target, dict) else None
        require(driver in {"github-release", "s3"}, "Unknown publication driver")
        h.check_shape(target, rules["$defs"]["github" if driver == "github-release" else "s3"], rules["$defs"])
        require(len(target["audiences"]) == len(set(target["audiences"])), "Duplicate target audience")
        require(target["visibility"] != "public" or not set(target["audiences"]) & {"private", "teacher"},
                "Public targets cannot accept private/teacher artifacts")
        if driver == "s3":
            endpoint = urlsplit(target["endpoint"])
            require(endpoint.scheme == "https" and endpoint.hostname and not endpoint.username and not endpoint.password
                    and endpoint.path in {"", "/"} and not endpoint.query and not endpoint.fragment and endpoint.port != 0
                    and not any(char.isspace() or ord(char) < 32 for char in target["endpoint"]),
                    "S3 endpoint must be a credential-free HTTPS origin")
            require(not re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", target["bucket"])
                    and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", part) for part in target["bucket"].split(".")),
                    "Invalid S3 bucket namespace")
            h.safe_path(target["prefix"])
    return value


def load(project, config, expected):
    require(project.is_absolute(), "Select an absolute consumer workspace")
    fs._require_git_root(project)
    tracked, ignored = fs._git_state(project, Path(h.safe_path(config)))
    require(tracked and not ignored, "Artifact routing must be a versioned, non-ignored project source")
    with closing(h.Workspace(str(project))) as workspace:
        sha, _, raw = workspace.read(config, 1024**2, collect=True)
        require(isinstance(expected, str) and HASH.fullmatch(expected) and sha == expected, "Artifact routing differs from its reviewed SHA-256")
        value = strict_json(raw.decode())
        require(isinstance(value, dict) and set(value) == {"kind", "schema_version", "publication", "artifacts"}
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "unaltraweb.practice-artifact-storage", "Unsupported practice artifact routing schema")
        require(isinstance(value["artifacts"], dict) and len(value["artifacts"]) <= 256, "Invalid bounded artifact selection")
        if value["publication"] is None:
            require(not value["artifacts"], "Unconfigured publication cannot route artifacts")
        else:
            publication_policy(value["publication"])
        for name, route in value["artifacts"].items():
            require(TOKEN.fullmatch(name), "Invalid logical artifact ID")
            require(isinstance(route, dict) and set(route) == {"target", "audience", "receipt", "receipt_sha256", "format"}, "Unknown artifact routing fields")
            require(route["target"] in value["publication"]["targets"], "Artifact must select one configured target; no fallback")
            target = value["publication"]["targets"][route["target"]]
            require(route["audience"] in target["audiences"], "Artifact audience is not admitted by its target")
            require(route["format"] in {"zip", "pdf"} and isinstance(route["receipt_sha256"], str)
                    and HASH.fullmatch(route["receipt_sha256"]), "Invalid artifact format/receipt pin")
            h.safe_path(route["receipt"])
        workspace.recheck()
    return value


def plan(project: Path, config: str, sha256: str, artifact: str):
    selection = load(project, config, sha256)
    require(artifact in selection["artifacts"], "Artifact has no explicit storage policy")
    route = selection["artifacts"][artifact]
    from .editorial_sources import yaml_mapping
    with closing(h.Workspace(str(project))) as workspace:
        actual, _, raw = workspace.read(route["receipt"], 1024**2, collect=True)
        require(actual == route["receipt_sha256"], "Native practice receipt differs from its selected seal")
        receipt = strict_json(raw.decode())
        require(isinstance(receipt, dict) and receipt.get("kind") == "unaltraweb-practice-edition-receipt" and type(receipt.get("schema_version")) is int
                and receipt["schema_version"] == 1 and receipt.get("recipient") in {"alumnat", "docent"}, "Select a native practice edition receipt")
        require(receipt["recipient"] != "docent" or route["audience"] in {"teacher", "private"}, "Teacher artifacts cannot be reclassified as student/public")
        require(receipt["recipient"] != "alumnat" or route["audience"] in {"student", "public", "private"}, "Student artifact audience differs from its native recipient")
        for key in ("slug", "version", "language"):
            h.safe_path(receipt[key])
        parent = Path("dist/practiques") / receipt["slug"] / receipt["version"] / receipt["language"]
        require(Path(route["receipt"]).parent == parent, "Practice receipt is outside its exact retained edition")
        fs._require_generated_path(project, parent, label="Retained native practice edition")
        row = receipt["zip"] if route["format"] == "zip" else receipt["reading"]["delivery"]
        h.safe_path(row["path"])
        require(Path(row["path"]).name == row["path"] and row["path"].endswith("." + route["format"]), "Invalid native delivery filename")
        require(Path(route["receipt"]).name == receipt["zip"]["path"] + ".receipt.json", "Receipt filename differs from native ZIP seal")
        source = (parent / row["path"]).as_posix()
        actual, size, _ = workspace.read(source, MAX_FILE)
        require(type(row["bytes"]) is int and (actual, size) == (row["sha256"], row["bytes"]), "Practice artifact bytes differ from their native seal")
        _, _, site_raw = workspace.read("_config.yml", 1024**2, collect=True)
        site = yaml_mapping(site_raw.decode())
        from .practice_pdf import private_path_issues
        issues = private_path_issues(site)
        require(not issues, "; ".join(issues))
        workspace.recheck()
    target = selection["publication"]["targets"][route["target"]]
    metadata = canonical({"kind": "unaltraweb.practice-artifact", "schema_version": 1, "artifact_id": artifact,
                          **{key: receipt[key] for key in ("slug", "version", "language", "recipient")},
                          "format": route["format"], "native_receipt_sha256": route["receipt_sha256"]})
    from .runtime_identity import fingerprint
    code = fingerprint(Path(__file__).parent)
    require(code["available"], "Producer package code cannot be fingerprinted safely")
    manifest = {"kind": "gacontext.product-manifest", "schema_version": 1,
                "producer": {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + code["sha256"]},
                "project_id": selection["publication"]["project_id"], "product_id": artifact, "audience": route["audience"],
                "files": [{"path": row["path"], "bytes": size, "sha256": actual, "role": "output",
                           "media_type": "application/zip" if route["format"] == "zip" else "application/pdf"},
                          {"path": "artifact.json", "bytes": len(metadata), "sha256": digest(metadata), "role": "evidence", "media_type": "application/json"}],
                "native": {"format": "unaltraweb-practice-artifact-v1", "manifest_sha256": digest(metadata)}}
    shape(manifest, "product-publication-v1.schema.json")
    content = canonical(manifest)
    return {"ok": True, "read_only": True, "publication_performed": False, "credentials_resolved": False,
            "artifact_id": artifact, "config_sha256": sha256, "manifest_sha256": digest(content),
            "publication": {"target_name": route["target"], "destination": target, "destination_sha256": digest(canonical(target)),
                            "policy_sha256": digest(canonical(selection["publication"]))},
            "manifest": manifest, "metadata": metadata.decode(), "source": source}


def stage(project: Path, config: str, sha256: str, artifact: str, destination: str):
    from .practice_editions import _copy_selected, write_new
    from .manual_release import _install_new_directory
    prepared = plan(project, config, sha256, artifact)
    path = Path(h.safe_path(destination))
    require(path.as_posix().startswith("sandbox/artifacts/") and len(path.parts) >= 4, "Artifact staging requires sandbox/artifacts/<id>/<run>")
    fs._require_generated_path(project, path, label="Practice artifact stage")
    with closing(h.Workspace(str(project))) as workspace:
        parent = fs._open_directory(workspace.fd, path.parent, create=True)
        stage_name = ".artifact-" + uuid.uuid4().hex
        os.mkdir(stage_name, mode=0o700, dir_fd=parent)
        directory = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            row = prepared["manifest"]["files"][0]
            fd = os.open(row["path"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as output:
                _copy_selected(workspace, {**row, "source": prepared["source"]}, output)
                output.flush()
                os.fsync(output.fileno())
            write_new(directory, "artifact.json", prepared["metadata"].encode())
            write_new(directory, "product.json", canonical(prepared["manifest"]))
            require(plan(project, config, sha256, artifact) == prepared, "Artifact source/policy changed during staging")
            workspace.recheck()
            fs._require_generated_path(project, path, label="Practice artifact stage")
            check = fs._open_directory(workspace.fd, path.parent)
            try:
                require(fs._identity(os.fstat(parent)) == fs._identity(os.fstat(check)), "Artifact stage parent changed")
            finally:
                os.close(check)
            os.fsync(directory)
            _install_new_directory(parent, stage_name, path.name)
            os.fsync(parent)
        finally:
            # Failed stages remain available for diagnosis; no cleanup is authorised.
            os.close(directory)
            os.close(parent)
    return {**prepared, "read_only": False, "stage": path.as_posix()}


def transfer(project, config, sha256, artifact, staged, manifest_sha256, *, auth_file=None, verify_only=False, connector=None):
    prepared = plan(project, config, sha256, artifact)
    require(prepared["manifest_sha256"] == manifest_sha256, "Staged manifest differs from the reviewed artifact plan")
    staged = h.safe_path(staged)
    require(staged.startswith("sandbox/artifacts/"), "Select a retained artifact stage")
    fs._require_generated_path(project, Path(staged), label="Retained practice artifact stage")
    with closing(h.Workspace(str(project))) as workspace:
        actual, _, raw = workspace.read(staged + "/product.json", 1024**2, collect=True)
        require(actual == manifest_sha256 and raw == canonical(prepared["manifest"]), "Staged product manifest changed")
        files, directories = workspace.inventory(staged)
        require(not directories and files == {"product.json", *[row["path"] for row in prepared["manifest"]["files"]]}, "Unexpected staged artifact files")
        records = [*prepared["manifest"]["files"], {"path": "product.json", "sha256": actual, "bytes": len(raw), "media_type": "application/json", "role": "evidence"}]
        for row in records:
            actual, size, _ = workspace.read(staged + "/" + row["path"], MAX_FILE)
            require((actual, size) == (row["sha256"], row["bytes"]), "Staged artifact changed before transfer")
        from .artifact_transports import connect
        store = (connector or connect)(prepared["publication"], prepared["manifest"]["project_id"], auth_file)
        observations = []
        try:
            store.preflight()
            for row in records:
                with workspace.directory(staged) as directory:
                    descriptor = os.open(row["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                    with os.fdopen(descriptor, "rb") as source:
                        require(h.signature(os.fstat(descriptor)) == workspace.snapshots[staged + "/" + row["path"]],
                                "Staged artifact changed before its transfer descriptor was opened")
                        observation = store.transfer(prepared["manifest"], manifest_sha256, row, source, write=not verify_only)
                require(observation.get("verified") is True, "Provider did not verify artifact readback")
                observations.append({**row, **observation})
            workspace.recheck()
            require(plan(project, config, sha256, artifact) == prepared, "Artifact routing/source changed during transfer")
        finally:
            store.close()
    return {"ok": True, "kind": "unaltraweb.practice-artifact-receipt", "schema_version": 1,
            "artifact_id": artifact, "project_id": prepared["manifest"]["project_id"], "audience": prepared["manifest"]["audience"],
            "config_sha256": sha256, "manifest_sha256": manifest_sha256, **prepared["publication"],
            "verified": True, "publication_performed": not verify_only, "catalogue_updated": False, "files": observations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "stage", "publish", "verify"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--sha256", required=True, help="Reviewed routing configuration SHA-256")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--stage", help="Project-relative, retained sandbox/artifacts/<id>/<run>")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--auth-file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation in {"plan", "stage"}:
            require(not args.auth_file and not args.manifest_sha256, "Planning/staging does not resolve credentials")
            if args.operation == "stage":
                require(args.stage, "stage requires --stage")
                result = stage(args.project, args.config, args.sha256, args.artifact, args.stage)
            else:
                require(not args.stage, "plan does not create a stage")
                result = plan(args.project, args.config, args.sha256, args.artifact)
        else:
            require(args.stage and args.manifest_sha256 and args.auth_file, "Transfers require --stage, --manifest-sha256 and explicit --auth-file")
            result = transfer(args.project, args.config, args.sha256, args.artifact, args.stage, args.manifest_sha256,
                              auth_file=args.auth_file, verify_only=args.operation == "verify")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, h.HandoffError, RuntimeError):
        # Provider responses and local credential paths must never enter diagnostics.
        print(json.dumps({"ok": False, "error": "Artifact operation refused; inspect the exact sources, policy and provider. No fallback or catalogue update."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
