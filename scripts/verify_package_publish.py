#!/usr/bin/env python3
"""Authorize and stage exact language-package release candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SEMVER_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
PACKAGE_WORKFLOW = ".github/workflows/package-prepare.yml"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"{label} must be a regular file")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            _require(key not in result, f"{label} contains duplicate JSON key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} contains non-finite JSON value {value}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    _require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def release_packages(receipt_path: Path, release_tag: str, receipt_sha256: str) -> dict[str, str]:
    match = SEMVER_TAG.fullmatch(release_tag)
    _require(match is not None, "release tag must be exact vX.Y.Z semver")
    _require(SHA256.fullmatch(receipt_sha256) is not None, "receipt SHA-256 must be lowercase hexadecimal")
    _require(receipt_path.is_file() and not receipt_path.is_symlink(),
             "release receipt must be a regular file")
    _require(_sha256(receipt_path) == receipt_sha256, "release receipt SHA-256 does not match the request")
    version = release_tag.removeprefix("v")
    receipt = _load_object(receipt_path, "release receipt")
    _require(set(receipt) == {"schema_version", "release", "source_commit", "components"},
             "release receipt has unexpected fields")
    _require(receipt.get("schema_version") == 1, "release receipt schema_version must be 1")
    _require(receipt.get("release") == release_tag, "release receipt tag does not match the request")
    source_commit = receipt.get("source_commit")
    _require(isinstance(source_commit, str) and FULL_SHA.fullmatch(source_commit) is not None,
             "release receipt source_commit must be a full lowercase SHA")
    components = receipt.get("components")
    _require(isinstance(components, dict), "release receipt components must be an object")

    expected_names = {
        "gem": f"unaltraweb-{version}.gem",
        "wheel": f"unaltraweb_mcp-{version}-py3-none-any.whl",
    }
    result = {
        "version": version,
        "source_commit": source_commit,
    }
    for component, expected_name in expected_names.items():
        candidate = components.get(component)
        _require(isinstance(candidate, dict), f"release receipt has no {component} candidate")
        _require(set(candidate) == {"artifact", "sha256"},
                 f"release receipt {component} candidate has unexpected fields")
        _require(candidate.get("artifact") == expected_name,
                 f"release receipt {component} artifact does not match version {version}")
        digest = candidate.get("sha256")
        _require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
                 f"release receipt {component} sha256 must be lowercase hexadecimal")
        result[f"{component}_artifact"] = expected_name
        result[f"{component}_sha256"] = digest
    return result


def _git(repository_dir: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def validate_release_checkout(
    repository_dir: Path,
    receipt_path: Path,
    release_tag: str,
    tag_object: str,
    receipt_sha256: str,
    default_branch: str,
) -> dict[str, str]:
    _require(repository_dir.is_dir() and not repository_dir.is_symlink(),
             "release checkout must be a real directory")
    _require(receipt_path.parent.resolve() == repository_dir.resolve(),
             "release receipt must be at the checkout root")
    _require(FULL_SHA.fullmatch(tag_object) is not None, "tag object must be a full lowercase SHA")
    packages = release_packages(receipt_path, release_tag, receipt_sha256)
    tag_ref = f"refs/tags/{release_tag}"
    _require(_git(repository_dir, "cat-file", "-t", tag_ref) == "tag",
             "release reference must be an annotated tag")
    _require(_git(repository_dir, "rev-parse", tag_ref) == tag_object,
             "release tag object does not match the reviewed request")
    release_commit = _git(repository_dir, "rev-parse", f"{tag_ref}^{{commit}}")
    _require(_git(repository_dir, "rev-parse", "HEAD") == release_commit,
             "release checkout does not match the tag target")
    _git(
        repository_dir,
        "diff",
        "--exit-code",
        "HEAD",
        "--",
        "release-candidates.json",
        "src/unaltraweb_mcp/component-contract.json",
    )
    source_commit = _git(repository_dir, "rev-parse", "HEAD^1")
    _require(packages["source_commit"] == source_commit,
             "release receipt source must be the tag target's first parent")
    changed_paths = [
        line
        for line in _git(repository_dir, "diff", "--name-only", source_commit, "HEAD").splitlines()
        if line
    ]
    _require(changed_paths == ["release-candidates.json"],
             "release tag target may change only release-candidates.json from its first parent")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, f"origin/{default_branch}"],
        cwd=repository_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _require(ancestor.returncode == 0, "release receipt source does not belong to the default branch")

    contract_path = repository_dir / "src/unaltraweb_mcp/component-contract.json"
    contract = _load_object(contract_path, "component contract")
    _require(contract.get("schema_version") == 1, "component contract schema_version must be 1")
    release = contract.get("release")
    _require(isinstance(release, dict), "component contract release must be an object")
    _require(release.get("tag") == release_tag and release.get("version") == packages["version"],
             "component contract release does not match the reviewed tag")
    components = contract.get("components")
    _require(isinstance(components, dict), "component contract components must be an object")
    receipt = _load_object(receipt_path, "release receipt")
    candidates = receipt.get("components")
    _require(isinstance(candidates, dict), "release receipt components must be an object")
    ready_components: dict[str, dict[str, Any]] = {}
    for component_id, component in components.items():
        _require(isinstance(component_id, str) and isinstance(component, dict),
                 "component contract entries must be objects")
        status = component.get("release_status")
        _require(status in {"ready", "released"},
                 f"component {component_id} is not release-ready")
        if status == "ready":
            _require(component.get("version") == packages["version"] and component.get("release") == release_tag,
                     f"ready component {component_id} does not match the reviewed release")
            ready_components[component_id] = component
    _require(set(candidates) == set(ready_components),
             "release receipt must contain exactly every ready component")
    for component_id, component in ready_components.items():
        candidate = candidates.get(component_id)
        _require(isinstance(candidate, dict), f"release receipt candidate {component_id} must be an object")
        kind = component.get("kind")
        if kind == "container":
            repository = component.get("image_repository")
            reference = candidate.get("reference")
            _require(isinstance(repository, str) and isinstance(reference, str) and
                     re.fullmatch(rf"{re.escape(repository)}@sha256:[0-9a-f]{{64}}", reference) is not None,
                     f"release receipt candidate {component_id} must use its immutable image repository")
            _require(set(candidate) == {"reference"},
                     f"release receipt container {component_id} has unexpected fields")
        elif kind in {"gem", "python-wheel"}:
            expected_artifact = (
                f"{component.get('name')}-{component.get('version')}.gem"
                if kind == "gem"
                else f"{str(component.get('name')).replace('-', '_')}-{component.get('version')}-py3-none-any.whl"
            )
            _require(candidate.get("artifact") == expected_artifact,
                     f"release receipt package {component_id} has an unexpected artifact")
            candidate_sha = candidate.get("sha256")
            _require(isinstance(candidate_sha, str) and SHA256.fullmatch(candidate_sha) is not None,
                     f"release receipt package {component_id} has an invalid SHA-256")
            _require(set(candidate) == {"artifact", "sha256"},
                     f"release receipt package {component_id} has unexpected fields")
        else:
            raise ValueError(f"ready component {component_id} has unsupported kind {kind}")

    return {
        "receipt-sha256": receipt_sha256,
        "release-commit": release_commit,
        "source-commit": source_commit,
        "tag-object": tag_object,
    }


def authorize_run(
    receipt_path: Path,
    release_tag: str,
    receipt_sha256: str,
    run_id: int,
    run_json_path: Path,
    artifacts_json_path: Path,
    repository: str,
    default_branch: str,
) -> dict[str, str]:
    packages = release_packages(receipt_path, release_tag, receipt_sha256)
    run = _load_object(run_json_path, "workflow run")
    _require(run_id > 0 and run.get("id") == run_id, "workflow run ID does not match the request")
    _require(run.get("path") == PACKAGE_WORKFLOW, "candidate run used an unexpected workflow path")
    _require(run.get("event") == "workflow_dispatch", "candidate run was not manually dispatched")
    _require(run.get("status") == "completed" and run.get("conclusion") == "success",
             "candidate run did not complete successfully")
    _require(run.get("head_sha") == packages["source_commit"],
             "candidate run source does not match release receipt")
    _require(run.get("head_branch") == default_branch, "candidate run did not use the default branch")
    run_repository = run.get("repository")
    head_repository = run.get("head_repository")
    _require(isinstance(run_repository, dict) and run_repository.get("full_name") == repository,
             "candidate run belongs to an unexpected repository")
    _require(isinstance(head_repository, dict) and head_repository.get("full_name") == repository,
             "candidate run head belongs to an unexpected repository")

    payload = _load_object(artifacts_json_path, "workflow artifacts")
    artifacts = payload.get("artifacts")
    _require(isinstance(artifacts, list), "workflow artifacts must contain an artifact list")
    _require(payload.get("total_count") == len(artifacts) == 1,
             "candidate run must contain exactly one artifact")
    artifact = artifacts[0]
    _require(isinstance(artifact, dict), "candidate artifact must be an object")
    expected_name = f"unaltraweb-{packages['version']}-{packages['source_commit']}"
    _require(artifact.get("name") == expected_name, "candidate artifact name does not match the receipt")
    _require(artifact.get("expired") is False, "candidate artifact has expired")
    artifact_id = artifact.get("id")
    _require(isinstance(artifact_id, int) and artifact_id > 0, "candidate artifact ID is invalid")
    digest = artifact.get("digest")
    _require(isinstance(digest, str) and digest.startswith("sha256:") and
             SHA256.fullmatch(digest.removeprefix("sha256:")) is not None,
             "candidate artifact archive has no SHA-256 digest")
    artifact_run = artifact.get("workflow_run")
    _require(isinstance(artifact_run, dict), "candidate artifact has no workflow run identity")
    _require(artifact_run.get("id") == run_id, "candidate artifact belongs to another workflow run")
    _require(artifact_run.get("head_sha") == packages["source_commit"],
             "candidate artifact source does not match release receipt")
    _require(artifact_run.get("head_branch") == default_branch,
             "candidate artifact did not originate on the default branch")

    return {
        "artifact-id": str(artifact_id),
        "artifact-name": expected_name,
        "gem-artifact": packages["gem_artifact"],
        "version": packages["version"],
        "wheel-artifact": packages["wheel_artifact"],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_candidates(
    receipt_path: Path,
    release_tag: str,
    receipt_sha256: str,
    candidate_dir: Path,
    output_dir: Path,
) -> dict[str, str]:
    packages = release_packages(receipt_path, release_tag, receipt_sha256)
    _require(candidate_dir.is_dir() and not candidate_dir.is_symlink(),
             "candidate directory must be a real directory")
    entries = list(candidate_dir.iterdir())
    _require(all(entry.is_file() and not entry.is_symlink() for entry in entries),
             "candidate directory may contain only regular files")
    expected_names = {
        "SHA256SUMS",
        packages["gem_artifact"],
        packages["wheel_artifact"],
    }
    _require({entry.name for entry in entries} == expected_names,
             "candidate directory inventory does not match the release receipt")

    for component in ["gem", "wheel"]:
        artifact = candidate_dir / packages[f"{component}_artifact"]
        _require(_sha256(artifact) == packages[f"{component}_sha256"],
                 f"{component} candidate SHA-256 does not match the release receipt")

    expected_sums = (
        f"{packages['gem_sha256']}  ./{packages['gem_artifact']}\n"
        f"{packages['wheel_sha256']}  ./{packages['wheel_artifact']}\n"
    )
    _require((candidate_dir / "SHA256SUMS").read_text(encoding="utf-8") == expected_sums,
             "SHA256SUMS does not exactly match the release receipt")

    _require(not output_dir.is_symlink(), "staging output must not be a symlink")
    if output_dir.exists():
        _require(output_dir.is_dir() and not any(output_dir.iterdir()),
                 "staging output must be absent or empty")
    pypi_dir = output_dir / "pypi"
    rubygems_dir = output_dir / "rubygems"
    pypi_dir.mkdir(parents=True)
    rubygems_dir.mkdir(parents=True)
    wheel_target = pypi_dir / packages["wheel_artifact"]
    gem_target = rubygems_dir / packages["gem_artifact"]
    shutil.copyfile(candidate_dir / packages["wheel_artifact"], wheel_target)
    shutil.copyfile(candidate_dir / packages["gem_artifact"], gem_target)
    return {"gem": str(gem_target), "wheel": str(wheel_target)}


def _write_github_outputs(path: Path, values: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in sorted(values.items()):
            _require("\n" not in key and "\n" not in value, "GitHub output values must be single-line")
            handle.write(f"{key}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    release = commands.add_parser("release", help="Validate the immutable release checkout and receipt.")
    release.add_argument("--repository-dir", type=Path, required=True)
    release.add_argument("--receipt", type=Path, required=True)
    release.add_argument("--release-tag", required=True)
    release.add_argument("--tag-object", required=True)
    release.add_argument("--receipt-sha256", required=True)
    release.add_argument("--default-branch", required=True)

    authorize = commands.add_parser("authorize", help="Authorize one package candidate workflow artifact.")
    authorize.add_argument("--receipt", type=Path, required=True)
    authorize.add_argument("--release-tag", required=True)
    authorize.add_argument("--receipt-sha256", required=True)
    authorize.add_argument("--run-id", type=int, required=True)
    authorize.add_argument("--run-json", type=Path, required=True)
    authorize.add_argument("--artifacts-json", type=Path, required=True)
    authorize.add_argument("--repository", required=True)
    authorize.add_argument("--default-branch", required=True)
    authorize.add_argument("--github-output", type=Path)

    stage = commands.add_parser("stage", help="Verify and split exact package files for privileged jobs.")
    stage.add_argument("--receipt", type=Path, required=True)
    stage.add_argument("--release-tag", required=True)
    stage.add_argument("--receipt-sha256", required=True)
    stage.add_argument("--candidate-dir", type=Path, required=True)
    stage.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "release":
            result = validate_release_checkout(
                args.repository_dir,
                args.receipt,
                args.release_tag,
                args.tag_object,
                args.receipt_sha256,
                args.default_branch,
            )
        elif args.command == "authorize":
            result = authorize_run(
                args.receipt,
                args.release_tag,
                args.receipt_sha256,
                args.run_id,
                args.run_json,
                args.artifacts_json,
                args.repository,
                args.default_branch,
            )
            if args.github_output:
                _write_github_outputs(args.github_output, result)
        else:
            result = stage_candidates(
                args.receipt,
                args.release_tag,
                args.receipt_sha256,
                args.candidate_dir,
                args.output_dir,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
