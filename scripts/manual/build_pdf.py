#!/usr/bin/env python3
"""Build and locally publish unaltremanual PDFs from Jekyll sources."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - supplied by the builder image
    raise SystemExit("PyYAML is required to build an unaltremanual PDF.") from exc


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_DOCKERFILE = SCRIPT_ROOT / "Dockerfile"
DEFAULT_TEMPLATE = SCRIPT_ROOT / "templates" / "manual.tex"
DEFAULT_BIBLIOGRAPHY_FILTER = SCRIPT_ROOT / "filters" / "bibliography.lua"
DEFAULT_CODE_BLOCK_FILTER = SCRIPT_ROOT / "filters" / "code-blocks.lua"
DEFAULT_FIGURE_FILTER = SCRIPT_ROOT / "filters" / "figure-captions.lua"
BIB_ENTRY_HEADER_RE = re.compile(r"(?im)^\s*@(?:[A-Za-z]+)\s*[({]\s*([^,\s]+)\s*,")
BIB_CUSTOM_URL_RE = re.compile(r'(?im)^\s*(?:manual_url|website)\s*=\s*(?:\{([^}\r\n]+)\}|"([^"\r\n]+)")\s*,?')
FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)", re.MULTILINE | re.DOTALL)
CITE_RE = re.compile(r"{%\s*cite\s+([^%]+?)\s*%}")
INCLUDE_RE = re.compile(r"{%\s*include\s+([^%]+?)\s*%}")
LIQUID_RE = re.compile(r"({[{%].*?[}%]})", re.DOTALL)
INLINE_CODE_RE = re.compile(r"<code>(.*?)</code>", re.IGNORECASE | re.DOTALL)
FENCED_CODE_BLOCK_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
MARKDOWN_INLINE_CODE_RE = re.compile(r"(`+)[^\n]*?\1")
DISPLAY_MATH_BLOCK_RE = re.compile(
    r"^[ \t]*\$\$[ \t]*\r?\n(?P<body>.*?)^[ \t]*\$\$[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
BASEURL_RE = re.compile(r"\{\{\s*site\.baseurl\s*\}\}")
IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>\S+?)(?:\s+(?:\"(?P<double_title>[^\"]*)\"|'(?P<single_title>[^']*)'))?\)"
    r"(?P<attrs>\{:[^}\n]*\})?"
)
TABLE_DIV_RE = re.compile(r'^::: table\s+["\'](.+?)["\']\s*\n(.*?)^:::\s*$', re.MULTILINE | re.DOTALL)
PIPE_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?\s*$")
TABLE_GUARD_AFTER_HEADING_RE = re.compile(
    r"^(?P<heading>#{2,6}\s+[^\n]+)\n\n```\{=latex\}\n"
    r"(?P<guard>\\(?:clearpage|Needspace\{(?P<baselines>\d+)\\baselineskip\}))\n```",
    re.MULTILINE,
)
SUBFIGURES_DIV_RE = re.compile(
    r'^:::\s*subfigures(?:\s+(?P<layout>[^\s"]+))?(?:\s+"(?P<caption>[^"]*)")?\s*\n'
    r'(?P<body>.*?)^:::\s*$',
    re.MULTILINE | re.DOTALL,
)
CALLOUT_BLOCK_RE = re.compile(r"^(?P<block>(?P<marks>>{2,})[^\n]*(?:\n(?P=marks)[^\n]*)*)", re.MULTILINE)
FIGURE_DIMENSION_ATTR_RE = re.compile(
    r"(?:\A|\s)(?P<name>data-figure-(?:width|height)(?:-(?:web|pdf))?)\s*=\s*"
    r"(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s}]+))"
)
LANGUAGE_NAMES = {"ca": "catalan", "es": "spanish", "en": "english"}
LANGUAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
COMPUTATION_SUFFIXES = {".qmd", ".rmd", ".r", ".py", ".ipynb"}
DIAGRAM_SUFFIXES = {".mmd", ".mermaid", ".puml", ".plantuml", ".uml"}
GENERATED_MEDIA_SUFFIXES = {".gif", ".jpeg", ".jpg", ".pdf", ".png", ".svg", ".webp"}
VEGA_SOURCE_SUFFIXES = (".vl.json", ".vg.json")
VEGA_OUTPUT_SUFFIXES = {".svg", ".png", ".pdf"}
VEGA_MANIFEST_NAME = ".vegavisuals.yml"
VEGA_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
REMOTE_PATH_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)?//", re.IGNORECASE)
VISUAL_LOCALIZATION_SUFFIXES = tuple(sorted({
    ".capture.edited.svg", ".capture.yaml", ".capture.yml", ".capture.svg",
    ".mermaid.edited.svg", ".mermaid.svg", ".plantuml.edited.svg", ".plantuml.svg",
    ".mmd.edited.svg", ".mmd.svg", ".puml.edited.svg", ".puml.svg", ".uml.edited.svg", ".uml.svg",
    ".vl.json", ".vg.json", ".edited.svg",
    ".qmd", ".rmd", ".ipynb", ".mermaid", ".plantuml", ".mmd", ".puml", ".uml", ".py", ".r",
    ".jpeg", ".tiff", ".webp", ".gif", ".jpg", ".png", ".svg", ".pdf",
}, key=len, reverse=True))
REPRODUCIBLE_BUILD_EPOCH = "0"
CALLOUT_STYLES = {
    2: ("ManualCalloutInfo", "info"),
    3: ("ManualCalloutExample", "example"),
    4: ("ManualCalloutWarning", "warning"),
    5: ("ManualCalloutObjectives", "objectives"),
    6: ("ManualCalloutDanger", "danger"),
}
CALLOUT_LABELS = {
    "ca": {
        "info": "NOTA",
        "example": "EXEMPLE",
        "warning": "ADVERTÈNCIA",
        "objectives": "OBJECTIUS D'APRENENTATGE",
        "danger": "ATENCIÓ",
    },
    "es": {
        "info": "NOTA",
        "example": "EJEMPLO",
        "warning": "ADVERTENCIA",
        "objectives": "OBJETIVOS DE APRENDIZAJE",
        "danger": "ATENCIÓN",
    },
    "en": {
        "info": "NOTE",
        "example": "EXAMPLE",
        "warning": "WARNING",
        "objectives": "LEARNING OBJECTIVES",
        "danger": "CAUTION",
    },
}
CODE_BLOCK_LABELS = {"ca": "Codi", "es": "Código", "en": "Code"}
CAPTURE_SVG_ALLOWED_ELEMENTS = {
    "svg", "g", "defs", "metadata", "title", "desc", "image", "rect", "path", "text", "tspan",
    "marker", "polygon", "polyline", "line", "circle", "ellipse", "clippath", "mask", "lineargradient",
    "radialgradient", "stop", "pattern", "use", "namedview", "grid", "page",
}
CAPTURE_SVG_ALLOWED_ATTRIBUTES = {
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
CAPTURE_SVG_ALLOWED_STYLE_PROPERTIES = {
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray",
    "stroke-dashoffset", "opacity", "fill-opacity", "stroke-opacity", "fill-rule", "clip-rule", "clip-path", "mask",
    "font-family", "font-size", "font-style", "font-weight", "text-anchor", "dominant-baseline", "marker-start", "marker-mid",
    "marker-end", "stop-color", "stop-opacity", "display", "visibility",
}
METADATA_LABELS = {
    "ca": {
        "title": "Crèdits editorials",
        "series": "Col·lecció",
        "publisher": "Editorial",
        "edition": "Edició",
        "publication_date": "Data de publicació",
        "subject": "Assignatura",
        "teaching_guides": "Guies docents",
        "academic_year": "Curs acadèmic",
        "department": "Departament",
        "faculty": "Facultat",
        "institution": "Institució",
        "location": "Localització",
        "revision_date": "Data de revisió",
        "instructors": "Autoria",
        "identifier": "Identificador",
        "license": "Llicència",
        "source": "Edició web",
        "rights": "Drets",
        "references": "Referències",
    },
    "es": {
        "title": "Créditos editoriales",
        "series": "Colección",
        "publisher": "Editorial",
        "edition": "Edición",
        "publication_date": "Fecha de publicación",
        "subject": "Asignatura",
        "teaching_guides": "Guías docentes",
        "academic_year": "Curso académico",
        "department": "Departamento",
        "faculty": "Facultad",
        "institution": "Institución",
        "location": "Localización",
        "revision_date": "Fecha de revisión",
        "instructors": "Autoría",
        "identifier": "Identificador",
        "license": "Licencia",
        "source": "Edición web",
        "rights": "Derechos",
        "references": "Referencias",
    },
    "en": {
        "title": "Editorial credits",
        "series": "Series",
        "publisher": "Publisher",
        "edition": "Edition",
        "publication_date": "Publication date",
        "subject": "Course",
        "teaching_guides": "Teaching guides",
        "academic_year": "Academic year",
        "department": "Department",
        "faculty": "Faculty",
        "institution": "Institution",
        "location": "Location",
        "revision_date": "Revision date",
        "instructors": "Authors",
        "identifier": "Identifier",
        "license": "License",
        "source": "Web edition",
        "rights": "Rights",
        "references": "References",
    },
}


class ManualPdfError(RuntimeError):
    pass


class UniqueKeySafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable mapping key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key: {key}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ManualPdfError(f"Missing required YAML file: {path}")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def read_source(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    parsed = yaml.safe_load(match.group(1))
    return (parsed if isinstance(parsed, dict) else {}), text[match.end():]


def nested(config: dict[str, Any], *keys: str) -> dict[str, Any]:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def safe_relative(project: Path, raw: str, *, label: str, must_exist: bool = False) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise ManualPdfError(f"No {label} path is configured.")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManualPdfError(f"{label} must be a project-relative path: {raw}")
    resolved = (project / relative).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ManualPdfError(f"{label} escapes the project: {raw}") from exc
    if must_exist and not resolved.exists():
        raise ManualPdfError(f"Missing {label}: {relative}")
    return resolved


def validate_language(value: str) -> str:
    language = value.strip()
    if not language or not LANGUAGE_RE.fullmatch(language):
        raise ManualPdfError(f"Invalid PDF language: {value!r}")
    return language


def normalize_callout_language(value: Any) -> str:
    normalized = str(value or "").lower().split("-", 1)[0]
    return normalized or "en"


def language_data(project: Path, config: dict[str, Any], lang: str) -> tuple[dict[str, Any], Path | None]:
    data_root = safe_relative(project, str(config.get("data_dir") or "_data"), label="Jekyll data directory")
    if not LANGUAGE_RE.fullmatch(lang):
        return {}, None
    for suffix in (".yml", ".yaml"):
        path = data_root / "i18n" / f"{lang}{suffix}"
        if not path.is_file():
            continue
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        return (parsed if isinstance(parsed, dict) else {}), path
    return {}, None


def resolve_callout_labels(project: Path, config: dict[str, Any], language: str) -> tuple[dict[str, str], list[Path]]:
    normalized_language = normalize_callout_language(language)
    default_language = normalize_callout_language(config.get("default_lang") or config.get("lang") or "en")
    localized_data, localized_path = language_data(project, config, normalized_language)
    if default_language == normalized_language:
        default_data, default_path = localized_data, localized_path
    else:
        default_data, default_path = language_data(project, config, default_language)

    localized_callouts = localized_data.get("callouts")
    default_callouts = default_data.get("callouts")
    if isinstance(localized_callouts, dict):
        configured = localized_callouts
    elif isinstance(default_callouts, dict):
        configured = default_callouts
    else:
        configured = {}

    defaults = CALLOUT_LABELS.get(normalized_language) or CALLOUT_LABELS.get(default_language) or CALLOUT_LABELS["en"]
    labels = dict(defaults)
    labels.update({str(key): "" if value is None else str(value) for key, value in configured.items()})
    dependencies = list(dict.fromkeys(path for path in (localized_path, default_path) if path is not None))
    return labels, dependencies


def resolve_code_block_label(project: Path, config: dict[str, Any], language: str) -> tuple[str, list[Path]]:
    normalized_language = normalize_callout_language(language)
    default_language = normalize_callout_language(config.get("default_lang") or config.get("lang") or "en")
    localized_data, localized_path = language_data(project, config, normalized_language)
    if default_language == normalized_language:
        default_data, default_path = localized_data, localized_path
    else:
        default_data, default_path = language_data(project, config, default_language)

    localized_label = nested(localized_data, "code_blocks").get("label")
    default_label = nested(default_data, "code_blocks").get("label")
    label = str(
        localized_label
        or default_label
        or CODE_BLOCK_LABELS.get(normalized_language)
        or CODE_BLOCK_LABELS.get(default_language)
        or CODE_BLOCK_LABELS["en"]
    )
    dependencies = list(dict.fromkeys(path for path in (localized_path, default_path) if path is not None))
    return label, dependencies


def language_list(config: dict[str, Any], pdf: dict[str, Any], requested: str = "") -> list[str]:
    configured = pdf.get("languages")
    values: list[str] = []
    if isinstance(configured, list):
        values = [validate_language(str(item)) for item in configured if str(item).strip()]
    if not values:
        values = [validate_language(str(config.get("default_lang") or config.get("lang") or "en"))]
    if requested.strip():
        language = validate_language(requested)
        if language not in values:
            raise ManualPdfError(f"Language '{language}' is not enabled in unaltraweb.manual.pdf.languages.")
        return [language]
    return values


def render_path(template: str, lang: str) -> str:
    try:
        return template.format(lang=lang)
    except (KeyError, ValueError) as exc:
        raise ManualPdfError(f"Invalid language path template: {template}") from exc


def artifact_paths(project: Path, config: dict[str, Any], lang: str) -> dict[str, Path]:
    lang = validate_language(lang)
    manual = nested(config, "unaltraweb", "manual")
    pdf = manual.get("pdf") if isinstance(manual.get("pdf"), dict) else {}
    build_dir_raw = str(pdf.get("build_dir") or "tmp/manual-pdf")
    build_root_raw = str(Path(build_dir_raw) / lang)
    build_root = safe_relative(project, build_root_raw, label="language PDF build directory")
    public_pdf_raw = render_path(str(pdf.get("output") or "assets/pdf/manual-{lang}.pdf"), lang)
    public_cover_raw = render_path(str(pdf.get("cover_output") or "assets/img/manual-cover-{lang}.png"), lang)
    if Path(public_pdf_raw).suffix.lower() != ".pdf":
        raise ManualPdfError("Published PDF path must use the .pdf extension.")
    if Path(public_cover_raw).suffix.lower() != ".png":
        raise ManualPdfError("Published cover path must use the .png extension.")
    public_pdf = safe_relative(project, public_pdf_raw, label="published PDF")
    public_cover = safe_relative(project, public_cover_raw, label="published cover")
    if public_pdf == public_cover:
        raise ManualPdfError("Published PDF and cover paths must be different.")
    if Path(public_pdf_raw).name == Path(public_cover_raw).name:
        raise ManualPdfError("Published PDF and cover filenames must be different.")
    return {
        "build_dir": build_root,
        "pdf": build_root / Path(public_pdf_raw).name,
        "cover": build_root / Path(public_cover_raw).name,
        "source": build_root / "manual.md",
        "metadata": build_root / "metadata.yml",
        "bibliography": build_root / "bibliography.bib",
        "manifest": build_root / "manifest.json",
        "public_pdf": public_pdf,
        "public_cover": public_cover,
    }


def manual_sources(project: Path, config: dict[str, Any], lang: str) -> tuple[Path | None, list[tuple[Path, dict[str, Any], str]], str]:
    manual = nested(config, "unaltraweb", "manual")
    collection = str(manual.get("collection") or "chapters").strip()
    collection_root = safe_relative(project, f"_{collection}", label="manual collection", must_exist=True)
    default_lang = str(config.get("default_lang") or config.get("lang") or lang)

    pages: list[tuple[Path, dict[str, Any], str]] = []
    for path in sorted(collection_root.rglob("*")):
        if path.suffix.lower() not in {".md", ".markdown"} or not path.is_file():
            continue
        front, body = read_source(path)
        if front.get("pdf") is False:
            continue
        pages.append((path, front, body))

    selected = [item for item in pages if str(item[1].get("lang") or default_lang) == lang]
    if not selected:
        raise ManualPdfError(f"No manual chapters found for language '{lang}'.")

    def weight(item: tuple[Path, dict[str, Any], str]) -> tuple[float, str]:
        raw = item[1].get("weight", 0)
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            numeric = 0
        return numeric, str(item[0])

    selected.sort(key=weight)
    numbered = [item for item in selected if item[1].get("manual_numbered") is not False]
    references = [item for item in selected if item[1].get("manual_numbered") is False]

    home: Path | None = None
    home_candidates: list[Path] = []
    pages_root = project / "_pages"
    if pages_root.is_dir():
        for path in sorted(pages_root.rglob("*")):
            if path.suffix.lower() not in {".md", ".markdown"} or not path.is_file():
                continue
            front, _ = read_source(path)
            if front.get("layout") == "manual-home" and str(front.get("lang") or default_lang) == lang:
                home_candidates.append(path)
    if len(home_candidates) > 1:
        choices = ", ".join(str(path.relative_to(project)) for path in home_candidates)
        raise ManualPdfError(f"Multiple manual-home pages found for language '{lang}': {choices}")
    if home_candidates:
        home = home_candidates[0]
    return home, numbered + references, lang


def validate_capture_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ManualPdfError(f"Unsafe web capture SVG: {path}")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ManualPdfError(f"Invalid web capture SVG: {path}: {exc}") from exc
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag not in CAPTURE_SVG_ALLOWED_ELEMENTS:
            raise ManualPdfError(f"Unsupported web capture SVG element in {path}: {tag}")
        for raw_name, raw_value in element.attrib.items():
            name = raw_name.rsplit("}", 1)[-1].lower()
            value = raw_value.strip()
            lowered_value = value.lower()
            if name not in CAPTURE_SVG_ALLOWED_ATTRIBUTES:
                raise ManualPdfError(f"Unsupported web capture SVG attribute in {path}: {name}")
            if "@import" in lowered_value or "javascript:" in lowered_value or "expression(" in lowered_value:
                raise ManualPdfError(f"Unsafe web capture SVG attribute in {path}: {name}")
            if name == "href" and not (value.startswith("data:image/png;base64,") or value.startswith("#")):
                raise ManualPdfError(f"External web capture SVG reference in {path}")
            without_local_urls = re.sub(r"url\(\s*['\"]?#[A-Za-z_][-:.A-Za-z0-9_]*['\"]?\s*\)", "", lowered_value)
            if "url(" in without_local_urls:
                raise ManualPdfError(f"External CSS reference in web capture SVG: {path}")
            if name == "style":
                declarations = [part.strip() for part in value.split(";") if part.strip()]
                for declaration in declarations:
                    property_name, separator, _ = declaration.partition(":")
                    if not separator or property_name.strip().lower() not in CAPTURE_SVG_ALLOWED_STYLE_PROPERTIES:
                        raise ManualPdfError(f"Unsupported CSS property in web capture SVG {path}: {property_name.strip()}")


def commented_front_matter(path: Path, prefix: str) -> str:
    marker = f"{prefix} ---"
    active = False
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == marker:
            if active:
                return "\n".join(lines)
            active = True
            continue
        if active:
            if not line.startswith(prefix):
                break
            value = line[len(prefix):]
            lines.append(value[1:] if value.startswith(" ") else value)
    return ""


def computation_front_matter(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = ""
    if suffix in {".qmd", ".rmd"}:
        match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
        text = match.group(1) if match else ""
    elif suffix == ".r":
        text = commented_front_matter(path, "#'")
    elif suffix == ".py":
        text = commented_front_matter(path, "#")
    elif suffix == ".ipynb":
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManualPdfError(f"Invalid notebook JSON in computation source {path}: {exc}") from exc
        if not isinstance(notebook, dict):
            raise ManualPdfError(f"Computation notebook must contain a JSON object: {path}")
        metadata = notebook.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("unaltraweb_front_matter"), dict):
            return metadata["unaltraweb_front_matter"]
        for cell in notebook.get("cells", []):
            if not isinstance(cell, dict) or cell.get("cell_type") not in {"raw", "markdown"}:
                continue
            source = cell.get("source", "")
            cell_text = "".join(source) if isinstance(source, list) else str(source)
            match = FRONT_MATTER_RE.match(cell_text)
            text = match.group(1) if match else ""
            break
    if not text:
        return {}
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManualPdfError(f"Invalid computation front matter in {path}: {exc}") from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ManualPdfError(f"Computation front matter must be a YAML mapping: {path}")
    return parsed


def split_url_decoration(raw: str) -> tuple[str, str]:
    indexes = [index for token in ("?", "#") if (index := raw.find(token)) >= 0]
    if not indexes:
        return raw, ""
    index = min(indexes)
    return raw[:index], raw[index:]


def load_vega_manifest(project: Path) -> list[dict[str, str]]:
    project = project.resolve()
    manifest_path = project / VEGA_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ManualPdfError(f"Missing required Vega visualization manifest: {VEGA_MANIFEST_NAME}")
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ManualPdfError(f"Vega visualization manifest exceeds 1048576 bytes: {VEGA_MANIFEST_NAME}")
    try:
        text = manifest_path.read_text(encoding="utf-8")
        if any(isinstance(token, yaml.tokens.AliasToken) for token in yaml.scan(text)):
            raise ManualPdfError(f"YAML aliases are not allowed in {VEGA_MANIFEST_NAME}")
        manifest = yaml.load(text, Loader=UniqueKeySafeLoader)
    except ManualPdfError:
        raise
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ManualPdfError(f"Invalid Vega visualization manifest {VEGA_MANIFEST_NAME}: {exc}") from exc

    if not isinstance(manifest, dict):
        raise ManualPdfError(f"Vega visualization manifest must be a mapping: {VEGA_MANIFEST_NAME}")
    if type(manifest.get("version")) is not int or manifest.get("version") != 1:
        raise ManualPdfError("Vega visualization manifest version must be 1")
    for field in ("profile", "family"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ManualPdfError(f"Vega visualization manifest requires a {field}")
    visualizations = manifest.get("visualizations")
    if not isinstance(visualizations, list):
        raise ManualPdfError("Vega visualization manifest visualizations must be a list")

    names: set[str] = set()
    sources: set[str] = set()
    outputs: set[str] = set()
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(visualizations):
        if not isinstance(item, dict):
            raise ManualPdfError(f"Vega visualization at index {index} must be a mapping")
        name = item.get("name")
        if not isinstance(name, str) or not VEGA_SAFE_NAME_RE.fullmatch(name):
            raise ManualPdfError(f"Vega visualization at index {index} has an invalid name")
        if name in names:
            raise ManualPdfError(f"Duplicate Vega visualization name: {name}")
        source_raw = item.get("source")
        output_raw = item.get("output")
        if not isinstance(source_raw, str) or not source_raw:
            raise ManualPdfError(f"Vega visualization {name} requires a source")
        if not isinstance(output_raw, str) or not output_raw:
            raise ManualPdfError(f"Vega visualization {name} requires an output")

        source = safe_relative(project, source_raw, label=f"source for Vega visualization {name}", must_exist=True)
        output = safe_relative(project, output_raw, label=f"output for Vega visualization {name}")
        if not source.is_file():
            raise ManualPdfError(f"Source for Vega visualization {name} is not a file: {source_raw}")
        source_relative = source.relative_to(project).as_posix()
        output_relative = output.relative_to(project).as_posix()
        if source == output:
            raise ManualPdfError(f"Vega visualization {name} output cannot replace its source")
        if source_relative in sources:
            raise ManualPdfError(f"Duplicate Vega visualization source: {source_relative}")
        if output_relative in outputs:
            raise ManualPdfError(f"Duplicate Vega visualization output: {output_relative}")

        output_suffix = output.suffix.lower()
        if output_suffix not in VEGA_OUTPUT_SUFFIXES:
            raise ManualPdfError(f"Vega visualization {name} output must use .svg, .png, or .pdf")
        item_format = item.get("format")
        if item_format is not None and not isinstance(item_format, str):
            raise ManualPdfError(f"Vega visualization {name} format must be a string")
        if item_format and f".{item_format.strip().lower()}" != output_suffix:
            raise ManualPdfError(f"Vega visualization {name} output suffix does not match format {item_format}")
        if not isinstance(item.get("engine", "auto"), str):
            raise ManualPdfError(f"Vega visualization {name} engine must be a string")
        inputs = item.get("inputs", [])
        if not isinstance(inputs, list) or not all(isinstance(entry, str) and entry for entry in inputs):
            raise ManualPdfError(f"Vega visualization {name} inputs must be a list of paths")

        names.add(name)
        sources.add(source_relative)
        outputs.add(output_relative)
        normalized.append({"name": name, "source": source_relative, "output": output_relative})
    return normalized


def resolve_vega_source(project: Path, source_path: str) -> str:
    project = project.resolve()
    if REMOTE_PATH_RE.match(source_path):
        raise ManualPdfError(f"Vega visualization source must be a local project path: {source_path}")
    source = safe_relative(project, source_path, label="Vega visualization source", must_exist=True)
    if not source.is_file():
        raise ManualPdfError(f"Vega visualization source is not a file: {source_path}")
    source_relative = source.relative_to(project).as_posix()
    matches = [item for item in load_vega_manifest(project) if item["source"] == source_relative]
    if not matches:
        raise ManualPdfError(f"Vega visualization source is not declared in {VEGA_MANIFEST_NAME}: {source_relative}")
    if len(matches) > 1:
        raise ManualPdfError(f"Vega visualization source is ambiguous in {VEGA_MANIFEST_NAME}: {source_relative}")
    output_relative = matches[0]["output"]
    output = safe_relative(project, output_relative, label="Vega visualization output")
    if not output.is_file():
        raise ManualPdfError(f"Missing rendered Vega visualization output: {output_relative}")
    return output.relative_to(project).as_posix()


def localized_visual_source(
    project: Path,
    path: str,
    *,
    language: str = "",
    default_language: str = "",
    languages: list[str] | None = None,
) -> str:
    current = language.strip()
    default = default_language.strip()
    if not current or current == default:
        return path
    suffix = next((candidate for candidate in VISUAL_LOCALIZATION_SUFFIXES if path.lower().endswith(candidate)), "")
    if not suffix:
        return path
    stem = path[:-len(suffix)]
    configured = {str(value).strip().lower() for value in (languages or []) if str(value).strip()}
    configured.update({current.lower(), default.lower()})
    if any(stem.lower().endswith(f".{code}") for code in configured):
        return path
    localized = f"{stem}.{current}{suffix}"
    candidate = (project.resolve() / localized.lstrip("/")).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        return path
    return localized if candidate.is_file() else path


def resolve_visual_source(
    project: Path,
    raw_path: str,
    *,
    language: str = "",
    default_language: str = "",
    languages: list[str] | None = None,
) -> str:
    undecorated, _ = split_url_decoration(raw_path)
    if REMOTE_PATH_RE.match(undecorated):
        if undecorated.lower().endswith(VEGA_SOURCE_SUFFIXES):
            raise ManualPdfError(f"Vega visualization source must be a local project path: {undecorated}")
        return raw_path
    path = localized_visual_source(
        project,
        undecorated.lstrip("/"),
        language=language,
        default_language=default_language,
        languages=languages,
    )
    vega_path = path.lstrip("/")
    if vega_path.lower().endswith(VEGA_SOURCE_SUFFIXES):
        return resolve_vega_source(project, vega_path)
    path = path.lstrip("/")
    if path.lower().endswith((".capture.yml", ".capture.yaml")):
        source = safe_relative(project, path, label="web capture source", must_exist=True)
        base = str(source).rsplit(".", 1)[0]
        candidates = [Path(base + ".edited.svg"), Path(base + ".svg")]
        for candidate in candidates:
            if candidate.is_file():
                validate_capture_svg(candidate)
                return str(candidate.relative_to(project))
        raise ManualPdfError(f"No printable SVG found for web capture source: {path}")
    suffix = Path(path).suffix.lower()
    if suffix in COMPUTATION_SUFFIXES:
        source = safe_relative(project, path, label="computation figure source", must_exist=True)
        front = computation_front_matter(source)
        metadata = front.get("unaltraweb_compute")
        if not isinstance(metadata, dict) or str(metadata.get("mode") or "").strip().lower() != "figure":
            raise ManualPdfError(f"Computation source is not declared as unaltraweb_compute.mode: figure: {path}")
        outputs = metadata.get("outputs")
        if outputs is None and metadata.get("output"):
            outputs = [metadata["output"]]
        if not isinstance(outputs, list) or not outputs or not str(outputs[0] or "").strip():
            raise ManualPdfError(f"Figure computation source declares no outputs: {path}")
        output_raw = str(outputs[0]).strip()
        output = safe_relative(project, output_raw, label="computed figure output")
        if output.suffix.lower() not in GENERATED_MEDIA_SUFFIXES:
            raise ManualPdfError(f"Unsupported computed figure output type for {path}: {output_raw}")
        edited = output.with_suffix(".edited.svg")
        if edited.is_file():
            return str(edited.relative_to(project))
        if output.is_file():
            return str(output.relative_to(project))
        raise ManualPdfError(
            f"Missing rendered figure {output_raw} for computation source {path}. "
            "Run `make manual-compute-render-figures` before building the PDF."
        )
    if suffix not in DIAGRAM_SUFFIXES:
        return path
    source = safe_relative(project, path, label="diagram source", must_exist=True)
    candidates = [Path(str(source) + ".edited.svg"), Path(str(source) + ".svg")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.relative_to(project))
    raise ManualPdfError(f"No printable SVG found for diagram source: {path}")


def pandoc_image_attributes(raw: str) -> str:
    source = raw.strip()
    if not source:
        return ""
    source = source.removeprefix("{: ").removeprefix("{:").removesuffix("}").strip()
    source = source.translate({0x2018: ord("'"), 0x2019: ord("'"), 0x201C: ord('"'), 0x201D: ord('"')})
    dimensions: dict[str, str] = {}
    while dimension_match := FIGURE_DIMENSION_ATTR_RE.search(source):
        dimensions[dimension_match.group("name")] = next(
            value for value in dimension_match.group("double", "single", "bare") if value is not None
        ).strip()
        source = f"{source[:dimension_match.start()]} {source[dimension_match.end():]}".strip()

    width = dimensions.get("data-figure-width-pdf") or dimensions.get("data-figure-width") or ""
    height = dimensions.get("data-figure-height-pdf") or dimensions.get("data-figure-height") or ""
    rem_width = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)rem", width, re.IGNORECASE)
    if rem_width:
        percentage = min(100.0, float(rem_width.group(1)) / 60.0 * 100.0)
        width = f"{percentage:.4f}".rstrip("0").rstrip(".") + "%"
    rem_height = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)rem", height, re.IGNORECASE)
    if rem_height:
        height = f"{float(rem_height.group(1)) * 11.0:.4f}".rstrip("0").rstrip(".") + "pt"

    attributes = [
        value
        for value in (
            source,
            f"width={width}" if width else "",
            f"height={height}" if height else "",
        )
        if value
    ]
    return "{" + " ".join(attributes) + "}" if attributes else ""


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "%": r"\%",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def transform_markdown(
    project: Path,
    text: str,
    source: Path,
    language: str = "en",
    config: dict[str, Any] | None = None,
    citation_keys: list[str] | None = None,
) -> str:
    callout_labels, _ = resolve_callout_labels(project, config or {}, language)
    visual_default_language = str((config or {}).get("default_lang") or (config or {}).get("lang") or language)
    configured_visual_languages = (config or {}).get("languages")
    if not isinstance(configured_visual_languages, list):
        configured_visual_languages = [visual_default_language]
    token_prefix = "UNALTRAWEBMANUALPROTECTED"
    while token_prefix in text:
        token_prefix += "X"
    protected: list[str] = []

    def protect(value: str) -> str:
        token = f"{token_prefix}_{len(protected)}_"
        protected.append(value)
        return token

    protected_token_re = re.compile(rf"{re.escape(token_prefix)}_(\d+)_")

    def latex_caption(value: str) -> str:
        chunks: list[str] = []
        position = 0
        for token in protected_token_re.finditer(value):
            chunks.append(latex_escape(value[position:token.start()]))
            protected_value = protected[int(token.group(1))]
            inline_match = MARKDOWN_INLINE_CODE_RE.fullmatch(protected_value)
            if inline_match:
                fence_length = len(inline_match.group(1))
                code = protected_value[fence_length:-fence_length]
                chunks.append(r"\texttt{" + latex_escape(code) + "}")
            else:
                chunks.append(latex_escape(protected_value))
            position = token.end()
        chunks.append(latex_escape(value[position:]))
        return "".join(chunks)

    def citations(match: re.Match[str]) -> str:
        keys = [key.lstrip("@").strip() for key in match.group(1).split() if key.strip()]
        if citation_keys is not None:
            citation_keys.extend(key for key in keys if key not in citation_keys)
        return "[" + "; ".join(f"@{key}" for key in keys) + "]"

    def table(match: re.Match[str]) -> str:
        body = match.group(2).strip()
        rows = [
            re.sub(r"\s+", " ", line.strip().strip("|"))
            for line in body.splitlines()
            if "|" in line and not PIPE_TABLE_SEPARATOR_RE.fullmatch(line)
        ]
        estimated_lines = 2 + sum(max(1, (len(row) + 71) // 72) for row in rows)
        required_baselines = max(10, round(estimated_lines * 1.25) + 2)
        page_guard = r"\clearpage" if required_baselines >= 40 else f"\\Needspace{{{required_baselines}\\baselineskip}}"
        return (
            f"```{{=latex}}\n{page_guard}\n```\n\n"
            f"Table: {match.group(1).strip()}\n\n{body}"
        )

    def inline_code(match: re.Match[str]) -> str:
        value = html.unescape(match.group(1))
        longest_fence = max((len(run) for run in re.findall(r"`+", value)), default=0) + 1
        fence = "`" * longest_fence
        padding = " " if value.startswith("`") or value.endswith("`") else ""
        return f"{fence}{padding}{value}{padding}{fence}"

    def table_guard_before_heading(match: re.Match[str]) -> str:
        guard = match.group("guard")
        if match.group("baselines"):
            guard = f"\\Needspace{{{int(match.group('baselines')) + 6}\\baselineskip}}"
        return f"```{{=latex}}\n{guard}\n```\n\n{match.group('heading')}"

    def display_math(match: re.Match[str]) -> str:
        body = match.group("body").rstrip("\r\n")
        return f"\\begin{{equation}}\n{body}\n\\end{{equation}}"

    def image(match: re.Match[str]) -> str:
        alt = match.group("alt")
        raw_path = match.group("path")
        title = match.group("double_title") or match.group("single_title")
        printable = resolve_visual_source(
            project,
            raw_path,
            language=language,
            default_language=visual_default_language,
            languages=[str(value) for value in configured_visual_languages],
        )
        caption = title or alt
        attributes = pandoc_image_attributes(match.group("attrs") or "")
        return f"![{caption}]({printable}){attributes}"

    def callout(match: re.Match[str]) -> str:
        marks = match.group("marks")
        depth = min(len(marks), max(CALLOUT_STYLES))
        color, callout_type = CALLOUT_STYLES[depth]
        body = "\n".join(line[len(marks):].lstrip(" \t") for line in match.group("block").splitlines()).strip()
        if not body:
            raise ManualPdfError(f"Empty callout in {source.relative_to(project)}")
        estimated_lines = 2 + sum(
            max(1, (len(line.strip()) + 71) // 72)
            for line in body.splitlines()
            if line.strip()
        )
        options = "[enhanced,breakable]" if estimated_lines >= 40 else ""
        label = latex_escape(callout_labels[callout_type])
        return (
            "```{=latex}\n"
            f"\\begin{{manualcallout}}{options}{{{color}}}{{{label}}}\n"
            "```\n\n"
            f"{body}\n\n"
            "```{=latex}\n"
            "\\end{manualcallout}\n"
            "```"
        )

    def subfigures(match: re.Match[str]) -> str:
        def raw_latex_inline(value: str) -> str:
            fence = "`" * (max((len(run) for run in re.findall(r"`+", value)), default=0) + 1)
            padding = " " if value.startswith("`") or value.endswith("`") else ""
            return f"{fence}{padding}{value}{padding}{fence}{{=latex}}"

        images = list(IMAGE_RE.finditer(match.group("body")))
        if not images:
            raise ManualPdfError(f"Subfigures block contains no images in {source.relative_to(project)}")

        layout = match.group("layout") or ""
        row_sizes = [len([token for token in row.split("+") if token.strip()]) for row in layout.split("/") if row.strip()]
        if not row_sizes:
            row_sizes = [min(2, len(images))]
            while sum(row_sizes) < len(images):
                row_sizes.append(min(2, len(images) - sum(row_sizes)))
        if sum(row_sizes) != len(images):
            raise ManualPdfError(
                f"Subfigures layout '{layout}' declares {sum(row_sizes)} panels but contains {len(images)} images "
                f"in {source.relative_to(project)}"
            )

        overall_caption = latex_caption(match.group("caption") or "")
        figure_start = "```{=latex}\n\\begin{figure}[H]\n\\centering\n"
        if overall_caption:
            figure_start += (
                f"\\caption{{{overall_caption}}}\n"
                "{\\color{ManualMuted!45}\\rule{\\linewidth}{0.35pt}}\\par\\medskip\n"
            )
        rendered = [figure_start + "```"]
        image_index = 0
        max_image_height = f"{0.52 / len(row_sizes):.3f}".rstrip("0").rstrip(".")
        for row_index, row_size in enumerate(row_sizes):
            panel_width = {1: "0.92", 2: "0.48", 3: "0.31", 4: "0.23"}.get(row_size, f"{0.92 / row_size:.3f}")
            row: list[str] = []
            for column_index in range(row_size):
                item = images[image_index]
                image_index += 1
                caption = item.group("double_title") or item.group("single_title") or item.group("alt")
                printable = resolve_visual_source(
                    project,
                    item.group("path"),
                    language=language,
                    default_language=visual_default_language,
                    languages=[str(value) for value in configured_visual_languages],
                )
                attributes = pandoc_image_attributes(item.group("attrs") or "")
                row.extend([
                    raw_latex_inline(
                        f"\\begin{{subfigure}}[t]{{{panel_width}\\linewidth}}"
                        "\\centering"
                        f"\\def\\maxheight{{{max_image_height}\\textheight}}"
                    ),
                    f"![]({printable}){attributes}",
                ])
                separator = r"\hfill" if column_index < row_size - 1 else ""
                row.append(raw_latex_inline(
                    f"\\caption{{{latex_caption(caption)}}}"
                    f"\\end{{subfigure}}{separator}"
                ))
            rendered.append("".join(row))
            if row_index < len(row_sizes) - 1:
                rendered.append("```{=latex}\n\\par\\medskip\n```")

        rendered.append("```{=latex}\n\\end{figure}\n```")
        return "\n\n".join(rendered)

    transformed = FENCED_CODE_BLOCK_RE.sub(lambda match: protect(match.group(0)), text)
    transformed = MARKDOWN_INLINE_CODE_RE.sub(lambda match: protect(match.group(0)), transformed)
    transformed = INLINE_CODE_RE.sub(lambda match: protect(inline_code(match)), transformed)
    transformed = DISPLAY_MATH_BLOCK_RE.sub(display_math, transformed)
    transformed = transformed.replace(r"\begin{equation\*}", r"\begin{equation*}")
    transformed = transformed.replace(r"\end{equation\*}", r"\end{equation*}")
    transformed = BASEURL_RE.sub("", transformed)
    transformed = transformed.replace("{% include manual-bibliography.liquid %}", "::: {#refs}\n:::")
    transformed = CITE_RE.sub(citations, transformed)
    transformed = CALLOUT_BLOCK_RE.sub(callout, transformed)
    transformed = TABLE_DIV_RE.sub(table, transformed)
    transformed = TABLE_GUARD_AFTER_HEADING_RE.sub(table_guard_before_heading, transformed)
    transformed = SUBFIGURES_DIV_RE.sub(subfigures, transformed)
    transformed = IMAGE_RE.sub(image, transformed)
    if re.search(r"^:::\s*subfigures\b", transformed, re.MULTILINE):
        raise ManualPdfError(f"Malformed subfigures block in {source.relative_to(project)}")
    unknown_includes = [item for item in INCLUDE_RE.findall(transformed) if item.strip()]
    unknown_liquid = [item for item in LIQUID_RE.findall(transformed) if item.strip()]
    if unknown_includes or unknown_liquid:
        token = (unknown_includes or unknown_liquid)[0]
        raise ManualPdfError(f"Unsupported Liquid in {source.relative_to(project)}: {token}")
    for index in range(len(protected) - 1, -1, -1):
        transformed = transformed.replace(f"{token_prefix}_{index}_", protected[index])
    return transformed.strip()


def localized(value: Any, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("default") or next(iter(value.values()), ""))
    return str(value or "")


def build_metadata(project: Path, config: dict[str, Any], lang: str, source_lang: str, home_front: dict[str, Any], chapters: list[tuple[Path, dict[str, Any], str]]) -> dict[str, Any]:
    manual = nested(config, "unaltraweb", "manual")
    pdf = manual.get("pdf") if isinstance(manual.get("pdf"), dict) else {}
    metadata = manual.get("metadata") if isinstance(manual.get("metadata"), dict) else {}
    cover = pdf.get("cover") if isinstance(pdf.get("cover"), dict) else {}
    author = config.get("author") if isinstance(config.get("author"), dict) else {}
    instructors_raw = metadata.get("instructors")
    if isinstance(instructors_raw, list):
        instructors = [str(item.get("name") if isinstance(item, dict) else item) for item in instructors_raw]
    else:
        instructors = [localized(author.get(f"name_{source_lang}") or author.get("name"), source_lang)]
    instructors = [item for item in instructors if item]
    guides_raw = metadata.get("teaching_guides")
    teaching_guides: list[dict[str, str]] = []
    if isinstance(guides_raw, list):
        for item in guides_raw:
            if not isinstance(item, dict):
                continue
            degree = localized(item.get("degree"), source_lang)
            if degree:
                teaching_guides.append({"degree": degree, "subject-code": str(item.get("subject_code") or "")})
    if not teaching_guides:
        degree = localized(metadata.get("degree"), source_lang)
        if degree:
            teaching_guides.append({"degree": degree, "subject-code": str(metadata.get("subject_code") or "")})
    metadata_labels = METADATA_LABELS.get(source_lang, METADATA_LABELS["en"])
    unaltraweb = nested(config, "unaltraweb")
    status_field = str(unaltraweb.get("content_status_field") or "content_status")
    approved_status = str(unaltraweb.get("approved_status") or "approved")
    statuses = {str(front.get(status_field) or "") for _, front, _ in chapters}
    if home_front:
        statuses.add(str(home_front.get(status_field) or ""))
    draft = any(status != approved_status for status in statuses)

    def asset(raw: Any) -> str:
        if not raw:
            return ""
        return str(safe_relative(project, str(raw), label="cover asset", must_exist=True).relative_to(project))

    title = localized(metadata.get("title"), source_lang) or localized(home_front.get("title"), source_lang) or str(config.get("title") or "Manual")
    copyright_holder = str(config.get("copyright_holder") or "").strip()
    return {
        "title": title,
        "short-title": localized(metadata.get("short_title"), source_lang) or str(config.get("short_title") or title),
        "description": localized(metadata.get("description"), source_lang) or localized(home_front.get("description"), source_lang) or str(config.get("description") or ""),
        "author": ", ".join(instructors),
        "instructors": instructors,
        "series": localized(metadata.get("series"), source_lang) or "unaltremanual",
        "series-subtitle": localized(metadata.get("series_subtitle"), source_lang),
        "publisher": localized(metadata.get("publisher"), source_lang),
        "edition": localized(metadata.get("edition"), source_lang),
        "publication-date": localized(metadata.get("publication_date"), source_lang),
        "identifier": localized(metadata.get("identifier"), source_lang),
        "license": localized(metadata.get("license"), source_lang),
        "source": localized(metadata.get("source"), source_lang),
        "subject": localized(metadata.get("subject"), source_lang),
        "subject-code": str(metadata.get("subject_code") or ""),
        "degree": localized(metadata.get("degree"), source_lang),
        "teaching-guides": teaching_guides,
        "department": localized(metadata.get("department"), source_lang),
        "faculty": localized(metadata.get("faculty"), source_lang),
        "institution": localized(metadata.get("institution"), source_lang) or localized(author.get(f"affiliation_{source_lang}") or author.get("affiliation"), source_lang),
        "location": localized(metadata.get("location"), source_lang) or localized(author.get(f"location_{source_lang}") or author.get("location"), source_lang),
        "academic-year": str(metadata.get("academic_year") or ""),
        "revision-date": localized(metadata.get("revision_date"), source_lang),
        "rights": localized(metadata.get("rights"), source_lang) or (f"© {copyright_holder}" if copyright_holder else ""),
        "metadata-page-title": metadata_labels["title"],
        "metadata-series-label": metadata_labels["series"],
        "metadata-publisher-label": metadata_labels["publisher"],
        "metadata-edition-label": metadata_labels["edition"],
        "metadata-publication-date-label": metadata_labels["publication_date"],
        "metadata-subject-label": metadata_labels["subject"],
        "metadata-teaching-guides-label": metadata_labels["teaching_guides"],
        "metadata-academic-year-label": metadata_labels["academic_year"],
        "metadata-department-label": metadata_labels["department"],
        "metadata-faculty-label": metadata_labels["faculty"],
        "metadata-institution-label": metadata_labels["institution"],
        "metadata-location-label": metadata_labels["location"],
        "metadata-revision-date-label": metadata_labels["revision_date"],
        "metadata-instructors-label": metadata_labels["instructors"],
        "metadata-identifier-label": metadata_labels["identifier"],
        "metadata-license-label": metadata_labels["license"],
        "metadata-source-label": metadata_labels["source"],
        "metadata-rights-label": metadata_labels["rights"],
        "chapter-references-title": metadata_labels["references"],
        "lang": lang,
        "babel-lang": LANGUAGE_NAMES.get(source_lang, "english"),
        "toc": bool(pdf.get("toc", True)),
        "nocite": "@*" if manual.get("bibliography", True) and bool(pdf.get("include_bibliography", True)) else "",
        "link-citations": bool(pdf.get("link_citations", True)),
        "draft": draft and bool(pdf.get("mark_drafts", True)),
        "draft-label": localized(pdf.get("draft_label"), source_lang) or {"ca": "ESBORRANY", "es": "BORRADOR", "en": "DRAFT"}.get(source_lang, "DRAFT"),
        "draft-description": localized(pdf.get("draft_description"), source_lang) or {"ca": "Material en revisió. No és una versió final.", "es": "Material en revisión. No es una versión final.", "en": "Material under review. This is not a final version."}.get(source_lang, "Material under review."),
        "primary-color": str(cover.get("primary_color") or "990000").lstrip("#"),
        "band-color": str(cover.get("band_color") or cover.get("primary_color") or "990000").lstrip("#"),
        "secondary-color": str(cover.get("secondary_color") or "003366").lstrip("#"),
        "muted-color": str(cover.get("muted_color") or "666666").lstrip("#"),
        "internal-link-color": str(pdf.get("internal_link_color") or cover.get("secondary_color") or "003366").lstrip("#"),
        "external-link-color": str(pdf.get("external_link_color") or cover.get("primary_color") or "990000").lstrip("#"),
        "citation-link-color": str(pdf.get("citation_link_color") or "C2185B").lstrip("#"),
        "inline-code-color": str(pdf.get("inline_code_color") or "5A1F5F").lstrip("#"),
        "cover-image": asset(cover.get("image")),
        "cover-logo": asset(cover.get("institution_logo")),
        "series-logo": asset(cover.get("series_logo")),
    }


def assemble(project: Path, config: dict[str, Any], lang: str, paths: dict[str, Path]) -> tuple[dict[str, Any], list[Path], str]:
    manual = nested(config, "unaltraweb", "manual")
    pdf = manual.get("pdf") if isinstance(manual.get("pdf"), dict) else {}
    home, chapters, source_lang = manual_sources(project, config, lang)
    home_front: dict[str, Any] = {}
    chunks: list[str] = []
    _, callout_label_sources = resolve_callout_labels(project, config, source_lang)
    code_block_label, code_block_label_sources = resolve_code_block_label(project, config, source_lang)
    source_paths: list[Path] = list(dict.fromkeys([*callout_label_sources, *code_block_label_sources]))
    includes_home = bool(home and pdf.get("include_home", True))

    if includes_home:
        assert home is not None
        home_front, body = read_source(home)
        body = transform_markdown(project, body, home, source_lang, config)
        home_title = localized(pdf.get("home_title"), source_lang) or {"ca": "Inici i presentació del curs", "es": "Inicio y presentación del curso", "en": "Course introduction"}.get(source_lang, "Introduction")
        first_heading = re.compile(rf"^##\s+{re.escape(home_title)}\s*$", re.MULTILINE)
        body = first_heading.sub("", body, count=1).strip()
        chunks.append(f"# {home_title}\n\n{body}")
        source_paths.append(home)

    included_chapters: list[tuple[Path, dict[str, Any], str]] = []
    for path, front, body in chapters:
        is_bibliography = front.get("manual_bibliography") is True or str(front.get("ref") or "") == "manual-bibliography"
        if is_bibliography and not bool(pdf.get("include_bibliography", True)):
            continue
        title = str(front.get("title") or path.stem)
        heading = f"# {title}"
        if front.get("manual_numbered") is False:
            heading += " {-}"
        citation_keys: list[str] = []
        transformed_body = transform_markdown(project, body, path, source_lang, config, citation_keys)
        references_requested = bool(front.get("related_publications") or front.get("manual_references") or front.get("references"))
        if citation_keys and references_requested and manual.get("bibliography", True) is not False:
            marker = html.escape(",".join(citation_keys), quote=True)
            transformed_body += f'\n\n::: {{.manual-chapter-citations data-citations="{marker}"}}\n:::'
        chunks.append(f"{heading}\n\n{transformed_body}")
        included_chapters.append((path, front, body))
        source_paths.append(path)

    metadata = build_metadata(project, config, lang, source_lang, home_front, included_chapters)
    metadata["include-home"] = includes_home
    metadata["code-block-label"] = code_block_label
    return metadata, source_paths, "\n\n\\newpage\n\n".join(chunks) + "\n"


def bibliography_source(project: Path, config: dict[str, Any]) -> Path | None:
    manual = nested(config, "unaltraweb", "manual")
    if manual.get("bibliography", True) is False:
        return None
    filename = str(manual.get("bibliography_file") or "manual.bib").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.bib", filename) or Path(filename).name != filename:
        raise ManualPdfError("unaltraweb.manual.bibliography_file must be a .bib filename under _bibliography/.")
    return safe_relative(project, f"_bibliography/{filename}", label="bibliography", must_exist=True)


def clean_bibliography(source: Path | None, destination: Path) -> None:
    if source is None:
        return
    text = source.read_text(encoding="utf-8")
    text = FRONT_MATTER_RE.sub("", text, count=1)
    destination.write_text(text, encoding="utf-8")


def bibliography_custom_urls(text: str) -> dict[str, list[str]]:
    matches = list(BIB_ENTRY_HEADER_RE.finditer(text))
    urls: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        values = [(custom.group(1) or custom.group(2)).strip() for custom in BIB_CUSTOM_URL_RE.finditer(text, match.end(), end)]
        if values:
            urls[match.group(1)] = list(dict.fromkeys(values))
    return urls


def fold_bibliography_value(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(character for character in decomposed if not unicodedata.combining(character)).split())


def contributor_sort_value(record: dict[str, Any]) -> str:
    contributors: Any = []
    for field in ("author", "editor", "collection-editor", "translator"):
        if isinstance(record.get(field), list) and record[field]:
            contributors = record[field]
            break
    values: list[str] = []
    for contributor in contributors:
        if not isinstance(contributor, dict):
            continue
        literal = str(contributor.get("literal") or "").strip()
        if literal:
            values.append(literal)
            continue
        family = str(contributor.get("family") or "").strip()
        given = str(contributor.get("given") or "").strip()
        values.append(", ".join(part for part in (family, given) if part))
    if values:
        return "; ".join(values)
    return str(record.get("publisher") or record.get("container-title") or record.get("title") or "")


def normalize_doi(value: Any) -> str:
    return re.sub(r"(?i)^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(value or "").strip()).rstrip("/")


def bibliography_filter_metadata(records: Any, custom_urls: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        raise ManualPdfError("Pandoc returned invalid CSL bibliography data.")
    sort_keys: dict[str, str] = {}
    access: dict[str, dict[str, str]] = {}
    for record in records:
        if not isinstance(record, dict) or not str(record.get("id") or "").strip():
            continue
        key = str(record["id"]).strip()
        issued = record.get("issued") if isinstance(record.get("issued"), dict) else {}
        date_parts = issued.get("date-parts") if isinstance(issued, dict) else []
        year = ""
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            year = str(date_parts[0][0])
        sort_keys[key] = " | ".join(
            fold_bibliography_value(value)
            for value in (contributor_sort_value(record), year, record.get("title"), key)
        )
        doi = normalize_doi(record.get("DOI") or record.get("doi"))
        standard_url = str(record.get("URL") or record.get("url") or "").strip()
        urls = list(dict.fromkeys(url for url in [standard_url, *custom_urls.get(key, [])] if url))
        normalized_doi = doi.casefold()
        if normalized_doi:
            urls = [
                url
                for url in urls
                if re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", url).rstrip("/").casefold() != normalized_doi
            ]
        if doi or urls:
            access[key] = {"doi": doi, "urls": urls}
    return {"bibliography-sort-keys": sort_keys, "bibliography-access": access}


def extract_bibliography_metadata(source: Path, destination: Path, project: Path) -> dict[str, dict[str, Any]]:
    csl_json = destination.with_suffix(".json")
    run_command(
        [
            "pandoc",
            str(destination),
            "--from=biblatex",
            "--to=csljson",
            f"--output={csl_json}",
        ],
        project,
    )
    try:
        records = json.loads(csl_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualPdfError(f"Could not read Pandoc CSL bibliography data: {exc}") from exc
    metadata = bibliography_filter_metadata(records, bibliography_custom_urls(source.read_text(encoding="utf-8")))
    for record in records:
        if not isinstance(record, dict):
            continue
        doi = normalize_doi(record.get("DOI") or record.get("doi"))
        if doi:
            record["DOI"] = doi
            record.pop("doi", None)
            url = str(record.get("URL") or record.get("url") or "").strip()
            if normalize_doi(url).casefold() == doi.casefold() and re.match(r"(?i)^https?://(?:dx\.)?doi\.org/", url):
                record.pop("URL", None)
                record.pop("url", None)
    csl_json.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def configured_template(project: Path, config: dict[str, Any]) -> Path:
    pdf = nested(config, "unaltraweb", "manual", "pdf")
    template_raw = str(pdf.get("template") or "").strip()
    return safe_relative(project, template_raw, label="PDF template", must_exist=True) if template_raw else DEFAULT_TEMPLATE


def configured_csl(project: Path, config: dict[str, Any], bibliography: Path | None) -> Path | None:
    if bibliography is None:
        return None
    pdf = nested(config, "unaltraweb", "manual", "pdf")
    csl_raw = str(pdf.get("csl") or "").strip()
    return safe_relative(project, csl_raw, label="CSL file", must_exist=True) if csl_raw else None


def build_dependencies(project: Path, metadata: dict[str, Any], source_paths: list[Path], markdown: str, template: Path, csl: Path | None) -> list[tuple[str, Path]]:
    dependencies: list[tuple[str, Path]] = [
        ("config:_config.yml", project / "_config.yml"),
        ("builder:build_pdf.py", Path(__file__).resolve()),
        ("toolchain:Dockerfile", DEFAULT_DOCKERFILE),
        (f"template:{template.name}", template),
        ("filter:bibliography.lua", DEFAULT_BIBLIOGRAPHY_FILTER),
        ("filter:code-blocks.lua", DEFAULT_CODE_BLOCK_FILTER),
        ("filter:figure-captions.lua", DEFAULT_FIGURE_FILTER),
    ]
    for path in source_paths:
        dependencies.append((f"source:{path.relative_to(project)}", path))
    if csl:
        dependencies.append((f"csl:{csl.relative_to(project)}", csl))
    for key in ["cover-image", "cover-logo", "series-logo"]:
        if metadata.get(key):
            path = safe_relative(project, str(metadata[key]), label=key, must_exist=True)
            dependencies.append((f"asset:{path.relative_to(project)}", path))
    dependency_markdown = FENCED_CODE_BLOCK_RE.sub("", markdown)
    dependency_markdown = MARKDOWN_INLINE_CODE_RE.sub("", dependency_markdown)
    for match in IMAGE_RE.finditer(dependency_markdown):
        raw = match.group("path")
        if raw.startswith(("http://", "https://", "data:", "#")):
            continue
        local_path, _ = split_url_decoration(raw)
        path = safe_relative(project, local_path, label="manual image", must_exist=True)
        dependencies.append((f"asset:{path.relative_to(project)}", path))
    unique: dict[str, Path] = {}
    for label, path in dependencies:
        unique[label] = path
    return sorted(unique.items())


def dependency_fingerprint(dependencies: list[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for label, path in dependencies:
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_signature(path: Path) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": path.stat().st_size}


def prepare_build(project: Path, config: dict[str, Any], lang: str) -> tuple[dict[str, Any], list[Path], str, Path, Path | None, Path | None, list[tuple[str, Path]], str]:
    metadata, source_paths, markdown = assemble(project, config, lang, artifact_paths(project, config, lang))
    bibliography = bibliography_source(project, config)
    if bibliography:
        source_paths.append(bibliography)
    template = configured_template(project, config)
    csl = configured_csl(project, config, bibliography)
    dependencies = build_dependencies(project, metadata, source_paths, markdown, template, csl)
    fingerprint = dependency_fingerprint(dependencies)
    metadata["trailer-id"] = fingerprint[:32]
    return metadata, source_paths, markdown, template, bibliography, csl, dependencies, fingerprint


def paths_in_build_dir(paths: dict[str, Path], build_dir: Path) -> dict[str, Path]:
    staged = dict(paths)
    staged["build_dir"] = build_dir
    for key in ["pdf", "cover", "source", "metadata", "bibliography", "manifest"]:
        staged[key] = build_dir / paths[key].name
    return staged


def run_command(command: list[str], project: Path) -> None:
    environment = os.environ.copy()
    environment.update({"SOURCE_DATE_EPOCH": REPRODUCIBLE_BUILD_EPOCH, "FORCE_SOURCE_DATE": "1", "TZ": "UTC"})
    completed = subprocess.run(
        command,
        cwd=project,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ManualPdfError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}")


def build_language(project: Path, config: dict[str, Any], lang: str) -> dict[str, Any]:
    paths = artifact_paths(project, config, lang)
    paths["build_dir"].parent.mkdir(parents=True, exist_ok=True)
    paths["manifest"].unlink(missing_ok=True)
    metadata, source_paths, markdown, template, bibliography, csl, dependencies, fingerprint = prepare_build(project, config, lang)

    with tempfile.TemporaryDirectory(prefix=f".{lang}-", dir=paths["build_dir"].parent) as temporary:
        staged = paths_in_build_dir(paths, Path(temporary))
        staged["source"].write_text(markdown, encoding="utf-8")
        clean_bibliography(bibliography, staged["bibliography"])
        if bibliography:
            metadata.update(extract_bibliography_metadata(bibliography, staged["bibliography"], project))
        staged["metadata"].write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8")
        command = [
            "pandoc",
            str(staged["source"]),
            "--from=markdown+fenced_divs+pipe_tables+link_attributes",
            "--standalone",
            "--top-level-division=chapter",
            "--number-sections",
            "--highlight-style=pygments",
            f"--metadata-file={staged['metadata']}",
            f"--template={template}",
            "--pdf-engine=xelatex",
            f"--resource-path={project}:{staged['build_dir']}",
            f"--output={staged['pdf']}",
        ]
        if bibliography:
            command.extend(["--citeproc", f"--bibliography={staged['bibliography'].with_suffix('.json')}"])
            if csl:
                command.append(f"--csl={csl}")
            command.append(f"--lua-filter={DEFAULT_BIBLIOGRAPHY_FILTER}")
        command.append(f"--lua-filter={DEFAULT_CODE_BLOCK_FILTER}")
        command.append(f"--lua-filter={DEFAULT_FIGURE_FILTER}")
        run_command(command, project)
        normalized_pdf = staged["pdf"].with_suffix(".normalized.pdf")
        run_command(
            [
                "qpdf",
                "--deterministic-id",
                "--object-streams=generate",
                "--recompress-flate",
                "--compression-level=9",
                str(staged["pdf"]),
                str(normalized_pdf),
            ],
            project,
        )
        os.replace(normalized_pdf, staged["pdf"])
        cover_prefix = staged["cover"].with_suffix("")
        run_command(["pdftoppm", "-f", "1", "-singlefile", "-png", "-r", "150", str(staged["pdf"]), str(cover_prefix)], project)
        manifest = {
            "language": lang,
            "built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "draft": metadata["draft"],
            "fingerprint": fingerprint,
            "dependencies": [label for label, _ in dependencies],
            "source_files": [str(path.relative_to(project)) for path in source_paths],
            "pdf": str(paths["pdf"].relative_to(project)),
            "cover": str(paths["cover"].relative_to(project)),
            "public_pdf": str(paths["public_pdf"].relative_to(project)),
            "public_cover": str(paths["public_cover"].relative_to(project)),
            "artifacts": {
                "pdf": file_signature(staged["pdf"]),
                "cover": file_signature(staged["cover"]),
            },
        }
        staged["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        previous: Path | None = None
        if paths["build_dir"].exists():
            previous = Path(tempfile.mkdtemp(prefix=f".{lang}-previous-", dir=paths["build_dir"].parent))
            previous.rmdir()
            os.replace(paths["build_dir"], previous)
        try:
            os.replace(staged["build_dir"], paths["build_dir"])
        except OSError:
            if previous and previous.exists():
                os.replace(previous, paths["build_dir"])
            raise
        if previous and previous.exists():
            shutil.rmtree(previous)
    return manifest


def status_language(project: Path, config: dict[str, Any], lang: str) -> dict[str, Any]:
    paths = artifact_paths(project, config, lang)
    manifest: dict[str, Any] = {}
    try:
        _, source_files, _, _, _, _, _, fingerprint = prepare_build(project, config, lang)
        source_lang = lang
        error = ""
    except ManualPdfError as exc:
        source_lang = lang
        source_files = []
        fingerprint = ""
        error = str(exc)
    if paths["manifest"].is_file():
        try:
            loaded = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            manifest = {}
    expected = {
        "language": lang,
        "fingerprint": fingerprint,
        "pdf": str(paths["pdf"].relative_to(project)),
        "cover": str(paths["cover"].relative_to(project)),
        "public_pdf": str(paths["public_pdf"].relative_to(project)),
        "public_cover": str(paths["public_cover"].relative_to(project)),
    }
    manifest_valid = bool(manifest) and all(manifest.get(key) == value for key, value in expected.items())
    generated_pdf_exists = paths["pdf"].is_file()
    generated_cover_exists = paths["cover"].is_file()
    expected_artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    artifacts_valid = (
        generated_pdf_exists
        and generated_cover_exists
        and expected_artifacts.get("pdf") == file_signature(paths["pdf"])
        and expected_artifacts.get("cover") == file_signature(paths["cover"])
    )
    ready = not error and manifest_valid and artifacts_valid
    published_current = (
        ready
        and paths["public_pdf"].is_file()
        and paths["public_cover"].is_file()
        and paths["public_pdf"].read_bytes() == paths["pdf"].read_bytes()
        and paths["public_cover"].read_bytes() == paths["cover"].read_bytes()
    )
    return {
        "language": lang,
        "source_language": source_lang,
        "source_count": len(source_files),
        "generated_pdf": str(paths["pdf"].relative_to(project)),
        "generated_pdf_exists": generated_pdf_exists,
        "generated_cover": str(paths["cover"].relative_to(project)),
        "generated_cover_exists": generated_cover_exists,
        "published_pdf": str(paths["public_pdf"].relative_to(project)),
        "published_pdf_exists": paths["public_pdf"].is_file(),
        "published_cover": str(paths["public_cover"].relative_to(project)),
        "published_cover_exists": paths["public_cover"].is_file(),
        "manifest_valid": manifest_valid,
        "artifacts_valid": artifacts_valid,
        "fresh": ready,
        "ready_to_publish": ready,
        "published_current": published_current,
        "error": error,
    }


def stage_copy(source: Path, destination: Path, suffix: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=suffix, dir=destination.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as origin:
            shutil.copyfileobj(origin, target)
        shutil.copystat(source, temporary)
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def publish_language(project: Path, config: dict[str, Any], lang: str, dry_run: bool) -> dict[str, Any]:
    paths = artifact_paths(project, config, lang)
    status = status_language(project, config, lang)
    if not status["ready_to_publish"]:
        raise ManualPdfError(f"Build language '{lang}' successfully after the latest source or configuration change before publishing it.")
    for destination in [paths["public_pdf"], paths["public_cover"]]:
        if destination.exists() and not destination.is_file():
            raise ManualPdfError(f"Publication destination is not a regular file: {destination.relative_to(project)}")
    operations = [
        {"source": str(paths["pdf"].relative_to(project)), "destination": str(paths["public_pdf"].relative_to(project))},
        {"source": str(paths["cover"].relative_to(project)), "destination": str(paths["public_cover"].relative_to(project))},
    ]
    if not dry_run:
        pairs = [(paths["pdf"], paths["public_pdf"]), (paths["cover"], paths["public_cover"])]
        staged: list[tuple[Path, Path]] = []
        try:
            for source, destination in pairs:
                staged.append((stage_copy(source, destination, ".tmp"), destination))
        except BaseException:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            raise
        backups: list[tuple[Path | None, Path]] = []
        try:
            for _, destination in staged:
                backup = stage_copy(destination, destination, ".backup") if destination.is_file() else None
                backups.append((backup, destination))
            for temporary, destination in staged:
                os.replace(temporary, destination)
        except BaseException:
            for backup, destination in backups:
                if backup and backup.exists():
                    os.replace(backup, destination)
                else:
                    destination.unlink(missing_ok=True)
            raise
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            for backup, _ in backups:
                if backup:
                    backup.unlink(missing_ok=True)
    return {"language": lang, "dry_run": dry_run, "operations": operations}


def sync_language(project: Path, config: dict[str, Any], lang: str) -> dict[str, Any]:
    status = status_language(project, config, lang)
    built = False
    published = False
    if not status["ready_to_publish"]:
        build_language(project, config, lang)
        built = True
        status = status_language(project, config, lang)
    if not status["published_current"]:
        publish_language(project, config, lang, False)
        published = True
    return {
        "language": lang,
        "state": "updated" if built or published else "current",
        "built": built,
        "published": published,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unaltraweb-manual-pdf")
    parser.add_argument("command", choices=["status", "check", "build", "publish", "sync"])
    parser.add_argument("--project", default=".")
    parser.add_argument("--language", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    try:
        config = read_yaml(project / "_config.yml")
        pdf = nested(config, "unaltraweb", "manual", "pdf")
        languages = language_list(config, pdf, args.language)
        if args.command == "sync" and not bool(pdf.get("enabled", False)):
            print(json.dumps({"project": str(project), "ok": True, "enabled": False, "skipped": True}, ensure_ascii=False, indent=2))
            return 0
        if args.command not in {"status", "check"} and not bool(pdf.get("enabled", False)):
            raise ManualPdfError("Manual PDF generation is disabled in unaltraweb.manual.pdf.enabled.")
        if args.command in {"status", "check"}:
            payload: dict[str, Any] = {
                "project": str(project),
                "enabled": bool(pdf.get("enabled", False)),
                "languages": [status_language(project, config, lang) for lang in languages],
            }
            payload["configuration_ok"] = payload["enabled"] and all(not item["error"] for item in payload["languages"])
            payload["ready_to_publish"] = payload["configuration_ok"] and all(item["ready_to_publish"] for item in payload["languages"])
            payload["published_current"] = payload["configuration_ok"] and all(item["published_current"] for item in payload["languages"])
            payload["ok"] = payload["published_current"] if args.command == "check" else payload["ready_to_publish"]
        elif args.command == "build":
            results = [build_language(project, config, lang) for lang in languages]
            payload = {"project": str(project), "ok": True, "built": results}
        elif args.command == "publish":
            results = [publish_language(project, config, lang, args.dry_run) for lang in languages]
            payload = {"project": str(project), "ok": True, "dry_run": args.dry_run, "published": results}
        else:
            results = [sync_language(project, config, lang) for lang in languages]
            payload = {"project": str(project), "ok": True, "synced": results}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    except (ManualPdfError, OSError, yaml.YAMLError) as exc:
        print(json.dumps({"project": str(project), "ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
