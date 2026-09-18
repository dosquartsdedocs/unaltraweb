from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterator


RECEIPT_PATH = Path(".cache/unaltraweb/manual-pdf-preview.json")
PUBLICATION_RECEIPT_PATH = Path(".cache/unaltraweb/manual-pdf-publication.json")
PUBLICATION_INTENT_PATH = Path(".cache/unaltraweb/manual-pdf-publication-intent.json")
LOCK_PATH = Path(".cache/unaltraweb/manual-pdf-preview.lock")
RECOVERY_PATH = Path(".cache/unaltraweb/manual-pdf-preview-recovery")
SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_ARTIFACTS = 100
LANGUAGE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
IDENTITY_KEYS = ("device", "inode", "mode", "mtime_ns", "ctime_ns", "uid", "gid", "nlink")
OWNED_FILE_KEYS = (
    "sha256", "size", "device", "inode", "mode", "mtime_ns", "uid", "gid", "nlink", "xattrs_sha256",
)


class ManualPdfPreviewError(RuntimeError):
    pass


class RecoveryRequiredError(OSError):
    def __init__(self, message: str, recovery_paths: list[str]) -> None:
        super().__init__(errno.EBUSY, message)
        self.recovery_paths = recovery_paths


def _identity(metadata: os.stat_result) -> dict[str, int]:
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "nlink": metadata.st_nlink,
    }


def _xattrs_sha256(descriptor: int, relative: Path) -> str:
    try:
        names = sorted(os.listxattr(descriptor))
        digest = hashlib.sha256()
        for name in names:
            encoded_name = os.fsencode(name)
            value = os.getxattr(descriptor, name)
            digest.update(len(encoded_name).to_bytes(8, "big"))
            digest.update(encoded_name)
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
        return digest.hexdigest()
    except OSError as exc:
        raise ManualPdfPreviewError(
            f"Could not inspect extended attributes for preview file: {relative.as_posix()}: {exc}"
        ) from exc


def _strict_json(content: bytes, *, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ManualPdfPreviewError(f"{label} contains a duplicate key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            content.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ManualPdfPreviewError(f"{label} contains a non-finite number: {value}")
            ),
            object_pairs_hook=unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualPdfPreviewError(f"{label} is not valid UTF-8 JSON: {exc}") from exc


def _relative(raw: Any, *, label: str) -> Path:
    value = str(raw or "")
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or path == Path(".")
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(character) < 32 for character in value)
    ):
        raise ManualPdfPreviewError(f"{label} must be a normalized project-relative path: {value!r}")
    if path.as_posix() != value:
        raise ManualPdfPreviewError(f"{label} must use its normalized POSIX spelling: {value!r}")
    return path


def _run_git(project: Path, arguments: list[str], *, allowed: set[int] | None = None) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    for name in [
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ]:
        environment.pop(name, None)
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={project}", "-C", str(project), *arguments],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ManualPdfPreviewError(f"Could not inspect preview destinations with Git: {exc}") from exc
    accepted = allowed or {0}
    if completed.returncode not in accepted:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ManualPdfPreviewError(f"Could not inspect preview destinations with Git: {detail or 'Git returned no detail.'}")
    return completed


def _require_git_root(project: Path) -> None:
    output = _run_git(project, ["rev-parse", "--show-toplevel"]).stdout.decode("utf-8", errors="strict").strip()
    if Path(output).resolve() != project:
        raise ManualPdfPreviewError(f"Manual PDF preview preparation requires the Git worktree root: {project}")


def _git_state(project: Path, relative: Path) -> tuple[bool, bool]:
    name = relative.as_posix()
    tracked = bool(_run_git(project, ["ls-files", "--stage", "-z", "--", name]).stdout)
    ignored_result = _run_git(
        project,
        ["check-ignore", "--quiet", "--no-index", "--", name],
        allowed={0, 1},
    )
    return tracked, ignored_result.returncode == 0


def _require_generated_path(project: Path, relative: Path, *, label: str) -> None:
    tracked, ignored = _git_state(project, relative)
    if tracked:
        raise ManualPdfPreviewError(f"{label} must not be tracked by Git: {relative.as_posix()}")
    if not ignored:
        raise ManualPdfPreviewError(f"{label} must be ignored by Git: {relative.as_posix()}")


def _open_directory(root_fd: int, relative: Path, *, create: bool = False) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    current_fd = os.dup(root_fd)
    try:
        if relative == Path("."):
            return current_fd
        for part in relative.parts:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=current_fd)
                    os.fsync(current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=current_fd)
            try:
                metadata = os.fstat(next_fd)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ManualPdfPreviewError(f"Preview path ancestor is not a directory: {relative.as_posix()}")
            except BaseException:
                os.close(next_fd)
                raise
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _open_regular_name(parent_fd: int, name: str, relative: Path, *, label: str) -> int:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ManualPdfPreviewError(f"{label} must be a regular file: {relative.as_posix()}")
        return descriptor
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _open_regular(root_fd: int, relative: Path, *, label: str) -> int:
    try:
        parent_fd = _open_directory(root_fd, relative.parent)
    except (FileNotFoundError, OSError) as exc:
        raise ManualPdfPreviewError(f"Cannot open {label} parent for {relative.as_posix()}: {exc}") from exc
    try:
        return _open_regular_name(parent_fd, relative.name, relative, label=label)
    finally:
        os.close(parent_fd)


def _record_descriptor(descriptor: int, relative: Path) -> dict[str, Any]:
    before = os.fstat(descriptor)
    xattrs_before = _xattrs_sha256(descriptor, relative)
    digest = hashlib.sha256()
    size = 0
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(descriptor)
    xattrs_after = _xattrs_sha256(descriptor, relative)
    if (
        _identity(before) != _identity(after)
        or before.st_size != after.st_size
        or size != after.st_size
        or xattrs_before != xattrs_after
    ):
        raise ManualPdfPreviewError(f"Preview file changed while it was read: {relative.as_posix()}")
    os.lseek(descriptor, 0, os.SEEK_SET)
    return {
        "path": relative.as_posix(),
        "sha256": digest.hexdigest(),
        "size": size,
        "xattrs_sha256": xattrs_after,
        **_identity(after),
    }


def _read_small_regular(root_fd: int, relative: Path, *, label: str, limit: int) -> bytes:
    descriptor = _open_regular(root_fd, relative, label=label)
    try:
        metadata = os.fstat(descriptor)
        if metadata.st_size > limit:
            raise ManualPdfPreviewError(f"{label} exceeds the {limit}-byte limit: {relative.as_posix()}")
        content = bytearray()
        while len(content) <= limit:
            chunk = os.read(descriptor, min(65536, limit + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        final = os.fstat(descriptor)
        if _identity(metadata) != _identity(final) or metadata.st_size != final.st_size:
            raise ManualPdfPreviewError(f"{label} changed while it was read: {relative.as_posix()}")
        if len(content) > limit:
            raise ManualPdfPreviewError(f"{label} exceeds the {limit}-byte limit: {relative.as_posix()}")
        return bytes(content)
    finally:
        os.close(descriptor)


def config_sha256(project: Path | str) -> str:
    project = Path(project).expanduser().resolve()
    root_fd = os.open(project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        content = _read_small_regular(root_fd, Path("_config.yml"), label="site configuration", limit=MAX_RECEIPT_BYTES)
    finally:
        os.close(root_fd)
    return hashlib.sha256(content).hexdigest()


def receipt_present(project: Path | str) -> bool:
    path = Path(project).expanduser().resolve() / RECEIPT_PATH
    return path.exists() or path.is_symlink()


def _existing_record(root_fd: int, relative: Path, *, label: str) -> dict[str, Any] | None:
    try:
        descriptor = _open_regular(root_fd, relative, label=label)
    except FileNotFoundError:
        return None
    except ManualPdfPreviewError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    try:
        return _record_descriptor(descriptor, relative)
    finally:
        os.close(descriptor)


def matching_public_languages(
    project: Path | str,
    languages: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    project = Path(project).expanduser().resolve()
    root_fd = os.open(project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    matches: dict[str, dict[str, dict[str, Any]]] = {}
    selected_languages: set[str] = set()
    try:
        for language_status in languages:
            language = str(language_status.get("language") or "")
            if not LANGUAGE_RE.fullmatch(language):
                raise ManualPdfPreviewError(f"Manual PDF status contains an invalid language: {language!r}")
            if language in selected_languages:
                raise ManualPdfPreviewError(f"Manual PDF status contains duplicate language entries: {language}")
            selected_languages.add(language)
            records: dict[str, dict[str, Any]] = {}
            for kind, source_key, destination_key in [
                ("pdf", "generated_pdf", "published_pdf"),
                ("cover", "generated_cover", "published_cover"),
            ]:
                source = _relative(language_status.get(source_key), label=f"generated {kind}")
                destination = _relative(language_status.get(destination_key), label=f"published {kind}")
                source_record = _existing_record(root_fd, source, label=f"generated {kind}")
                destination_record = _existing_record(root_fd, destination, label=f"published {kind}")
                if (
                    source_record is None
                    or destination_record is None
                    or source_record["sha256"] != destination_record["sha256"]
                    or source_record["size"] != destination_record["size"]
                ):
                    continue
                records[kind] = destination_record
            if records:
                matches[language] = records
        return matches
    finally:
        os.close(root_fd)


def _validate_entry(value: Any) -> dict[str, Any]:
    required = {
        "language", "kind", "source", "destination", "sha256", "size",
        "device", "inode", "mode", "mtime_ns", "uid", "gid", "nlink", "xattrs_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF preview receipt contains an invalid artifact entry.")
    language = str(value["language"])
    kind = str(value["kind"])
    source = _relative(value["source"], label="receipt source")
    destination = _relative(value["destination"], label="receipt destination")
    if not LANGUAGE_RE.fullmatch(language) or kind not in {"pdf", "cover"}:
        raise ManualPdfPreviewError("Manual PDF preview receipt contains invalid artifact metadata.")
    digest = str(value["sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ManualPdfPreviewError("Manual PDF preview receipt contains an invalid SHA-256 digest.")
    xattrs_digest = str(value["xattrs_sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", xattrs_digest):
        raise ManualPdfPreviewError("Manual PDF preview receipt contains an invalid extended-attribute digest.")
    integer_keys = ["size", "device", "inode", "mode", "mtime_ns", "uid", "gid", "nlink"]
    if any(not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < 0 for key in integer_keys):
        raise ManualPdfPreviewError("Manual PDF preview receipt contains invalid file identity metadata.")
    return {
        **value,
        "language": language,
        "kind": kind,
        "source": source.as_posix(),
        "destination": destination.as_posix(),
        "sha256": digest,
        "xattrs_sha256": xattrs_digest,
    }


def _read_receipt(root_fd: int) -> dict[str, Any] | None:
    try:
        content = _read_small_regular(
            root_fd,
            RECEIPT_PATH,
            label="manual PDF preview receipt",
            limit=MAX_RECEIPT_BYTES,
        )
    except FileNotFoundError:
        return None
    except ManualPdfPreviewError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    value = _strict_json(content, label="Manual PDF preview receipt")
    required = {"schema_version", "operation", "config_sha256", "artifacts"}
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF preview receipt has an unsupported structure.")
    if value["schema_version"] != SCHEMA_VERSION or value["operation"] != "manual-pdf-preview":
        raise ManualPdfPreviewError("Manual PDF preview receipt has an unsupported schema or operation.")
    config_digest = str(value["config_sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", config_digest):
        raise ManualPdfPreviewError("Manual PDF preview receipt has an invalid configuration digest.")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Manual PDF preview receipt must contain a bounded non-empty artifact list.")
    validated = [_validate_entry(entry) for entry in artifacts]
    destinations = [entry["destination"] for entry in validated]
    if len(destinations) != len(set(destinations)):
        raise ManualPdfPreviewError("Manual PDF preview receipt contains duplicate destinations.")
    language_kinds = [(entry["language"], entry["kind"]) for entry in validated]
    if len(language_kinds) != len(set(language_kinds)):
        raise ManualPdfPreviewError("Manual PDF preview receipt contains duplicate language artifacts.")
    return {
        **value,
        "config_sha256": config_digest,
        "artifacts": validated,
        "_sha256": hashlib.sha256(content).hexdigest(),
    }


def _validate_publication_entry(value: Any) -> dict[str, Any]:
    required = {
        "language", "kind", "destination", "sha256", "size",
        "device", "inode", "mode", "mtime_ns", "uid", "gid", "nlink", "xattrs_sha256",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF publication receipt contains an invalid artifact entry.")
    language = str(value["language"])
    kind = str(value["kind"])
    destination = _relative(value["destination"], label="publication receipt destination")
    digest = str(value["sha256"])
    if not LANGUAGE_RE.fullmatch(language) or kind not in {"pdf", "cover"}:
        raise ManualPdfPreviewError("Manual PDF publication receipt contains invalid artifact metadata.")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ManualPdfPreviewError("Manual PDF publication receipt contains an invalid SHA-256 digest.")
    xattrs_digest = str(value["xattrs_sha256"])
    if not re.fullmatch(r"[0-9a-f]{64}", xattrs_digest):
        raise ManualPdfPreviewError("Manual PDF publication receipt contains an invalid extended-attribute digest.")
    integer_keys = ["size", "device", "inode", "mode", "mtime_ns", "uid", "gid", "nlink"]
    if any(not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < 0 for key in integer_keys):
        raise ManualPdfPreviewError("Manual PDF publication receipt contains invalid file identity metadata.")
    return {
        **value,
        "language": language,
        "kind": kind,
        "destination": destination.as_posix(),
        "sha256": digest,
        "xattrs_sha256": xattrs_digest,
    }


def _read_publication_receipt(root_fd: int) -> dict[str, Any] | None:
    try:
        content = _read_small_regular(
            root_fd,
            PUBLICATION_RECEIPT_PATH,
            label="manual PDF publication receipt",
            limit=MAX_RECEIPT_BYTES,
        )
    except FileNotFoundError:
        return None
    except ManualPdfPreviewError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    value = _strict_json(content, label="Manual PDF publication receipt")
    required = {"schema_version", "operation", "artifacts"}
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF publication receipt has an unsupported structure.")
    if value["schema_version"] != SCHEMA_VERSION or value["operation"] != "manual-pdf-publication":
        raise ManualPdfPreviewError("Manual PDF publication receipt has an unsupported schema or operation.")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Manual PDF publication receipt must contain a bounded non-empty artifact list.")
    validated = [_validate_publication_entry(entry) for entry in artifacts]
    destinations = [entry["destination"] for entry in validated]
    if len(destinations) != len(set(destinations)):
        raise ManualPdfPreviewError("Manual PDF publication receipt contains duplicate destinations.")
    language_kinds = [(entry["language"], entry["kind"]) for entry in validated]
    if len(language_kinds) != len(set(language_kinds)):
        raise ManualPdfPreviewError("Manual PDF publication receipt contains duplicate language artifacts.")
    return {
        **value,
        "artifacts": validated,
        "_sha256": hashlib.sha256(content).hexdigest(),
    }


def _validate_publication_intent_entry(value: Any) -> dict[str, Any]:
    required = {"language", "kind", "source", "destination", "sha256", "size"}
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF publication intent contains an invalid artifact entry.")
    language = str(value["language"])
    kind = str(value["kind"])
    source = _relative(value["source"], label="publication intent source")
    destination = _relative(value["destination"], label="publication intent destination")
    digest = str(value["sha256"])
    size = value["size"]
    if not LANGUAGE_RE.fullmatch(language) or kind not in {"pdf", "cover"}:
        raise ManualPdfPreviewError("Manual PDF publication intent contains invalid artifact metadata.")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ManualPdfPreviewError("Manual PDF publication intent contains an invalid SHA-256 digest.")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ManualPdfPreviewError("Manual PDF publication intent contains an invalid artifact size.")
    return {
        **value,
        "language": language,
        "kind": kind,
        "source": source.as_posix(),
        "destination": destination.as_posix(),
        "sha256": digest,
        "size": size,
    }


def _read_publication_intent(root_fd: int) -> dict[str, Any] | None:
    try:
        content = _read_small_regular(
            root_fd,
            PUBLICATION_INTENT_PATH,
            label="manual PDF publication intent",
            limit=MAX_RECEIPT_BYTES,
        )
    except FileNotFoundError:
        return None
    except ManualPdfPreviewError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    value = _strict_json(content, label="Manual PDF publication intent")
    required = {"schema_version", "operation", "artifacts"}
    if not isinstance(value, dict) or set(value) != required:
        raise ManualPdfPreviewError("Manual PDF publication intent has an unsupported structure.")
    if value["schema_version"] != SCHEMA_VERSION or value["operation"] != "manual-pdf-publication-intent":
        raise ManualPdfPreviewError("Manual PDF publication intent has an unsupported schema or operation.")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not artifacts or len(artifacts) > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Manual PDF publication intent must contain a bounded non-empty artifact list.")
    validated = [_validate_publication_intent_entry(entry) for entry in artifacts]
    destinations = [entry["destination"] for entry in validated]
    if len(destinations) != len(set(destinations)):
        raise ManualPdfPreviewError("Manual PDF publication intent contains duplicate destinations.")
    language_kinds = [(entry["language"], entry["kind"]) for entry in validated]
    if len(language_kinds) != len(set(language_kinds)):
        raise ManualPdfPreviewError("Manual PDF publication intent contains duplicate language artifacts.")
    return {
        **value,
        "artifacts": validated,
        "_sha256": hashlib.sha256(content).hexdigest(),
    }


@contextlib.contextmanager
def _locked_project(project: Path) -> Iterator[tuple[int, int]]:
    _require_git_root(project)
    root_fd = os.open(project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    lock_fd: int | None = None
    try:
        # The directory inode cannot be bypassed by unlinking the visible marker file.
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        for relative, label in [
            (RECEIPT_PATH, "Preview receipt"),
            (PUBLICATION_RECEIPT_PATH, "Publication receipt"),
            (PUBLICATION_INTENT_PATH, "Publication intent"),
            (LOCK_PATH, "Preview lock"),
        ]:
            _require_generated_path(project, relative, label=label)
        parent_fd = _open_directory(root_fd, LOCK_PATH.parent, create=True)
        try:
            lock_fd = os.open(
                LOCK_PATH.name,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent_fd,
            )
            if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
                raise ManualPdfPreviewError(f"Preview lock must be a regular file: {LOCK_PATH.as_posix()}")
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            current = os.stat(LOCK_PATH.name, dir_fd=parent_fd, follow_symlinks=False)
            locked = os.fstat(lock_fd)
            if (current.st_dev, current.st_ino) != (locked.st_dev, locked.st_ino):
                raise ManualPdfPreviewError("Preview lock was replaced while it was acquired.")
        finally:
            os.close(parent_fd)
        yield root_fd, lock_fd
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(root_fd)


@contextlib.contextmanager
def project_lock(project: Path | str) -> Iterator[None]:
    resolved = Path(project).expanduser().resolve()
    with _locked_project(resolved):
        yield


@contextlib.contextmanager
def _locked_git_index(project: Path) -> Iterator[Callable[[], None]]:
    output = _run_git(project, ["rev-parse", "--path-format=absolute", "--git-path", "index"])
    index_path = Path(output.stdout.decode("utf-8", errors="strict").strip())
    if not index_path.is_absolute() or index_path.name != "index":
        raise ManualPdfPreviewError("Git returned an invalid index path for preview staging.")
    common_output = _run_git(project, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
    common_path = Path(common_output.stdout.decode("utf-8", errors="strict").strip()).resolve()
    index_parent = index_path.parent.resolve()
    if index_parent != common_path and common_path not in index_parent.parents:
        raise ManualPdfPreviewError("Git returned an index path outside its common directory for preview staging.")
    lock_path = index_path.with_name(index_path.name + ".lock")
    descriptor: int | None = None
    metadata: os.stat_result | None = None
    body_failed = False

    def verify() -> None:
        if descriptor is None or metadata is None:
            raise ManualPdfPreviewError("Git index lock is not held.")
        try:
            current = os.stat(lock_path, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise ManualPdfPreviewError("Git index lock was removed during manual PDF preview staging.") from exc
        if (
            not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)
        ):
            raise ManualPdfPreviewError("Git index lock was replaced during manual PDF preview staging.")

    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        metadata = os.fstat(descriptor)
        verify()
        try:
            yield verify
        except BaseException:
            body_failed = True
            raise
    except FileExistsError as exc:
        raise ManualPdfPreviewError("Git index is busy; retry manual PDF preview staging after the current Git operation finishes.") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if metadata is not None:
            try:
                current = os.stat(lock_path, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (metadata.st_dev, metadata.st_ino):
                    os.unlink(lock_path)
                elif not body_failed:
                    raise ManualPdfPreviewError("Git index lock was replaced before it could be released safely.")
            except FileNotFoundError:
                if not body_failed:
                    raise ManualPdfPreviewError("Git index lock disappeared before it could be released safely.")


def _receipt_bytes(config_digest: str, artifacts: list[dict[str, Any]]) -> bytes:
    value = {
        "schema_version": SCHEMA_VERSION,
        "operation": "manual-pdf-preview",
        "config_sha256": config_digest,
        "artifacts": artifacts,
    }
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publication_receipt_bytes(artifacts: list[dict[str, Any]]) -> bytes:
    value = {
        "schema_version": SCHEMA_VERSION,
        "operation": "manual-pdf-publication",
        "artifacts": artifacts,
    }
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _publication_intent_bytes(artifacts: list[dict[str, Any]]) -> bytes:
    value = {
        "schema_version": SCHEMA_VERSION,
        "operation": "manual-pdf-publication-intent",
        "artifacts": artifacts,
    }
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_write(root_fd: int, relative: Path, content: bytes) -> None:
    parent_fd = _open_directory(root_fd, relative.parent, create=True)
    temporary = f".{relative.name}.{os.getpid()}.{secrets.token_hex(8)}"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
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
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent_fd)


def _stash_backup(root_fd: int, parent_fd: int, backup: str, destination: Path) -> str:
    recovery_fd = _open_directory(root_fd, RECOVERY_PATH, create=True)
    recovery_name = f"{destination.name}.{secrets.token_hex(8)}.backup"
    recovery_path = (RECOVERY_PATH / recovery_name).as_posix()
    original_path = (destination.parent / backup).as_posix()
    try:
        try:
            os.replace(backup, recovery_name, src_dir_fd=parent_fd, dst_dir_fd=recovery_fd)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            source_fd = _open_regular_name(
                parent_fd,
                backup,
                destination,
                label="preview recovery backup",
            )
            target_fd: int | None = None
            try:
                target_fd = os.open(
                    recovery_name,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                    dir_fd=recovery_fd,
                )
                while True:
                    chunk = os.read(source_fd, 1024 * 1024)
                    if not chunk:
                        break
                    remaining = memoryview(chunk)
                    while remaining:
                        written = os.write(target_fd, remaining)
                        if written <= 0:
                            raise OSError("short write")
                        remaining = remaining[written:]
                os.fsync(target_fd)
                source_record = _record_descriptor(source_fd, destination)
                target_record = _record_descriptor(target_fd, destination)
                current_source = os.stat(backup, dir_fd=parent_fd, follow_symlinks=False)
                current_target = os.stat(recovery_name, dir_fd=recovery_fd, follow_symlinks=False)
                source_matches = (
                    current_source.st_size == source_record["size"]
                    and _identity(current_source) == {
                        key: source_record[key]
                        for key in IDENTITY_KEYS
                    }
                )
                target_matches = (
                    current_target.st_size == target_record["size"]
                    and _identity(current_target) == {
                        key: target_record[key]
                        for key in IDENTITY_KEYS
                    }
                )
                if (
                    source_record["sha256"] != target_record["sha256"]
                    or source_record["size"] != target_record["size"]
                    or source_record["xattrs_sha256"] != target_record["xattrs_sha256"]
                    or not source_matches
                    or not target_matches
                ):
                    recovery_paths = []
                    if target_matches:
                        recovery_paths.append(recovery_path)
                    if source_matches:
                        recovery_paths.append(original_path)
                    raise RecoveryRequiredError(
                        "Backup changed during cross-filesystem recovery.",
                        recovery_paths or [original_path, recovery_path],
                    )
                os.unlink(backup, dir_fd=parent_fd)
            finally:
                os.close(source_fd)
                if target_fd is not None:
                    os.close(target_fd)
        os.fsync(recovery_fd)
        return recovery_path
    except RecoveryRequiredError:
        raise
    except BaseException as exc:
        recovery_paths = []
        for directory_fd, name, path in [
            (parent_fd, backup, original_path),
            (recovery_fd, recovery_name, recovery_path),
        ]:
            try:
                os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                continue
            recovery_paths.append(path)
        if recovery_paths:
            raise RecoveryRequiredError(
                "Backup recovery did not complete; retained files require manual review.",
                recovery_paths,
            ) from exc
        raise
    finally:
        os.close(recovery_fd)


def _same_owned_file(current: dict[str, Any], receipt: dict[str, Any]) -> bool:
    return all(current.get(key) == receipt.get(key) for key in OWNED_FILE_KEYS)


def _move_noreplace(source: str, destination: str, *, source_fd: int, destination_fd: int) -> None:
    os.link(
        source,
        destination,
        src_dir_fd=source_fd,
        dst_dir_fd=destination_fd,
        follow_symlinks=False,
    )
    source_metadata = os.stat(source, dir_fd=source_fd, follow_symlinks=False)
    destination_metadata = os.stat(destination, dir_fd=destination_fd, follow_symlinks=False)
    if (
        source_metadata.st_size != destination_metadata.st_size
        or _identity(source_metadata) != _identity(destination_metadata)
    ):
        raise OSError(errno.EBUSY, "Rollback source changed after its no-replace link was created.")
    os.unlink(source, dir_fd=source_fd)


def _unlink_verified_backup(parent_fd: int, backup: str, plan: dict[str, Any]) -> None:
    descriptor = _open_regular_name(
        parent_fd,
        backup,
        plan["destination"],
        label="previous preview backup",
    )
    try:
        backup_record = _record_descriptor(descriptor, plan["destination"])
        metadata = os.stat(backup, dir_fd=parent_fd, follow_symlinks=False)
    finally:
        os.close(descriptor)
    if not _same_owned_file(backup_record, plan["backup_record"]):
        raise ManualPdfPreviewError(
            f"Previous preview destination changed before backup cleanup: {plan['destination'].as_posix()}"
        )
    if any(
        value != backup_record[key]
        for key, value in {
            "size": metadata.st_size,
            **_identity(metadata),
        }.items()
    ):
        raise ManualPdfPreviewError(
            f"Previous preview destination was replaced before backup cleanup: {plan['destination'].as_posix()}"
        )
    os.unlink(backup, dir_fd=parent_fd)


def _plan_records(root_fd: int, languages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not languages or len(languages) * 2 > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Manual PDF preview requires a bounded non-empty language inventory.")
    plans: list[dict[str, Any]] = []
    destinations: set[str] = set()
    selected_languages: set[str] = set()
    try:
        for language_status in languages:
            language = str(language_status.get("language") or "")
            if not LANGUAGE_RE.fullmatch(language):
                raise ManualPdfPreviewError(f"Manual PDF status contains an invalid language: {language!r}")
            if language in selected_languages:
                raise ManualPdfPreviewError(f"Manual PDF status contains duplicate language entries: {language}")
            selected_languages.add(language)
            if (
                language_status.get("ready_to_publish") is not True
                or language_status.get("fresh") is not True
                or language_status.get("release_selector") != "latest"
            ):
                raise ManualPdfPreviewError(f"Manual PDF language '{language}' is not fresh enough for preview staging.")
            path_pairs = {
                "pdf": (
                    _relative(language_status.get("generated_pdf"), label="generated pdf"),
                    _relative(language_status.get("published_pdf"), label="preview pdf destination"),
                ),
                "cover": (
                    _relative(language_status.get("generated_cover"), label="generated cover"),
                    _relative(language_status.get("published_cover"), label="preview cover destination"),
                ),
            }
            if path_pairs["pdf"][0].parent != path_pairs["cover"][0].parent:
                raise ManualPdfPreviewError(f"Generated manual PDF artifacts do not share one build directory for '{language}'.")
            manifest_path = path_pairs["pdf"][0].parent / "manifest.json"
            manifest = _strict_json(
                _read_small_regular(root_fd, manifest_path, label="manual PDF build manifest", limit=MAX_RECEIPT_BYTES),
                label="Manual PDF build manifest",
            )
            expected_manifest = {
                "language": language,
                "pdf": path_pairs["pdf"][0].as_posix(),
                "cover": path_pairs["cover"][0].as_posix(),
                "public_pdf": path_pairs["pdf"][1].as_posix(),
                "public_cover": path_pairs["cover"][1].as_posix(),
                "release_selector": "latest",
            }
            if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected_manifest.items()):
                raise ManualPdfPreviewError(f"Manual PDF build manifest metadata is not current for '{language}'.")
            if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("fingerprint") or "")):
                raise ManualPdfPreviewError(f"Manual PDF build manifest has no valid fingerprint for '{language}'.")
            artifacts = manifest.get("artifacts")
            if not isinstance(artifacts, dict):
                raise ManualPdfPreviewError(f"Manual PDF build manifest has no artifact inventory for '{language}'.")

            for kind, (source, destination) in path_pairs.items():
                if source == destination or destination in {
                    RECEIPT_PATH,
                    PUBLICATION_RECEIPT_PATH,
                    PUBLICATION_INTENT_PATH,
                    LOCK_PATH,
                }:
                    raise ManualPdfPreviewError(f"Invalid manual PDF preview destination: {destination.as_posix()}")
                if kind == "pdf" and destination.suffix.lower() != ".pdf":
                    raise ManualPdfPreviewError(f"Preview PDF destination must end in .pdf: {destination.as_posix()}")
                if kind == "cover" and destination.suffix.lower() != ".png":
                    raise ManualPdfPreviewError(f"Preview cover destination must end in .png: {destination.as_posix()}")
                if destination.as_posix() in destinations:
                    raise ManualPdfPreviewError(f"Duplicate manual PDF preview destination: {destination.as_posix()}")
                destinations.add(destination.as_posix())
                source_fd = _open_regular(root_fd, source, label=f"generated {kind}")
                plan = {
                    "language": language,
                    "kind": kind,
                    "source": source,
                    "destination": destination,
                    "source_fd": source_fd,
                    "published_current": language_status.get("published_current") is True,
                    "replaceable_previous": (
                        language_status.get("_replaceable_previous_public", {}).get(kind)
                        if isinstance(language_status.get("_replaceable_previous_public"), dict)
                        else None
                    ),
                }
                plans.append(plan)
                source_record = _record_descriptor(source_fd, source)
                plan["source_record"] = source_record
                expected = artifacts.get(kind) if isinstance(artifacts, dict) else None
                if not isinstance(expected, dict) or expected.get("sha256") != source_record["sha256"] or expected.get("size") != source_record["size"]:
                    raise ManualPdfPreviewError(f"Generated {kind} no longer matches its build manifest: {source.as_posix()}")
        return plans
    except BaseException:
        _close_plans(plans)
        raise


def _close_plans(plans: list[dict[str, Any]]) -> None:
    for plan in plans:
        descriptor = plan.get("source_fd")
        if isinstance(descriptor, int):
            try:
                os.close(descriptor)
            except OSError:
                pass
            plan["source_fd"] = None


@contextlib.contextmanager
def _preview_root(project: Path, *, lock_held: bool) -> Iterator[int]:
    if lock_held:
        root_fd = os.open(project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            yield root_fd
        finally:
            os.close(root_fd)
        return
    with _locked_project(project) as (root_fd, _):
        yield root_fd


def known_publication_languages(
    project: Path | str,
    languages: list[dict[str, Any]],
    *,
    lock_held: bool = False,
) -> dict[str, dict[str, dict[str, Any]]]:
    project = Path(project).expanduser().resolve()
    with _preview_root(project, lock_held=lock_held) as root_fd:
        receipt = _read_publication_receipt(root_fd)
        intent = _read_publication_intent(root_fd)
        entries = {
            (entry["language"], entry["kind"]): entry
            for entry in (receipt["artifacts"] if receipt else [])
        }
        intended = {
            (entry["language"], entry["kind"]): entry
            for entry in (intent["artifacts"] if intent else [])
        }
        matches: dict[str, dict[str, dict[str, Any]]] = {}
        selected_languages: set[str] = set()
        for language_status in languages:
            language = str(language_status.get("language") or "")
            if not LANGUAGE_RE.fullmatch(language):
                raise ManualPdfPreviewError(f"Manual PDF status contains an invalid language: {language!r}")
            if language in selected_languages:
                raise ManualPdfPreviewError(f"Manual PDF status contains duplicate language entries: {language}")
            selected_languages.add(language)
            records: dict[str, dict[str, Any]] = {}
            for kind, destination_key in [("pdf", "published_pdf"), ("cover", "published_cover")]:
                destination = _relative(language_status.get(destination_key), label=f"published {kind}")
                entry = entries.get((language, kind))
                current = _existing_record(root_fd, destination, label=f"published {kind}")
                if current is None:
                    continue
                if (
                    entry is not None
                    and entry["destination"] == destination.as_posix()
                    and _same_owned_file(current, entry)
                ):
                    records[kind] = current
                    continue
                pending = intended.get((language, kind))
                if (
                    pending is None
                    or pending["destination"] != destination.as_posix()
                    or pending["sha256"] != current["sha256"]
                    or pending["size"] != current["size"]
                ):
                    continue
                records[kind] = current
            if records:
                matches[language] = records
        return matches


def begin_publication(
    project: Path | str,
    languages: list[dict[str, Any]],
    *,
    lock_held: bool = False,
) -> dict[str, Any]:
    project = Path(project).expanduser().resolve()
    if not languages or len(languages) * 2 > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Publication intent requires a bounded non-empty language inventory.")
    with _preview_root(project, lock_held=lock_held) as root_fd, _locked_git_index(project) as verify_git_index:
        verify_git_index()
        _require_generated_path(project, PUBLICATION_RECEIPT_PATH, label="Publication receipt")
        _require_generated_path(project, PUBLICATION_INTENT_PATH, label="Publication intent")
        _read_publication_receipt(root_fd)
        previous_intent = _read_publication_intent(root_fd)
        artifacts: list[dict[str, Any]] = []
        destinations: set[str] = set()
        selected_languages: set[str] = set()
        for language_status in languages:
            language = str(language_status.get("language") or "")
            if not LANGUAGE_RE.fullmatch(language) or language_status.get("ready_to_publish") is not True:
                raise ManualPdfPreviewError("Manual PDF artifacts are not ready for confirmed publication.")
            if language in selected_languages:
                raise ManualPdfPreviewError(f"Publication intent contains duplicate language entries: {language}")
            selected_languages.add(language)
            for kind, source_key, destination_key in [
                ("pdf", "generated_pdf", "published_pdf"),
                ("cover", "generated_cover", "published_cover"),
            ]:
                source = _relative(language_status.get(source_key), label=f"generated {kind}")
                destination = _relative(language_status.get(destination_key), label=f"published {kind}")
                if source == destination or destination in {
                    RECEIPT_PATH,
                    PUBLICATION_RECEIPT_PATH,
                    PUBLICATION_INTENT_PATH,
                    LOCK_PATH,
                } or destination.as_posix() in destinations:
                    raise ManualPdfPreviewError(f"Invalid publication destination: {destination.as_posix()}")
                destinations.add(destination.as_posix())
                _require_generated_path(project, destination, label="Published manual PDF destination")
                source_record = _existing_record(root_fd, source, label=f"generated {kind}")
                if source_record is None:
                    raise ManualPdfPreviewError(f"Generated {kind} is missing before publication: {source.as_posix()}")
                artifacts.append({
                    "language": language,
                    "kind": kind,
                    "source": source.as_posix(),
                    "destination": destination.as_posix(),
                    "sha256": source_record["sha256"],
                    "size": source_record["size"],
                })
        for entry in previous_intent["artifacts"] if previous_intent else []:
            if entry["language"] in selected_languages:
                continue
            if entry["destination"] in destinations:
                raise ManualPdfPreviewError(
                    f"Publication destination conflicts with an outstanding intent: {entry['destination']}"
                )
            destinations.add(entry["destination"])
            artifacts.append({key: value for key, value in entry.items() if not key.startswith("_")})
        if len(artifacts) > MAX_ARTIFACTS:
            raise ManualPdfPreviewError("Merged publication intent exceeds the artifact limit.")
        artifacts.sort(key=lambda item: (item["language"], item["kind"], item["destination"]))
        verify_git_index()
        _require_generated_path(project, PUBLICATION_INTENT_PATH, label="Publication intent")
        content = _publication_intent_bytes(artifacts)
        _atomic_write(root_fd, PUBLICATION_INTENT_PATH, content)
        return {
            "path": PUBLICATION_INTENT_PATH.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "artifacts": len(artifacts),
        }


def validate_publication_worker(
    project: Path | str,
    expected_intent_sha256: str,
    language: str = "",
) -> dict[str, Any]:
    project = Path(project).expanduser().resolve()
    _require_git_root(project)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_intent_sha256):
        raise ManualPdfPreviewError("Publication worker requires a valid intent SHA-256.")
    if language and not LANGUAGE_RE.fullmatch(language):
        raise ManualPdfPreviewError(f"Publication worker received an invalid language: {language!r}")

    root_fd = os.open(project, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(root_fd, fcntl.LOCK_UN)
            raise ManualPdfPreviewError(
                "Real publication workers must run under the provenance-aware controller project lock."
            )

        with _locked_git_index(project) as verify_git_index:
            verify_git_index()
            _require_generated_path(project, RECEIPT_PATH, label="Preview receipt")
            _require_generated_path(project, PUBLICATION_INTENT_PATH, label="Publication intent")
            if _read_receipt(root_fd) is not None:
                raise ManualPdfPreviewError("Clean receipt-owned manual PDF preview files before real publication.")
            intent = _read_publication_intent(root_fd)
            if intent is None or intent["_sha256"] != expected_intent_sha256:
                raise ManualPdfPreviewError("Publication worker intent does not match its controller authorization.")
            selected = [
                entry
                for entry in intent["artifacts"]
                if not language or entry["language"] == language
            ]
            if not selected:
                raise ManualPdfPreviewError("Publication worker intent does not contain the selected language.")
            selected_pairs = {(entry["language"], entry["kind"]) for entry in selected}
            selected_languages = {entry["language"] for entry in selected}
            if selected_pairs != {
                (selected_language, kind)
                for selected_language in selected_languages
                for kind in ["pdf", "cover"]
            }:
                raise ManualPdfPreviewError("Publication worker intent must contain one PDF and cover per language.")
            for entry in selected:
                source = _relative(entry["source"], label="publication intent source")
                destination = _relative(entry["destination"], label="publication intent destination")
                _require_generated_path(project, destination, label="Published manual PDF destination")
                current = _existing_record(root_fd, source, label=f"generated {entry['kind']}")
                if (
                    current is None
                    or current["sha256"] != entry["sha256"]
                    or current["size"] != entry["size"]
                ):
                    raise ManualPdfPreviewError(
                        f"Generated {entry['kind']} changed after publication was confirmed: {source.as_posix()}"
                    )
            verify_git_index()
            return {
                "ok": True,
                "intent_sha256": expected_intent_sha256,
                "languages": sorted(selected_languages),
                "artifacts": len(selected),
            }
    finally:
        os.close(root_fd)


def record_publication(
    project: Path | str,
    languages: list[dict[str, Any]],
    *,
    lock_held: bool = False,
    expected_intent_sha256: str = "",
) -> dict[str, Any]:
    project = Path(project).expanduser().resolve()
    if not languages or len(languages) * 2 > MAX_ARTIFACTS:
        raise ManualPdfPreviewError("Publication provenance requires a bounded non-empty language inventory.")
    with _preview_root(project, lock_held=lock_held) as root_fd, _locked_git_index(project) as verify_git_index:
        verify_git_index()
        _require_generated_path(project, PUBLICATION_RECEIPT_PATH, label="Publication receipt")
        _require_generated_path(project, PUBLICATION_INTENT_PATH, label="Publication intent")
        intent = _read_publication_intent(root_fd)
        intent_entries = {
            (entry["language"], entry["kind"]): entry
            for entry in (intent["artifacts"] if intent else [])
        }
        if expected_intent_sha256:
            if not re.fullmatch(r"[0-9a-f]{64}", expected_intent_sha256):
                raise ManualPdfPreviewError("Publication provenance requires a valid intent SHA-256.")
            if intent is None or intent["_sha256"] != expected_intent_sha256:
                raise ManualPdfPreviewError("Manual PDF publication intent changed before provenance was recorded.")
        previous = _read_publication_receipt(root_fd)
        previous_entries = previous["artifacts"] if previous else []
        selected_languages: set[str] = set()
        finalized_intent_keys: set[tuple[str, str]] = set()
        artifacts: list[dict[str, Any]] = []
        destinations: set[str] = set()
        for language_status in languages:
            language = str(language_status.get("language") or "")
            if not LANGUAGE_RE.fullmatch(language) or language_status.get("published_current") is not True:
                raise ManualPdfPreviewError("Published manual PDF artifacts are not current enough to record provenance.")
            if language in selected_languages:
                raise ManualPdfPreviewError(f"Publication provenance contains duplicate language entries: {language}")
            selected_languages.add(language)
            for kind, source_key, destination_key in [
                ("pdf", "generated_pdf", "published_pdf"),
                ("cover", "generated_cover", "published_cover"),
            ]:
                source = _relative(language_status.get(source_key), label=f"generated {kind}")
                destination = _relative(language_status.get(destination_key), label=f"published {kind}")
                if destination.as_posix() in destinations:
                    raise ManualPdfPreviewError(
                        f"Publication provenance contains a duplicate destination: {destination.as_posix()}"
                    )
                _require_generated_path(project, destination, label="Published manual PDF destination")
                source_record = _existing_record(root_fd, source, label=f"generated {kind}")
                destination_record = _existing_record(root_fd, destination, label=f"published {kind}")
                expected = intent_entries.get((language, kind))
                if (
                    source_record is None
                    or destination_record is None
                    or source_record["sha256"] != destination_record["sha256"]
                    or source_record["size"] != destination_record["size"]
                ):
                    raise ManualPdfPreviewError(
                        f"Published {kind} no longer matches its generated artifact: {destination.as_posix()}"
                    )
                if expected_intent_sha256 and (
                    expected is None
                    or expected["source"] != source.as_posix()
                    or expected["destination"] != destination.as_posix()
                    or expected["sha256"] != source_record["sha256"]
                    or expected["size"] != source_record["size"]
                ):
                    raise ManualPdfPreviewError(
                        f"Published {kind} does not match the confirmed publication intent: {destination.as_posix()}"
                    )
                finalized_intent_keys.add((language, kind))
                destinations.add(destination.as_posix())
                artifacts.append({
                    "language": language,
                    "kind": kind,
                    "destination": destination.as_posix(),
                    **{
                        key: destination_record[key]
                        for key in OWNED_FILE_KEYS
                    },
                })
        if expected_intent_sha256:
            selected_intent_keys = {
                (entry["language"], entry["kind"])
                for entry in intent["artifacts"]
                if entry["language"] in selected_languages
            } if intent else set()
            if selected_intent_keys != finalized_intent_keys:
                raise ManualPdfPreviewError("Confirmed publication languages do not match the publication intent.")
        for entry in previous_entries:
            if entry["language"] in selected_languages or entry["destination"] in destinations:
                continue
            destination = _relative(entry["destination"], label="publication receipt destination")
            _require_generated_path(project, destination, label="Published manual PDF destination")
            current = _existing_record(root_fd, destination, label="published manual PDF destination")
            if current is not None and _same_owned_file(current, entry):
                artifacts.append({key: value for key, value in entry.items() if not key.startswith("_")})
        if len(artifacts) > MAX_ARTIFACTS:
            raise ManualPdfPreviewError("Merged publication provenance exceeds the artifact limit.")
        artifacts.sort(key=lambda item: (item["language"], item["kind"], item["destination"]))
        verify_git_index()
        _require_generated_path(project, PUBLICATION_RECEIPT_PATH, label="Publication receipt")
        content = _publication_receipt_bytes(artifacts)
        _atomic_write(root_fd, PUBLICATION_RECEIPT_PATH, content)
        intent_retained = False
        if intent is not None and expected_intent_sha256 and intent["_sha256"] == expected_intent_sha256:
            remaining_intent = [
                {key: value for key, value in entry.items() if not key.startswith("_")}
                for entry in intent["artifacts"]
                if entry["language"] not in selected_languages
            ]
            if remaining_intent:
                try:
                    _atomic_write(root_fd, PUBLICATION_INTENT_PATH, _publication_intent_bytes(remaining_intent))
                    intent_retained = True
                except OSError:
                    intent_retained = True
            else:
                intent_parent = _open_directory(root_fd, PUBLICATION_INTENT_PATH.parent)
                try:
                    try:
                        os.unlink(PUBLICATION_INTENT_PATH.name, dir_fd=intent_parent)
                        os.fsync(intent_parent)
                    except OSError:
                        intent_retained = True
                finally:
                    os.close(intent_parent)
        return {
            "path": PUBLICATION_RECEIPT_PATH.as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "artifacts": len(artifacts),
            "intent_retained": intent_retained,
        }


def prepare(
    project: Path | str,
    languages: list[dict[str, Any]],
    *,
    expected_config_sha256: str,
    lock_held: bool = False,
) -> dict[str, Any]:
    project = Path(project).expanduser().resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_config_sha256):
        raise ManualPdfPreviewError("A valid configuration SHA-256 is required for preview staging.")

    with _preview_root(project, lock_held=lock_held) as root_fd, _locked_git_index(project) as verify_git_index:
        verify_git_index()
        _require_generated_path(project, RECEIPT_PATH, label="Preview receipt")
        _require_generated_path(project, LOCK_PATH, label="Preview lock")
        if config_sha256(project) != expected_config_sha256:
            raise ManualPdfPreviewError("Site configuration changed while manual PDF preview preparation was running.")
        previous_receipt = _read_receipt(root_fd)
        previous_by_destination = {
            entry["destination"]: entry for entry in previous_receipt["artifacts"]
        } if previous_receipt else {}
        plans = _plan_records(root_fd, languages)
        temporaries: list[tuple[int, str]] = []
        backups: list[tuple[int, str, str]] = []
        installed: list[tuple[int, str, dict[str, Any]]] = []
        receipt_artifacts: list[dict[str, Any]] = []
        new_receipt_bytes: bytes | None = None
        receipt_committed = False
        try:
            requested = {plan["destination"].as_posix() for plan in plans}
            if previous_receipt and not set(previous_by_destination).issubset(requested):
                raise ManualPdfPreviewError(
                    "Configured preview destinations changed; clean the existing receipt-owned preview before preparing again."
                )
            for plan in plans:
                destination = plan["destination"]
                _require_generated_path(project, destination, label="Preview destination")
                current = _existing_record(root_fd, destination, label="preview destination")
                previous = previous_by_destination.get(destination.as_posix())
                if current is not None and previous is not None and not _same_owned_file(current, previous):
                    raise ManualPdfPreviewError(
                        f"Refusing to replace an unmanaged or changed preview destination: {destination.as_posix()}"
                    )
                plan["previous"] = current
                if previous is not None:
                    plan["skip_published"] = False
                    continue
                if current is not None and (
                    current["sha256"] == plan["source_record"]["sha256"]
                    and current["size"] == plan["source_record"]["size"]
                ):
                    plan["skip_published"] = True
                    continue
                if previous_receipt is not None:
                    raise ManualPdfPreviewError(
                        "Configured preview destinations changed; clean the existing receipt-owned preview before preparing again."
                    )
                replaceable = plan["replaceable_previous"]
                if current is not None and (
                    not isinstance(replaceable, dict)
                    or not _same_owned_file(current, replaceable)
                ):
                    raise ManualPdfPreviewError(
                        f"Refusing to replace an unmanaged or changed preview destination: {destination.as_posix()}"
                    )
                plan["skip_published"] = False

            staged_plans = [plan for plan in plans if not plan["skip_published"]]
            if not staged_plans:
                return {
                    "ok": True,
                    "publishes": False,
                    "receipt": "",
                    "receipt_sha256": "",
                    "state": "published-current",
                    "artifacts": [
                        {
                            "language": plan["language"],
                            "kind": plan["kind"],
                            "source": plan["source"].as_posix(),
                            "destination": plan["destination"].as_posix(),
                            "sha256": plan["previous"]["sha256"],
                            "size": plan["previous"]["size"],
                        }
                        for plan in plans
                    ],
                }

            verify_git_index()
            for plan in staged_plans:
                destination = plan["destination"]
                parent_fd = _open_directory(root_fd, destination.parent, create=True)
                temporary = f".{destination.name}.preview-{secrets.token_hex(8)}"
                descriptor: int | None = None
                try:
                    descriptor = os.open(
                        temporary,
                        os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                        0o644,
                        dir_fd=parent_fd,
                    )
                    source_fd = plan["source_fd"]
                    os.lseek(source_fd, 0, os.SEEK_SET)
                    while True:
                        chunk = os.read(source_fd, 1024 * 1024)
                        if not chunk:
                            break
                        remaining = memoryview(chunk)
                        while remaining:
                            written = os.write(descriptor, remaining)
                            if written <= 0:
                                raise OSError("short write")
                            remaining = remaining[written:]
                    os.fsync(descriptor)
                    plan["temporary_record"] = _record_descriptor(descriptor, destination)
                    if any(
                        plan["temporary_record"][key] != plan["source_record"][key]
                        for key in ["sha256", "size"]
                    ):
                        raise ManualPdfPreviewError(
                            f"Generated {plan['kind']} changed while it was copied: {plan['source'].as_posix()}"
                        )
                    source_after = _record_descriptor(source_fd, plan["source"])
                    current_source = _existing_record(
                        root_fd,
                        plan["source"],
                        label=f"generated {plan['kind']}",
                    )
                    if (
                        not _same_owned_file(source_after, plan["source_record"])
                        or current_source is None
                        or not _same_owned_file(current_source, plan["source_record"])
                    ):
                        raise ManualPdfPreviewError(
                            f"Generated {plan['kind']} changed while it was staged: {plan['source'].as_posix()}"
                        )
                except BaseException:
                    try:
                        try:
                            os.unlink(temporary, dir_fd=parent_fd)
                        except FileNotFoundError:
                            pass
                    finally:
                        os.close(parent_fd)
                    raise
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
                temporaries.append((parent_fd, temporary))
                plan["parent_fd"] = parent_fd
                plan["temporary"] = temporary

            for plan in staged_plans:
                destination = plan["destination"]
                parent_fd = plan["parent_fd"]
                current = _existing_record(root_fd, destination, label="preview destination")
                if current != plan["previous"]:
                    raise ManualPdfPreviewError(f"Preview destination changed during staging: {destination.as_posix()}")
                if current is not None:
                    backup = f".{destination.name}.preview-backup-{secrets.token_hex(8)}"
                    os.replace(destination.name, backup, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                    backups.append((parent_fd, backup, destination.name))
                    descriptor = _open_regular_name(
                        parent_fd,
                        backup,
                        destination,
                        label="previous preview backup",
                    )
                    try:
                        backup_record = _record_descriptor(descriptor, destination)
                    finally:
                        os.close(descriptor)
                    plan["backup_record"] = backup_record
                    if not _same_owned_file(backup_record, plan["previous"]):
                        raise ManualPdfPreviewError(
                            f"Preview destination changed while it was moved for staging: {destination.as_posix()}"
                        )
                try:
                    os.link(
                        plan["temporary"],
                        destination.name,
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                except FileExistsError as exc:
                    raise ManualPdfPreviewError(
                        f"A new file appeared at a preview destination during staging: {destination.as_posix()}"
                    ) from exc
                installed_record: dict[str, Any] = dict(plan["temporary_record"])
                installed.append((parent_fd, destination.name, installed_record))
                os.unlink(plan["temporary"], dir_fd=parent_fd)
                temporaries.remove((parent_fd, plan["temporary"]))
                descriptor = _open_regular_name(
                    parent_fd,
                    destination.name,
                    destination,
                    label="staged preview",
                )
                try:
                    installed_record = _record_descriptor(descriptor, destination)
                finally:
                    os.close(descriptor)
                if not _same_owned_file(installed_record, plan["temporary_record"]):
                    raise ManualPdfPreviewError(f"Staged preview differs from its generated source: {destination.as_posix()}")
                installed[-1] = (parent_fd, destination.name, installed_record)
                receipt_artifacts.append({
                    "language": plan["language"],
                    "kind": plan["kind"],
                    "source": plan["source"].as_posix(),
                    "destination": destination.as_posix(),
                    **{key: installed_record[key] for key in OWNED_FILE_KEYS},
                })

            if config_sha256(project) != expected_config_sha256:
                raise ManualPdfPreviewError("Site configuration changed while manual PDF preview files were staged.")
            verify_git_index()
            for plan in staged_plans:
                _require_generated_path(project, plan["destination"], label="Preview destination")
                current = _existing_record(root_fd, plan["destination"], label="preview destination")
                installed_record = next(
                    record
                    for parent_fd, destination_name, record in installed
                    if parent_fd == plan["parent_fd"] and destination_name == plan["destination"].name
                )
                if current is None or not _same_owned_file(current, installed_record):
                    raise ManualPdfPreviewError(
                        f"Preview destination changed before its receipt was committed: {plan['destination'].as_posix()}"
                    )
                os.fsync(plan["parent_fd"])
            _require_generated_path(project, RECEIPT_PATH, label="Preview receipt")
            _require_generated_path(project, LOCK_PATH, label="Preview lock")
            new_receipt_bytes = _receipt_bytes(expected_config_sha256, receipt_artifacts)
            _atomic_write(root_fd, RECEIPT_PATH, new_receipt_bytes)
            receipt_committed = True
            failed_backups: list[str] = []
            for item in list(backups):
                parent_fd, backup, destination_name = item
                plan = next(value for value in plans if value.get("parent_fd") == parent_fd and value["destination"].name == destination_name)
                try:
                    _unlink_verified_backup(parent_fd, backup, plan)
                except (OSError, ManualPdfPreviewError):
                    try:
                        failed_backups.append(_stash_backup(root_fd, parent_fd, backup, plan["destination"]))
                        backups.remove(item)
                    except RecoveryRequiredError as recovery:
                        failed_backups.extend(recovery.recovery_paths)
                        backups.remove(item)
                    except OSError:
                        failed_backups.append((plan["destination"].parent / backup).as_posix())
                else:
                    backups.remove(item)
            return {
                "ok": not failed_backups,
                "publishes": False,
                "receipt": RECEIPT_PATH.as_posix(),
                "receipt_sha256": hashlib.sha256(new_receipt_bytes).hexdigest(),
                "state": "staged" if not failed_backups else "recovery-required",
                "error": "" if not failed_backups else "Staging succeeded, but old receipt-owned backup files require manual recovery.",
                "recovery_backups": failed_backups,
                "artifacts": [
                    {
                        "language": entry["language"],
                        "kind": entry["kind"],
                        "source": entry["source"],
                        "destination": entry["destination"],
                        "sha256": entry["sha256"],
                        "size": entry["size"],
                    }
                    for entry in receipt_artifacts
                ],
            }
        except BaseException as exc:
            if new_receipt_bytes is not None and not receipt_committed:
                try:
                    current_receipt_bytes = _read_small_regular(
                        root_fd,
                        RECEIPT_PATH,
                        label="manual PDF preview receipt",
                        limit=MAX_RECEIPT_BYTES,
                    )
                    receipt_committed = hashlib.sha256(current_receipt_bytes).digest() == hashlib.sha256(new_receipt_bytes).digest()
                except (FileNotFoundError, ManualPdfPreviewError, OSError):
                    pass
            if receipt_committed:
                recovery_backups: list[str] = []
                for item in list(backups):
                    parent_fd, backup, destination_name = item
                    plan = next(
                        (
                            value
                            for value in plans
                            if value.get("parent_fd") == parent_fd and value["destination"].name == destination_name
                        ),
                        None,
                    )
                    try:
                        if plan is None:
                            raise ManualPdfPreviewError("Could not identify a committed preview backup.")
                        _unlink_verified_backup(parent_fd, backup, plan)
                        backups.remove(item)
                    except (OSError, ManualPdfPreviewError):
                        if plan is None:
                            recovery_backups.append(backup)
                            continue
                        try:
                            recovery_backups.append(_stash_backup(root_fd, parent_fd, backup, plan["destination"]))
                            backups.remove(item)
                        except RecoveryRequiredError as recovery:
                            recovery_backups.extend(recovery.recovery_paths)
                            backups.remove(item)
                        except OSError:
                            recovery_backups.append((plan["destination"].parent / backup).as_posix())
                detail = (
                    f" Recovery backups: {', '.join(recovery_backups)}."
                    if recovery_backups
                    else ""
                )
                raise ManualPdfPreviewError(
                    "Manual PDF preview receipt was committed; staged artifacts were retained after a post-commit failure."
                    + detail
                ) from exc

            rollback_recovery: list[str] = []
            for parent_fd, destination_name, installed_record in reversed(installed):
                removed = False
                try:
                    rollback_name = f".{destination_name}.preview-rollback-{secrets.token_hex(8)}"
                    os.replace(destination_name, rollback_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                except FileNotFoundError:
                    removed = True
                else:
                    matches = False
                    try:
                        descriptor = _open_regular_name(
                            parent_fd,
                            rollback_name,
                            Path(destination_name),
                            label="preview rollback file",
                        )
                        try:
                            rollback_record = _record_descriptor(descriptor, Path(destination_name))
                        finally:
                            os.close(descriptor)
                        matches = all(
                            rollback_record[key] == installed_record[key]
                            for key in OWNED_FILE_KEYS
                        )
                    except (OSError, ManualPdfPreviewError):
                        matches = False
                    if matches:
                        try:
                            metadata = os.stat(rollback_name, dir_fd=parent_fd, follow_symlinks=False)
                            if all(
                                value == rollback_record[key]
                                for key, value in {
                                    "size": metadata.st_size,
                                    **_identity(metadata),
                                }.items()
                            ):
                                os.unlink(rollback_name, dir_fd=parent_fd)
                                removed = True
                        except FileNotFoundError:
                            removed = True
                    if not removed:
                        try:
                            os.stat(destination_name, dir_fd=parent_fd, follow_symlinks=False)
                        except FileNotFoundError:
                            try:
                                _move_noreplace(
                                    rollback_name,
                                    destination_name,
                                    source_fd=parent_fd,
                                    destination_fd=parent_fd,
                                )
                            except OSError:
                                rollback_recovery.append(rollback_name)
                        else:
                            plan = next(
                                value
                                for value in plans
                                if value.get("parent_fd") == parent_fd and value["destination"].name == destination_name
                            )
                            try:
                                rollback_recovery.append(
                                    _stash_backup(root_fd, parent_fd, rollback_name, plan["destination"])
                                )
                            except RecoveryRequiredError as recovery:
                                rollback_recovery.extend(recovery.recovery_paths)
                            except OSError:
                                rollback_recovery.append((plan["destination"].parent / rollback_name).as_posix())
                matching = next((item for item in backups if item[0] == parent_fd and item[2] == destination_name), None)
                if matching is not None and removed:
                    try:
                        _move_noreplace(
                            matching[1],
                            destination_name,
                            source_fd=parent_fd,
                            destination_fd=parent_fd,
                        )
                        backups.remove(matching)
                    except OSError:
                        pass
            for item in reversed(list(backups)):
                parent_fd, backup, destination_name = item
                try:
                    _move_noreplace(
                        backup,
                        destination_name,
                        source_fd=parent_fd,
                        destination_fd=parent_fd,
                    )
                    backups.remove(item)
                except OSError:
                    pass
            recovery_backups: list[str] = list(rollback_recovery)
            for item in list(backups):
                parent_fd, backup, destination_name = item
                plan = next(
                    value
                    for value in plans
                    if value.get("parent_fd") == parent_fd and value["destination"].name == destination_name
                )
                try:
                    recovery_backups.append(_stash_backup(root_fd, parent_fd, backup, plan["destination"]))
                    backups.remove(item)
                except RecoveryRequiredError as recovery:
                    recovery_backups.extend(recovery.recovery_paths)
                    backups.remove(item)
                except OSError:
                    recovery_backups.append((plan["destination"].parent / backup).as_posix())
            if recovery_backups:
                raise ManualPdfPreviewError(
                    f"Preview staging failed; preserved previous files for recovery at: {', '.join(recovery_backups)}"
                ) from exc
            raise
        finally:
            for parent_fd, temporary in temporaries:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except OSError:
                    pass
            for plan in plans:
                parent_fd = plan.get("parent_fd")
                if isinstance(parent_fd, int):
                    try:
                        os.close(parent_fd)
                    except OSError:
                        pass
                    plan["parent_fd"] = None
            _close_plans(plans)


def clean(
    project: Path | str,
    *,
    dry_run: bool = True,
    confirm_clean: bool = False,
    expected_receipt_sha256: str = "",
    lock_held: bool = False,
) -> dict[str, Any]:
    project = Path(project).expanduser().resolve()
    if not dry_run and not confirm_clean:
        raise ManualPdfPreviewError(
            "Deleting receipt-owned manual PDF preview files requires confirm_clean=True after reviewing the dry-run."
        )
    receipt_path = project / RECEIPT_PATH
    if not receipt_path.exists() and not receipt_path.is_symlink():
        return {
            "ok": True,
            "publishes": False,
            "dry_run": dry_run,
            "confirmed": confirm_clean,
            "state": "absent",
            "receipt": RECEIPT_PATH.as_posix(),
            "artifacts": [],
        }
    with _preview_root(project, lock_held=lock_held) as root_fd, _locked_git_index(project) as verify_git_index:
        verify_git_index()
        _require_generated_path(project, RECEIPT_PATH, label="Preview receipt")
        receipt = _read_receipt(root_fd)
        if receipt is None:
            return {
                "ok": True,
                "publishes": False,
                "dry_run": dry_run,
                "confirmed": confirm_clean,
                "state": "absent",
                "receipt": RECEIPT_PATH.as_posix(),
                "artifacts": [],
            }
        receipt_sha256 = receipt["_sha256"]
        if not dry_run:
            if not re.fullmatch(r"[0-9a-f]{64}", expected_receipt_sha256):
                raise ManualPdfPreviewError(
                    "Real preview cleanup requires expected_receipt_sha256 from the reviewed dry-run."
                )
            if expected_receipt_sha256 != receipt_sha256:
                raise ManualPdfPreviewError(
                    "Manual PDF preview receipt changed after the reviewed cleanup dry-run."
                )
        checked: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        conflicts: list[dict[str, str]] = []
        for entry in receipt["artifacts"]:
            destination = _relative(entry["destination"], label="receipt destination")
            try:
                _require_generated_path(project, destination, label="Preview destination")
                current = _existing_record(root_fd, destination, label="preview destination")
            except ManualPdfPreviewError as exc:
                conflicts.append({"destination": destination.as_posix(), "reason": str(exc)})
                continue
            if current is not None and not _same_owned_file(current, entry):
                conflicts.append({
                    "destination": destination.as_posix(),
                    "reason": "The file no longer matches the receipt-owned identity and content.",
                })
            checked.append((entry, current))
        if conflicts:
            return {
                "ok": False,
                "publishes": False,
                "dry_run": dry_run,
                "confirmed": confirm_clean,
                "state": "conflict",
                "receipt": RECEIPT_PATH.as_posix(),
                "receipt_sha256": receipt_sha256,
                "conflicts": conflicts,
                "artifacts": [],
            }
        operations = [
            {"destination": entry["destination"], "state": "missing" if current is None else "owned"}
            for entry, current in checked
        ]
        if dry_run:
            return {
                "ok": True,
                "publishes": False,
                "dry_run": True,
                "confirmed": confirm_clean,
                "state": "planned",
                "receipt": RECEIPT_PATH.as_posix(),
                "receipt_sha256": receipt_sha256,
                "artifacts": operations,
            }

        quarantined: list[dict[str, Any]] = []
        cleanup_error = ""
        recovery_paths: list[str] = []
        try:
            verify_git_index()
            for entry, current in checked:
                if current is None:
                    continue
                destination = _relative(entry["destination"], label="receipt destination")
                latest = _existing_record(root_fd, destination, label="preview destination")
                if latest is None or not _same_owned_file(latest, entry):
                    raise ManualPdfPreviewError(f"Preview destination changed during cleanup: {destination.as_posix()}")
                parent_fd = _open_directory(root_fd, destination.parent)
                quarantine = f".{destination.name}.preview-clean-{secrets.token_hex(8)}"
                try:
                    os.replace(destination.name, quarantine, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                    item = {
                        "entry": entry,
                        "destination": destination,
                        "parent_fd": parent_fd,
                        "quarantine": quarantine,
                    }
                    quarantined.append(item)
                    descriptor = _open_regular_name(
                        parent_fd,
                        quarantine,
                        destination,
                        label="quarantined preview",
                    )
                    try:
                        quarantined_record = _record_descriptor(descriptor, destination)
                    finally:
                        os.close(descriptor)
                    if any(
                        quarantined_record[key] != entry[key]
                        for key in OWNED_FILE_KEYS
                    ):
                        raise ManualPdfPreviewError(f"Preview destination changed while it was quarantined: {destination.as_posix()}")
                    item["record"] = quarantined_record
                except BaseException:
                    if not any(item.get("parent_fd") == parent_fd for item in quarantined):
                        os.close(parent_fd)
                    raise

            for item in quarantined:
                destination = item["destination"]
                if _existing_record(root_fd, destination, label="preview destination") is not None:
                    raise ManualPdfPreviewError(f"A new file appeared at a preview destination during cleanup: {destination.as_posix()}")
                _require_generated_path(project, destination, label="Preview destination")
            current_receipt = _read_receipt(root_fd)
            if current_receipt is None or current_receipt["_sha256"] != receipt_sha256:
                raise ManualPdfPreviewError("Manual PDF preview receipt changed during cleanup.")
            verify_git_index()

            for item in quarantined:
                descriptor = _open_regular_name(
                    item["parent_fd"],
                    item["quarantine"],
                    item["destination"],
                    label="quarantined preview",
                )
                try:
                    current = _record_descriptor(descriptor, item["destination"])
                    metadata = os.stat(item["quarantine"], dir_fd=item["parent_fd"], follow_symlinks=False)
                finally:
                    os.close(descriptor)
                if any(
                    current[key] != item["record"][key]
                    for key in (*OWNED_FILE_KEYS, "ctime_ns")
                ):
                    raise ManualPdfPreviewError(
                        f"Quarantined preview file changed before deletion: {item['destination'].as_posix()}"
                    )
                if any(
                    value != current[key]
                    for key, value in {
                        "size": metadata.st_size,
                        **_identity(metadata),
                    }.items()
                ):
                    raise ManualPdfPreviewError(
                        f"Quarantined preview file was replaced before deletion: {item['destination'].as_posix()}"
                    )
                os.unlink(item["quarantine"], dir_fd=item["parent_fd"])
                item["deleted"] = True
                os.fsync(item["parent_fd"])

            receipt_parent = _open_directory(root_fd, RECEIPT_PATH.parent)
            try:
                verify_git_index()
                _require_generated_path(project, RECEIPT_PATH, label="Preview receipt")
                os.unlink(RECEIPT_PATH.name, dir_fd=receipt_parent)
                os.fsync(receipt_parent)
            finally:
                os.close(receipt_parent)
        except BaseException as exc:
            cleanup_error = str(exc)
            for item in reversed(quarantined):
                if item.get("deleted"):
                    continue
                parent_fd = item["parent_fd"]
                destination = item["destination"]
                try:
                    _move_noreplace(
                        item["quarantine"],
                        destination.name,
                        source_fd=parent_fd,
                        destination_fd=parent_fd,
                    )
                except OSError:
                    recovery_paths.append((destination.parent / item["quarantine"]).as_posix())
        finally:
            for item in quarantined:
                try:
                    os.close(item["parent_fd"])
                except OSError:
                    pass
        if cleanup_error:
            return {
                "ok": False,
                "publishes": False,
                "dry_run": False,
                "confirmed": confirm_clean,
                "state": "conflict",
                "receipt": RECEIPT_PATH.as_posix(),
                "receipt_sha256": receipt_sha256,
                "error": cleanup_error,
                "recovery_paths": recovery_paths,
                "artifacts": operations,
            }
        return {
            "ok": True,
            "publishes": False,
            "dry_run": False,
            "confirmed": confirm_clean,
            "state": "cleaned",
            "receipt": RECEIPT_PATH.as_posix(),
            "receipt_sha256": receipt_sha256,
            "artifacts": operations,
        }
