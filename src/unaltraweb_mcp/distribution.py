from __future__ import annotations

import json
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from .processes import run_process


CONTRACT_NAME = "component-contract.json"
CONTRACT_SCHEMA_NAME = "component-contract.schema.json"
DOCTOR_SCHEMA_VERSION = 1
MUTABLE_TAGS = {"edge", "latest", "main", "master", "nightly", "stable"}


def _strict_json(path: Path) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"non-finite JSON number is not allowed: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def _schema_type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _validate_schema_value(value: Any, rule: dict[str, Any], root: dict[str, Any], path: str) -> None:
    if "$ref" in rule:
        reference = str(rule["$ref"])
        if not reference.startswith("#/"):
            raise RuntimeError(f"Unsupported external schema reference at {path}: {reference}")
        selected: Any = root
        for part in reference[2:].split("/"):
            selected = selected[part.replace("~1", "/").replace("~0", "~")]
        _validate_schema_value(value, selected, root, path)
        return
    expected_type = rule.get("type")
    if expected_type and not _schema_type_matches(value, str(expected_type)):
        raise RuntimeError(f"Component contract {path} must have type {expected_type}.")
    if "const" in rule and value != rule["const"]:
        raise RuntimeError(f"Component contract {path} must equal {rule['const']!r}.")
    if "enum" in rule and value not in rule["enum"]:
        raise RuntimeError(f"Component contract {path} is not one of {rule['enum']!r}.")
    if "pattern" in rule and isinstance(value, str) and re.search(str(rule["pattern"]), value) is None:
        raise RuntimeError(f"Component contract {path} does not match {rule['pattern']!r}.")
    if isinstance(value, dict):
        properties = rule.get("properties") if isinstance(rule.get("properties"), dict) else {}
        required = rule.get("required") if isinstance(rule.get("required"), list) else []
        missing = [key for key in required if key not in value]
        if missing:
            raise RuntimeError(f"Component contract {path} is missing required keys: {missing}.")
        additional = rule.get("additionalProperties", True)
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key in properties:
                _validate_schema_value(item, properties[key], root, item_path)
            elif additional is False:
                raise RuntimeError(f"Component contract {item_path} is not allowed by the schema.")
            elif isinstance(additional, dict):
                _validate_schema_value(item, additional, root, item_path)
    if isinstance(value, list):
        if rule.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise RuntimeError(f"Component contract {path} must contain unique items.")
        items = rule.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_schema_value(item, items, root, f"{path}[{index}]")


def validate_component_contract(value: dict[str, Any], schema: dict[str, Any]) -> None:
    _validate_schema_value(value, schema, schema, "$")


def component_contract_semantic_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    release = value["release"]
    release_version = str(release["version"])
    if release["tag"] != f"v{release_version}":
        errors.append("release tag must equal v plus the release version")
    for component_id, selected in value["components"].items():
        version = str(selected["version"])
        component_release = str(selected["release"])
        reference = str(selected["reference"])
        repository = str(selected["repository"])
        image_repository = str(selected.get("image_repository") or "")
        image_repository_valid = re.fullmatch(
            r"ghcr\.io/dosquartsdedocs/[a-z0-9._-]+",
            image_repository,
        ) is not None
        digest_pinned = bool(image_repository_valid and re.fullmatch(
            rf"{re.escape(image_repository)}@sha256:[0-9a-f]{{64}}",
            reference,
        ))
        if component_release != f"v{version}":
            errors.append(f"{component_id} release must equal v plus its version")
        kind = selected["kind"]
        if component_id == "mcp" and selected["release_status"] == "released":
            errors.append("mcp release status must remain ready because its publication digest is recorded externally")
        if kind == "container" and not image_repository_valid:
            errors.append(f"{component_id} container must declare a valid image repository")
        elif kind != "container" and image_repository:
            errors.append(f"{component_id} non-container must not declare an image repository")
        if kind == "companion" and selected["release_status"] == "ready":
            errors.append(f"{component_id} companion must be released before coordinated publication")
        if kind == "gem" and reference != f"{selected['name']} (= {version})":
            errors.append(f"{component_id} gem reference does not match its version")
        elif kind == "python-wheel" and reference != f"{selected['name']}=={version}":
            errors.append(f"{component_id} wheel reference does not match its version")
        elif kind == "container" and not (
            reference == f"{image_repository}:{version}"
            or digest_pinned
        ):
            errors.append(f"{component_id} container reference does not match its version")
        elif kind == "container" and component_id != "mcp" and selected["release_status"] == "released" and not digest_pinned:
            errors.append(f"{component_id} released container reference must use an immutable digest")
        elif kind == "companion" and reference != f"{repository}.git@{component_release}":
            errors.append(f"{component_id} companion reference does not match its repository and release")
    included = {name for name, item in value["components"].items() if item["included_in_wheel"]}
    if included != {"wheel"}:
        errors.append("only the wheel component may be included in the wheel")
    expected_not_bundled = set(value["components"]) - {"wheel"}
    if set(value["wheel_contract"]["not_bundled"]) != expected_not_bundled:
        errors.append("wheel_contract.not_bundled must list every external component exactly")
    return errors


@lru_cache(maxsize=1)
def _contract() -> dict[str, Any]:
    path = Path(__file__).resolve().with_name(CONTRACT_NAME)
    schema_path = path.with_name(CONTRACT_SCHEMA_NAME)
    try:
        value = _strict_json(path)
        schema = _strict_json(schema_path)
        if not isinstance(value, dict) or not isinstance(schema, dict):
            raise RuntimeError("Component contract and schema roots must be JSON objects.")
        validate_component_contract(value, schema)
        semantic_errors = component_contract_semantic_errors(value)
        if semantic_errors:
            raise RuntimeError("; ".join(semantic_errors))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
        raise RuntimeError(f"Unsupported or invalid package component contract: {path}: {exc}") from exc
    return value


def distribution_contract() -> dict[str, Any]:
    """Return an isolated copy of the package-owned component BOM."""
    return json.loads(json.dumps(_contract()))


def distribution_version() -> str:
    return str(_contract()["release"]["version"])


def component(component_id: str) -> dict[str, Any]:
    try:
        value = _contract()["components"][component_id]
    except KeyError as exc:
        raise KeyError(f"Unknown unaltraweb component: {component_id}") from exc
    return dict(value)


def component_reference(component_id: str) -> str:
    return str(component(component_id)["reference"])


def companion_dependency_requirements(component_id: str) -> dict[str, Any]:
    capabilities = {
        "diavisuals": {
            "tools": [
                "compatibility_status",
                "release_status",
                "factory_manifest",
                "project_check",
                "render_diagram",
                "render_diagram_text",
            ],
            "resources": ["diavisuals://project/check", "diavisuals://factory-manifest"],
        },
        "vegavisuals": {
            "tools": [
                "initialize_project",
                "validate_visualization",
                "render_visualization",
                "visualization_status",
                "visualization_check",
                "render_visualizations",
                "compatibility_status",
                "release_status",
                "factory_manifest",
            ],
            "resources": ["vegavisuals://project/check", "vegavisuals://factory-manifest"],
        },
    }
    if component_id not in capabilities:
        raise KeyError(f"Unknown unaltraweb companion: {component_id}")
    selected = component(component_id)
    return {
        "lifecycle": {
            "required": True,
            "install": True,
            "build": True,
            "init": False,
            "check": True,
            "smoke": True,
            "update": False,
        },
        "uv_spec": f"{component_id}[mcp] @ git+{selected['reference']}",
        **capabilities[component_id],
    }


def is_mutable_reference(reference: str) -> bool:
    value = reference.strip().lower()
    if not value:
        return True
    if re.search(r"@sha256:[0-9a-f]{64}$", value):
        return False
    if value.startswith("http") and ".git@" in value:
        selected = value.rsplit("@", 1)[-1]
        return selected in MUTABLE_TAGS or selected.startswith("refs/heads/")
    if "@" in value:
        return True
    image_name = value.rsplit("/", 1)[-1]
    if ":" not in image_name:
        return True
    tag = image_name.rsplit(":", 1)[-1]
    return not tag or tag in MUTABLE_TAGS


def _finding(
    code: str,
    severity: str,
    expected: Any,
    actual: Any,
    remediation: str,
    *,
    component_id: str = "",
) -> dict[str, Any]:
    finding = {
        "code": code,
        "severity": severity,
        "expected": expected,
        "actual": actual,
        "remediation": remediation,
    }
    if component_id:
        finding["component"] = component_id
    return finding


def _load_yaml(path: Path) -> dict[str, Any]:
    from .site_tools import load_yaml_file

    return load_yaml_file(path)


def _make_value(path: Path, variable: str) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"(?m)^{re.escape(variable)}\s*\?[:+]?=\s*([^\s#]+)", text)
    return match.group(1).strip('"\'') if match else ""


def _factory_findings(factory: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    contract = _contract()
    expected_version = distribution_version()
    manifest = _load_yaml(factory / "mcp-factory.yml")
    actual_version = str(manifest.get("version") or "")
    findings.append(
        _finding(
            "UW-DIST-FACTORY-VERSION",
            "info" if actual_version == expected_version else "error",
            expected_version,
            actual_version or "unreadable",
            "No action required." if actual_version == expected_version else "Use a factory checkout from the wheel's selected release.",
        )
    )

    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    actual_mcp = str(runtime.get("image") or "")
    expected_mcp = component_reference("mcp")
    findings.append(
        _finding(
            "UW-DIST-FACTORY-MCP-PIN",
            "info" if actual_mcp == expected_mcp else "error",
            expected_mcp,
            actual_mcp or "missing",
            "No action required." if actual_mcp == expected_mcp else "Align runtime.image with the package component contract.",
            component_id="mcp",
        )
    )

    dependencies = manifest.get("mcp_dependencies") if isinstance(manifest.get("mcp_dependencies"), list) else []
    dependency_map = {str(item.get("name")): item for item in dependencies if isinstance(item, dict)}
    receipt_tools = {"diavisuals": "project_check", "vegavisuals": "visualization_check"}
    for component_id in ["diavisuals", "vegavisuals"]:
        expected = contract["components"][component_id]
        dependency = dependency_map.get(component_id, {})
        requirements = companion_dependency_requirements(component_id)
        actual = {
            "version": str(dependency.get("version") or ""),
            "release": str(dependency.get("release") or ""),
            "release_status": str(dependency.get("release_status") or ""),
            "remote": str(dependency.get("remote") or ""),
        }
        selected = {
            "version": expected["version"],
            "release": expected["release"],
            "release_status": expected["release_status"],
            "remote": expected["repository"] + ".git",
        }
        findings.append(
            _finding(
                "UW-DIST-COMPANION-PIN",
                "info" if actual == selected else "error",
                selected,
                actual,
                "No action required." if actual == selected else f"Pin {component_id} to the selected HTTPS release metadata.",
                component_id=component_id,
            )
        )
        expected_lifecycle = requirements["lifecycle"]
        actual_lifecycle = {key: dependency.get(key) for key in expected_lifecycle}
        findings.append(
            _finding(
                "UW-DIST-COMPANION-LIFECYCLE",
                "info" if actual_lifecycle == expected_lifecycle else "error",
                expected_lifecycle,
                actual_lifecycle,
                (
                    "No action required."
                    if actual_lifecycle == expected_lifecycle
                    else f"Align {component_id} dependency lifecycle with the required ContExt contract."
                ),
                component_id=component_id,
            )
        )
        actual_uv_spec = str(dependency.get("uv_spec") or "")
        findings.append(
            _finding(
                "UW-DIST-COMPANION-INSTALL-SPEC",
                "info" if actual_uv_spec == requirements["uv_spec"] else "error",
                requirements["uv_spec"],
                actual_uv_spec or "missing",
                (
                    "No action required."
                    if actual_uv_spec == requirements["uv_spec"]
                    else f"Use the selected immutable {component_id} release in uv_spec."
                ),
                component_id=component_id,
            )
        )
        declared_tools = dependency.get("required_tools") if isinstance(dependency.get("required_tools"), list) else []
        declared_resources = dependency.get("required_resources") if isinstance(dependency.get("required_resources"), list) else []
        missing_capabilities = sorted(
            (set(requirements["tools"]) - set(declared_tools))
            | (set(requirements["resources"]) - set(declared_resources))
        )
        findings.append(
            _finding(
                "UW-DIST-COMPANION-CAPABILITIES",
                "info" if not missing_capabilities else "error",
                {"tools": requirements["tools"], "resources": requirements["resources"]},
                {"tools": declared_tools, "resources": declared_resources},
                (
                    "No action required."
                    if not missing_capabilities
                    else f"Require the missing {component_id} tools and resources: {', '.join(missing_capabilities)}."
                ),
                component_id=component_id,
            )
        )
        receipt_tool = receipt_tools[component_id]
        findings.append(
            _finding(
                "UW-DIST-COMPANION-RECEIPT-TOOL",
                "info" if receipt_tool in declared_tools else "error",
                receipt_tool,
                declared_tools,
                "No action required." if receipt_tool in declared_tools else f"Require {receipt_tool} from {component_id} before enforcing its provider receipt.",
                component_id=component_id,
            )
        )

    makefile = factory / "Makefile"
    make_pins = {
        "MCP_RUNTIME_IMAGE": "runtime",
        "MCP_IMAGE": "mcp",
        "WEB_CAPTURE_IMAGE": "web_capture",
        "DOCKER_IMAGE": "runtime",
        "MANUAL_PDF_IMAGE": "manual_pdf",
    }
    for variable, component_id in make_pins.items():
        expected = component_reference(component_id)
        actual = _make_value(makefile, variable)
        findings.append(
            _finding(
                "UW-DIST-FACTORY-COMPONENT-PIN",
                "info" if actual == expected else "error",
                expected,
                actual or f"{variable} missing",
                "No action required." if actual == expected else f"Set {variable} to the selected component reference.",
                component_id=component_id,
            )
        )
    return findings


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _project_image_references(config: dict[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    engines = config.get("engines") if isinstance(config.get("engines"), dict) else {}
    for engine in ["python", "r"]:
        settings = engines.get(engine) if isinstance(engines.get(engine), dict) else {}
        for key in ["image", "base_image"]:
            value = str(settings.get(key) or "").strip()
            if value:
                references.append((f"{engine}.{key}", value))
        environments = settings.get("environments") if isinstance(settings.get("environments"), dict) else {}
        for name, value in environments.items():
            if str(value).strip():
                references.append((f"{engine}.environments.{name}", str(value).strip()))
    return references


def _has_files(project: Path, patterns: list[str], roots: list[str]) -> bool:
    for root_name in roots:
        root = project / root_name
        if not root.is_dir():
            continue
        for pattern in patterns:
            if next(root.rglob(pattern), None) is not None:
                return True
    return False


def _project_findings(project: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str], list[str]]:
    findings: list[dict[str, Any]] = []
    images: dict[str, str] = {}
    selected_components = ["wheel"]
    if not project.exists() or not project.is_dir():
        findings.append(_finding("UW-DIST-PROJECT", "error", "existing project directory", str(project), "Pass an existing consumer project directory."))
        return findings, {"supplied": True, "path": str(project), "is_unaltraweb_site": False}, images, selected_components

    from . import site_tools

    detection = site_tools.detect_site(project)
    config = site_tools.site_config(project)
    is_site = bool(detection["is_unaltraweb_site"])
    profile = site_tools.site_profile(config)
    project_state: dict[str, Any] = {
        "supplied": True,
        "path": str(project),
        "is_unaltraweb_site": is_site,
        "profile": profile,
    }
    findings.append(
        _finding(
            "UW-DIST-PROJECT-CONFIG",
            "info" if is_site else "warning",
            "unaltraweb consumer markers in _config.yml and Gemfile",
            "unaltraweb consumer site" if is_site else "no complete consumer markers",
            "No action required." if is_site else "Pass an unaltraweb site or omit --project for distribution-only checks.",
        )
    )
    if not is_site:
        return findings, project_state, images, selected_components

    selected_components.extend(["gem", "mcp"])
    gem_version = component("gem")["version"]
    gemfile = (project / "Gemfile").read_text(encoding="utf-8", errors="ignore") if (project / "Gemfile").is_file() else ""
    exact_gem = bool(re.search(rf"(?m)^\s*gem\s+['\"]unaltraweb['\"]\s*,\s*['\"](?:=\s*)?{re.escape(gem_version)}['\"]", gemfile))
    lock_text = (project / "Gemfile.lock").read_text(encoding="utf-8", errors="ignore") if (project / "Gemfile.lock").is_file() else ""
    lock_match = re.search(r"(?m)^\s{2}unaltraweb \(= ([^)]+)\)\s*$", lock_text)
    locked_gem = lock_match.group(1) if lock_match else ""
    gem_ok = exact_gem and locked_gem == gem_version
    findings.append(
        _finding(
            "UW-DIST-PROJECT-GEM-PIN",
            "info" if gem_ok else "warning",
            f"Gemfile and Gemfile.lock pin {gem_version}",
            {"gemfile_exact": exact_gem, "lock_version": locked_gem or "missing"},
            "No action required." if gem_ok else "Pin the gem to the selected release and refresh Gemfile.lock.",
            component_id="gem",
        )
    )

    makefile = project / "Makefile"
    expected_mcp = component_reference("mcp")
    actual_mcp = _make_value(makefile, "MCP_IMAGE")
    mcp_severity = "info" if actual_mcp == expected_mcp else ("warning" if not actual_mcp else "error")
    findings.append(
        _finding(
            "UW-DIST-PROJECT-MCP-PIN",
            mcp_severity,
            expected_mcp,
            actual_mcp or "MCP_IMAGE not declared",
            "No action required." if actual_mcp == expected_mcp else "Use the selected MCP image, or document an intentional immutable override.",
            component_id="mcp",
        )
    )
    images["mcp"] = actual_mcp or expected_mcp

    runtime_image = _make_value(makefile, "DOCKER_IMAGE")
    if runtime_image:
        selected_components.append("runtime")
        images["runtime"] = runtime_image

    computations_path = project / ".unaltraweb/computations.yml"
    computation_sources = _has_files(project, ["*.qmd", "*.Rmd", "*.rmd", "*.R", "*.r", "*.py", "*.ipynb"], ["_chapters", "assets"])
    computation_enabled = computations_path.is_file() or computation_sources
    capture_enabled = _has_files(project, ["*.capture.yml", "*.capture.yaml"], ["assets", "_chapters"])
    pdf_enabled = _nested(config, "unaltraweb", "manual", "pdf", "enabled") is True
    vega_enabled = (project / ".vegavisuals.yml").is_file()
    diagram_enabled = _has_files(project, ["*.mmd", "*.mermaid", "*.puml", "*.plantuml", "*.uml"], ["assets", "_chapters", "_documentation"])
    features = {
        "manual_computations": computation_enabled,
        "web_captures": capture_enabled,
        "manual_pdf": pdf_enabled,
        "vegavisuals": vega_enabled,
        "diavisuals": diagram_enabled,
    }
    project_state["features"] = features

    if computation_enabled:
        computation_config = _load_yaml(computations_path)
        configured_engines = computation_config.get("engines") if isinstance(computation_config.get("engines"), dict) else {}
        engine_ids = [engine for engine in ["python", "r"] if engine in configured_engines]
        if not engine_ids:
            engine_ids = ["python", "r"]
        for engine in engine_ids:
            component_id = f"compute_{engine}"
            selected_components.append(component_id)
            settings = configured_engines.get(engine) if isinstance(configured_engines.get(engine), dict) else {}
            images[component_id] = str(settings.get("image") or component_reference(component_id))
        for location, reference in _project_image_references(computation_config):
            if is_mutable_reference(reference):
                findings.append(
                    _finding(
                        "UW-DIST-PROJECT-MUTABLE-PIN",
                        "warning",
                        "version tag or digest",
                        f"{location}={reference}",
                        "Replace mutable worker tags with a release tag or digest.",
                    )
                )

    if capture_enabled:
        selected_components.append("web_capture")
        images["web_capture"] = _make_value(makefile, "WEB_CAPTURE_IMAGE") or component_reference("web_capture")
    if pdf_enabled:
        selected_components.append("manual_pdf")
        images["manual_pdf"] = _make_value(makefile, "MANUAL_PDF_IMAGE") or component_reference("manual_pdf")
    if vega_enabled:
        selected_components.append("vegavisuals")
    if diagram_enabled:
        selected_components.append("diavisuals")

    for component_id, reference in images.items():
        if is_mutable_reference(reference):
            findings.append(
                _finding(
                    "UW-DIST-PROJECT-MUTABLE-PIN",
                    "warning",
                    "version tag or digest",
                    reference,
                    "Replace mutable runtime tags with a release tag or digest.",
                    component_id=component_id,
                )
            )
    return findings, project_state, images, list(dict.fromkeys(selected_components))


def _docker_findings(images: dict[str, str]) -> list[dict[str, Any]]:
    if not shutil.which("docker"):
        return [_finding("UW-DIST-DOCKER-AVAILABLE", "info", "optional Docker CLI", "not installed", "Install Docker only when container-backed features are needed.")]
    try:
        version = run_process(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            timeout_seconds=5,
        )
    except OSError as exc:
        return [_finding("UW-DIST-DOCKER-AVAILABLE", "warning", "reachable optional Docker daemon", str(exc), "Start Docker or rerun doctor without --docker.")]
    if version.returncode != 0:
        return [_finding("UW-DIST-DOCKER-AVAILABLE", "warning", "reachable optional Docker daemon", version.stderr.strip() or "unavailable", "Start Docker or rerun doctor without --docker.")]

    findings = [_finding("UW-DIST-DOCKER-AVAILABLE", "info", "reachable optional Docker daemon", version.stdout.strip() or "available", "No action required.")]
    for component_id, reference in images.items():
        try:
            inspected = run_process(
                ["docker", "image", "inspect", reference, "--format", "{{.Id}}"],
                timeout_seconds=5,
            )
        except OSError as exc:
            findings.append(
                _finding(
                    "UW-DIST-IMAGE-PRESENCE",
                    "warning",
                    f"optional local image {reference}",
                    str(exc),
                    "Retry local inspection or prepare the image explicitly; doctor never pulls images.",
                    component_id=component_id,
                )
            )
            continue
        present = inspected.returncode == 0
        findings.append(
            _finding(
                "UW-DIST-IMAGE-PRESENCE",
                "info",
                f"optional local image {reference}",
                inspected.stdout.strip() if present else "not present locally",
                "No action required." if present else "Pull or build the image explicitly before using this feature; doctor never pulls images.",
                component_id=component_id,
            )
        )
    return findings


def distribution_doctor(
    *,
    project: Path | None = None,
    factory: Path | None = None,
    check_docker: bool = False,
) -> dict[str, Any]:
    contract = distribution_contract()
    pending_components = sorted(
        component_id for component_id, selected in contract["components"].items()
        if selected["release_status"] == "pending"
    )
    unavailable_components = sorted(
        component_id for component_id, selected in contract["components"].items()
        if selected["release_status"] == "unavailable"
    )
    findings = [
        _finding(
            "UW-DIST-COMPONENT-CONTRACT",
            "info",
            1,
            contract["schema_version"],
            "No action required.",
        )
    ]
    for component_id in pending_components:
        selected = contract["components"][component_id]
        code = "UW-DIST-COMPANION-RELEASE-PENDING" if selected["kind"] == "companion" else "UW-DIST-RELEASE-PENDING"
        findings.append(_finding(
            code,
            "warning",
            f"published immutable release {selected['release']}",
            "pending",
            f"Use an explicitly selected local {component_id} candidate for development; do not publish the coordinated release until this component is available.",
            component_id=component_id,
        ))
    for component_id in unavailable_components:
        selected = contract["components"][component_id]
        code = "UW-DIST-COMPANION-RELEASE-UNAVAILABLE" if selected["kind"] == "companion" else "UW-DIST-RELEASE-UNAVAILABLE"
        findings.append(_finding(
            code,
            "warning",
            f"published immutable release {selected['release']}",
            "unavailable",
            f"Restore availability of the selected {component_id} release before publishing the modular release.",
            component_id=component_id,
        ))
    selected_components = ["wheel"]
    images: dict[str, str] = {}
    if factory is None:
        findings.append(
            _finding(
                "UW-DIST-WHEEL-MODE",
                "info",
                "factory checkout optional for package-only commands",
                "limited wheel mode",
                "Set UNALTRAWEB_FACTORY_DIR only for factory-backed MCP, build, computation, capture, PDF, or bibliometrics commands.",
            )
        )
        factory_state = {"available": False, "path": "", "mode": "wheel"}
    else:
        factory = factory.expanduser().resolve()
        factory_state = {"available": (factory / "mcp-factory.yml").is_file(), "path": str(factory), "mode": "factory"}
        if factory_state["available"]:
            findings.extend(_factory_findings(factory))
            if project is None:
                selected_components = list(contract["components"])
                images = {
                    component_id: str(value["reference"])
                    for component_id, value in contract["components"].items()
                    if value["kind"] == "container"
                }
        else:
            findings.append(_finding("UW-DIST-FACTORY", "error", "mcp-factory.yml", str(factory), "Set UNALTRAWEB_FACTORY_DIR to a valid factory checkout."))

    project_state: dict[str, Any] = {"supplied": False, "path": ""}
    if project is not None:
        project = project.expanduser().resolve()
        project_findings, project_state, project_images, project_components = _project_findings(project)
        findings.extend(project_findings)
        images = project_images
        selected_components = project_components

    if check_docker:
        findings.extend(_docker_findings(images))
    else:
        findings.append(_finding("UW-DIST-DOCKER-CHECK", "info", "optional local image inspection", "not requested", "Pass --docker to inspect selected local images without pulling."))

    severities = {severity: sum(1 for item in findings if item["severity"] == severity) for severity in ["error", "warning", "info"]}
    return {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "ok": severities["error"] == 0,
        "release_ready": not pending_components and not unavailable_components and severities["error"] == 0,
        "pending_releases": pending_components,
        "unavailable_releases": unavailable_components,
        "offline": True,
        "mode": factory_state["mode"],
        "limited": factory_state["mode"] == "wheel",
        "release": contract["release"],
        "receipt_contract": contract["receipt_contract"],
        "wheel_contract": contract["wheel_contract"],
        "components": contract["components"],
        "selected_components": selected_components,
        "factory": factory_state,
        "project": project_state,
        "docker": {"checked": check_docker, "images": images},
        "summary": severities,
        "findings": findings,
    }
