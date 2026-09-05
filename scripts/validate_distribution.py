#!/usr/bin/env python3
"""Validate release parity, component pins, and the modular wheel boundary."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 package dependency.
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
RELEASE_CANDIDATES_PATH = Path("release-candidates.json")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from unaltraweb_mcp import __version__  # noqa: E402
from unaltraweb_mcp.cli import (  # noqa: E402
    FACTORY_REQUIRED_COMMANDS,
    FACTORY_REQUIRED_MCP_COMMANDS,
    PACKAGE_ONLY_COMMANDS,
    PACKAGE_ONLY_MCP_COMMANDS,
)
from unaltraweb_mcp.distribution import (  # noqa: E402
    companion_dependency_requirements,
    component_contract_semantic_errors,
    component_reference,
    distribution_contract,
    is_mutable_reference,
    validate_component_contract,
)
from scripts.validate_workflows import load_workflow_text, reusable_deploy_input_errors  # noqa: E402


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        class UniqueKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping(loader, node, deep=False):
            mapping: dict[Any, Any] = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise ValueError(f"duplicate YAML key: {key}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except Exception as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc
    return value if isinstance(value, dict) else {}


def make_value(path: Path, variable: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{re.escape(variable)}\s*\?[:+]?=\s*([^\s#]+)", text)
    return match.group(1).strip('"\'') if match else ""


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract = distribution_contract()
    version = str(contract["release"]["version"])
    required_components = {
        "gem", "wheel", "runtime", "mcp", "compute_python", "compute_r", "web_capture", "manual_pdf", "diavisuals", "vegavisuals"
    }
    if contract.get("schema_version") != 1:
        errors.append("component contract schema_version must be 1")
    if set(contract.get("components", {})) != required_components:
        errors.append("component contract inventory is incomplete")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
    if RELEASE_CANDIDATES_PATH.as_posix() not in dockerignore:
        errors.append("release-candidates.json must be excluded from Docker build contexts")
    if __version__ != version:
        errors.append(f"wheel version {__version__} != contract version {version}")
    for component_id in ["gem", "wheel", "runtime", "mcp", "compute_python", "compute_r", "web_capture", "manual_pdf"]:
        if str(contract["components"][component_id]["version"]) != version:
            errors.append(f"{component_id} version does not match release {version}")
    included = {name for name, item in contract["components"].items() if item["included_in_wheel"]}
    if included != {"wheel"}:
        errors.append(f"wheel must not bundle external components: {sorted(included)}")
    wheel_contract = contract["wheel_contract"]
    if set(wheel_contract["package_only_commands"]) != PACKAGE_ONLY_COMMANDS:
        errors.append("wheel package-only command inventory does not match the CLI")
    if set(wheel_contract["factory_required_commands"]) != FACTORY_REQUIRED_COMMANDS:
        errors.append("wheel factory-required command inventory does not match the CLI")
    if set(wheel_contract["package_only_mcp"]) != PACKAGE_ONLY_MCP_COMMANDS:
        errors.append("wheel package-only MCP inventory does not match the CLI")
    if set(wheel_contract["factory_required_mcp"]) != FACTORY_REQUIRED_MCP_COMMANDS:
        errors.append("wheel factory-required MCP inventory does not match the CLI")

    schema = json.loads((root / "src/unaltraweb_mcp/component-contract.schema.json").read_text(encoding="utf-8"))
    try:
        validate_component_contract(contract, schema)
    except RuntimeError as exc:
        errors.append(f"component contract schema validation failed: {exc}")
    errors.extend(f"component contract semantic validation failed: {error}" for error in component_contract_semantic_errors(contract))
    core_sha = str(contract["consumer_integration"]["core_sha"])
    core_object = subprocess.run(
        ["git", "cat-file", "-e", f"{core_sha}^{{commit}}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if core_object.returncode != 0:
        errors.append("consumer integration core SHA is not a commit in this repository")
    else:
        core_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", core_sha, "HEAD"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if core_ancestor.returncode != 0:
            errors.append("consumer integration core SHA must be an ancestor of the current source")
        pinned_workflow = subprocess.run(
            ["git", "show", f"{core_sha}:.github/workflows/site-deploy.yml"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if pinned_workflow.returncode != 0:
            errors.append("consumer integration core SHA does not contain the reusable deploy workflow")
        else:
            try:
                pinned_deploy = load_workflow_text(pinned_workflow.stdout)
            except Exception as exc:
                errors.append(f"consumer integration workflow is invalid YAML: {exc}")
            else:
                errors.extend(
                    f"consumer integration workflow: {error}"
                    for error in reusable_deploy_input_errors(pinned_deploy)
                )
    if schema.get("properties", {}).get("schema_version", {}).get("const") != 1:
        errors.append("component contract schema does not select version 1")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    if "version" in project or project.get("dynamic") != ["version"]:
        errors.append("pyproject version must be derived from the package component contract")
    if pyproject.get("tool", {}).get("setuptools", {}).get("dynamic", {}).get("version", {}).get("attr") != "unaltraweb_mcp.__version__":
        errors.append("setuptools dynamic version is not wired to unaltraweb_mcp.__version__")
    ruby_version_source = (root / "lib/unaltraweb/version.rb").read_text(encoding="utf-8")
    if "component-contract.json" not in ruby_version_source or re.search(r'VERSION\s*=\s*["\']\d', ruby_version_source):
        errors.append("gem version must be derived from the package component contract")
    gemspec = (root / "unaltraweb.gemspec").read_text(encoding="utf-8")
    if 'spec.required_ruby_version = ">= 3.2"' not in gemspec:
        errors.append("gemspec Ruby requirement must support the Bundler 4 scaffold lock")
    for asset in ["component-contract.json", "component-contract.schema.json"]:
        if gemspec.count(f'"src/unaltraweb_mcp/{asset}"') < 2:
            errors.append(f"gemspec must discover and select {asset}")
    runtime_base = (root / "Dockerfile").read_text(encoding="utf-8").splitlines()[0]
    if not re.fullmatch(r"FROM ruby:[0-9]+\.[0-9]+\.[0-9]+-slim@sha256:[0-9a-f]{64}", runtime_base):
        errors.append("Dockerfile runtime base must pin an exact Ruby patch version and image digest")

    manifest = load_yaml(root / "mcp-factory.yml")
    if str(manifest.get("version")) != version:
        errors.append("mcp-factory.yml version does not match the component contract")
    if str(manifest.get("release", {}).get("default")) != contract["release"]["tag"]:
        errors.append("mcp-factory.yml release.default does not match the component contract")
    if str(manifest.get("runtime", {}).get("image")) != component_reference("mcp"):
        errors.append("mcp-factory.yml runtime image does not match the component contract")

    dependencies = {
        str(item.get("name")): item
        for item in manifest.get("mcp_dependencies", [])
        if isinstance(item, dict)
    }
    for component_id in ["diavisuals", "vegavisuals"]:
        expected = contract["components"][component_id]
        actual = dependencies.get(component_id, {})
        requirements = companion_dependency_requirements(component_id)
        expected_remote = expected["repository"] + ".git"
        for key, selected in [
            ("version", expected["version"]),
            ("release", expected["release"]),
            ("release_status", expected["release_status"]),
            ("remote", expected_remote),
        ]:
            if str(actual.get(key) or "") != selected:
                errors.append(f"{component_id} {key} does not match the selected companion release")
        if not str(actual.get("remote") or "").startswith("https://"):
            errors.append(f"{component_id} remote must use HTTPS")
        for key, selected in requirements["lifecycle"].items():
            if actual.get(key) is not selected:
                errors.append(f"{component_id} lifecycle flag {key} must be {selected}")
        if actual.get("uv_spec") != requirements["uv_spec"]:
            errors.append(f"{component_id} uv_spec must select its immutable companion release")
        missing_tools = set(requirements["tools"]) - set(actual.get("required_tools", []))
        missing_resources = set(requirements["resources"]) - set(actual.get("required_resources", []))
        if missing_tools:
            errors.append(f"{component_id} dependency is missing required tools: {sorted(missing_tools)}")
        if missing_resources:
            errors.append(f"{component_id} dependency is missing required resources: {sorted(missing_resources)}")

    make_pins = {
        "MCP_RUNTIME_IMAGE": "runtime",
        "MCP_IMAGE": "mcp",
        "WEB_CAPTURE_IMAGE": "web_capture",
        "DOCKER_IMAGE": "runtime",
        "MANUAL_PDF_IMAGE": "manual_pdf",
    }
    for variable, component_id in make_pins.items():
        actual = make_value(root / "Makefile", variable)
        expected = component_reference(component_id)
        if actual != expected:
            errors.append(f"Makefile {variable}={actual or 'missing'} != {expected}")

    pinned_text = {
        "scripts/computations/render.py": [component_reference("compute_python"), component_reference("compute_r")],
        "scripts/web_captures/render.py": [component_reference("web_capture")],
        "scripts/unaltraweb-mcp-bootstrap.sh": [component_reference("mcp")],
        "Dockerfile.mcp": [component_reference("runtime")],
    }
    for relative, references in pinned_text.items():
        text = (root / relative).read_text(encoding="utf-8")
        for reference in references:
            if reference not in text:
                errors.append(f"{relative} does not contain selected reference {reference}")
        if re.search(r"ghcr\.io/dosquartsdedocs/[^\s\"']+:(?:main|latest)\b", text):
            errors.append(f"{relative} contains a mutable production default")

    scaffold_templates = {
        "Gemfile.tmpl": ["__GEM_VERSION__", "__CORE_REPOSITORY__", "__CORE_SHA__"],
        "Gemfile.lock.tmpl": ["__GEM_VERSION__", "__CORE_REPOSITORY__", "__CORE_SHA__"],
        "Makefile.tmpl": ["__MCP_IMAGE__"],
        ".github/workflows/deploy.yml.tmpl": [
            "__SITE_DEPLOY_WORKFLOW__",
            "__CORE_SHA__",
            "__MANUAL_PDF_IMAGE__",
            "__VEGAVISUALS_SHA__",
        ],
        ".github/dependabot.yml.tmpl": ["__SITE_DEPLOY_WORKFLOW__"],
    }
    for name, tokens in scaffold_templates.items():
        text = (root / "src/unaltraweb_mcp/scaffolds/common" / name).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                errors.append(f"scaffold {name} must derive {token} from the component contract")
    computation_template = (root / "src/unaltraweb_mcp/scaffolds/profiles/unaltremanual/computations.yml.tmpl").read_text(encoding="utf-8")
    for token in ["__COMPUTE_PYTHON_IMAGE__", "__COMPUTE_R_IMAGE__"]:
        if token not in computation_template:
            errors.append(f"unaltremanual computation scaffold is missing component token {token}")

    release_references = [
        item["reference"]
        for item in contract["components"].values()
        if item["kind"] in {"container", "companion"}
    ]
    for reference in release_references:
        if is_mutable_reference(str(reference)):
            errors.append(f"component contract contains a mutable release reference: {reference}")

    package_root = root / "src/unaltraweb_mcp"
    forbidden = ["mcp-factory.yml", "Dockerfile", "Makefile", "docs", "scripts", "_layouts", "_includes", "_sass"]
    for name in forbidden:
        if (package_root / name).exists():
            errors.append(f"wheel boundary contains factory asset: {name}")
    if not (package_root / "scaffolds").is_dir():
        errors.append("wheel boundary is missing package-owned scaffolds")

    ruby = shutil.which("ruby")
    if ruby:
        completed = subprocess.run(
            [ruby, "-Ilib", "-runaltraweb/version", "-e", "print Unaltraweb::VERSION"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0 or completed.stdout != version:
            errors.append(f"gem version parity failed: {completed.stderr.strip() or completed.stdout}")
    return errors


def release_tag_status_errors(
    contract: dict[str, Any],
    *,
    ref_type: str,
    ref_name: str,
) -> list[str]:
    release_tag = str(contract.get("release", {}).get("tag") or "")
    if ref_type != "tag" or ref_name != release_tag:
        return []
    errors: list[str] = []
    for component_id, component in sorted(contract.get("components", {}).items()):
        status = str(component.get("release_status") or "") if isinstance(component, dict) else ""
        if status not in {"ready", "released"}:
            errors.append(
                f"{component_id} must be release-ready before publishing exact release tag {release_tag}; found {status or '<unset>'}"
            )
    return errors


def release_candidate_receipt_errors(
    contract: dict[str, Any],
    receipt: Any,
    *,
    parent_commit: str = "",
    changed_paths: list[str] | None = None,
    default_branch_ancestor: bool | None = None,
) -> list[str]:
    errors: list[str] = []
    ready_components = {
        component_id: component
        for component_id, component in contract.get("components", {}).items()
        if isinstance(component, dict) and component.get("release_status") == "ready"
    }
    if not isinstance(receipt, dict):
        return ["release candidate receipt must be a JSON object"]
    if receipt.get("schema_version") != 1:
        errors.append("release candidate receipt schema_version must be 1")
    release = contract.get("release", {})
    if receipt.get("release") != release.get("tag"):
        errors.append(f"release candidate receipt must select {release.get('tag')}")
    source_commit = str(receipt.get("source_commit") or "")
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        errors.append("release candidate receipt source_commit must be a full lowercase Git SHA")
    if parent_commit and source_commit != parent_commit:
        errors.append("release candidate receipt source_commit must be the parent of the release metadata commit")
    if default_branch_ancestor is False:
        errors.append("release candidate source commit must belong to the default branch")
    if changed_paths is not None and changed_paths != [RELEASE_CANDIDATES_PATH.as_posix()]:
        errors.append("release metadata commit may change only release-candidates.json")

    candidates = receipt.get("components")
    if not isinstance(candidates, dict):
        errors.append("release candidate receipt components must be an object")
        candidates = {}
    if set(candidates) != set(ready_components):
        errors.append("release candidate receipt components must exactly match ready BOM components")
    for component_id, component in ready_components.items():
        candidate = candidates.get(component_id)
        if not isinstance(candidate, dict):
            continue
        if component.get("kind") == "container":
            reference = str(candidate.get("reference") or "")
            image_repository = str(component.get("image_repository") or "")
            if re.fullmatch(rf"{re.escape(image_repository)}@sha256:[0-9a-f]{{64}}", reference) is None:
                errors.append(f"{component_id} candidate reference must use an immutable digest from {image_repository}")
            if set(candidate) != {"reference"}:
                errors.append(f"{component_id} container candidate may contain only reference")
        elif component.get("kind") in {"gem", "python-wheel"}:
            artifact = str(candidate.get("artifact") or "")
            sha256 = str(candidate.get("sha256") or "")
            expected_artifact = (
                f"{component['name']}-{component['version']}.gem"
                if component.get("kind") == "gem"
                else f"{str(component['name']).replace('-', '_')}-{component['version']}-py3-none-any.whl"
            )
            if artifact != expected_artifact:
                errors.append(f"{component_id} candidate artifact must be {expected_artifact}")
            if re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
                errors.append(f"{component_id} candidate sha256 must be a lowercase SHA-256 digest")
            if set(candidate) != {"artifact", "sha256"}:
                errors.append(f"{component_id} package candidate must contain only artifact and sha256")
        else:
            errors.append(f"{component_id} must be released instead of using a candidate receipt")
    return errors


def load_release_candidate_receipt_errors(root: Path, contract: dict[str, Any]) -> list[str]:
    path = root / RELEASE_CANDIDATES_PATH
    if not path.is_file():
        return [f"missing release candidate receipt: {RELEASE_CANDIDATES_PATH}"]

    def unique_object(pairs):
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid release candidate receipt: {exc}"]
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if parent.returncode != 0:
        return [f"could not inspect release candidate source commit: {parent.stderr.strip() or parent.stdout.strip()}"]
    parent_commit = parent.stdout.strip()
    changed = subprocess.run(
        ["git", "diff", "--name-only", parent_commit, "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if changed.returncode != 0:
        return [f"could not inspect release metadata commit: {changed.stderr.strip() or changed.stdout.strip()}"]
    changed_paths = [line for line in changed.stdout.splitlines() if line]
    default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "").strip()
    if not default_branch:
        symbolic = subprocess.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if symbolic.returncode != 0 or not symbolic.stdout.strip().startswith("origin/"):
            return ["could not determine the default branch for release candidate ancestry validation"]
        default_branch = symbolic.stdout.strip().removeprefix("origin/")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", parent_commit, f"origin/{default_branch}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestor.returncode not in {0, 1}:
        return [f"could not verify default-branch ancestry: {ancestor.stderr.decode().strip()}"]
    default_branch_ancestor = ancestor.returncode == 0
    return release_candidate_receipt_errors(
        contract,
        receipt,
        parent_commit=parent_commit,
        changed_paths=changed_paths,
        default_branch_ancestor=default_branch_ancestor,
    )


def publish_ref_errors(
    contract: dict[str, Any],
    *,
    ref_type: str,
    ref_name: str,
    default_branch: str,
    component_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    release = contract.get("release", {})
    version = str(release.get("version") or "")
    release_tag = str(release.get("tag") or "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or release_tag != f"v{version}":
        errors.append("distribution release must use matching X.Y.Z and vX.Y.Z values")

    components = contract.get("components", {})
    for component_id in component_ids:
        component = components.get(component_id)
        if not isinstance(component, dict):
            errors.append(f"unknown publish component: {component_id}")
            continue
        if str(component.get("version") or "") != version:
            errors.append(f"{component_id} publish version does not match distribution release {version}")
        if str(component.get("release") or "") != release_tag:
            errors.append(f"{component_id} publish tag does not match distribution release {release_tag}")

    if ref_type == "branch" and ref_name == default_branch and default_branch:
        return errors
    if ref_type == "tag" and ref_name == release_tag:
        errors.extend(release_tag_status_errors(contract, ref_type=ref_type, ref_name=ref_name))
        return errors
    errors.append(f"publish ref must be the default branch {default_branch or '<unset>'} or exact release tag {release_tag or '<unset>'}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help="Fail when a selected component release is pending or unavailable.",
    )
    parser.add_argument(
        "--validate-publish-ref",
        action="store_true",
        help="Require the default branch or exact distribution release tag; release tags require every component to be ready or released.",
    )
    parser.add_argument(
        "--components",
        default="",
        help="Comma-separated component IDs whose versions and release tags must match before publication.",
    )
    args = parser.parse_args(argv)
    errors = validate()
    release_tag_errors: list[str] = []
    candidate_receipt_errors: list[str] = []
    other_publish_errors: list[str] = []
    contract = distribution_contract()
    if args.validate_publish_ref:
        component_ids = [item.strip() for item in args.components.split(",") if item.strip()]
        if not component_ids:
            errors.append("--validate-publish-ref requires at least one --components value")
        ref_type = os.environ.get("GITHUB_REF_TYPE", "")
        ref_name = os.environ.get("GITHUB_REF_NAME", "")
        release_tag_errors = release_tag_status_errors(contract, ref_type=ref_type, ref_name=ref_name)
        publish_errors = publish_ref_errors(
            contract,
            ref_type=ref_type,
            ref_name=ref_name,
            default_branch=os.environ.get("GITHUB_DEFAULT_BRANCH", ""),
            component_ids=component_ids,
        )
        other_publish_errors = [error for error in publish_errors if error not in release_tag_errors]
        errors.extend(publish_errors)
    pending = sorted(
        component_id for component_id, selected in contract["components"].items()
        if selected["release_status"] == "pending"
    )
    unavailable = sorted(
        component_id for component_id, selected in contract["components"].items()
        if selected["release_status"] == "unavailable"
    )
    ready = sorted(
        component_id for component_id, selected in contract["components"].items()
        if selected["release_status"] == "ready"
    )
    exact_release_tag = (
        args.validate_publish_ref
        and os.environ.get("GITHUB_REF_TYPE") == "tag"
        and os.environ.get("GITHUB_REF_NAME") == contract.get("release", {}).get("tag")
    )
    if ready and (args.require_release_ready or exact_release_tag):
        candidate_receipt_errors = load_release_candidate_receipt_errors(ROOT, contract)
        errors.extend(candidate_receipt_errors)
    print(json.dumps({
        "ok": not errors,
        "release_ready": not errors and not pending and not unavailable,
        "errors": errors,
        "pending_releases": pending,
        "unavailable_releases": unavailable,
    }, indent=2, sort_keys=True))
    readiness_errors = release_tag_errors + candidate_receipt_errors
    structural_errors = [error for error in errors if error not in readiness_errors]
    if structural_errors or other_publish_errors:
        return 1
    if readiness_errors or (args.require_release_ready and (pending or unavailable)):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
