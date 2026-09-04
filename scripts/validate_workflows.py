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
JOB_ENV_RUNNER_CONTEXT = re.compile(
    r"\${{.*?(?<![A-Za-z0-9_.])runner\s*(?:\.|\[).*?}}",
    re.DOTALL,
)
DOCKER_BUILD_COMMAND = re.compile(r"\bdocker\s+(?:build|buildx\s+build|compose\s+build)(?:\s|$)")
CANDIDATE_EXECUTION_COMMAND = re.compile(
    r"\bdocker\s+(?:(?:container)\s+)?(?:run|create|start|exec)(?:\s|$)"
    r"|\bdocker\s+compose\s+(?:run|up|start|exec)(?:\s|$)"
)
CANDIDATE_EXECUTION_TARGETS = {
    "docs-build",
    "mcp-smoke-prebuilt",
    "reproducible-site-check",
}
REVIEWED_SITE_DEPLOY_SHAS = {"6427c5963d6d32845cd774dd8537fe935b42d381"}
REVIEWED_ACTIONS = {
    "actions/attest-build-provenance": "4d101475d8b20a2381f78447822ac1eab6504dd8",
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/configure-pages": "983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/deploy-pages": "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
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
FULLY_PINNED_WORKFLOWS = IMAGE_WORKFLOWS | {"ci.yml", "package-prepare.yml", "site-deploy.yml", "site-release.yml"}


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


def _named_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    for step in job.get("steps", []):
        if isinstance(step, dict) and step.get("name") == name:
            return step
    return {}


def _job_uses(workflow: dict[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for job_name, job in workflow.get("jobs", {}).items():
        if isinstance(job, dict) and isinstance(job.get("uses"), str):
            result.append((str(job_name), str(job["uses"])))
    return result


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict))


def _needs(job: dict[str, Any]) -> set[str]:
    value = job.get("needs", [])
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value} if isinstance(value, list) else set()


def _executes_candidate(step: dict[str, Any]) -> bool:
    run = str(step.get("run", ""))
    if str(step.get("uses", "")).startswith("docker://") or CANDIDATE_EXECUTION_COMMAND.search(run):
        return True
    return any(re.search(rf"(?<![\w-]){re.escape(target)}(?![\w-])", run) for target in CANDIDATE_EXECUTION_TARGETS)


def validate_workflows(root: Path = WORKFLOW_ROOT) -> list[str]:
    errors: list[str] = []
    workflows: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.yml")):
        try:
            workflows[path.name] = load_workflow(path)
        except Exception as exc:
            errors.append(f"{path.name}: invalid YAML: {exc}")

    for name, workflow in workflows.items():
        for job_name, job in workflow.get("jobs", {}).items():
            if not isinstance(job, dict) or not isinstance(job.get("env", {}), dict):
                continue
            for value in job.get("env", {}).values():
                if isinstance(value, str) and JOB_ENV_RUNNER_CONTEXT.search(value):
                    errors.append(f"{name}:{job_name}: job-level env cannot use the runner context")

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
        if name == "project-compute-image.yml":
            for required_gate in ["distribution-check", "distribution-release-check"]:
                if required_gate not in preflight_commands:
                    errors.append(f"{name}: preflight must run {required_gate} for its matching publication channel")
        elif "distribution-check" not in preflight_commands:
            errors.append(f"{name}: preflight must run distribution-check")
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
                job = jobs.get(job_name, {})
                if (
                    str(step.get("if", "")) != "github.ref_type == 'branch'"
                    and str(job.get("if", "")) != "github.ref_type == 'branch'"
                ):
                    errors.append(f"{name}:{job_name}: image builds may push only default-branch candidates")

    docker_workflow = workflows.get("docker-image.yml", {})
    docker_jobs = docker_workflow.get("jobs", {})
    docker_preflight = docker_jobs.get("preflight", {})
    docker_build = docker_jobs.get("build-candidates", {})
    docker_test = docker_jobs.get("test-candidates", {})
    docker_promote = docker_jobs.get("promote-candidates", {})
    docker_release = docker_jobs.get("promote-release", {})
    expected_docker_jobs = {
        "preflight": (set(), None, {"contents": "read"}),
        "build-candidates": (
            {"preflight"},
            "github.ref_type == 'branch'",
            {"contents": "read", "packages": "write", "attestations": "write", "id-token": "write"},
        ),
        "test-candidates": (
            {"build-candidates"},
            "github.ref_type == 'branch'",
            {"contents": "read", "packages": "read", "attestations": "read"},
        ),
        "promote-candidates": (
            {"test-candidates"},
            "github.ref_type == 'branch'",
            {"contents": "read", "packages": "write", "attestations": "read"},
        ),
        "promote-release": (
            {"preflight"},
            "github.ref_type == 'tag'",
            {"contents": "read", "packages": "write", "attestations": "read"},
        ),
    }
    if set(docker_jobs) != set(expected_docker_jobs):
        errors.append("docker-image.yml: must use only credential-separated preflight/build/test/promote/release jobs")
    for job_name, (expected_needs, expected_if, expected_permissions) in expected_docker_jobs.items():
        job = docker_jobs.get(job_name, {})
        if (
            _needs(job) != expected_needs
            or job.get("if") != expected_if
            or job.get("permissions") != expected_permissions
        ):
            errors.append(f"docker-image.yml:{job_name}: job boundary, dependency, or permissions differ from policy")

    preflight_builds = [
        step
        for step in docker_preflight.get("steps", [])
        if isinstance(step, dict)
        and str(step.get("uses", "")).startswith("docker/build-push-action@")
    ]
    if preflight_builds or DOCKER_BUILD_COMMAND.search(_run_text(docker_preflight)):
        errors.append("docker-image.yml: unprivileged preflight must not build Docker images")
    if any(
        "continue-on-error" in job
        or any("continue-on-error" in step for step in job.get("steps", []) if isinstance(step, dict))
        for job in docker_jobs.values()
        if isinstance(job, dict)
    ):
        errors.append("docker-image.yml: publication gates must not allow job-level failure")

    for job_name, job in docker_jobs.items():
        if not isinstance(job, dict) or job.get("permissions", {}).get("packages") != "write":
            continue
        for step in job.get("steps", []):
            if isinstance(step, dict) and _executes_candidate(step):
                errors.append(f"docker-image.yml:{job_name}: package-write jobs must never execute candidate images")
                break

    for job_name in ["test-candidates", "promote-candidates", "promote-release"]:
        job = docker_jobs.get(job_name, {})
        if DOCKER_BUILD_COMMAND.search(_run_text(job)) or any(
            isinstance(step, dict) and str(step.get("uses", "")).startswith("docker/build-push-action@")
            for step in job.get("steps", [])
        ):
            errors.append(f"docker-image.yml:{job_name}: tested candidates must be promoted without rebuild")

    expected_builds = {
        "Build and publish runtime candidate": (
            "runtime",
            "ghcr.io/dosquartsdedocs/unaltraweb:sha-${{ github.sha }}",
        ),
        "Build and publish MCP candidate from runtime digest": (
            "mcp",
            "ghcr.io/dosquartsdedocs/unaltraweb-mcp:sha-${{ github.sha }}",
        ),
        "Build and publish manual PDF candidate": (
            "manual",
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf:sha-${{ github.sha }}",
        ),
    }
    candidate_builds = [
        (index, step)
        for index, step in enumerate(docker_build.get("steps", []))
        if isinstance(step, dict)
        if str(step.get("uses", "")).startswith("docker/build-push-action@")
    ]
    if DOCKER_BUILD_COMMAND.search(_run_text(docker_build)):
        errors.append("docker-image.yml: build-candidates may build only through the three reviewed build actions")
    if [str(step.get("name")) for _, step in candidate_builds] != list(expected_builds):
        errors.append(
            "docker-image.yml: build-candidates must build runtime, MCP, and manual PDF exactly once in that order"
        )
    for _, step in candidate_builds:
        name = str(step.get("name"))
        settings = step.get("with", {})
        expected = expected_builds.get(name)
        tags = str(settings.get("tags", ""))
        if re.search(r"(?:^|[:,\s])(?:main|latest)(?:$|[,\s])", tags):
            errors.append(f"docker-image.yml:{name}: build-push tags must not contain broad aliases")
        if expected and (
            (step.get("id"), tags) != expected
            or step.get("if") is not None
            or settings.get("push") is not True
            or settings.get("sbom") is not True
            or settings.get("provenance") != "mode=max"
        ):
            errors.append(f"docker-image.yml:{name}: build-push tags must contain only its immutable SHA candidate")
    runtime_build = _named_step(docker_build, "Build and publish runtime candidate")
    mcp_build = _named_step(docker_build, "Build and publish MCP candidate from runtime digest")
    manual_build = _named_step(docker_build, "Build and publish manual PDF candidate")
    if mcp_build.get("with", {}).get("build-args") != (
        "UNALTRAWEB_RUNTIME_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb@${{ steps.runtime.outputs.digest }}"
    ):
        errors.append("docker-image.yml: MCP publication must use the exact runtime build digest")
    for step, metadata_id in [
        (runtime_build, "runtime-meta"),
        (mcp_build, "mcp-meta"),
        (manual_build, "manual-meta"),
    ]:
        if step.get("with", {}).get("labels") != f"${{{{ steps.{metadata_id}.outputs.labels }}}}":
            errors.append(f"docker-image.yml:{step.get('name')}: candidate must retain OCI metadata labels")

    for name in ["Runtime metadata", "MCP metadata", "Manual PDF metadata"]:
        metadata = _named_step(docker_build, name)
        settings = metadata.get("with", {})
        if (
            metadata.get("if") is not None
            or settings.get("flavor") != "latest=false"
            or settings.get("tags") != "type=raw,value=sha-${{ github.sha }},enable={{is_default_branch}}"
        ):
            errors.append(f"docker-image.yml:{name}: metadata must describe only the default-branch SHA candidate")

    build_steps = [step for step in docker_build.get("steps", []) if isinstance(step, dict)]
    expected_build_step_names = [
        "Checkout",
        "Set up Docker Buildx",
        "Runtime metadata",
        "MCP metadata",
        "Manual PDF metadata",
        "Log in to GHCR",
        "Require unused candidate SHA tags",
        "Build and publish runtime candidate",
        "Attest runtime candidate build provenance",
        "Build and publish MCP candidate from runtime digest",
        "Attest MCP candidate build provenance",
        "Build and publish manual PDF candidate",
        "Attest manual PDF candidate build provenance",
        "Record built candidate digests",
    ]
    if [str(step.get("name")) for step in build_steps] != expected_build_step_names:
        errors.append("docker-image.yml: build-candidates step inventory differs from the reviewed boundary")
    build_step_positions = {
        str(step.get("name")): index for index, step in enumerate(build_steps) if step.get("name")
    }
    no_clobber = _named_step(docker_build, "Require unused candidate SHA tags")
    expected_candidate_env = {
        "MANUAL_PDF_CANDIDATE": "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf:sha-${{ github.sha }}",
        "MCP_CANDIDATE": "ghcr.io/dosquartsdedocs/unaltraweb-mcp:sha-${{ github.sha }}",
        "RUNTIME_CANDIDATE": "ghcr.io/dosquartsdedocs/unaltraweb:sha-${{ github.sha }}",
    }
    no_clobber_text = str(no_clobber.get("run", ""))
    if (
        no_clobber.get("if") is not None
        or no_clobber.get("env") != expected_candidate_env
        or "continue-on-error" in no_clobber
        or any(mask in no_clobber_text for mask in ["|| true", "|| :", "set +e"])
        or (
            candidate_builds
            and build_step_positions.get("Require unused candidate SHA tags", len(build_steps))
            >= candidate_builds[0][0]
        )
        or not all(
            marker in no_clobber_text
            for marker in [
                "imagetools inspect",
                "candidate tag already exists",
                "manifest unknown",
                "not found",
                'require_absent "$RUNTIME_CANDIDATE"',
                'require_absent "$MCP_CANDIDATE"',
                'require_absent "$MANUAL_PDF_CANDIDATE"',
            ]
        )
    ):
        errors.append("docker-image.yml: branch publication must fail closed before overwriting any SHA candidate")

    expected_attestations = {
        "Build and publish runtime candidate": (
            "Attest runtime candidate build provenance",
            "ghcr.io/dosquartsdedocs/unaltraweb",
            "${{ steps.runtime.outputs.digest }}",
        ),
        "Build and publish MCP candidate from runtime digest": (
            "Attest MCP candidate build provenance",
            "ghcr.io/dosquartsdedocs/unaltraweb-mcp",
            "${{ steps.mcp.outputs.digest }}",
        ),
        "Build and publish manual PDF candidate": (
            "Attest manual PDF candidate build provenance",
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf",
            "${{ steps.manual.outputs.digest }}",
        ),
    }
    attest_action = (
        "actions/attest-build-provenance@"
        "4d101475d8b20a2381f78447822ac1eab6504dd8"
    )
    attestation_steps = [
        step for step in build_steps if str(step.get("uses", "")).startswith("actions/attest-build-provenance@")
    ]
    if len(attestation_steps) != len(expected_attestations):
        errors.append("docker-image.yml: every candidate build must have one GitHub signed provenance attestation")
    for build_name, (attestation_name, subject_name, subject_digest) in expected_attestations.items():
        build_position = build_step_positions.get(build_name, -2)
        attestation = _named_step(docker_build, attestation_name)
        expected_settings = {
            "subject-name": subject_name,
            "subject-digest": subject_digest,
            "push-to-registry": True,
            "create-storage-record": False,
        }
        if (
            build_position < 0
            or build_position + 1 >= len(build_steps)
            or build_steps[build_position + 1].get("name") != attestation_name
            or attestation.get("uses") != attest_action
            or attestation.get("with") != expected_settings
        ):
            errors.append(f"docker-image.yml:{build_name}: must be immediately followed by exact signed provenance")

    built = _named_step(docker_build, "Record built candidate digests")
    expected_build_outputs = {
        "source_commit": "${{ steps.built.outputs.source_commit }}",
        "runtime_digest": "${{ steps.built.outputs.runtime_digest }}",
        "mcp_digest": "${{ steps.built.outputs.mcp_digest }}",
        "manual_pdf_digest": "${{ steps.built.outputs.manual_pdf_digest }}",
    }
    expected_built_env = {
        "MANUAL_PDF_DIGEST": "${{ steps.manual.outputs.digest }}",
        "MCP_DIGEST": "${{ steps.mcp.outputs.digest }}",
        "RUNTIME_DIGEST": "${{ steps.runtime.outputs.digest }}",
    }
    built_text = str(built.get("run", ""))
    built_position = build_step_positions.get("Record built candidate digests", -1)
    last_attestation_position = max(
        (build_step_positions.get(name, len(build_steps)) for name, _, _ in expected_attestations.values()),
        default=len(build_steps),
    )
    if (
        docker_build.get("outputs") != expected_build_outputs
        or built.get("id") != "built"
        or built.get("env") != expected_built_env
        or built_position <= last_attestation_position
        or not all(
            marker in built_text
            for marker in ["GITHUB_OUTPUT", "source_commit", "runtime_digest", "mcp_digest", "manual_pdf_digest"]
        )
    ):
        errors.append("docker-image.yml: build-candidates must expose the source commit and all three exact digests")

    exact_test_contract = {
        "Test all Ruby files in exact runtime": (
            {
                "RUNTIME_IMAGE": (
                    "ghcr.io/dosquartsdedocs/unaltraweb@"
                    "${{ needs.build-candidates.outputs.runtime_digest }}"
                )
            },
            ["docker run", '$PWD:/work:ro', "globstar", "test/**/*_test.rb", "bundle exec ruby"],
        ),
        "Test all manual PDF integrations in exact image": (
            {
                "MANUAL_PDF_IMAGE": (
                    "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@"
                    "${{ needs.build-candidates.outputs.manual_pdf_digest }}"
                )
            },
            ["docker run", '$PWD:/work:ro', "-m unittest discover -s test/manual_pdf -p 'test_*_integration.py'"],
        ),
        "Check reproducible packaged Jekyll build with exact MCP": (
            {
                "MCP_IMAGE": (
                    "ghcr.io/dosquartsdedocs/unaltraweb-mcp@"
                    "${{ needs.build-candidates.outputs.mcp_digest }}"
                )
            },
            ["reproducible-site-check", 'DOCKER_IMAGE="$MCP_IMAGE"'],
        ),
        "Smoke test exact MCP": (
            {
                "MCP_IMAGE": (
                    "ghcr.io/dosquartsdedocs/unaltraweb-mcp@"
                    "${{ needs.build-candidates.outputs.mcp_digest }}"
                )
            },
            ["mcp-smoke-prebuilt", 'MCP_IMAGE="$MCP_IMAGE"'],
        ),
        "Build docs with exact runtime": (
            {
                "RUNTIME_IMAGE": (
                    "ghcr.io/dosquartsdedocs/unaltraweb@"
                    "${{ needs.build-candidates.outputs.runtime_digest }}"
                )
            },
            ["docs-build", 'DOCKER_IMAGE="$RUNTIME_IMAGE"'],
        ),
    }
    test_steps = [step for step in docker_test.get("steps", []) if isinstance(step, dict)]
    test_step_names = [str(step.get("name")) for step in test_steps if step.get("name")]
    expected_test_step_names = [
        "Checkout",
        "Isolate Docker credentials",
        "Log in to GHCR for read-only verification",
        "Verify signed provenance and exact candidate revisions",
        "Remove GHCR credentials before candidate execution",
        *exact_test_contract,
        "Record tested candidate digests",
    ]
    if [str(step.get("name")) for step in test_steps] != expected_test_step_names:
        errors.append("docker-image.yml: test-candidates step inventory differs from the reviewed boundary")
    test_step_positions = {
        str(step.get("name")): index for index, step in enumerate(test_steps) if step.get("name")
    }
    for name, (expected_env, markers) in exact_test_contract.items():
        step = _named_step(docker_test, name)
        run = str(step.get("run", ""))
        if (
            test_step_names.count(name) != 1
            or step.get("if") is not None
            or step.get("env") != expected_env
            or "continue-on-error" in step
            or any(mask in run for mask in ["|| true", "|| :", "set +e"])
            or not all(marker in run for marker in markers)
        ):
            errors.append(f"docker-image.yml:{name}: must test the exact candidate build digest")

    candidate_execution_steps = [
        (index, step) for index, step in enumerate(test_steps) if _executes_candidate(step)
    ]
    if [str(step.get("name")) for _, step in candidate_execution_steps] != list(exact_test_contract):
        errors.append("docker-image.yml:test-candidates: candidate execution inventory differs from the reviewed tests")
    exact_test_positions = [test_step_positions[name] for name in exact_test_contract if name in test_step_positions]
    first_exact_test = min(exact_test_positions) if exact_test_positions else None
    last_exact_test = max(exact_test_positions) if exact_test_positions else None
    if len(exact_test_positions) == len(exact_test_contract) and exact_test_positions != sorted(exact_test_positions):
        errors.append("docker-image.yml: exact-image verification and tests must retain their reviewed order")

    verification = _named_step(docker_test, "Verify signed provenance and exact candidate revisions")
    verification_text = str(verification.get("run", ""))
    expected_verification_env = {
        "GH_TOKEN": "${{ github.token }}",
        "MANUAL_PDF_IMAGE": (
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@"
            "${{ needs.build-candidates.outputs.manual_pdf_digest }}"
        ),
        "MCP_IMAGE": (
            "ghcr.io/dosquartsdedocs/unaltraweb-mcp@"
            "${{ needs.build-candidates.outputs.mcp_digest }}"
        ),
        "RUNTIME_IMAGE": (
            "ghcr.io/dosquartsdedocs/unaltraweb@"
            "${{ needs.build-candidates.outputs.runtime_digest }}"
        ),
    }
    attestation_markers = [
        'gh attestation verify "oci://${image}"',
        "--bundle-from-oci",
        "--repo dosquartsdedocs/unaltraweb",
        "--signer-workflow dosquartsdedocs/unaltraweb/.github/workflows/docker-image.yml",
        '--source-digest "$GITHUB_SHA"',
        'docker pull "$image"',
        "org.opencontainers.image.revision",
        'if [ "$revision" != "$GITHUB_SHA" ]',
        'verify_candidate "$RUNTIME_IMAGE"',
        'verify_candidate "$MCP_IMAGE"',
        'verify_candidate "$MANUAL_PDF_IMAGE"',
    ]
    if (
        verification.get("env") != expected_verification_env
        or any(mask in verification_text for mask in ["|| true", "|| :", "set +e"])
        or not all(marker in verification_text for marker in attestation_markers)
    ):
        errors.append("docker-image.yml:test-candidates: exact digests require signed provenance and revision checks")

    test_login = _named_step(docker_test, "Log in to GHCR for read-only verification")
    expected_test_login = {
        "registry": "ghcr.io",
        "username": "${{ github.actor }}",
        "password": "${{ secrets.GITHUB_TOKEN }}",
    }
    test_login_steps = [
        step for step in test_steps if str(step.get("uses", "")).startswith("docker/login-action@")
    ]
    if (
        len(test_login_steps) != 1
        or test_login.get("uses")
        != "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9"
        or test_login.get("with") != expected_test_login
        or any(
            "secrets." in json.dumps(step)
            for step in test_steps
            if step is not test_login
        )
    ):
        errors.append("docker-image.yml:test-candidates: GHCR login must use only the read-scoped repository token")

    isolation = _named_step(docker_test, "Isolate Docker credentials")
    isolation_position = test_step_positions.get("Isolate Docker credentials", -1)
    isolation_text = str(isolation.get("run", ""))
    login_position = test_step_positions.get("Log in to GHCR for read-only verification", -1)
    verification_position = test_step_positions.get("Verify signed provenance and exact candidate revisions", -1)
    logout = _named_step(docker_test, "Remove GHCR credentials before candidate execution")
    logout_position = test_step_positions.get("Remove GHCR credentials before candidate execution", -1)
    logout_text = str(logout.get("run", ""))
    if (
        docker_test.get("env") not in (None, {})
        or first_exact_test is None
        or not (0 <= isolation_position < login_position < verification_position < logout_position < first_exact_test)
        or isolation_text.strip()
        != 'printf \'DOCKER_CONFIG=%s\\n\' "$RUNNER_TEMP/unaltraweb-test-docker" >> "$GITHUB_ENV"'
        or not all(
            marker in logout_text
            for marker in [
                "docker logout ghcr.io",
                'rm -rf -- "$DOCKER_CONFIG"',
                'mkdir -m 0700 -- "$DOCKER_CONFIG"',
                'printf \'{"auths":{}}\\n\' > "$DOCKER_CONFIG/config.json"',
            ]
        )
        or any(
            str(step.get("uses", "")).startswith("docker/login-action@")
            for step in test_steps[logout_position + 1 :]
        )
    ):
        errors.append("docker-image.yml:test-candidates: GHCR credentials must be destroyed before candidate execution")

    for _, step in candidate_execution_steps:
        serialized = json.dumps({"env": step.get("env", {}), "run": step.get("run", "")})
        if "GH_TOKEN" in serialized or "GITHUB_TOKEN" in serialized or "secrets." in serialized:
            errors.append("docker-image.yml:test-candidates: candidate execution must not receive GitHub credentials")
            break

    broad_promotions = [
        (job_name, index, step)
        for job_name, job in docker_jobs.items()
        if isinstance(job, dict)
        for index, step in enumerate(job.get("steps", []))
        if isinstance(step, dict)
        and "imagetools create" in str(step.get("run", ""))
        and all(alias in str(step.get("run", "")) for alias in [':main"', ':latest"'])
    ]
    if len(broad_promotions) != 1 or broad_promotions[0][0] != "promote-candidates":
        errors.append("docker-image.yml: main/latest aliases may be assigned only after test-candidates")
    else:
        promotion = broad_promotions[0][2]
        promotion_text = str(promotion.get("run", ""))
        expected_promotion_env = {
            "MANUAL_PDF_SOURCE": (
                "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@"
                "${{ needs.test-candidates.outputs.manual_pdf_digest }}"
            ),
            "MCP_SOURCE": (
                "ghcr.io/dosquartsdedocs/unaltraweb-mcp@"
                "${{ needs.test-candidates.outputs.mcp_digest }}"
            ),
            "RUNTIME_SOURCE": (
                "ghcr.io/dosquartsdedocs/unaltraweb@"
                "${{ needs.test-candidates.outputs.runtime_digest }}"
            ),
        }
        if (
            promotion.get("name") != "Promote tested candidates to default-branch aliases"
            or promotion.get("if") is not None
            or promotion.get("env") != expected_promotion_env
            or any(mask in promotion_text for mask in ["|| true", "|| :", "set +e"])
            or not all(
                marker in promotion_text
                for marker in [
                    'expected="${source##*@}"',
                    "--prefer-index=false",
                    '--tag "${repository}:sha-${GITHUB_SHA}"',
                    'for alias in "sha-${GITHUB_SHA}" main latest',
                    "Manifest.Digest",
                    'if [ "$actual" != "$expected" ]',
                    'promote_aliases ghcr.io/dosquartsdedocs/unaltraweb "$RUNTIME_SOURCE"',
                    'promote_aliases ghcr.io/dosquartsdedocs/unaltraweb-mcp "$MCP_SOURCE"',
                    'promote_aliases ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf "$MANUAL_PDF_SOURCE"',
                ]
            )
        ):
            errors.append("docker-image.yml: broad aliases must resolve to the three tested build digests")

    for job_name, step in _steps(docker_workflow):
        text = json.dumps({"run": step.get("run", ""), "with": step.get("with", {})})
        if any(alias in text for alias in [':main\\"', ':latest\\"']) and (
            job_name != "promote-candidates"
            or step.get("name") != "Promote tested candidates to default-branch aliases"
        ):
            errors.append("docker-image.yml: broad aliases may be assigned only by promote-candidates")
            break

    promote_verification = _named_step(docker_promote, "Reverify tested candidate provenance and revisions")
    promote_verification_text = str(promote_verification.get("run", ""))
    promote_steps = [step for step in docker_promote.get("steps", []) if isinstance(step, dict)]
    expected_promote_step_names = [
        "Set up Docker Buildx",
        "Log in to GHCR",
        "Reverify tested candidate provenance and revisions",
        "Promote tested candidates to default-branch aliases",
    ]
    if [str(step.get("name")) for step in promote_steps] != expected_promote_step_names:
        errors.append("docker-image.yml: promote-candidates step inventory differs from the reviewed boundary")
    promote_positions = {
        str(step.get("name")): index for index, step in enumerate(promote_steps) if step.get("name")
    }
    expected_promote_verification_env = {
        "GH_TOKEN": "${{ github.token }}",
        "MANUAL_PDF_SOURCE": (
            "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@"
            "${{ needs.test-candidates.outputs.manual_pdf_digest }}"
        ),
        "MCP_SOURCE": (
            "ghcr.io/dosquartsdedocs/unaltraweb-mcp@"
            "${{ needs.test-candidates.outputs.mcp_digest }}"
        ),
        "RUNTIME_SOURCE": (
            "ghcr.io/dosquartsdedocs/unaltraweb@"
            "${{ needs.test-candidates.outputs.runtime_digest }}"
        ),
    }
    if (
        promote_verification.get("env") != expected_promote_verification_env
        or any(mask in promote_verification_text for mask in ["|| true", "|| :", "set +e"])
        or promote_positions.get("Reverify tested candidate provenance and revisions", len(promote_steps))
        >= promote_positions.get("Promote tested candidates to default-branch aliases", -1)
        or not all(
            marker in promote_verification_text
            for marker in [
                "Manifest.Digest",
                'gh attestation verify "oci://${source}"',
                "--bundle-from-oci",
                "--repo dosquartsdedocs/unaltraweb",
                "--signer-workflow dosquartsdedocs/unaltraweb/.github/workflows/docker-image.yml",
                '--source-digest "$GITHUB_SHA"',
                "org.opencontainers.image.revision",
                'if [ "$revision" != "$GITHUB_SHA" ]',
            ]
        )
    ):
        errors.append("docker-image.yml: branch promotion must reverify provenance, SHA tag, and revision")

    tested = _named_step(docker_test, "Record tested candidate digests")
    expected_outputs = {
        "runtime_digest": "${{ steps.tested.outputs.runtime_digest }}",
        "mcp_digest": "${{ steps.tested.outputs.mcp_digest }}",
        "manual_pdf_digest": "${{ steps.tested.outputs.manual_pdf_digest }}",
    }
    tested_text = str(tested.get("run", ""))
    expected_tested_env = {
        "MANUAL_PDF_DIGEST": "${{ needs.build-candidates.outputs.manual_pdf_digest }}",
        "MCP_DIGEST": "${{ needs.build-candidates.outputs.mcp_digest }}",
        "RUNTIME_DIGEST": "${{ needs.build-candidates.outputs.runtime_digest }}",
    }
    tested_position = test_step_positions.get("Record tested candidate digests", -1)
    if (
        docker_test.get("outputs") != expected_outputs
        or tested.get("id") != "tested"
        or tested.get("if") is not None
        or tested.get("env") != expected_tested_env
        or last_exact_test is None
        or tested_position <= last_exact_test
        or not all(
            marker in tested_text
            for marker in [
                "GITHUB_OUTPUT",
                "GITHUB_STEP_SUMMARY",
                "runtime_digest",
                "mcp_digest",
                "manual_pdf_digest",
            ]
        )
    ):
        errors.append("docker-image.yml: test-candidates may expose digests only after every candidate test passes")

    release = _named_step(docker_release, "Read release version and candidate receipt")
    release_text = str(release.get("run", ""))
    if (
        'receipt["components"].get(component_id)' not in release_text
        or 'component["reference"]' in release_text
        or "source_commit" not in release_text
    ):
        errors.append("docker-image.yml: release tags may promote only immutable digests recorded in the candidate receipt")
    release_verification = _named_step(docker_release, "Verify recorded candidate provenance and source binding")
    release_verification_text = str(release_verification.get("run", ""))
    if (
        "continue-on-error" in release_verification
        or any(mask in release_verification_text for mask in ["|| true", "|| :", "set +e"])
        or release_verification.get("env", {}).get("SOURCE_COMMIT")
        != "${{ steps.release.outputs.source_commit }}"
        or not all(
            marker in release_verification_text
            for marker in [
                "Manifest.Digest",
                'gh attestation verify "oci://${source}"',
                "--bundle-from-oci",
                "--repo dosquartsdedocs/unaltraweb",
                "--signer-workflow dosquartsdedocs/unaltraweb/.github/workflows/docker-image.yml",
                '--source-digest "$SOURCE_COMMIT"',
                'docker pull "$source"',
                "org.opencontainers.image.revision",
                'if [ "$revision" != "$SOURCE_COMMIT" ]',
            ]
        )
    ):
        errors.append("docker-image.yml: tag promotion must verify signed provenance bound to receipt source_commit")

    release_promotions = {
        "Promote reviewed runtime candidate": "runtime",
        "Promote reviewed MCP candidate": "mcp",
        "Promote reviewed manual PDF candidate": "manual_pdf",
    }
    release_steps = [step for step in docker_release.get("steps", []) if isinstance(step, dict)]
    expected_release_step_names = [
        "Checkout",
        "Set up Docker Buildx",
        "Read release version and candidate receipt",
        "Log in to GHCR",
        "Verify recorded candidate provenance and source binding",
        *release_promotions,
    ]
    if [str(step.get("name")) for step in release_steps] != expected_release_step_names:
        errors.append("docker-image.yml: promote-release step inventory differs from the reviewed boundary")
    release_step_positions = {
        str(step.get("name")): index for index, step in enumerate(release_steps) if step.get("name")
    }
    verification_position = release_step_positions.get(
        "Verify recorded candidate provenance and source binding", len(release_steps)
    )
    for name, component in release_promotions.items():
        step = _named_step(docker_release, name)
        run = str(step.get("run", ""))
        if (
            step.get("if") != f"steps.release.outputs.{component} != ''"
            or step.get("env", {}).get("SOURCE") != f"${{{{ steps.release.outputs.{component} }}}}"
            or "imagetools create" not in run
            or "--prefer-index=false" not in run
            or "Manifest.Digest" not in run
            or 'expected="${SOURCE##*@}"' not in run
            or any(mask in run for mask in ["|| true", "|| :", "set +e"])
            or release_step_positions.get(name, -1) <= verification_position
        ):
            errors.append(f"docker-image.yml:{name}: version aliases must use only its recorded candidate digest")

    project_compute = workflows.get("project-compute-image.yml", {})
    project_preflight = project_compute.get("jobs", {}).get("preflight", {})
    provider_checkout = _named_step(project_preflight, "Checkout workflow release gate")
    provider_settings = provider_checkout.get("with", {})
    if (
        provider_settings.get("repository") != "${{ job.workflow_repository }}"
        or provider_settings.get("ref") != "${{ job.workflow_sha }}"
    ):
        errors.append("project-compute-image.yml: provider checkout must use the defining reusable workflow repository and SHA")
    candidate_gate = _named_step(project_preflight, "Validate candidate core distribution")
    if (
        candidate_gate.get("if") != "github.ref_type == 'branch'"
        or "distribution-check" not in str(candidate_gate.get("run", ""))
        or "distribution-release-check" in str(candidate_gate.get("run", ""))
    ):
        errors.append("project-compute-image.yml: default-branch candidates must use only distribution-check")
    release_gate = _named_step(project_preflight, "Require release-ready core distribution")
    if (
        release_gate.get("if") != "github.ref_type == 'tag'"
        or "distribution-release-check" not in str(release_gate.get("run", ""))
        or release_gate.get("env", {}).get("GITHUB_DEFAULT_BRANCH") != "main"
    ):
        errors.append("project-compute-image.yml: vX.Y.Z publication must use distribution-release-check with the core default branch")

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
        "wheel-check", "gem-check", "reproducible-site-check", "mcp-smoke-prebuilt", "docs-build",
    ]:
        if marker not in ci_text:
            errors.append(f"ci.yml: missing required check {marker}")
    ci_docker = ci.get("jobs", {}).get("docker", {})
    ruby_tests = str(_named_step(ci_docker, "Test all Ruby files").get("run") or "")
    if not all(
        marker in ruby_tests
        for marker in ["$PWD:/work:ro", "globstar", "test/**/*_test.rb", "bundle exec ruby"]
    ):
        errors.append("ci.yml: Docker runtime must run every Ruby test from a read-only source mount")
    manual_pdf_tests = str(_named_step(ci_docker, "Test all manual PDF integrations").get("run") or "")
    if "-m unittest discover -s test/manual_pdf -p 'test_*_integration.py'" not in manual_pdf_tests:
        errors.append("ci.yml: manual PDF image must run every test_*_integration.py suite")

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

    deploy = workflows.get("site-deploy.yml")
    if deploy is None:
        errors.append("missing reusable latest site workflow: site-deploy.yml")
    else:
        deploy_text = json.dumps(deploy)
        deploy_inputs = deploy.get("on", {}).get("workflow_call", {}).get("inputs", {})
        if deploy_inputs.get("reviewed_sha", {}).get("required") is not True:
            errors.append("site-deploy.yml: reviewed_sha must be required")
        if deploy_inputs.get("manual-pdf-image", {}).get("required") is not True:
            errors.append("site-deploy.yml: manual-pdf-image must be required")
        for marker in [
            "refs/heads/main",
            "github.sha",
            "latest",
            "public-paths",
            "git",
            "ls-files",
            "unaltraweb-manual-pdf@sha256:",
            "MANUAL_PDF_IMAGE",
            "SOURCE_DATE_EPOCH",
            "git show --no-patch --format=%ct",
            "docker pull",
            "docker image inspect",
            "org.opencontainers.image.revision",
        ]:
            if marker not in deploy_text:
                errors.append(f"site-deploy.yml: missing latest publication gate {marker}")
        if deploy.get("permissions", {}).get("contents") != "read":
            errors.append("site-deploy.yml: reusable workflow must default to contents: read")
        deploy_build = deploy.get("jobs", {}).get("build", {})
        provenance_step = _named_step(deploy_build, "Verify manual PDF image provenance")
        if provenance_step.get("env") != {
            "WORKFLOW_REPOSITORY": "${{ job.workflow_repository }}",
            "WORKFLOW_SHA": "${{ job.workflow_sha }}",
        }:
            errors.append("site-deploy.yml: PDF worker provenance must use the defining job workflow identity")
        provenance_text = str(provenance_step.get("run") or "")
        for marker in ["MANUAL_PDF_IMAGE", "WORKFLOW_REPOSITORY", "WORKFLOW_SHA", "docker pull", "docker image inspect", "org.opencontainers.image.revision"]:
            if marker not in provenance_text:
                errors.append(f"site-deploy.yml: PDF worker provenance check missing {marker}")
        if '[[ "$image_revision" != "$WORKFLOW_SHA" ]]' not in provenance_text:
            errors.append("site-deploy.yml: PDF worker revision label must be compared with the defining workflow SHA")
        if "docker pull" in provenance_text and "docker image inspect" in provenance_text and provenance_text.index("docker pull") > provenance_text.index("docker image inspect"):
            errors.append("site-deploy.yml: PDF worker digest must be pulled before its revision label is inspected")
        if "${{ github.workflow_sha }}" in deploy_text or "${{ github.workflow_repository }}" in deploy_text:
            errors.append("site-deploy.yml: reusable provider identity must not come from the caller's github workflow context")
        build_step_names = [str(step.get("name") or "") for step in deploy_build.get("steps", []) if isinstance(step, dict)]
        if "Verify manual PDF image provenance" not in build_step_names or "Reject versioned manual publication outputs" not in build_step_names:
            errors.append("site-deploy.yml: PDF worker provenance must run before publication output processing")
        elif build_step_names.index("Verify manual PDF image provenance") > build_step_names.index("Reject versioned manual publication outputs"):
            errors.append("site-deploy.yml: PDF worker provenance must run before publication output processing")

    stable = workflows.get("site-release.yml")
    if stable is None:
        errors.append("missing reusable stable manual workflow: site-release.yml")
    else:
        stable_text = json.dumps(stable)
        if set(stable) != {"name", "on", "permissions", "concurrency", "jobs"}:
            errors.append("site-release.yml: stable workflow contains authority outside the reviewed structure")
        stable_on = stable.get("on", {})
        if set(stable_on) != {"workflow_call"}:
            errors.append("site-release.yml: stable publication must be workflow_call-only")
        workflow_call = stable_on.get("workflow_call", {})
        if set(workflow_call) != {"inputs"}:
            errors.append("site-release.yml: stable workflow_call may only declare reviewed inputs")
        stable_inputs = workflow_call.get("inputs", {})
        expected_stable_inputs = {
            "selector",
            "reviewed_sha",
            "candidate_manifest_sha256",
            "core_sha",
            "manual_pdf_image",
            "site_build_image",
            "vegavisuals_sha",
            "ruby_version",
            "python_version",
        }
        if set(stable_inputs) != expected_stable_inputs:
            errors.append("site-release.yml: stable workflow input inventory differs from the reviewed contract")
        for input_name in ["selector", "reviewed_sha", "candidate_manifest_sha256", "core_sha", "manual_pdf_image", "site_build_image"]:
            if stable_inputs.get(input_name, {}).get("required") is not True:
                errors.append(f"site-release.yml: {input_name} must be required")
        jobs = stable.get("jobs", {})
        if set(jobs) != {"prepare", "publish"}:
            errors.append("site-release.yml: stable workflow must contain only prepare and publish jobs")
        prepare = jobs.get("prepare", {})
        publish = jobs.get("publish", {})
        if stable.get("permissions") != {"contents": "read"}:
            errors.append("site-release.yml: stable workflow must default to only contents: read")
        if prepare.get("permissions") != {"contents": "read"}:
            errors.append("site-release.yml: preparation job must have only contents: read")
        expected_concurrency = {
            "group": "stable-manual-${{ github.repository }}-${{ inputs.selector }}",
            "cancel-in-progress": False,
        }
        if stable.get("concurrency") != expected_concurrency:
            errors.append("site-release.yml: stable publication must use the reviewed non-cancelling concurrency key")
        prepare_text = json.dumps(prepare)
        for forbidden in ["gh release create", "gh release edit", "contents: write"]:
            if forbidden in prepare_text:
                errors.append(f"site-release.yml: preparation job contains publication authority: {forbidden}")
        for marker in [
            "manual-release-prepare",
            "actions/upload-artifact@",
            "SHA256SUMS",
            "reviewed_sha",
            "candidate_manifest_sha256",
            "core_sha",
            "manual_pdf_image",
            "site_build_image",
            "LOCAL_CORE",
            "SOURCE_DATE_EPOCH",
            "source_date_epoch",
            "unaltraweb-mcp@sha256:",
            "UNALTRAWEB_MCP_IMAGE_REFERENCE",
            "SITE_BUILD_PYTHON_VERSION",
            "platform.python_version()",
            "visualization-check",
            "VEGAVISUALS_PATH",
            "VEGAVISUALS_DIR",
            "--network none",
            "dst=/reviewed-core,readonly",
        ]:
            if marker not in stable_text:
                errors.append(f"site-release.yml: missing stable release evidence {marker}")
        request_step = _named_step(prepare, "Validate stable release request")
        request_text = str(request_step.get("run") or "")
        request_env = request_step.get("env", {})
        if (
            request_env.get("WORKFLOW_SHA") != "${{ job.workflow_sha }}"
            or request_env.get("WORKFLOW_REF") != "${{ job.workflow_ref }}"
            or request_env.get("WORKFLOW_REPOSITORY") != "${{ job.workflow_repository }}"
        ):
            errors.append("site-release.yml: stable request must bind core authority to the defining reusable workflow")
        for marker in ["CORE_SHA", "WORKFLOW_SHA", "WORKFLOW_REF", "WORKFLOW_REPOSITORY", "WORKFLOW_FILE_PATH"]:
            if marker not in request_text:
                errors.append(f"site-release.yml: stable request identity check missing {marker}")

        expected_publish = {
            "needs": "prepare",
            "runs-on": "ubuntu-latest",
            "environment": "stable-release",
            "permissions": {"contents": "write"},
            "env": {
                "CORE_SHA": "${{ inputs.core_sha }}",
                "CANDIDATE_MANIFEST_SHA256": "${{ inputs.candidate_manifest_sha256 }}",
                "MANUAL_PDF_IMAGE": "${{ inputs.manual_pdf_image }}",
                "PYTHON_VERSION": "${{ inputs.python_version }}",
                "REVIEWED_SHA": "${{ inputs.reviewed_sha }}",
                "RUBY_VERSION": "${{ inputs.ruby_version }}",
                "SELECTOR": "${{ inputs.selector }}",
                "SITE_BUILD_IMAGE": "${{ inputs.site_build_image }}",
                "VEGAVISUALS_SHA": "${{ inputs.vegavisuals_sha }}",
            },
            "steps": [
                {
                    "name": "Download prepared candidate",
                    "uses": "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
                    "with": {
                        "name": "stable-manual-${{ inputs.selector }}-${{ inputs.reviewed_sha }}-${{ github.run_id }}-${{ github.run_attempt }}",
                        "path": "release-assets",
                    },
                },
                {
                    "name": "Checkout reviewed release verifier",
                    "uses": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
                    "with": {
                        "repository": "${{ job.workflow_repository }}",
                        "ref": "${{ job.workflow_sha }}",
                        "path": ".unaltraweb-release-core",
                        "persist-credentials": False,
                    },
                },
                {
                    "name": "Setup privileged verifier Python",
                    "uses": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                    "with": {"python-version": "${{ inputs.python_version }}"},
                },
                {
                    "name": "Publish verified stable release",
                    "env": {
                        "GH_TOKEN": "${{ github.token }}",
                        "WORKFLOW_FILE_PATH": "${{ job.workflow_file_path }}",
                        "WORKFLOW_REF": "${{ job.workflow_ref }}",
                        "WORKFLOW_REPOSITORY": "${{ job.workflow_repository }}",
                        "WORKFLOW_SHA": "${{ job.workflow_sha }}",
                    },
                    "run": "exec bash .unaltraweb-release-core/scripts/manual/publish_release.sh",
                },
            ],
        }
        if publish != expected_publish:
            errors.append("site-release.yml: privileged publication job differs from the exact reviewed structure")

    scaffold_path = ROOT / "src/unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml"
    try:
        scaffold = load_workflow(scaffold_path)
    except Exception as exc:
        errors.append(f"scaffold deploy.yml: invalid YAML: {exc}")
    else:
        scaffold_on = scaffold.get("on", {})
        if set(scaffold_on) != {"workflow_dispatch"}:
            errors.append("scaffold deploy.yml: latest deployment must be workflow_dispatch-only")
        dispatch_inputs = scaffold_on.get("workflow_dispatch", {}).get("inputs", {})
        if dispatch_inputs.get("reviewed_sha", {}).get("required") is not True:
            errors.append("scaffold deploy.yml: reviewed_sha must be required")
        scaffold_text = json.dumps(scaffold)
        for marker in ["refs/heads/main", "github.sha", "reviewed_sha"]:
            if marker not in scaffold_text:
                errors.append(f"scaffold deploy.yml: missing reviewed-main gate {marker}")
        if '"contents": "write"' in scaffold_text:
            errors.append("scaffold deploy.yml: latest Pages caller must not receive contents: write")
        reusable_jobs = _job_uses(scaffold)
        if len(reusable_jobs) != 1:
            errors.append("scaffold deploy.yml: expected exactly one reusable deployment job")
        else:
            job_name, uses = reusable_jobs[0]
            action, separator, revision = uses.rpartition("@")
            if not separator or action != "dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml" or not FULL_SHA.fullmatch(revision):
                errors.append(f"scaffold deploy.yml:{job_name}: reusable workflow must use an immutable unaltraweb SHA")
            elif revision not in REVIEWED_SITE_DEPLOY_SHAS:
                errors.append(f"scaffold deploy.yml:{job_name}: reusable workflow SHA has not been reviewed")
            reusable_job = scaffold.get("jobs", {}).get(job_name, {})
            if reusable_job.get("needs") != "validate":
                errors.append("scaffold deploy.yml: reusable deployment must depend on caller-side reviewed-main validation")
            settings = reusable_job.get("with", {})
            if settings != {"check-manual-pdf": False, "sync-manual-pdf": True}:
                errors.append("scaffold deploy.yml: bootstrap caller must use only the old-compatible PDF rebuild/sync input shape")
    return errors


def main() -> int:
    errors = validate_workflows()
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
