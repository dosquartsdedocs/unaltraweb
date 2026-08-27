#!/usr/bin/env python3
"""Render versioned executable chapter sources to Markdown and figures."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional for status/check on lean hosts
    yaml = None


CONFIG_PATH = Path(".unaltraweb/computations.yml")
LOCK_PATH = Path(".unaltraweb/computations.lock.json")
SUPPORTED_SUFFIXES = {".qmd", ".rmd", ".r", ".py", ".ipynb"}
GENERATED_MEDIA_SUFFIXES = {".gif", ".jpeg", ".jpg", ".pdf", ".png", ".svg", ".webp"}
DEFAULT_IMAGES = {
    "python": "ghcr.io/dosquartsdedocs/unaltraweb-compute-python:0.3.0",
    "r": "ghcr.io/dosquartsdedocs/unaltraweb-compute-r:0.3.0",
}
ENGINE_ENV = {"python": "COMPUTE_PYTHON_IMAGE", "r": "COMPUTE_R_IMAGE"}
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"']([^\"']*)[\"'])?\)(\{[^}\n]*\})?"
)
QUARTO_FIGURE_RE = re.compile(r'<div\s+id="fig-[^"]+"[^>]*>\s*<img\s+(.*?)\s*/>\s*(.*?)\s*</div>', re.DOTALL | re.IGNORECASE)


class ComputationError(RuntimeError):
    pass


def strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value.strip()


def parse_scalar(value: str) -> Any:
    value = strip_inline_comment(value)
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def simple_yaml_load(text: str) -> Any:
    lines = [(len(raw) - len(raw.lstrip(" ")), raw.strip()) for raw in text.splitlines() if raw.strip() and not raw.lstrip().startswith("#")]

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        if lines[index][0] < indent:
            return {}, index
        if lines[index][1].startswith("- "):
            items: list[Any] = []
            while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
                item = lines[index][1][2:].strip()
                if item:
                    items.append(parse_scalar(item))
                    index += 1
                else:
                    child, index = parse_block(index + 1, indent + 2)
                    items.append(child)
            return items, index
        data: dict[str, Any] = {}
        while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
            line = lines[index][1]
            if ":" not in line:
                index += 1
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                data[key] = parse_scalar(value)
                index += 1
            else:
                child_indent = lines[index + 1][0] if index + 1 < len(lines) else indent + 2
                child, index = parse_block(index + 1, child_indent)
                data[key] = child
        return data, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed


def simple_yaml_dump(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(simple_yaml_dump(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {format_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(simple_yaml_dump(item, indent + 2))
            else:
                lines.append(f"{prefix}- {format_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{format_scalar(value)}"


def format_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    text = str(value)
    if not text or re.search(r"[:#\[\]{},]|^[-?]|\s$|^\s", text):
        return json.dumps(text, ensure_ascii=False)
    return text


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def safe_relative(project: Path, raw: str, *, label: str, must_exist: bool = False) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise ComputationError(f"No {label} path is configured.")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ComputationError(f"{label} must be a project-relative path: {raw}")
    resolved = (project / relative).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ComputationError(f"{label} escapes the project: {raw}") from exc
    if must_exist and not resolved.exists():
        raise ComputationError(f"Missing {label}: {relative}")
    return resolved


def relative(project: Path, path: Path) -> str:
    return str(path.resolve().relative_to(project)).replace(os.sep, "/")


def contains(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def paths_overlap(left: Path, right: Path) -> bool:
    return contains(left, right) or contains(right, left)


def read_yaml_mapping(text: str, *, label: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ComputationError(f"Invalid YAML in {label}: {exc}") from exc
    else:
        parsed = simple_yaml_load(text)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ComputationError(f"{label} must contain a YAML mapping.")
    return parsed


def comment_content(line: str, prefix: str) -> str:
    value = line[len(prefix):]
    return value[1:] if value.startswith(" ") else value


def front_matter_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".qmd", ".rmd"}:
        text = path.read_text(encoding="utf-8")
        match = FRONT_MATTER_RE.match(text)
        return match.group(1) if match else ""
    if suffix == ".r":
        lines = path.read_text(encoding="utf-8").splitlines()
        yaml_lines: list[str] = []
        active = False
        for line in lines:
            if not line.startswith("#'"):
                if active:
                    break
                continue
            value = comment_content(line, "#'")
            if value == "---":
                if active:
                    return "\n".join(yaml_lines)
                active = True
                continue
            if active:
                yaml_lines.append(value)
        return ""
    if suffix == ".py":
        lines = path.read_text(encoding="utf-8").splitlines()
        yaml_lines = []
        active = False
        for line in lines:
            if line.strip() == "# ---":
                if active:
                    return "\n".join(yaml_lines)
                active = True
                continue
            if active:
                if not line.startswith("#"):
                    break
                yaml_lines.append(comment_content(line, "#"))
        return ""
    if suffix == ".ipynb":
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ComputationError(f"Invalid notebook JSON in {path}: {exc}") from exc
        metadata = notebook.get("metadata") if isinstance(notebook, dict) else {}
        if isinstance(metadata, dict) and isinstance(metadata.get("unaltraweb_front_matter"), dict):
            return yaml.safe_dump(metadata["unaltraweb_front_matter"], sort_keys=False) if yaml is not None else simple_yaml_dump(metadata["unaltraweb_front_matter"])
        for cell in notebook.get("cells", []) if isinstance(notebook, dict) else []:
            if not isinstance(cell, dict) or cell.get("cell_type") not in {"raw", "markdown"}:
                continue
            source = cell.get("source", "")
            text = "".join(source) if isinstance(source, list) else str(source)
            match = FRONT_MATTER_RE.match(text)
            if match:
                return match.group(1)
            break
        return ""
    return ""


def read_front_matter(path: Path) -> dict[str, Any]:
    text = front_matter_text(path)
    return read_yaml_mapping(text, label=str(path)) if text else {}


def validate_keys(mapping: dict[str, Any], allowed: set[str], *, label: str) -> None:
    unknown = sorted(str(key) for key in mapping if key not in allowed)
    if unknown:
        raise ComputationError(f"Unknown {label} keys: {', '.join(unknown)}")


def load_config(project: Path) -> tuple[dict[str, Any], Path]:
    path = project / CONFIG_PATH
    if not path.is_file():
        return {
            "version": 1,
            "project_name": project.name,
            "enabled": True,
            "source_roots": ["_chapters"],
            "generated_assets_root": "assets/img/generated",
            "engines": {},
        }, path
    config = read_yaml_mapping(path.read_text(encoding="utf-8"), label=str(CONFIG_PATH))
    validate_keys(
        config,
        {"version", "enabled", "source_roots", "generated_assets_root", "engines"},
        label="computation configuration",
    )
    if config.get("version", 1) != 1:
        raise ComputationError("Unsupported computations.yml version; expected version: 1.")
    roots = config.get("source_roots", ["_chapters"])
    if not isinstance(roots, list) or not roots:
        raise ComputationError("source_roots must be a non-empty list.")
    engines = config.get("engines", {})
    if not isinstance(engines, dict):
        raise ComputationError("engines must be a mapping.")
    for engine, settings in engines.items():
        if engine not in {"r", "python"} or not isinstance(settings, dict):
            raise ComputationError(f"Unsupported computation engine configuration: {engine}")
        validate_keys(
            settings,
            {
                "image",
                "local_image",
                "base_image",
                "environments",
                "dockerfile",
                "context",
                "lockfiles",
                "fingerprint_paths",
                "rstudio",
            },
            label=f"{engine} engine",
        )
    return {
        "version": 1,
        "project_name": project.name,
        "enabled": bool(config.get("enabled", True)),
        "source_roots": [str(item) for item in roots],
        "generated_assets_root": str(config.get("generated_assets_root") or "assets/img/generated"),
        "engines": engines,
    }, path


def compute_environment() -> str:
    explicit = os.environ.get("COMPUTE_ENV", "").strip()
    if explicit:
        return explicit
    return "ci" if os.environ.get("CI", "").lower() in {"1", "true", "yes"} else "local"


def engine_settings(config: dict[str, Any], engine: str) -> dict[str, Any]:
    settings = config.get("engines", {}).get(engine, {})
    return settings if isinstance(settings, dict) else {}


def default_local_image(config: dict[str, Any], engine: str) -> str:
    name = re.sub(r"[^a-z0-9._-]+", "-", str(config["project_name"]).lower()).strip("-._") or "project"
    return f"{name}-compute-{engine}:local"


def resolve_image(config: dict[str, Any], engine: str) -> dict[str, str]:
    if engine not in ENGINE_ENV:
        raise ComputationError(f"Unsupported computation engine: {engine}")
    settings = engine_settings(config, engine)
    env_name = ENGINE_ENV[engine]
    explicit = os.environ.get(env_name, "").strip()
    environment = compute_environment()
    environments = settings.get("environments") if isinstance(settings.get("environments"), dict) else {}
    if explicit:
        image, source = explicit, f"environment:{env_name}"
    elif str(environments.get(environment) or "").strip():
        image, source = str(environments[environment]).strip(), f"config:environments.{environment}"
    elif environment == "local" and settings.get("dockerfile"):
        image = str(settings.get("local_image") or default_local_image(config, engine)).strip()
        source = "config:local_image"
    elif str(settings.get("image") or "").strip():
        image, source = str(settings["image"]).strip(), "config:image"
    else:
        image, source = DEFAULT_IMAGES[engine], "unaltraweb:default"
    if not image:
        raise ComputationError(f"Resolved an empty image for engine {engine}.")
    return {"engine": engine, "environment": environment, "image": image, "source": source}


def source_engine(path: Path, front: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    metadata = front.get("unaltraweb_compute", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ComputationError(f"unaltraweb_compute must be a mapping in {path}")
    validate_keys(metadata, {"engine", "inputs", "output", "outputs", "figures", "mode", "enabled"}, label=f"unaltraweb_compute in {path}")
    declared = str(metadata.get("engine") or "").strip().lower()
    suffix = path.suffix.lower()
    inferred = "r" if suffix in {".r", ".rmd"} else "python" if suffix in {".py", ".ipynb"} else ""
    if suffix == ".qmd" and declared not in {"r", "python"}:
        raise ComputationError(f"Quarto source must declare unaltraweb_compute.engine as r or python: {path}")
    engine = declared or inferred
    if engine not in {"r", "python"}:
        raise ComputationError(f"Cannot determine computation engine for {path}")
    if inferred and declared and inferred != declared:
        raise ComputationError(f"Declared engine {declared} conflicts with {path.suffix} source: {path}")
    return engine, metadata


def source_roots(project: Path, config: dict[str, Any]) -> list[Path]:
    roots = [safe_relative(project, item, label="computation source root") for item in config["source_roots"]]
    if any(root == project for root in roots):
        raise ComputationError("A computation source root cannot be the project root.")
    for index, root in enumerate(roots):
        if any(paths_overlap(root, other) for other in roots[index + 1:]):
            raise ComputationError("Computation source roots must not overlap.")
    return roots


def discover_sources(project: Path, config: dict[str, Any], engine_filter: str = "") -> list[dict[str, Any]]:
    if not config["enabled"]:
        return []
    records: list[dict[str, Any]] = []
    roots = source_roots(project, config)
    assets_root = safe_relative(project, config["generated_assets_root"], label="generated assets root")
    if any(paths_overlap(root, assets_root) for root in roots):
        raise ComputationError("generated_assets_root must not overlap a computation source root.")
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES):
            front = read_front_matter(path)
            engine, metadata = source_engine(path, front)
            if engine_filter and engine != engine_filter:
                continue
            if metadata.get("enabled") is False:
                continue
            mode = str(metadata.get("mode") or "chapter").strip().lower()
            if mode not in {"chapter", "figure"}:
                raise ComputationError(f"Unsupported unaltraweb_compute.mode in {relative(project, path)}: {mode}")
            if not front.get("title") or not front.get("lang") or not front.get("ref"):
                raise ComputationError(f"Executable source requires title, lang, and ref front matter: {relative(project, path)}")
            source_path = relative(project, path)
            inputs_raw = metadata.get("inputs", [])
            if not isinstance(inputs_raw, list):
                raise ComputationError(f"unaltraweb_compute.inputs must be a list in {source_path}")
            inputs = [safe_relative(project, str(item), label="computation input", must_exist=True) for item in inputs_raw]
            if mode == "figure":
                outputs_raw = metadata.get("outputs")
                if outputs_raw is None and metadata.get("output"):
                    outputs_raw = [metadata["output"]]
                if not isinstance(outputs_raw, list) or not outputs_raw:
                    raise ComputationError(f"Figure computation requires unaltraweb_compute.outputs in {source_path}")
                outputs = [safe_relative(project, str(item), label="generated figure output") for item in outputs_raw]
                for output in outputs:
                    if output.suffix.lower() not in GENERATED_MEDIA_SUFFIXES:
                        raise ComputationError(f"Figure computation output must use a supported media suffix: {relative(project, output)}")
                    if any(contains(source_root, output) for source_root in roots):
                        raise ComputationError(f"Figure computation output must not be inside a configured source root: {relative(project, output)}")
                if len({relative(project, output) for output in outputs}) != len(outputs):
                    raise ComputationError(f"Figure computation outputs must be unique in {source_path}")
                for existing in records:
                    if existing.get("mode") == "figure":
                        if any(output == existing_output for output in outputs for existing_output in existing["outputs"]):
                            raise ComputationError(f"Executable sources collide on generated figure outputs: {existing['source_path']} and {source_path}")
                    elif any(output == existing["output"] or paths_overlap(output, existing["figures"]) for output in outputs):
                        raise ComputationError(f"Generated output paths overlap for {existing['source_path']} and {source_path}")
                records.append(
                    {
                        "mode": mode,
                        "source": path,
                        "source_path": source_path,
                        "outputs": outputs,
                        "output_paths": [relative(project, output) for output in outputs],
                        "engine": engine,
                        "front": front,
                        "inputs": inputs,
                        "input_paths": [relative(project, item) for item in inputs],
                    }
                )
                continue
            output_raw = str(metadata.get("output") or relative(project, path.with_suffix(".md")))
            output = safe_relative(project, output_raw, label="generated Markdown output")
            if output.suffix.lower() != ".md":
                raise ComputationError(f"Generated chapter output must use .md: {output_raw}")
            if not any(contains(root, output) for root in roots):
                raise ComputationError(f"Generated chapter output must remain under a configured source root: {output_raw}")
            output_path = relative(project, output)
            figures_raw = str(metadata.get("figures") or Path(relative(project, assets_root)) / str(front["lang"]) / str(front["ref"]))
            figures = safe_relative(project, figures_raw, label="generated figures directory")
            if figures == assets_root or not contains(assets_root, figures):
                raise ComputationError(f"Generated figures must use a subdirectory of {relative(project, assets_root)}: {figures_raw}")
            for existing in records:
                if existing.get("mode") == "figure":
                    if any(existing_output == output or paths_overlap(existing_output, figures) for existing_output in existing["outputs"]):
                        raise ComputationError(f"Generated output paths overlap for {existing['source_path']} and {source_path}")
                    continue
                if output == existing["output"]:
                    raise ComputationError(f"Executable sources collide on {output_path}: {existing['source_path']} and {source_path}")
                if paths_overlap(figures, existing["figures"]):
                    raise ComputationError(f"Executable sources overlap on generated figures: {existing['source_path']} and {source_path}")
                if paths_overlap(output, existing["figures"]) or paths_overlap(figures, existing["output"]):
                    raise ComputationError(f"Generated output paths overlap for {existing['source_path']} and {source_path}")
            records.append(
                {
                    "mode": mode,
                    "source": path,
                    "source_path": source_path,
                    "output": output,
                    "output_path": output_path,
                    "figures": figures,
                    "figures_path": relative(project, figures),
                    "engine": engine,
                    "front": front,
                    "inputs": inputs,
                    "input_paths": [relative(project, item) for item in inputs],
                }
            )
    return records


def path_entries(project: Path, path: Path) -> list[dict[str, Any]]:
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ComputationError(f"Fingerprint path has no files: {relative(project, path)}")
    return [{"path": relative(project, item), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()} for item in files]


def engine_dependencies(project: Path, config: dict[str, Any], engine: str) -> list[Path]:
    settings = engine_settings(config, engine)
    raw_paths: list[str] = []
    for key in ["dockerfile"]:
        if settings.get(key):
            raw_paths.append(str(settings[key]))
    for key in ["lockfiles", "fingerprint_paths"]:
        values = settings.get(key, [])
        if values and not isinstance(values, list):
            raise ComputationError(f"{engine}.{key} must be a list.")
        raw_paths.extend(str(item) for item in values or [])
    return [safe_relative(project, item, label=f"{engine} environment dependency", must_exist=True) for item in raw_paths]


def fingerprint(
    project: Path,
    config: dict[str, Any],
    config_path: Path,
    record: dict[str, Any],
    saved: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    image = resolve_image(config, record["engine"])
    environment_identity = os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_DIGEST", "").strip() or os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_ID", "").strip()
    local_identity = inspect_image(image["image"])
    saved_image = saved.get("image") if isinstance(saved, dict) and isinstance(saved.get("image"), dict) else {}
    saved_identity = saved.get("image_identity") if isinstance(saved, dict) and isinstance(saved.get("image_identity"), dict) else {}
    recorded_identity = ""
    if saved_image.get("image") == image["image"]:
        recorded_identity = str(saved_identity.get("digest") or saved_identity.get("id") or "")
    image_identity = environment_identity or local_identity.get("digest") or local_identity.get("id") or recorded_identity
    dependencies = [record["source"], *record["inputs"], *engine_dependencies(project, config, record["engine"])]
    if config_path.is_file():
        dependencies.append(config_path)
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in dependencies:
        for entry in path_entries(project, path):
            if entry["path"] not in seen:
                entries.append(entry)
                seen.add(entry["path"])
    payload = {
        "schema": 1,
        "engine": record["engine"],
        "image": image["image"],
        "image_identity": image_identity,
        "dependencies": entries,
    }
    if record.get("mode") == "figure":
        payload["outputs"] = record["output_paths"]
    else:
        payload["output"] = record["output_path"]
        payload["figures"] = record["figures_path"]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return digest, entries, image


def file_signature(path: Path) -> dict[str, Any]:
    return {"size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def tree_signatures(project: Path, root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    return [
        {"path": relative(project, path), **file_signature(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def signatures_match(project: Path, entries: list[dict[str, Any]]) -> bool:
    for entry in entries:
        try:
            path = safe_relative(project, str(entry["path"]), label="recorded artifact", must_exist=True)
        except ComputationError:
            return False
        if file_signature(path) != {"size": entry.get("size"), "sha256": entry.get("sha256")}:
            return False
    return True


def no_unexpected_assets(project: Path, root: Path, entries: list[dict[str, Any]]) -> bool:
    expected = {str(entry.get("path") or "") for entry in entries}
    actual = {relative(project, path) for path in root.rglob("*") if path.is_file()} if root.is_dir() else set()
    return actual == expected


def load_lock(project: Path) -> dict[str, Any]:
    path = project / LOCK_PATH
    if not path.is_file():
        return {"version": 1, "records": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ComputationError(f"Invalid computation lock file: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("records"), dict):
        raise ComputationError("Invalid computations.lock.json structure.")
    return data


def write_lock(project: Path, lock: dict[str, Any]) -> None:
    path = project / LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lock["version"] = 1
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json_dump(lock))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect_image(image: str) -> dict[str, str]:
    if not shutil.which("docker"):
        return {"available": "false", "id": "", "digest": ""}
    command = ["docker", "image", "inspect", image, "--format", "{{.Id}}|{{join .RepoDigests \",\"}}"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if completed.returncode != 0:
        return {"available": "false", "id": "", "digest": ""}
    image_id, _, digest = completed.stdout.strip().partition("|")
    return {"available": "true", "id": image_id, "digest": digest}


def status_item(project: Path, config: dict[str, Any], config_path: Path, record: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    current_fingerprint, dependencies, image = fingerprint(project, config, config_path, record, saved)
    if record.get("mode") == "figure":
        saved_outputs = saved.get("outputs") if isinstance(saved.get("outputs"), list) else []
        outputs_exist = all(output.is_file() for output in record["outputs"])
        outputs_valid = bool(outputs_exist and saved_outputs and signatures_match(project, saved_outputs))
        current = bool(outputs_exist and not saved) or bool(saved and saved.get("fingerprint") == current_fingerprint and outputs_valid)
        reason = "current"
        if not saved and outputs_exist:
            reason = "present_unmanaged"
        elif not saved:
            reason = "not_rendered"
        elif saved.get("fingerprint") != current_fingerprint:
            reason = "source_or_environment_changed"
        elif not outputs_exist:
            reason = "output_missing"
        elif not outputs_valid:
            reason = "output_modified"
        return {
            "source": record["source_path"],
            "mode": "figure",
            "outputs": record["output_paths"],
            "engine": record["engine"],
            "image": image,
            "local_image": inspect_image(image["image"]),
            "fingerprint": current_fingerprint,
            "dependencies": dependencies,
            "current": current,
            "reason": reason,
        }
    output_exists = record["output"].is_file()
    output_valid = bool(output_exists and saved.get("output") and signatures_match(project, [saved["output"]]))
    saved_assets = saved.get("assets", [])
    assets_valid = signatures_match(project, saved_assets) and no_unexpected_assets(project, record["figures"], saved_assets)
    current = bool(output_exists and not saved) or bool(saved and saved.get("fingerprint") == current_fingerprint and output_valid and assets_valid)
    reason = "current"
    if not saved and output_exists:
        reason = "present_unmanaged"
    elif not saved:
        reason = "not_rendered"
    elif saved.get("fingerprint") != current_fingerprint:
        reason = "source_or_environment_changed"
    elif not output_exists:
        reason = "output_missing"
    elif not output_valid:
        reason = "output_modified"
    elif not assets_valid:
        reason = "assets_missing_or_modified"
    return {
        "source": record["source_path"],
        "mode": "chapter",
        "output": record["output_path"],
        "figures": record["figures_path"],
        "engine": record["engine"],
        "image": image,
        "local_image": inspect_image(image["image"]),
        "fingerprint": current_fingerprint,
        "dependencies": dependencies,
        "current": current,
        "reason": reason,
    }


def status(project: Path, source: str = "", engine: str = "", mode: str = "") -> dict[str, Any]:
    config, config_path = load_config(project)
    all_records = discover_sources(project, config)
    records = [
        item for item in all_records
        if (not engine or item["engine"] == engine) and (not mode or item["mode"] == mode)
    ]
    if source:
        selected = safe_relative(project, source, label="selected computation source", must_exist=True)
        records = [item for item in records if item["source"] == selected]
        if not records:
            raise ComputationError(f"Selected file is not an enabled computation source: {source}")
    lock = load_lock(project)
    lock_records = lock["records"]
    items = [status_item(project, config, config_path, record, lock_records.get(record["source_path"], {})) for record in records]
    known = {item["source_path"] for item in all_records}
    orphaned = sorted(path for path in lock_records if path not in known)
    return {
        "project": str(project),
        "enabled": config["enabled"],
        "config": str(CONFIG_PATH) if config_path.is_file() else "",
        "lock": str(LOCK_PATH) if (project / LOCK_PATH).is_file() else "",
        "sources": items,
        "source_count": len(items),
        "current_count": sum(1 for item in items if item["current"]),
        "orphaned_records": orphaned,
        "ok": all(item["current"] for item in items) and not orphaned,
    }


def run_command(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise ComputationError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def locate_rendered_markdown(stage: Path, source: Path) -> Path:
    candidates = sorted(stage.rglob("*.md"))
    preferred = [path for path in candidates if path.stem == source.stem]
    if len(preferred) == 1:
        return preferred[0]
    if len(candidates) == 1:
        return candidates[0]
    names = ", ".join(str(path.relative_to(stage)) for path in candidates)
    raise ComputationError(f"Expected one rendered Markdown output for {source.name}; found: {names or 'none'}")


def split_generated_markdown(text: str) -> str:
    match = FRONT_MATTER_RE.match(text)
    return text[match.end():] if match else text


def normalize_generated_body(text: str, title: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].strip() == f"# {title}":
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    elif len(lines) >= 2 and lines[0].strip() == title and re.fullmatch(r"=+", lines[1].strip()):
        lines = lines[2:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def yaml_front(front: dict[str, Any]) -> str:
    public = {key: value for key, value in front.items() if key != "unaltraweb_compute"}
    dumped = yaml.safe_dump(public, allow_unicode=True, sort_keys=False).rstrip() if yaml is not None else simple_yaml_dump(public).rstrip()
    return "---\n" + dumped + "\n---\n"


def generated_media(stage: Path, markdown: Path, text: str, figures_path: str) -> tuple[str, list[tuple[Path, Path]]]:
    copies: dict[str, tuple[Path, Path]] = {}

    def quarto_figure(match: re.Match[str]) -> str:
        attributes, raw_caption = match.groups()

        def attribute(name: str) -> str:
            found = re.search(rf'\b{re.escape(name)}="([^"]*)"', attributes, re.IGNORECASE)
            return html.unescape(found.group(1)) if found else ""

        raw_path = attribute("src")
        alt = attribute("data-fig-alt") or attribute("alt")
        caption = html.unescape(re.sub(r"<[^>]+>", "", raw_caption)).replace("\u00a0", " ").strip()
        caption = re.sub(r"^Figure\s+\d+\s*:\s*", "", caption, flags=re.IGNORECASE)
        escaped = caption.replace('"', "&quot;")
        return f'![{alt or caption}]({raw_path} "{escaped}")'

    text = QUARTO_FIGURE_RE.sub(quarto_figure, text)

    def image(match: re.Match[str]) -> str:
        alt, raw_path, title, attributes = match.groups()
        if re.match(r"^[a-z][a-z0-9+.-]*://", raw_path, re.IGNORECASE) or raw_path.startswith("{{"):
            return match.group(0)
        if raw_path.startswith("/output/"):
            candidate = stage / raw_path.removeprefix("/output/")
        else:
            candidate = (markdown.parent / raw_path).resolve()
        try:
            candidate.relative_to(stage)
        except ValueError:
            return match.group(0)
        if not candidate.is_file():
            return match.group(0)
        if candidate.suffix.lower() not in GENERATED_MEDIA_SUFFIXES:
            raise ComputationError(f"Unsupported generated media type: {candidate.name}")
        relative_media = candidate.relative_to(markdown.parent)
        if ".." in relative_media.parts:
            relative_media = Path(candidate.name)
        target_relative = Path(figures_path) / relative_media
        copies[str(target_relative)] = (candidate, target_relative)
        caption = (title or alt).strip()
        if not caption:
            raise ComputationError(f"Generated figure requires fig-cap or fig-alt: {raw_path}")
        escaped = caption.replace('"', "&quot;")
        return f'![{alt or caption}]({{{{ site.baseurl }}}}/{str(target_relative).replace(os.sep, "/")} "{escaped}"){attributes or ""}'

    rendered = IMAGE_RE.sub(image, text)
    return rendered, list(copies.values())


def render_stage(project: Path, config: dict[str, Any], record: dict[str, Any], stage: Path, image: str) -> tuple[str, list[tuple[Path, Path]], dict[str, str]]:
    command = [
        "quarto",
        "render",
        record["source_path"],
        "--to",
        "gfm+yaml_metadata_block",
        "--output-dir",
        str(stage),
        "--execute",
        "--no-cache",
        "--no-clean",
    ]
    run_command(command)
    image_identity = {
        "available": "true",
        "id": os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_ID", ""),
        "digest": os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_DIGEST", ""),
    }
    markdown = locate_rendered_markdown(stage, record["source"])
    body = normalize_generated_body(
        split_generated_markdown(markdown.read_text(encoding="utf-8")),
        str(record["front"]["title"]),
    )
    body, media = generated_media(stage, markdown, body, record["figures_path"])
    marker = f'<!-- Generated from {record["source_path"]} by unaltraweb computations. Do not edit this file directly. -->'
    output_text = yaml_front(record["front"]) + "\n" + marker + "\n\n" + body + "\n"
    return output_text, media, image_identity


def staged_figure_output(stage: Path, output_path: str) -> Path | None:
    direct = stage / output_path
    if direct.is_file():
        return direct
    matches = sorted(path for path in stage.rglob(Path(output_path).name) if path.is_file())
    return matches[0] if len(matches) == 1 else None


def publish_figure_outputs(record: dict[str, Any], stage: Path, confirm_overwrite: bool, owned: bool) -> None:
    staged: list[tuple[Path, Path]] = []
    missing: list[Path] = []
    for output, output_path in zip(record["outputs"], record["output_paths"]):
        candidate = staged_figure_output(stage, output_path)
        if candidate:
            staged.append((candidate, output))
        elif not output.is_file():
            missing.append(output)
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise ComputationError(f"Figure computation did not create declared output(s): {names}")
    if not staged:
        return
    unmanaged = [output for _, output in staged if output.exists()]
    if unmanaged and not owned and not confirm_overwrite:
        names = ", ".join(str(path) for path in unmanaged)
        raise ComputationError(
            f"Refusing to replace unmanaged generated figure output(s) for {record['source_path']}: {names}; rerun with --confirm-overwrite after review."
        )
    token = secrets.token_hex(6)
    replacements: list[tuple[Path, Path, Path | None]] = []
    try:
        for source, output in staged:
            output.parent.mkdir(parents=True, exist_ok=True)
            temp_output = output.with_name(f".{output.name}.{token}.compute-tmp")
            backup_output = output.with_name(f".{output.name}.{token}.compute-backup")
            if temp_output.exists():
                temp_output.unlink()
            if backup_output.exists():
                backup_output.unlink()
            shutil.copy2(source, temp_output)
            if output.exists():
                os.replace(output, backup_output)
                replacements.append((temp_output, output, backup_output))
            else:
                replacements.append((temp_output, output, None))
            os.replace(temp_output, output)
    except Exception:
        for temp_output, output, backup_output in replacements:
            if output.exists():
                output.unlink()
            if backup_output and backup_output.exists():
                os.replace(backup_output, output)
            if temp_output.exists():
                temp_output.unlink()
        raise
    finally:
        for _, _, backup_output in replacements:
            if backup_output and backup_output.exists():
                backup_output.unlink()


def render_figure_outputs(record: dict[str, Any], stage: Path, confirm_overwrite: bool, owned: bool) -> dict[str, str]:
    command = [
        "quarto",
        "render",
        record["source_path"],
        "--to",
        "gfm+yaml_metadata_block",
        "--output-dir",
        str(stage),
        "--execute",
        "--no-cache",
        "--no-clean",
    ]
    run_command(command)
    publish_figure_outputs(record, stage, confirm_overwrite, owned)
    return {
        "available": "true",
        "id": os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_ID", ""),
        "digest": os.environ.get("UNALTRAWEB_COMPUTE_IMAGE_DIGEST", ""),
    }


def saved_paths_match(record: dict[str, Any], saved: dict[str, Any]) -> bool:
    output = saved.get("output") if isinstance(saved.get("output"), dict) else {}
    return output.get("path") == record["output_path"] and saved.get("figures") == record["figures_path"]


def saved_figure_outputs_match(record: dict[str, Any], saved: dict[str, Any]) -> bool:
    outputs = saved.get("outputs") if isinstance(saved.get("outputs"), list) else []
    return [str(item.get("path") or "") for item in outputs] == record["output_paths"]


def validate_path_migration(
    project: Path,
    config: dict[str, Any],
    record: dict[str, Any],
    saved: dict[str, Any],
    confirm_overwrite: bool,
    other_records: list[dict[str, Any]],
) -> tuple[Path | None, Path | None]:
    if not saved or saved_paths_match(record, saved):
        return None, None
    if not confirm_overwrite:
        raise ComputationError(f"Changing managed output paths for {record['source_path']} requires --confirm-overwrite after review.")
    saved_output_data = saved.get("output") if isinstance(saved.get("output"), dict) else {}
    saved_output_raw = str(saved_output_data.get("path") or "")
    saved_figures_raw = str(saved.get("figures") or "")
    old_output = safe_relative(project, saved_output_raw, label="previous generated Markdown output") if saved_output_raw else None
    old_figures = safe_relative(project, saved_figures_raw, label="previous generated figures directory") if saved_figures_raw else None
    roots = source_roots(project, config)
    assets_root = safe_relative(project, config["generated_assets_root"], label="generated assets root")
    if old_output and (old_output.suffix.lower() != ".md" or not any(contains(root, old_output) for root in roots)):
        raise ComputationError(f"Recorded previous Markdown path is outside managed source roots: {saved_output_raw}")
    if old_figures and (old_figures == assets_root or not contains(assets_root, old_figures)):
        raise ComputationError(f"Recorded previous figures path is outside the managed assets root: {saved_figures_raw}")
    protected: list[Path] = []
    for item in other_records:
        if item.get("mode") == "figure":
            protected.extend(item["outputs"])
        else:
            protected.extend([item["output"], item["figures"]])
    if any(old_path and any(paths_overlap(old_path, path) for path in protected) for old_path in [old_output, old_figures]):
        raise ComputationError(f"Recorded previous paths overlap another source's current output: {record['source_path']}")
    for old_path in [old_output, old_figures]:
        if old_path and any(paths_overlap(old_path, current) and old_path != current for current in [record["output"], record["figures"]]):
            raise ComputationError(f"Previous and new generated paths overlap for {record['source_path']}; move them manually after review.")
    if old_output and old_output.exists() and not signatures_match(project, [saved_output_data]):
        raise ComputationError(f"Previous generated Markdown was modified and will not be removed: {saved_output_raw}")
    saved_assets = saved.get("assets") if isinstance(saved.get("assets"), list) else []
    if old_figures and old_figures.exists() and (not signatures_match(project, saved_assets) or not no_unexpected_assets(project, old_figures, saved_assets)):
        raise ComputationError(f"Previous generated figures were modified and will not be removed: {saved_figures_raw}")
    return old_output, old_figures


def remove_previous_paths(record: dict[str, Any], old_output: Path | None, old_figures: Path | None) -> None:
    if old_output and old_output != record["output"]:
        old_output.unlink(missing_ok=True)
    if old_figures and old_figures != record["figures"] and old_figures.is_dir():
        shutil.rmtree(old_figures)


def record_managed_paths(record: dict[str, Any]) -> list[Path]:
    if record.get("mode") == "figure":
        return list(record["outputs"])
    return [record["output"], record["figures"]]


def orphan_paths(project: Path, saved: dict[str, Any]) -> list[Path]:
    if saved.get("mode") == "figure":
        outputs = saved.get("outputs") if isinstance(saved.get("outputs"), list) else []
        paths: list[Path] = []
        for entry in outputs:
            raw = str(entry.get("path") or "") if isinstance(entry, dict) else ""
            if raw:
                paths.append(safe_relative(project, raw, label="orphaned generated figure"))
        return paths
    paths = []
    output = saved.get("output") if isinstance(saved.get("output"), dict) else {}
    output_path = str(output.get("path") or "")
    figures_path = str(saved.get("figures") or "")
    if output_path:
        paths.append(safe_relative(project, output_path, label="orphaned generated Markdown"))
    if figures_path:
        paths.append(safe_relative(project, figures_path, label="orphaned generated figures"))
    return paths


def prune_absent_orphan_records(project: Path, lock: dict[str, Any], records: list[dict[str, Any]]) -> None:
    known = {item["source_path"] for item in records}
    managed_paths = [path for record in records for path in record_managed_paths(record)]
    for source_path in [path for path in lock["records"] if path not in known]:
        saved = lock["records"][source_path]
        try:
            saved_paths = orphan_paths(project, saved)
        except ComputationError:
            saved_paths = []
        if saved_paths and all(any(paths_overlap(saved_path, managed_path) for managed_path in managed_paths) for saved_path in saved_paths):
            del lock["records"][source_path]
            continue
        if saved.get("mode") == "figure":
            if not any(path.exists() for path in saved_paths):
                del lock["records"][source_path]
            continue
        if not any(path.exists() for path in saved_paths):
            del lock["records"][source_path]


def publish_render(project: Path, record: dict[str, Any], output_text: str, media: list[tuple[Path, Path]], confirm_overwrite: bool, owned: bool) -> None:
    output = record["output"]
    figures = record["figures"]
    if not owned and (output.exists() or figures.exists()) and not confirm_overwrite:
        raise ComputationError(
            f"Refusing to replace unmanaged generated paths for {record['source_path']}; rerun with --confirm-overwrite after review."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    figures.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(6)
    temp_output = output.with_name(f".{output.name}.{token}.compute-tmp")
    temp_figures = figures.with_name(f".{figures.name}.{token}.compute-tmp")
    backup_output = output.with_name(f".{output.name}.{token}.compute-backup")
    backup_figures = figures.with_name(f".{figures.name}.{token}.compute-backup")
    for path in [temp_output, temp_figures, backup_output, backup_figures]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    temp_output.write_text(output_text, encoding="utf-8")
    temp_figures.mkdir(parents=True)
    for source, target_relative in media:
        target = temp_figures / Path(target_relative).relative_to(Path(record["figures_path"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    try:
        if output.exists():
            os.replace(output, backup_output)
        if figures.exists():
            os.replace(figures, backup_figures)
        os.replace(temp_figures, figures)
        os.replace(temp_output, output)
    except Exception:
        if output.exists():
            output.unlink()
        if figures.exists():
            shutil.rmtree(figures)
        if backup_output.exists():
            os.replace(backup_output, output)
        if backup_figures.exists():
            os.replace(backup_figures, figures)
        raise
    finally:
        if backup_output.exists():
            backup_output.unlink()
        if backup_figures.exists():
            shutil.rmtree(backup_figures)


@contextlib.contextmanager
def project_render_lock(project: Path):
    root = project / "tmp" / "manual-computations"
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".render.lock").open("w", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _render(project: Path, source: str = "", engine: str = "", confirm_overwrite: bool = False, stale_only: bool = False, mode: str = "") -> dict[str, Any]:
    config, config_path = load_config(project)
    all_records = discover_sources(project, config)
    records = [
        item for item in all_records
        if (not engine or item["engine"] == engine) and (not mode or item["mode"] == mode)
    ]
    if source:
        selected = safe_relative(project, source, label="selected computation source", must_exist=True)
        records = [item for item in records if item["source"] == selected]
        if not records:
            raise ComputationError(f"Selected file is not an enabled computation source: {source}")
    lock = load_lock(project)
    results: list[dict[str, Any]] = []
    for record in records:
        saved = lock["records"].get(record["source_path"], {})
        if stale_only:
            if status_item(project, config, config_path, record, saved)["current"]:
                continue
            managed_paths = list(record["outputs"]) if record.get("mode") == "figure" else [record["output"], record["figures"]]
            if not saved and all(path.exists() for path in managed_paths):
                continue
        current_fingerprint, dependencies, image = fingerprint(project, config, config_path, record, saved)
        saved = lock["records"].get(record["source_path"], {})
        if record.get("mode") == "figure":
            build_root = project / "tmp" / "manual-computations"
            build_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"{record['source'].stem}-", dir=build_root) as temporary:
                image_identity = render_figure_outputs(record, Path(temporary), confirm_overwrite, bool(saved and saved_figure_outputs_match(record, saved)))
            lock["records"][record["source_path"]] = {
                "mode": "figure",
                "engine": record["engine"],
                "image": image,
                "image_identity": image_identity,
                "fingerprint": current_fingerprint,
                "dependencies": dependencies,
                "outputs": [{"path": relative(project, output), **file_signature(output)} for output in record["outputs"]],
                "rendered_at": utc_now(),
            }
            write_lock(project, lock)
            results.append({"source": record["source_path"], "mode": "figure", "outputs": record["output_paths"], "engine": record["engine"], "image": image})
            continue
        other_records = [item for item in all_records if item["source_path"] != record["source_path"]]
        old_output, old_figures = validate_path_migration(project, config, record, saved, confirm_overwrite, other_records)
        build_root = project / "tmp" / "manual-computations"
        build_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{record['source'].stem}-", dir=build_root) as temporary:
            output_text, media, image_identity = render_stage(project, config, record, Path(temporary), image["image"])
            publish_render(project, record, output_text, media, confirm_overwrite, bool(saved and saved_paths_match(record, saved)))
        remove_previous_paths(record, old_output, old_figures)
        lock["records"][record["source_path"]] = {
            "engine": record["engine"],
            "image": image,
            "image_identity": image_identity,
            "fingerprint": current_fingerprint,
            "dependencies": dependencies,
            "output": {"path": record["output_path"], **file_signature(record["output"])},
            "figures": record["figures_path"],
            "assets": tree_signatures(project, record["figures"]),
            "rendered_at": utc_now(),
        }
        write_lock(project, lock)
        results.append({"source": record["source_path"], "output": record["output_path"], "figures": record["figures_path"], "engine": record["engine"], "image": image, "assets": len(media)})
    if not source and not engine:
        prune_absent_orphan_records(project, lock, all_records)
    write_lock(project, lock)
    return {"project": str(project), "rendered": results, "rendered_count": len(results), "ok": True}


def render(project: Path, source: str = "", engine: str = "", confirm_overwrite: bool = False, stale_only: bool = False, mode: str = "") -> dict[str, Any]:
    with project_render_lock(project):
        return _render(project, source=source, engine=engine, mode=mode, confirm_overwrite=confirm_overwrite, stale_only=stale_only)


def prune(project: Path) -> dict[str, Any]:
    with project_render_lock(project):
        config, _ = load_config(project)
        records = discover_sources(project, config)
        lock = load_lock(project)
        before = set(lock["records"])
        prune_absent_orphan_records(project, lock, records)
        removed = sorted(before - set(lock["records"]))
        write_lock(project, lock)
        return {"project": str(project), "removed_records": removed, "removed_count": len(removed), "ok": True}


def build_engine_image(project: Path, config: dict[str, Any], engine: str) -> dict[str, Any]:
    settings = engine_settings(config, engine)
    selected = resolve_image(config, engine)
    dockerfile_raw = str(settings.get("dockerfile") or "").strip()
    local_image = str(settings.get("local_image") or default_local_image(config, engine)).strip()
    if not dockerfile_raw or compute_environment() != "local" or selected["image"] != local_image:
        image = selected["image"]
        if inspect_image(image)["available"] == "true":
            return {"engine": engine, "action": "reuse", "image": image, "ok": True}
        run_command(["docker", "pull", image])
        return {"engine": engine, "action": "pull", "image": image, "ok": True}
    dockerfile = safe_relative(project, dockerfile_raw, label=f"{engine} Dockerfile", must_exist=True)
    context = safe_relative(project, str(settings.get("context") or "."), label=f"{engine} Docker context", must_exist=True)
    base_image = str(settings.get("base_image") or DEFAULT_IMAGES[engine]).strip()
    command = ["docker", "build"]
    network = os.environ.get("COMPUTE_DOCKER_BUILD_NETWORK", "").strip()
    if network:
        command.extend(["--network", network])
    command.extend(
        [
            "--build-arg",
            f"BASE_IMAGE={base_image}",
            "-f",
            str(dockerfile),
            "-t",
            local_image,
            str(context),
        ]
    )
    run_command(command)
    return {"engine": engine, "action": "build", "image": local_image, "base_image": base_image, "dockerfile": relative(project, dockerfile), "context": relative(project, context), "ok": True}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="unaltraweb-computations")
    root.add_argument("command", choices=["status", "check", "render", "prune", "resolve", "image"])
    root.add_argument("--project", default=".")
    root.add_argument("--source", default="")
    root.add_argument("--engine", choices=["r", "python"], default="")
    root.add_argument("--mode", choices=["chapter", "figure"], default="")
    root.add_argument("--confirm-overwrite", action="store_true")
    root.add_argument("--stale-only", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    try:
        if args.command in {"status", "check"}:
            result = status(project, source=args.source, engine=args.engine, mode=args.mode)
        elif args.command == "render":
            result = render(project, source=args.source, engine=args.engine, mode=args.mode, confirm_overwrite=args.confirm_overwrite, stale_only=args.stale_only)
        elif args.command == "prune":
            result = prune(project)
        elif args.command == "resolve":
            if not args.engine:
                raise ComputationError("resolve requires --engine r or --engine python")
            config, _ = load_config(project)
            result = {**resolve_image(config, args.engine), "ok": True}
        else:
            if not args.engine:
                raise ComputationError("image requires --engine r or --engine python")
            config, _ = load_config(project)
            result = build_engine_image(project, config, args.engine)
        print(json_dump(result), end="")
        if args.command == "status":
            return 0
        return 0 if result.get("ok") else 1
    except ComputationError as exc:
        print(json_dump({"project": str(project), "ok": False, "error": str(exc)}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
