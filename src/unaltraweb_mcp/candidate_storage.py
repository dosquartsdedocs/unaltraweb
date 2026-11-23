"""Versioned, fail-closed transport of temporary release candidates.

This module does not publish, choose a build, rewrite publication.json, or acquire
credentials. GitHub v4 actions carry the same directory that the optional S3 SDK
carries. The native release verifier remains the publication authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

POLICY_PATH = Path(".unaltraweb/artifact-storage.json")
ENVELOPE = "candidate-transfer.json"
DEFAULT_POLICY = {"schema_version": 1, "release_candidate": {"transport": "github-actions", "retention_days": 14}}
SDK_REQUIREMENT = "boto3==1.40.75"
MAX_FILE_BYTES = 2 * 1024**3
MAX_TOTAL_BYTES = 4 * 1024**3
MAX_JSON_BYTES = 65536
HASH = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SELECTOR = re.compile(r"v[0-9]{4}\.(?:0[1-9]|1[0-2])(?:\.[1-9][0-9]*)?\Z")


class StorageError(RuntimeError):
    """A transport/configuration/integrity failure, with no fallback authority."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def decode(content: bytes) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StorageError("Duplicate JSON key.")
            result[key] = value
        return result

    def nonfinite(_):
        raise StorageError("Non-finite JSON value.")

    try:
        if len(content) > MAX_JSON_BYTES:
            raise StorageError("JSON exceeds the bounded transport limit.")
        result = json.loads(content, object_pairs_hook=unique, parse_constant=nonfinite)
        if not isinstance(result, dict):
            raise StorageError("Expected a JSON object.")
        return result
    except (ValueError, UnicodeError) as exc:
        raise StorageError("Invalid UTF-8 JSON.") from exc


def real_path(path: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise StorageError("Symlinked transport paths are forbidden.")


def read_file(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    real_path(path)
    with path.open("rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise StorageError("Expected a regular transport file.")
        value = handle.read(limit + 1)
    if len(value) > limit:
        raise StorageError("Transport file exceeds its byte limit.")
    return value


def file_record(path: Path) -> dict[str, Any]:
    real_path(path)
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise StorageError("Candidate file is not a bounded regular file.")
        sha = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise StorageError("Candidate exceeds the file byte limit.")
        after = os.fstat(handle.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != after.st_size:
            raise StorageError("Candidate changed during hashing.")
    return {"sha256": sha.hexdigest(), "bytes": size}


def policy(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"schema_version", "release_candidate"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise StorageError("Unsupported artifact-storage schema; only release_candidate is selectable.")
    selection = value["release_candidate"]
    if not isinstance(selection, dict):
        raise StorageError("Invalid release_candidate policy.")
    transport = selection.get("transport")
    expected = {"transport", "retention_days"} | ({"s3"} if transport == "s3-private" else set())
    if transport not in {"github-actions", "s3-private"} or set(selection) != expected:
        raise StorageError("Unknown transport or policy fields.")
    days = selection["retention_days"]
    if type(days) is not int or not 1 <= days <= 14:
        raise StorageError("Candidate retention_days must be between 1 and 14.")
    if transport == "s3-private":
        s3 = selection["s3"]
        fields = {"profile", "endpoint_url", "region", "bucket", "prefix", "addressing_style", "lifecycle_rule_id"}
        if not isinstance(s3, dict) or set(s3) != fields or not all(isinstance(item, str) and item for item in s3.values()):
            raise StorageError("S3 configuration has missing/unknown fields; credentials never belong in policy.")
        if s3["profile"] not in {"s3", "s4"} or s3["addressing_style"] not in {"path", "virtual"}:
            raise StorageError("Unsupported S3 profile/addressing style.")
        endpoint = urlsplit(s3["endpoint_url"])
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or endpoint.path not in {"", "/"}:
            raise StorageError("S3 endpoint must be an explicit HTTPS origin without credentials.")
        for key in ("region", "bucket", "lifecycle_rule_id"):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", s3[key]):
                raise StorageError(f"Invalid S3 {key}.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", s3["prefix"]):
            raise StorageError("S3 prefix must be an isolated relative namespace.")
    return value


def project_policy(project: Path) -> dict[str, Any]:
    path = project / POLICY_PATH
    real_path(path)
    return policy(decode(read_file(path))) if path.exists() else policy(decode(canonical(DEFAULT_POLICY)))


def identity(repository: str, selector: str, source_sha: str, run_id: str, run_attempt: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or any(part in {".", ".."} for part in repository.split("/")):
        raise StorageError("Invalid GitHub project identity.")
    if not SELECTOR.fullmatch(selector) or not COMMIT.fullmatch(source_sha):
        raise StorageError("Invalid candidate selector/source SHA.")
    if not all(re.fullmatch(r"[1-9][0-9]{0,19}", item) for item in (run_id, run_attempt)):
        raise StorageError("Candidate run and attempt must be exact positive IDs.")
    return {"repository": repository, "selector": selector, "source_sha": source_sha, "run_id": run_id, "run_attempt": run_attempt}


def asset_inventory(assets: Path, binding: dict[str, str]) -> dict[str, dict[str, Any]]:
    real_path(assets)
    if not assets.is_dir():
        raise StorageError("Candidate assets are absent.")
    records = {}
    for path in assets.iterdir():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", path.name):
            raise StorageError("Unsafe candidate asset name.")
        records[path.name] = file_record(path)
    fixed = {"SHA256SUMS", "publication.json", "release-manifest.json", f"manual-site-{binding['selector']}.tar.gz"}
    pdfs = {name for name in records if name.endswith(".pdf")}
    if not 1 <= len(pdfs) <= 32 or set(records) != fixed | pdfs or sum(item["bytes"] for item in records.values()) > MAX_TOTAL_BYTES:
        raise StorageError("Candidate asset inventory differs from the native release package.")
    publication = decode(read_file(assets / "publication.json"))
    if type(publication.get("schema_version")) is not int or publication["schema_version"] != 2 or any(publication.get(key) != binding[key] for key in ("repository", "selector", "source_sha")):
        raise StorageError("Native schema2 publication identity differs from the selected build.")
    if publication.get("candidate_manifest_sha256") != records["release-manifest.json"]["sha256"]:
        raise StorageError("Native publication does not bind the release manifest.")
    return records


def _new_directory(destination: Path, write: Callable[[Path], None]) -> None:
    real_path(destination)
    real_path(destination.parent)
    if destination.exists() or not destination.parent.is_dir():
        raise StorageError("Transport output must be absent beneath an existing real directory.")
    with tempfile.TemporaryDirectory(prefix=".candidate-stage-", dir=destination.parent) as raw:
        stage = Path(raw) / "package"
        stage.mkdir()
        write(stage)
        # mkdir is create-only: even an empty competing destination is preserved.
        destination.mkdir()
        try:
            for child in stage.iterdir():
                child.rename(destination / child.name)
        except BaseException:
            # Never erase a caller's path on an uncertain partial installation.
            raise


def seal(assets: Path, destination: Path, selection: dict[str, Any], binding: dict[str, str], *, now: int | None = None) -> str:
    policy(selection)
    records = asset_inventory(assets, binding)
    now = int(time.time()) if now is None else now
    envelope = {"schema_version": 1, "artifact_class": "release_candidate", "identity": binding,
                "policy_sha256": digest(canonical(selection)), "created_at": now,
                "expires_at": now + selection["release_candidate"]["retention_days"] * 86400, "files": records}
    content = canonical(envelope)

    def write(stage):
        shutil.copytree(assets, stage / "release-assets", symlinks=False)
        (stage / ENVELOPE).write_bytes(content)
        verify(stage, selection, binding, digest(content), now=now)

    _new_directory(destination, write)
    return digest(content)


def verify_envelope(content: bytes, selection: dict[str, Any], binding: dict[str, str], expected: str, *, now: int | None = None) -> dict[str, Any]:
    policy(selection)
    if not HASH.fullmatch(expected) or digest(content) != expected:
        raise StorageError("Candidate transfer envelope SHA-256 differs from prepare output.")
    value = decode(content)
    if set(value) != {"schema_version", "artifact_class", "identity", "policy_sha256", "created_at", "expires_at", "files"} or value["schema_version"] != 1 or type(value["schema_version"]) is not int:
        raise StorageError("Unknown transfer envelope schema.")
    if value["artifact_class"] != "release_candidate" or value["identity"] != binding or value["policy_sha256"] != digest(canonical(selection)):
        raise StorageError("Candidate identity/policy mismatch; no other run or attempt may be selected.")
    now = int(time.time()) if now is None else now
    created, expires = value["created_at"], value["expires_at"]
    if type(created) is not int or type(expires) is not int or expires != created + selection["release_candidate"]["retention_days"] * 86400 or created > now + 300 or now >= expires:
        raise StorageError("Candidate retention has expired or its time bounds are invalid.")
    records = value["files"]
    if not isinstance(records, dict) or not 5 <= len(records) <= 36:
        raise StorageError("Invalid transfer inventory.")
    for name, record in records.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", name) or not isinstance(record, dict) or set(record) != {"bytes", "sha256"}:
            raise StorageError("Invalid transfer asset record.")
        if type(record["bytes"]) is not int or not 0 <= record["bytes"] <= MAX_FILE_BYTES or not isinstance(record["sha256"], str) or not HASH.fullmatch(record["sha256"]):
            raise StorageError("Invalid transfer asset hash/size.")
    if sum(item["bytes"] for item in records.values()) > MAX_TOTAL_BYTES:
        raise StorageError("Candidate exceeds the total byte limit.")
    return value


def verify(package: Path, selection: dict[str, Any], binding: dict[str, str], expected: str, *, now: int | None = None) -> dict[str, Any]:
    real_path(package)
    if {item.name for item in package.iterdir()} != {ENVELOPE, "release-assets"}:
        raise StorageError("Unexpected transfer package files.")
    envelope = verify_envelope(read_file(package / ENVELOPE), selection, binding, expected, now=now)
    if asset_inventory(package / "release-assets", binding) != envelope["files"]:
        raise StorageError("Candidate readback SHA-256/size/inventory mismatch.")
    return envelope


def sdk_client(selection: dict[str, Any]):
    """Explicit CI credentials only; never consult ~/.aws, metadata, or host keys."""
    access = os.environ.get("UNALTRAWEB_S3_ACCESS_KEY_ID", "")
    secret = os.environ.get("UNALTRAWEB_S3_SECRET_ACCESS_KEY", "")
    if not access or not secret:
        raise StorageError("Private S3 requires project CI credentials (optionally short-lived OIDC-derived credentials).")
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise StorageError(f"Install the optional public transport SDK: {SDK_REQUIREMENT}.") from exc
    config = selection["release_candidate"]["s3"]
    return boto3.client("s3", endpoint_url=config["endpoint_url"], region_name=config["region"],
                        aws_access_key_id=access, aws_secret_access_key=secret,
                        aws_session_token=os.environ.get("UNALTRAWEB_S3_SESSION_TOKEN") or None,
                        config=Config(signature_version="s3v4", connect_timeout=10, read_timeout=60,
                                      retries={"max_attempts": 0}, s3={"addressing_style": config["addressing_style"]}))


def _call(operation: Callable[[], Any], *, sleep: Callable[[float], None] = time.sleep):
    for attempt in range(3):
        try:
            return operation()
        except StorageError:
            raise
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            retryable = code in {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable"} or status in {429, 500, 502, 503, 504} or type(exc).__name__ in {"EndpointConnectionError", "ReadTimeoutError", "ConnectTimeoutError", "ConnectionClosedError"}
            if not retryable or attempt == 2:
                # SDK errors can include endpoints/headers; expose no raw exception.
                raise StorageError("S3 operation failed (absent, denied, conflict, or exhausted bounded retries); no fallback.") from None
            sleep(0.25 * (2**attempt))


def _s3_context(selection: dict[str, Any], binding: dict[str, str], client):
    policy(selection)
    if selection["release_candidate"]["transport"] != "s3-private":
        raise StorageError("S3 was not selected for this project/artifact class.")
    config = selection["release_candidate"]["s3"]
    bucket = config["bucket"]
    public_block = _call(lambda: client.get_public_access_block(Bucket=bucket)).get("PublicAccessBlockConfiguration", {})
    if any(public_block.get(key) is not True for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise StorageError("S3 candidates require all four bucket public-access blocks; qualify the private provider first.")
    rules = _call(lambda: client.get_bucket_lifecycle_configuration(Bucket=bucket)).get("Rules", [])
    matching = [rule for rule in rules if rule.get("ID") == config["lifecycle_rule_id"]]
    if len(matching) != 1:
        raise StorageError("Selected S3 lifecycle rule is absent or ambiguous.")
    rule = matching[0]
    prefix = config["prefix"] + "/"
    expiry = rule.get("Expiration", {})
    if rule.get("Status") != "Enabled" or rule.get("Filter", {"Prefix": rule.get("Prefix")}) != {"Prefix": prefix} or set(expiry) != {"Days"} or type(expiry["Days"]) is not int or not 1 <= expiry["Days"] <= selection["release_candidate"]["retention_days"]:
        raise StorageError("S3 lifecycle must bound only the isolated candidate prefix.")
    versioning = _call(lambda: client.get_bucket_versioning(Bucket=bucket)).get("Status")
    if versioning in {"Enabled", "Suspended"}:
        noncurrent = rule.get("NoncurrentVersionExpiration", {})
        if set(noncurrent) != {"NoncurrentDays"} or type(noncurrent["NoncurrentDays"]) is not int or not 1 <= noncurrent["NoncurrentDays"] <= selection["release_candidate"]["retention_days"]:
            raise StorageError("Versioned S3 candidates require bounded noncurrent-version expiration too.")
    suffix = "/".join(binding[key] for key in ("repository", "selector", "source_sha", "run_id", "run_attempt"))
    return bucket, prefix + "release_candidate/" + suffix + "/"


def _get(client, bucket: str, key: str, destination: Path | None, record: dict[str, Any], *, collect: bool = False) -> bytes:
    def read():
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            if response.get("ContentLength") != record["bytes"]:
                raise StorageError("S3 readback size mismatch.")
            sha = hashlib.sha256()
            size = 0
            result = bytearray()
            handle = destination.open("wb") if destination else None
            try:
                while True:
                    chunk = body.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > record["bytes"]:
                        raise StorageError("S3 readback exceeds its sealed size.")
                    sha.update(chunk)
                    if handle:
                        handle.write(chunk)
                    elif collect:
                        result.extend(chunk)
            finally:
                if handle:
                    handle.close()
            if size != record["bytes"] or sha.hexdigest() != record["sha256"]:
                raise StorageError("S3 readback SHA-256/size mismatch.")
            return bytes(result)
        finally:
            body.close()
    return _call(read)


def s3_upload(package: Path, selection: dict[str, Any], binding: dict[str, str], expected: str, *, client=None, now: int | None = None) -> None:
    envelope = verify(package, selection, binding, expected, now=now)
    client = client if client is not None else sdk_client(selection)
    bucket, prefix = _s3_context(selection, binding, client)
    for name, record in [*(envelope["files"].items()), (ENVELOPE, file_record(package / ENVELOPE))]:
        source = package / ENVELOPE if name == ENVELOPE else package / "release-assets" / name

        def put():
            with source.open("rb") as handle:
                return client.put_object(Bucket=bucket, Key=prefix + name, Body=handle, ContentLength=record["bytes"],
                                         IfNoneMatch="*", Metadata={"sha256": record["sha256"]})

        _call(put)
        _get(client, bucket, prefix + name, None, record)
    verify(package, selection, binding, expected, now=now)


def s3_download(destination: Path, selection: dict[str, Any], binding: dict[str, str], expected: str, envelope_bytes: int, *, client=None, now: int | None = None) -> None:
    if type(envelope_bytes) is not int or not 0 < envelope_bytes <= MAX_JSON_BYTES:
        raise StorageError("Invalid prepare envelope byte count.")
    client = client if client is not None else sdk_client(selection)
    bucket, prefix = _s3_context(selection, binding, client)
    content = _get(client, bucket, prefix + ENVELOPE, None, {"sha256": expected, "bytes": envelope_bytes}, collect=True)
    envelope = verify_envelope(content, selection, binding, expected, now=now)

    def write(stage):
        assets = stage / "release-assets"
        assets.mkdir()
        (stage / ENVELOPE).write_bytes(content)
        for name, record in envelope["files"].items():
            _get(client, bucket, prefix + name, assets / name, record)
        verify(stage, selection, binding, expected, now=now)

    _new_directory(destination, write)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["plan", "seal", "verify", "s3-upload", "s3-download", "receive"])
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path, help="Frozen versioned policy, outside release assets.")
    parser.add_argument("--policy-json-env", help="Read frozen policy from a named environment variable.")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sha256", default="")
    parser.add_argument("--envelope-bytes", type=int, default=0)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.policy and args.policy_json_env:
            raise StorageError("Select one frozen policy source.")
        selection = policy(decode(os.environ[args.policy_json_env].encode())) if args.policy_json_env else policy(decode(read_file(args.policy))) if args.policy else project_policy(args.project)
        if args.operation == "plan":
            if args.output:
                real_path(args.output)
                with args.output.open("xb") as handle:
                    handle.write(canonical(selection))
            values = {"transport": selection["release_candidate"]["transport"], "retention_days": selection["release_candidate"]["retention_days"],
                      "policy_json": json.dumps(selection, sort_keys=True, separators=(",", ":"))}
        else:
            binding = identity(os.environ["GITHUB_REPOSITORY"], os.environ["SELECTOR"], os.environ["REVIEWED_SHA"], os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"])
            if args.operation == "seal":
                if not args.assets or not args.output:
                    raise StorageError("seal requires --assets and --output.")
                sha = seal(args.assets, args.output, selection, binding)
                values = {"sha256": sha, "envelope_bytes": (args.output / ENVELOPE).stat().st_size}
            elif args.operation == "s3-download":
                if not args.output:
                    raise StorageError("s3-download requires --output.")
                s3_download(args.output, selection, binding, args.sha256, args.envelope_bytes)
                values = {"ok": True}
            else:
                if not args.package:
                    raise StorageError("Operation requires --package.")
                if args.operation == "s3-upload":
                    s3_upload(args.package, selection, binding, args.sha256)
                else:
                    verify(args.package, selection, binding, args.sha256)
                    if args.operation == "receive":
                        if not args.output:
                            raise StorageError("receive requires --output.")
                        _new_directory(args.output, lambda stage: [shutil.copyfile(source, stage / source.name) for source in (args.package / "release-assets").iterdir()])
                        if asset_inventory(args.output, binding) != asset_inventory(args.package / "release-assets", binding):
                            raise StorageError("Received native candidate differs from the transport package.")
                values = {"ok": True}
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                for key, value in values.items():
                    handle.write(f"{key}={value}\n")
        print(json.dumps(values, sort_keys=True))
        return 0
    except (StorageError, OSError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, StorageError) else "Missing/unsafe transport input or output."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
