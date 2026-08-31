#!/usr/bin/env python3
"""Validate GitHub Actions syntax, immutable pins, and publication gates."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github/workflows"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REVIEWED_ACTIONS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/configure-pages": "983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/deploy-pages": "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/upload-pages-artifact": "56afc609e74202658d3ffba0e8f6dda462b719fa",
    "docker/build-push-action": "10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
    "docker/login-action": "c94ce9fb468520275223c153574b00df6fe4bcc9",
    "docker/metadata-action": "c299e40c65443455700f0fdfc63efafe5b349051",
    "docker/setup-buildx-action": "8d2750c68a42422c14e847fe6c8ac0403b4cbd6f",
    "ruby/setup-ruby": "95ef2b042f9d7a56d8268cba8559e2842e2ad01b",
}
IMAGE_WORKFLOWS = {
    "compute-images.yml",
    "docker-image.yml",
    "project-compute-image.yml",
    "web-capture-image.yml",
}
PROMOTED_CORE_IMAGE_WORKFLOWS = {"compute-images.yml", "docker-image.yml", "web-capture-image.yml"}
FULLY_PINNED_WORKFLOWS = IMAGE_WORKFLOWS | {"ci.yml", "package-prepare.yml"}


class WorkflowLoader(yaml.SafeLoader):
    pass


WorkflowLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for initial, resolvers in list(WorkflowLoader.yaml_implicit_resolvers.items()):
    WorkflowLoader.yaml_implicit_resolvers[initial] = [
        (tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _construct_mapping(loader: WorkflowLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_workflow(path: Path) -> dict[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=WorkflowLoader)
    if not isinstance(value, dict):
        raise ValueError("workflow root must be a mapping")
    return value


def _steps(workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for job_name, job in workflow.get("jobs", {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if isinstance(step, dict):
                result.append((str(job_name), step))
    return result


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict))


def _needs(job: dict[str, Any]) -> set[str]:
    value = job.get("needs", [])
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value} if isinstance(value, list) else set()


def validate_workflows(root: Path = WORKFLOW_ROOT) -> list[str]:
    errors: list[str] = []
    workflows: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.yml")):
        try:
            workflows[path.name] = load_workflow(path)
        except Exception as exc:
            errors.append(f"{path.name}: invalid YAML: {exc}")

    for name, workflow in workflows.items():
        for job_name, step in _steps(workflow):
            uses = step.get("uses")
            if not isinstance(uses, str) or uses.startswith("./"):
                continue
            action, separator, revision = uses.rpartition("@")
            if not separator:
                errors.append(f"{name}:{job_name}: action has no revision: {uses}")
                continue
            reviewed = REVIEWED_ACTIONS.get(action)
            if reviewed and revision != reviewed:
                errors.append(f"{name}:{job_name}: {action} must use reviewed SHA {reviewed}")
            if name in FULLY_PINNED_WORKFLOWS and not FULL_SHA.fullmatch(revision):
                errors.append(f"{name}:{job_name}: action must use a full commit SHA: {uses}")
            if action == "actions/checkout" and step.get("with", {}).get("persist-credentials") is not False:
                errors.append(f"{name}:{job_name}: checkout must set persist-credentials: false")

    for name in IMAGE_WORKFLOWS:
        workflow = workflows.get(name)
        if workflow is None:
            errors.append(f"missing image publication workflow: {name}")
            continue
        jobs = workflow.get("jobs", {})
        preflight = jobs.get("preflight", {})
        preflight_commands = _run_text(preflight)
        required_gate = "distribution-release-check" if name == "project-compute-image.yml" else "distribution-check"
        if required_gate not in preflight_commands:
            errors.append(f"{name}: preflight must run {required_gate}")
        if "GITHUB_REF_TYPE" not in json.dumps(preflight) and "--validate-publish-ref" not in preflight_commands:
            errors.append(f"{name}: preflight must validate the publication ref and version")
        if "login-action" in "\n".join(str(step.get("uses", "")) for step in preflight.get("steps", [])):
            errors.append(f"{name}: preflight must not log in to a registry")
        if (
            workflow.get("permissions", {}).get("packages") == "write"
            or preflight.get("permissions", {}).get("packages") == "write"
        ):
            errors.append(f"{name}: preflight must not receive package-write permission")
        if any(
            isinstance(step, dict) and step.get("with", {}).get("push") is True
            for step in preflight.get("steps", [])
        ):
            errors.append(f"{name}: preflight must not push an image")
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            push_steps = [
                step for step in job.get("steps", [])
                if isinstance(step, dict)
                and str(step.get("uses", "")).startswith("docker/build-push-action@")
                and step.get("with", {}).get("push") is True
            ]
            if not push_steps:
                continue
            if "preflight" not in _needs(job):
                errors.append(f"{name}:{job_name}: publishing job must need preflight")
            for step in push_steps:
                settings = step.get("with", {})
                if settings.get("sbom") is not True:
                    errors.append(f"{name}:{job_name}: publishing build must enable sbom")
                if settings.get("provenance") != "mode=max":
                    errors.append(f"{name}:{job_name}: publishing build must use provenance: mode=max")
        concurrency = workflow.get("concurrency", {})
        if concurrency.get("cancel-in-progress") is not False:
            errors.append(f"{name}: publication concurrency must not cancel an in-progress publish")

        if name in PROMOTED_CORE_IMAGE_WORKFLOWS:
            workflow_text = json.dumps(workflow)
            if "sha-${{ github.sha }}" not in workflow_text:
                errors.append(f"{name}: default-branch candidates must use the full source commit SHA")
            if "imagetools create" not in workflow_text:
                errors.append(f"{name}: release tags must promote a reviewed candidate manifest")
            if "release-candidates.json" not in workflow_text:
                errors.append(f"{name}: release-tag promotion must read the external candidate receipt")
            if "Manifest.Digest" not in workflow_text:
                errors.append(f"{name}: release-tag promotion must verify the candidate tag still resolves to the recorded digest")
            for job_name, step in _steps(workflow):
                if not (
                    str(step.get("uses", "")).startswith("docker/build-push-action@")
                    and step.get("with", {}).get("push") is True
                ):
                    continue
                if str(step.get("if", "")) != "github.ref_type == 'branch'":
                    errors.append(f"{name}:{job_name}: image builds may push only default-branch candidates")

    docker_text = (root / "docker-image.yml").read_text(encoding="utf-8") if (root / "docker-image.yml").exists() else ""
    if "UNALTRAWEB_RUNTIME_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb@${{ steps.runtime.outputs.digest }}" not in docker_text:
        errors.append("docker-image.yml: MCP publication must use the exact runtime build digest")

    project_compute = workflows.get("project-compute-image.yml", {})
    project_compute_steps = _steps(project_compute)
    strict_gate_steps = [step for _, step in project_compute_steps if "distribution-release-check" in str(step.get("run", ""))]
    if not strict_gate_steps or strict_gate_steps[0].get("env", {}).get("GITHUB_DEFAULT_BRANCH") != "main":
        errors.append("project-compute-image.yml: release gate must declare the core default branch")

    codeql = workflows.get("codeql.yml", {})
    codeql_on = codeql.get("on", {})
    for event in ["push", "pull_request", "schedule"]:
        if event not in codeql_on:
            errors.append(f"codeql.yml: missing automatic {event} trigger")
    codeql_text = json.dumps(codeql)
    for language in ["javascript-typescript", "python", "ruby"]:
        if language not in codeql_text:
            errors.append(f"codeql.yml: missing {language} analysis")

    ci = workflows.get("ci.yml", {})
    ci_on = ci.get("on", {})
    for event in ["push", "pull_request"]:
        if event not in ci_on:
            errors.append(f"ci.yml: missing automatic {event} trigger")
    ci_text = json.dumps(ci)
    for marker in [
        "compileall", "unittest discover", "git diff --check", "distribution-check",
        "wheel-check", "gem-check", "mcp-smoke-prebuilt", "docs-build",
    ]:
        if marker not in ci_text:
            errors.append(f"ci.yml: missing required check {marker}")

    package = workflows.get("package-prepare.yml", {})
    package_text = json.dumps(package)
    for marker in ["distribution-check", "wheel-check", "gem-check", "sha256sum", "actions/upload-artifact@"]:
        if marker not in package_text:
            errors.append(f"package-prepare.yml: missing release preparation step {marker}")
    for forbidden in ["gem push", "twine upload", "gh release create", "docker push"]:
        if forbidden in package_text:
            errors.append(f"package-prepare.yml: forbidden publication command {forbidden}")
    if "${{ github.sha }}" not in package_text or '"overwrite": false' not in package_text:
        errors.append("package-prepare.yml: artifact must be SHA-named and immutable")
    if package.get("permissions", {}).get("contents") != "read" or len(package.get("permissions", {})) != 1:
        errors.append("package-prepare.yml: candidate preparation must have read-only repository permissions")
    return errors


def main() -> int:
    errors = validate_workflows()
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
