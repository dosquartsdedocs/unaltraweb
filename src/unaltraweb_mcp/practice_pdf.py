"""Factory-owned, private practice handouts; no site or Moodle publication.

Only a bounded snapshot of the selected Markdown, images and rendering controls
is exposed to the PDF toolchain. The consumer and factory checkouts are not
mounted in that worker. Jobs are retained, create-only, and sealed last.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any

from markdown_it import MarkdownIt
import yaml

from . import manual_pdf_preview as fs
from .docker_mount import docker_bind_mount
from .editorial_sources import Reader, canonical, digest, relative_path, strict_json, yaml_mapping
from .processes import run_process
from .runtime_lifecycle import inspect_image

SOURCE_RE = re.compile(r"practiques/([a-z0-9][a-z0-9-]{0,63})/(ca|es|en)/(alumnat|docent)/(LLEGIU-ME|LEEME|README)\.md\Z")
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
BASENAMES = {"ca": "LLEGIU-ME", "es": "LEEME", "en": "README"}
LABELS = {
    "ca": ("Guia de pràctica", "Guia docent", "Versió", "continuació"),
    "es": ("Guía de práctica", "Guía docente", "Versión", "continuación"),
    "en": ("Practice guide", "Instructor guide", "Version", "continued"),
}
PRIVATE_ROOTS = ("practiques", "sandbox", "dist")
MAX_ASSET_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf"}
FILTERS = ("practice-layout.lua", "code-blocks.lua", "figure-captions.lua", "practice-finish.lua")


def validate_request(source: str, version: str, run: str = "") -> tuple[str, str, str, str]:
    match = SOURCE_RE.fullmatch(source)
    if not match:
        raise ValueError("Use practiques/<slug>/<ca|es|en>/<alumnat|docent>/<LLEGIU-ME|LEEME|README>.md")
    slug, language, audience, basename = match.groups()
    if basename != BASENAMES[language]:
        raise ValueError("The practice reading filename must match its language")
    if not NAME_RE.fullmatch(version) or (run and not NAME_RE.fullmatch(run)):
        raise ValueError("Practice version and optional run must be safe names of at most 64 characters")
    return slug, language, audience, basename


def private_path_issues(config: dict[str, Any]) -> list[str]:
    excluded = config.get("exclude", [])
    included = config.get("include", [])
    if not isinstance(excluded, list) or not isinstance(included, list):
        return ["Jekyll exclude/include must be lists"]
    names = {value.rstrip("/") for value in excluded if isinstance(value, str)}
    issues = [f"Add {name}/ to _config.yml exclude" for name in PRIVATE_ROOTS if name not in names]
    for value in included:
        if isinstance(value, str):
            prefix = value.strip("/").split("/")[0]
            if value == "." or any(fnmatch.fnmatchcase(root, prefix)
                                   or fnmatch.fnmatchcase(root + "/LLEGIU-ME.md", value)
                                   or fnmatch.fnmatchcase(root + "/reading.pdf", value) for root in PRIVATE_ROOTS):
                issues.append(f"Jekyll include must not expose private practice paths: {value}")
    return issues


def _manual_builder(factory: Path):
    path = factory / "scripts/manual/build_pdf.py"
    spec = importlib.util.spec_from_file_location("unaltraweb_practice_manual_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("The factory-owned manual builder is required")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def practice_metadata(manual, project: Path, config: dict[str, Any], front: dict[str, Any],
                      source: str, language: str, audience: str, version: str) -> dict[str, Any]:
    # Metadata normalization is shared with the manual. Validate/copy the actual
    # selected logos separately through the descriptor-relative snapshot reader.
    normalized_config = copy.deepcopy(config)
    pdf_config = normalized_config["unaltraweb"].setdefault("manual", {}).setdefault("pdf", {})
    cover = pdf_config.setdefault("cover", {})
    for key in ("image", "institution_logo", "series_logo"):
        cover.pop(key, None)
    metadata = manual.build_metadata(project, normalized_config, language, language, {}, [(project / source, front, "")])
    title = front.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("The practice Markdown requires a title in its front matter")
    if front.get("lang", language) != language:
        raise ValueError("Practice front matter language differs from the source path")
    codes = list(dict.fromkeys(item["subject-code"] for item in metadata["teaching-guides"] if item["subject-code"]))
    if not codes and metadata["subject-code"]:
        codes = [metadata["subject-code"]]
    metadata.update({
        "course-short-title": metadata["short-title"],
        "subject": metadata["subject"] or " ".join(metadata["title"].split()),
        "title": title,
        "short-title": str(front.get("short_title") or title),
        "subject-codes": ", ".join(codes),
        "practice-version": version,
        "audience-label": LABELS[language][audience == "docent"],
        "practice-version-label": LABELS[language][2],
        "continuation-label": LABELS[language][3],
        "institution-line": " · ".join(metadata[key] for key in ("faculty", "institution", "location") if metadata[key]),
    })
    if re.sub(r"\s+", "", metadata["series"]).casefold() == "dosquartsdedocs":
        metadata["series"] = "dosquartsdedocs"
    return metadata


def practice_template(manual_template: str, wrapper: str) -> str:
    """Derive the article from the one existing typographic authority.

    Fail closed if its boundaries change, rather than silently copying a stale
    preamble or introducing book front matter into a private handout.
    """
    boundary = r"\usepackage{fancyhdr}"
    if manual_template.count(boundary) != 1:
        raise ValueError("Manual typographic preamble boundary changed")
    preamble = manual_template.split("\n", 1)[1].split(boundary)[0]
    chapter = r"\\titleformat\{\\chapter\}\[hang\].*?\\titlespacing\*\{\\chapter\}\{0pt\}\{36pt\}\{30pt\}\n"
    preamble, replacements = re.subn(chapter, "", preamble, flags=re.S)
    old_geometry = r"\geometry{inner=25mm,outer=22mm,top=24mm,bottom=26mm}"
    if replacements != 1 or preamble.count(old_geometry) != 1:
        raise ValueError("Manual chapter/geometry contract changed; review the practice wrapper")
    preamble = preamble.replace(old_geometry, r"\geometry{left=20mm,right=20mm,top=20mm,bottom=20mm,headheight=14pt,headsep=5mm,footskip=10mm}")
    return r"\documentclass[11pt,a4paper,oneside,landscape]{article}" + "\n" + preamble + wrapper


def _image_references(markdown: str) -> list[str]:
    references: list[str] = []

    def visit(tokens):
        for token in tokens:
            if token.type in {"text", "html_inline", "html_block"} and ("{%" in token.content or "{{" in token.content):
                raise ValueError("Practice v1 reads standalone Markdown; unresolved Liquid is not supported")
            if token.type == "image":
                references.append(token.attrGet("src") or "")
            if token.children:
                visit(token.children)

    visit(MarkdownIt().parse(markdown))
    unique = list(dict.fromkeys(references))
    if len(unique) > 200:
        raise ValueError("A practice handout supports at most 200 image references")
    return unique


def prepare(project: Path, factory: Path, source: str, version: str, image_id: str, run: str = "", *, source_root: str = "/source") -> dict[str, Any]:
    if source_root not in {"/source", "/work/inputs/prepared"}:
        raise ValueError("Unsupported practice execution root")
    slug, language, audience, basename = validate_request(source, version, run)
    manual = _manual_builder(factory)
    files: dict[str, bytes] = {}
    with Reader(project, max_bytes=MAX_ASSET_BYTES, max_total_bytes=MAX_TOTAL_BYTES) as reader:
        config = yaml_mapping(reader.text("_config.yml"))
        if manual.nested(config, "unaltraweb").get("site_profile") != "unaltremanual":
            raise ValueError("Practice PDFs require the unaltremanual profile")
        manual_config = config["unaltraweb"].get("manual", {})
        if (not isinstance(manual_config, dict) or not isinstance(manual_config.get("pdf", {}), dict)
                or not isinstance(manual_config.get("pdf", {}).get("cover", {}), dict)):
            raise ValueError("Manual, PDF and cover configuration must be mappings")
        issues = private_path_issues(config)
        if issues:
            raise ValueError("; ".join(issues))
        languages = config.get("languages") or [config.get("default_lang") or config.get("lang") or "en"]
        if language not in languages:
            raise ValueError("The practice language is not enabled in _config.yml")
        text = reader.text(source)
        if len(text.encode()) > 2 * 1024 * 1024:
            raise ValueError("Practice Markdown exceeds 2 MiB")
        match = manual.FRONT_MATTER_RE.match(text)
        front = yaml_mapping(match.group(1)) if match else {}
        markdown = text[match.end():] if match else text
        metadata = practice_metadata(manual, project, config, front, source, language, audience, version)

        def asset(raw: str, *, source_relative: bool = False) -> str:
            relative_path(raw)
            if Path(raw).suffix.lower() not in ASSET_SUFFIXES:
                raise ValueError("Practice v1 images must be local PNG, JPEG or PDF; render other figure sources first")
            content = reader.read(raw, optional=source_relative)
            if content is None:
                raw = (Path(source).parent / raw).as_posix()
                content = reader.read(raw)
            assert content is not None
            target = f"assets/{digest(content)}{Path(raw).suffix.lower()}"
            files[target] = content
            return source_root + "/" + target

        cover = manual.nested(config, "unaltraweb", "manual", "pdf", "cover")
        for key, original in (("series-logo", "series_logo"), ("cover-logo", "institution_logo")):
            metadata[key] = asset(str(cover[original])) if cover.get(original) else ""
        metadata["practice-assets"] = {raw: asset(raw, source_relative=True) for raw in _image_references(markdown)}
        original_inputs = {path: digest(content) if content is not None else None for path, content in reader.cache.items()}

    with Reader(factory) as reader:
        original_template = reader.text("scripts/manual/templates/manual.tex")
        wrapper = reader.text("scripts/manual/templates/practice.tex")
        files["practice.tex"] = practice_template(original_template, wrapper).encode()
        files["render_practice.py"] = reader.read("scripts/manual/render_practice.py")
        for name in FILTERS:
            files[name] = reader.read("scripts/manual/filters/" + name)
        for name in ("scripts/manual/build_pdf.py", "src/unaltraweb_mcp/practice_pdf.py"):
            reader.read(name)
        factory_inputs = {path: digest(content) for path, content in reader.cache.items() if content is not None}
    files["source.md"] = markdown.encode()
    files["metadata.yml"] = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).encode()
    files["request.json"] = canonical({"basename": basename, "filters": list(FILTERS)})
    fingerprint = digest(canonical({"schema_version": 1, "source": source, "version": version,
                                    "image_id": image_id, "original_inputs": original_inputs,
                                    "factory_inputs": factory_inputs,
                                    "prepared_inputs": {name: digest(content) for name, content in files.items()}}))
    job = f"sandbox/practiques/{slug}/lectura-{version}-{language}-{audience}-{run or fingerprint[:16]}"
    return {"files": files, "metadata": metadata, "job": job, "basename": basename,
            "fingerprint": fingerprint, "original_inputs": original_inputs, "factory_inputs": factory_inputs,
            "image_id": image_id, "source": source, "version": version, "language": language, "audience": audience}


def _unchanged(project: Path, hashes: dict[str, str | None]) -> None:
    with Reader(project, max_bytes=MAX_ASSET_BYTES, max_total_bytes=MAX_TOTAL_BYTES) as reader:
        for name, expected in hashes.items():
            content = reader.read(name, optional=expected is None)
            if (digest(content) if content is not None else None) != expected:
                raise ValueError(f"Practice input changed during the build: {name}")


def _write(root_fd: int, relative: str, content: bytes) -> None:
    path = Path(relative_path(relative))
    parent = fs._open_directory(root_fd, path.parent, create=True)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(parent)


def docker_command(host_project: str, plan: dict[str, Any], project_id: str, token: str) -> list[str]:
    job = Path(host_project) / plan["job"]
    session = os.environ.get("UNALTRAWEB_RUNTIME_SESSION", "")
    command = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only",
               "--user", os.environ.get("UNALTRAWEB_PROJECT_USER") or f"{os.getuid()}:{os.getgid()}",
               "--cpus", "2", "--memory", "2g", "--pids-limit", "256", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912",
               "--label", "io.context.mcp-factory=unaltraweb", "--label", "io.context.mcp-role=manual-pdf",
               "--label", f"io.context.mcp-project={project_id}", "--label", f"io.context.mcp-worker-token={token}"]
    if session:
        command.extend(["--label", f"io.context.mcp-session={session}"])
    return command + ["-e", "HOME=/tmp", "-e", "SOURCE_DATE_EPOCH=0", "-e", "FORCE_SOURCE_DATE=1", "-e", "TZ=UTC",
                      "--mount", docker_bind_mount(job / "inputs", "/source", readonly=True),
                      "--mount", docker_bind_mount(job / "outputs", "/out"), "--workdir", "/out",
                      "--entrypoint", "python3", plan["image_id"], "/source/render_practice.py"]


def build(project: Path, factory: Path, source: str, version: str, *, image: str, run: str = "", dry_run: bool = False) -> dict[str, Any]:
    validate_request(source, version, run)
    project, factory = project.resolve(strict=True), factory.resolve(strict=True)
    fs._require_git_root(project)
    identity = inspect_image(image)
    if identity.get("state") != "matched":
        raise ValueError("Prepare the selected manual PDF image explicitly before building practice PDFs")
    plan = prepare(project, factory, source, version, identity["observed_image_id"], run)
    job = Path(plan["job"])
    fs._require_generated_path(project, job, label="Private practice job")
    result = {"ok": True, "publishes": False, "dry_run": dry_run,
              **{key: plan[key] for key in ("job", "source", "version", "language", "audience", "fingerprint")},
              "pdf": f"{job}/outputs/{plan['basename']}.pdf", "preview": f"{job}/outputs/preview.png", "renderer": identity}
    with Reader(project, max_bytes=MAX_ASSET_BYTES, max_total_bytes=MAX_TOTAL_BYTES) as reader:
        existing = reader.read(f"{job}/receipt.json", optional=True)
        if existing is not None:
            receipt = strict_json(existing.decode())
            if not isinstance(receipt, dict) or receipt.get("fingerprint") != plan["fingerprint"]:
                raise ValueError("Existing practice run has different inputs; choose another run")
            expected_inputs = {"inputs/" + name for name in plan["files"]}
            required_outputs = {f"outputs/{plan['basename']}.pdf", "outputs/preview.png", "outputs/render-report.json"}
            actual_paths = {path.removeprefix(f"{job}/") for path in reader.walk(job.as_posix(), include_hidden=True)} - {"receipt.json"}
            if (type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1
                    or receipt.get("kind") != "private-practice-pdf"
                    or not isinstance(receipt.get("artifacts"), dict) or set(receipt["artifacts"]) != actual_paths
                    or not required_outputs.issubset(actual_paths)
                    or {path for path in actual_paths if not path.startswith("outputs/")} != expected_inputs
                    or receipt.get("original_inputs") != plan["original_inputs"]
                    or receipt.get("factory_inputs") != plan["factory_inputs"]):
                raise ValueError("Invalid retained practice receipt or artifact inventory")
            for path, expected in receipt["artifacts"].items():
                if digest(reader.read(f"{job}/{relative_path(path)}")) != expected:
                    raise ValueError("A retained practice artifact was modified; choose another run")
                if path.startswith("inputs/") and expected != digest(plan["files"][path.removeprefix("inputs/")]):
                    raise ValueError("Retained practice snapshot differs from its declared inputs")
            return {**result, "state": "current", "receipt": f"{job}/receipt.json"}
        try:
            with reader.parent(job.as_posix()) as (parent, name):
                os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("Existing unsealed practice run is retained; inspect it and choose another run")
    if dry_run:
        return {**result, "state": "planned", "inputs": plan["original_inputs"]}

    root_fd = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    job_fd = None
    try:
        parent = fs._open_directory(root_fd, job.parent, create=True)
        try:
            os.mkdir(job.name, 0o700, dir_fd=parent)
            job_fd = os.open(job.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileExistsError as exc:
            raise ValueError("Existing unsealed practice run is retained; inspect it and choose another run") from exc
        finally:
            os.close(parent)
        for name, content in plan["files"].items():
            _write(job_fd, "inputs/" + name, content)
        os.mkdir("outputs", 0o700, dir_fd=job_fd)
        _unchanged(project, plan["original_inputs"])
        _unchanged(factory, plan["factory_inputs"])
        host = os.environ.get("UNALTRAWEB_DOCKER_ROOT") or str(project)
        if not Path(host).is_absolute():
            raise ValueError("UNALTRAWEB_DOCKER_ROOT must be absolute")
        project_id = hashlib.sha256(host.encode()).hexdigest()[:16]
        token = os.environ.get("UNALTRAWEB_WORKER_TOKEN") or secrets.token_hex(8)
        completed = run_process(docker_command(host, plan, project_id, token), timeout_seconds=900)
        if completed.returncode or completed.timed_out:
            from .site_tools import _cleanup_timed_out_workers
            cleanup = _cleanup_timed_out_workers(role="manual-pdf", project_id=project_id, token=token)
            raise ValueError(f"Practice render failed; retained {job}: {completed.stderr or completed.stdout}; cleanup={cleanup}")
        _unchanged(project, plan["original_inputs"])
        _unchanged(factory, plan["factory_inputs"])
        with Reader(project, max_bytes=MAX_ASSET_BYTES, max_total_bytes=MAX_TOTAL_BYTES) as reader:
            artifacts = {}
            outputs = reader.walk(f"{job}/outputs", include_hidden=True)
            required = {f"{job}/outputs/{name}" for name in (f"{plan['basename']}.pdf", "preview.png", "render-report.json")}
            if not required.issubset(outputs):
                raise ValueError("Practice worker did not produce its required outputs")
            for path in outputs:
                artifacts[path.removeprefix(f"{job}/")] = digest(reader.read(path))
            for name, content in plan["files"].items():
                path = "inputs/" + name
                if reader.read(f"{job}/{path}") != content:
                    raise ValueError("Prepared practice snapshot changed during rendering")
                artifacts[path] = digest(content)
        fs._require_generated_path(project, job, label="Private practice job")
        receipt = {"schema_version": 1, "kind": "private-practice-pdf", "fingerprint": plan["fingerprint"],
                   "source": source, "version": version, "renderer": identity,
                   "original_inputs": plan["original_inputs"], "factory_inputs": plan["factory_inputs"], "artifacts": artifacts}
        _write(job_fd, "receipt.json", canonical(receipt))
        return {**result, "state": "built", "receipt": f"{job}/receipt.json"}
    finally:
        if job_fd is not None:
            os.close(job_fd)
        os.close(root_fd)
