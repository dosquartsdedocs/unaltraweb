#!/usr/bin/env python3
"""Capture local web previews as versioned PNG and annotated SVG artefacts."""

from __future__ import annotations

import argparse
import base64
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
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as exc:  # pragma: no cover - supplied by project tooling
    raise SystemExit("PyYAML is required for unaltraweb web captures.") from exc


LOCK_PATH = Path(".unaltraweb/web-captures.lock.json")
SOURCE_SUFFIXES = (".capture.yml", ".capture.yaml")
DEFAULT_IMAGE = "ghcr.io/dosquartsdedocs/unaltraweb-web-capture:main"
DEFAULT_VIEWPORT = {"width": 1440, "height": 900, "device_scale_factor": 1}
CAPTURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
SAFE_SOURCE_RE = re.compile(r"^[A-Za-z0-9_./-]+\.capture\.ya?ml$")
SVG_METADATA_RE = re.compile(r'<metadata\s+id="unaltraweb-capture">(.*?)</metadata>', re.DOTALL)
SVG_ALLOWED_ELEMENTS = {
    "svg", "g", "defs", "metadata", "title", "desc", "image", "rect", "path", "text", "tspan",
    "marker", "polygon", "polyline", "line", "circle", "ellipse", "clippath", "mask", "lineargradient",
    "radialgradient", "stop", "pattern", "use", "namedview", "grid", "page",
}
SVG_ALLOWED_ATTRIBUTES = {
    "id", "class", "version", "baseprofile", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "viewbox", "preserveaspectratio", "d", "points", "transform", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "opacity", "fill-opacity",
    "stroke-opacity", "fill-rule", "clip-rule", "clip-path", "mask", "font-family", "font-size", "font-style", "font-weight",
    "text-anchor", "dominant-baseline", "marker-start", "marker-mid", "marker-end", "markerwidth", "markerheight", "refx", "refy",
    "orient", "offset", "stop-color", "stop-opacity", "patternunits", "patterncontentunits", "gradientunits", "gradienttransform",
    "spreadmethod", "href", "style", "data-selector", "groupmode", "label", "space", "role", "aria-label", "pagecolor",
    "bordercolor", "borderopacity", "objecttolerance", "gridtolerance", "guidetolerance", "showgrid", "showguides", "zoom",
    "current-layer", "document-units", "pagecheckerboard", "deskcolor", "units", "originx", "originy", "spacingx", "spacingy",
}
SVG_ALLOWED_STYLE_PROPERTIES = {
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray",
    "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity", "fill-rule", "clip-rule", "clip-path", "mask",
    "font-family", "font-size", "font-style", "font-weight", "text-anchor", "dominant-baseline", "marker-start", "marker-mid",
    "marker-end", "stop-color", "stop-opacity", "display", "visibility",
}


class WebCaptureError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_signature(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"sha256": sha256_bytes(data), "size": len(data)}


def path_signatures(project: Path, path: Path) -> list[dict[str, str]]:
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    return [{"path": relative(project, item), "sha256": file_signature(item)["sha256"]} for item in files]


def safe_relative(project: Path, raw: str, *, label: str, must_exist: bool = False) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise WebCaptureError(f"No {label} path is configured.")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise WebCaptureError(f"{label} must be a project-relative path: {raw}")
    resolved = (project / relative).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise WebCaptureError(f"{label} escapes the project: {raw}") from exc
    if must_exist and not resolved.exists():
        raise WebCaptureError(f"Missing {label}: {relative}")
    return resolved


def relative(project: Path, path: Path) -> str:
    return str(path.resolve().relative_to(project)).replace(os.sep, "/")


def validate_keys(mapping: dict[str, Any], allowed: set[str], *, label: str) -> None:
    unknown = sorted(str(key) for key in mapping if key not in allowed)
    if unknown:
        raise WebCaptureError(f"Unknown {label} keys: {', '.join(unknown)}")


def mapping(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise WebCaptureError(f"{label} must be a mapping.")
    return value


def bounded_int(value: Any, *, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise WebCaptureError(f"{label} must be an integer between {minimum} and {maximum}.")
    return value


def validate_selector(value: Any, *, label: str) -> str:
    selector = str(value or "").strip()
    if not selector or len(selector) > 500 or any(character in selector for character in "\r\n\0"):
        raise WebCaptureError(f"{label} must be a non-empty CSS selector of at most 500 characters.")
    return selector


def validate_path(value: Any) -> str:
    path = str(value or "").strip()
    parsed = urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc or parsed.fragment or any(ord(char) < 32 for char in path):
        raise WebCaptureError("Capture path must be a local absolute URL path without a scheme, host, fragment, or control characters.")
    return path


def normalize_viewport(raw: Any) -> dict[str, Any]:
    viewport = {**DEFAULT_VIEWPORT, **mapping(raw, label="viewport")}
    validate_keys(viewport, {"width", "height", "device_scale_factor"}, label="viewport")
    width = bounded_int(viewport["width"], label="viewport width", minimum=320, maximum=4096)
    height = bounded_int(viewport["height"], label="viewport height", minimum=240, maximum=4096)
    scale = viewport["device_scale_factor"]
    if scale not in {1, 2}:
        raise WebCaptureError("viewport device_scale_factor must be 1 or 2.")
    return {"width": width, "height": height, "device_scale_factor": scale}


def normalize_capture(raw: Any) -> dict[str, Any]:
    capture = mapping(raw, label="capture")
    validate_keys(capture, {"full_page", "selector", "clip", "padding"}, label="capture")
    result: dict[str, Any] = {"full_page": bool(capture.get("full_page", False))}
    if capture.get("selector"):
        result["selector"] = validate_selector(capture["selector"], label="capture selector")
    if capture.get("clip"):
        clip = mapping(capture["clip"], label="capture clip")
        validate_keys(clip, {"selector", "padding"}, label="capture clip")
        result["clip"] = {
            "selector": validate_selector(clip.get("selector"), label="capture clip selector"),
            "padding": bounded_int(clip.get("padding", 0), label="capture clip padding", minimum=0, maximum=500),
        }
    result["padding"] = bounded_int(capture.get("padding", 0), label="capture padding", minimum=0, maximum=500)
    modes = int(result["full_page"]) + int("selector" in result) + int("clip" in result)
    if modes > 1:
        raise WebCaptureError("capture full_page, selector, and clip are mutually exclusive.")
    return result


def normalize_theme(raw: Any) -> dict[str, Any]:
    theme = mapping(raw, label="theme")
    validate_keys(theme, {"setting", "color_scheme", "expect"}, label="theme")
    setting = str(theme.get("setting") or "").strip()
    if len(setting) > 80 or any(ord(char) < 32 for char in setting):
        raise WebCaptureError("theme setting is invalid.")
    color_scheme = str(theme.get("color_scheme") or ("dark" if setting == "dark" else "light"))
    if color_scheme not in {"light", "dark", "no-preference"}:
        raise WebCaptureError("theme color_scheme must be light, dark, or no-preference.")
    result: dict[str, Any] = {"setting": setting, "color_scheme": color_scheme, "expect": None}
    if theme.get("expect"):
        expect = mapping(theme["expect"], label="theme expect")
        validate_keys(expect, {"selector", "attribute", "equals"}, label="theme expect")
        attribute = str(expect.get("attribute") or "").strip()
        equals = str(expect.get("equals") or "")
        if not re.fullmatch(r"[A-Za-z_:][-A-Za-z0-9_:.]*", attribute):
            raise WebCaptureError("theme expect attribute is invalid.")
        result["expect"] = {
            "selector": validate_selector(expect.get("selector"), label="theme expect selector"),
            "attribute": attribute,
            "equals": equals,
        }
    return result


def normalize_waits(raw: Any) -> dict[str, Any]:
    waits = mapping(raw, label="waits")
    validate_keys(waits, {"wait_until", "timeout_ms", "delay_ms", "fonts", "images", "selectors"}, label="waits")
    wait_until = str(waits.get("wait_until") or "load")
    if wait_until not in {"load", "domcontentloaded", "commit"}:
        raise WebCaptureError("waits wait_until must be load, domcontentloaded, or commit.")
    selectors = []
    for index, raw_selector in enumerate(waits.get("selectors") or []):
        item = {"selector": raw_selector} if isinstance(raw_selector, str) else mapping(raw_selector, label=f"wait selector {index}")
        validate_keys(item, {"selector", "state"}, label=f"wait selector {index}")
        state = str(item.get("state") or "visible")
        if state not in {"attached", "detached", "visible", "hidden"}:
            raise WebCaptureError(f"Invalid wait selector state: {state}")
        selectors.append({"selector": validate_selector(item.get("selector"), label=f"wait selector {index}"), "state": state})
    if len(selectors) > 100:
        raise WebCaptureError("At most 100 wait selectors are allowed.")
    return {
        "wait_until": wait_until,
        "timeout_ms": bounded_int(waits.get("timeout_ms", 30000), label="wait timeout", minimum=1000, maximum=120000),
        "delay_ms": bounded_int(waits.get("delay_ms", 0), label="wait delay", minimum=0, maximum=10000),
        "fonts": waits.get("fonts", True) is not False,
        "images": waits.get("images", True) is not False,
        "selectors": selectors,
    }


def normalize_annotations(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > 100:
        raise WebCaptureError("annotations must be a list of at most 100 items.")
    annotations = []
    for index, value in enumerate(raw):
        item = mapping(value, label=f"annotation {index}")
        validate_keys(item, {"id", "selector", "kind", "text", "padding", "color", "stroke_width", "position", "offset", "strict", "nth", "required"}, label=f"annotation {index}")
        identifier = str(item.get("id") or f"annotation-{index + 1}")
        if not CAPTURE_ID_RE.fullmatch(identifier):
            raise WebCaptureError(f"Invalid annotation id: {identifier}")
        kind = str(item.get("kind") or "outline")
        if kind not in {"outline", "label", "arrow", "spotlight"}:
            raise WebCaptureError(f"Invalid annotation kind: {kind}")
        color = str(item.get("color") or "#b42318")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise WebCaptureError(f"Annotation color must be #RRGGBB: {color}")
        position = str(item.get("position") or "top-right")
        if position not in {"top-left", "top-right", "bottom-left", "bottom-right", "left", "right"}:
            raise WebCaptureError(f"Invalid annotation position: {position}")
        offset = item.get("offset") or [0, 0]
        if not isinstance(offset, list) or len(offset) != 2 or any(isinstance(part, bool) or not isinstance(part, (int, float)) or abs(part) > 2000 for part in offset):
            raise WebCaptureError(f"Annotation offset must contain two bounded numbers: {identifier}")
        annotations.append({
            "id": identifier,
            "selector": validate_selector(item.get("selector"), label=f"annotation {identifier} selector"),
            "kind": kind,
            "text": str(item.get("text") or ""),
            "padding": bounded_int(item.get("padding", 6), label=f"annotation {identifier} padding", minimum=0, maximum=500),
            "color": color.lower(),
            "stroke_width": bounded_int(item.get("stroke_width", 3), label=f"annotation {identifier} stroke_width", minimum=1, maximum=20),
            "position": position,
            "offset": [float(offset[0]), float(offset[1])],
            "strict": item.get("strict", True) is not False,
            "nth": bounded_int(item.get("nth", 0), label=f"annotation {identifier} nth", minimum=0, maximum=1000),
            "required": item.get("required", True) is not False,
        })
    return annotations


def read_recipe(project: Path, source: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WebCaptureError(f"Invalid capture recipe YAML in {relative(project, source)}: {exc}") from exc
    if not isinstance(data, dict):
        raise WebCaptureError(f"Capture recipe must be a YAML mapping: {relative(project, source)}")
    validate_keys(data, {"version", "path", "viewport", "capture", "theme", "waits", "annotations", "inputs", "locale"}, label="capture recipe")
    if data.get("version") != 1:
        raise WebCaptureError(f"Unsupported capture recipe version in {relative(project, source)}")
    inputs = data.get("inputs") or []
    if not isinstance(inputs, list):
        raise WebCaptureError("Capture recipe inputs must be a list.")
    normalized_inputs = [relative(project, safe_relative(project, str(item), label="capture input", must_exist=True)) for item in inputs]
    locale = str(data.get("locale") or "en-US")
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", locale):
        raise WebCaptureError(f"Invalid capture locale: {locale}")
    return {
        "version": 1,
        "path": validate_path(data.get("path")),
        "viewport": normalize_viewport(data.get("viewport")),
        "capture": normalize_capture(data.get("capture")),
        "theme": normalize_theme(data.get("theme")),
        "waits": normalize_waits(data.get("waits")),
        "annotations": normalize_annotations(data.get("annotations")),
        "inputs": normalized_inputs,
        "locale": locale,
    }


def output_paths(source: Path) -> tuple[Path, Path, Path]:
    if not source.name.endswith(SOURCE_SUFFIXES):
        raise WebCaptureError(f"Capture source must end with .capture.yml or .capture.yaml: {source}")
    return source.with_suffix(".png"), source.with_suffix(".svg"), source.with_suffix(".edited.svg")


def discover(project: Path) -> list[dict[str, Any]]:
    assets = project / "assets"
    records = []
    sources = sorted({source for suffix in SOURCE_SUFFIXES for source in assets.rglob(f"*{suffix}")}) if assets.is_dir() else []
    for source in sources:
        if any(part.startswith(".") for part in source.relative_to(project).parts):
            continue
        recipe = read_recipe(project, source)
        png, svg, edited = output_paths(source)
        records.append({"source": source, "source_path": relative(project, source), "recipe": recipe, "png": png, "svg": svg, "edited": edited})
    return records


def selected_records(project: Path, source: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = discover(project)
    if not source:
        return records, records
    if not SAFE_SOURCE_RE.fullmatch(source) or source.startswith("/") or ".." in Path(source).parts:
        raise WebCaptureError("Selected capture source must be a safe project-relative *.capture.yml or *.capture.yaml path.")
    selected = safe_relative(project, source, label="selected capture source", must_exist=True)
    matches = [record for record in records if record["source"] == selected]
    if not matches:
        raise WebCaptureError(f"Selected file is not a capture recipe under assets/: {source}")
    return matches, records


def load_lock(project: Path) -> dict[str, Any]:
    path = project / LOCK_PATH
    if not path.is_file():
        return {"version": 1, "records": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WebCaptureError(f"Invalid web capture lock file: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("records"), dict):
        raise WebCaptureError("Invalid web-captures.lock.json structure.")
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
    configured_id = os.environ.get("UNALTRAWEB_CAPTURE_IMAGE_ID", "").strip()
    configured_digest = os.environ.get("UNALTRAWEB_CAPTURE_IMAGE_DIGEST", "").strip()
    if configured_id or configured_digest:
        return {"available": "true", "id": configured_id, "digest": configured_digest}
    if not shutil.which("docker"):
        return {"available": "false", "id": "", "digest": ""}
    completed = subprocess.run(["docker", "image", "inspect", image, "--format", '{{.Id}}|{{join .RepoDigests ","}}'], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if completed.returncode != 0:
        return {"available": "false", "id": "", "digest": ""}
    image_id, _, digest = completed.stdout.strip().partition("|")
    return {"available": "true", "id": image_id, "digest": digest}


def selected_image() -> str:
    return os.environ.get("WEB_CAPTURE_IMAGE", "").strip() or DEFAULT_IMAGE


def factory_root() -> Path:
    configured = os.environ.get("UNALTRAWEB_FACTORY_ROOT", "").strip()
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[2]


def renderer_files() -> list[Path]:
    root = factory_root()
    return [
        root / "scripts/web_captures/render.py",
        root / "scripts/web_captures/capture.mjs",
        root / "scripts/web_captures/Dockerfile",
        root / "scripts/web_captures/package.json",
        root / "scripts/web_captures/package-lock.json",
        root / "_config.yml",
        root / "_plugins",
        root / "_layouts",
        root / "_includes",
        root / "_sass",
        root / "assets/js",
    ]


def fingerprint(project: Path, record: dict[str, Any], saved: dict[str, Any] | None = None) -> tuple[str, list[dict[str, str]], dict[str, str]]:
    dependencies = [record["source"], *[safe_relative(project, item, label="capture input", must_exist=True) for item in record["recipe"]["inputs"]]]
    signatures = [signature for path in dependencies for signature in path_signatures(project, path)]
    root = factory_root()
    renderer = [
        {"path": str(item.relative_to(root)).replace(os.sep, "/"), "sha256": file_signature(item)["sha256"]}
        for path in renderer_files() if path.exists()
        for item in ([path] if path.is_file() else sorted(candidate for candidate in path.rglob("*") if candidate.is_file()))
    ]
    image = selected_image()
    local_identity = inspect_image(image)
    saved_identity = (saved or {}).get("image_identity") if isinstance((saved or {}).get("image_identity"), dict) else {}
    identity = local_identity if local_identity["available"] == "true" else saved_identity
    payload = {"recipe": record["recipe"], "dependencies": signatures, "renderer": renderer, "image": image, "image_identity": identity}
    return sha256_bytes(canonical_json(payload)), signatures, {"image": image, **identity}


def signatures_match(path: Path, saved: Any) -> bool:
    return isinstance(saved, dict) and path.is_file() and saved.get("sha256") == file_signature(path)["sha256"] and saved.get("size") == path.stat().st_size


def svg_metadata(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = SVG_METADATA_RE.search(text)
    if not match:
        return None
    try:
        value = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def validate_svg_safety(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise WebCaptureError(f"Unsafe executable content in capture SVG: {path}")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise WebCaptureError(f"Invalid capture SVG XML: {path}: {exc}") from exc
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag not in SVG_ALLOWED_ELEMENTS:
            raise WebCaptureError(f"Unsupported element in capture SVG: {path}: {tag}")
        for raw_name, raw_value in element.attrib.items():
            name = raw_name.rsplit("}", 1)[-1].lower()
            value = raw_value.strip()
            lowered_value = value.lower()
            if name not in SVG_ALLOWED_ATTRIBUTES:
                raise WebCaptureError(f"Unsupported attribute in capture SVG: {path}: {name}")
            if "@import" in lowered_value or "javascript:" in lowered_value or "expression(" in lowered_value:
                raise WebCaptureError(f"Unsafe attribute in capture SVG: {path}: {name}")
            if name == "href" and not (value.startswith("data:image/png;base64,") or value.startswith("#")):
                raise WebCaptureError(f"External reference in capture SVG: {path}")
            without_local_urls = re.sub(r"url\(\s*['\"]?#[A-Za-z_][-:.A-Za-z0-9_]*['\"]?\s*\)", "", lowered_value)
            if "url(" in without_local_urls:
                raise WebCaptureError(f"External CSS reference in capture SVG: {path}")
            if name == "style":
                declarations = [part.strip() for part in value.split(";") if part.strip()]
                for declaration in declarations:
                    property_name, separator, _ = declaration.partition(":")
                    if not separator or property_name.strip().lower() not in SVG_ALLOWED_STYLE_PROPERTIES:
                        raise WebCaptureError(f"Unsupported style in capture SVG: {path}: {property_name.strip()}")


def edited_state(record: dict[str, Any], fingerprint_value: str = "") -> dict[str, Any]:
    edited = record["edited"]
    if not edited.is_file():
        return {"status": "none", "path": ""}
    validate_svg_safety(edited)
    metadata = svg_metadata(edited)
    png_hash = file_signature(record["png"])["sha256"] if record["png"].is_file() else ""
    if not metadata or not metadata.get("png_sha256") or not metadata.get("fingerprint"):
        return {"status": "invalid", "path": str(edited)}
    current = metadata["png_sha256"] == png_hash and (not fingerprint_value or metadata["fingerprint"] == fingerprint_value)
    return {"status": "current" if current else "stale", "path": str(edited), "png_sha256": metadata["png_sha256"], "fingerprint": metadata["fingerprint"]}


def orphaned_artifacts(project: Path, records: list[dict[str, Any]]) -> list[str]:
    expected = {relative(project, path) for record in records for path in [record["png"], record["svg"], record["edited"]]}
    assets = project / "assets"
    actual = {
        relative(project, path)
        for pattern in ["*.capture.png", "*.capture.svg", "*.capture.edited.svg"]
        for path in (assets.rglob(pattern) if assets.is_dir() else [])
    }
    return sorted(actual - expected)


def status(project: Path, source: str = "") -> dict[str, Any]:
    selected, all_records = selected_records(project, source)
    lock = load_lock(project)
    items = []
    for record in selected:
        saved = lock["records"].get(record["source_path"], {})
        current_fingerprint, dependencies, image = fingerprint(project, record, saved)
        png_valid = signatures_match(record["png"], saved.get("png"))
        svg_valid = signatures_match(record["svg"], saved.get("svg"))
        if record["svg"].is_file():
            validate_svg_safety(record["svg"])
        edited = edited_state(record, current_fingerprint)
        current = bool(saved and saved.get("fingerprint") == current_fingerprint and png_valid and svg_valid and edited["status"] in {"none", "current"})
        reason = "current"
        if not saved:
            reason = "not_rendered"
        elif saved.get("fingerprint") != current_fingerprint:
            reason = "source_or_environment_changed"
        elif not record["png"].is_file():
            reason = "png_missing"
        elif not png_valid:
            reason = "png_modified"
        elif not record["svg"].is_file():
            reason = "svg_missing"
        elif not svg_valid:
            reason = "svg_modified"
        elif edited["status"] == "stale":
            reason = "edited_override_stale"
        elif edited["status"] == "invalid":
            reason = "edited_override_invalid"
        effective = record["edited"] if record["edited"].is_file() else record["svg"]
        items.append({
            "source": record["source_path"],
            "path": record["recipe"]["path"],
            "png": relative(project, record["png"]),
            "svg": relative(project, record["svg"]),
            "edited_svg": relative(project, record["edited"]),
            "effective_svg": relative(project, effective),
            "edited": {**edited, "path": relative(project, record["edited"]) if record["edited"].is_file() else ""},
            "image": image,
            "dependencies": dependencies,
            "fingerprint": current_fingerprint,
            "current": current,
            "reason": reason,
        })
    known = {record["source_path"] for record in all_records}
    orphaned = sorted(path for path in lock["records"] if path not in known)
    orphaned_files = orphaned_artifacts(project, all_records)
    return {
        "project": str(project),
        "lock": str(LOCK_PATH) if (project / LOCK_PATH).is_file() else "",
        "captures": items,
        "capture_count": len(items),
        "current_count": sum(1 for item in items if item["current"]),
        "orphaned_records": orphaned,
        "orphaned_artifacts": orphaned_files,
        "ok": all(item["current"] for item in items) and not orphaned and not orphaned_files,
    }


def validate_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise WebCaptureError("Base URL must be an http(s) origin without credentials, path, query, or fragment.")
    hostname = (parsed.hostname or "").lower()
    service_host = os.environ.get("WEB_CAPTURE_SERVICE_HOST", "").strip().lower()
    network = os.environ.get("WEB_CAPTURE_DOCKER_NETWORK", "").strip()
    allowed = bool(service_host and hostname == service_host and network not in {"", "host", "none"})
    if not allowed:
        raise WebCaptureError("Base URL must use the declared service host on an isolated Docker network.")
    if not internal_network(network):
        raise WebCaptureError(f"Browser capture requires an internal Docker network: {network}")
    return f"{parsed.scheme}://{parsed.netloc}"


def internal_network(network: str) -> bool:
    if not shutil.which("docker") or network in {"", "host", "none"}:
        return False
    completed = subprocess.run(
        ["docker", "network", "inspect", network, "--format", "{{.Internal}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip().lower() == "true"


def build_image(image: str) -> None:
    available = inspect_image(image)["available"] == "true"
    if available:
        return
    if image != DEFAULT_IMAGE:
        completed = subprocess.run(["docker", "pull", image], check=False)
        if completed.returncode != 0:
            raise WebCaptureError(f"Could not pull web capture image: {image}")
        return
    root = factory_root()
    command = ["docker", "build"]
    network = os.environ.get("WEB_CAPTURE_DOCKER_BUILD_NETWORK", "").strip()
    if network:
        command.extend(["--network", network])
    command.extend(["-f", str(root / "scripts/web_captures/Dockerfile"), "-t", image, str(root)])
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise WebCaptureError(f"Could not build web capture image: {image}")


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise WebCaptureError(f"Invalid PNG output: {path}")
    return struct.unpack(">II", data[16:24])


def xml(value: Any) -> str:
    return html.escape(str(value), quote=True)


def annotation_box(annotation: dict[str, Any], origin: dict[str, float], scale: float) -> dict[str, float]:
    box = annotation["box"]
    padding = annotation["padding"]
    return {
        "x": (box["x"] - origin["x"] - padding) * scale,
        "y": (box["y"] - origin["y"] - padding) * scale,
        "width": (box["width"] + padding * 2) * scale,
        "height": (box["height"] + padding * 2) * scale,
    }


def label_position(box: dict[str, float], position: str, offset: list[float], scale: float) -> tuple[float, float]:
    x = box["x"] + box["width"]
    y = box["y"] - 12 * scale
    if "left" in position:
        x = box["x"]
    if "bottom" in position:
        y = box["y"] + box["height"] + 26 * scale
    if position == "left":
        x, y = box["x"] - 16 * scale, box["y"] + box["height"] / 2
    if position == "right":
        x, y = box["x"] + box["width"] + 16 * scale, box["y"] + box["height"] / 2
    return x + offset[0] * scale, y + offset[1] * scale


def svg_for(project: Path, record: dict[str, Any], png: Path, worker: dict[str, Any], fingerprint_value: str) -> str:
    width, height = png_dimensions(png)
    scale = float(worker["device_scale_factor"])
    metadata = {
        "schema": 1,
        "source": record["source_path"],
        "png_sha256": file_signature(png)["sha256"],
        "fingerprint": fingerprint_value,
        "path": record["recipe"]["path"],
        "viewport": record["recipe"]["viewport"],
        "browser_version": worker.get("browser_version", ""),
    }
    background = base64.b64encode(png.read_bytes()).decode("ascii")
    highlights: list[str] = []
    arrows: list[str] = []
    labels: list[str] = []
    notes: list[str] = []
    for annotation in worker.get("annotations", []):
        box = annotation_box(annotation, worker["origin"], scale)
        if box["x"] + box["width"] <= 0 or box["y"] + box["height"] <= 0 or box["x"] >= width or box["y"] >= height:
            if annotation.get("required", True):
                raise WebCaptureError(f"Annotation is outside the captured area: {annotation['id']}")
            continue
        identifier = xml(annotation["id"])
        selector = xml(annotation["selector"])
        color = annotation["color"]
        stroke = annotation["stroke_width"] * scale
        rect = f'<rect x="{box["x"]:.2f}" y="{box["y"]:.2f}" width="{box["width"]:.2f}" height="{box["height"]:.2f}" rx="{6 * scale:.2f}" fill="none" stroke="{color}" stroke-width="{stroke:.2f}"/>'
        if annotation["kind"] == "spotlight":
            path = f'M0 0H{width}V{height}H0Z M{box["x"]:.2f} {box["y"]:.2f}h{box["width"]:.2f}v{box["height"]:.2f}h-{box["width"]:.2f}Z'
            highlights.append(f'<g id="annotation-{identifier}" data-selector="{selector}"><path d="{path}" fill="#000000" fill-opacity="0.48" fill-rule="evenodd"/>{rect}</g>')
        else:
            highlights.append(f'<g id="annotation-{identifier}" data-selector="{selector}">{rect}</g>')
        text = annotation.get("text", "")
        if text:
            lx, ly = label_position(box, annotation["position"], annotation["offset"], scale)
            text_width = max(44, min(420, len(text) * 8 + 20)) * scale
            text_height = 30 * scale
            lx = max(4 * scale, min(lx, width - text_width - 4 * scale))
            ly = max(text_height, min(ly, height - 4 * scale))
            label = (
                f'<g id="label-{identifier}" data-selector="{selector}">'
                f'<rect x="{lx:.2f}" y="{ly - text_height:.2f}" width="{text_width:.2f}" height="{text_height:.2f}" rx="{5 * scale:.2f}" fill="{color}"/>'
                f'<text x="{lx + 10 * scale:.2f}" y="{ly - 9 * scale:.2f}" fill="#ffffff" font-family="Arial, sans-serif" font-size="{14 * scale:.2f}" font-weight="600">{xml(text)}</text></g>'
            )
            labels.append(label)
            if annotation["kind"] == "arrow":
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                arrows.append(f'<path id="arrow-{identifier}" d="M{lx + text_width / 2:.2f} {ly:.2f} L{cx:.2f} {cy:.2f}" fill="none" stroke="{color}" stroke-width="{stroke:.2f}" marker-end="url(#arrowhead)"/>')
        if annotation["kind"] == "label" and not text:
            notes.append(f'<!-- Empty label annotation: {identifier} -->')
    metadata_text = xml(json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <metadata id="unaltraweb-capture">{metadata_text}</metadata>\n'
        '  <defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#b42318"/></marker></defs>\n'
        f'  <g id="background" inkscape:groupmode="layer" inkscape:label="Background"><image width="{width}" height="{height}" href="data:image/png;base64,{background}"/></g>\n'
        f'  <g id="highlights" inkscape:groupmode="layer" inkscape:label="Highlights">{"".join(highlights)}</g>\n'
        f'  <g id="arrows" inkscape:groupmode="layer" inkscape:label="Arrows">{"".join(arrows)}</g>\n'
        f'  <g id="labels" inkscape:groupmode="layer" inkscape:label="Labels">{"".join(labels)}</g>\n'
        f'  <g id="notes" inkscape:groupmode="layer" inkscape:label="Notes">{"".join(notes)}</g>\n'
        '</svg>\n'
    )


def worker_config(record: dict[str, Any], base_url: str, png_path: str, result_path: str) -> dict[str, Any]:
    recipe = record["recipe"]
    return {
        "url": base_url + recipe["path"],
        "viewport": recipe["viewport"],
        "capture": recipe["capture"],
        "theme": recipe["theme"],
        "waits": recipe["waits"],
        "annotations": recipe["annotations"],
        "locale": recipe["locale"],
        "png_path": png_path,
        "result_path": result_path,
    }


def run_worker(project: Path, image: str, config_path: Path) -> None:
    network = os.environ.get("WEB_CAPTURE_DOCKER_NETWORK", "").strip()
    if not internal_network(network):
        raise WebCaptureError("Browser capture requires a named isolated Docker network.")
    command = [
        "docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "--network", network, "--ipc=host",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "256", "--cpus", "2", "--memory", "2g",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m", "-e", "HOME=/tmp", "-v", f"{project}:/project:rw", "-w", "/project", image,
        "/project/" + relative(project, config_path),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise WebCaptureError(f"Browser capture failed with exit code {completed.returncode}.")


def publish(record: dict[str, Any], png_temp: Path, svg_text: str, *, confirm_overwrite: bool, owned: bool) -> None:
    png = record["png"]
    svg = record["svg"]
    if not owned and (png.exists() or svg.exists()) and not confirm_overwrite:
        raise WebCaptureError(f"Refusing to replace unmanaged capture outputs for {record['source_path']}; rerun with --confirm-overwrite after review.")
    png.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(6)
    svg_temp = svg.with_name(f".{svg.name}.{token}.tmp")
    png_stage = png.with_name(f".{png.name}.{token}.tmp")
    png_backup = png.with_name(f".{png.name}.{token}.backup")
    svg_backup = svg.with_name(f".{svg.name}.{token}.backup")
    shutil.copy2(png_temp, png_stage)
    svg_temp.write_text(svg_text, encoding="utf-8")
    try:
        if png.exists():
            os.replace(png, png_backup)
        if svg.exists():
            os.replace(svg, svg_backup)
        os.replace(png_stage, png)
        os.replace(svg_temp, svg)
    except Exception:
        png.unlink(missing_ok=True)
        svg.unlink(missing_ok=True)
        if png_backup.exists():
            os.replace(png_backup, png)
        if svg_backup.exists():
            os.replace(svg_backup, svg)
        raise
    finally:
        for path in [png_stage, svg_temp, png_backup, svg_backup]:
            path.unlink(missing_ok=True)


@contextlib.contextmanager
def project_lock(project: Path):
    root = project / "tmp" / "web-captures"
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".render.lock").open("w", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def render(project: Path, base_url: str, source: str = "", confirm_overwrite: bool = False) -> dict[str, Any]:
    base_url = validate_base_url(base_url)
    selected, _ = selected_records(project, source)
    image = selected_image()
    build_image(image)
    lock = load_lock(project)
    rendered = []
    with project_lock(project):
        for record in selected:
            saved = lock["records"].get(record["source_path"], {})
            current_fingerprint, dependencies, image_state = fingerprint(project, record, saved)
            with tempfile.TemporaryDirectory(prefix=f"{record['source'].stem}-", dir=project / "tmp" / "web-captures") as temporary_raw:
                temporary = Path(temporary_raw)
                png_temp = temporary / "capture.png"
                result_temp = temporary / "result.json"
                config_temp = temporary / "config.json"
                config_temp.write_text(json_dump(worker_config(record, base_url, "/project/" + relative(project, png_temp), "/project/" + relative(project, result_temp))), encoding="utf-8")
                run_worker(project, image, config_temp)
                if not png_temp.is_file() or not result_temp.is_file():
                    raise WebCaptureError(f"Browser worker did not produce capture outputs for {record['source_path']}.")
                worker = json.loads(result_temp.read_text(encoding="utf-8"))
                svg_text = svg_for(project, record, png_temp, worker, current_fingerprint)
                publish(record, png_temp, svg_text, confirm_overwrite=confirm_overwrite, owned=bool(saved))
            identity = inspect_image(image)
            lock["records"][record["source_path"]] = {
                "fingerprint": current_fingerprint,
                "dependencies": dependencies,
                "image": image,
                "image_identity": identity,
                "png": {"path": relative(project, record["png"]), **file_signature(record["png"])},
                "svg": {"path": relative(project, record["svg"]), **file_signature(record["svg"])},
                "captured_at": utc_now(),
                "final_path": urlsplit(worker.get("final_url", "")).path,
                "browser_version": worker.get("browser_version", ""),
            }
            write_lock(project, lock)
            rendered.append({"source": record["source_path"], "png": relative(project, record["png"]), "svg": relative(project, record["svg"]), "effective_svg": relative(project, record["edited"] if record["edited"].is_file() else record["svg"]), "annotations": len(worker.get("annotations", []))})
    return {"project": str(project), "rendered": rendered, "rendered_count": len(rendered), "ok": True}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="unaltraweb-web-captures")
    root.add_argument("command", choices=["status", "check", "render"])
    root.add_argument("--project", default=".")
    root.add_argument("--source", default="")
    root.add_argument("--base-url", default="")
    root.add_argument("--confirm-overwrite", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    try:
        if args.command in {"status", "check"}:
            result = status(project, source=args.source)
        else:
            if not args.base_url:
                raise WebCaptureError("render requires --base-url for a trusted running preview.")
            result = render(project, args.base_url, source=args.source, confirm_overwrite=args.confirm_overwrite)
        print(json_dump(result), end="")
        return 0 if args.command == "status" or result.get("ok") else 1
    except WebCaptureError as exc:
        print(json_dump({"project": str(project), "ok": False, "error": str(exc)}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
