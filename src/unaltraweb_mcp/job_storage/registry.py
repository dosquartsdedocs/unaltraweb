"""Private, descriptor-anchored W1 ledger outside disposable work volumes.

The kernel lock serializes cooperating managers. Root identity and filesystem
ownership are checked independently of JSON; copying a ledger does not adopt
its volumes. No registry operation performs volume or consumer-file cleanup.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import secrets
import stat
import time
from typing import Any
import uuid

from .contract import ID_RE, MAX_DOCUMENT, StorageError, canonical, parse, relative_path, require

MAX_LEDGER_FILES = 8192
MAX_LEDGER_BYTES = 64 * 1024 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def identity(info: os.stat_result) -> dict[str, int]:
    return {"device": info.st_dev, "inode": info.st_ino}


def private_file(info: os.stat_result) -> None:
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
            and not stat.S_IMODE(info.st_mode) & 0o077,
            "Registry file is not private, regular and singly linked", "storage-registry-unsafe")


def open_root(path: Path, create: bool = False) -> int:
    raw = os.fspath(path)
    require(path.is_absolute() and path != Path("/") and path.as_posix() == raw
            and ".." not in path.parts and not any(ord(char) < 32 for char in raw),
            "Registry requires an explicit normalized absolute path", "storage-registry-unsafe")
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            following = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        metadata = os.fstat(descriptor)
        require(metadata.st_uid == os.getuid() and not stat.S_IMODE(metadata.st_mode) & 0o077,
                "Registry directory must be private and owned by this operating-system user", "storage-registry-unsafe")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class Registry:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser()
        self.fd: int | None = None
        self.writable = False
        self.record: dict[str, Any] | None = None

    @contextmanager
    def locked(self, *, write: bool = False, create: bool = False, daemon_id: str | None = None, wait_seconds: float = 0):
        require(self.fd is None, "Nested registry transactions are not supported", "storage-registry-busy")
        require(not create or write, "Read-only registry observation cannot initialize state")
        require(type(wait_seconds) in {int, float} and 0 <= wait_seconds <= 5, "Registry lock wait exceeds its bound")
        root_fd = open_root(self.root, create=create)
        lock_fd = None
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
            if create:
                flags |= os.O_CREAT
            lock_fd = os.open(".registry.lock", flags, 0o600, dir_fd=root_fd)
            private_file(os.fstat(lock_fd))
            deadline = time.monotonic() + wait_seconds
            while True:
                try:
                    fcntl.flock(lock_fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise StorageError("storage-registry-busy", "Another manager transaction holds this registry") from exc
                    time.sleep(.01)
            self.fd, self.writable = root_fd, write
            record = self.read("registry.json", optional=True)
            if record is None:
                require(create and daemon_id is not None, "Registry is not initialized", "storage-binding-mismatch")
                record = {"kind": "unaltraweb.job-storage-registry", "schema_version": 1,
                          "id": uuid.uuid4().hex, "revision": 1, "owner_uid": os.getuid(),
                          "root_identity": identity(os.fstat(root_fd)), "daemon_id": daemon_id,
                          "jobs": [], "bindings": {}, "capacity_probe": None}
                self.write("registry.json", record, create_only=True)
            require(record.get("kind") == "unaltraweb.job-storage-registry" and type(record.get("schema_version")) is int
                    and record["schema_version"] == 1 and record.get("owner_uid") == os.getuid()
                    and record.get("root_identity") == identity(os.fstat(root_fd)),
                    "Registry identity changed; ownership transfer must be explicit", "storage-registry-unsafe")
            require(isinstance(record.get("id"), str) and ID_RE.fullmatch(record["id"]) is not None
                    and type(record.get("revision")) is int and record["revision"] >= 1
                    and isinstance(record.get("jobs"), list) and len(record["jobs"]) <= 4096
                    and all(isinstance(item, str) and ID_RE.fullmatch(item) for item in record["jobs"])
                    and len(set(record["jobs"])) == len(record["jobs"])
                    and isinstance(record.get("bindings"), dict),
                    "Registry index has invalid identities or bounds", "storage-registry-unsafe")
            if daemon_id is not None:
                require(record.get("daemon_id") == daemon_id, "Registry belongs to another Docker daemon", "storage-binding-mismatch")
            self.record = record
            self.revalidate_root()
            yield self
            self.revalidate_root()
        finally:
            self.fd, self.record, self.writable = None, None, False
            if lock_fd is not None:
                os.close(lock_fd)
            os.close(root_fd)

    def revalidate_root(self) -> None:
        require(self.fd is not None, "Registry access requires a transaction")
        observed = open_root(self.root)
        try:
            require(identity(os.fstat(observed)) == identity(os.fstat(self.fd)),
                    "Registry directory was replaced", "storage-registry-unsafe")
        finally:
            os.close(observed)

    @contextmanager
    def parent(self, relative: str, *, create: bool = False):
        require(self.fd is not None, "Registry access requires a transaction")
        require(not create or self.writable, "Read-only registry cannot create directories")
        parts = relative_path(relative).split("/")
        current = os.dup(self.fd)
        try:
            for component in parts[:-1]:
                if create:
                    try:
                        os.mkdir(component, 0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                following = os.open(component, DIRECTORY_FLAGS, dir_fd=current)
                metadata = os.fstat(following)
                if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
                    os.close(following)
                    raise StorageError("storage-registry-unsafe", "Registry child directory is not private")
                os.close(current)
                current = following
            yield current, parts[-1]
        finally:
            os.close(current)

    def read_bytes(self, relative: str, *, optional: bool = False) -> bytes | None:
        try:
            with self.parent(relative) as (parent, name):
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    before = os.fstat(descriptor)
                    private_file(before)
                    require(before.st_size <= MAX_DOCUMENT, "Registry member exceeds its bound", "storage-registry-unsafe")
                    with os.fdopen(descriptor, "rb", closefd=False) as stream:
                        raw = stream.read(MAX_DOCUMENT + 1)
                    signature = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                                                value.st_size, value.st_mtime_ns, value.st_ctime_ns)
                    require(len(raw) <= MAX_DOCUMENT and signature(before) == signature(os.fstat(descriptor))
                            == signature(os.stat(name, dir_fd=parent, follow_symlinks=False)),
                            "Registry member changed during observation", "storage-registry-unsafe")
                    return raw
                finally:
                    os.close(descriptor)
        except FileNotFoundError:
            if optional:
                return None
            raise StorageError("storage-binding-mismatch", "Unknown registry member")
        except OSError as exc:
            raise StorageError("storage-registry-unsafe", "Registry member cannot be read without following links") from exc

    def read(self, relative: str, *, optional: bool = False) -> dict[str, Any] | None:
        raw = self.read_bytes(relative, optional=optional)
        return parse(raw) if raw is not None else None

    def usage(self) -> tuple[int, int]:
        require(self.fd is not None, "Registry access requires a transaction")
        count, size = 0, 0

        def walk(fd: int, depth: int):
            nonlocal count, size
            require(depth <= 4, "Registry directory depth exceeds its bound", "storage-registry-unsafe")
            for name in os.listdir(fd):
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                count += 1
                require(count <= MAX_LEDGER_FILES, "Registry file budget is exhausted", "storage-budget-exceeded")
                if stat.S_ISDIR(info.st_mode):
                    require(info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077,
                            "Registry directory is not private", "storage-registry-unsafe")
                    child = os.open(name, DIRECTORY_FLAGS, dir_fd=fd)
                    try:
                        walk(child, depth + 1)
                    finally:
                        os.close(child)
                else:
                    private_file(info)
                    size += info.st_size
                    require(size <= MAX_LEDGER_BYTES, "Registry byte budget is exhausted", "storage-budget-exceeded")

        walk(self.fd, 0)
        return count, size

    def write_bytes(self, relative: str, raw: bytes, *, create_only: bool = False) -> None:
        require(self.writable and self.fd is not None, "Read-only registry cannot mutate state")
        require(isinstance(raw, bytes) and len(raw) <= MAX_DOCUMENT, "Registry member exceeds its bound")
        self.revalidate_root()
        old = self.read_bytes(relative, optional=True)
        require(not create_only or old is None, "Registry member already exists", "storage-revision-conflict")
        count, size = self.usage()
        require(count + 2 <= MAX_LEDGER_FILES and size + len(raw) <= MAX_LEDGER_BYTES,
                "Registry capacity is exhausted; retain and archive its metadata explicitly", "storage-budget-exceeded")
        with self.parent(relative, create=True) as (parent, name):
            temporary = ".pending-" + secrets.token_hex(16)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                require(self.read_bytes(relative, optional=True) == old, "Registry changed before commit", "storage-revision-conflict")
                os.rename(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            except BaseException:
                # A partial transaction stays visible as bounded recovery data.
                raise

    def write(self, relative: str, value: dict[str, Any], *, create_only: bool = False) -> None:
        self.write_bytes(relative, canonical(value), create_only=create_only)

    def save_registry(self) -> None:
        require(self.record is not None and self.writable, "Registry mutation requires its write lock")
        self.record["revision"] += 1
        self.write("registry.json", self.record)

    def acquire_guard(self, lease_id: str) -> int:
        require(self.writable and ID_RE.fullmatch(lease_id) is not None, "Lease guard requires an admitted writer transaction")
        count, _ = self.usage()
        require(count + 2 <= MAX_LEDGER_FILES, "Registry lease budget is exhausted", "storage-budget-exceeded")
        with self.parent(f"leases/{lease_id}.lock", create=True) as (parent, name):
            descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            private_file(os.fstat(descriptor))
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def guard_state(self, lease_id: str) -> str:
        require(ID_RE.fullmatch(lease_id) is not None, "Invalid lease guard identity")
        try:
            with self.parent(f"leases/{lease_id}.lock") as (parent, name):
                descriptor = os.open(name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                private_file(os.fstat(descriptor))
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return "unlocked"
                except BlockingIOError:
                    return "held"
            finally:
                os.close(descriptor)
        except OSError:
            return "unknown"
