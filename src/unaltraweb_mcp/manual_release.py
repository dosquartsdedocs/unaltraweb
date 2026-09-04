from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import string
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable


SELECTOR_RE = re.compile(r"(?:latest|v[0-9]{4}\.(?:0[1-9]|1[0-2])(?:\.[1-9][0-9]*)?)\Z")
LANGUAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SITE_BUILD_IMAGE_RE = re.compile(r"ghcr\.io/dosquartsdedocs/unaltraweb-mcp@sha256:[0-9a-f]{64}\Z")
FINGERPRINT_SCHEMA = "unaltraweb-tree-v1"
BUILD_RECEIPT = Path("tmp/.unaltraweb/site-build.json")
RELEASE_ROOT = Path("tmp/manual-release")
SOURCE_EXCLUDED_DIRECTORIES = {
    ".bundle",
    ".cache",
    ".git",
    ".hg",
    ".jekyll-cache",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".sass-cache",
    ".svn",
    ".tox",
    ".unaltraweb-core",
    "__pycache__",
    "_site",
    "legacy",
    "node_modules",
    "sandbox",
    "tmp",
    "vendor",
}
FORBIDDEN_SITE_ROOTS = SOURCE_EXCLUDED_DIRECTORIES - {"_site"}
FORBIDDEN_SITE_COMPONENTS = {".git", ".hg", ".svn"}


class ManualReleaseError(RuntimeError):
    pass


def validate_selector(selector: str) -> str:
    value = str(selector or "").strip()
    if value != selector or not SELECTOR_RE.fullmatch(value):
        raise ValueError("Manual release selector must be exactly 'latest', vYYYY.MM, or vYYYY.MM.N with a valid month and N starting at 1.")
    return value


def release_channel(selector: str) -> str:
    return "latest" if validate_selector(selector) == "latest" else "stable"


def _project_path(project: Path | str) -> Path:
    value = Path(project).expanduser().resolve()
    if not value.is_dir():
        raise ManualReleaseError(f"Manual release project is not a directory: {value}")
    return value


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _strict_json(text: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number is not allowed: {value}")

    return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)


def _validate_relative(raw: str, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw or raw != raw.strip() or "\\" in raw or raw.startswith("/"):
        raise ManualReleaseError(f"{label} must be a non-empty project-relative path: {raw!r}")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise ManualReleaseError(f"{label} contains control characters: {raw!r}")
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ManualReleaseError(f"{label} is not valid UTF-8: {raw!r}") from exc
    parts = raw.split("/")
    if any(part in {"", ".", ".."} or part != part.strip() for part in parts):
        raise ManualReleaseError(f"{label} contains an empty or traversal segment: {raw!r}")
    return Path(*parts)


def _name_key(raw: str) -> str:
    return unicodedata.normalize("NFC", raw).casefold()


def _file_record_from_descriptor(descriptor: int, relative: str) -> dict[str, Any]:
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManualReleaseError(f"Release input is not a regular file: {relative}")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity_before != identity_after or size != after.st_size:
            raise ManualReleaseError(f"Release input changed while it was read: {relative}")
        return {
            "path": relative,
            "sha256": digest.hexdigest(),
            "size": size,
            "mode": stat.S_IMODE(after.st_mode),
        }
    except OSError as exc:
        raise ManualReleaseError(f"Cannot read release input {relative}: {exc}") from exc


def _read_regular_from_descriptor(descriptor: int, relative: str, *, max_bytes: int) -> bytes:
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManualReleaseError(f"Release metadata is not a regular file: {relative}")
        if before.st_size > max_bytes:
            raise ManualReleaseError(f"Release metadata exceeds the {max_bytes}-byte limit: {relative}")
        content = bytearray()
        while len(content) <= max_bytes:
            chunk = os.read(descriptor, min(65536, max_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity_before != identity_after:
            raise ManualReleaseError(f"Release metadata changed while it was read: {relative}")
        if len(content) > max_bytes:
            raise ManualReleaseError(f"Release metadata exceeds the {max_bytes}-byte limit: {relative}")
        return bytes(content)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot read release metadata {relative}: {exc}") from exc


def _read_regular(path: Path, relative: str, *, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        return _read_regular_from_descriptor(descriptor, relative, max_bytes=max_bytes)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot open release metadata {relative}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _snapshot(
    root: Path,
    *,
    exclude: Callable[[str, bool], bool] | None = None,
    canonical_modes: bool = False,
) -> dict[str, Any]:
    root_fd: int | None = None
    try:
        root_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        root_metadata = os.fstat(root_fd)
    except OSError as exc:
        if root_fd is not None:
            os.close(root_fd)
        raise ManualReleaseError(f"Release tree is missing or unreadable: {root}: {exc}") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        os.close(root_fd)
        raise ManualReleaseError(f"Release tree must be a real directory: {root}")

    directories: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    names: dict[str, str] = {}

    def add_name(relative: str) -> None:
        key = _name_key(relative)
        previous = names.get(key)
        if previous is not None and previous != relative:
            raise ManualReleaseError(f"Release tree contains duplicate or normalization-colliding names: {previous!r} and {relative!r}")
        names[key] = relative

    def walk(directory_fd: int, prefix: str) -> None:
        before = os.fstat(directory_fd)
        try:
            with os.scandir(directory_fd) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as exc:
            raise ManualReleaseError(f"Cannot inspect release tree directory {prefix or '.'}: {exc}") from exc
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            _validate_relative(relative, label="release tree path")
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ManualReleaseError(f"Cannot inspect release tree entry {relative}: {exc}") from exc
            is_directory = stat.S_ISDIR(metadata.st_mode)
            if exclude is not None and exclude(relative, is_directory):
                continue
            if stat.S_ISLNK(metadata.st_mode):
                raise ManualReleaseError(f"Release trees cannot contain symlinks: {relative}")
            if is_directory:
                child_fd: int | None = None
                try:
                    child_fd = os.open(
                        entry.name,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=directory_fd,
                    )
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                        raise ManualReleaseError(f"Release tree entry changed while it was inspected: {relative}")
                    add_name(relative)
                    directories.append({"path": relative, "mode": 0o755 if canonical_modes else stat.S_IMODE(opened.st_mode)})
                    walk(child_fd, relative)
                except OSError as exc:
                    raise ManualReleaseError(f"Cannot inspect release tree directory {relative}: {exc}") from exc
                finally:
                    if child_fd is not None:
                        os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode):
                file_fd: int | None = None
                try:
                    file_fd = os.open(
                        entry.name,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
                        dir_fd=directory_fd,
                    )
                    opened = os.fstat(file_fd)
                    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                        raise ManualReleaseError(f"Release tree entry changed while it was inspected: {relative}")
                    add_name(relative)
                    record = _file_record_from_descriptor(file_fd, relative)
                    if canonical_modes:
                        record["mode"] = 0o644
                    files.append(record)
                except OSError as exc:
                    raise ManualReleaseError(f"Cannot inspect release tree file {relative}: {exc}") from exc
                finally:
                    if file_fd is not None:
                        os.close(file_fd)
            else:
                raise ManualReleaseError(f"Release trees cannot contain special files: {relative}")
        after = os.fstat(directory_fd)
        before_identity = (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
        after_identity = (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)
        if before_identity != after_identity:
            raise ManualReleaseError(f"Release tree directory changed while it was inspected: {prefix or '.'}")

    try:
        walk(root_fd, "")
        try:
            path_metadata = root.lstat()
        except OSError as exc:
            raise ManualReleaseError(f"Release tree root changed while it was inspected: {root}: {exc}") from exc
        if (path_metadata.st_dev, path_metadata.st_ino) != (root_metadata.st_dev, root_metadata.st_ino):
            raise ManualReleaseError(f"Release tree root changed while it was inspected: {root}")
        payload = {"schema": FINGERPRINT_SCHEMA, "directories": directories, "files": files}
        digest = hashlib.sha256(b"unaltraweb-tree-v1\0" + _canonical_json(payload)).hexdigest()
        return {
            "sha256": digest,
            "file_count": len(files),
            "directory_count": len(directories),
            "bytes": sum(int(record["size"]) for record in files),
            "directories": directories,
            "files": files,
        }
    finally:
        os.close(root_fd)


def _load_config(project: Path) -> dict[str, Any]:
    from . import site_tools

    config = site_tools.site_config(project)
    if not isinstance(config, dict) or not config:
        raise ManualReleaseError("_config.yml is missing or invalid.")
    return config


def _pdf_config(config: dict[str, Any]) -> dict[str, Any]:
    unaltraweb = config.get("unaltraweb") if isinstance(config.get("unaltraweb"), dict) else {}
    manual = unaltraweb.get("manual") if isinstance(unaltraweb.get("manual"), dict) else {}
    return manual.get("pdf") if isinstance(manual.get("pdf"), dict) else {}


def _pdf_languages(config: dict[str, Any]) -> list[str]:
    pdf = _pdf_config(config)
    values = pdf.get("languages")
    if not isinstance(values, list) or not values:
        values = config.get("languages")
    if not isinstance(values, list) or not values:
        values = [config.get("default_lang") or config.get("lang") or "en"]
    languages = [str(value) for value in values]
    if not languages or any(not LANGUAGE_RE.fullmatch(value) for value in languages):
        raise ManualReleaseError("Manual PDF languages contain an invalid or empty identifier.")
    if len({_name_key(value) for value in languages}) != len(languages):
        raise ManualReleaseError("Manual PDF languages contain duplicate identifiers.")
    return languages


def _render_output_path(template: str, language: str, *, label: str, suffix: str) -> Path:
    formatter = string.Formatter()
    try:
        parsed = list(formatter.parse(template))
    except ValueError as exc:
        raise ManualReleaseError(f"Invalid {label} template: {template}") from exc
    for _, field, format_spec, conversion in parsed:
        if field not in {None, "lang"} or format_spec or conversion:
            raise ManualReleaseError(f"{label} template may contain only the plain {{lang}} field.")
    try:
        rendered = template.format(lang=language)
    except (KeyError, ValueError) as exc:
        raise ManualReleaseError(f"Invalid {label} template: {template}") from exc
    relative = _validate_relative(rendered, label=label)
    if relative.suffix.lower() != suffix:
        raise ManualReleaseError(f"{label} must end in {suffix}: {rendered}")
    return relative


def _public_outputs(config: dict[str, Any]) -> set[str]:
    pdf = _pdf_config(config)
    if pdf.get("enabled") is not True:
        return set()
    pdf_template = str(pdf.get("output") or "assets/pdf/manual-{lang}.pdf")
    cover_template = str(pdf.get("cover_output") or "assets/img/manual-cover-{lang}.png")
    outputs: set[str] = set()
    for language in _pdf_languages(config):
        outputs.add(_render_output_path(pdf_template, language, label="published PDF", suffix=".pdf").as_posix())
        outputs.add(_render_output_path(cover_template, language, label="published cover", suffix=".png").as_posix())
    return outputs


def _expected_pdf_paths(config: dict[str, Any], language: str) -> dict[str, Path]:
    pdf = _pdf_config(config)
    published_pdf = _render_output_path(
        str(pdf.get("output") or "assets/pdf/manual-{lang}.pdf"),
        language,
        label=f"published PDF for {language}",
        suffix=".pdf",
    )
    published_cover = _render_output_path(
        str(pdf.get("cover_output") or "assets/img/manual-cover-{lang}.png"),
        language,
        label=f"published cover for {language}",
        suffix=".png",
    )
    build_root = _validate_relative(
        str(pdf.get("build_dir") or "tmp/manual-pdf"),
        label="manual PDF build directory",
    ) / language
    return {
        "generated_pdf": build_root / published_pdf.name,
        "generated_cover": build_root / published_cover.name,
        "published_pdf": published_pdf,
        "published_cover": published_cover,
    }


def source_snapshot(project: Path | str, *, tracked_only: bool = False) -> dict[str, Any]:
    project = _project_path(project)
    excluded_files = _public_outputs(_load_config(project))
    tracked_files = _tracked_source_paths(project) if tracked_only else None
    tracked_directories: set[str] = set()
    if tracked_files is not None:
        for relative in tracked_files:
            parent = Path(relative).parent
            while parent != Path("."):
                tracked_directories.add(parent.as_posix())
                parent = parent.parent

        def reject_filesystem_only(relative: str, is_directory: bool) -> bool:
            parts = relative.split("/")
            if is_directory and parts[0].casefold() in SOURCE_EXCLUDED_DIRECTORIES:
                return True
            if len(parts) == 1 and parts[0].casefold() in FORBIDDEN_SITE_COMPONENTS:
                return True
            if not is_directory and relative in excluded_files:
                return True
            if any(part.casefold() in FORBIDDEN_SITE_COMPONENTS for part in parts):
                raise ManualReleaseError(f"Manual release sources cannot contain nested VCS metadata: {relative}")
            if not is_directory and relative not in tracked_files:
                raise ManualReleaseError(f"Stable manual sources cannot contain filesystem-only files: {relative}")
            return False

        _snapshot(project, exclude=reject_filesystem_only, canonical_modes=True)

    def exclude(relative: str, is_directory: bool) -> bool:
        parts = relative.split("/")
        if is_directory and parts[0].casefold() in SOURCE_EXCLUDED_DIRECTORIES:
            return True
        if len(parts) == 1 and parts[0].casefold() in FORBIDDEN_SITE_COMPONENTS:
            return True
        if not is_directory and relative in excluded_files:
            return True
        if any(part.casefold() in FORBIDDEN_SITE_COMPONENTS for part in parts):
            raise ManualReleaseError(f"Manual release sources cannot contain nested VCS metadata: {relative}")
        if tracked_files is not None:
            return relative not in (tracked_directories if is_directory else tracked_files)
        return False

    return _snapshot(project, exclude=exclude, canonical_modes=True)


def site_snapshot(project: Path | str) -> dict[str, Any]:
    project = _project_path(project)
    snapshot = _snapshot(project / "_site", canonical_modes=True)
    forbidden = sorted(
        record["path"]
        for record in [*snapshot["directories"], *snapshot["files"]]
        if record["path"].split("/", 1)[0].casefold() in FORBIDDEN_SITE_ROOTS
        or any(part.casefold() in FORBIDDEN_SITE_COMPONENTS for part in record["path"].split("/"))
    )
    if forbidden:
        raise ManualReleaseError(
            "Generated _site contains release-forbidden runtime, VCS, legacy, or sandbox content: "
            + ", ".join(forbidden[:8])
        )
    return snapshot


def _git_output(project: Path, *arguments: str, input_text: str | None = None) -> str:
    command = ["git", "-c", f"safe.directory={project}", "-C", str(project), *arguments]
    try:
        completed = subprocess.run(
            command,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ManualReleaseError(f"Could not inspect the stable source checkout with Git: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Git returned no detail."
        raise ManualReleaseError(f"Could not inspect the stable source checkout with Git: {detail}")
    return completed.stdout


def _tracked_source_paths(project: Path) -> set[str]:
    raw = _git_output(project, "ls-files", "--stage", "-z")
    entries = [value for value in raw.split("\0") if value]
    tracked: set[str] = set()
    indexed: dict[str, tuple[str, str]] = {}
    for entry in entries:
        metadata, separator, raw_path = entry.partition("\t")
        fields = metadata.split(" ")
        if not separator or len(fields) != 3 or fields[2] != "0":
            raise ManualReleaseError("Git index contains an unmerged or malformed stable source entry.")
        mode, object_id, _ = fields
        if mode == "160000":
            raise ManualReleaseError(f"Stable manual releases do not support Git submodules: {raw_path}")
        if mode not in {"100644", "100755"}:
            raise ManualReleaseError(f"Stable manual sources must be regular Git files, not mode {mode}: {raw_path}")
        relative = _validate_relative(raw_path, label="tracked stable source").as_posix()
        if relative in tracked:
            raise ManualReleaseError(f"Git returned a duplicate stable source path: {relative}")
        tracked.add(relative)
        indexed[relative] = (mode, object_id)

    head: dict[str, tuple[str, str]] = {}
    head_entries = _git_output(project, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split("\0")
    for entry in [value for value in head_entries if value]:
        metadata, separator, raw_path = entry.partition("\t")
        fields = metadata.split(" ")
        if not separator or len(fields) != 3 or fields[1] != "blob":
            raise ManualReleaseError("Reviewed Git tree contains an unsupported or malformed stable source entry.")
        mode, _, object_id = fields
        relative = _validate_relative(raw_path, label="reviewed stable source").as_posix()
        if relative in head:
            raise ManualReleaseError(f"Reviewed Git tree contains a duplicate stable source path: {relative}")
        head[relative] = (mode, object_id)
    if indexed != head:
        raise ManualReleaseError("Stable Git index does not exactly match the reviewed HEAD tree.")

    if tracked:
        attributes = _git_output(
            project,
            "check-attr",
            "-z",
            "--stdin",
            "filter",
            input_text="".join(f"{path}\0" for path in sorted(tracked)),
        ).split("\0")
        if attributes and attributes[-1] == "":
            attributes.pop()
        if len(attributes) % 3 != 0:
            raise ManualReleaseError("Git returned malformed filter attributes for stable sources.")
        filtered = [
            attributes[index]
            for index in range(0, len(attributes), 3)
            if attributes[index + 2] not in {"unspecified", "unset"}
        ]
        if filtered:
            raise ManualReleaseError(
                "Stable manual releases do not support Git clean/smudge filters: " + ", ".join(filtered[:8])
            )

    object_format = _git_output(project, "rev-parse", "--show-object-format").strip()
    if object_format not in {"sha1", "sha256"}:
        raise ManualReleaseError(f"Unsupported Git object format for stable sources: {object_format}")
    for relative, (_, expected_object_id) in sorted(indexed.items()):
        actual_object_id = _git_blob_oid_confined(project, Path(relative), object_format)
        if actual_object_id != expected_object_id:
            raise ManualReleaseError(f"Stable worktree bytes do not match the reviewed Git blob: {relative}")

    public_outputs = _public_outputs(_load_config(project))
    versioned_outputs = sorted(tracked & public_outputs)
    if versioned_outputs:
        raise ManualReleaseError(
            "Generated manual publication outputs must not be tracked by Git: " + ", ".join(versioned_outputs[:8])
        )
    return tracked


def _git_blob_oid_confined(project: Path, relative: Path, algorithm: str) -> str:
    descriptor = _open_confined_regular(project, relative, label="tracked stable source")
    try:
        before = os.fstat(descriptor)
        digest = hashlib.new(algorithm)
        digest.update(f"blob {before.st_size}\0".encode("ascii"))
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if before_identity != after_identity or size != after.st_size:
            raise ManualReleaseError(f"Tracked stable source changed while it was read: {relative.as_posix()}")
        return digest.hexdigest()
    except OSError as exc:
        raise ManualReleaseError(f"Cannot hash tracked stable source {relative.as_posix()}: {exc}") from exc
    finally:
        os.close(descriptor)


def stable_source_identity(project: Path | str) -> dict[str, str]:
    project = _project_path(project)
    root = Path(_git_output(project, "rev-parse", "--show-toplevel").strip()).resolve()
    if root != project:
        raise ManualReleaseError(f"Stable manual source must be the Git worktree root: {project}")

    status = _git_output(project, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        changed = [line for line in status.splitlines() if line][:8]
        raise ManualReleaseError(
            "Stable manual source must be a clean Git checkout; commit or remove: " + ", ".join(changed)
        )

    staged = _git_output(project, "ls-files", "--stage", "-z")
    gitlinks = []
    for entry in staged.split("\0"):
        if not entry:
            continue
        metadata, _, path = entry.partition("\t")
        if metadata.split(" ", 1)[0] == "160000":
            gitlinks.append(path)
    if gitlinks:
        raise ManualReleaseError(
            "Stable manual releases do not support Git submodules: " + ", ".join(sorted(gitlinks)[:8])
        )

    commit = _git_output(project, "rev-parse", "HEAD^{commit}").strip()
    source_date_epoch = _git_output(project, "show", "--no-patch", "--format=%ct", "HEAD").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9]+", source_date_epoch):
        raise ManualReleaseError("Stable manual source has no canonical commit SHA or commit timestamp.")
    return {"commit": commit, "source_date_epoch": source_date_epoch}


def stable_build_image_reference() -> str:
    image = os.environ.get("UNALTRAWEB_MCP_IMAGE_REFERENCE", "").strip()
    if not SITE_BUILD_IMAGE_RE.fullmatch(image):
        raise ManualReleaseError(
            "Stable manual builds require UNALTRAWEB_MCP_IMAGE_REFERENCE pinned to "
            "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:<digest>."
        )
    return image


def _open_confined_directory(project: Path, relative: Path, *, create: bool) -> int | None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.open(project, flags)
    try:
        for part in relative.parts:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except FileNotFoundError:
                if not create:
                    os.close(current_fd)
                    return None
                raise
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_directory_at(root_fd: int, relative: Path, *, create: bool) -> int:
    current_fd = os.dup(root_fd)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        for part in relative.parts:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_confined_regular(project: Path, relative: Path, *, label: str) -> int:
    try:
        parent_fd = _open_confined_directory(project, relative.parent, create=False)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot open {label} parent {relative.as_posix()}: {exc}") from exc
    if parent_fd is None:
        raise ManualReleaseError(f"Missing {label} parent: {relative.as_posix()}")
    try:
        descriptor = os.open(
            relative.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ManualReleaseError(f"Cannot open {label} {relative.as_posix()}: {exc}") from exc
    finally:
        os.close(parent_fd)
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        os.close(descriptor)
        raise ManualReleaseError(f"Cannot inspect {label} {relative.as_posix()}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise ManualReleaseError(f"{label} must be a regular file: {relative.as_posix()}")
    return descriptor


def _file_record_confined(project: Path, relative: Path, *, label: str) -> dict[str, Any]:
    descriptor = _open_confined_regular(project, relative, label=label)
    try:
        return _file_record_from_descriptor(descriptor, relative.as_posix())
    finally:
        os.close(descriptor)


def _read_regular_confined(
    project: Path,
    relative: Path,
    *,
    label: str,
    max_bytes: int = 8 * 1024 * 1024,
) -> bytes:
    descriptor = _open_confined_regular(project, relative, label=label)
    try:
        return _read_regular_from_descriptor(descriptor, relative.as_posix(), max_bytes=max_bytes)
    finally:
        os.close(descriptor)


def _atomic_write(project: Path, relative: Path, content: bytes) -> None:
    try:
        parent_fd = _open_confined_directory(project, relative.parent, create=True)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot open confined destination for {relative.as_posix()}: {exc}") from exc
    assert parent_fd is not None
    temporary = ""
    descriptor: int | None = None
    try:
        try:
            metadata = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise ManualReleaseError(f"Atomic destination is not a regular file: {relative.as_posix()}")
        temporary = f".{relative.name}.{os.getpid()}.{secrets.token_hex(8)}"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o644,
            dir_fd=parent_fd,
        )
        remaining = memoryview(content)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, relative.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
    except OSError as exc:
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except OSError:
                pass
        raise ManualReleaseError(f"Atomic write failed for {relative.as_posix()}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)


def write_site_build_receipt(
    project: Path | str,
    selector: str = "latest",
    *,
    source: dict[str, Any] | None = None,
    site: dict[str, Any] | None = None,
    source_identity: dict[str, str] | None = None,
    site_build_image: str | None = None,
) -> dict[str, Any]:
    project = _project_path(project)
    selector = validate_selector(selector)
    current_identity = stable_source_identity(project) if selector != "latest" else None
    current_site_build_image = stable_build_image_reference() if selector != "latest" else None
    source = source if source is not None else source_snapshot(project, tracked_only=selector != "latest")
    site = site if site is not None else site_snapshot(project)
    receipt = {
        "channel": release_channel(selector),
        "fingerprint_schema": FINGERPRINT_SCHEMA,
        "schema_version": 2,
        "selector": selector,
        "site_bytes": site["bytes"],
        "site_files": site["file_count"],
        "site_fingerprint": site["sha256"],
        "source_bytes": source["bytes"],
        "source_files": source["file_count"],
        "source_fingerprint": source["sha256"],
    }
    if selector != "latest":
        assert current_identity is not None
        assert current_site_build_image is not None
        if source_identity is not None and source_identity != current_identity:
            raise ManualReleaseError("Stable source identity changed while the site was being built.")
        if site_build_image is not None and site_build_image != current_site_build_image:
            raise ManualReleaseError("Stable site-build image changed while the site was being built.")
        receipt.update({
            "site_build_image": current_site_build_image,
            "source_commit": current_identity["commit"],
            "source_date_epoch": current_identity["source_date_epoch"],
        })
    _atomic_write(project, BUILD_RECEIPT, _canonical_json(receipt))
    return {"ok": True, "path": BUILD_RECEIPT.as_posix(), "receipt": receipt}


def site_build_receipt_status(project: Path | str, selector: str = "latest") -> dict[str, Any]:
    project = _project_path(project)
    selector = validate_selector(selector)
    try:
        source_identity = stable_source_identity(project) if selector != "latest" else None
        site_build_image = stable_build_image_reference() if selector != "latest" else None
        source = source_snapshot(project, tracked_only=selector != "latest")
        site = site_snapshot(project)
    except ManualReleaseError as exc:
        return {"ok": False, "state": "invalid", "path": BUILD_RECEIPT.as_posix(), "error": str(exc)}
    expected = {
        "channel": release_channel(selector),
        "fingerprint_schema": FINGERPRINT_SCHEMA,
        "schema_version": 2,
        "selector": selector,
        "site_bytes": site["bytes"],
        "site_files": site["file_count"],
        "site_fingerprint": site["sha256"],
        "source_bytes": source["bytes"],
        "source_files": source["file_count"],
        "source_fingerprint": source["sha256"],
    }
    if source_identity is not None:
        expected.update({
            "site_build_image": site_build_image,
            "source_commit": source_identity["commit"],
            "source_date_epoch": source_identity["source_date_epoch"],
        })
    try:
        received = _strict_json(
            _read_regular_confined(project, BUILD_RECEIPT, label="site build receipt").decode("utf-8")
        )
    except (ManualReleaseError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        state = "missing" if not os.path.lexists(project / BUILD_RECEIPT) else "invalid"
        return {
            "ok": False,
            "state": state,
            "path": BUILD_RECEIPT.as_posix(),
            "error": str(exc),
            "current": expected,
            "_source_snapshot": source,
            "_site_snapshot": site,
        }
    matches = isinstance(received, dict) and received == expected
    return {
        "ok": matches,
        "state": "current" if matches else "stale",
        "path": BUILD_RECEIPT.as_posix(),
        "receipt": received,
        "current": expected,
        "error": "" if matches else "Site build receipt does not match the current source and _site trees.",
        "_source_snapshot": source,
        "_site_snapshot": site,
    }


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _pdf_release_status(
    project: Path,
    config: dict[str, Any],
    pdf_status: dict[str, Any],
    site: dict[str, Any],
    selector: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    if not isinstance(pdf_status, dict):
        return records, [_issue("UW-RELEASE-PDF-STATUS", "manual_pdf_status did not return an object.")]
    input_error = str(pdf_status.get("input_error") or "")
    if input_error:
        issues.append(_issue("UW-RELEASE-PDF-STATUS", input_error))
    for field in ["configuration_ok", "ready_to_publish", "published_current"]:
        if pdf_status.get(field) is not True:
            issues.append(_issue("UW-RELEASE-PDF-STATUS", f"manual_pdf_status requires {field}=true for all configured languages."))

    try:
        expected_languages = _pdf_languages(config)
    except ManualReleaseError as exc:
        return records, issues + [_issue("UW-RELEASE-PDF-CONFIG", str(exc))]
    raw_languages = pdf_status.get("languages")
    if not isinstance(raw_languages, list):
        return records, issues + [_issue("UW-RELEASE-PDF-STATUS", "manual_pdf_status languages must be an array.")]
    actual_languages = [str(item.get("language") or "") if isinstance(item, dict) else "" for item in raw_languages]
    if actual_languages != expected_languages:
        issues.append(_issue("UW-RELEASE-PDF-LANGUAGES", "manual_pdf_status does not exactly cover configured PDF languages in configured order."))

    site_files = {record["path"]: record for record in site["files"]}
    candidate_names: dict[str, str] = {}
    for item in raw_languages:
        if not isinstance(item, dict):
            issues.append(_issue("UW-RELEASE-PDF-STATUS", "manual_pdf_status contains a non-object language record."))
            continue
        language = str(item.get("language") or "")
        if not LANGUAGE_RE.fullmatch(language):
            issues.append(_issue("UW-RELEASE-PDF-LANGUAGE", f"Invalid PDF language in manual_pdf_status: {language!r}"))
            continue
        if any(item.get(field) is not True for field in ["fresh", "ready_to_publish", "published_current"]):
            issues.append(_issue("UW-RELEASE-PDF-FRESHNESS", f"PDF language {language} is not fresh, ready, and published_current."))
        if item.get("release_selector") != selector or item.get("release_channel") != release_channel(selector):
            issues.append(_issue("UW-RELEASE-PDF-SELECTOR", f"PDF language {language} was not built for release selector {selector}."))

        try:
            expected_paths = _expected_pdf_paths(config, language)
            paths = {
                "generated_pdf": _validate_relative(str(item.get("generated_pdf") or ""), label=f"generated PDF for {language}"),
                "generated_cover": _validate_relative(str(item.get("generated_cover") or ""), label=f"generated cover for {language}"),
                "published_pdf": _validate_relative(str(item.get("published_pdf") or ""), label=f"published PDF for {language}"),
                "published_cover": _validate_relative(str(item.get("published_cover") or ""), label=f"published cover for {language}"),
            }
            if paths != expected_paths:
                raise ManualReleaseError(f"manual_pdf_status paths do not match the configured outputs for {language}.")
            if paths["generated_pdf"].suffix.lower() != ".pdf" or paths["published_pdf"].suffix.lower() != ".pdf":
                raise ManualReleaseError(f"PDF paths for {language} must end in .pdf.")
            if paths["generated_cover"].suffix.lower() != ".png" or paths["published_cover"].suffix.lower() != ".png":
                raise ManualReleaseError(f"Cover paths for {language} must end in .png.")
            generated_pdf = _file_record_confined(project, paths["generated_pdf"], label="generated PDF")
            generated_cover = _file_record_confined(project, paths["generated_cover"], label="generated cover")
            published_pdf = _file_record_confined(project, paths["published_pdf"], label="published PDF")
            published_cover = _file_record_confined(project, paths["published_cover"], label="published cover")
            if generated_pdf["sha256"] != published_pdf["sha256"] or generated_pdf["size"] != published_pdf["size"]:
                raise ManualReleaseError(f"Generated and published PDF differ for {language}.")
            if generated_cover["sha256"] != published_cover["sha256"] or generated_cover["size"] != published_cover["size"]:
                raise ManualReleaseError(f"Generated and published cover differ for {language}.")
            site_pdf = site_files.get(paths["published_pdf"].as_posix())
            site_cover = site_files.get(paths["published_cover"].as_posix())
            if site_pdf is None or (site_pdf["sha256"], site_pdf["size"]) != (published_pdf["sha256"], published_pdf["size"]):
                raise ManualReleaseError(f"Published PDF is missing from _site or differs from it for {language}.")
            if site_cover is None or (site_cover["sha256"], site_cover["size"]) != (published_cover["sha256"], published_cover["size"]):
                raise ManualReleaseError(f"Published cover is missing from _site or differs from it for {language}.")

            manifest_relative = paths["generated_pdf"].parent / "manifest.json"
            manifest = _strict_json(
                _read_regular_confined(project, manifest_relative, label="manual PDF manifest").decode("utf-8")
            )
            expected_manifest = {
                "language": language,
                "pdf": paths["generated_pdf"].as_posix(),
                "cover": paths["generated_cover"].as_posix(),
                "public_pdf": paths["published_pdf"].as_posix(),
                "public_cover": paths["published_cover"].as_posix(),
                "release_selector": selector,
                "release_channel": release_channel(selector),
            }
            if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected_manifest.items()):
                raise ManualReleaseError(f"Manual PDF manifest does not match configured release outputs for {language}.")
            if type(manifest.get("draft")) is not bool or not SHA256_RE.fullmatch(str(manifest.get("fingerprint") or "")):
                raise ManualReleaseError(f"Manual PDF manifest has no valid draft state or fingerprint for {language}.")
            artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
            if artifacts.get("pdf") != {"sha256": generated_pdf["sha256"], "size": generated_pdf["size"]}:
                raise ManualReleaseError(f"Manual PDF manifest does not inventory the generated PDF for {language}.")
            if artifacts.get("cover") != {"sha256": generated_cover["sha256"], "size": generated_cover["size"]}:
                raise ManualReleaseError(f"Manual PDF manifest does not inventory the generated cover for {language}.")

            candidate_path = f"pdf/{paths['published_pdf'].name}"
            key = _name_key(candidate_path)
            if key in candidate_names:
                raise ManualReleaseError(
                    f"Configured PDFs produce duplicate or unsafe candidate names: {candidate_names[key]} and {candidate_path}."
                )
            candidate_names[key] = candidate_path
            records.append(
                {
                    "language": language,
                    "path": candidate_path,
                    "published_path": paths["published_pdf"].as_posix(),
                    "site_path": f"site/{paths['published_pdf'].as_posix()}",
                    "sha256": published_pdf["sha256"],
                    "size": published_pdf["size"],
                    "mode": site_pdf["mode"],
                    "cover_path": paths["published_cover"].as_posix(),
                    "cover_site_path": f"site/{paths['published_cover'].as_posix()}",
                    "cover_sha256": published_cover["sha256"],
                    "cover_size": published_cover["size"],
                    "draft": manifest["draft"],
                }
            )
        except (ManualReleaseError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            issues.append(_issue("UW-RELEASE-PDF-ARTIFACT", str(exc)))
    return sorted(records, key=lambda record: record["language"]), issues


def _stable_status(project: Path, selector: str, pdfs: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if selector == "latest":
        return {"required": False, "ok": True}, []
    from . import site_tools

    issues: list[dict[str, Any]] = []
    approval = site_tools.content_approval_inventory(project)
    editorial = site_tools.manual_editorial_quality_check(project)
    drafts = [record["language"] for record in pdfs if record.get("draft") is True]
    if drafts:
        issues.append(_issue("UW-RELEASE-STABLE-DRAFT", f"Stable candidates cannot contain draft PDFs: {', '.join(drafts)}."))
    if int(approval.get("default_language_count") or 0) == 0 or int(approval.get("pending_default_count") or 0) != 0:
        issues.append(_issue("UW-RELEASE-STABLE-APPROVAL", "All publishable default-language content must be explicitly approved for a stable candidate."))
    if editorial.get("ok") is not True:
        issues.append(_issue("UW-RELEASE-STABLE-EDITORIAL", "Stable candidates require a clean manual_editorial_quality_check."))
    return {
        "required": True,
        "ok": not issues,
        "draft_languages": drafts,
        "approval": approval,
        "editorial_quality": editorial,
    }, issues


def _site_release_metadata(project: Path, selector: str, site: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    relative = Path("manual-release.json")
    site_files = {record["path"]: record for record in site["files"]}
    if relative.as_posix() not in site_files:
        return {}, [_issue("UW-RELEASE-SITE-METADATA", "Generated _site has no manual-release.json publication marker.")]
    try:
        content = _read_regular_confined(
            project,
            Path("_site") / relative,
            label="manual release site marker",
        )
        marker = _strict_json(content.decode("utf-8"))
        expected = {
            "channel": release_channel(selector),
            "schema_version": 1,
            "selector": selector,
        }
        if not isinstance(marker, dict) or marker != expected or _canonical_json(marker) != content:
            raise ManualReleaseError("manual-release.json does not exactly match the requested release selector.")
        return marker, []
    except (ManualReleaseError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return {}, [_issue("UW-RELEASE-SITE-METADATA", str(exc))]


def _release_readiness(project: Path, selector: str, pdf_status: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        from . import site_tools

        config = _load_config(project)
        unaltraweb = config.get("unaltraweb") if isinstance(config.get("unaltraweb"), dict) else {}
        if str(unaltraweb.get("site_profile") or "") != "unaltremanual":
            issues.append(_issue("UW-RELEASE-PROFILE", "Manual release candidates require the unaltremanual site profile."))
        receipt = site_build_receipt_status(project, selector)
        if receipt.get("ok") is not True:
            issues.append(_issue("UW-RELEASE-BUILD-RECEIPT", str(receipt.get("error") or "A current successful site build receipt is required.")))
            public_receipt = {key: value for key, value in receipt.items() if not key.startswith("_")}
            return {
                "ok": False,
                "issues": issues,
                "build_receipt": public_receipt,
                "html_audit": {"ok": False, "skipped": True, "reason": "Build receipt is not current and safe."},
                "pdf": {
                    "configuration_ok": False,
                    "ready_to_publish": False,
                    "published_current": False,
                    "languages": [],
                },
                "stable": {"required": selector != "latest", "ok": False},
                "site_release": {},
                "_receipt": receipt,
                "_pdfs": [],
            }
        audit = site_tools.html_audit(project)
        if audit.get("ok") is not True:
            issues.append(_issue("UW-RELEASE-HTML-AUDIT", "The current _site tree does not pass html_audit."))
        site = receipt["_site_snapshot"]
        site_release, site_release_issues = _site_release_metadata(project, selector, site)
        issues.extend(site_release_issues)
        pdfs, pdf_issues = _pdf_release_status(project, config, pdf_status, site, selector)
        issues.extend(pdf_issues)
        stable, stable_issues = _stable_status(project, selector, pdfs)
        issues.extend(stable_issues)
        final_source = source_snapshot(project, tracked_only=selector != "latest")
        final_site = site_snapshot(project)
        if final_source["sha256"] != receipt["_source_snapshot"]["sha256"] or final_site["sha256"] != site["sha256"]:
            issues.append(
                _issue(
                    "UW-RELEASE-INPUT-CHANGED",
                    "Source or generated site changed while release readiness was evaluated.",
                )
            )
    except ManualReleaseError as exc:
        receipt = {"ok": False, "state": "invalid", "error": str(exc), "path": BUILD_RECEIPT.as_posix()}
        audit = {"ok": False, "error": str(exc)}
        pdfs = []
        stable = {"required": selector != "latest", "ok": False}
        site_release = {}
        issues.append(_issue("UW-RELEASE-INPUT", str(exc)))
    public_receipt = {key: value for key, value in receipt.items() if not key.startswith("_")}
    return {
        "ok": not issues,
        "issues": issues,
        "build_receipt": public_receipt,
        "html_audit": audit,
        "pdf": {
            "configuration_ok": pdf_status.get("configuration_ok") is True if isinstance(pdf_status, dict) else False,
            "ready_to_publish": pdf_status.get("ready_to_publish") is True if isinstance(pdf_status, dict) else False,
            "published_current": pdf_status.get("published_current") is True if isinstance(pdf_status, dict) else False,
            "languages": pdfs,
        },
        "stable": stable,
        "site_release": site_release,
        "_receipt": receipt,
        "_pdfs": pdfs,
    }


def _release_manifest(selector: str, receipt: dict[str, Any], pdfs: list[dict[str, Any]]) -> dict[str, Any]:
    current = receipt["current"]
    source = {
        "bytes": current["source_bytes"],
        "file_count": current["source_files"],
        "sha256": current["source_fingerprint"],
    }
    if selector != "latest":
        source.update({
            "commit": current["source_commit"],
            "site_build_image": current["site_build_image"],
            "source_date_epoch": current["source_date_epoch"],
        })
    return {
        "channel": "latest" if selector == "latest" else "stable",
        "fingerprint_schema": FINGERPRINT_SCHEMA,
        "pdfs": [
            {key: record[key] for key in [
                "language",
                "path",
                "published_path",
                "site_path",
                "sha256",
                "size",
                "cover_path",
                "cover_site_path",
                "cover_sha256",
                "cover_size",
                "draft",
            ]}
            for record in pdfs
        ],
        "schema_version": 2,
        "selector": selector,
        "site": {
            "bytes": current["site_bytes"],
            "file_count": current["site_files"],
            "path": "site",
            "sha256": current["site_fingerprint"],
        },
        "source": source,
    }


def _checksum_bytes(entries: dict[str, str]) -> bytes:
    return "".join(f"{entries[path]}  {path}\n" for path in sorted(entries)).encode("utf-8")


def _expected_candidate(selector: str, readiness: dict[str, Any]) -> dict[str, Any]:
    receipt = readiness["_receipt"]
    site = receipt["_site_snapshot"]
    pdfs = readiness["_pdfs"]
    manifest_bytes = _canonical_json(_release_manifest(selector, receipt, pdfs))
    files: dict[str, dict[str, Any]] = {}
    directories: dict[str, int] = {"site": 0o755, "pdf": 0o755}
    for record in site["directories"]:
        directories[f"site/{record['path']}"] = int(record["mode"])
    for record in site["files"]:
        files[f"site/{record['path']}"] = {
            "sha256": record["sha256"],
            "size": record["size"],
            "mode": record["mode"],
        }
    for record in pdfs:
        files[record["path"]] = {"sha256": record["sha256"], "size": record["size"], "mode": record["mode"]}
    files["release-manifest.json"] = {
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "size": len(manifest_bytes),
        "mode": 0o644,
        "content": manifest_bytes,
    }
    sums = _checksum_bytes({path: record["sha256"] for path, record in files.items()})
    files["SHA256SUMS"] = {
        "sha256": hashlib.sha256(sums).hexdigest(),
        "size": len(sums),
        "mode": 0o644,
        "content": sums,
    }
    return {"directories": directories, "files": files, "manifest": _strict_json(manifest_bytes.decode("utf-8"))}


def _parse_sums(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManualReleaseError("SHA256SUMS is not UTF-8.") from exc
    entries: dict[str, str] = {}
    lines = text.splitlines(keepends=True)
    if not lines or any(not line.endswith("\n") for line in lines):
        raise ManualReleaseError("SHA256SUMS must be non-empty and newline terminated.")
    paths: list[str] = []
    keys: set[str] = set()
    for line in lines:
        value = line[:-1]
        if "  " not in value:
            raise ManualReleaseError("SHA256SUMS contains a malformed line.")
        digest, raw_path = value.split("  ", 1)
        if not SHA256_RE.fullmatch(digest):
            raise ManualReleaseError("SHA256SUMS contains an invalid digest.")
        path = _validate_relative(raw_path, label="SHA256SUMS path").as_posix()
        key = _name_key(path)
        if path == "SHA256SUMS" or key in keys:
            raise ManualReleaseError("SHA256SUMS contains a duplicate, self-referential, or unsafe path.")
        keys.add(key)
        paths.append(path)
        entries[path] = digest
    if paths != sorted(paths):
        raise ManualReleaseError("SHA256SUMS entries are not sorted.")
    return entries


def _candidate_status(
    project: Path,
    selector: str,
    expected: dict[str, Any] | None,
    *,
    candidate_path: Path | None = None,
) -> dict[str, Any]:
    relative = (RELEASE_ROOT / selector).as_posix() if candidate_path is None else str(candidate_path)
    if candidate_path is not None:
        return _candidate_status_at(candidate_path, relative, selector, expected)
    try:
        root_fd = _open_confined_directory(project, RELEASE_ROOT, create=False)
    except OSError as exc:
        return {
            "ok": False,
            "exists": True,
            "state": "unsafe",
            "path": relative,
            "error": f"Cannot open confined manual release root: {exc}",
        }
    if root_fd is None:
        return {"ok": False, "exists": False, "state": "absent", "path": relative, "error": "Prepared candidate does not exist."}
    try:
        return _candidate_status_at(Path(f"/proc/self/fd/{root_fd}") / selector, relative, selector, expected)
    finally:
        os.close(root_fd)


def _candidate_status_at(
    candidate: Path,
    relative: str,
    selector: str,
    expected: dict[str, Any] | None,
) -> dict[str, Any]:
    if not os.path.lexists(candidate):
        return {"ok": False, "exists": False, "state": "absent", "path": relative, "error": "Prepared candidate does not exist."}
    try:
        candidate_metadata = candidate.lstat()
    except OSError as exc:
        return {"ok": False, "exists": True, "state": "unsafe", "path": relative, "error": str(exc)}
    if stat.S_ISLNK(candidate_metadata.st_mode) or not stat.S_ISDIR(candidate_metadata.st_mode):
        return {"ok": False, "exists": True, "state": "unsafe", "path": relative, "error": "Candidate path must be a real directory."}
    try:
        snapshot = _snapshot(candidate)
        file_map = {record["path"]: record for record in snapshot["files"]}
        directory_map = {record["path"]: record["mode"] for record in snapshot["directories"]}
        required = {"release-manifest.json", "SHA256SUMS"}
        if not required.issubset(file_map):
            raise ManualReleaseError("Candidate is missing release-manifest.json or SHA256SUMS.")
        manifest_content = _read_regular(candidate / "release-manifest.json", "release-manifest.json")
        manifest = _strict_json(manifest_content.decode("utf-8"))
        if not isinstance(manifest, dict) or _canonical_json(manifest) != manifest_content:
            raise ManualReleaseError("release-manifest.json is not canonical JSON.")
        if manifest.get("schema_version") != 2 or manifest.get("fingerprint_schema") != FINGERPRINT_SCHEMA:
            raise ManualReleaseError("release-manifest.json uses an unsupported schema.")
        if manifest.get("selector") != selector or manifest.get("channel") != ("latest" if selector == "latest" else "stable"):
            raise ManualReleaseError("release-manifest.json selector or channel does not match its candidate path.")
        source = manifest.get("source")
        source_keys = {"bytes", "file_count", "sha256"}
        if selector != "latest":
            source_keys.update({"commit", "site_build_image", "source_date_epoch"})
        if (
            not isinstance(source, dict)
            or set(source) != source_keys
            or type(source.get("bytes")) is not int
            or type(source.get("file_count")) is not int
            or not SHA256_RE.fullmatch(str(source.get("sha256") or ""))
        ):
            raise ManualReleaseError("release-manifest.json has an invalid source fingerprint.")
        if selector != "latest" and (
            not re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit") or ""))
            or not SITE_BUILD_IMAGE_RE.fullmatch(str(source.get("site_build_image") or ""))
            or not re.fullmatch(r"[0-9]+", str(source.get("source_date_epoch") or ""))
        ):
            raise ManualReleaseError("Stable release manifest has no canonical Git source identity.")
        sums_content = _read_regular(candidate / "SHA256SUMS", "SHA256SUMS")
        sums = _parse_sums(sums_content)
        expected_sum_paths = set(file_map) - {"SHA256SUMS"}
        if set(sums) != expected_sum_paths:
            raise ManualReleaseError("SHA256SUMS does not exactly inventory candidate files.")
        for path, digest in sums.items():
            if file_map[path]["sha256"] != digest:
                raise ManualReleaseError(f"Candidate checksum mismatch: {path}")

        site = _snapshot(candidate / "site")
        manifest_site = manifest.get("site")
        if not isinstance(manifest_site, dict) or manifest_site != {
            "bytes": site["bytes"],
            "file_count": site["file_count"],
            "path": "site",
            "sha256": site["sha256"],
        }:
            raise ManualReleaseError("Candidate site tree does not match release-manifest.json.")
        pdfs = manifest.get("pdfs")
        if not isinstance(pdfs, list) or not pdfs:
            raise ManualReleaseError("release-manifest.json has no PDF inventory.")
        seen_pdf_paths: set[str] = set()
        for record in pdfs:
            if not isinstance(record, dict):
                raise ManualReleaseError("release-manifest.json contains a non-object PDF record.")
            pdf_path = _validate_relative(str(record.get("path") or ""), label="candidate PDF path").as_posix()
            site_path = _validate_relative(str(record.get("site_path") or ""), label="candidate site PDF path").as_posix()
            cover_path = _validate_relative(str(record.get("cover_site_path") or ""), label="candidate site cover path").as_posix()
            key = _name_key(pdf_path)
            if key in seen_pdf_paths or not pdf_path.startswith("pdf/"):
                raise ManualReleaseError("release-manifest.json contains duplicate or misplaced PDF paths.")
            seen_pdf_paths.add(key)
            if pdf_path not in file_map or site_path not in file_map or cover_path not in file_map:
                raise ManualReleaseError("release-manifest.json refers to a missing PDF or cover.")
            if (file_map[pdf_path]["sha256"], file_map[pdf_path]["size"]) != (record.get("sha256"), record.get("size")):
                raise ManualReleaseError(f"Standalone candidate PDF does not match its manifest: {pdf_path}")
            if (file_map[site_path]["sha256"], file_map[site_path]["size"]) != (record.get("sha256"), record.get("size")):
                raise ManualReleaseError(f"Candidate site PDF does not match its manifest: {site_path}")
            if (file_map[cover_path]["sha256"], file_map[cover_path]["size"]) != (record.get("cover_sha256"), record.get("cover_size")):
                raise ManualReleaseError(f"Candidate site cover does not match its manifest: {cover_path}")

        if _snapshot(candidate) != snapshot:
            raise ManualReleaseError("Candidate changed while it was being verified.")

        if expected is not None:
            expected_directories = expected["directories"]
            if directory_map != expected_directories:
                return {"ok": False, "exists": True, "state": "stale", "path": relative, "error": "Candidate directory inventory differs from current verified outputs.", "manifest": manifest}
            expected_files = expected["files"]
            actual_values = {path: {key: record[key] for key in ["sha256", "size", "mode"]} for path, record in file_map.items()}
            expected_values = {path: {key: record[key] for key in ["sha256", "size", "mode"]} for path, record in expected_files.items()}
            if actual_values != expected_values:
                return {"ok": False, "exists": True, "state": "stale", "path": relative, "error": "Candidate files differ from current verified inputs or outputs.", "manifest": manifest}
        return {"ok": expected is not None, "exists": True, "state": "current" if expected is not None else "verified", "path": relative, "error": "", "manifest": manifest}
    except (ManualReleaseError, UnicodeDecodeError, ValueError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "exists": True, "state": "tampered", "path": relative, "error": str(exc)}


def release_status(project: Path | str, selector: str, pdf_status: dict[str, Any]) -> dict[str, Any]:
    project = _project_path(project)
    selector = validate_selector(selector)
    readiness = _release_readiness(project, selector, pdf_status)
    expected = _expected_candidate(selector, readiness) if readiness["ok"] else None
    candidate = _candidate_status(project, selector, expected)
    ready = bool(readiness["ok"])
    ok = ready and candidate["state"] not in {"tampered", "unsafe"}
    return {
        "schema_version": 1,
        "operation": "manual_release_status",
        "project": str(project),
        "selector": selector,
        "channel": release_channel(selector),
        "publishes": False,
        "ready": ready,
        "ok": ok,
        "issues": readiness["issues"],
        "build_receipt": readiness["build_receipt"],
        "html_audit": readiness["html_audit"],
        "pdf": readiness["pdf"],
        "site_release": readiness["site_release"],
        "stable": readiness["stable"],
        "candidate": candidate,
    }


def release_check(project: Path | str, selector: str, pdf_status: dict[str, Any]) -> dict[str, Any]:
    result = release_status(project, selector, pdf_status)
    candidate_current = result["candidate"].get("state") == "current"
    return {
        **result,
        "operation": "manual_release_check",
        "ok": bool(result["ready"] and candidate_current),
        "candidate_current": candidate_current,
    }


def _write_new_file_at(parent_fd: int, name: str, content: bytes, mode: int = 0o644) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            mode,
            dir_fd=parent_fd,
        )
        remaining = memoryview(content)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write")
            remaining = remaining[written:]
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        os.fsync(parent_fd)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _copy_verified(
    project: Path,
    source: Path,
    destination_parent_fd: int,
    destination_name: str,
    expected: dict[str, Any],
) -> None:
    source_fd: int | None = None
    destination_fd: int | None = None
    try:
        source_fd = _open_confined_regular(project, source, label="candidate source")
        source_before = os.fstat(source_fd)
        if not stat.S_ISREG(source_before.st_mode):
            raise ManualReleaseError(f"Candidate source is not a regular file: {source.as_posix()}")
        destination_fd = os.open(
            destination_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            int(expected["mode"]),
            dir_fd=destination_parent_fd,
        )
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            remaining = memoryview(chunk)
            while remaining:
                written = os.write(destination_fd, remaining)
                if written <= 0:
                    raise OSError("short write")
                remaining = remaining[written:]
        source_after = os.fstat(source_fd)
        identity_before = (source_before.st_dev, source_before.st_ino, source_before.st_size, source_before.st_mtime_ns, source_before.st_ctime_ns)
        identity_after = (source_after.st_dev, source_after.st_ino, source_after.st_size, source_after.st_mtime_ns, source_after.st_ctime_ns)
        if identity_before != identity_after:
            raise ManualReleaseError(f"Candidate source changed while it was copied: {source.as_posix()}")
        if (digest.hexdigest(), size) != (expected["sha256"], expected["size"]):
            raise ManualReleaseError(f"Candidate source no longer matches verified output: {source.as_posix()}")
        os.fchmod(destination_fd, int(expected["mode"]))
        os.fsync(destination_fd)
        os.fsync(destination_parent_fd)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot stage candidate file {destination_name}: {exc}") from exc
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)


def _stage_candidate(
    project: Path,
    root_fd: int,
    expected: dict[str, Any],
    readiness: dict[str, Any],
) -> tuple[str, int]:
    stage_name = ""
    for _ in range(32):
        candidate = f".prepare-{os.getpid()}-{secrets.token_hex(8)}"
        try:
            os.mkdir(candidate, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            continue
        stage_name = candidate
        break
    if not stage_name:
        raise ManualReleaseError("Could not allocate a private candidate staging directory.")
    stage = Path(f"/proc/self/fd/{root_fd}") / stage_name
    stage_fd: int | None = None
    try:
        stage_fd = os.open(
            stage_name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        for relative, mode in sorted(expected["directories"].items(), key=lambda item: (item[0].count("/"), item[0])):
            destination = _validate_relative(relative, label="candidate directory")
            directory_fd = _open_directory_at(stage_fd, destination, create=True)
            try:
                os.fchmod(directory_fd, 0o755)
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        site_files = {record["path"]: record for record in readiness["_receipt"]["_site_snapshot"]["files"]}
        for relative, record in sorted(expected["files"].items()):
            destination = _validate_relative(relative, label="candidate file")
            parent_fd = _open_directory_at(stage_fd, destination.parent, create=False)
            try:
                if "content" in record:
                    _write_new_file_at(parent_fd, destination.name, record["content"], int(record["mode"]))
                elif relative.startswith("site/"):
                    source_relative = relative[len("site/"):]
                    source_record = site_files[source_relative]
                    _copy_verified(project, Path("_site") / source_relative, parent_fd, destination.name, source_record)
                elif relative.startswith("pdf/"):
                    pdf = next(item for item in readiness["_pdfs"] if item["path"] == relative)
                    _copy_verified(project, Path("_site") / pdf["published_path"], parent_fd, destination.name, record)
                else:
                    raise ManualReleaseError(f"Unexpected candidate file: {relative}")
            finally:
                os.close(parent_fd)
        for relative, mode in sorted(expected["directories"].items(), key=lambda item: (item[0].count("/"), item[0]), reverse=True):
            directory_fd = _open_directory_at(stage_fd, _validate_relative(relative, label="candidate directory"), create=False)
            try:
                os.fchmod(directory_fd, int(mode))
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        os.fchmod(stage_fd, 0o755)
        os.fsync(stage_fd)
        verified = _candidate_status(project, str(expected["manifest"]["selector"]), expected, candidate_path=stage)
        if verified.get("ok") is not True:
            raise ManualReleaseError(str(verified.get("error") or "Staged candidate verification failed."))
        staged_metadata = os.stat(stage_name, dir_fd=root_fd, follow_symlinks=False)
        opened_metadata = os.fstat(stage_fd)
        if (staged_metadata.st_dev, staged_metadata.st_ino) != (opened_metadata.st_dev, opened_metadata.st_ino):
            raise ManualReleaseError("Staged candidate path changed before installation.")
        return stage_name, stage_fd
    except BaseException:
        if stage_fd is not None:
            try:
                _remove_tree_at(root_fd, stage_name, expected_fd=stage_fd)
            except (ManualReleaseError, OSError):
                pass
            os.close(stage_fd)
        else:
            try:
                os.rmdir(stage_name, dir_fd=root_fd)
            except OSError:
                pass
        raise


def _remove_tree_at(parent_fd: int, name: str, *, expected_fd: int | None = None) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    tree_fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        if expected_fd is not None:
            actual = os.fstat(tree_fd)
            expected = os.fstat(expected_fd)
            if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                raise ManualReleaseError(f"Refusing to clean a replaced staging directory: {name}")

        def clear(directory_fd: int) -> None:
            os.fchmod(directory_fd, 0o700)
            with os.scandir(directory_fd) as iterator:
                entries = list(iterator)
            for entry in entries:
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(child_fd)
                        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                            raise ManualReleaseError(f"Cleanup path changed while it was inspected: {entry.name}")
                        clear(child_fd)
                    finally:
                        os.close(child_fd)
                    os.rmdir(entry.name, dir_fd=directory_fd)
                else:
                    os.unlink(entry.name, dir_fd=directory_fd)
            os.fsync(directory_fd)

        clear(tree_fd)
    finally:
        os.close(tree_fd)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _exchange_directories(parent_fd: int, staged: str, current: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ManualReleaseError("Atomic latest replacement requires renameat2 support.")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(staged), parent_fd, os.fsencode(current), 2) != 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise ManualReleaseError("Atomic latest replacement is not supported by this filesystem.")
        raise ManualReleaseError(f"Atomic latest replacement failed: {os.strerror(error)}")


def _install_new_directory(parent_fd: int, staged: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ManualReleaseError("Atomic no-clobber candidate installation requires renameat2 support.")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(staged), parent_fd, os.fsencode(target), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise ManualReleaseError(f"Candidate destination appeared during installation: {target}")
        if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise ManualReleaseError("Atomic no-clobber candidate installation is not supported by this filesystem.")
        raise ManualReleaseError(f"Atomic no-clobber candidate installation failed: {os.strerror(error)}")


def release_prepare(
    project: Path | str,
    selector: str,
    pdf_status: dict[str, Any],
    *,
    dry_run: bool = True,
    confirm_prepare: bool = False,
) -> dict[str, Any]:
    if not dry_run and not confirm_prepare:
        raise RuntimeError("A real manual release preparation requires confirm_prepare=True after reviewing the dry-run.")
    project = _project_path(project)
    selector = validate_selector(selector)
    readiness = _release_readiness(project, selector, pdf_status)
    expected = _expected_candidate(selector, readiness) if readiness["ok"] else None
    candidate = _candidate_status(project, selector, expected)
    plan = "reuse" if candidate["state"] == "current" else ("replace" if candidate["exists"] else "create")
    base = {
        "schema_version": 1,
        "operation": "manual_release_prepare",
        "project": str(project),
        "selector": selector,
        "channel": release_channel(selector),
        "publishes": False,
        "dry_run": dry_run,
        "confirmed": confirm_prepare,
        "ready": bool(readiness["ok"]),
        "issues": readiness["issues"],
        "build_receipt": readiness["build_receipt"],
        "html_audit": readiness["html_audit"],
        "pdf": readiness["pdf"],
        "site_release": readiness["site_release"],
        "stable": readiness["stable"],
        "candidate": candidate,
        "plan": plan,
    }
    if not readiness["ok"]:
        return {**base, "ok": False, "prepared": False}
    if candidate["state"] == "unsafe":
        return {**base, "ok": False, "prepared": False, "error": candidate["error"]}
    if selector != "latest" and candidate["exists"] and candidate["state"] != "current":
        return {
            **base,
            "ok": False,
            "prepared": False,
            "error": "Stable local candidates are no-clobber evidence; choose a new selector or restore the byte-identical candidate.",
        }
    if dry_run or candidate["state"] == "current":
        return {**base, "ok": True, "prepared": False, "idempotent": candidate["state"] == "current"}

    try:
        root_fd = _open_confined_directory(project, RELEASE_ROOT, create=True)
    except OSError as exc:
        raise ManualReleaseError(f"Cannot open confined manual release root: {exc}") from exc
    assert root_fd is not None
    root = Path(f"/proc/self/fd/{root_fd}")
    stage_name: str | None = None
    stage_fd: int | None = None
    cleanup_error = ""
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        locked_candidate = _candidate_status(project, selector, expected, candidate_path=root / selector)
        locked_candidate["path"] = (RELEASE_ROOT / selector).as_posix()
        if locked_candidate["state"] == "current":
            return {**base, "ok": True, "prepared": False, "idempotent": True, "candidate": locked_candidate, "plan": "reuse"}
        if selector != "latest" and locked_candidate["exists"]:
            return {
                **base,
                "ok": False,
                "prepared": False,
                "candidate": locked_candidate,
                "error": "Stable local candidates are no-clobber evidence; choose a new selector or restore the byte-identical candidate.",
            }
        stage_name, stage_fd = _stage_candidate(project, root_fd, expected, readiness)

        final_readiness = _release_readiness(project, selector, pdf_status)
        if not final_readiness["ok"]:
            raise ManualReleaseError("Release inputs changed or became invalid while the candidate was staged.")
        final_expected = _expected_candidate(selector, final_readiness)
        if final_expected["manifest"] != expected["manifest"] or {
            path: (record["sha256"], record["size"], record["mode"])
            for path, record in final_expected["files"].items()
        } != {
            path: (record["sha256"], record["size"], record["mode"])
            for path, record in expected["files"].items()
        }:
            raise ManualReleaseError("Release inputs changed while the candidate was staged.")

        staged_metadata = os.stat(stage_name, dir_fd=root_fd, follow_symlinks=False)
        opened_stage_metadata = os.fstat(stage_fd)
        if (staged_metadata.st_dev, staged_metadata.st_ino) != (
            opened_stage_metadata.st_dev,
            opened_stage_metadata.st_ino,
        ):
            raise ManualReleaseError("Staged candidate path changed before atomic installation.")
        target_metadata = None
        if selector == "latest":
            try:
                target_metadata = os.stat(selector, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
        if selector == "latest" and target_metadata is not None:
            if not stat.S_ISDIR(target_metadata.st_mode):
                raise ManualReleaseError(f"Candidate destination is not a real directory: {(RELEASE_ROOT / selector).as_posix()}")
            _exchange_directories(root_fd, stage_name, selector)
            installed_metadata = os.stat(selector, dir_fd=root_fd, follow_symlinks=False)
            if (installed_metadata.st_dev, installed_metadata.st_ino) != (
                opened_stage_metadata.st_dev,
                opened_stage_metadata.st_ino,
            ):
                raise ManualReleaseError("Installed latest candidate does not match the verified staging directory.")
            old_name = stage_name
            stage_name = None
            try:
                _remove_tree_at(root_fd, old_name)
            except (ManualReleaseError, OSError) as exc:
                cleanup_error = str(exc)
        else:
            _install_new_directory(root_fd, stage_name, selector)
            installed_metadata = os.stat(selector, dir_fd=root_fd, follow_symlinks=False)
            if (installed_metadata.st_dev, installed_metadata.st_ino) != (
                opened_stage_metadata.st_dev,
                opened_stage_metadata.st_ino,
            ):
                raise ManualReleaseError("Installed candidate does not match the verified staging directory.")
            stage_name = None
        os.fsync(root_fd)
    except OSError as exc:
        raise ManualReleaseError(f"Atomic candidate installation failed: {exc}") from exc
    finally:
        if stage_name is not None and stage_fd is not None:
            try:
                _remove_tree_at(root_fd, stage_name, expected_fd=stage_fd)
            except (ManualReleaseError, OSError):
                pass
        if stage_fd is not None:
            os.close(stage_fd)
        os.close(root_fd)

    final_status = release_status(project, selector, pdf_status)
    checked = final_status["candidate"]
    result = {
        **base,
        "ok": bool(final_status["ready"] and checked["state"] == "current"),
        "prepared": True,
        "idempotent": False,
        "ready": final_status["ready"],
        "issues": final_status["issues"],
        "build_receipt": final_status["build_receipt"],
        "html_audit": final_status["html_audit"],
        "pdf": final_status["pdf"],
        "site_release": final_status["site_release"],
        "stable": final_status["stable"],
        "candidate": checked,
    }
    if cleanup_error:
        result["cleanup_warning"] = cleanup_error
    return result


def _stdin_pdf_status() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {"configuration_ok": False, "ready_to_publish": False, "published_current": False, "languages": [], "input_error": "manual_pdf_status returned no JSON output."}
    try:
        value = _strict_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return {"configuration_ok": False, "ready_to_publish": False, "published_current": False, "languages": [], "input_error": f"manual_pdf_status returned invalid JSON: {exc}"}
    if not isinstance(value, dict):
        return {"configuration_ok": False, "ready_to_publish": False, "published_current": False, "languages": [], "input_error": "manual_pdf_status JSON must be an object."}
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unaltraweb-manual-release")
    parser.add_argument("command", choices=["status", "check", "prepare"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--selector", default=os.environ.get("MANUAL_RELEASE_SELECTOR", "latest"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-prepare", action="store_true")
    args = parser.parse_args(argv)
    pdf_status = _stdin_pdf_status()
    try:
        if args.command == "status":
            result = release_status(args.project, args.selector, pdf_status)
        elif args.command == "check":
            result = release_check(args.project, args.selector, pdf_status)
        else:
            result = release_prepare(
                args.project,
                args.selector,
                pdf_status,
                dry_run=not args.apply,
                confirm_prepare=args.confirm_prepare,
            )
    except (ManualReleaseError, RuntimeError, ValueError, OSError) as exc:
        result = {
            "ok": False,
            "operation": f"manual_release_{args.command}",
            "project": str(Path(args.project).expanduser()),
            "selector": args.selector,
            "publishes": False,
            "error": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
