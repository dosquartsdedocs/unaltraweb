from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional local dependency
    yaml = None


CONTENT_DIRS = [
    "_pages",
    "_posts",
    "_news",
    "_projects",
    "_outputs",
    "_chapters",
    "_documentation",
    "_books",
    "_theses",
]
COMPUTATION_SUFFIXES = {".qmd", ".rmd", ".r", ".py", ".ipynb"}
DIAGRAM_SOURCE_SUFFIXES = {".mmd", ".mermaid", ".puml", ".plantuml", ".uml"}
MANUAL_PDF_BODY_FONT_POINTS = 11.0
MANUAL_PDF_TEXT_WIDTH_POINTS = 462.0
DIAGRAM_PDF_FONT_MIN_POINTS = 8.0
DIAGRAM_PDF_FONT_MAX_POINTS = 11.0
DIAGRAM_PDF_HEIGHT_MAX_POINTS = 600.0
MANUAL_WEB_ROOT_FONT_PIXELS = 16.0
MANUAL_WEB_BODY_FONT_PIXELS = 16.32
MANUAL_WEB_TEXT_WIDTH_PIXELS = 920.0
FIGURE_WEB_FONT_MIN_PIXELS = MANUAL_WEB_BODY_FONT_PIXELS * 0.75
FIGURE_WEB_FONT_MAX_PIXELS = MANUAL_WEB_BODY_FONT_PIXELS
VEGA_SOURCE_SUFFIXES = (".vl.json", ".vg.json")
WEB_CAPTURE_SUFFIXES = (".capture.yml", ".capture.yaml")
PROMPT_SPECS: dict[str, dict[str, Any]] = {
    "start_site_session": {
        "source": "00-start-site-session.txt",
        "description": "Start or resume work in an unaltraweb website workspace.",
        "arguments": [],
    },
    "create_new_web": {
        "source": "05-create-new-web.txt",
        "description": "Create a fresh website safely from a package-owned profile scaffold.",
        "arguments": [{"name": "site_profile", "type": "string", "default": "unaltreselfie"}],
    },
    "content_update": {
        "source": "10-content-update.txt",
        "description": "Update one page, post, news item, project, output, or structured data file.",
        "arguments": [{"name": "target", "type": "string", "default": "next content item"}],
    },
    "edit_default_content": {
        "source": "15-edit-default-content.txt",
        "description": "Draft, revise, and approve content in the configured default language before localization.",
        "arguments": [{"name": "target", "type": "string", "default": "default-language content item"}],
    },
    "manual_teaching_materials": {
        "source": "20-manual-teaching-materials.txt",
        "description": "Create or revise teaching/manual content for unaltremanual sites.",
        "arguments": [{"name": "target", "type": "string", "default": "manual chapter or teaching resource"}],
    },
    "manual_style_audit": {
        "source": "22-manual-style-audit.txt",
        "description": "Audit unaltremanual prose for pedagogical flow, technical precision, and local style.",
        "arguments": [{"name": "target", "type": "string", "default": "manual chapter or teaching resource"}],
    },
    "manual_structure_audit": {
        "source": "23-manual-structure-audit.txt",
        "description": "Audit section and paragraph functions against reader goals and tasks.",
        "arguments": [
            {"name": "target", "type": "string", "default": "whole manual"},
            {"name": "revision_mode", "type": "string", "default": "report only"},
        ],
    },
    "translation_prepublish": {
        "source": "25-translation-prepublish.txt",
        "description": "Prepare approved default-language content for translation shortly before publication.",
        "arguments": [{"name": "target_language", "type": "string", "default": ""}],
    },
    "project_site_update": {
        "source": "30-project-site-update.txt",
        "description": "Update research project content, outputs, repositories, team data, or news.",
        "arguments": [{"name": "target", "type": "string", "default": "project site section"}],
    },
    "documentation_update": {
        "source": "40-documentation-update.txt",
        "description": "Update technical or operational documentation.",
        "arguments": [{"name": "target", "type": "string", "default": "documentation page"}],
    },
    "bibliography_entry": {
        "source": "50-bibliography-entry.txt",
        "description": "Add or revise bibliography entries without inventing metadata.",
        "arguments": [{"name": "source", "type": "string", "default": "verified source metadata"}],
    },
    "bibliometrics_refresh": {
        "source": "60-bibliometrics-refresh.txt",
        "description": "Check and update static bibliometrics data.",
        "arguments": [],
    },
    "build_and_review": {
        "source": "70-build-and-review.txt",
        "description": "Build the site and review local rendered output or a running preview.",
        "arguments": [{"name": "site_profile", "type": "string", "default": ""}],
    },
}
RASTER_VISUAL_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".tiff", ".webp"}
VISUAL_LOCALIZATION_SUFFIXES = tuple(sorted({
    ".capture.edited.svg", ".capture.yaml", ".capture.yml", ".capture.svg",
    ".mermaid.edited.svg", ".mermaid.svg", ".plantuml.edited.svg", ".plantuml.svg",
    ".mmd.edited.svg", ".mmd.svg", ".puml.edited.svg", ".puml.svg", ".uml.edited.svg", ".uml.svg",
    ".vl.json", ".vg.json", ".edited.svg",
    ".qmd", ".rmd", ".ipynb", ".mermaid", ".plantuml", ".mmd", ".puml", ".uml", ".py", ".r",
    ".jpeg", ".tiff", ".webp", ".gif", ".jpg", ".png", ".svg", ".pdf",
}, key=len, reverse=True))

TRANSLATABLE_CONTENT_DIRS = {
    "_pages",
    "_posts",
    "_news",
    "_projects",
    "_outputs",
    "_chapters",
    "_documentation",
}

BIB_ENTRY_RE = re.compile(r"(?m)^@(\w+)\s*\{\s*([^,\s]+)")
DATE_RE = re.compile(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b")
POST_LANG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-([a-z]{2,3})-")
DEFAULT_STATUS_FIELD = "content_status"
DEFAULT_APPROVED_VALUE = "approved"
MARKDOWN_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
DIAGRAM_FENCE_RE = re.compile(r"^\s*(```|~~~)\s*(mermaid|plantuml|puml|uml)\b", re.IGNORECASE)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\n]+)\)")
STANDALONE_BOLD_LABEL_RE = re.compile(r"^\s*\*\*[^*\n]+\.\*\*\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
LEARNING_OBJECTIVE_CALLOUT_RE = re.compile(r"^>{5}(?!>)\s*(.*)$")
FIGURE_DIMENSION_RE = re.compile(
    r'''(?:\A|\s)(?P<name>data-figure-(?:width|height)(?:-(?:web|pdf))?)\s*=\s*'''
    r'''(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s}]+))''',
    re.IGNORECASE,
)
SVG_VIEWBOX_RE = re.compile(r'''\bviewBox=["']([^"']+)["']''', re.IGNORECASE)
SVG_CSS_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([0-9]+(?:\.[0-9]+)?)(px|pt|rem)?", re.IGNORECASE)
SVG_ATTRIBUTE_FONT_SIZE_RE = re.compile(r'''font-size=["']([0-9]+(?:\.[0-9]+)?)(px|pt|rem)?["']''', re.IGNORECASE)
MANUAL_EDITORIAL_RULES = [
    (
        "workflow_status",
        re.compile(r"\b(?:content_status|translation_status|needs_review|TODO|FIXME|TBD)\b", re.IGNORECASE),
        "Remove internal workflow states and task markers from publishable prose.",
    ),
    (
        "editorial_scaffolding",
        re.compile(
            r"\b(?:estat editorial|estado editorial|editorial status|nota d['’]edici[oó]|nota de edici[oó]n|editorial note|draft notes?|pendent (?:de|d['’]) (?:redacci[oó]|revisi[oó]|aprovaci[oó]|traducci[oó])|pending (?:writing|review|approval|translation))\b",
            re.IGNORECASE,
        ),
        "Move editorial planning and approval notes out of the manual body.",
    ),
    (
        "author_instruction_reference",
        re.compile(
            r"(?:\b(?:tal com|com)\s+(?:m['’]has|ens has|has)\s+(?:demanat|indicat|dit)\b|\b(?:segons|d['’]acord amb)\s+(?:les\s+)?teves instruccions\b|\b(?:l['’]usuari|la usuària|la persona usuària)\s+(?:ha|vol|demana|indica)\b|\b(?:como|tal como)\s+(?:me|nos)\s+has\s+(?:pedido|indicado|dicho)\b|\bseg[uú]n tus instrucciones\b|\bel usuario\s+(?:ha|quiere|pide|indica)\b|\b(?:as requested|per your instructions|the user\s+(?:asked|wants|requested))\b)",
            re.IGNORECASE,
        ),
        "Rewrite references to the author, user, or their instructions as standalone publishable content.",
    ),
    (
        "assistant_conversation",
        re.compile(
            r"\b(?:aqu[ií] tens|aqu[ií] tienes|here (?:is|are)|he afegit|hem afegit|he canviat|hem canviat|he añadido|hemos añadido|i have added|i['’]ve added|si vols|si quieres|if you want|puc afegir|puedo añadir|i can add)\b",
            re.IGNORECASE,
        ),
        "Remove assistant-style conversational framing from the manual body.",
    ),
    (
        "author_note",
        re.compile(
            r"\b(?:nota per a l['’]autor|nota para el autor|note to the author|instruccions? per a l['’](?:autor|agent)|instrucciones? para el (?:autor|agente)|instructions? for the (?:author|agent))\b",
            re.IGNORECASE,
        ),
        "Keep author and agent instructions in context files, not publishable manual prose.",
    ),
    (
        "placeholder",
        re.compile(r"(?:\[\s*(?:pendent|todo|tbd)[^\]]*\]|<insert[^>]*>|\b(?:afegir|inserir) (?:aqu[ií]|ac[ií])\b)", re.IGNORECASE),
        "Replace editorial placeholders with final prose or remove them.",
    ),
    (
        "draft_process_language",
        re.compile(
            r"\b(?:en aquest esborrany|en este borrador|in this draft|aquesta versi[oó] provisional|esta versi[oó]n provisional|this provisional version|(?:la versi[oó] catalana|la versi[oó] castellana|the (?:Catalan|Spanish|English) version) (?:[ée]s la font de treball|es la fuente de trabajo|is the working source))\b",
            re.IGNORECASE,
        ),
        "Remove drafting and localization-process language from reader-facing content.",
    ),
]

PROFILE_CONTRACTS: dict[str, dict[str, Any]] = {
    "unaltreselfie": {
        "description": "Personal academic or professional site.",
        "recommended_paths": ["_pages", "_bibliography", "_projects"],
        "config_keys": ["author"],
        "content_notes": ["profile pages", "posts/news", "projects", "publications", "CV assets"],
    },
    "unaltreprojecte": {
        "description": "Research project, group, infrastructure, or output site.",
        "recommended_paths": ["_pages", "_outputs", "_projects", "_data/team.yml"],
        "config_keys": [],
        "content_notes": ["project landing pages", "team data", "outputs", "repositories", "news"],
    },
    "unaltremanual": {
        "description": "Book-like manual, course, or teaching site.",
        "recommended_paths": ["_chapters", "_bibliography"],
        "config_keys": ["unaltraweb.manual"],
        "content_notes": ["localized chapters", "manual home", "figures/tables", "teaching blocks", "manual bibliography", "local writing policy"],
    },
    "unaltredocs": {
        "description": "Technical or operational documentation portal.",
        "recommended_paths": ["_documentation"],
        "config_keys": ["unaltraweb.documentation"],
        "content_notes": ["documentation home", "sectioned documentation", "reader profiles", "search"],
    },
}

SCAFFOLD_TEMPLATE_FILES = {"_config.yml.tmpl", "home.md.tmpl"}
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def project_path(raw: str | Path | None) -> Path:
    return Path(raw or os.getcwd()).expanduser().resolve()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _strip_inline_comment(value: str) -> str:
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


def _parse_scalar(value: str) -> Any:
    value = _strip_inline_comment(value)
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _fallback_config_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, data)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value:
            parent[key] = _parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return data


def load_yaml_text(text: str) -> Any:
    if yaml is not None:
        parsed = yaml.safe_load(text)
        return parsed if parsed is not None else {}
    return _fallback_config_yaml(text)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed = load_yaml_text(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def read_front_matter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    parsed = load_yaml_text(parts[1])
    return parsed if isinstance(parsed, dict) else {}


def rel(project: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)


def site_config(project: Path) -> dict[str, Any]:
    return load_yaml_file(project / "_config.yml")


def _make_target_available(project: Path, target: str) -> bool:
    makefile = project / "Makefile"
    text = makefile.read_text(encoding="utf-8", errors="ignore") if makefile.is_file() else ""
    return bool(re.search(rf"(?m)^{re.escape(target)}(?:\s+[^:#=\s]+)*\s*::?(?!=)", text))


def _capture_runtime_available(project: Path) -> bool:
    makefile = project / "Makefile"
    text = makefile.read_text(encoding="utf-8", errors="ignore") if makefile.is_file() else ""
    return bool(re.search(r"(?m)^UNALTRAWEB_CAPTURE_RUNTIME\s*:=\s*1\s*$", text))


def detect_site(project: Path) -> dict[str, Any]:
    project = project_path(project)
    config_path = project / "_config.yml"
    gemfile_path = project / "Gemfile"
    config = site_config(project)
    plugins = config.get("plugins")
    plugin_names = [str(item) for item in plugins] if isinstance(plugins, list) else []
    gemfile = gemfile_path.read_text(encoding="utf-8", errors="ignore") if gemfile_path.is_file() else ""

    markers = {
        "theme": str(config.get("theme") or "") == "unaltraweb",
        "plugin": "unaltraweb" in plugin_names,
        "config_namespace": isinstance(config.get("unaltraweb"), dict),
        "gem": bool(re.search(r"(?m)^\s*gem\s+['\"]unaltraweb['\"]", gemfile)),
    }
    runtime_targets = {
        "build_native": _make_target_available(project, "build-native"),
        "serve_native": _make_target_available(project, "serve-native"),
    }
    return {
        "project": str(project),
        "is_unaltraweb_site": config_path.is_file() and any(markers.values()),
        "markers": markers,
        "runtime_targets": runtime_targets,
        "profile": site_profile(config),
        "paths": {
            "config": config_path.is_file(),
            "gemfile": gemfile_path.is_file(),
            "makefile": (project / "Makefile").is_file(),
        },
    }


def unaltraweb_config(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("unaltraweb")
    return value if isinstance(value, dict) else {}


def site_profile(config: dict[str, Any]) -> str:
    return str(unaltraweb_config(config).get("site_profile") or "").strip()


def feature_flags(config: dict[str, Any]) -> dict[str, Any]:
    features = unaltraweb_config(config).get("features")
    return features if isinstance(features, dict) else {}


def configured_languages(config: dict[str, Any]) -> list[str]:
    languages = config.get("languages")
    if isinstance(languages, list):
        return [str(item) for item in languages]
    default_lang = config.get("default_lang") or config.get("lang")
    return [str(default_lang)] if default_lang else []


def default_language(config: dict[str, Any]) -> str:
    uw_config = unaltraweb_config(config)
    for value in [
        uw_config.get("default_lang"),
        uw_config.get("lang"),
        config.get("default_lang"),
        config.get("lang"),
    ]:
        if value:
            return str(value)
    languages = configured_languages(config)
    return languages[0] if languages else ""


def editorial_config(config: dict[str, Any]) -> dict[str, str]:
    uw_config = unaltraweb_config(config)
    return {
        "status_field": str(uw_config.get("content_status_field") or DEFAULT_STATUS_FIELD),
        "approved_value": str(uw_config.get("approved_status") or DEFAULT_APPROVED_VALUE),
    }


def _parse_languages(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _profile_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _resolve_site_profile(project: Path, site_profile_value: str = "") -> str:
    profile = site_profile_value.strip() if site_profile_value else site_profile(site_config(project))
    if not profile:
        raise ValueError("No site profile configured. Pass site_profile or set unaltraweb.site_profile in _config.yml.")
    if profile not in PROFILE_CONTRACTS:
        raise ValueError(f"Unknown site profile: {profile}")
    return profile


def iter_content_files(project: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in CONTENT_DIRS:
        root = project / directory
        if root.is_dir():
            paths.extend(path for path in root.rglob("*") if path.suffix.lower() in {".md", ".html"})
    return sorted(paths)


def content_inventory(project: Path) -> dict[str, Any]:
    project = project_path(project)
    collections: dict[str, Any] = {}
    for directory in CONTENT_DIRS:
        root = project / directory
        files = sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else []
        markdown = [path for path in files if path.suffix.lower() in {".md", ".html"}]
        collections[directory] = {
            "exists": root.is_dir(),
            "files": len(files),
            "documents": len(markdown),
            "sample": [rel(project, path) for path in markdown[:8]],
        }
    data_files = sorted((project / "_data").glob("**/*")) if (project / "_data").is_dir() else []
    computation_sources = sorted(
        path
        for directory in CONTENT_DIRS
        for path in (project / directory).rglob("*")
        if (project / directory).is_dir() and path.is_file() and path.suffix.lower() in COMPUTATION_SUFFIXES
    )
    web_capture_sources = sorted(
        path
        for path in (project / "assets").rglob("*")
        if path.is_file() and path.name.lower().endswith(WEB_CAPTURE_SUFFIXES)
    ) if (project / "assets").is_dir() else []
    visualization_sources = sorted(
        path
        for path in (project / "assets").rglob("*")
        if path.is_file() and path.name.lower().endswith((".vl.json", ".vg.json"))
    ) if (project / "assets").is_dir() else []
    visualization_manifest = project / ".vegavisuals.yml"
    return {
        "project": str(project),
        "generated_at": utc_now(),
        "collections": collections,
        "data_files": [rel(project, path) for path in data_files if path.is_file()],
        "assets_present": (project / "assets").is_dir(),
        "computation_sources": [rel(project, path) for path in computation_sources],
        "web_capture_sources": [rel(project, path) for path in web_capture_sources],
        "visualization_manifest": rel(project, visualization_manifest) if visualization_manifest.is_file() else "",
        "visualization_sources": [rel(project, path) for path in visualization_sources],
    }


def _scaffold_root() -> Path:
    return Path(__file__).resolve().parent / "scaffolds"


def scaffold_inventory() -> dict[str, Any]:
    root = _scaffold_root()
    profiles = []
    for profile, contract in PROFILE_CONTRACTS.items():
        profile_root = root / "profiles" / profile
        profiles.append(
            {
                "profile": profile,
                "description": contract["description"],
                "available": (profile_root / "_config.yml.tmpl").is_file() and (profile_root / "home.md.tmpl").is_file(),
                "recommended_paths": contract["recommended_paths"],
            }
        )
    return {
        "source": "unaltraweb_mcp package",
        "default": "unaltreselfie",
        "common_available": (root / "common" / "Makefile").is_file() and (root / "common" / "Gemfile").is_file(),
        "profiles": profiles,
    }


def starter_templates(factory: Path) -> dict[str, Any]:
    """Return the package-owned scaffolds exposed by the legacy inventory name."""
    return {"factory": str(project_path(factory)), **scaffold_inventory()}


def _yaml_scalar(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_inline_list(values: list[str]) -> str:
    return "[" + ", ".join(_yaml_scalar(value) for value in values) + "]"


def _validated_languages(default_lang: str, languages: str | list[str] | None) -> tuple[str, list[str]]:
    values = _parse_languages(languages)
    selected_default = default_lang.strip() or (values[0] if values else "en")
    if selected_default not in values:
        values.insert(0, selected_default)
    values = list(dict.fromkeys(values))
    invalid = [value for value in values if not LANGUAGE_RE.fullmatch(value)]
    if invalid:
        raise ValueError(f"Invalid language identifier: {invalid[0]}")
    return selected_default, values


def _render_scaffold_template(path: Path, replacements: dict[str, str]) -> bytes:
    text = path.read_text(encoding="utf-8")
    for token, value in replacements.items():
        text = text.replace(f"__{token}__", value)
    unresolved = sorted(set(re.findall(r"__[A-Z_]+__", text)))
    if unresolved:
        raise RuntimeError(f"Unresolved scaffold tokens in {path.name}: {', '.join(unresolved)}")
    return text.encode("utf-8")


def _scaffold_payloads(profile: str, *, title: str, baseurl: str, url: str, default_lang: str, languages: list[str]) -> dict[Path, bytes]:
    root = _scaffold_root()
    common_root = root / "common"
    profile_root = root / "profiles" / profile
    required = [common_root / "Makefile", common_root / "Gemfile", profile_root / "_config.yml.tmpl", profile_root / "home.md.tmpl"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Package-owned new-web scaffold is incomplete: {', '.join(missing)}")

    payloads: dict[Path, bytes] = {}
    for source_root in [common_root, profile_root]:
        for source in sorted(source_root.rglob("*")):
            if source.is_symlink():
                raise RuntimeError(f"Package-owned scaffold contains a symlink: {source}")
            if not source.is_file() or source.name in SCAFFOLD_TEMPLATE_FILES:
                continue
            relative = source.relative_to(source_root)
            if relative in payloads:
                raise RuntimeError(f"Duplicate package-owned scaffold path: {relative}")
            payloads[relative] = source.read_bytes()

    replacements = {
        "TITLE": _yaml_scalar(title),
        "URL": _yaml_scalar(url),
        "BASEURL": _yaml_scalar(baseurl),
        "DEFAULT_LANG": _yaml_scalar(default_lang),
        "LANGUAGES": _yaml_inline_list(languages),
    }
    payloads[Path("_config.yml")] = _render_scaffold_template(profile_root / "_config.yml.tmpl", replacements)
    for language in languages:
        home_replacements = {
            "TITLE": _yaml_scalar(title),
            "LANG": _yaml_scalar(language),
            "PERMALINK": _yaml_scalar("/" if language == default_lang else f"/{language}/"),
        }
        payloads[Path("_pages") / language / "index.md"] = _render_scaffold_template(profile_root / "home.md.tmpl", home_replacements)
    return payloads


def _scaffold_preflight(project: Path, payloads: dict[Path, bytes], required_directories: set[Path]) -> tuple[list[Path], list[Path]]:
    if project.exists() and not project.is_dir():
        raise RuntimeError(f"New website path is not a directory: {project}")

    all_directories = set(required_directories)
    for relative in required_directories | set(payloads):
        parent = relative.parent
        while parent != Path("."):
            all_directories.add(parent)
            parent = parent.parent

    conflicts: list[str] = []
    for relative in sorted(all_directories | set(payloads)):
        if relative.is_absolute() or ".." in relative.parts:
            conflicts.append(f"unsafe scaffold path: {relative}")
            continue
        target = project / relative
        current = project
        has_symlink = False
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                conflicts.append(f"symlink is not allowed at scaffold path: {current.relative_to(project)}")
                has_symlink = True
                break
        if has_symlink:
            continue
        try:
            target.resolve(strict=False).relative_to(project)
        except ValueError:
            conflicts.append(f"path escapes the website root: {relative}")

    for relative in sorted(all_directories):
        target = project / relative
        if target.exists() and not target.is_dir():
            conflicts.append(f"expected a directory but found a file: {relative}")

    create: list[Path] = []
    unchanged: list[Path] = []
    for relative, content in sorted(payloads.items()):
        target = project / relative
        if target.is_symlink():
            continue
        if target.exists():
            if not target.is_file():
                conflicts.append(f"expected a file but found a directory: {relative}")
            elif target.read_bytes() == content:
                unchanged.append(relative)
            else:
                conflicts.append(f"existing file differs from the package scaffold: {relative}")
        else:
            create.append(relative)

    if conflicts:
        details = "\n".join(f"- {message}" for message in sorted(set(conflicts)))
        raise RuntimeError(f"new-web preflight failed; no website files were written:\n{details}")
    return create, unchanged


def _new_web_project_path(raw: str | Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"Symlinks are not allowed in the new website destination: {current}")
    return path


def _open_or_create_scaffold_root(project: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open(project.anchor, flags)
    try:
        for part in project.parts[1:]:
            try:
                os.mkdir(part, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _open_scaffold_directory(root_fd: int, relative: Path, *, create: bool) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.dup(root_fd)
    try:
        for part in relative.parts:
            if create:
                try:
                    os.mkdir(part, dir_fd=current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _create_scaffold_file(root_fd: int, relative: Path, content: bytes) -> None:
    parent_fd = _open_scaffold_directory(root_fd, relative.parent, create=True)
    file_fd: int | None = None
    created_stat: os.stat_result | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        file_fd = os.open(relative.name, flags, 0o644, dir_fd=parent_fd)
        created_stat = os.fstat(file_fd)
        remaining = memoryview(content)
        while remaining:
            written = os.write(file_fd, remaining)
            if written == 0:
                raise OSError(f"Could not finish writing scaffold file: {relative}")
            remaining = remaining[written:]
        os.fsync(file_fd)
    except Exception:
        if created_stat is not None:
            try:
                current_stat = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
                if (current_stat.st_dev, current_stat.st_ino) == (created_stat.st_dev, created_stat.st_ino):
                    os.unlink(relative.name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        raise
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent_fd)


def _read_scaffold_file(root_fd: int, relative: Path) -> bytes:
    parent_fd = _open_scaffold_directory(root_fd, relative.parent, create=False)
    file_fd: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        file_fd = os.open(relative.name, flags, dir_fd=parent_fd)
        chunks = []
        while chunk := os.read(file_fd, 65536):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent_fd)


def new_web(
    project: Path,
    *,
    site_profile_value: str = "unaltreselfie",
    title: str = "",
    baseurl: str = "",
    url: str = "",
    default_lang: str = "",
    languages: str | list[str] | None = None,
) -> dict[str, Any]:
    project = _new_web_project_path(project)
    if site_profile_value not in PROFILE_CONTRACTS:
        raise ValueError(f"Unknown site profile: {site_profile_value}")

    selected_default, language_values = _validated_languages(default_lang, languages)
    selected_title = title.strip() or "New unaltraweb site"
    payloads = _scaffold_payloads(
        site_profile_value,
        title=selected_title,
        baseurl=baseurl,
        url=url,
        default_lang=selected_default,
        languages=language_values,
    )
    recommended_paths = {Path(path) for path in PROFILE_CONTRACTS[site_profile_value]["recommended_paths"]}
    required_directories = {path for path in recommended_paths if path not in payloads}
    required_directories.update(relative.parent for relative in payloads if relative.parent != Path("."))
    create, unchanged = _scaffold_preflight(project, payloads, required_directories)

    root_fd = _open_or_create_scaffold_root(project)
    try:
        for relative in sorted(required_directories):
            directory_fd = _open_scaffold_directory(root_fd, relative, create=True)
            os.close(directory_fd)
        for relative in create:
            _create_scaffold_file(root_fd, relative, payloads[relative])
        for relative, content in sorted(payloads.items()):
            if _read_scaffold_file(root_fd, relative) != content:
                raise RuntimeError(f"Scaffold file changed while new-web was running: {relative}")
    except OSError as exc:
        raise RuntimeError(f"new-web could not apply the preflighted scaffold safely: {exc}") from exc
    finally:
        os.close(root_fd)

    check = profile_check(project)
    return {
        "ok": check["ok"],
        "operation": "new_web",
        "project": str(project),
        "source": "unaltraweb_mcp package",
        "site_profile": site_profile_value,
        "default_language": selected_default,
        "languages": language_values,
        "created_count": len(create),
        "created": [str(path) for path in create],
        "unchanged_count": len(unchanged),
        "unchanged": [str(path) for path in unchanged],
        "profile_check": check,
        "next_steps": ["Edit the generated configuration and home page", "Run site_check", "Run build_site"],
    }


def initialize_site(
    project: Path,
    factory: Path,
    *,
    template_path: str = "",
    site_profile_value: str = "unaltreselfie",
    title: str = "",
    baseurl: str = "",
    url: str = "",
    default_lang: str = "",
    languages: str | list[str] | None = None,
    force: bool = False,
    confirm_overwrite: bool = False,
) -> dict[str, Any]:
    del factory, confirm_overwrite
    if template_path:
        raise ValueError("External template paths are not supported; new websites use package-owned profile scaffolds")
    if force:
        raise RuntimeError("Package-owned new-web scaffolds never overwrite differing files")
    return new_web(
        project,
        site_profile_value=site_profile_value,
        title=title,
        baseurl=baseurl,
        url=url,
        default_lang=default_lang,
        languages=languages,
    )


def profile_prune_plan(project: Path, site_profile_value: str = "") -> dict[str, Any]:
    project = project_path(project)
    profile = _resolve_site_profile(project, site_profile_value)
    candidates: list[dict[str, Any]] = []
    kept_profiled: list[dict[str, Any]] = []
    unprofiled: list[str] = []

    for path in iter_content_files(project):
        front = read_front_matter(path)
        profiles = _profile_values(front.get("profiles"))
        relative = rel(project, path)
        if not profiles:
            unprofiled.append(relative)
            continue
        item = {
            "path": relative,
            "profiles": profiles,
            "title": str(front.get("title") or ""),
        }
        if profile in profiles:
            kept_profiled.append(item)
        else:
            candidates.append(item)

    return {
        "project": str(project),
        "site_profile": profile,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "kept_profiled_count": len(kept_profiled),
        "kept_profiled_sample": kept_profiled[:40],
        "unprofiled_count": len(unprofiled),
        "unprofiled_sample": unprofiled[:40],
        "rule": "Only content files with explicit front matter profiles not containing the selected site profile are prune candidates.",
    }


def _remove_empty_content_dirs(project: Path) -> list[str]:
    removed: list[str] = []
    roots = [(project / directory).resolve() for directory in CONTENT_DIRS]
    for root in roots:
        if not root.is_dir():
            continue
        for directory in sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                continue
            removed.append(rel(project, directory))
    return removed


def profile_prune(project: Path, site_profile_value: str = "", *, dry_run: bool = True, confirm_prune: bool = False) -> dict[str, Any]:
    project = project_path(project)
    plan = profile_prune_plan(project, site_profile_value)
    if dry_run:
        return {"ok": True, "dry_run": True, **plan}
    if not confirm_prune:
        raise RuntimeError("profile_prune deletes files; call again with confirm_prune=True only after reviewing profile_prune_plan")

    deleted: list[str] = []
    skipped: list[dict[str, str]] = []
    for item in plan["candidates"]:
        target = _safe_relative_path(project, str(item["path"]), default="")
        if not target.is_file():
            skipped.append({"path": str(item["path"]), "reason": "not a file"})
            continue
        target.unlink()
        deleted.append(str(item["path"]))

    return {
        "ok": True,
        "dry_run": False,
        "project": str(project),
        "site_profile": plan["site_profile"],
        "deleted_count": len(deleted),
        "deleted": deleted,
        "skipped": skipped,
        "empty_dirs_removed": _remove_empty_content_dirs(project),
        "prune_plan": plan,
    }


def _manual_markdown_paths(project: Path) -> list[Path]:
    paths: list[Path] = []
    chapters_root = project / "_chapters"
    if chapters_root.is_dir():
        paths.extend(path for path in chapters_root.rglob("*.md") if path.is_file())

    pages_root = project / "_pages"
    if pages_root.is_dir():
        for path in pages_root.rglob("*.md"):
            front = read_front_matter(path)
            profiles = _profile_values(front.get("profiles"))
            if front.get("layout") in {"manual-home", "manual-chapter"} or "unaltremanual" in profiles:
                paths.append(path)
    return sorted(set(paths))


def _computation_front_matter_for_typography(source: Path) -> dict[str, Any]:
    if source.suffix.lower() in {".qmd", ".rmd"}:
        return read_front_matter(source)
    if source.suffix.lower() == ".ipynb":
        try:
            notebook = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        value = notebook.get("metadata", {}).get("unaltraweb_front_matter")
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            parsed = load_yaml_text(value)
            return parsed if isinstance(parsed, dict) else {}
        return {}

    prefix = "#'" if source.suffix.lower() == ".r" else "#"
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    yaml_lines: list[str] = []
    in_front_matter = False
    for line in lines:
        stripped = line.lstrip()
        if not stripped.startswith(prefix):
            if in_front_matter:
                break
            continue
        content = stripped[len(prefix):].lstrip()
        if content == "---":
            if in_front_matter:
                break
            in_front_matter = True
            continue
        if in_front_matter:
            yaml_lines.append(content)
    parsed = load_yaml_text("\n".join(yaml_lines)) if yaml_lines else {}
    return parsed if isinstance(parsed, dict) else {}


def _visual_output_for_typography(project: Path, reference: str) -> tuple[Path | None, str]:
    source = (project / reference).resolve()
    try:
        source.relative_to(project)
    except ValueError:
        return None, "outside_project"
    if not source.is_file():
        return None, "missing_source"

    lower = source.as_posix().lower()
    if any(lower.endswith(suffix) for suffix in DIAGRAM_SOURCE_SUFFIXES):
        candidates = [Path(str(source) + ".edited.svg"), Path(str(source) + ".svg")]
        return next((candidate for candidate in candidates if candidate.is_file()), None), "diagram"
    if lower.endswith(WEB_CAPTURE_SUFFIXES):
        base = str(source).rsplit(".", 1)[0]
        candidates = [Path(base + ".edited.svg"), Path(base + ".svg")]
        return next((candidate for candidate in candidates if candidate.is_file()), None), "web_capture"
    if lower.endswith(VEGA_SOURCE_SUFFIXES):
        manifest = load_yaml_file(project / ".vegavisuals.yml")
        items = manifest.get("visualizations") if isinstance(manifest, dict) else None
        source_relative = source.relative_to(project).as_posix()
        matches = [item for item in items or [] if isinstance(item, dict) and str(item.get("source") or "") == source_relative]
        if len(matches) != 1:
            return None, "vega_manifest"
        output = (project / str(matches[0].get("output") or "")).resolve()
        try:
            output.relative_to(project)
        except ValueError:
            return None, "outside_project"
        return (output if output.is_file() else None), "vega"
    if source.suffix.lower() in COMPUTATION_SUFFIXES:
        front = _computation_front_matter_for_typography(source)
        metadata = front.get("unaltraweb_compute") if isinstance(front, dict) else None
        if not isinstance(metadata, dict) or str(metadata.get("mode") or "").strip().lower() != "figure":
            return None, "computation_metadata"
        outputs = metadata.get("outputs")
        if outputs is None and metadata.get("output"):
            outputs = [metadata["output"]]
        if not isinstance(outputs, list) or not outputs:
            return None, "computation_metadata"
        output = (project / str(outputs[0])).resolve()
        try:
            output.relative_to(project)
        except ValueError:
            return None, "outside_project"
        edited = output.with_suffix(".edited.svg")
        if edited.is_file():
            return edited, "computation"
        return (output if output.is_file() else None), "computation"
    if source.suffix.lower() == ".svg":
        return source, "svg"
    if source.suffix.lower() in RASTER_VISUAL_SUFFIXES:
        return source, "raster"
    return source, "unsupported"


def _localized_visual_reference(
    project: Path,
    reference: str,
    *,
    language: str,
    default_lang: str,
    languages: list[str],
) -> str:
    current = language.strip()
    default = default_lang.strip()
    if not current or current == default:
        return reference
    suffix = next((candidate for candidate in VISUAL_LOCALIZATION_SUFFIXES if reference.lower().endswith(candidate)), "")
    if not suffix:
        return reference
    stem = reference[:-len(suffix)]
    configured = {str(value).strip().lower() for value in languages if str(value).strip()}
    configured.update({current.lower(), default.lower()})
    if any(stem.lower().endswith(f".{code}") for code in configured):
        return reference
    localized = f"{stem}.{current}{suffix}"
    candidate = (project / localized).resolve()
    try:
        candidate.relative_to(project)
    except ValueError:
        return reference
    return localized if candidate.is_file() else reference


def _figure_dimensions(line: str) -> dict[str, str]:
    normalized = line.translate({0x2018: ord("'"), 0x2019: ord("'"), 0x201C: ord('"'), 0x201D: ord('"')})
    values: dict[str, str] = {}
    for match in FIGURE_DIMENSION_RE.finditer(normalized):
        values[match.group("name").lower()] = next(
            value for value in match.group("double", "single", "bare") if value is not None
        ).strip()
    return {
        "web_width": values.get("data-figure-width-web") or values.get("data-figure-width") or "",
        "web_height": values.get("data-figure-height-web") or values.get("data-figure-height") or "",
        "pdf_width": values.get("data-figure-width-pdf") or values.get("data-figure-width") or "",
        "pdf_height": values.get("data-figure-height-pdf") or values.get("data-figure-height") or "",
    }


def _dimension_value(value: str, *, support: str, axis: str, percentage_base: float | None = None) -> float | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(%|px|pt|rem|em|in|cm|mm)", value.strip(), re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower()
    if support == "web":
        if unit == "%":
            return percentage_base * number / 100.0 if percentage_base is not None else None
        if unit == "px":
            return number
        if unit == "pt":
            return number * 96.0 / 72.0
        if unit == "rem":
            return number * MANUAL_WEB_ROOT_FONT_PIXELS
        if unit == "em":
            return number * MANUAL_WEB_BODY_FONT_PIXELS
        if unit == "in":
            return number * 96.0
        if unit == "cm":
            return number * 96.0 / 2.54
        if unit == "mm":
            return number * 96.0 / 25.4
    else:
        if unit == "%":
            base = percentage_base or (MANUAL_PDF_TEXT_WIDTH_POINTS if axis == "width" else DIAGRAM_PDF_HEIGHT_MAX_POINTS)
            return base * number / 100.0
        if unit == "px":
            return number * 72.0 / 96.0
        if unit == "pt":
            return number
        if unit in {"rem", "em"}:
            if axis == "width" and unit == "rem":
                return min(number / 60.0, 1.0) * MANUAL_PDF_TEXT_WIDTH_POINTS
            return number * MANUAL_PDF_BODY_FONT_POINTS
        if unit == "in":
            return number * 72.0
        if unit == "cm":
            return number * 72.0 / 2.54
        if unit == "mm":
            return number * 72.0 / 25.4
    return None


def _support_typography(
    *,
    support: str,
    viewbox_width: float,
    viewbox_height: float,
    font_pixels: float,
    width: str,
    height: str,
    width_factor: float = 1.0,
) -> dict[str, Any] | None:
    maximum_width = (MANUAL_WEB_TEXT_WIDTH_PIXELS if support == "web" else MANUAL_PDF_TEXT_WIDTH_POINTS) * width_factor
    if width:
        display_width = _dimension_value(width, support=support, axis="width", percentage_base=maximum_width)
        if display_width is None:
            return None
        display_width = min(display_width, maximum_width)
    elif support == "web":
        display_width = min(viewbox_width, maximum_width)
    else:
        display_width = min(viewbox_width * 72.0 / 96.0, maximum_width)

    scale = display_width / viewbox_width
    if height:
        display_height_limit = _dimension_value(height, support=support, axis="height")
        if display_height_limit is None:
            return None
        scale = min(scale, display_height_limit / viewbox_height)
    display_width = viewbox_width * scale
    display_height = viewbox_height * scale
    effective_font = font_pixels * scale

    if support == "web":
        if effective_font < FIGURE_WEB_FONT_MIN_PIXELS:
            state = "undersized"
        elif effective_font > FIGURE_WEB_FONT_MAX_PIXELS:
            state = "oversized"
        else:
            state = "ok"
        return {
            "state": state,
            "display_width_pixels": round(display_width, 2),
            "display_height_pixels": round(display_height, 2),
            "font_pixels": round(effective_font, 2),
            "font_to_body_ratio": round(effective_font / MANUAL_WEB_BODY_FONT_PIXELS, 3),
        }

    if display_height > DIAGRAM_PDF_HEIGHT_MAX_POINTS:
        state = "too_tall"
    elif effective_font < DIAGRAM_PDF_FONT_MIN_POINTS:
        state = "undersized"
    elif effective_font > DIAGRAM_PDF_FONT_MAX_POINTS:
        state = "oversized"
    else:
        state = "ok"
    return {
        "state": state,
        "display_width_points": round(display_width, 2),
        "display_height_points": round(display_height, 2),
        "font_points": round(effective_font, 2),
        "font_to_body_ratio": round(effective_font / MANUAL_PDF_BODY_FONT_POINTS, 3),
    }


def _recommended_figure_dimensions(
    viewbox_width: float,
    viewbox_height: float,
    font_pixels: float,
    *,
    web_width_factor: float = 1.0,
    pdf_width_factor: float = 1.0,
) -> dict[str, Any]:
    web_target_font = MANUAL_WEB_BODY_FONT_PIXELS * 0.85
    web_width_pixels = web_target_font * viewbox_width / font_pixels
    web_minimum_width = FIGURE_WEB_FONT_MIN_PIXELS * viewbox_width / font_pixels
    web_width_limit = MANUAL_WEB_TEXT_WIDTH_PIXELS * web_width_factor
    if web_width_pixels <= web_width_limit:
        web_width_rem = round(web_width_pixels / MANUAL_WEB_ROOT_FONT_PIXELS * 2.0) / 2.0
        web = {
            "width": f"{web_width_rem:g}rem",
            "height": "auto",
            "estimated_height_pixels": round(viewbox_height * web_width_pixels / viewbox_width, 1),
        }
    elif web_minimum_width <= web_width_limit:
        web = {
            "width": "100%",
            "height": "auto",
            "estimated_height_pixels": round(viewbox_height * web_width_limit / viewbox_width, 1),
            "message": "Use the full available web panel; embedded text reaches the minimum target but not the preferred 85% of body text.",
        }
    else:
        web = {
            "width": None,
            "height": "auto",
            "message": "The source text cannot reach 85% of body text within the web reading column; increase source font size or split the figure.",
        }

    pdf_target_font = 9.5
    pdf_width_points = pdf_target_font * viewbox_width / font_pixels
    pdf_minimum_width = DIAGRAM_PDF_FONT_MIN_POINTS * viewbox_width / font_pixels
    pdf_width_limit = min(
        MANUAL_PDF_TEXT_WIDTH_POINTS * pdf_width_factor,
        DIAGRAM_PDF_HEIGHT_MAX_POINTS * viewbox_width / viewbox_height,
    )
    if pdf_width_points <= pdf_width_limit:
        pdf_percentage = round(pdf_width_points / MANUAL_PDF_TEXT_WIDTH_POINTS * 100.0)
        pdf = {
            "width": f"{pdf_percentage}%",
            "height": "auto",
            "estimated_height_points": round(viewbox_height * pdf_width_points / viewbox_width, 1),
        }
    elif pdf_minimum_width <= pdf_width_limit:
        pdf = {
            "width": "100%",
            "height": "auto",
            "estimated_height_points": round(viewbox_height * pdf_width_limit / viewbox_width, 1),
            "message": "Use the full available PDF panel; embedded text reaches 8 pt but not the preferred 9.5 pt target.",
        }
    else:
        pdf = {
            "width": None,
            "height": "auto",
            "message": "The source cannot reach 9.5 pt text within both the PDF width and 600 pt height limits; increase source font size or split the figure.",
        }
    return {"web": web, "pdf": pdf}


def _figure_typography(
    project: Path,
    markdown_path: Path,
    line: str,
    lineno: int,
    raw: str,
    *,
    web_width_factor: float = 1.0,
    pdf_width_factor: float = 1.0,
    language: str = "",
    default_lang: str = "",
    languages: list[str] | None = None,
) -> dict[str, Any] | None:
    undecorated = re.sub(r"\{\{\s*site\.baseurl\s*\}\}", "", raw).strip()
    path_match = re.match(r"([^\s?#]+)", undecorated)
    if not path_match:
        return None
    reference = path_match.group(1).lstrip("/")
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:)?//", reference, re.IGNORECASE):
        return {
            "path": rel(project, markdown_path),
            "line": lineno,
            "source": reference,
            "output": "",
            "state": "unverified",
            "message": "Remote figures require a rendered visual review; embedded text metrics are not locally inspectable.",
        }

    selected_reference = _localized_visual_reference(
        project,
        reference,
        language=language,
        default_lang=default_lang,
        languages=languages or [],
    )
    output, visual_kind = _visual_output_for_typography(project, selected_reference)
    if output is None:
        return {
            "path": rel(project, markdown_path),
            "line": lineno,
            "source": reference,
            "localized_source": selected_reference if selected_reference != reference else None,
            "output": "",
            "state": "unverified",
            "message": "Render or restore the local visual before checking embedded text size on web and PDF.",
        }
    if output.suffix.lower() != ".svg":
        return {
            "path": rel(project, markdown_path),
            "line": lineno,
            "source": reference,
            "localized_source": selected_reference if selected_reference != reference else None,
            "output": rel(project, output),
            "visual_kind": visual_kind,
            "state": "unverified",
            "message": "Raster figures do not expose reliable embedded text metrics; prefer SVG for text-bearing figures or review the rendered web and PDF at final size.",
        }

    try:
        svg = output.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    viewbox_match = SVG_VIEWBOX_RE.search(svg)
    if not re.search(r"<(?:text|foreignObject)\b", svg, re.IGNORECASE):
        return {
            "path": rel(project, markdown_path),
            "line": lineno,
            "source": reference,
            "localized_source": selected_reference if selected_reference != reference else None,
            "output": rel(project, output),
            "visual_kind": visual_kind,
            "state": "no_text",
            "message": "The SVG contains no inspectable text; no inside/outside text comparison is needed.",
        }
    font_matches: list[float] = []
    for pattern in (SVG_CSS_FONT_SIZE_RE, SVG_ATTRIBUTE_FONT_SIZE_RE):
        for match in pattern.finditer(svg):
            value = float(match.group(1))
            unit = (match.group(2) or "px").lower()
            if unit == "pt":
                value *= 96.0 / 72.0
            elif unit == "rem":
                value *= MANUAL_WEB_ROOT_FONT_PIXELS
            font_matches.append(value)
    if not viewbox_match or not font_matches:
        return {
            "path": rel(project, markdown_path),
            "line": lineno,
            "source": reference,
            "output": rel(project, output),
            "state": "unverified",
            "message": "The rendered SVG does not expose a measurable viewBox and font size.",
        }
    try:
        viewbox = [float(value) for value in viewbox_match.group(1).replace(",", " ").split()]
    except ValueError:
        return None
    if len(viewbox) != 4 or viewbox[2] <= 0:
        return None

    font_size = min(font_matches)
    dimensions = _figure_dimensions(line)
    web = _support_typography(
        support="web",
        viewbox_width=viewbox[2],
        viewbox_height=viewbox[3],
        font_pixels=font_size,
        width=dimensions["web_width"],
        height=dimensions["web_height"],
        width_factor=web_width_factor,
    )
    pdf = _support_typography(
        support="pdf",
        viewbox_width=viewbox[2],
        viewbox_height=viewbox[3],
        font_pixels=font_size,
        width=dimensions["pdf_width"],
        height=dimensions["pdf_height"],
        width_factor=pdf_width_factor,
    )
    if web is None or pdf is None:
        state = "unverified"
        message = "One or more figure dimensions use a value that cannot be converted into a reliable web/PDF text-size estimate."
    else:
        states = {web["state"], pdf["state"]}
        if states == {"ok"}:
            state = "ok"
            message = "Embedded text is proportionate to body text in the base web layout and within the 8-11 pt PDF target."
        elif "too_tall" in states:
            state = "too_tall"
            message = "The figure is estimated to exceed the 600 pt PDF height target at its configured print dimensions."
        elif len(states) == 1:
            state = next(iter(states))
            message = "Embedded text or figure height falls outside the target on both supports."
        else:
            state = "mixed"
            message = "Web and PDF need different figure dimensions to keep embedded text proportionate to body text."
    return {
        "path": rel(project, markdown_path),
        "line": lineno,
        "source": reference,
        "localized_source": selected_reference if selected_reference != reference else None,
        "output": rel(project, output),
        "visual_kind": visual_kind,
        "source_minimum_font_pixels": round(font_size, 2),
        "data_figure_width_web": dimensions["web_width"] or None,
        "data_figure_height_web": dimensions["web_height"] or None,
        "data_figure_width_pdf": dimensions["pdf_width"] or None,
        "data_figure_height_pdf": dimensions["pdf_height"] or None,
        "web_panel_width_factor": web_width_factor,
        "pdf_panel_width_factor": pdf_width_factor,
        "web": web,
        "pdf": pdf,
        "estimated_pdf_font_points": pdf["font_points"] if pdf else None,
        "estimated_pdf_height_points": pdf["display_height_points"] if pdf else None,
        "suggested_dimensions": _recommended_figure_dimensions(
            viewbox[2],
            viewbox[3],
            font_size,
            web_width_factor=web_width_factor,
            pdf_width_factor=pdf_width_factor,
        ),
        "state": state,
        "message": message,
    }


def _subfigure_width_factors(layout: str) -> list[tuple[float, float]]:
    factors: list[tuple[float, float]] = []
    for row in layout.split("/"):
        count = len([token for token in row.split("+") if token.strip()])
        if not count:
            continue
        web_factor = {1: 1.0, 2: 0.49, 3: 0.32, 4: 0.24}.get(count, 0.96 / count)
        pdf_factor = {1: 0.92, 2: 0.48, 3: 0.31, 4: 0.23}.get(count, 0.92 / count)
        factors.extend((web_factor, pdf_factor) for _ in range(count))
    return factors


def manual_source_quality_check(project: Path) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    configured_language_values = configured_languages(config)
    configured_default_language = default_language(config)
    paths = _manual_markdown_paths(project)

    bare_tables: list[dict[str, Any]] = []
    inline_diagrams: list[dict[str, Any]] = []
    figures_without_title: list[dict[str, Any]] = []
    standalone_bold_labels: list[dict[str, Any]] = []
    learning_objective_callouts: list[dict[str, Any]] = []
    figure_typography: list[dict[str, Any]] = []

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        front = read_front_matter(path)
        path_parts = path.relative_to(project).as_posix().split("/")
        document_language = str(front.get("lang") or (path_parts[1] if len(path_parts) > 2 else "") or configured_default_language)
        document_default_language = configured_default_language or document_language

        in_front_matter = bool(lines and lines[0].strip() == "---")
        in_fence = False
        fence_marker = ""
        in_table_block = False
        in_subfigures_block = False
        subfigure_factors: list[tuple[float, float]] = []
        in_bare_table = False
        current_section = "chapter opening"
        current_section_line = 1
        section_opening_blocks = 0
        section_seen_subheading = False
        previous_opening_block_kind = ""
        in_learning_objective_callout = False
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            if in_front_matter:
                if lineno > 1 and stripped == "---":
                    in_front_matter = False
                    current_section_line = lineno + 1
                continue

            if not stripped:
                previous_opening_block_kind = ""
                if in_learning_objective_callout:
                    in_learning_objective_callout = False
                continue

            if in_table_block:
                if stripped == ":::":
                    in_table_block = False
                continue
            if in_subfigures_block and stripped == ":::":
                in_subfigures_block = False
                subfigure_factors = []
                continue
            subfigures_match = re.match(r'^:::\s*subfigures(?:\s+([^\s"]+))?', stripped)
            if subfigures_match:
                in_subfigures_block = True
                subfigure_factors = _subfigure_width_factors(subfigures_match.group(1) or "")
                continue
            if stripped.startswith("::: table"):
                if not previous_opening_block_kind:
                    section_opening_blocks += 1
                previous_opening_block_kind = "table"
                in_table_block = True
                in_bare_table = False
                continue

            if in_fence:
                if stripped.startswith(fence_marker):
                    in_fence = False
                    fence_marker = ""
                continue

            diagram_match = DIAGRAM_FENCE_RE.match(line)
            if diagram_match:
                inline_diagrams.append(
                    {
                        "path": rel(project, path),
                        "line": lineno,
                        "engine": diagram_match.group(2).lower(),
                        "message": "Use a versioned diagram source under assets/diagrams and reference it as a captioned image.",
                    }
                )
                in_fence = True
                fence_marker = diagram_match.group(1)
                in_bare_table = False
                continue

            fence_match = FENCE_RE.match(line)
            if fence_match:
                in_fence = True
                fence_marker = fence_match.group(1)
                in_bare_table = False
                in_learning_objective_callout = False
                continue

            h2_match = H2_RE.match(line)
            if h2_match:
                current_section = h2_match.group(1).strip()
                current_section_line = lineno
                section_opening_blocks = 0
                section_seen_subheading = False
                previous_opening_block_kind = ""
                in_learning_objective_callout = False
                in_bare_table = False
                continue

            if stripped.startswith("###"):
                section_seen_subheading = True
                previous_opening_block_kind = ""

            objective_match = LEARNING_OBJECTIVE_CALLOUT_RE.match(line)
            if objective_match:
                if not in_learning_objective_callout:
                    learning_objective_callouts.append(
                        {
                            "path": rel(project, path),
                            "line": lineno,
                            "section": current_section,
                            "section_line": current_section_line,
                            "opening_blocks_before": section_opening_blocks,
                            "after_subheading": section_seen_subheading,
                            "message": "Use learning-objective callouts sparingly, normally after a brief introduction at a chapter or major-section opening.",
                        }
                    )
                    in_learning_objective_callout = True
                continue
            in_learning_objective_callout = False

            opening_block_kind = "list" if re.match(r"^\s*(?:[-*+]\s+|\d+\.\s+)", line) else "paragraph"
            if not previous_opening_block_kind:
                section_opening_blocks += 1
            previous_opening_block_kind = opening_block_kind

            if MARKDOWN_TABLE_ROW_RE.match(line):
                if not in_bare_table:
                    bare_tables.append(
                        {
                            "path": rel(project, path),
                            "line": lineno,
                            "message": 'Wrap manual tables in ::: table "Caption" blocks.',
                        }
                    )
                    in_bare_table = True
                continue
            in_bare_table = False

            if STANDALONE_BOLD_LABEL_RE.match(line):
                standalone_bold_labels.append(
                    {
                        "path": rel(project, path),
                        "line": lineno,
                        "message": "Use a semantic #### heading for a real fourth-level subsection, or keep a bold run-in in the same paragraph.",
                    }
                )

            for image_match in MARKDOWN_IMAGE_RE.finditer(line):
                raw = image_match.group(1).strip()
                web_width_factor, pdf_width_factor = subfigure_factors.pop(0) if subfigure_factors else (1.0, 1.0)
                typography = _figure_typography(
                    project,
                    path,
                    line,
                    lineno,
                    raw,
                    web_width_factor=web_width_factor,
                    pdf_width_factor=pdf_width_factor,
                    language=document_language,
                    default_lang=document_default_language,
                    languages=configured_language_values,
                )
                if typography:
                    figure_typography.append(typography)
                if ".no-figure" in line or "data-no-figure" in line:
                    continue
                if not re.search(r'''\s+(?:"[^"]+"|'[^']+')\s*$''', raw):
                    figures_without_title.append(
                        {
                            "path": rel(project, path),
                            "line": lineno,
                            "message": "Add a Markdown image title so the manual figure caption is explicit.",
                        }
                    )

    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if bare_tables:
        issues.append(
            {
                "severity": "error",
                "message": "Manual contains Markdown tables without captioned table blocks.",
                "count": len(bare_tables),
                "sample": bare_tables[:20],
            }
        )
    if inline_diagrams:
        issues.append(
            {
                "severity": "error",
                "message": "Manual contains inline diagram fences; use diavisuals source files instead.",
                "count": len(inline_diagrams),
                "sample": inline_diagrams[:20],
            }
        )
    if figures_without_title:
        warnings.append(
            {
                "severity": "warning",
                "message": "Some manual figures do not have an explicit Markdown title caption.",
                "count": len(figures_without_title),
                "sample": figures_without_title[:20],
            }
        )
    if standalone_bold_labels:
        warnings.append(
            {
                "severity": "warning",
                "message": "Some standalone bold labels look like non-semantic fourth-level headings.",
                "count": len(standalone_bold_labels),
                "sample": standalone_bold_labels[:20],
            }
        )
    dense_learning_objective_callouts: list[dict[str, Any]] = []
    for path_name in sorted({item["path"] for item in learning_objective_callouts}):
        path_items = [item for item in learning_objective_callouts if item["path"] == path_name]
        for section_line in sorted({item["section_line"] for item in path_items}):
            section_items = [item for item in path_items if item["section_line"] == section_line]
            if len(section_items) > 1:
                dense_learning_objective_callouts.append(
                    {
                        "path": path_name,
                        "section": section_items[0]["section"],
                        "section_line": section_line,
                        "count": len(section_items),
                        "lines": [item["line"] for item in section_items],
                        "message": "A section contains multiple learning-objective callout blocks; keep objectives after the brief opening and use prose, tables, or ordinary notes for intermediate criteria.",
                    }
                )
            for item in section_items:
                opening_blocks_before = int(item.get("opening_blocks_before", 0))
                if item.get("after_subheading") or opening_blocks_before == 0 or opening_blocks_before > 2:
                    dense_learning_objective_callouts.append(
                        {
                            "path": path_name,
                            "section": item["section"],
                            "section_line": item["section_line"],
                            "line": item["line"],
                            "opening_blocks_before": opening_blocks_before,
                            "after_subheading": item.get("after_subheading", False),
                            "message": "A learning-objective callout appears before or beyond the brief opening of a section; place it after one or two introductory paragraphs, or use normal prose for mid-section emphasis.",
                        }
                    )
    if dense_learning_objective_callouts:
        warnings.append(
            {
                "severity": "warning",
                "message": "Some learning-objective callouts are repeated or placed away from section openings.",
                "count": len(dense_learning_objective_callouts),
                "sample": dense_learning_objective_callouts[:20],
            }
        )
    figure_typography_findings = [item for item in figure_typography if item["state"] in {"oversized", "undersized", "too_tall", "mixed"}]
    if figure_typography_findings:
        warnings.append(
            {
                "severity": "warning",
                "message": "Some figures need different web/PDF dimensions to keep embedded text proportionate to body text and within the 8-11 pt PDF target.",
                "count": len(figure_typography_findings),
                "sample": figure_typography_findings[:20],
            }
        )

    return {
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
        "bare_tables": bare_tables,
        "inline_diagrams": inline_diagrams,
        "figures_without_title": figures_without_title,
        "standalone_bold_labels": standalone_bold_labels,
        "learning_objective_callouts": learning_objective_callouts,
        "dense_learning_objective_callouts": dense_learning_objective_callouts,
        "figure_typography": {
            "web_body_font_pixels": MANUAL_WEB_BODY_FONT_PIXELS,
            "web_minimum_font_pixels": round(FIGURE_WEB_FONT_MIN_PIXELS, 2),
            "web_maximum_font_pixels": round(FIGURE_WEB_FONT_MAX_PIXELS, 2),
            "body_font_points": MANUAL_PDF_BODY_FONT_POINTS,
            "minimum_font_points": DIAGRAM_PDF_FONT_MIN_POINTS,
            "maximum_font_points": DIAGRAM_PDF_FONT_MAX_POINTS,
            "maximum_height_points": DIAGRAM_PDF_HEIGHT_MAX_POINTS,
            "references": figure_typography,
            "findings": figure_typography_findings,
        },
        "diagram_typography": {
            "web_body_font_pixels": MANUAL_WEB_BODY_FONT_PIXELS,
            "web_minimum_font_pixels": round(FIGURE_WEB_FONT_MIN_PIXELS, 2),
            "web_maximum_font_pixels": round(FIGURE_WEB_FONT_MAX_PIXELS, 2),
            "body_font_points": MANUAL_PDF_BODY_FONT_POINTS,
            "minimum_font_points": DIAGRAM_PDF_FONT_MIN_POINTS,
            "maximum_font_points": DIAGRAM_PDF_FONT_MAX_POINTS,
            "maximum_height_points": DIAGRAM_PDF_HEIGHT_MAX_POINTS,
            "references": [item for item in figure_typography if item.get("visual_kind") == "diagram"],
            "findings": [item for item in figure_typography_findings if item.get("visual_kind") == "diagram"],
        },
    }


def manual_editorial_quality_check(project: Path) -> dict[str, Any]:
    project = project_path(project)
    paths = _manual_markdown_paths(project)
    findings: list[dict[str, Any]] = []

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        in_front_matter = bool(lines and lines[0].strip() == "---")
        in_fence = False
        fence_marker = ""
        in_html_comment = False
        in_liquid_comment = False
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            if in_front_matter:
                if lineno > 1 and stripped == "---":
                    in_front_matter = False
                continue
            if in_html_comment:
                if "-->" in line:
                    in_html_comment = False
                continue
            if in_liquid_comment:
                if "{% endcomment %}" in line:
                    in_liquid_comment = False
                continue
            if "<!--" in line:
                if "-->" not in line.split("<!--", 1)[1]:
                    in_html_comment = True
                line = line.split("<!--", 1)[0]
                stripped = line.strip()
            if "{% comment %}" in line:
                in_liquid_comment = "{% endcomment %}" not in line.split("{% comment %}", 1)[1]
                line = line.split("{% comment %}", 1)[0]
                stripped = line.strip()
            if in_fence:
                if stripped.startswith(fence_marker):
                    in_fence = False
                    fence_marker = ""
                continue
            fence_match = FENCE_RE.match(line)
            if fence_match:
                in_fence = True
                fence_marker = fence_match.group(1)
                continue
            if not stripped:
                continue

            for rule, pattern, message in MANUAL_EDITORIAL_RULES:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": rel(project, path),
                            "line": lineno,
                            "rule": rule,
                            "excerpt": stripped[:240],
                            "message": message,
                        }
                    )

    grouped: list[dict[str, Any]] = []
    for rule, _, message in MANUAL_EDITORIAL_RULES:
        matches = [item for item in findings if item["rule"] == rule]
        if matches:
            grouped.append({"severity": "error", "rule": rule, "message": message, "count": len(matches), "sample": matches[:20]})

    writing_profile = project / "context" / "writing-profile.md"
    warnings: list[dict[str, Any]] = []
    if not writing_profile.is_file():
        warnings.append(
            {
                "severity": "warning",
                "message": "Add context/writing-profile.md so drafting and review agents have project-specific voice and style rules.",
            }
        )

    return {
        "project": str(project),
        "ok": not findings,
        "files_checked": len(paths),
        "writing_profile": rel(project, writing_profile) if writing_profile.is_file() else "",
        "issues": grouped,
        "warnings": warnings,
        "findings": findings,
        "review_checklist": [
            "Every body paragraph must read as final material for the intended reader.",
            "No passage may mention the user, author instructions, agent actions, chat history, drafting status, or approval workflow.",
            "Give each paragraph one primary job and, when appropriate, develop topic, problem, arguments or examples, discussion or limits, and a concrete closure.",
            "Choose callouts, definition lists, figure layouts, tables, diagrams, citations, code, and math for a pedagogical purpose and check web/PDF compatibility.",
            "Check spelling, grammar, terminology, factual precision, pedagogical sequence, citations, captions, and cross-references before approval.",
            "Keep editorial plans and unresolved decisions in AGENTS.md, context/, issues, or review notes outside publishable Markdown bodies.",
        ],
    }


def manual_authoring_capabilities(project: Path) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    unaltraweb = config.get("unaltraweb") if isinstance(config.get("unaltraweb"), dict) else {}
    manual = unaltraweb.get("manual") if isinstance(unaltraweb.get("manual"), dict) else {}
    pdf = manual.get("pdf") if isinstance(manual.get("pdf"), dict) else {}
    return {
        "project": str(project),
        "site_profile": site_profile(config),
        "features": feature_flags(config),
        "languages": configured_languages(config),
        "pdf_enabled": bool(pdf.get("enabled", False)),
        "paragraph_structure": {
            "principle": "Diagnose function before sentence polish; give each paragraph one primary job and a concrete handoff.",
            "diagnostic_sequence": ["topic_or_reader_goal", "problem_or_question", "arguments_and_examples", "discussion_or_limits", "concrete_closure_or_transition"],
            "note": "Do not force every paragraph through every move. Use the sequence to find missing logic and combine moves only when they serve one clear purpose.",
        },
        "components": [
            {
                "id": "heading_levels",
                "syntax": ["## numbered section", "### numbered subsection", "#### numbered fourth-level subsection"],
                "web": "all three are numbered; h2 and h3 appear in the secondary TOC, h4 does not",
                "pdf": "all three are numbered; h4 remains below the configured TOC depth",
                "guidance": "Use #### for a cohesive minor subsection with its own developed content. Do not imitate a heading with a standalone bold phrase and terminal period.",
            },
            {
                "id": "callouts",
                "syntax": ["> quotation", ">> note", ">>> example", ">>>> warning", ">>>>> learning objectives", ">>>>>> caution"],
                "web": "supported with localized labels and nested-blockquote styling",
                "pdf": "supported with the same localized labels and styled callout boxes",
                "guidance": "Do not type the generated callout label in the body. Use learning-objective callouts sparingly, normally once after a brief chapter or major-section introduction; use prose, tables, or ordinary notes for mid-section criteria.",
            },
            {
                "id": "definition_lists",
                "syntax": ["Term", ": Definition"],
                "web": "supported and styled as dictionary entries",
                "pdf": "supported as indented description entries with term colons",
                "guidance": "Use for compact terminology, not as a substitute for conceptual explanation.",
            },
            {
                "id": "figures",
                "syntax": [
                    '![Alt text](assets/img/example.png "Explicit caption")',
                    '![Alt text](assets/img/example.png "Explicit caption"){: data-figure-width="22rem"}',
                    '![Alt text](assets/img/example.svg "Explicit caption"){: data-figure-width-web="44rem" data-figure-width-pdf="82%"}',
                ],
                "web": "supported with localized numbering; data-figure-width-web and data-figure-height-web control the web box independently",
                "pdf": "supported; data-figure-width-pdf and data-figure-height-pdf become Pandoc print constraints with aspect ratio preserved",
                "guidance": "Always provide meaningful alt text and an explicit Markdown title caption. Keep height auto unless a real support limit requires a maximum. Use data-figure-width as a compatible shared fallback, or support-specific attributes when web and PDF need different visible sizes. Run manual_source_quality_check after inserting a text-bearing SVG: it compares the smallest embedded text with body text on both supports and returns suggested dimensions. For localized visuals, reference the unsuffixed default-language source; add .<lang> before the complete suffix only when a translated visual is needed. Missing localized variants fall back to the default source. To publish a figure computed with R or Python, reference the executable source instead of its SVG and let the build rewrite it to the declared mode:figure output (see executable_sources).",
            },
            {
                "id": "subfigures",
                "syntax": ['::: subfigures a+b/c "Overall caption"', '![Panel A](a.png "Panel caption")', ":::"] ,
                "web": "supported; + joins panels in a row and / starts a new row",
                "pdf": "supported with the declared rows, panel captions, and shared caption; inspect the rendered PDF for legibility",
                "guidance": "Use when direct comparison is the teaching task: before/after states, controlled alternatives, a short sequence, or complementary views that benefit from one shared caption and number. Prefer compact layouts such as a+b or a+b/c, keep panel captions specific, and use the component selectively. Do not group images only because they share a topic, and avoid consecutive multi-panel blocks that weaken emphasis or legibility.",
            },
            {
                "id": "captioned_tables",
                "syntax": ['::: table "Caption"', "| Column | Column |", "| --- | --- |", ":::"] ,
                "web": "supported with localized numbering",
                "pdf": "supported through Pandoc table captions",
                "guidance": "Bare pipe tables are rejected by manual_source_quality_check. Inline code spans in cells are rendered by the core table parser; update the consumer lock file if literal backticks appear in numbered tables.",
            },
            {
                "id": "diagrams",
                "syntax": ['![Flow](assets/diagrams/flow.mmd "Flow caption")', '![Folders](assets/diagrams/folders.puml "Folder layout")'],
                "web": "supported through diavisuals-generated SVGs",
                "pdf": "supported for .mmd, .mermaid, .puml, .plantuml, and .uml when a printable SVG exists",
                "guidance": "Keep source files under assets/diagrams, prefer PlantUML @startfiles for file trees, and never overwrite *.edited.svg without approval. Use manual_source_quality_check to compare embedded diagram text with body text on web and PDF, keep effective PDF text between 8 pt and the 11 pt body size, and keep print height at or below 600 pt. Apply its separate web/PDF width suggestions when feasible; simplify or split diagrams when no legible dimensions fit.",
            },
            {
                "id": "vega_visualizations",
                "syntax": [
                    '![Bars](assets/charts/bars.vl.json "Quarterly bars")',
                    '![Network](assets/charts/network.vg.json "Network overview"){: data-figure-width="42rem"}',
                    ".vegavisuals.yml: source -> output",
                ],
                "web": "the source reference is rewritten to its single manifest-declared SVG or PNG output; PDF cannot be embedded in an HTML img",
                "pdf": "uses the same checked manifest output; SVG is recommended for web/PDF parity",
                "guidance": "Declare each referenced .vl.json or .vg.json source exactly once in .vegavisuals.yml, render with the companion vegavisuals factory, commit the output and lock, and never publish while visualization_check reports stale or modified output.",
            },
            {
                "id": "citations",
                "syntax": ["{% cite key %}", "{% cite key1 key2 %}"],
                "web": "supported through Jekyll Scholar",
                "pdf": "supported through linked Pandoc citeproc citations",
                "guidance": "Use verified bibliography keys and manual_references: true when a chapter needs its references section. Bibliographic citations use the citation color, distinct from external URLs and internal links.",
            },
            {
                "id": "links_and_cross_references",
                "syntax": ["[External](https://example.org/)", "## Stable heading {#stable-heading}", "[Internal](#stable-heading)"],
                "web": "external and internal links are supported with distinct semantic colors",
                "pdf": "external URLs and internal links are supported with distinct hyperref colors",
                "guidance": "Use explicit stable heading identifiers for cross-section links. Link text should name the destination; automatic figure and table number references are not currently generated.",
            },
            {
                "id": "code_and_math",
                "syntax": ["`inline_code()`", "```python ... ```", "$x_i$", "$$\nE = mc^2\n\\label{eq:model}\n$$", "$\\eqref{eq:model}$", "\\begin{equation*} ... \\end{equation*}"],
                "web": "inline code and Rouge-highlighted language fences; MathJax math with display equations numbered by default",
                "pdf": "styled inline code and Pandoc Skylighting language fences; LaTeX math with display equations numbered by default",
                "guidance": "Use explicit language names on fences. Use $...$ for inline math and $$ on separate lines for display math; display equations are numbered by default. Add \\label{eq:...} inside the display block and use $\\eqref{eq:...}$ for a cross-reference. Use equation* only when a displayed expression explicitly does not need a number. Do not use inline code for mathematical variables or \\(...\\) directly in Markdown sources.",
            },
            {
                "id": "executable_sources",
                "syntax": ["chapter.qmd -> chapter.md", "analysis.py -> analysis.md", "analysis.R -> analysis.md", "mode: figure -> declared SVG/PNG outputs"],
                "web": "the versioned generated Markdown and/or declared figure outputs are published; executable sources are excluded",
                "pdf": "uses the same checked generated Markdown and figures as the web build",
                "guidance": "When an executable source exists, edit it rather than generated artefacts. Declare one r or python engine per source, use mode: figure for reusable figures without generated chapter Markdown, list non-code inputs, render explicitly, and never publish while manual_computation_check reports stale outputs.",
            },
            {
                "id": "web_captures",
                "syntax": ["page.capture.yml -> page.capture.png + page.capture.svg", "page.capture.edited.svg"],
                "web": "publishes the generated or author-edited self-contained SVG; recipe and original PNG remain source artefacts",
                "pdf": "uses the same generated or author-edited SVG as the web build",
                "guidance": "Define local paths, waits, themes, and CSS selectors in a .capture.yml recipe. Preserve the original PNG, edit vector layers only in .capture.edited.svg, and never publish while web_capture_check reports stale outputs or an obsolete edited override.",
            },
        ],
        "web_only_or_pdf_review_required": ["tabs", "details", "interactive charts", "interactive maps", "galleries", "audio", "video", "arbitrary Liquid figure includes"],
        "quality_tools": ["manual_source_quality_check", "manual_editorial_quality_check", "manual_computation_check", "web_capture_check", "visualization_check", "build_site", "manual_pdf_build"],
        "source_guides": [
            "docs/agents/manual-authoring-components.md",
            "plugins/unaltraweb-site/skills/manual-pedagogical-writing/SKILL.md",
            "context/writing-profile.md",
        ],
    }


def profile_check(project: Path) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    profile = site_profile(config)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not (project / "_config.yml").is_file():
        issues.append({"severity": "error", "message": "Missing _config.yml"})
    if not profile:
        issues.append({"severity": "error", "message": "Missing unaltraweb.site_profile"})
    elif profile not in PROFILE_CONTRACTS:
        issues.append({"severity": "error", "message": f"Unknown site profile: {profile}"})

    contract = PROFILE_CONTRACTS.get(profile, {})
    for path in contract.get("recommended_paths", []):
        if not (project / path).exists():
            warnings.append({"severity": "warning", "message": f"Recommended path is missing for {profile}: {path}"})

    for key in contract.get("config_keys", []):
        cursor: Any = config
        for part in str(key).split("."):
            cursor = cursor.get(part) if isinstance(cursor, dict) else None
        if cursor is None or cursor == "":
            warnings.append({"severity": "warning", "message": f"Recommended config key is missing for {profile}: {key}"})

    missing_front_matter: list[dict[str, Any]] = []
    for path in iter_content_files(project):
        relative = rel(project, path)
        front = read_front_matter(path)
        required = ["title"]
        if relative.startswith(("_pages/", "_documentation/", "_chapters/", "_projects/", "_outputs/")):
            required.extend(["lang", "ref"])
        absent = [key for key in required if not front.get(key)]
        if absent:
            missing_front_matter.append({"path": relative, "missing": absent})

    if missing_front_matter:
        warnings.append(
            {
                "severity": "warning",
                "message": "Some content files are missing recommended front matter.",
                "count": len(missing_front_matter),
                "sample": missing_front_matter[:20],
            }
        )

    manual_source_quality: dict[str, Any] = {}
    manual_editorial_quality: dict[str, Any] = {}
    if profile == "unaltremanual":
        manual_source_quality = manual_source_quality_check(project)
        issues.extend(manual_source_quality.get("issues", []))
        warnings.extend(manual_source_quality.get("warnings", []))
        manual_editorial_quality = manual_editorial_quality_check(project)
        issues.extend(manual_editorial_quality.get("issues", []))
        warnings.extend(manual_editorial_quality.get("warnings", []))

    return {
        "project": str(project),
        "profile": profile,
        "contract": contract,
        "default_language": default_language(config),
        "languages": configured_languages(config),
        "features": feature_flags(config),
        "manual_source_quality": manual_source_quality,
        "manual_editorial_quality": manual_editorial_quality,
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
    }


def _collection_root(relative: str) -> str:
    parts = Path(relative).parts
    return parts[0] if parts else ""


def _infer_content_language(project: Path, path: Path, front: dict[str, Any], config: dict[str, Any]) -> str:
    explicit = str(front.get("lang") or "").strip()
    if explicit:
        return explicit
    languages = configured_languages(config)
    relative_parts = Path(rel(project, path)).parts
    for part in relative_parts:
        if part in languages:
            return part
    match = POST_LANG_RE.match(path.name)
    if match and match.group(1) in languages:
        return match.group(1)
    return default_language(config)


def _content_status(front: dict[str, Any], status_field: str) -> str:
    value = front.get(status_field)
    return str(value).strip() if value is not None else ""


def _content_record(project: Path, path: Path, config: dict[str, Any], *, status_field: str, approved_value: str) -> dict[str, Any]:
    front = read_front_matter(path)
    status = _content_status(front, status_field)
    return {
        "path": rel(project, path),
        "collection": _collection_root(rel(project, path)),
        "lang": _infer_content_language(project, path, front, config),
        "ref": str(front.get("ref") or "").strip(),
        "title": str(front.get("title") or "").strip(),
        "status": status,
        "approved": status == approved_value,
    }


def _suggest_translation_path(source_path: str, source_lang: str, target_lang: str) -> str:
    path = Path(source_path)
    parts = list(path.parts)
    for index, part in enumerate(parts[:-1]):
        if part == source_lang:
            parts[index] = target_lang
            return str(Path(*parts))
    filename = path.name
    replaced = POST_LANG_RE.sub(lambda match: match.group(0).replace(f"-{source_lang}-", f"-{target_lang}-", 1), filename)
    if replaced != filename:
        return str(path.with_name(replaced))
    if len(parts) > 1:
        return str(Path(parts[0]) / target_lang / filename)
    return str(path.with_name(f"{path.stem}-{target_lang}{path.suffix}"))


def language_policy(project: Path) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    languages = configured_languages(config)
    default_lang = default_language(config)
    editorial = editorial_config(config)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not default_lang:
        issues.append({"severity": "error", "message": "No default language configured. Set default_lang or lang in _config.yml."})
    if default_lang and languages and default_lang not in languages:
        issues.append({"severity": "error", "message": "Default language is not listed in languages.", "default_language": default_lang, "languages": languages})
    if not languages:
        warnings.append({"severity": "warning", "message": "No languages list configured; multilingual translation planning will be limited."})

    return {
        "project": str(project),
        "default_language": default_lang,
        "languages": languages,
        "translation_languages": [lang for lang in languages if lang != default_lang],
        "status_field": editorial["status_field"],
        "approved_value": editorial["approved_value"],
        "workflow": [
            "Draft, edit, and approve meaningful content in the default language first.",
            "Treat translations as pre-publication work after the default-language source is approved.",
            "Keep lang and ref stable across localized versions.",
            "Use translation_plan before publication to find missing or premature translations.",
        ],
        "visual_assets": {
            "default_source": "Use an unsuffixed visual source for the configured default language.",
            "localized_variant": "Insert .<lang> before the complete recognized suffix, for example map.ca.svg, plot.ca.qmd, bars.ca.vl.json, or flow.ca.puml.",
            "fallback": "When a localized source is absent, web and PDF use the unsuffixed default source. A present localized source with a missing or invalid generated output remains an error.",
        },
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
    }


def content_approval_inventory(project: Path, *, status_field: str = "", approved_value: str = "") -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    editorial = editorial_config(config)
    status_field = status_field or editorial["status_field"]
    approved_value = approved_value or editorial["approved_value"]
    default_lang = default_language(config)
    records = [_content_record(project, path, config, status_field=status_field, approved_value=approved_value) for path in iter_content_files(project)]
    by_status: dict[str, int] = {}
    for record in records:
        status = str(record["status"] or "missing")
        by_status[status] = by_status.get(status, 0) + 1
    default_records = [record for record in records if record["lang"] == default_lang]
    approved_default = [record for record in default_records if record["approved"]]
    pending_default = [record for record in default_records if not record["approved"]]
    return {
        "project": str(project),
        "default_language": default_lang,
        "status_field": status_field,
        "approved_value": approved_value,
        "content_count": len(records),
        "status_counts": dict(sorted(by_status.items())),
        "default_language_count": len(default_records),
        "approved_default_count": len(approved_default),
        "pending_default_count": len(pending_default),
        "pending_default_sample": pending_default[:40],
        "records_sample": records[:80],
    }


def translation_plan(project: Path, *, target_langs: list[str] | str | None = None, status_field: str = "", approved_value: str = "") -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    editorial = editorial_config(config)
    status_field = status_field or editorial["status_field"]
    approved_value = approved_value or editorial["approved_value"]
    languages = configured_languages(config)
    default_lang = default_language(config)
    targets = _parse_languages(target_langs)
    if not targets:
        targets = [lang for lang in languages if lang != default_lang]

    records = [
        _content_record(project, path, config, status_field=status_field, approved_value=approved_value)
        for path in iter_content_files(project)
        if _collection_root(rel(project, path)) in TRANSLATABLE_CONTENT_DIRS
    ]
    with_ref = [record for record in records if record["ref"]]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in with_ref:
        groups.setdefault((str(record["collection"]), str(record["ref"])), []).append(record)

    ready_sources: list[dict[str, Any]] = []
    blocked_sources: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    existing: list[dict[str, Any]] = []
    premature: list[dict[str, Any]] = []
    orphan_translations: list[dict[str, Any]] = []

    for key, group in sorted(groups.items()):
        source = next((record for record in group if record["lang"] == default_lang), None)
        if source is None:
            orphan_translations.extend(record for record in group if record["lang"] in targets)
            continue
        if source["approved"]:
            ready_sources.append(source)
            for target in targets:
                translation = next((record for record in group if record["lang"] == target), None)
                if translation:
                    existing.append({"source": source["path"], "target": translation["path"], "target_lang": target, "status": translation["status"]})
                else:
                    missing.append(
                        {
                            "source": source["path"],
                            "target_lang": target,
                            "suggested_path": _suggest_translation_path(str(source["path"]), default_lang, target),
                            "ref": source["ref"],
                            "title": source["title"],
                        }
                    )
        else:
            blocked_sources.append(source)
            for target in targets:
                translation = next((record for record in group if record["lang"] == target), None)
                if translation:
                    premature.append({"source": source["path"], "target": translation["path"], "target_lang": target, "source_status": source["status"], "translation_status": translation["status"]})

    return {
        "project": str(project),
        "default_language": default_lang,
        "target_languages": targets,
        "status_field": status_field,
        "approved_value": approved_value,
        "ready_source_count": len(ready_sources),
        "blocked_source_count": len(blocked_sources),
        "missing_translation_count": len(missing),
        "existing_translation_count": len(existing),
        "premature_translation_count": len(premature),
        "orphan_translation_count": len(orphan_translations),
        "ready_sources_sample": ready_sources[:40],
        "blocked_sources_sample": blocked_sources[:40],
        "missing_translations": missing,
        "existing_translations_sample": existing[:80],
        "premature_translations_sample": premature[:80],
        "orphan_translations_sample": orphan_translations[:40],
        "rule": "Only default-language content with an approved editorial status is ready for translation.",
    }


def bibliography_files(project: Path) -> list[Path]:
    root = project / "_bibliography"
    return sorted(root.glob("*.bib")) if root.is_dir() else []


def bibliography_inventory(project: Path) -> dict[str, Any]:
    project = project_path(project)
    by_type: dict[str, int] = {}
    entries: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    duplicates: list[dict[str, str]] = []
    update_dates: list[str] = []
    for path in bibliography_files(project):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in BIB_ENTRY_RE.finditer(text):
            entry_type, key = match.group(1).lower(), match.group(2).strip()
            by_type[entry_type] = by_type.get(entry_type, 0) + 1
            if key in seen:
                duplicates.append({"key": key, "first": seen[key], "duplicate": rel(project, path)})
            seen[key] = rel(project, path)
            entries.append({"key": key, "type": entry_type, "path": rel(project, path)})
        update_dates.extend(re.findall(r"x_(?:biblio)?metrics_updated\s*=\s*[\{\"]([^\}\"]+)", text))
    return {
        "project": str(project),
        "files": [rel(project, path) for path in bibliography_files(project)],
        "entry_count": len(entries),
        "types": dict(sorted(by_type.items())),
        "duplicates": duplicates,
        "sample_entries": entries[:30],
        "bibliometrics_update_dates": sorted(set(update_dates)),
    }


def _safe_relative_path(project: Path, raw_path: str, *, default: str) -> Path:
    candidate = Path(raw_path or default)
    if candidate.is_absolute():
        raise ValueError("Only project-relative paths are allowed")
    resolved = (project / candidate).resolve()
    if project not in [resolved, *resolved.parents]:
        raise ValueError("Path escapes the project workspace")
    return resolved


def _bib_key(bibtex: str) -> str:
    match = BIB_ENTRY_RE.search(bibtex.strip())
    if not match:
        raise ValueError("BibTeX entry must start with @type{citekey,")
    return match.group(2).strip()


def bibliography_add_entry(project: Path, bibtex: str, path: str = "_bibliography/papers.bib", replace: bool = False) -> dict[str, Any]:
    project = project_path(project)
    target = _safe_relative_path(project, path, default="_bibliography/papers.bib")
    if not rel(project, target).startswith("_bibliography/"):
        raise ValueError("Bibliography writes are restricted to _bibliography/")
    entry = bibtex.strip()
    key = _bib_key(entry)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    duplicate = re.search(rf"(?m)^@\w+\s*\{{\s*{re.escape(key)}\s*,", existing) is not None
    if duplicate and not replace:
        return {"ok": False, "path": rel(project, target), "key": key, "error": "citekey already exists; pass replace=True only after user approval"}
    if duplicate and replace:
        pattern = re.compile(rf"(?ms)^@\w+\s*\{{\s*{re.escape(key)}\s*,.*?(?=^@\w+\s*\{{|\Z)")
        existing = pattern.sub(entry.rstrip() + "\n\n", existing).rstrip() + "\n"
    else:
        separator = "\n" if existing.endswith("\n") or not existing else "\n\n"
        existing = existing + separator + entry.rstrip() + "\n"
    target.write_text(existing, encoding="utf-8")
    return {"ok": True, "path": rel(project, target), "key": key, "replaced": duplicate and replace}


def bibliometrics_status(project: Path) -> dict[str, Any]:
    project = project_path(project)
    metrics_paths = [project / "_data" / "bibliometrics.yml", project / "_data" / "metrics.yml"]
    files: list[dict[str, Any]] = []
    updated_on = ""
    for path in metrics_paths:
        if not path.is_file():
            continue
        data = load_yaml_file(path)
        metrics = data.get("bibliometrics") or data.get("metrics") if isinstance(data, dict) else {}
        if isinstance(metrics, dict) and metrics.get("updated_on"):
            updated_on = str(metrics["updated_on"])
        if not updated_on:
            match = DATE_RE.search(path.read_text(encoding="utf-8", errors="ignore"))
            updated_on = match.group(0) if match else ""
        files.append({"path": rel(project, path), "updated_on": updated_on})
    bib = bibliography_inventory(project)
    return {
        "project": str(project),
        "summary_files": files,
        "updated_on": updated_on,
        "bibliography_entry_count": bib["entry_count"],
        "bibliography_update_dates": bib["bibliometrics_update_dates"],
    }


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def content_freshness_check(project: Path, max_bibliometrics_age_days: int = 180) -> dict[str, Any]:
    project = project_path(project)
    today = dt.date.today()
    warnings: list[dict[str, Any]] = []
    status = bibliometrics_status(project)
    updated = _parse_date(str(status.get("updated_on") or ""))
    if updated:
        age = (today - updated).days
        if age > max_bibliometrics_age_days:
            warnings.append({"severity": "warning", "message": "Bibliometrics summary looks stale", "updated_on": updated.isoformat(), "age_days": age})
    elif status.get("bibliography_entry_count", 0):
        warnings.append({"severity": "warning", "message": "Bibliography exists but no bibliometrics updated_on date was found"})

    future_dated: list[str] = []
    for directory in ["_posts", "_news"]:
        root = project / directory
        if not root.is_dir():
            continue
        for path in root.glob("*.md"):
            match = DATE_RE.search(path.name)
            if match:
                parsed = _parse_date(match.group(0))
                if parsed and parsed > today:
                    future_dated.append(rel(project, path))
    if future_dated:
        warnings.append({"severity": "warning", "message": "Future-dated posts/news found", "paths": future_dated})
    return {"project": str(project), "ok": not warnings, "bibliometrics": status, "warnings": warnings}


def build_health(project: Path) -> dict[str, Any]:
    project = project_path(project)
    site = project / "_site"
    html_files = sorted(site.rglob("*.html")) if site.is_dir() else []
    newest = max((path.stat().st_mtime for path in html_files), default=0)
    newest_iso = dt.datetime.fromtimestamp(newest).isoformat() if newest else ""
    return {
        "project": str(project),
        "site_dir_exists": site.is_dir(),
        "html_files": len(html_files),
        "newest_html_mtime": newest_iso,
        "sample": [rel(project, path) for path in html_files[:12]],
    }


def run_make(project: Path, target: str, *, extra_args: list[str] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    command = ["make", target, *(extra_args or [])]
    completed = subprocess.run(command, cwd=str(project), env=merged_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {"target": target, "command": command, "returncode": completed.returncode, "ok": completed.returncode == 0, "stdout": completed.stdout, "stderr": completed.stderr}


def run_factory_make(factory: Path, project: Path, target: str, *, extra_args: list[str] | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    factory_root = project_path(factory)
    project_root = project_path(project)
    unsafe = set("$`\"'\\\r\n")
    if any(character in str(path) for path in [factory_root, project_root] for character in unsafe):
        raise ValueError("Factory and project paths contain characters that are unsafe for Make delegation.")
    command = ["make", "--silent", "--no-print-directory", "-C", str(factory_root), target, f"PROJECT={project_root}", *(extra_args or [])]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(command, env=merged_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    payload: dict[str, Any] = {
        "target": target,
        "command": command,
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, dict):
                payload = {**parsed, "target": target, "command": command, "returncode": completed.returncode, "ok": completed.returncode == 0 and bool(parsed.get("ok", True)), "stderr": completed.stderr}
    return payload


def _computation_env(source: str = "", stale_only: bool = False) -> dict[str, str]:
    env: dict[str, str] = {}
    value = source.strip()
    if value:
        if Path(value).is_absolute() or ".." in Path(value).parts or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
            raise ValueError("Computation source must be a safe project-relative path.")
        env["COMPUTE_SOURCE"] = value
    if stale_only:
        env["COMPUTE_STALE_ONLY"] = "1"
    return env


def manual_computation_status(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-compute-status", env=_computation_env(source))


def manual_computation_check(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-compute-check", env=_computation_env(source))


def manual_computation_render(project: Path, factory: Path, source: str = "", *, confirm_overwrite: bool = False, stale_only: bool = False) -> dict[str, Any]:
    env = _computation_env(source, stale_only=stale_only)
    if confirm_overwrite:
        env["COMPUTE_CONFIRM_OVERWRITE"] = "1"
    return run_factory_make(factory, project, "manual-compute-render", env=env)


def manual_computation_render_figures(project: Path, factory: Path) -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-compute-render-figures", env={})


def _web_capture_env(source: str = "") -> dict[str, str]:
    env: dict[str, str] = {}
    value = source.strip()
    if value:
        if Path(value).is_absolute() or ".." in Path(value).parts or not re.fullmatch(r"[A-Za-z0-9_./-]+\.capture\.ya?ml", value):
            raise ValueError("Web capture source must be a safe project-relative *.capture.yml or *.capture.yaml path.")
        env["WEB_CAPTURE_SOURCE"] = value
    return env


def web_capture_status(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "web-capture-status", env=_web_capture_env(source))


def web_capture_check(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "web-capture-check", env=_web_capture_env(source))


def web_capture_render(project: Path, factory: Path, source: str = "", *, confirm_overwrite: bool = False) -> dict[str, Any]:
    env = _web_capture_env(source)
    if confirm_overwrite:
        env["WEB_CAPTURE_CONFIRM_OVERWRITE"] = "1"
    return _web_capture_render_isolated(project, factory, env)


def visualization_status(project: Path, factory: Path) -> dict[str, Any]:
    project = project_path(project)
    configured = (project / ".vegavisuals.yml").is_file()
    return {
        "ok": True,
        "configured": configured,
        "delegated": configured,
        "owner": "vegavisuals",
        "required_tool": "visualization_check" if configured else "",
        "message": (
            "Run visualization_check through the required vegavisuals MCP before building."
            if configured
            else "No .vegavisuals.yml; no Vega visualization check is required."
        ),
    }


def _require_site_runtime(project: Path, target: str) -> tuple[Path, dict[str, Any]]:
    project = project_path(project)
    detection = detect_site(project)
    if not detection["is_unaltraweb_site"]:
        raise RuntimeError(f"Not an unaltraweb consumer site: {project}")
    if not detection["runtime_targets"].get(target, False):
        make_target = target.replace("_", "-")
        raise RuntimeError(f"The consumer Makefile does not expose the required {make_target} target: {project}")
    return project, detection


def _site_profile_arg(site_profile_value: str) -> list[str]:
    value = site_profile_value.strip()
    if value and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Site profile must contain only letters, numbers, underscores, or hyphens.")
    return [f"SITE_PROFILE={value}"] if value else []


def build_site(project: Path, factory: Path, site_profile: str = "") -> dict[str, Any]:
    project, detection = _require_site_runtime(project, "build_native")
    args = [f"LOCAL_CORE={project_path(factory)}", *_site_profile_arg(site_profile)]
    result = run_make(project, "build-native", extra_args=args, env={"UNALTRAWEB_MCP_RUNTIME": "1"})
    return {**result, "runtime": "mcp-container", "nested_container": False, "site": detection}


PREVIEW_FACTORY_LABEL = "io.context.mcp-factory"
PREVIEW_ROLE_LABEL = "io.context.mcp-role"
PREVIEW_PROJECT_LABEL = "io.context.mcp-project"
PREVIEW_PORT_LABEL = "io.context.mcp-port"
PREVIEW_PROFILE_LABEL = "io.context.mcp-profile"
PREVIEW_BASEURL_LABEL = "io.context.mcp-baseurl"
PREVIEW_PATH_LABEL = "io.context.mcp-path"


def _docker(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["docker", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        raise RuntimeError(f"Docker is not available to the MCP runtime: {exc}") from exc


def _web_capture_render_isolated(project: Path, factory: Path, env: dict[str, str]) -> dict[str, Any]:
    project = project_path(project)
    if not _capture_runtime_available(project):
        return run_make(project, "web-capture-render", env=env)
    host_project, project_id, _ = _preview_identity(project)
    token = hashlib.sha256(f"{host_project}:{time.time_ns()}".encode("utf-8")).hexdigest()[:12]
    network = f"unaltraweb-capture-{token}"
    service = f"unaltraweb-capture-site-{token}"
    image = os.environ.get("UNALTRAWEB_MCP_IMAGE", "ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0")
    owner = os.environ.get("UNALTRAWEB_PROJECT_USER", f"{os.getuid()}:{os.getgid()}").strip()
    if not re.fullmatch(r"\d+:\d+", owner):
        raise RuntimeError("UNALTRAWEB_PROJECT_USER must use the uid:gid format.")

    created = _docker([
        "network", "create", "--internal",
        "--label", f"{PREVIEW_FACTORY_LABEL}=unaltraweb",
        "--label", f"{PREVIEW_ROLE_LABEL}=web-capture",
        "--label", f"{PREVIEW_PROJECT_LABEL}={project_id}",
        network,
    ])
    if created.returncode != 0:
        raise RuntimeError(created.stderr or created.stdout or "Could not create the isolated web capture network.")

    try:
        started = _docker([
            "run", "-d", "--name", service,
            "--label", f"{PREVIEW_FACTORY_LABEL}=unaltraweb",
            "--label", f"{PREVIEW_ROLE_LABEL}=web-capture-site",
            "--label", f"{PREVIEW_PROJECT_LABEL}={project_id}",
            "--user", owner,
            "--network", network,
            "--network-alias", service,
            "-e", "HOME=/tmp",
            "-e", "JEKYLL_ENV=development",
            "-v", f"{host_project}:/workspace",
            "-w", "/workspace",
            "--entrypoint", "make", image,
            "--no-print-directory", "serve-capture-native", "LOCAL_CORE=/opt/unaltraweb",
            "HOST=0.0.0.0", "PORT=4000", "LIVERELOAD=", "DEVELOPER_MODE=false", "PROFILE_DEMO_TITLES=0",
        ])
        if started.returncode != 0:
            raise RuntimeError(started.stderr or started.stdout or "Could not start the isolated web capture site.")

        ready = False
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            probe = _docker(["exec", service, "curl", "--silent", "--output", "/dev/null", "http://127.0.0.1:4000/"])
            if probe.returncode == 0:
                ready = True
                break
            running = _docker(["inspect", service, "--format", "{{.State.Running}}"])
            if running.returncode != 0 or running.stdout.strip().lower() != "true":
                break
            time.sleep(0.5)
        if not ready:
            logs = _preview_logs(service)
            raise RuntimeError(f"The isolated web capture site did not become ready.\n{logs}".strip())

        capture_env = {
            **env,
            "WEB_CAPTURE_BASE_URL": f"http://{service}:4000",
            "WEB_CAPTURE_DOCKER_NETWORK": network,
            "WEB_CAPTURE_SERVICE_HOST": service,
        }
        return run_factory_make(factory, project, "web-capture-render", env=capture_env)
    finally:
        _docker(["rm", "-f", service])
        _docker(["network", "rm", network])


def _preview_identity(project: Path) -> tuple[str, str, str]:
    host_project = os.environ.get("UNALTRAWEB_DOCKER_ROOT", "").strip() or str(project_path(project))
    if not Path(host_project).is_absolute():
        raise RuntimeError("UNALTRAWEB_DOCKER_ROOT must be an absolute host path.")
    project_id = hashlib.sha256(host_project.encode("utf-8")).hexdigest()[:16]
    return host_project, project_id, f"unaltraweb-preview-{project_id}"


def _preview_inspect(name: str) -> dict[str, Any] | None:
    completed = _docker(["inspect", name])
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        if "no such object" in message.lower() or "no such container" in message.lower():
            return None
        raise RuntimeError(message or f"Docker could not inspect {name}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Docker returned invalid inspect data for {name}") from exc
    return payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else None


def _preview_owned(info: dict[str, Any], project_id: str) -> bool:
    labels = info.get("Config", {}).get("Labels", {}) or {}
    return (
        labels.get(PREVIEW_FACTORY_LABEL) == "unaltraweb"
        and labels.get(PREVIEW_ROLE_LABEL) == "preview"
        and labels.get(PREVIEW_PROJECT_LABEL) == project_id
    )


def _preview_logs(name: str) -> str:
    completed = _docker(["logs", "--tail", "40", name])
    return (completed.stdout + completed.stderr).strip()


def _preview_payload(project: Path, info: dict[str, Any], *, include_logs: bool = False) -> dict[str, Any]:
    host_project, project_id, name = _preview_identity(project)
    labels = info.get("Config", {}).get("Labels", {}) or {}
    state = info.get("State", {}) or {}
    networks = info.get("NetworkSettings", {}).get("Networks", {}) or {}
    ip_address = next(
        (str(network.get("IPAddress") or "") for network in networks.values() if network.get("IPAddress")),
        "",
    )
    port = int(labels.get(PREVIEW_PORT_LABEL) or 0)
    route = str(labels.get(PREVIEW_PATH_LABEL) or "/")
    payload = {
        "project": str(project_path(project)),
        "host_project": host_project,
        "project_id": project_id,
        "container": name,
        "owned": _preview_owned(info, project_id),
        "running": bool(state.get("Running")),
        "status": str(state.get("Status") or ""),
        "exit_code": state.get("ExitCode"),
        "port": port,
        "profile": str(labels.get(PREVIEW_PROFILE_LABEL) or ""),
        "url": f"http://127.0.0.1:{port}{route}" if port else "",
        "internal_url": f"http://{ip_address}:{port}{route}" if ip_address and port else "",
    }
    if include_logs:
        payload["logs"] = _preview_logs(name)
    return payload


def preview_status(project: Path, *, include_logs: bool = False) -> dict[str, Any]:
    project = project_path(project)
    host_project, project_id, name = _preview_identity(project)
    info = _preview_inspect(name)
    if info is None:
        return {
            "ok": True,
            "project": str(project),
            "host_project": host_project,
            "project_id": project_id,
            "container": name,
            "running": False,
            "status": "absent",
        }
    payload = _preview_payload(project, info, include_logs=include_logs)
    return {"ok": bool(payload["owned"]), **payload}


def _wait_for_preview(project: Path, name: str, timeout_seconds: float) -> tuple[bool, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    ready = False
    while True:
        info = _preview_inspect(name)
        if info is None:
            break
        latest = _preview_payload(project, info)
        if not latest["running"]:
            break
        internal_url = str(latest.get("internal_url") or "")
        if internal_url and http_check(internal_url, timeout_seconds=1.0)["ok"]:
            ready = True
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)

    info = _preview_inspect(name)
    if info is not None:
        latest = _preview_payload(project, info, include_logs=not ready)
    return ready, latest


def preview_start(project: Path, *, port: int = 4000, site_profile: str = "", timeout_seconds: float = 60.0) -> dict[str, Any]:
    project, detection = _require_site_runtime(project, "serve_native")
    if not 1024 <= port <= 65535:
        raise ValueError("Preview port must be between 1024 and 65535.")
    if not 0 <= timeout_seconds <= 300:
        raise ValueError("Preview timeout must be between 0 and 300 seconds.")
    profile_args = _site_profile_arg(site_profile)
    host_project, project_id, name = _preview_identity(project)
    existing = _preview_inspect(name)
    if existing is not None:
        if not _preview_owned(existing, project_id):
            raise RuntimeError(f"Refusing to replace unowned Docker container: {name}")
        status = _preview_payload(project, existing, include_logs=True)
        if status["running"]:
            requested_profile = site_profile.strip()
            if status["port"] != port or status["profile"] != requested_profile:
                raise RuntimeError(
                    f"Preview {name} is already running on port {status['port']} with profile "
                    f"{status['profile'] or '(default)'}. Stop it before changing preview settings."
                )
            ready, latest = _wait_for_preview(project, name, timeout_seconds)
            return {"ok": ready, "already_running": True, "ready": ready, "site": detection, **latest}
        removed = _docker(["rm", name])
        if removed.returncode != 0:
            raise RuntimeError(removed.stderr or removed.stdout)

    config = site_config(project)
    baseurl = str(config.get("baseurl") or "").strip()
    if baseurl == "/":
        baseurl = ""
    prefix = "/" + baseurl.strip("/") if baseurl else ""
    lang = default_language(config).strip("/")
    route = f"{prefix}/{lang}/" if lang else f"{prefix}/"
    image = os.environ.get("UNALTRAWEB_MCP_IMAGE", "ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0")
    owner = os.environ.get("UNALTRAWEB_PROJECT_USER", "").strip()
    if owner and not re.fullmatch(r"\d+:\d+", owner):
        raise RuntimeError("UNALTRAWEB_PROJECT_USER must use the uid:gid format.")

    command = [
        "run", "-d", "--name", name,
        "--label", f"{PREVIEW_FACTORY_LABEL}=unaltraweb",
        "--label", f"{PREVIEW_ROLE_LABEL}=preview",
        "--label", f"{PREVIEW_PROJECT_LABEL}={project_id}",
        "--label", f"{PREVIEW_PORT_LABEL}={port}",
        "--label", f"{PREVIEW_PROFILE_LABEL}={site_profile.strip()}",
        "--label", f"{PREVIEW_BASEURL_LABEL}={baseurl}",
        "--label", f"{PREVIEW_PATH_LABEL}={route}",
        "-e", "HOME=/tmp",
        "-e", "JEKYLL_ENV=development",
        "-p", f"127.0.0.1:{port}:{port}",
        "-v", f"{host_project}:/workspace",
        "-w", "/workspace",
    ]
    if owner:
        command.extend(["--user", owner])
    command.extend([
        "--entrypoint", "make", image,
        "--no-print-directory", "serve-native", "LOCAL_CORE=/opt/unaltraweb",
        "HOST=0.0.0.0", f"PORT={port}", "LIVERELOAD=", "DEVELOPER_MODE=false",
        "PROFILE_DEMO_TITLES=0", *profile_args,
    ])
    started = _docker(command)
    if started.returncode != 0:
        raise RuntimeError(started.stderr or started.stdout)

    ready, latest = _wait_for_preview(project, name, timeout_seconds)
    return {"ok": ready, "already_running": False, "ready": ready, "site": detection, **latest}


def preview_stop(project: Path) -> dict[str, Any]:
    project = project_path(project)
    host_project, project_id, name = _preview_identity(project)
    info = _preview_inspect(name)
    if info is None:
        return {"ok": True, "project": str(project), "host_project": host_project, "container": name, "stopped": False}
    if not _preview_owned(info, project_id):
        raise RuntimeError(f"Refusing to remove unowned Docker container: {name}")
    removed = _docker(["rm", "-f", name])
    if removed.returncode != 0:
        raise RuntimeError(removed.stderr or removed.stdout)
    return {"ok": True, "project": str(project), "host_project": host_project, "container": name, "stopped": True}


def _manual_pdf_args(language: str) -> list[str]:
    value = language.strip()
    if value and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Manual PDF language must contain only letters, numbers, underscores, or hyphens.")
    return [f"MANUAL_PDF_LANG={value}"] if value else []


def manual_pdf_status(project: Path, factory: Path, language: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-pdf-status", extra_args=_manual_pdf_args(language))


def manual_pdf_build(project: Path, factory: Path, language: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-pdf-build", extra_args=_manual_pdf_args(language))


def manual_pdf_publish(project: Path, factory: Path, language: str = "", *, dry_run: bool = True, confirm_publish: bool = False) -> dict[str, Any]:
    if not dry_run and not confirm_publish:
        raise RuntimeError("A real manual PDF publication requires confirm_publish=True after reviewing the dry-run.")
    args = _manual_pdf_args(language)
    args.append(f"MANUAL_PDF_PUBLISH_DRY_RUN={1 if dry_run else 0}")
    result = run_factory_make(factory, project, "manual-pdf-publish", extra_args=args)
    return {**result, "dry_run": dry_run, "confirmed": confirm_publish}


def bibliometrics_check(project: Path, factory: Path) -> dict[str, Any]:
    return run_factory_make(factory, project, "metrics-check")


def bibliometrics_fetch_scimago(project: Path, factory: Path, scimago_input: str = "") -> dict[str, Any]:
    value = scimago_input.strip()
    path = Path(value)
    if value and (path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[A-Za-z0-9_./-]+\.(?:csv|rda)", value, flags=re.IGNORECASE)):
        raise ValueError("Scimago input must be a safe project-relative .csv or .rda path.")
    args = [f"SCIMAGO_INPUT={value}"] if value else []
    return run_factory_make(factory, project, "metrics-scimago-fetch", extra_args=args)


def bibliometrics_update(project: Path, factory: Path, *, fetch_scimago: bool = False, offline: bool = False, dry_run: bool = False, strict_external: bool = False, require_scimago: bool = False) -> dict[str, Any]:
    metrics_args: list[str] = []
    if offline:
        metrics_args.append("--offline")
    if dry_run:
        metrics_args.append("--dry-run")
    if strict_external:
        metrics_args.append("--strict-external")
    if require_scimago:
        metrics_args.append("--require-scimago")
    target = "metrics-update-all" if fetch_scimago else "metrics-update"
    extra = ["METRICS_ARGS=" + " ".join(metrics_args)] if metrics_args else []
    return run_factory_make(factory, project, target, extra_args=extra)


def http_check(base_url: str, paths: list[str] | None = None, timeout_seconds: float = 5.0) -> dict[str, Any]:
    paths = paths or ["/"]
    checks: list[dict[str, Any]] = []
    parsed_base = base_url.rstrip("/")
    for path in paths:
        url = parsed_base + (path if path.startswith("/") else "/" + path)
        try:
            with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
                checks.append({"url": url, "ok": 200 <= response.status < 400, "status": response.status, "reason": response.reason})
        except urllib.error.HTTPError as error:
            checks.append({"url": url, "ok": False, "status": error.code, "reason": str(error)})
        except OSError as error:
            checks.append({"url": url, "ok": False, "status": None, "reason": str(error)})
    return {"base_url": base_url, "ok": all(item["ok"] for item in checks), "checks": checks}


def prompt_text(factory: Path, name: str) -> str:
    spec = PROMPT_SPECS.get(name, {})
    source = str(spec.get("source") or "")
    path = factory / "docs" / "agents" / "action-prompts" / source
    if source and path.is_file():
        return path.read_text(encoding="utf-8")
    return f"Prompt `{name}` is not available in this unaltraweb checkout."


def prompt_inventory(factory: Path) -> dict[str, Any]:
    root = factory / "docs" / "agents" / "action-prompts"
    prompts = []
    for name, spec in PROMPT_SPECS.items():
        source = str(spec["source"])
        prompts.append({
            "name": name,
            "description": spec["description"],
            "arguments": spec["arguments"],
            "source": source,
            "available": (root / source).is_file(),
        })
    return {
        "factory": str(factory),
        "prompt_count": len(prompts),
        "all_available": all(prompt["available"] for prompt in prompts),
        "prompts": prompts,
    }


def site_check(project: Path, factory: Path, max_bibliometrics_age_days: int = 180) -> dict[str, Any]:
    project = project_path(project)
    checks = {
        "detection": detect_site(project),
        "profile": profile_check(project),
        "language": language_policy(project),
        "approval": content_approval_inventory(project),
        "translation": translation_plan(project),
        "freshness": content_freshness_check(project, max_bibliometrics_age_days),
        "computations": manual_computation_status(project, factory),
        "web_captures": web_capture_status(project, factory),
        "visualizations": visualization_status(project, factory),
        "bibliography": bibliography_inventory(project),
        "build_health": build_health(project),
    }
    ok = bool(checks["detection"]["is_unaltraweb_site"])
    ok = ok and all(not isinstance(check, dict) or check.get("ok") is not False for check in checks.values())
    return {"project": str(project), "ok": ok, **checks}


def site_context(project: Path, factory: Path | None = None) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    return {
        "project": str(project),
        "generated_at": utc_now(),
        "detection": detect_site(project),
        "title": str(config.get("title") or ""),
        "profile": site_profile(config),
        "language_policy": language_policy(project),
        "languages": configured_languages(config),
        "features": feature_flags(config),
        "content": content_inventory(project),
        "approval": content_approval_inventory(project),
        "bibliography": bibliography_inventory(project),
        "bibliometrics": bibliometrics_status(project),
        "build_health": build_health(project),
        "web_captures": web_capture_status(project, factory) if factory else {},
        "factory": str(factory) if factory else "",
    }


def list_tools() -> dict[str, Any]:
    return {
        "resources": ["web://site-context", "web://new-web-scaffolds", "web://starter-templates", "web://profile-contract", "web://manual-writing-guidance", "web://manual-authoring-components", "web://manual-computations", "web://web-captures", "web://profile-prune-plan", "web://content-inventory", "web://language-policy", "web://content-approval", "web://translation-plan", "web://bibliography", "web://bibliometrics", "web://build-health", "web://prompts"],
        "prompts": list(PROMPT_SPECS),
        "tools": ["new_web", "initialize_site", "starter_templates", "detect_site", "site_context", "site_check", "profile_check", "manual_source_quality_check", "manual_editorial_quality_check", "manual_authoring_capabilities", "manual_computation_status", "manual_computation_check", "manual_computation_render", "manual_computation_render_figures", "web_capture_status", "web_capture_check", "web_capture_render", "manual_pdf_status", "manual_pdf_build", "manual_pdf_publish", "profile_prune_plan", "profile_prune", "content_inventory", "language_policy", "content_approval_inventory", "translation_plan", "content_freshness_check", "bibliography_inventory", "bibliography_add_entry", "bibliometrics_check", "bibliometrics_update", "bibliometrics_fetch_scimago", "build_site", "build_health", "preview_start", "preview_status", "preview_stop", "http_check"],
    }


def dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
