"""Fixed manager/worker program executed inside an explicitly prepared image.

Only the authenticated controller supplies this program and its request. It is
not a public command API. No Docker socket or host checkout is available here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import unicodedata
import zipfile

MARKER = ".mcp-job-storage-marker.json"
ROOT = Path("/work")
ROOTS = {"inputs", "results", "exports", "recovery", "scratch"}
DOMAIN_UID = 65532
MAX_CONTROL = 1024 * 1024


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(value):
    require(isinstance(value, str) and 0 < len(value) <= 1024 and unicodedata.normalize("NFC", value) == value
            and not any(unicodedata.category(c).startswith("C") or c in '\\:%$*?[]{}<>"|' for c in value), "unsafe worker path")
    parts = value.split("/")
    require(len(parts) <= 64 and all(part not in {"", ".", ".."} and part == part.strip() and not part.endswith(".")
            and part.casefold() not in {".git", ".hg", ".svn"} and not part.startswith("~")
            and re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?", part) is None for part in parts), "unsafe worker path")
    return value


def path(value):
    relative(value)
    require(value.split("/")[0] in ROOTS, "path is outside job roots")
    current = ROOT
    for component in value.split("/"):
        current = current / component
        require(not current.is_symlink(), "worker path contains a symlink")
    return current


def read_regular(source, maximum=512*1024*1024, collect=False):
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum, "unverifiable worker file")
        hasher, total, chunks = hashlib.sha256(), 0, []
        while True:
            chunk = os.read(fd, min(65536, maximum-total+1))
            if not chunk:
                break
            total += len(chunk)
            require(total <= maximum, "worker file exceeds limit")
            hasher.update(chunk)
            if collect:
                chunks.append(chunk)
        after = os.fstat(fd)
        signature = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_nlink, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        require(signature(before) == signature(after) == signature(os.stat(source, follow_symlinks=False)), "worker file changed while reading")
        return hasher.hexdigest(), total, b"".join(chunks)
    finally:
        os.close(fd)


def marker(root, expected):
    actual, _, raw = read_regular(root / MARKER, MAX_CONTROL, collect=True)
    require(actual == expected["sha256"] and raw == canonical(expected["document"]), "mounted volume marker differs from its binding")


def check_markers(request):
    for role, expected in request["markers"].items():
        require(role in {"retained", "scratch"}, "unsupported marker role")
        marker(ROOT if role == "retained" else ROOT / "scratch", expected)


def install_binding(request):
    binding = request.get("binding")
    if binding is None:  # Manager-owned maintenance, not a domain/transfer lease.
        return
    require(binding.get("job_root") == "/work" and binding.get("kind") == "gacontext.job-storage-binding", "invalid worker binding")
    for mount in binding["mounts"]:
        expected = request["markers"][mount["role"]]
        document = expected["document"]
        require(mount["marker_sha256"] == expected["sha256"] and mount["id"] == document["volume_id"], "binding volume mismatch")
        for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id"):
            require(binding[key] == document[key], "binding identity mismatch")
    target = Path("/run/gacontext/job-storage.json")
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(canonical(binding))
    target.chmod(0o444)
    os.environ["MCP_JOB_STORAGE_BINDING"] = str(target)


def initialize(request):
    for role, expected in request["markers"].items():
        root = ROOT if role == "retained" else ROOT / "scratch"
        allowed = {"scratch"} if role == "retained" else set()
        require(set(os.listdir(root)) <= allowed, "new volume is not empty; refusing marker adoption")
        raw = canonical(expected["document"])
        require(digest(raw) == expected["sha256"], "invalid initial marker digest")
        with (root / MARKER).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        (root / MARKER).chmod(0o444)
        directories = ("inputs", "results", "exports", "recovery") if role == "retained" else ("tmp", "home", "cache", "work")
        for name in directories:
            directory = root / name
            directory.mkdir(mode=0o755)
            if role == "scratch" or name in {"results", "recovery"}:
                os.chown(directory, DOMAIN_UID, DOMAIN_UID)
        if role == "retained":
            (root / "recovery/.manager").mkdir(mode=0o700)
        root.chmod(0o755)
    check_markers(request)
    return observe(request)


def walk(root, *, hashing=False, skip=()):
    records, total, entries = [], 0, 0
    pending = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        for item in sorted(os.scandir(directory), key=lambda item: item.name):
            rel = prefix + item.name
            if not prefix and item.name in skip:
                continue
            entries += 1
            require(entries <= 1000000, "job entry count exceeds observation bound")
            info = item.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                require(rel.count("/") <= 64, "job directory depth exceeds observation bound")
                pending.append((Path(item.path), rel + "/"))
                if hashing:
                    records.append({"path": rel, "type": "directory"})
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                total += info.st_size
                if hashing:
                    hashed, size, _ = read_regular(item.path, 2*1024*1024*1024 + MAX_CONTROL)
                    records.append({"path": rel, "type": "file", "sha256": hashed, "bytes": size})
            else:
                if hashing:
                    records.append({"path": rel, "type": "unverifiable"})
                total += info.st_size
    records.sort(key=lambda item: item["path"])
    return total, entries, records


def usage(request):
    metrics = {}
    for role in request["markers"]:
        root = ROOT if role == "retained" else ROOT / "scratch"
        size, entries, _ = walk(root, skip=(MARKER, "scratch") if role == "retained" else (MARKER,))
        filesystem = os.statvfs(root)
        metrics[role] = {"bytes": size, "entries": entries, "free_bytes": filesystem.f_bavail * filesystem.f_frsize,
                         "filesystem_device": os.stat(root).st_dev}
    return metrics


def budget(request):
    metrics = usage(request)
    limits = request["limits"]
    for role, value in metrics.items():
        require(value["bytes"] <= limits["max_"+role+"_bytes"], role + " byte ceiling exceeded")
        require(value["entries"] <= limits["max_entries"], "job entry ceiling exceeded")
        require(value["free_bytes"] >= limits["min_free_bytes"], "Docker storage minimum free space breached")
    return metrics


def observe(request):
    check_markers(request)
    size, entries, records = walk(ROOT, hashing=True, skip=(MARKER, "scratch"))
    covered = {}
    for product in request.get("products", []):
        from unaltraweb_mcp import artifact_handoff_v1 as handoff
        manifest_path = product["bundle_path"]
        handoff.check(str(ROOT), "bundle", manifest_path, product["bundle_sha256"])
        domain_check(ROOT, manifest_path, product["bundle_sha256"])
        _, _, raw = read_regular(path(manifest_path), MAX_CONTROL, collect=True)
        manifest = json.loads(raw)
        bundle_root = manifest_path.rpartition("/")[0]
        covered.setdefault(manifest_path, set()).add(product["bundle_sha256"])
        for item in manifest["files"]:
            covered.setdefault(bundle_root + "/" + item["path"], set()).add(item["sha256"])
            if item["path"].startswith("payload/"):
                covered.setdefault(item["path"].removeprefix("payload/"), set()).add(item["sha256"])
        for representation in product.get("representations", []):
            actual, size, _ = read_regular(path(representation["path"]), 2*1024*1024*1024 + MAX_CONTROL)
            require(actual == representation["sha256"] and size == representation["bytes"], "retention representation changed")
            covered.setdefault(representation["path"], set()).add(actual)
    unresolved = [item for item in records if item["type"] != "directory"
                  and item.get("sha256") not in covered.get(item["path"], set())]
    by_root = {}
    for item in unresolved:
        key = item["path"].split("/")[0]
        key = key if key in ROOTS else "unknown"
        by_root[key] = by_root.get(key, 0) + 1
    return {"observed_at": utc(), "metrics": usage(request),
            "protected_inventory": {"state": "verified", "tree_sha256": digest(canonical(records)),
                                    "unresolved_entries": len(unresolved)},
            "sample": unresolved[:16], "unresolved_by_root": by_root,
            "work_tree_sha256": digest(canonical([item for item in records if item["path"].split("/")[0] != "exports"])),
            "protected_bytes": size, "protected_entries": entries}


def unpack_inputs(request):
    destination = path(request.get("destination", "inputs"))
    require(destination == ROOT / "inputs", "input transfer must use inputs/")
    seen, aliases, total = set(), {}, 0
    last_budget = time.monotonic()
    initial = budget(request)["retained"]["bytes"]
    limits = request["limits"]
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as archive:
        for member in archive:
            relative(member.name)
            require(member.name.casefold() not in seen, "duplicate or case-aliased input path")
            seen.add(member.name.casefold())
            parts = member.name.split("/")
            for depth in range(1, len(parts)+1):
                prefix = "/".join(parts[:depth])
                key = prefix.casefold()
                require(key not in aliases or aliases[key] == prefix, "case-aliased input ancestor")
                aliases[key] = prefix
            require(len(seen) <= limits["max_entries"], "input entry limit exceeded")
            require(member.isdir() or member.isfile(), "input links/devices are unsupported")
            require(not member.sparse and 0 <= member.size <= 512*1024*1024, "input member exceeds limit")
            total += member.size
            require(initial + total <= limits["max_retained_bytes"], "input transfer exceeds retained budget")
            target = path("inputs/" + member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            require(source is not None, "input member is incomplete")
            with target.open("xb") as output:
                remaining = member.size
                while remaining:
                    chunk = source.read(min(65536, remaining))
                    require(bool(chunk), "truncated input transfer")
                    output.write(chunk)
                    remaining -= len(chunk)
                    if time.monotonic() - last_budget >= limits["monitor_interval_seconds"]:
                        budget(request)
                        last_budget = time.monotonic()
                output.flush()
                os.fsync(output.fileno())
            target.chmod(0o444 | (member.mode & 0o111))
    _, _, raw = read_regular(path(request["manifest"]), MAX_CONTROL, collect=True)
    manifest = json.loads(raw)
    for entry in manifest["inputs"]:
        actual, size, _ = read_regular(path("inputs/" + entry["path"]))
        require(actual == entry["sha256"] and size == entry["bytes"], "selected input bytes changed during transfer")
    budget(request)
    return observe(request)


def prepare_workspace(request):
    source, destination = path(request["source"]), path(request["destination"])
    require(request["source"].startswith("inputs/") and request["destination"].startswith("results/"), "invalid execution workspace copy")
    require(not destination.exists(), "execution workspace already exists")
    for item in source.rglob("*"):
        require(not item.is_symlink(), "execution input contains a link")
    shutil.copytree(source, destination, symlinks=False)
    for item in [destination, *destination.rglob("*")]:
        item.chmod(0o700 if item.is_dir() else 0o600 | (item.stat().st_mode & 0o111))
        os.chown(item, DOMAIN_UID, DOMAIN_UID)
    budget(request)
    return observe(request)


def seal_product(request):
    from unaltraweb_mcp import artifact_handoff_v1 as handoff
    product_id = request["product_id"]
    require(re.fullmatch(r"[0-9a-f]{32}", product_id) is not None, "invalid product identity")
    _, _, records = walk(ROOT, hashing=True, skip=(MARKER, "scratch", "exports"))
    members = [item for item in records if item["type"] != "directory"]
    require(all(item["type"] == "file" for item in members), "unverifiable source/result remains protected")
    require(any(item["path"] == "inputs/request.json" for item in members), "effective request is not retained")
    require(any(item["path"].startswith("results/") for item in members), "no result is available to seal")
    require(len(members) <= 10000 and sum(item["bytes"] for item in members) <= 2*1024*1024*1024,
            "product exceeds artifact handoff v1 bounds")
    handoff.unique_paths([item["path"] for item in members])
    current = budget(request)["retained"]["bytes"]
    require(current + sum(item["bytes"] for item in members) + MAX_CONTROL <= request["limits"]["max_retained_bytes"],
            "sealing cannot fit within the retained reservation")
    destination = path("exports/" + product_id)
    require(not destination.exists(), "sealed product identity already exists")
    temporary = path("exports/.pending-" + product_id)
    temporary.mkdir()
    entries = []
    for index, item in enumerate(members):
        source = path(item["path"])
        target = temporary / "payload" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        actual, length, _ = read_regular(target)
        require(actual == item["sha256"] and length == item["bytes"], "file changed during product seal")
        relative_name = "payload/" + item["path"]
        kind = "input" if item["path"].startswith("inputs/") else "evidence" if item["path"].startswith("recovery/") else "output"
        is_request = item["path"] == "inputs/request.json"
        role = "request" if is_request else "source" if kind == "input" else "native-evidence" if kind == "evidence" else "result"
        if kind == "output" and source.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg"}:
            role = "rendered-visual"
        elif kind == "output" and source.suffix.lower() == ".pdf":
            role = "document"
        entries.append({"id": "request" if is_request else f"file-{index:06d}", "path": relative_name,
                        "kind": kind, "role": role, "ownership": "author" if kind == "input" else "producer",
                        "sha256": actual, "bytes": length})
    by_path = {item["path"]: item for item in entries}
    for item in entries:
        if item["path"].endswith(".edited.svg"):
            original = by_path.get(item["path"].removesuffix(".edited.svg") + ".svg")
            require(original is not None and original["kind"] == item["kind"], "edited figure has no same-kind original")
            item.update(variant_of=original["id"], ownership="author", role="edited-visual")
    manifest = {"schema_version": 1, "kind": "mcp-artifact-bundle", "producer": request["producer"],
                "request": "request", "files": entries, "dependencies": []}
    encoded = canonical(manifest)
    require(len(encoded) <= MAX_CONTROL, "sealed manifest exceeds its bound")
    with (temporary / "bundle.json").open("xb") as output:
        output.write(encoded)
    expected = digest(encoded)
    handoff.check(str(ROOT), "bundle", temporary.relative_to(ROOT).as_posix() + "/bundle.json", expected)
    domain = domain_check(ROOT, temporary.relative_to(ROOT).as_posix() + "/bundle.json", expected)
    budget(request)
    temporary.rename(destination)
    return {"product_id": product_id, "bundle_path": destination.relative_to(ROOT).as_posix() + "/bundle.json",
            "bundle_sha256": expected, "domain_profile": domain["domain_profile"], "domain_check_sha256": domain["evidence_sha256"],
            "work_tree_sha256": digest(canonical(records)), "files": len(entries), "observed_at": utc()}


def export_product(request):
    require(request.get("binding", {}).get("access") == "read-only", "product export requires its read-only transfer binding")
    manifest = request["bundle_path"]
    report = domain_check(ROOT, manifest, request["bundle_sha256"])
    source = path(manifest).parent
    members = sorted(item for item in source.rglob("*") if item.is_file())
    require(len(members) <= 10000, "product entry limit exceeded")
    format_name = request["format"]
    require(format_name in {"directory", "zip", "tar-gzip"}, "unsupported retention format")
    if format_name == "zip":
        with zipfile.ZipFile(sys.stdout.buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for source_file in members:
                read_regular(source_file)
                info = zipfile.ZipInfo(source_file.relative_to(source).as_posix(), date_time=(1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                with source_file.open("rb") as incoming, archive.open(info, "w", force_zip64=True) as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=65536)
    else:
        wrapper = gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb", mtime=0) if format_name == "tar-gzip" else sys.stdout.buffer
        try:
            with tarfile.open(fileobj=wrapper, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for source_file in members:
                    _, size, _ = read_regular(source_file)
                    info = tarfile.TarInfo(source_file.relative_to(source).as_posix())
                    info.size, info.mode, info.mtime = size, 0o644, 0
                    with source_file.open("rb") as incoming:
                        archive.addfile(info, incoming)
        finally:
            if format_name == "tar-gzip":
                wrapper.close()
    domain_check(ROOT, manifest, request["bundle_sha256"])
    print(json.dumps({"kind": "unaltraweb.product-export-check", "bundle_sha256": request["bundle_sha256"],
                      "domain_profile": report["domain_profile"], "domain_check_sha256": report["evidence_sha256"]}), file=sys.stderr)


def verify_archive(request):
    format_name = request["format"]
    require(format_name in {"zip", "tar-gzip"}, "unsupported archive format")
    source = path("inputs/source.archive")
    hasher, received = hashlib.sha256(), 0
    with source.open("xb") as output:
        while chunk := sys.stdin.buffer.read(65536):
            received += len(chunk)
            require(received <= request["archive_bytes"] <= 2*1024*1024*1024 + MAX_CONTROL, "archive transfer exceeds its bound")
            output.write(chunk)
            hasher.update(chunk)
    require(received == request["archive_bytes"] and hasher.hexdigest() == request["archive_sha256"], "archive copy differs from receiver bytes")
    extracted = path("scratch/work/verify-" + request["operation_id"])
    extracted.mkdir()
    names, aliases, total = set(), {}, 0

    def name_check(name):
        relative(name)
        require(name not in names, "duplicate archive entry")
        names.add(name)
        require(len(names) <= 10000, "archive entry limit exceeded")
        for depth in range(1, len(name.split("/"))+1):
            prefix = "/".join(name.split("/")[:depth])
            require(prefix.casefold() not in aliases or aliases[prefix.casefold()] == prefix, "case-aliased archive path")
            aliases[prefix.casefold()] = prefix

    def member(name, size, incoming):
        nonlocal total
        name_check(name)
        total += size
        require(0 <= size <= 512*1024*1024 and total <= 2*1024*1024*1024, "archive expansion exceeds artifact limits")
        target = extracted / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            remaining = size
            while remaining:
                chunk = incoming.read(min(65536, remaining))
                require(bool(chunk), "truncated archive entry")
                output.write(chunk)
                remaining -= len(chunk)
        budget(request)

    def directory(name):
        name_check(name)
        (extracted / name).mkdir(parents=True, exist_ok=True)

    if format_name == "zip":
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                require(not info.flag_bits & 1 and info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, "unsupported encrypted/compressed ZIP entry")
                mode = info.external_attr >> 16
                require(not mode or stat.S_IFMT(mode) in {0, stat.S_IFREG, stat.S_IFDIR}, "archive links/devices are unsupported")
                if info.is_dir():
                    directory(info.filename.rstrip("/"))
                    continue
                with archive.open(info) as incoming:
                    member(info.filename, info.file_size, incoming)
    else:
        with tarfile.open(source, mode="r:gz") as archive:
            for info in archive:
                require(info.isdir() or (info.isfile() and not info.sparse), "archive links/devices/sparse files are unsupported")
                if info.isdir():
                    directory(info.name.rstrip("/"))
                    continue
                incoming = archive.extractfile(info)
                require(incoming is not None, "archive entry is unreadable")
                member(info.name, info.size, incoming)
    report = domain_check(extracted, "bundle.json", request["bundle_sha256"])
    destination = path("exports/" + request["product_id"])
    require(not destination.exists(), "verification product already exists")
    budget(request)
    shutil.copytree(extracted, destination)
    domain_check(ROOT, destination.relative_to(ROOT).as_posix()+"/bundle.json", request["bundle_sha256"])
    budget(request)
    return {"bundle_path": destination.relative_to(ROOT).as_posix()+"/bundle.json", "bundle_sha256": request["bundle_sha256"],
            "domain_report": report, "archive_path": "inputs/source.archive", "archive_sha256": request["archive_sha256"],
            "archive_bytes": received, "format": format_name, "observed_at": utc()}


def lower_privileges():
    os.setgroups([])
    os.setgid(DOMAIN_UID)
    os.setuid(DOMAIN_UID)


def run_domain(request):
    require(request.get("binding", {}).get("access") == "read-write", "domain work needs a writer binding")
    command = request["command"]
    require(isinstance(command, list) and 1 <= len(command) <= 128 and all(isinstance(arg, str) and "\x00" not in arg for arg in command), "invalid internal worker command")
    cwd = path(request["cwd"])
    require(cwd.is_dir(), "domain working directory is absent")
    environment = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/work/scratch/home",
                   "TMPDIR": "/work/scratch/tmp", "XDG_CACHE_HOME": "/work/scratch/cache",
                   "MCP_JOB_STORAGE_BINDING": os.environ["MCP_JOB_STORAGE_BINDING"],
                   "MCP_CONSUMER_WORKSPACE": request["consumer"], "UNALTRAWEB_EXECUTION_WORKSPACE": str(cwd),
                   "SOURCE_DATE_EPOCH": "0", "FORCE_SOURCE_DATE": "1", "TZ": "UTC", "LANG": "C.UTF-8"}
    for key, value in request.get("environment", {}).items():
        require(key not in {"MCP_CONSUMER_WORKSPACE", "MCP_JOB_STORAGE_BINDING", "HOME", "TMPDIR"}, "internal environment overrides a storage binding")
        environment[key] = value
    operation = request["operation_id"]
    require(re.fullmatch(r"[0-9a-f]{32}", operation) is not None, "invalid operation identity")
    log_path = ROOT / "recovery/.manager" / (operation + ".log")
    budget(request)
    process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True, preexec_fn=lower_privileges)
    written, truncated = 0, False

    def drain():
        nonlocal written, truncated
        with log_path.open("xb") as log:
            while chunk := process.stdout.read(65536):
                permitted = max(0, 128*1024-written)
                log.write(chunk[:permitted])
                written += min(permitted, len(chunk))
                truncated = truncated or len(chunk) > permitted

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline = time.monotonic() + request.get("timeout_seconds", 1800)
    failure = None
    while process.poll() is None:
        try:
            check_markers(request)
            metrics = budget(request)
            require(time.monotonic() < deadline, "domain deadline exceeded")
            print(json.dumps({"kind": "unaltraweb.job-measurement", "operation_id": operation,
                              "observed_at": utc(), "metrics": metrics}), flush=True)
        except (ValueError, OSError) as exc:
            failure = str(exc)
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
            break
        time.sleep(min(request["limits"]["monitor_interval_seconds"], .25 if request.get("short_poll") else 2))
    process.wait()
    reader.join(timeout=3)
    require(not reader.is_alive(), "domain log stream did not terminate")
    try:
        final_metrics = budget(request)
    except (ValueError, OSError) as exc:
        failure = failure or str(exc)
        final_metrics = usage(request)
    result = {"kind": "unaltraweb.job-operation-result", "operation_id": operation, "exit_code": process.returncode,
              "pressure_or_timeout": failure, "log_truncated": truncated, "observed_at": utc(), "metrics": final_metrics}
    with (ROOT / "recovery/.manager" / (operation + ".json")).open("xb") as output:
        output.write(canonical(result))
    return result


def main():
    raw = os.environ.pop("UNALTRAWEB_W1_REQUEST", "")
    require(len(raw.encode()) <= MAX_CONTROL, "worker control request is too large")
    request = json.loads(raw)
    operation = request["operation"]
    if operation == "capacity-init":
        root = Path("/capacity")
        require(not list(root.iterdir()), "capacity probe volume is not empty")
        with (root / MARKER).open("xb") as stream:
            stream.write(canonical(request["marker"]["document"]))
        (root / MARKER).chmod(0o444)
        operation = "capacity"
    if operation == "capacity":
        marker(Path("/capacity"), request["marker"])
        info = os.statvfs("/capacity")
        result = {"observed_at": utc(), "free_bytes": info.f_bavail*info.f_frsize,
                  "filesystem_device": os.stat("/capacity").st_dev}
    elif operation == "initialize":
        result = initialize(request)
    else:
        check_markers(request)
        if request.get("binding") is not None:
            install_binding(request)
        if operation == "observe":
            result = observe(request)
        elif operation == "stage":
            result = unpack_inputs(request)
        elif operation == "run":
            result = run_domain(request)
        elif operation == "prepare-workspace":
            result = prepare_workspace(request)
        elif operation == "seal":
            result = seal_product(request)
        elif operation == "export":
            export_product(request)
            return
        elif operation == "verify-archive":
            result = verify_archive(request)
        else:
            raise ValueError("unsupported internal storage operation")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)[:4096]}), file=sys.stderr)
        raise SystemExit(1)
