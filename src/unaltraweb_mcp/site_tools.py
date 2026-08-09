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

BIB_ENTRY_RE = re.compile(r"(?m)^@(\w+)\s*\{\s*([^,\s]+)")
DATE_RE = re.compile(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b")

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
    return {
        "project": str(project),
        "generated_at": utc_now(),
        "collections": collections,
        "data_files": [rel(project, path) for path in data_files if path.is_file()],
        "assets_present": (project / "assets").is_dir(),
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


def _update_initialized_config(project: Path, *, site_profile_value: str, title: str, baseurl: str, url: str) -> dict[str, Any]:
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

    return {
        "project": str(project),
        "profile": profile,
        "contract": contract,
        "languages": configured_languages(config),
        "features": feature_flags(config),
        "ok": not issues,
        "issues": issues,
        "warnings": warnings,
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


def build_site(project: Path, site_profile: str = "") -> dict[str, Any]:
    args = [f"SITE_PROFILE={site_profile}"] if site_profile else []
    return run_make(project_path(project), "build", extra_args=args)


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
        "languages": configured_languages(config),
        "features": feature_flags(config),
        "content": content_inventory(project),
        "bibliography": bibliography_inventory(project),
        "bibliometrics": bibliometrics_status(project),
        "build_health": build_health(project),
        "factory": str(factory) if factory else "",
    }


def list_tools() -> dict[str, Any]:
    return {
        "resources": ["web://site-context", "web://starter-templates", "web://profile-contract", "web://profile-prune-plan", "web://content-inventory", "web://bibliography", "web://bibliometrics", "web://build-health", "web://prompts"],
        "prompts": ["start_site_session", "content_update", "manual_teaching_materials", "project_site_update", "documentation_update", "bibliography_entry", "bibliometrics_refresh", "build_and_review"],
        "tools": ["initialize_site", "starter_templates", "site_context", "site_check", "profile_check", "profile_prune_plan", "profile_prune", "content_inventory", "content_freshness_check", "bibliography_inventory", "bibliography_add_entry", "bibliometrics_check", "bibliometrics_update", "bibliometrics_fetch_scimago", "build_site", "build_health", "http_check"],
    }


def dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
