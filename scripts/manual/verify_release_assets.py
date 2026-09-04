#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
import unicodedata
import zlib
from pathlib import Path, PurePosixPath
from typing import Any


SELECTOR_RE = re.compile(r"v[0-9]{4}\.(?:0[1-9]|1[0-2])(?:\.[1-9][0-9]*)?\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_RE = re.compile(r"ghcr\.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:[0-9a-f]{64}\Z")
SITE_IMAGE_RE = re.compile(r"ghcr\.io/dosquartsdedocs/unaltraweb-mcp@sha256:[0-9a-f]{64}\Z")
FINGERPRINT_SCHEMA = "unaltraweb-tree-v1"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_TAR_MEMBERS = 200_000
MAX_SITE_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TAR_CONTENT_BYTES = 2 * 1024 * 1024 * 1024
MAX_TAR_STREAM_BYTES = 4 * 1024 * 1024 * 1024


class VerificationError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def strict_json(content: bytes, *, label: str) -> Any:
    if len(content) > MAX_JSON_BYTES:
        raise VerificationError(f"{label} exceeds the JSON size limit.")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"{label} contains duplicate key {key!r}.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise VerificationError(f"{label} contains non-finite number {value}.")

    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label} is not strict UTF-8 JSON: {exc}") from exc
    if canonical_json(value) != content:
        raise VerificationError(f"{label} is not canonical JSON.")
    return value


def name_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def safe_relative(value: Any, *, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or value != value.strip() or value.startswith("/") or "\\" in value:
        raise VerificationError(f"{label} is not a safe relative path: {value!r}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise VerificationError(f"{label} contains control characters.")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part != part.strip() for part in parts):
        raise VerificationError(f"{label} contains an empty or traversal segment: {value!r}")
    return PurePosixPath(*parts)


def file_record(path: Path, *, label: str) -> dict[str, Any]:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise VerificationError(f"{label} is not a regular file.")
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
            raise VerificationError(f"{label} changed while it was read.")
        return {"sha256": digest.hexdigest(), "size": size}
    except OSError as exc:
        raise VerificationError(f"Cannot read {label}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def regular_content(path: Path, *, label: str, max_bytes: int = MAX_JSON_BYTES) -> tuple[bytes, dict[str, Any]]:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise VerificationError(f"{label} is not a bounded regular file.")
        content = bytearray()
        digest = hashlib.sha256()
        while len(content) <= max_bytes:
            chunk = os.read(descriptor, min(65536, max_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
            digest.update(chunk)
        after = os.fstat(descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity_before != identity_after or len(content) != after.st_size:
            raise VerificationError(f"{label} changed while it was read.")
        if len(content) > max_bytes:
            raise VerificationError(f"{label} exceeds the size limit.")
        return bytes(content), {"sha256": digest.hexdigest(), "size": len(content)}
    except OSError as exc:
        raise VerificationError(f"Cannot read {label}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def regular_asset_inventory(assets: Path) -> dict[str, Path]:
    try:
        metadata = assets.lstat()
    except OSError as exc:
        raise VerificationError(f"Release asset directory is unavailable: {exc}") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise VerificationError("Release asset root must be a real directory.")
    inventory: dict[str, Path] = {}
    keys: set[str] = set()
    for entry in os.scandir(assets):
        entry_metadata = entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(entry_metadata.st_mode):
            raise VerificationError(f"Release asset must be a regular file: {entry.name}")
        safe_relative(entry.name, label="release asset name")
        key = name_key(entry.name)
        if key in keys:
            raise VerificationError(f"Release assets contain colliding names: {entry.name}")
        keys.add(key)
        inventory[entry.name] = Path(entry.path)
    return inventory


def _compare_regular_files(reference: Path, received: Path, *, label: str) -> None:
    descriptors: list[int] = []
    try:
        for path in (reference, received):
            descriptors.append(
                os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
            )
        reference_before, received_before = (os.fstat(descriptor) for descriptor in descriptors)
        if not stat.S_ISREG(reference_before.st_mode) or not stat.S_ISREG(received_before.st_mode):
            raise VerificationError(f"{label} must compare two regular files.")
        if (reference_before.st_dev, reference_before.st_ino) == (received_before.st_dev, received_before.st_ino):
            raise VerificationError(f"{label} must compare independently transferred files.")

        identical = reference_before.st_size == received_before.st_size
        while identical:
            reference_chunk = os.read(descriptors[0], 1024 * 1024)
            received_chunk = os.read(descriptors[1], 1024 * 1024)
            if reference_chunk != received_chunk:
                identical = False
                break
            if not reference_chunk:
                break

        reference_after, received_after = (os.fstat(descriptor) for descriptor in descriptors)
        for name, before, after in [
            ("reference", reference_before, reference_after),
            ("received", received_before, received_after),
        ]:
            before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            if before_identity != after_identity:
                raise VerificationError(f"{label} {name} changed while it was compared.")
        if not identical:
            raise VerificationError(f"{label} differs from the locally verified release asset.")
    except OSError as exc:
        raise VerificationError(f"Cannot compare {label}: {exc}") from exc
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def compare_asset_directories(reference: Path, received: Path) -> None:
    try:
        reference_metadata = reference.lstat()
        received_metadata = received.lstat()
    except OSError as exc:
        raise VerificationError(f"Cannot inspect release asset roots for exact comparison: {exc}") from exc
    if (reference_metadata.st_dev, reference_metadata.st_ino) == (received_metadata.st_dev, received_metadata.st_ino):
        raise VerificationError("Reference and received release asset roots must be independent directories.")

    reference_assets = regular_asset_inventory(reference)
    received_assets = regular_asset_inventory(received)
    if set(reference_assets) != set(received_assets):
        raise VerificationError("Received release assets do not exactly match the local asset names.")
    for name in sorted(reference_assets):
        _compare_regular_files(
            reference_assets[name],
            received_assets[name],
            label=f"received release asset {name}",
        )


def _validate_single_gzip_member(
    descriptor: int,
    *,
    logical_tar_end: int | None = None,
    expected_metadata: os.stat_result | None = None,
) -> os.stat_result:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise VerificationError("Site archive is not a regular file.")
    if before.st_size > MAX_SITE_ARCHIVE_BYTES:
        raise VerificationError("Site archive exceeds the compressed size limit.")
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    if expected_metadata is not None:
        expected_identity = (
            expected_metadata.st_dev,
            expected_metadata.st_ino,
            expected_metadata.st_size,
            expected_metadata.st_mtime_ns,
            expected_metadata.st_ctime_ns,
        )
        if before_identity != expected_identity:
            raise VerificationError("Site archive changed before its tar padding was validated.")
    if logical_tar_end is not None and (logical_tar_end < 0 or logical_tar_end % tarfile.BLOCKSIZE):
        raise VerificationError("Site archive logical tar end is not block aligned.")

    os.lseek(descriptor, 0, os.SEEK_SET)
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    decoded_size = 0
    try:
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            if decoder.eof:
                raise VerificationError("Site archive has trailing bytes or a concatenated gzip member.")
            pending = chunk
            while pending:
                output = decoder.decompress(
                    pending,
                    min(1024 * 1024, MAX_TAR_STREAM_BYTES - decoded_size + 1),
                )
                output_start = decoded_size
                decoded_size += len(output)
                if decoded_size > MAX_TAR_STREAM_BYTES:
                    raise VerificationError("Site archive exceeds the decompressed stream size limit.")
                if logical_tar_end is not None and decoded_size > logical_tar_end:
                    tail_start = max(0, logical_tar_end - output_start)
                    if output[tail_start:].strip(b"\0"):
                        raise VerificationError("Site archive contains nonzero data after its logical tar end.")
                if decoder.eof:
                    if decoder.unused_data:
                        raise VerificationError("Site archive has trailing bytes or a concatenated gzip member.")
                    break
                pending = decoder.unconsumed_tail
        if not decoder.eof:
            raise VerificationError("Site archive contains an incomplete gzip stream.")
    except zlib.error as exc:
        raise VerificationError(f"Site archive is not a valid gzip stream: {exc}") from exc

    if logical_tar_end is not None:
        if decoded_size % tarfile.BLOCKSIZE:
            raise VerificationError("Site archive decompressed stream is not block aligned.")
        if decoded_size - logical_tar_end < 2 * tarfile.BLOCKSIZE:
            raise VerificationError("Site archive omits the canonical two-block tar end marker.")

    after = os.fstat(descriptor)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if before_identity != after_identity:
        raise VerificationError("Site archive changed while its gzip stream was validated.")
    os.lseek(descriptor, 0, os.SEEK_SET)
    return before


def tar_tree_record(archive_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    directories: dict[str, dict[str, Any]] = {}
    files: dict[str, dict[str, Any]] = {}
    keys: set[str] = set()
    root_members = 0
    member_count = 0
    content_size = 0
    logical_tar_end: int | None = None
    descriptor: int | None = None
    try:
        descriptor = os.open(
            archive_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        archive_metadata = _validate_single_gzip_member(descriptor)
        with os.fdopen(os.dup(descriptor), "rb") as archive_file:
            with tarfile.open(fileobj=archive_file, mode="r:gz") as archive:
                for member in archive:
                    member_count += 1
                    if member_count > MAX_TAR_MEMBERS:
                        raise VerificationError("Site archive contains too many members.")
                    if member.uid != 0 or member.gid != 0 or member.mtime != 0:
                        raise VerificationError("Site archive contains non-canonical owner or timestamp metadata.")
                    raw = member.name
                    while raw.startswith("./"):
                        raw = raw[2:]
                    raw = raw.rstrip("/")
                    if raw in {"", "."}:
                        root_members += 1
                        if not member.isdir() or member.mode & 0o7777 != 0o755:
                            raise VerificationError("Site archive root member is not one canonical mode-0755 directory.")
                        continue
                    relative = safe_relative(raw, label="site archive member").as_posix()
                    key = name_key(relative)
                    if key in keys:
                        raise VerificationError(f"Site archive contains duplicate or colliding member: {relative}")
                    keys.add(key)
                    if member.isdir():
                        if member.mode & 0o7777 != 0o755:
                            raise VerificationError(f"Site archive directory does not use canonical mode 0755: {relative}")
                        directories[relative] = {"path": relative, "mode": member.mode & 0o7777}
                        continue
                    if not member.isfile():
                        raise VerificationError(f"Site archive contains a link or special member: {relative}")
                    if member.mode & 0o7777 != 0o644:
                        raise VerificationError(f"Site archive file does not use canonical mode 0644: {relative}")
                    if member.size > MAX_TAR_CONTENT_BYTES - content_size:
                        raise VerificationError("Site archive exceeds the file content size limit.")
                    content_size += member.size
                    source = archive.extractfile(member)
                    if source is None:
                        raise VerificationError(f"Cannot read site archive member: {relative}")
                    digest = hashlib.sha256()
                    size = 0
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                    if size != member.size:
                        raise VerificationError(f"Site archive member has an inconsistent size: {relative}")
                    files[relative] = {
                        "path": relative,
                        "sha256": digest.hexdigest(),
                        "size": size,
                        "mode": member.mode & 0o7777,
                    }
                logical_tar_end = archive.offset
        if logical_tar_end is None:
            raise VerificationError("Site archive has no logical tar end.")
        _validate_single_gzip_member(
            descriptor,
            logical_tar_end=logical_tar_end,
            expected_metadata=archive_metadata,
        )
        final_metadata = os.fstat(descriptor)
        archive_identity = (
            archive_metadata.st_dev,
            archive_metadata.st_ino,
            archive_metadata.st_size,
            archive_metadata.st_mtime_ns,
            archive_metadata.st_ctime_ns,
        )
        final_identity = (
            final_metadata.st_dev,
            final_metadata.st_ino,
            final_metadata.st_size,
            final_metadata.st_mtime_ns,
            final_metadata.st_ctime_ns,
        )
        if archive_identity != final_identity:
            raise VerificationError("Site archive changed while it was inspected.")
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if root_members != 1:
        raise VerificationError("Site archive must contain exactly one canonical root directory member.")

    children: dict[str, set[str]] = {"": set()}
    for relative in [*directories, *files]:
        path = PurePosixPath(relative)
        parent = "" if path.parent == PurePosixPath(".") else path.parent.as_posix()
        if parent and parent not in directories:
            raise VerificationError(f"Site archive omits parent directory for {relative}.")
        children.setdefault(parent, set()).add(path.name)
        children.setdefault(relative, set())

    ordered_directories: list[dict[str, Any]] = []
    ordered_files: list[dict[str, Any]] = []

    def walk(parent: str) -> None:
        for child in sorted(children.get(parent, set())):
            relative = f"{parent}/{child}" if parent else child
            if relative in directories:
                ordered_directories.append(directories[relative])
                walk(relative)
            elif relative in files:
                ordered_files.append(files[relative])
            else:
                raise VerificationError(f"Site archive inventory is inconsistent at {relative}.")

    walk("")
    if len(ordered_directories) != len(directories) or len(ordered_files) != len(files):
        raise VerificationError("Site archive contains unreachable inventory entries.")
    payload = {
        "schema": FINGERPRINT_SCHEMA,
        "directories": ordered_directories,
        "files": ordered_files,
    }
    tree = {
        "bytes": sum(record["size"] for record in ordered_files),
        "file_count": len(ordered_files),
        "path": "site",
        "sha256": hashlib.sha256(b"unaltraweb-tree-v1\0" + canonical_json(payload)).hexdigest(),
    }
    return tree, files


def verify_sums(path: Path, assets: dict[str, Path], expected_names: set[str]) -> None:
    content, _ = regular_content(path, label="SHA256SUMS")
    lines = content.splitlines(keepends=True)
    if not lines or any(not line.endswith(b"\n") for line in lines):
        raise VerificationError("SHA256SUMS must be non-empty and newline terminated.")
    received: dict[str, str] = {}
    for line in lines:
        value = line[:-1].decode("utf-8")
        if "  " not in value:
            raise VerificationError("SHA256SUMS contains a malformed line.")
        digest, raw_name = value.split("  ", 1)
        if raw_name.startswith("./"):
            raw_name = raw_name[2:]
        name = safe_relative(raw_name, label="SHA256SUMS asset").as_posix()
        if "/" in name or not SHA256_RE.fullmatch(digest) or name in received:
            raise VerificationError("SHA256SUMS contains an unsafe, duplicate, or invalid entry.")
        received[name] = digest
    if set(received) != expected_names:
        raise VerificationError("SHA256SUMS does not exactly inventory the authorized release assets.")
    for name, digest in received.items():
        if file_record(assets[name], label=f"release asset {name}")["sha256"] != digest:
            raise VerificationError(f"Release asset checksum mismatch: {name}")


def verify(args: argparse.Namespace) -> dict[str, Any]:
    if not SELECTOR_RE.fullmatch(args.selector):
        raise VerificationError("Invalid stable selector.")
    for label, value in [
        ("reviewed SHA", args.reviewed_sha),
        ("core SHA", args.core_sha),
    ]:
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            raise VerificationError(f"Invalid {label}.")
    if not SHA256_RE.fullmatch(args.candidate_manifest_sha256):
        raise VerificationError("Invalid candidate manifest SHA-256.")
    if not IMAGE_RE.fullmatch(args.manual_pdf_image):
        raise VerificationError("Invalid manual PDF image digest reference.")
    if not SITE_IMAGE_RE.fullmatch(args.site_build_image):
        raise VerificationError("Invalid stable site-build image digest reference.")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.python_version) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", args.ruby_version
    ):
        raise VerificationError("Stable runtime versions must use exact three-part versions.")
    if args.vegavisuals_sha and not re.fullmatch(r"[0-9a-f]{40}", args.vegavisuals_sha):
        raise VerificationError("Invalid vegavisuals SHA.")

    assets_root = args.assets.absolute()
    assets = regular_asset_inventory(assets_root)
    manifest_path = assets.get("release-manifest.json")
    publication_path = assets.get("publication.json")
    if manifest_path is None or publication_path is None:
        raise VerificationError("Release assets omit required publication metadata.")

    manifest_content, manifest_record = regular_content(manifest_path, label="release-manifest.json")
    if manifest_record["sha256"] != args.candidate_manifest_sha256:
        raise VerificationError("release-manifest.json does not match the locally reviewed digest.")
    manifest = strict_json(manifest_content, label="release-manifest.json")
    expected_manifest_keys = {"channel", "fingerprint_schema", "pdfs", "schema_version", "selector", "site", "source"}
    if not isinstance(manifest, dict) or set(manifest) != expected_manifest_keys:
        raise VerificationError("release-manifest.json has an unexpected schema.")
    if (
        manifest["channel"] != "stable"
        or manifest["fingerprint_schema"] != FINGERPRINT_SCHEMA
        or manifest["schema_version"] != 2
        or manifest["selector"] != args.selector
    ):
        raise VerificationError("release-manifest.json does not identify the authorized stable release.")
    source = manifest.get("source")
    if (
        not isinstance(source, dict)
        or set(source) != {"bytes", "commit", "file_count", "sha256", "site_build_image", "source_date_epoch"}
        or type(source.get("bytes")) is not int
        or type(source.get("file_count")) is not int
        or source.get("commit") != args.reviewed_sha
        or source.get("site_build_image") != args.site_build_image
        or not SHA256_RE.fullmatch(str(source.get("sha256") or ""))
        or not re.fullmatch(r"[0-9]+", str(source.get("source_date_epoch") or ""))
    ):
        raise VerificationError("release-manifest.json has an invalid source fingerprint.")

    publication_content, _ = regular_content(publication_path, label="publication.json")
    publication = strict_json(publication_content, label="publication.json")
    if not isinstance(publication, dict) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", str(publication.get("site_build_python_version") or "")
    ):
        raise VerificationError("publication.json does not record a valid site-build Python version.")
    expected_publication = {
        "candidate_manifest_sha256": args.candidate_manifest_sha256,
        "channel": "stable",
        "core_sha": args.core_sha,
        "manual_pdf_image": args.manual_pdf_image,
        "python_version": args.python_version,
        "repository": args.repository,
        "ruby_version": args.ruby_version,
        "schema_version": 2,
        "selector": args.selector,
        "site_build_image": args.site_build_image,
        "site_build_python_version": publication["site_build_python_version"],
        "source_date_epoch": source["source_date_epoch"],
        "source_sha": args.reviewed_sha,
        "vegavisuals_sha": args.vegavisuals_sha,
    }
    if publication != expected_publication:
        raise VerificationError("publication.json does not match the authorized release request.")

    pdfs = manifest["pdfs"]
    if not isinstance(pdfs, list) or not pdfs:
        raise VerificationError("release-manifest.json has no PDF inventory.")
    expected_asset_names = {
        "SHA256SUMS",
        "publication.json",
        "release-manifest.json",
        f"manual-site-{args.selector}.tar.gz",
    }
    pdf_asset_records: dict[str, dict[str, Any]] = {}
    expected_pdf_keys = {
        "cover_path",
        "cover_sha256",
        "cover_site_path",
        "cover_size",
        "draft",
        "language",
        "path",
        "published_path",
        "sha256",
        "site_path",
        "size",
    }
    for record in pdfs:
        if not isinstance(record, dict) or set(record) != expected_pdf_keys or record.get("draft") is not False:
            raise VerificationError("Stable PDF inventory contains an invalid or draft record.")
        pdf_path = safe_relative(record.get("path"), label="standalone PDF path")
        published_path = safe_relative(record.get("published_path"), label="published PDF path")
        site_path = safe_relative(record.get("site_path"), label="site PDF path")
        cover_path = safe_relative(record.get("cover_path"), label="published cover path")
        cover_site_path = safe_relative(record.get("cover_site_path"), label="site cover path")
        if len(pdf_path.parts) != 2 or pdf_path.parts[0] != "pdf" or pdf_path.suffix.lower() != ".pdf":
            raise VerificationError("Standalone PDF path is misplaced or has the wrong suffix.")
        if site_path.parts != ("site", *published_path.parts) or cover_site_path.parts != ("site", *cover_path.parts):
            raise VerificationError("PDF or cover site path does not match its published path.")
        if pdf_path.name != published_path.name:
            raise VerificationError("Standalone and published PDF names differ.")
        if not SHA256_RE.fullmatch(str(record.get("sha256") or "")) or not SHA256_RE.fullmatch(str(record.get("cover_sha256") or "")):
            raise VerificationError("PDF inventory contains an invalid digest.")
        if type(record.get("size")) is not int or type(record.get("cover_size")) is not int:
            raise VerificationError("PDF inventory contains an invalid size.")
        key = name_key(pdf_path.name)
        if key in {name_key(name) for name in expected_asset_names} or key in pdf_asset_records:
            raise VerificationError("PDF asset names collide.")
        expected_asset_names.add(pdf_path.name)
        pdf_asset_records[key] = record

    if set(assets) != expected_asset_names:
        raise VerificationError("Release artifact contains missing or unauthorized files.")

    site_archive = assets[f"manual-site-{args.selector}.tar.gz"]
    site_tree, site_files = tar_tree_record(site_archive)
    if manifest.get("site") != site_tree:
        raise VerificationError("Site archive fingerprint does not match release-manifest.json.")
    for record in pdfs:
        pdf_name = PurePosixPath(record["path"]).name
        standalone = file_record(assets[pdf_name], label=f"standalone PDF {pdf_name}")
        if standalone != {"sha256": record["sha256"], "size": record["size"]}:
            raise VerificationError(f"Standalone PDF does not match release-manifest.json: {pdf_name}")
        site_pdf = PurePosixPath(record["site_path"]).relative_to("site").as_posix()
        site_cover = PurePosixPath(record["cover_site_path"]).relative_to("site").as_posix()
        site_pdf_record = site_files.get(site_pdf)
        if site_pdf_record is None or (site_pdf_record["sha256"], site_pdf_record["size"]) != (
            record["sha256"],
            record["size"],
        ):
            raise VerificationError(f"Site PDF does not match release-manifest.json: {site_pdf}")
        cover = site_files.get(site_cover)
        if cover is None or (cover["sha256"], cover["size"]) != (record["cover_sha256"], record["cover_size"]):
            raise VerificationError(f"Site cover does not match release-manifest.json: {site_cover}")

    verify_sums(assets["SHA256SUMS"], assets, expected_asset_names - {"SHA256SUMS"})
    return {
        "asset_count": len(expected_asset_names),
        "candidate_manifest_sha256": args.candidate_manifest_sha256,
        "ok": True,
        "selector": args.selector,
        "site_fingerprint": site_tree["sha256"],
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Verify stable manual release assets against reviewed evidence.")
    value.add_argument("--assets", type=Path, required=True)
    value.add_argument("--selector", required=True)
    value.add_argument("--reviewed-sha", required=True)
    value.add_argument("--core-sha", required=True)
    value.add_argument("--manual-pdf-image", required=True)
    value.add_argument("--python-version", required=True)
    value.add_argument("--ruby-version", required=True)
    value.add_argument("--site-build-image", required=True)
    value.add_argument("--vegavisuals-sha", default="")
    value.add_argument("--repository", required=True)
    value.add_argument("--candidate-manifest-sha256", required=True)
    value.add_argument("--reference-assets", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.reference_assets is not None:
            compare_asset_directories(args.reference_assets.absolute(), args.assets.absolute())
        result = verify(args)
        if args.reference_assets is not None:
            result["reference_assets_match"] = True
    except (OSError, VerificationError, tarfile.TarError) as exc:
        print(json.dumps({"error": str(exc), "ok": False}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
