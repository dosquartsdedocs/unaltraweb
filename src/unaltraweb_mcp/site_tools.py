from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
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
        "content_notes": ["localized chapters", "manual home", "figures/tables", "teaching blocks", "manual bibliography"],
    },
    "unaltredocs": {
        "description": "Technical or operational documentation portal.",
        "recommended_paths": ["_documentation"],
        "config_keys": ["unaltraweb.documentation"],
        "content_notes": ["documentation home", "sectioned documentation", "reader profiles", "search"],
    },
}

SKIPPED_TEMPLATE_PARTS = {
    ".git",
    ".bundle",
    ".cache",
    ".jekyll-cache",
    "_site",
    "node_modules",
    "tmp",
    "vendor",
}


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
    return {
        "project": str(project),
        "generated_at": utc_now(),
        "collections": collections,
        "data_files": [rel(project, path) for path in data_files if path.is_file()],
        "assets_present": (project / "assets").is_dir(),
        "computation_sources": [rel(project, path) for path in computation_sources],
    }


def starter_templates(factory: Path) -> dict[str, Any]:
    factory = project_path(factory)
    candidates = [
        factory.parent / "unaltraweb-template",
        factory / "templates" / "site",
        factory / "templates" / "project",
    ]
    templates = []
    for candidate in candidates:
        templates.append(
            {
                "path": str(candidate),
                "available": (candidate / "_config.yml").is_file(),
                "has_makefile": (candidate / "Makefile").is_file(),
                "has_gemfile": (candidate / "Gemfile").is_file(),
            }
        )
    default = next((item["path"] for item in templates if item["available"]), "")
    return {"factory": str(factory), "default": default, "templates": templates}


def _resolve_template(factory: Path, template_path: str = "") -> Path:
    if template_path:
        template = Path(template_path).expanduser().resolve()
        if not (template / "_config.yml").is_file():
            raise ValueError(f"Template path does not look like an unaltraweb site template: {template}")
        return template
    status = starter_templates(factory)
    default = str(status.get("default") or "")
    if not default:
        raise ValueError("No starter template found. Pass template_path or place unaltraweb-template next to the factory checkout.")
    return Path(default)


def _should_skip_template_path(path: Path) -> bool:
    return any(part in SKIPPED_TEMPLATE_PARTS for part in path.parts)


def _yaml_scalar(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_inline_list(values: list[str]) -> str:
    return "[" + ", ".join(_yaml_scalar(value) for value in values) + "]"


def _replace_top_level_scalar(lines: list[str], key: str, value: str) -> tuple[list[str], bool]:
    replaced = False
    rendered = f"{key}: {_yaml_scalar(value)}"
    output = []
    for line in lines:
        if not replaced and line.startswith(f"{key}:"):
            output.append(rendered)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(rendered)
    return output, replaced


def _replace_unaltraweb_site_profile(lines: list[str], site_profile_value: str) -> tuple[list[str], bool]:
    rendered = f"  site_profile: {_yaml_scalar(site_profile_value)}"
    output: list[str] = []
    in_unaltraweb = False
    replaced = False
    inserted = False
    for line in lines:
        if line.startswith("unaltraweb:"):
            in_unaltraweb = True
            output.append(line)
            continue
        if in_unaltraweb and line and not line.startswith((" ", "\t")):
            if not replaced and not inserted:
                output.append(rendered)
                inserted = True
            in_unaltraweb = False
        if in_unaltraweb and line.startswith("  site_profile:"):
            output.append(rendered)
            replaced = True
            continue
        output.append(line)
    if in_unaltraweb and not replaced and not inserted:
        output.append(rendered)
        inserted = True
    if not any(line.startswith("unaltraweb:") for line in lines):
        output.extend(["unaltraweb:", rendered])
        inserted = True
    return output, replaced or inserted


def _replace_top_level_list(lines: list[str], key: str, values: list[str]) -> tuple[list[str], bool]:
    replaced = False
    rendered = f"{key}: {_yaml_inline_list(values)}"
    output = []
    for line in lines:
        if not replaced and line.startswith(f"{key}:"):
            output.append(rendered)
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(rendered)
    return output, replaced


def _update_initialized_config(project: Path, *, site_profile_value: str, title: str, baseurl: str, url: str, default_lang: str, languages: list[str]) -> dict[str, Any]:
    config_path = project / "_config.yml"
    if not config_path.is_file():
        return {"updated": False, "reason": "_config.yml not found"}
    lines = config_path.read_text(encoding="utf-8").splitlines()
    updates: list[str] = []
    if title:
        lines, _ = _replace_top_level_scalar(lines, "title", title)
        updates.append("title")
    if baseurl:
        lines, _ = _replace_top_level_scalar(lines, "baseurl", baseurl)
        updates.append("baseurl")
    if url:
        lines, _ = _replace_top_level_scalar(lines, "url", url)
        updates.append("url")
    if default_lang:
        lines, _ = _replace_top_level_scalar(lines, "lang", default_lang)
        lines, _ = _replace_top_level_scalar(lines, "default_lang", default_lang)
        updates.extend(["lang", "default_lang"])
    if languages:
        lines, _ = _replace_top_level_list(lines, "languages", languages)
        updates.append("languages")
    if site_profile_value:
        lines, _ = _replace_unaltraweb_site_profile(lines, site_profile_value)
        updates.append("unaltraweb.site_profile")
    config_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"updated": bool(updates), "path": rel(project, config_path), "keys": updates}


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
    project = project_path(project)
    factory = project_path(factory)
    if force and not confirm_overwrite:
        raise RuntimeError("force=True can overwrite existing website files; call again with confirm_overwrite=True only after user approval")
    if site_profile_value and site_profile_value not in PROFILE_CONTRACTS:
        raise ValueError(f"Unknown site profile: {site_profile_value}")

    template = _resolve_template(factory, template_path)
    language_values = _parse_languages(languages)
    if default_lang and language_values and default_lang not in language_values:
        language_values.insert(0, default_lang)
    project.mkdir(parents=True, exist_ok=True)
    config_existed_before = (project / "_config.yml").exists()
    copied: list[str] = []
    skipped_existing: list[str] = []
    skipped_template: list[str] = []
    overwritten: list[str] = []

    for root_raw, dirnames, filenames in os.walk(template):
        dirnames.sort()
        filenames.sort()
        root = Path(root_raw)
        root_relative = root.relative_to(template)
        skipped_dirs = [name for name in dirnames if name in SKIPPED_TEMPLATE_PARTS]
        for name in skipped_dirs:
            skipped_path = Path(name) if str(root_relative) == "." else root_relative / name
            skipped_template.append(str(skipped_path))
        dirnames[:] = [name for name in dirnames if name not in SKIPPED_TEMPLATE_PARTS]

        target_root = project if str(root_relative) == "." else project / root_relative
        target_root.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            source = root / filename
            relative = source.relative_to(template)
            if _should_skip_template_path(relative):
                skipped_template.append(str(relative))
                continue
            target = project / relative
            if target.exists() and not force:
                skipped_existing.append(str(relative))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and force:
                overwritten.append(str(relative))
            shutil.copy2(source, target)
            copied.append(str(relative))

    if config_existed_before and not force:
        config_update = {"updated": False, "path": "_config.yml", "reason": "existing _config.yml was left unchanged because force is false"}
    else:
        config_update = _update_initialized_config(
            project,
            site_profile_value=site_profile_value,
            title=title,
            baseurl=baseurl,
            url=url,
            default_lang=default_lang,
            languages=language_values,
        )
    return {
        "ok": True,
        "project": str(project),
        "template": str(template),
        "requested_site_profile": site_profile_value,
        "site_profile": site_profile(site_config(project)),
        "copied_count": len(copied),
        "copied": copied[:120],
        "skipped_existing_count": len(skipped_existing),
        "skipped_existing": skipped_existing[:120],
        "skipped_template": sorted(set(skipped_template))[:120],
        "overwritten_count": len(overwritten),
        "overwritten": overwritten[:120],
        "config_update": config_update,
        "next_steps": ["Run profile_check", "Run profile_prune_plan if the starter should be reduced to one profile", "Run build_site when dependencies are available"],
    }


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


def manual_source_quality_check(project: Path) -> dict[str, Any]:
    project = project_path(project)
    paths = _manual_markdown_paths(project)

    bare_tables: list[dict[str, Any]] = []
    inline_diagrams: list[dict[str, Any]] = []
    figures_without_title: list[dict[str, Any]] = []
    standalone_bold_labels: list[dict[str, Any]] = []
    learning_objective_callouts: list[dict[str, Any]] = []

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        in_front_matter = bool(lines and lines[0].strip() == "---")
        in_fence = False
        fence_marker = ""
        in_table_block = False
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
                "pdf": "partial: preserved as blockquotes without equivalent web labels or styling",
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
                ],
                "web": "supported with localized numbering; data-figure-width narrows and centres an individual figure container",
                "pdf": "supported; custom web container width requires rendered PDF review",
                "guidance": "Always provide meaningful alt text and an explicit Markdown title caption. Use data-figure-width only when the natural content is substantially narrower than the reading column; it does not set a fixed height.",
            },
            {
                "id": "subfigures",
                "syntax": ['::: subfigures a+b/c "Overall caption"', '![Panel A](a.png "Panel caption")', ":::"] ,
                "web": "supported; + joins panels in a row and / starts a new row",
                "pdf": "not yet layout-equivalent; inspect rendered PDF or use separate figures",
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
                "pdf": "supported for .mmd, .puml, and .plantuml when a printable SVG exists",
                "guidance": "Keep source files under assets/diagrams, prefer PlantUML @startfiles for file trees, and never overwrite *.edited.svg without approval.",
            },
            {
                "id": "citations",
                "syntax": ["{% cite key %}", "{% cite key1 key2 %}"],
                "web": "supported through Jekyll Scholar",
                "pdf": "supported through Pandoc citeproc",
                "guidance": "Use verified bibliography keys and manual_references: true when a chapter needs its references section.",
            },
            {
                "id": "code_and_math",
                "syntax": ["```python ... ```", "$x_i$", "$$\nE = mc^2\n$$"],
                "web": "supported",
                "pdf": "ordinary fenced code and LaTeX-compatible math supported",
                "guidance": "Use $...$ for inline math and $$ on separate lines for display math. Do not use inline code for mathematical variables or \\(...\\) directly in Markdown sources. Prefer ordinary fenced code with an explicit language and avoid PDF-unsupported Liquid widgets.",
            },
            {
                "id": "executable_sources",
                "syntax": ["chapter.qmd -> chapter.md", "analysis.py -> analysis.md", "analysis.R -> analysis.md", "mode: figure -> declared SVG/PNG outputs"],
                "web": "the versioned generated Markdown and/or declared figure outputs are published; executable sources are excluded",
                "pdf": "uses the same checked generated Markdown and figures as the web build",
                "guidance": "When an executable source exists, edit it rather than generated artefacts. Declare one r or python engine per source, use mode: figure for reusable figures without generated chapter Markdown, list non-code inputs, render explicitly, and never publish while manual_computation_check reports stale outputs.",
            },
        ],
        "web_only_or_pdf_review_required": ["tabs", "details", "interactive charts", "interactive maps", "galleries", "audio", "video", "arbitrary Liquid figure includes"],
        "quality_tools": ["manual_source_quality_check", "manual_editorial_quality_check", "build_site", "manual_pdf_build"],
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
    unsafe = set("$`\"'\\\r\n \t")
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


def _computation_env(source: str) -> dict[str, str]:
    value = source.strip()
    if not value:
        return {}
    if Path(value).is_absolute() or ".." in Path(value).parts or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        raise ValueError("Computation source must be a safe project-relative path.")
    return {"COMPUTE_SOURCE": value}


def manual_computation_status(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-compute-status", env=_computation_env(source))


def manual_computation_check(project: Path, factory: Path, source: str = "") -> dict[str, Any]:
    return run_factory_make(factory, project, "manual-compute-check", env=_computation_env(source))


def manual_computation_render(project: Path, factory: Path, source: str = "", *, confirm_overwrite: bool = False) -> dict[str, Any]:
    env = _computation_env(source)
    if confirm_overwrite:
        env["COMPUTE_CONFIRM_OVERWRITE"] = "1"
    return run_factory_make(factory, project, "manual-compute-render", env=env)


def build_site(project: Path, site_profile: str = "") -> dict[str, Any]:
    args = [f"SITE_PROFILE={site_profile}"] if site_profile else []
    return run_make(project_path(project), "build", extra_args=args)


def _manual_pdf_args(language: str) -> list[str]:
    value = language.strip()
    if value and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Manual PDF language must contain only letters, numbers, underscores, or hyphens.")
    return [f"MANUAL_PDF_LANG={value}"] if value else []


def manual_pdf_status(project: Path, language: str = "") -> dict[str, Any]:
    return run_make(project_path(project), "manual-pdf-status", extra_args=_manual_pdf_args(language))


def manual_pdf_build(project: Path, language: str = "") -> dict[str, Any]:
    return run_make(project_path(project), "manual-pdf-build", extra_args=_manual_pdf_args(language))


def manual_pdf_publish(project: Path, language: str = "", *, dry_run: bool = True, confirm_publish: bool = False) -> dict[str, Any]:
    if not dry_run and not confirm_publish:
        raise RuntimeError("A real manual PDF publication requires confirm_publish=True after reviewing the dry-run.")
    args = _manual_pdf_args(language)
    args.append(f"MANUAL_PDF_PUBLISH_DRY_RUN={1 if dry_run else 0}")
    result = run_make(project_path(project), "manual-pdf-publish", extra_args=args)
    return {**result, "dry_run": dry_run, "confirmed": confirm_publish}


def bibliometrics_check(project: Path) -> dict[str, Any]:
    return run_make(project_path(project), "metrics-check")


def bibliometrics_fetch_scimago(project: Path, scimago_input: str = "") -> dict[str, Any]:
    args = [f"SCIMAGO_INPUT={scimago_input}"] if scimago_input else []
    return run_make(project_path(project), "metrics-scimago-fetch", extra_args=args)


def bibliometrics_update(project: Path, *, fetch_scimago: bool = False, offline: bool = False, dry_run: bool = False, strict_external: bool = False, require_scimago: bool = False) -> dict[str, Any]:
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
    return run_make(project_path(project), target, extra_args=extra)


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


def prompt_inventory(factory: Path) -> dict[str, Any]:
    root = factory / "docs" / "agents" / "action-prompts"
    prompts = sorted(root.glob("*.txt")) if root.is_dir() else []
    return {"factory": str(factory), "prompts": [path.name for path in prompts]}


def site_context(project: Path, factory: Path | None = None) -> dict[str, Any]:
    project = project_path(project)
    config = site_config(project)
    return {
        "project": str(project),
        "generated_at": utc_now(),
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
        "factory": str(factory) if factory else "",
    }


def list_tools() -> dict[str, Any]:
    return {
        "resources": ["web://site-context", "web://starter-templates", "web://profile-contract", "web://manual-writing-guidance", "web://manual-authoring-components", "web://manual-computations", "web://profile-prune-plan", "web://content-inventory", "web://language-policy", "web://content-approval", "web://translation-plan", "web://bibliography", "web://bibliometrics", "web://build-health", "web://prompts"],
        "prompts": ["start_site_session", "content_update", "edit_default_content", "manual_teaching_materials", "manual_style_audit", "manual_structure_audit", "translation_prepublish", "project_site_update", "documentation_update", "bibliography_entry", "bibliometrics_refresh", "build_and_review"],
        "tools": ["initialize_site", "starter_templates", "site_context", "site_check", "profile_check", "manual_source_quality_check", "manual_editorial_quality_check", "manual_authoring_capabilities", "manual_computation_status", "manual_computation_check", "manual_computation_render", "manual_pdf_status", "manual_pdf_build", "manual_pdf_publish", "profile_prune_plan", "profile_prune", "content_inventory", "language_policy", "content_approval_inventory", "translation_plan", "content_freshness_check", "bibliography_inventory", "bibliography_add_entry", "bibliometrics_check", "bibliometrics_update", "bibliometrics_fetch_scimago", "build_site", "build_health", "http_check"],
    }


def dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
