"""Offline, runtime-specific generated Bundler state. Author locks are never repaired."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import uuid

from .processes import run_process


GEMFILE = b'source "https://rubygems.org"\n\ngroup :jekyll_plugins do\n  gem "unaltraweb", path: ENV.fetch("UNALTRAWEB_BUNDLE_CORE")\nend\n'
PROBE = '''require "json"; require "rubygems"; require "bundler"
puts JSON.generate({ruby: RUBY_DESCRIPTION, platform: RUBY_PLATFORM,
  rubygems: Gem::VERSION, bundler: Bundler::VERSION,
  gems: Gem::Specification.map { |s| [s.name, s.version.to_s, s.platform.to_s, s.full_gem_path] }.sort})'''


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextmanager
def directory(path: Path, *, create: bool = False):
    """Open every component without following symlinks, including cache ancestors."""
    path = path.absolute()
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part in {".", ".."}:
                raise RuntimeError("Unsafe Bundler directory")
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_file(parent: int, name: str) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1024 * 1024:
            raise RuntimeError(f"Unsafe Bundler file: {name}")
        data = os.read(fd, 1024 * 1024 + 1)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if len(data) != info.st_size or any(getattr(after, name) != getattr(info, name) for name in fields):
            raise RuntimeError(f"Bundler file changed while reading: {name}")
        return data
    finally:
        os.close(fd)


def source_bytes(path: Path) -> bytes:
    with directory(path.parent) as fd:
        return read_file(fd, path.name)


def write_new(fd: int, name: str, data: bytes) -> None:
    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
    with os.fdopen(output, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def environment(project: Path, core: Path, gemfile: Path) -> dict[str, str]:
    return {**os.environ, "UNALTRAWEB_BUNDLE_CORE": str(core), "BUNDLE_GEMFILE": str(gemfile),
            "BUNDLE_APP_CONFIG": os.environ.get("BUNDLE_APP_CONFIG", str(project / ".bundle"))}


def checked(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    result = run_process(command, cwd=cwd, env=env, timeout_seconds=180)
    if result.returncode or result.stdout_truncated or result.stderr_truncated:
        raise RuntimeError(f"Offline Bundler preparation failed: {result.stdout}\n{result.stderr}")
    return result.stdout


def runtime_identity(project: Path, core: Path) -> dict:
    probe_env = dict(os.environ)
    probe_env.pop("BUNDLE_GEMFILE", None)
    ruby = json.loads(checked(["ruby", "-e", PROBE], cwd=core, env=probe_env))
    core_inputs = ["unaltraweb.gemspec", "lib/unaltraweb/version.rb", "src/unaltraweb_mcp/component-contract.json"]
    config = Path(os.environ.get("BUNDLE_APP_CONFIG", str(project / ".bundle"))) / "config"
    if not config.is_absolute():
        config = project / config
    return {
        "schema_version": 1, "preparation": "offline-lock-invocation-copy-v1", "ruby": ruby, "core": str(core),
        "core_inputs": {name: digest(source_bytes(core / name)) for name in core_inputs},
        "gemfile": digest(GEMFILE),
        "bundle_env": {key: digest(value.encode()) for key, value in sorted(os.environ.items()) if key.startswith("BUNDLE_") and key != "BUNDLE_GEMFILE"},
        "bundle_config": digest(source_bytes(config)) if os.path.lexists(config) else "",
    }


def prepare(project: Path, core: Path) -> Path:
    """Create once per effective Ruby/core/config identity; validate every reuse."""
    project, core = project.absolute(), core.absolute()
    identity = runtime_identity(project, core)
    key = digest(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    root = project / "tmp/unaltraweb-bundle"
    with directory(root, create=True) as parent:
        lock = os.open(".prepare.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        try:
            info = os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError("Unsafe Bundler coordination lock")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not os.path.lexists(root / key):
                stage_name = f".prepare-{uuid.uuid4().hex}"
                os.mkdir(stage_name, dir_fd=parent)
                stage = root / stage_name
                with directory(stage) as fd:
                    write_new(fd, "Gemfile", GEMFILE)
                    env = environment(project, core, stage / "Gemfile")
                    checked(["bundle", "lock", "--local"], cwd=project, env=env)
                    checked(["bundle", "check"], cwd=project, env=env)
                    receipt = {"schema_version": 1, "identity": identity, "files": {
                        name: digest(read_file(fd, name)) for name in ("Gemfile", "Gemfile.lock")
                    }}
                    write_new(fd, "receipt.json", (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode())
                # Exclusive creation cannot replace even a raced empty directory.
                # Interrupted preparations remain inspectable and fail closed.
                os.mkdir(key, dir_fd=parent)
                with directory(stage) as source, directory(root / key) as target:
                    for name in ("Gemfile", "Gemfile.lock", "receipt.json"):
                        write_new(target, name, read_file(source, name))
            with directory(root / key) as fd:
                receipt = json.loads(read_file(fd, "receipt.json"))
                expected = {name: digest(read_file(fd, name)) for name in ("Gemfile", "Gemfile.lock")}
                if receipt != {"schema_version": 1, "identity": identity, "files": expected} or read_file(fd, "Gemfile") != GEMFILE:
                    raise RuntimeError("Generated Bundler cache was modified; preserve it and review the changes before reuse")
            return root / key / "Gemfile"
        finally:
            os.close(lock)


def invocation_copy(cached: Path) -> Path:
    # Both historical recipes and Bundler 4's default-gem checksum completion can
    # write locks. Only invocation-owned copies are mutable, never cached/author
    # locks. No checksum validation setting is disabled to allow those writes.
    invocation = cached.parent.parent / f"run-{uuid.uuid4().hex}"
    with directory(cached.parent) as cached_fd:
        payloads = {name: read_file(cached_fd, name) for name in ("Gemfile", "Gemfile.lock")}
        receipt = json.loads(read_file(cached_fd, "receipt.json"))
        if receipt.get("files") != {name: digest(data) for name, data in payloads.items()} or payloads["Gemfile"] != GEMFILE:
            raise RuntimeError("Generated Bundler cache changed before use")
    with directory(invocation, create=True) as fd:
        for name, data in payloads.items():
            write_new(fd, name, data)
    return invocation / "Gemfile"


def legacy_make_args(project: Path, core: Path) -> list[str]:
    """Adapt unchanged package scaffolds only; custom Makefiles retain control."""
    try:
        text = source_bytes(project / "Makefile")
        if b"LOCAL_GEMFILE := tmp/Gemfile.local\n" not in text:
            return []
        baseline = json.loads(source_bytes(project / ".unaltraweb/scaffold.json"))
        if baseline.get("files", {}).get("Makefile") != digest(text):
            return []
    except (FileNotFoundError, ValueError):
        return []
    gemfile = invocation_copy(prepare(project, core))
    return [f"LOCAL_GEMFILE={gemfile.relative_to(project).as_posix()}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--gemfile", default="", help="Explicit author-managed Gemfile; its existing lock is frozen.")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        project, core = args.project.absolute(), args.core.absolute()
        if args.gemfile:
            gemfile = project / args.gemfile
            gemfile.relative_to(project)
            source_bytes(gemfile)
            source_bytes(Path(str(gemfile) + ".lock"))
        else:
            gemfile = invocation_copy(prepare(project, core))
        env = environment(project, core, gemfile)
        if args.gemfile:
            env["BUNDLE_FROZEN"] = "true"
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            print(gemfile)
            return 0
        os.execvpe(command[0], command, env)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
