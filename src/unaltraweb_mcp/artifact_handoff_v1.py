#!/usr/bin/env python3
"""Read-only reference verifier for the artifact handoff v1 review candidate.

No provider, Git, network, importer or cleanup operations. Python 3.10+ stdlib.
The adjacent schema supplies structural rules; semantic checks bind those rules
to exact bytes in one explicitly selected, descriptor-anchored workspace.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import pathlib
import re
import stat
import sys
import unicodedata


SCHEMA_PATH = pathlib.Path(__file__).with_name("artifact-handoff-v1.schema.json")
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_ENTRIES = 10000
MAX_BUNDLES = 64
MAX_DEPTH = 8
HASH_RE = re.compile(r"[0-9a-f]{64}")


class HandoffError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise HandoffError(code, message)


def parse_json(raw: bytes) -> dict:
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in items:
            require(key not in result, "json", "duplicate JSON key")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise HandoffError("json", "non-finite JSON number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise HandoffError("json", "expected bounded UTF-8 JSON") from exc
    require(isinstance(value, dict), "schema", "document must be an object")
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(depth <= 32 and nodes <= 100000, "limit", "JSON exceeds depth or node limits")
        require(not isinstance(item, float) or math.isfinite(item), "json", "non-finite JSON number")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return value


def check_shape(value: object, rule: dict, definitions: dict, location: str = "document") -> None:
    """Evaluate only the vocabulary used by the checked-in schema, not arbitrary schemas."""
    if "$ref" in rule:
        return check_shape(value, definitions[rule["$ref"].removeprefix("#/$defs/")], definitions, location)
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if "type" in rule:
        require(type(value) is types[rule["type"]], "schema", f"{location}: invalid type")
    for key in ("const", "enum"):
        if key in rule:
            choices = [rule[key]] if key == "const" else rule[key]
            require(any(type(value) is type(choice) and value == choice for choice in choices),
                    "schema", f"{location}: unsupported value")
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        require(set(rule.get("required", [])) <= value.keys(), "schema", f"{location}: missing fields")
        if rule.get("additionalProperties") is False:
            require(value.keys() <= properties.keys(), "schema", f"{location}: unknown fields")
        for key, item in value.items():
            if key in properties:
                check_shape(item, properties[key], definitions, f"{location}.{key}")
    if isinstance(value, list):
        require(rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", MAX_ENTRIES),
                "schema", f"{location}: invalid array length")
        for index, item in enumerate(value):
            check_shape(item, rule["items"], definitions, f"{location}[{index}]")
    if isinstance(value, str):
        require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", 1024),
                "schema", f"{location}: invalid string length")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"], value) is not None,
                    "schema", f"{location}: invalid string")
    if type(value) is int:
        require(rule.get("minimum", value) <= value <= rule.get("maximum", value),
                "schema", f"{location}: integer outside limits")


def safe_path(value: str) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 1024, "path", "invalid relative path")
    require(unicodedata.normalize("NFC", value) == value, "path", "paths must use NFC Unicode")
    require(not any(unicodedata.category(char).startswith("C") or char in '\\:%$*?[]{}<>"|'
                    for char in value), "path", "path contains reserved characters")
    for part in value.split("/"):
        require(part not in ("", ".", "..") and part == part.strip() and not part.endswith("."),
                "path", "path must be normalized and relative")
        require(part.casefold() not in {".git", ".hg", ".svn"} and not part.startswith("~"),
                "path", "reserved path component")
        require(re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?", part) is None,
                "path", "reserved device name")
    require(len(value.split("/")) <= 64, "limit", "path depth exceeds 64")
    return value


def unique_paths(paths: list[str]) -> None:
    require(len(paths) == len(set(paths)), "path", "duplicate file path")
    aliases: dict[str, str] = {}
    files = set(paths)
    for path in paths:
        safe_path(path)
        parts = path.split("/")
        for length in range(1, len(parts) + 1):
            prefix = "/".join(parts[:length])
            key = prefix.casefold()
            require(key not in aliases or aliases[key] == prefix, "path", "case-aliased path")
            aliases[key] = prefix
            require(length == len(parts) or prefix not in files, "path", "file/directory collision")


def join(parent: str, child: str) -> str:
    return f"{parent}/{child}" if parent else child


def signature(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class Workspace:
    def __init__(self, path: str):
        if (not os.path.isabs(path) or path == "/" or path.startswith("//")
                or str(pathlib.PurePosixPath(path)) != path
                or any(unicodedata.category(char).startswith("C") for char in path)):
            raise HandoffError("workspace", "workspace must be an explicit normalized absolute directory", 2)
        if ".." in pathlib.PurePosixPath(path).parts:
            raise HandoffError("workspace", "workspace must not contain traversal", 2)
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise HandoffError("platform", "descriptor-relative no-follow access is required", 2)
        self.dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        self.fd = os.open("/", self.dir_flags)
        self.total_bytes = 0
        self.snapshots: dict[str, tuple] = {}
        self.directories: dict[str, tuple] = {}
        try:
            for part in pathlib.PurePosixPath(path).parts[1:]:
                next_fd = os.open(part, self.dir_flags, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = next_fd
        except OSError:
            os.close(self.fd)
            raise

    def close(self) -> None:
        os.close(self.fd)

    @contextlib.contextmanager
    def directory(self, relative: str):
        fd = os.dup(self.fd)
        try:
            for part in safe_path(relative).split("/") if relative else []:
                next_fd = os.open(part, self.dir_flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            yield fd
        finally:
            os.close(fd)

    def read(self, path: str, limit: int, *, collect: bool = False) -> tuple[str, int, bytes]:
        safe_path(path)
        require(path in self.snapshots or len(self.snapshots) < MAX_ENTRIES,
                "limit", "inspection exceeds file count limit")
        parent, _, name = path.rpartition("/")
        with self.directory(parent) as parent_fd:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=parent_fd)
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                        "file", "only regular, non-hardlinked files are supported")
                require(before.st_size <= limit, "limit", "file exceeds byte limit")
                digest = hashlib.sha256()
                chunks = []
                size = 0
                while True:
                    chunk = os.read(fd, min(1024 * 1024, limit - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    self.total_bytes += len(chunk)
                    require(size <= limit and self.total_bytes <= MAX_TOTAL_BYTES,
                            "limit", "inspection exceeds byte limits")
                    digest.update(chunk)
                    if collect:
                        chunks.append(chunk)
                after = os.fstat(fd)
                linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                require(signature(before) == signature(after) == signature(linked) and size == after.st_size,
                        "changed", "file changed during inspection")
                snapshot = signature(after)
                require(path not in self.snapshots or self.snapshots[path] == snapshot,
                        "changed", "file changed between inspections")
                self.snapshots[path] = snapshot
                return digest.hexdigest(), size, b"".join(chunks)
            finally:
                os.close(fd)

    def inventory(self, base: str) -> tuple[set[str], set[str]]:
        files: set[str] = set()
        directories: set[str] = set()
        count = 0

        def walk(fd: int, prefix: str, depth: int) -> None:
            nonlocal count
            require(depth <= 64, "limit", "directory depth exceeds 64")
            before = signature(os.fstat(fd))
            with os.scandir(fd) as entries:
                for entry in entries:
                    count += 1
                    require(count <= MAX_ENTRIES, "limit", "bundle tree exceeds entry limit")
                    relative = join(prefix, entry.name)
                    safe_path(relative)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        directories.add(relative)
                        child = os.open(entry.name, self.dir_flags, dir_fd=fd)
                        try:
                            require(signature(info) == signature(os.fstat(child)),
                                    "changed", "directory changed during inspection")
                            walk(child, relative, depth + 1)
                        finally:
                            os.close(child)
                    else:
                        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                                "file", "bundle contains a link or special file")
                        files.add(relative)
            require(signature(os.fstat(fd)) == before, "changed", "directory changed during inventory")
            self.directories[join(base, prefix) if prefix else base] = before

        with self.directory(base) as fd:
            walk(fd, "", 0)
        return files, directories

    def recheck(self) -> None:
        for path, expected in self.directories.items():
            with self.directory(path) as fd:
                require(signature(os.fstat(fd)) == expected,
                        "changed", "bundle directory changed before verification completed")
        for path, expected in self.snapshots.items():
            parent, _, name = path.rpartition("/")
            with self.directory(parent) as fd:
                actual = os.stat(name, dir_fd=fd, follow_symlinks=False)
                require(signature(actual) == expected, "changed", "file changed before verification completed")


class Verifier:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.definitions = parse_json(SCHEMA_PATH.read_bytes())["$defs"]
        self.bundle_count = 0

    def document(self, path: str, kind: str, expected: str | None = None) -> tuple[dict, str]:
        digest, _, raw = self.workspace.read(path, MAX_MANIFEST_BYTES, collect=True)
        require(expected is None or digest == expected, "hash", "manifest SHA-256 mismatch")
        doc = parse_json(raw)
        check_shape(doc, self.definitions[kind], self.definitions)
        actor = doc["producer" if kind == "bundle" else "integrator"]
        names = [runtime["name"] for runtime in actor["runtimes"]]
        require(len(names) == len(set(names)), "schema", "duplicate runtime name")
        return doc, digest

    def bundle(self, path: str, expected: str, depth: int = 0) -> tuple[dict, dict, set[str]]:
        safe_path(path)
        base, _, name = path.rpartition("/")
        require(name == "bundle.json", "path", "bundle manifest must be named bundle.json")
        self.bundle_count += 1
        require(depth <= MAX_DEPTH and self.bundle_count <= MAX_BUNDLES,
                "limit", "bundle graph exceeds depth or count limits")
        doc, _ = self.document(path, "bundle", expected)
        files = {item["id"]: item for item in doc["files"]}
        require(len(files) == len(doc["files"]), "schema", "duplicate file id")
        request = files.get(doc["request"], {})
        require(request.get("kind") == "input" and request.get("role") == "request",
                "provenance", "request must identify a retained input with role request")
        require(any(item["kind"] == "output" for item in files.values()),
                "schema", "bundle requires at least one output")
        paths = [item["path"] for item in files.values()]
        unique_paths(paths)
        for item in files.values():
            require(item["path"].startswith("payload/"), "path", "bundle files must be beneath payload/")
            if "variant_of" in item:
                original = files.get(item["variant_of"], {})
                require(item["ownership"] == "author" and original.get("kind") == item["kind"]
                        and original is not item and "variant_of" not in original,
                        "provenance", "variant must retain a same-kind original and be author-owned")
            digest, size, _ = self.workspace.read(join(base, item["path"]), MAX_FILE_BYTES)
            require((digest, size) == (item["sha256"], item["bytes"]),
                    "hash", f"file SHA-256 or size mismatch: {item['path']}")

        dependencies = {}
        flattened = {item["path"]: item for item in files.values()}
        inventory = {"bundle.json", *flattened}
        for dependency in doc["dependencies"]:
            identity = dependency["id"]
            require(identity not in dependencies, "schema", "duplicate dependency id")
            prefix = f"dependencies/{identity}"
            child, child_files, child_inventory = self.bundle(
                join(base, f"{prefix}/bundle.json"), dependency["sha256"], depth + 1)
            dependencies[identity] = {item["id"]: item for item in child["files"]}
            flattened.update({f"{prefix}/{key}": item for key, item in child_files.items()})
            inventory.update(f"{prefix}/{key}" for key in child_inventory)
        used = set()
        for item in files.values():
            if "from" not in item:
                continue
            upstream = item["from"]
            source = dependencies.get(upstream["dependency"], {}).get(upstream["file"], {})
            require(item["kind"] == "input" and source.get("kind") == "output",
                    "provenance", "upstream reference must bind an input to a direct dependency output")
            require(all(item[key] == source.get(key) for key in ("sha256", "bytes", "ownership")),
                    "provenance", "upstream input must retain exact bytes and ownership")
            used.add(upstream["dependency"])
        require(used == dependencies.keys(), "provenance", "every dependency must supply a declared input")
        unique_paths(sorted(inventory))
        if depth == 0:
            actual_files, actual_dirs = self.workspace.inventory(base)
            expected_dirs = {parent for item in inventory for parent in self.parents(item)}
            require(actual_files == inventory and actual_dirs == expected_dirs,
                    "inventory", "bundle tree differs from its complete declared inventory")
        return doc, flattened, inventory

    @staticmethod
    def parents(path: str) -> list[str]:
        parts = path.split("/")
        return ["/".join(parts[:length]) for length in range(1, len(parts))]

    def integration(self, path: str, expected: str | None) -> tuple[str, int]:
        doc, digest = self.document(path, "integration", expected)
        bundle_path = safe_path(doc["bundle"]["path"])
        base = bundle_path.rpartition("/")[0]
        require(bool(base) and not path.casefold().startswith(base.casefold() + "/"),
                "path", "integration record must be outside the sealed bundle")
        bundle, files, inventory = self.bundle(bundle_path, doc["bundle"]["sha256"])
        destinations = [safe_path(item["destination"]) for item in doc["mappings"]]
        unique_paths([path, *destinations, *(join(base, item) for item in inventory)])
        root_outputs = {item["path"] for item in bundle["files"] if item["kind"] == "output"}
        selected = set()
        for mapping in doc["mappings"]:
            source_path = safe_path(mapping["source"])
            source = files.get(source_path)
            require(source is not None, "provenance", "mapping source is not a declared bundle file")
            destination = mapping["destination"]
            require(not destination.casefold().startswith(base.casefold() + "/"),
                    "path", "mapped destinations must be outside the sealed bundle")
            current_hash, size, _ = self.workspace.read(destination, MAX_FILE_BYTES)
            require((current_hash, size) == (source["sha256"], source["bytes"]),
                    "hash", f"integrated file differs from its source: {destination}")
            selected.add(source_path)
        require(bool(selected & root_outputs), "provenance", "integration must expose a root bundle output")
        return digest, len(doc["mappings"])


def check(workspace_path: str, action: str, path: str, expected: str | None = None) -> dict:
    safe_path(path)
    if expected is not None and HASH_RE.fullmatch(expected) is None:
        raise HandoffError("argument", "expected SHA-256 must be 64 lowercase hex characters", 2)
    if action == "bundle" and expected is None:
        raise HandoffError("argument", "bundle verification requires the sender's SHA-256", 2)
    if action not in {"bundle", "integration"}:
        raise HandoffError("argument", "unknown verification action", 2)
    with contextlib.closing(Workspace(workspace_path)) as workspace:
        verifier = Verifier(workspace)
        if action == "bundle":
            verifier.bundle(path, expected)
            digest, mappings = expected, 0
        else:
            digest, mappings = verifier.integration(path, expected)
        workspace.recheck()
        return {"schema_version": 1, "ok": True, "action": action,
                "manifest_sha256": digest, "bundles": verifier.bundle_count,
                "verified_files": len(workspace.snapshots), "mappings": mappings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bundle", "integration"))
    parser.add_argument("--workspace", required=True, help="explicit absolute workspace; no environment fallback")
    parser.add_argument("--path", required=True, help="workspace-relative bundle.json or integration record")
    parser.add_argument("--sha256", help="expected manifest bytes hash; required for bundle")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    exit_code = 0
    try:
        result = check(args.workspace, args.action, args.path, args.sha256)
    except HandoffError as exc:
        result = {"schema_version": 1, "ok": False, "action": args.action,
                  "error": {"code": exc.code, "message": str(exc)}}
        exit_code = exc.exit_code
    except OSError as exc:
        result = {"schema_version": 1, "ok": False, "action": args.action,
                  "error": {"code": "inspection", "message": f"cannot safely inspect files (errno {exc.errno})"}}
        exit_code = 2
    if args.json:
        print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    elif result["ok"]:
        print(f"VERIFIED\t{result['manifest_sha256']}\t{result['bundles']} bundles\t{result['mappings']} mappings")
    else:
        print(f"FAILED\t{result['error']['code']}\t{result['error']['message']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
