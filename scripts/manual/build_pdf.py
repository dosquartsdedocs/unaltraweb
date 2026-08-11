#!/usr/bin/env python3
"""Build and locally publish unaltremanual PDFs from Jekyll sources."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - supplied by the builder image
    raise SystemExit("PyYAML is required to build an unaltremanual PDF.") from exc


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_ROOT / "templates" / "manual.tex"
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
CITE_RE = re.compile(r"{%\s*cite\s+([^%]+?)\s*%}")
INCLUDE_RE = re.compile(r"{%\s*include\s+([^%]+?)\s*%}")
LIQUID_RE = re.compile(r"({[{%].*?[}%]})", re.DOTALL)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((\S+?)(?:\s+[\"']([^\"']+)[\"'])?\)")
TABLE_DIV_RE = re.compile(r'^::: table\s+["\'](.+?)["\']\s*\n(.*?)^:::\s*$', re.MULTILINE | re.DOTALL)
LANGUAGE_NAMES = {"ca": "catalan", "es": "spanish", "en": "english"}
LANGUAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
METADATA_LABELS = {
    "ca": {
        "title": "Fitxa del manual",
        "subject": "Assignatura",
        "teaching_guides": "Guies docents",
        "academic_year": "Curs acadèmic",
        "department": "Departament",
        "faculty": "Facultat",
        "institution": "Institució",
        "location": "Localització",
        "revision_date": "Data de revisió",
        "instructors": "Professorat",
    },
    "es": {
        "title": "Ficha del manual",
        "subject": "Asignatura",
        "teaching_guides": "Guías docentes",
        "academic_year": "Curso académico",
        "department": "Departamento",
        "faculty": "Facultad",
        "institution": "Institución",
        "location": "Localización",
        "revision_date": "Fecha de revisión",
        "instructors": "Profesorado",
    },
    "en": {
        "title": "Manual details",
        "subject": "Course",
        "teaching_guides": "Teaching guides",
        "academic_year": "Academic year",
        "department": "Department",
        "faculty": "Faculty",
        "institution": "Institution",
        "location": "Location",
        "revision_date": "Revision date",
        "instructors": "Instructors",
    },
}


class ManualPdfError(RuntimeError):
    pass


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


def resolve_diagram(project: Path, raw_path: str) -> str:
    path = raw_path.lstrip("/")
    if not path.lower().endswith((".mmd", ".puml", ".plantuml")):
        return path
    source = safe_relative(project, path, label="diagram source", must_exist=True)
    candidates = [Path(str(source) + ".edited.svg"), Path(str(source) + ".svg")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.relative_to(project))
    raise ManualPdfError(f"No printable SVG found for diagram source: {path}")


def transform_markdown(project: Path, text: str, source: Path) -> str:
    text = text.replace("{{ site.baseurl }}", "")
    text = text.replace("{% include manual-bibliography.liquid %}", "::: {#refs}\n:::")

    def citations(match: re.Match[str]) -> str:
        keys = [key.lstrip("@").strip() for key in match.group(1).split() if key.strip()]
        return "[" + "; ".join(f"@{key}" for key in keys) + "]"

    def table(match: re.Match[str]) -> str:
        return f"Table: {match.group(1).strip()}\n\n{match.group(2).strip()}"

    def image(match: re.Match[str]) -> str:
        alt, raw_path, title = match.groups()
        printable = resolve_diagram(project, raw_path)
        caption = title or alt
        return f"![{caption}]({printable})"

    text = CITE_RE.sub(citations, text)
    text = TABLE_DIV_RE.sub(table, text)
    text = IMAGE_RE.sub(image, text)
    unknown_includes = [item for item in INCLUDE_RE.findall(text) if item.strip()]
    unknown_liquid = [item for item in LIQUID_RE.findall(text) if item.strip()]
    if unknown_includes or unknown_liquid:
        token = (unknown_includes or unknown_liquid)[0]
        raise ManualPdfError(f"Unsupported Liquid in {source.relative_to(project)}: {token}")
    return text.strip()


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
    return {
        "title": title,
        "short-title": localized(metadata.get("short_title"), source_lang) or str(config.get("short_title") or title),
        "description": localized(metadata.get("description"), source_lang) or localized(home_front.get("description"), source_lang) or str(config.get("description") or ""),
        "author": ", ".join(instructors),
        "instructors": instructors,
        "series": localized(metadata.get("series"), source_lang) or "unaltremanual",
        "series-subtitle": localized(metadata.get("series_subtitle"), source_lang),
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
        "rights": localized(metadata.get("rights"), source_lang) or f"© {config.get('copyright_holder') or ''}".strip(),
        "metadata-page-title": metadata_labels["title"],
        "metadata-subject-label": metadata_labels["subject"],
        "metadata-teaching-guides-label": metadata_labels["teaching_guides"],
        "metadata-academic-year-label": metadata_labels["academic_year"],
        "metadata-department-label": metadata_labels["department"],
        "metadata-faculty-label": metadata_labels["faculty"],
        "metadata-institution-label": metadata_labels["institution"],
        "metadata-location-label": metadata_labels["location"],
        "metadata-revision-date-label": metadata_labels["revision_date"],
        "metadata-instructors-label": metadata_labels["instructors"],
        "lang": lang,
        "babel-lang": LANGUAGE_NAMES.get(source_lang, "english"),
        "toc": bool(pdf.get("toc", True)),
        "nocite": "@*" if manual.get("bibliography", True) and bool(pdf.get("include_bibliography", True)) else "",
        "draft": draft and bool(pdf.get("mark_drafts", True)),
        "draft-label": localized(pdf.get("draft_label"), source_lang) or {"ca": "ESBORRANY", "es": "BORRADOR", "en": "DRAFT"}.get(source_lang, "DRAFT"),
        "draft-description": localized(pdf.get("draft_description"), source_lang) or {"ca": "Material en revisió. No és una versió final.", "es": "Material en revisión. No es una versión final.", "en": "Material under review. This is not a final version."}.get(source_lang, "Material under review."),
        "primary-color": str(cover.get("primary_color") or "990000").lstrip("#"),
        "band-color": str(cover.get("band_color") or cover.get("primary_color") or "990000").lstrip("#"),
        "secondary-color": str(cover.get("secondary_color") or "003366").lstrip("#"),
        "muted-color": str(cover.get("muted_color") or "666666").lstrip("#"),
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
    source_paths: list[Path] = []

    if home and bool(pdf.get("include_home", True)):
        home_front, body = read_source(home)
        body = transform_markdown(project, body, home)
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
        chunks.append(f"{heading}\n\n{transform_markdown(project, body, path)}")
        included_chapters.append((path, front, body))
        source_paths.append(path)

    metadata = build_metadata(project, config, lang, source_lang, home_front, included_chapters)
    return metadata, source_paths, "\n\n\\newpage\n\n".join(chunks) + "\n"


def bibliography_source(project: Path, config: dict[str, Any]) -> Path | None:
    manual = nested(config, "unaltraweb", "manual")
    if manual.get("bibliography", True) is False:
        return None
    filename = str(manual.get("bibliography_file") or "manual.bib")
    return safe_relative(project, f"_bibliography/{filename}", label="bibliography", must_exist=True)


def clean_bibliography(source: Path | None, destination: Path) -> None:
    if source is None:
        return
    text = source.read_text(encoding="utf-8")
    text = FRONT_MATTER_RE.sub("", text, count=1)
    destination.write_text(text, encoding="utf-8")


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
        (f"template:{template.name}", template),
    ]
    for path in source_paths:
        dependencies.append((f"source:{path.relative_to(project)}", path))
    if csl:
        dependencies.append((f"csl:{csl.relative_to(project)}", csl))
    for key in ["cover-image", "cover-logo", "series-logo"]:
        if metadata.get(key):
            path = safe_relative(project, str(metadata[key]), label=key, must_exist=True)
            dependencies.append((f"asset:{path.relative_to(project)}", path))
    for match in IMAGE_RE.finditer(markdown):
        raw = match.group(2)
        if raw.startswith(("http://", "https://", "data:", "#")):
            continue
        path = safe_relative(project, raw, label="manual image", must_exist=True)
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
    return metadata, source_paths, markdown, template, bibliography, csl, dependencies, fingerprint


def paths_in_build_dir(paths: dict[str, Path], build_dir: Path) -> dict[str, Path]:
    staged = dict(paths)
    staged["build_dir"] = build_dir
    for key in ["pdf", "cover", "source", "metadata", "bibliography", "manifest"]:
        staged[key] = build_dir / paths[key].name
    return staged


def run_command(command: list[str], project: Path) -> None:
    completed = subprocess.run(command, cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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
        staged["metadata"].write_text(yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8")
        clean_bibliography(bibliography, staged["bibliography"])
        command = [
            "pandoc",
            str(staged["source"]),
            "--from=markdown+fenced_divs+pipe_tables+link_attributes",
            "--standalone",
            "--top-level-division=chapter",
            "--number-sections",
            "--no-highlight",
            f"--metadata-file={staged['metadata']}",
            f"--template={template}",
            "--pdf-engine=xelatex",
            f"--resource-path={project}:{staged['build_dir']}",
            f"--output={staged['pdf']}",
        ]
        if bibliography:
            command.extend(["--citeproc", f"--bibliography={staged['bibliography']}"])
            if csl:
                command.append(f"--csl={csl}")
        run_command(command, project)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unaltraweb-manual-pdf")
    parser.add_argument("command", choices=["status", "build", "publish"])
    parser.add_argument("--project", default=".")
    parser.add_argument("--language", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    try:
        config = read_yaml(project / "_config.yml")
        pdf = nested(config, "unaltraweb", "manual", "pdf")
        languages = language_list(config, pdf, args.language)
        if args.command != "status" and not bool(pdf.get("enabled", False)):
            raise ManualPdfError("Manual PDF generation is disabled in unaltraweb.manual.pdf.enabled.")
        if args.command == "status":
            payload: dict[str, Any] = {
                "project": str(project),
                "enabled": bool(pdf.get("enabled", False)),
                "languages": [status_language(project, config, lang) for lang in languages],
            }
            payload["configuration_ok"] = payload["enabled"] and all(not item["error"] for item in payload["languages"])
            payload["ready_to_publish"] = payload["configuration_ok"] and all(item["ready_to_publish"] for item in payload["languages"])
            payload["ok"] = payload["ready_to_publish"]
        elif args.command == "build":
            results = [build_language(project, config, lang) for lang in languages]
            payload = {"project": str(project), "ok": True, "built": results}
        else:
            results = [publish_language(project, config, lang, args.dry_run) for lang in languages]
            payload = {"project": str(project), "ok": True, "dry_run": args.dry_run, "published": results}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    except (ManualPdfError, OSError, yaml.YAMLError) as exc:
        print(json.dumps({"project": str(project), "ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
