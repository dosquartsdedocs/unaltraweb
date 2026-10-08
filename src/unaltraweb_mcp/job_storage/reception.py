"""Explicit site-selected durable retention; temporary jobs never witness delivery."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import tarfile
import uuid
import zipfile

from .. import __version__, artifact_handoff_v1 as handoff, manual_pdf_preview as fs
from ..editorial_sources import Reader, yaml_mapping
from . import bundles, contract as c

VOLATILE = {"tmp", "scratch", "sandbox", "dist", "_site", ".cache", ".jekyll-cache", "node_modules", "vendor"}


def policy(project):
    with Reader(project) as reader:
        raw = reader.read("_config.yml")
        config = yaml_mapping(raw.decode())
    value = (config.get("unaltraweb") or {}).get("product_retention")
    c.require(isinstance(value, dict) and value.get("enabled") is True,
              "Configure an explicit unaltraweb.product_retention policy once before automatic delivery", "storage-retention-policy-required")
    c.require(set(value) == {"enabled", "root", "format", "profiles", "assets"}, "Unknown or missing retention policy fields")
    root = c.relative_path(value["root"])
    c.require(not any(part in VOLATILE for part in Path(root).parts), "Retention root is temporary or generated staging", "storage-destination-not-durable")
    c.require(value["format"] in {"directory", "zip", "tar-gzip"}, "Unsupported receiver archive format")
    c.require(isinstance(value["profiles"], list) and all(isinstance(item, str) for item in value["profiles"]), "Invalid receiver profile selection")
    assets = value["assets"]
    c.require(isinstance(assets, dict) and set(assets) == {"root", "roles"}, "Invalid exposed asset policy")
    asset_root = c.relative_path(assets["root"])
    c.require(asset_root.startswith("assets/") and not any(part in VOLATILE for part in Path(asset_root).parts), "Exposed assets need a durable site assets root")
    c.require(isinstance(assets["roles"], list) and all(isinstance(item, str) for item in assets["roles"]), "Invalid exposed asset roles")
    c.require(not (root == asset_root or root.startswith(asset_root+"/") or asset_root.startswith(root+"/")), "Retained sources and exposed assets must have separate roots")
    return value, c.sha256(raw)


def durable_binding(manager):
    project = manager.origin.project
    fs._require_git_root(project)
    if manager.origin.container_id:
        container = manager.docker.inspect("container", manager.origin.container_id)
        c.require(container is not None, "Receiver container identity is unavailable", "storage-destination-not-durable")
        applicable = [mount for mount in container["mounts"] if str(project) == mount.get("Destination")
                      or str(project).startswith(str(mount.get("Destination", "!")) + "/")]
        c.require(applicable, "Receiver root has no observed source mount", "storage-destination-not-durable")
        selected = max(applicable, key=lambda item: len(item["Destination"]))
        c.require(selected.get("Type") == "bind", "A disposable or undeclared volume cannot be the durable receiver", "storage-destination-not-durable")
    else:
        c.require(not Path("/.dockerenv").exists(), "Uncorrelated container receiver cannot attest durability", "storage-destination-not-durable")
        mountpoints = []
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, _, right = line.partition(" - ")
            fields = left.split()
            target = fields[4].replace("\\040", " ").replace("\\134", "\\")
            if target == "/" or str(project) == target or str(project).startswith(target.rstrip("/") + "/"):
                mountpoints.append((len(target), right.split()[0]))
        c.require(mountpoints and max(mountpoints)[1] not in {"tmpfs", "ramfs"}, "Receiver is a temporary memory filesystem", "storage-destination-not-durable")


@contextmanager
def receiver_lock(project):
    root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parent = fs._open_directory(root, Path(".unaltraweb"), create=True)
    descriptor = os.open(".product-retention.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
    try:
        info = os.fstat(descriptor)
        c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Unsafe receiver lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise c.StorageError("storage-receiver-busy", "Another durable receiver transaction is active") from exc
        yield root
    finally:
        os.close(descriptor)
        os.close(parent)
        os.close(root)


def write_new(root, relative, content):
    relative = Path(c.relative_path(relative))
    parent = fs._open_directory(root, relative.parent, create=True)
    try:
        descriptor = os.open(relative.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(parent)


def copy_new(root, source_project, source_relative, target_relative, expected_sha):
    source_root = os.open(source_project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        source = fs._open_regular(source_root, Path(source_relative), label="retained source")
    finally:
        os.close(source_root)
    parent = fs._open_directory(root, Path(target_relative).parent, create=True)
    try:
        destination = os.open(Path(target_relative).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        hasher = hashlib.sha256()
        with os.fdopen(destination, "wb") as stream:
            while chunk := os.read(source, 65536):
                stream.write(chunk)
                hasher.update(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        c.require(hasher.hexdigest() == expected_sha, "Source changed while copying an exposed asset", "storage-copy-incomplete")
    finally:
        os.close(source)
        os.close(parent)


def rename_new(parent_fd, source, destination):
    function = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    c.require(function is not None, "Atomic no-replace directory publication is unavailable", "storage-publication-unsupported")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(parent_fd, os.fsencode(source), parent_fd, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise c.StorageError("storage-destination-conflict", "Final destination appeared before publication")
        raise OSError(error, os.strerror(error))


def selected_mappings(chosen, manifest, domain):
    by_path = {item["path"]: item for item in manifest["files"]}
    needed = {item["path"] for item in manifest["files"] if item["kind"] == "output" and item["role"] in chosen["assets"]["roles"]}
    changed = True
    while changed:
        changed = False
        for edge in domain["references"]:
            if edge["source"] in needed and edge["target"] not in needed:
                needed.add(edge["target"])
                changed = True
    return [{"source": path, "destination": chosen["assets"]["root"] + "/" + domain["bundle_sha256"] + "/" + path,
             "sha256": by_path[path]["sha256"]} for path in sorted(needed)]


class DirectorySink:
    def __init__(self, root_fd, destination):
        self.root_fd, self.destination = root_fd, destination
        self.complete = False

    def __call__(self, incoming):
        paths, size = [], 0
        with tarfile.open(fileobj=incoming, mode="r|") as archive:
            for member in archive:
                path = handoff.safe_path(member.name.rstrip("/"))
                c.require(member.isfile() and not member.sparse, "Transfer must contain only declared regular files", "storage-copy-incomplete")
                paths.append(path)
                handoff.unique_paths(paths)
                size += member.size
                c.require(len(paths) <= handoff.MAX_ENTRIES and 0 <= member.size <= handoff.MAX_FILE_BYTES and size <= handoff.MAX_TOTAL_BYTES,
                          "Transfer exceeds negotiated artifact limits", "storage-copy-incomplete")
                target = self.destination + "/" + path
                parent = fs._open_directory(self.root_fd, Path(target).parent, create=True)
                try:
                    fd = os.open(Path(target).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                    source = archive.extractfile(member)
                    c.require(source is not None, "Incomplete transfer member", "storage-copy-incomplete")
                    with os.fdopen(fd, "wb") as output:
                        remaining = member.size
                        while remaining:
                            chunk = source.read(min(65536, remaining))
                            c.require(bool(chunk), "Truncated transfer member", "storage-copy-incomplete")
                            output.write(chunk)
                            remaining -= len(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                finally:
                    os.close(parent)
        self.complete = True


class ArchiveSink:
    def __init__(self, root_fd, destination):
        self.root_fd, self.destination = root_fd, destination
        self.complete, self.bytes, self.sha256 = False, 0, ""

    def __call__(self, incoming):
        parent = fs._open_directory(self.root_fd, Path(self.destination).parent, create=True)
        try:
            descriptor = os.open(Path(self.destination).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            hasher = hashlib.sha256()
            with os.fdopen(descriptor, "wb") as output:
                while chunk := incoming.read(65536):
                    self.bytes += len(chunk)
                    c.require(self.bytes <= handoff.MAX_TOTAL_BYTES + c.MAX_DOCUMENT, "Archive exceeds transfer bound", "storage-copy-incomplete")
                    output.write(chunk)
                    hasher.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            self.sha256, self.complete = hasher.hexdigest(), True
        finally:
            os.close(parent)


@contextmanager
def archive_member(project, archive_path, format_name, member_path):
    handoff.safe_path(member_path)
    root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = fs._open_regular(root, Path(archive_path), label="retained archive")
    finally:
        os.close(root)
    with os.fdopen(descriptor, "rb") as source:
        if format_name == "zip":
            with zipfile.ZipFile(source) as archive:
                info = archive.getinfo(member_path)
                c.require(info.file_size <= handoff.MAX_FILE_BYTES, "Selected archive member exceeds bound")
                with archive.open(info) as stream:
                    yield stream
        else:
            with tarfile.open(fileobj=source, mode="r:gz") as archive:
                info = archive.getmember(member_path)
                c.require(info.isfile() and info.size <= handoff.MAX_FILE_BYTES, "Selected archive member is not bounded regular data")
                stream = archive.extractfile(info)
                c.require(stream is not None, "Selected archive member is absent")
                with stream:
                    yield stream


def copy_archive_asset(root, project, archive_path, format_name, mapping):
    parent = fs._open_directory(root, Path(mapping["destination"]).parent, create=True)
    try:
        descriptor = os.open(Path(mapping["destination"]).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        hasher, size = hashlib.sha256(), 0
        with os.fdopen(descriptor, "wb") as output, archive_member(project, archive_path, format_name, mapping["source"]) as source:
            while chunk := source.read(65536):
                size += len(chunk)
                c.require(size <= handoff.MAX_FILE_BYTES, "Exposed archive member exceeds bound")
                output.write(chunk)
                hasher.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        c.require(hasher.hexdigest() == mapping["sha256"], "Archive asset differs from verified bytes", "storage-copy-incomplete")
    finally:
        os.close(parent)


def acknowledge(manager, root, witness, domain, registry_id, job_id, product_id):
    """Write evidence of bytes already independently checked by the receiver."""
    envelope = {"kind": "gacontext.job-product-retention", "schema_version": 1, "registry_id": registry_id,
                "job_id": job_id, "product_id": product_id, "bundle_sha256": witness["bundle_sha256"],
                "receiver_binding_id": witness["receiver_binding_id"],
                "destination": {"path": witness["path"], "format": witness["format"], "content_sha256": witness["content_sha256"]},
                "domain_profile": domain["domain_profile"], "domain_check_sha256": domain["evidence_sha256"], "verified_at": c.now()}
    c.validate(envelope)
    witness = {**witness, "envelope_path": str(Path(witness["binding_path"]).parent /
               ("retention-" + product_id + "-" + uuid.uuid4().hex + ".json"))}
    write_new(root, witness["envelope_path"], c.canonical(envelope))
    witness["envelope_sha256"] = c.sha256(c.canonical(envelope))
    return {"envelope": envelope, "witness": witness}


def observe_stored(manager, bundle_sha256):
    """Revalidate a policy-selected final copy, including after relocation.

    Caller holds the receiver lock. Previous receipts are historical data, never
    authority to skip verification of a copied archive or adopt another registry.
    """
    c.require(isinstance(bundle_sha256, str) and c.HASH_RE.fullmatch(bundle_sha256) is not None, "Invalid bundle digest")
    project = manager.origin.project
    chosen, policy_sha = policy(project)
    durable_binding(manager)
    with manager.registry.locked() as registry:
        receiver_id = manager._binding(registry)["id"]
    base = chosen["root"] + "/" + bundle_sha256 + "/" + chosen["format"]
    filename = "bundle" if chosen["format"] == "directory" else "bundle.zip" if chosen["format"] == "zip" else "bundle.tar.gz"
    witness = {"receiver_binding_id": receiver_id, "receiver_host_root": manager.origin.host_project,
               "receiver_root_identity": {"device": project.stat().st_dev, "inode": project.stat().st_ino},
               "binding_path": base + "/binding.json", "format": chosen["format"], "path": base + "/" + filename,
               "bundle_sha256": bundle_sha256, "content_sha256": bundle_sha256, "policy_sha256": policy_sha}
    # Reject obvious partial copies/author conflicts before allocating verifier storage.
    with Reader(project, max_bytes=handoff.MAX_FILE_BYTES, max_total_bytes=handoff.MAX_TOTAL_BYTES) as reader:
        binding = c.parse(reader.read(witness["binding_path"]))
        c.require(binding.get("bundle_sha256") == bundle_sha256 and binding.get("policy_sha256") == policy_sha
                  and binding.get("path") == witness["path"] and binding.get("format") == chosen["format"],
                  "Stored binding no longer matches receiver policy", "storage-retention-stale")
        for mapping in binding["mappings"]:
            c.require(c.sha256(reader.read(mapping["destination"])) == mapping["sha256"], "An exposed authored asset changed", "storage-retention-stale")
    verification = None
    if chosen["format"] != "directory":
        workspace = handoff.Workspace(str(project))
        try:
            archive_sha, size, _ = workspace.read(witness["path"], handoff.MAX_TOTAL_BYTES + c.MAX_DOCUMENT)
        finally:
            workspace.close()
        verification = manager.verify_archive(witness["path"], chosen["format"], bundle_sha256, archive_sha, size)
        witness.update(content_sha256=archive_sha, archive_verification_id=verification["verification_id"])
    domain = verify_record(manager, witness)
    return {"witness": witness, "domain": domain, "verification_job": verification}


def receive_product(manager, registry_id, job_id, product_id):
    project = manager.origin.project
    chosen, policy_sha = policy(project)
    format_name = chosen["format"]
    durable_binding(manager)
    with manager.registry.locked() as registry:
        job = manager._job(registry, job_id, registry_id)
        c.require(job["phase"] not in {"releasing", "released"}, "Retirement is fenced; use independent retained-product revalidation", "storage-admission-closed")
        product = next((item for item in job["products"] if item["id"] == product_id), None)
        c.require(product is not None and product["domain_profile"] in chosen["profiles"], "Product domain is outside the receiver policy", "storage-retention-policy-mismatch")
        bundle_sha = product["bundle_sha256"]
        receiver_id = manager._binding(registry)["id"]
    parent_relative = chosen["root"] + "/" + bundle_sha
    final_relative = parent_relative + "/" + format_name
    candidate = parent_relative + "/.incoming-" + uuid.uuid4().hex
    filename = "bundle" if format_name == "directory" else "bundle.zip" if format_name == "zip" else "bundle.tar.gz"
    with receiver_lock(project) as root:
        parent = fs._open_directory(root, Path(parent_relative), create=True)
        os.close(parent)
        final = project / final_relative
        if final.exists() or final.is_symlink():
            existing = observe_stored(manager, bundle_sha)
            result = acknowledge(manager, root, existing["witness"], existing["domain"], registry_id, job_id, product_id)
            return {**result, "export_check": None, "verification_job": existing["verification_job"], "reused": True}
        candidate_fd = fs._open_directory(root, Path(candidate + ("/bundle" if format_name == "directory" else "")), create=True)
        os.close(candidate_fd)
        sink = DirectorySink(root, candidate + "/bundle") if format_name == "directory" else ArchiveSink(root, candidate + "/" + filename)
        transferred = manager.export_product(registry_id, job_id, product_id, format_name, sink)
        c.require(sink.complete, "Copy did not complete", "storage-copy-incomplete")
        verification = None
        if format_name == "directory":
            domain = bundles.check(project, candidate + "/bundle/bundle.json", bundle_sha)
            content_sha = bundle_sha
        else:
            verification = manager.verify_archive(candidate + "/" + filename, format_name, bundle_sha, sink.sha256, sink.bytes)
            domain, content_sha = verification["report"], sink.sha256
        c.require(domain["domain_profile"] in chosen["profiles"], "Copied domain differs from receiver policy", "storage-retention-policy-mismatch")
        with Reader(project, max_bytes=handoff.MAX_FILE_BYTES, max_total_bytes=handoff.MAX_TOTAL_BYTES) as reader:
            if format_name == "directory":
                manifest = c.parse(reader.read(candidate + "/bundle/bundle.json"))
            else:
                with archive_member(project, candidate + "/" + filename, format_name, "bundle.json") as member:
                    manifest = c.parse(member.read(c.MAX_DOCUMENT+1))
            mappings = selected_mappings(chosen, manifest, domain)
            for mapping in mappings:
                existing = reader.read(mapping["destination"], optional=True)
                c.require(existing is None or c.sha256(existing) == mapping["sha256"],
                          "An authored asset collides with the receiver selection", "storage-author-conflict")
            c.require(c.sha256(reader.read("_config.yml")) == policy_sha, "Receiver policy changed during copy", "storage-revision-conflict")
        record = {"kind": "unaltraweb.retained-product", "schema_version": 1, "bundle_sha256": bundle_sha,
                  "format": format_name, "path": final_relative + "/" + filename, "policy_sha256": policy_sha,
                  "domain_profile": domain["domain_profile"], "domain_check_sha256": domain["evidence_sha256"], "mappings": mappings}
        if verification:
            record["archive_verification_id"] = verification["verification_id"]
        write_new(root, candidate + "/binding.json", c.canonical(record))
        write_new(root, candidate + "/domain-check.json", c.canonical({key: value for key, value in domain.items() if key != "evidence_sha256"}))
        if mappings and format_name == "directory":
            integration = {"schema_version": 1, "kind": "mcp-artifact-integration",
                           "integrator": {"name": "unaltraweb", "version": __version__, "revision": "sha256:"+bundles.VALIDATOR_SHA256, "runtimes": []},
                           "bundle": {"path": final_relative + "/bundle/bundle.json", "sha256": bundle_sha},
                           "mappings": [{key: item[key] for key in ("source", "destination")} for item in mappings]}
            write_new(root, candidate + "/integration.json", c.canonical(integration))
        for mapping in mappings:
            with Reader(project, max_bytes=handoff.MAX_FILE_BYTES, max_total_bytes=handoff.MAX_TOTAL_BYTES) as reader:
                existing = reader.read(mapping["destination"], optional=True)
            if existing is None:
                if format_name == "directory":
                    copy_new(root, project, candidate + "/bundle/" + mapping["source"], mapping["destination"], mapping["sha256"])
                else:
                    copy_archive_asset(root, project, candidate + "/" + filename, format_name, mapping)
            else:
                c.require(c.sha256(existing) == mapping["sha256"], "Authored asset changed before publication", "storage-author-conflict")
        parent = fs._open_directory(root, Path(parent_relative))
        try:
            c.require(not final.exists() and not final.is_symlink(), "Final destination changed", "storage-destination-conflict")
            rename_new(parent, Path(candidate).name, format_name)
            os.fsync(parent)
        finally:
            os.close(parent)
        witness = {"receiver_binding_id": receiver_id, "receiver_host_root": manager.origin.host_project,
                   "receiver_root_identity": {"device": project.stat().st_dev, "inode": project.stat().st_ino},
                   "binding_path": final_relative + "/binding.json", "format": format_name, "path": record["path"],
                   "content_sha256": content_sha, "bundle_sha256": bundle_sha, "policy_sha256": policy_sha}
        if verification:
            witness["archive_verification_id"] = verification["verification_id"]
        verified = verify_record(manager, witness)
        result = acknowledge(manager, root, witness, verified, registry_id, job_id, product_id)
        return {**result, "export_check": transferred["export_check"], "verification_job": verification, "reused": False}


def verify_record(manager, witness, registry=None):
    project = manager.origin.project
    durable_binding(manager)
    c.require(witness["receiver_host_root"] == manager.origin.host_project and witness["receiver_root_identity"] == {
        "device": project.stat().st_dev, "inode": project.stat().st_ino}, "Receiver binding changed", "storage-destination-not-durable")
    chosen, policy_sha = policy(project)
    c.require(policy_sha == witness["policy_sha256"], "Receiver policy is stale", "storage-retention-stale")
    base = chosen["root"] + "/" + witness["bundle_sha256"] + "/" + witness["format"]
    filename = "bundle" if witness["format"] == "directory" else "bundle.zip" if witness["format"] == "zip" else "bundle.tar.gz"
    c.require(witness["format"] == chosen["format"] and witness["path"] == base + "/" + filename
              and witness["binding_path"] == base + "/binding.json",
              "Retention witness is outside its explicit durable policy", "storage-destination-not-durable")
    with Reader(project, max_bytes=handoff.MAX_FILE_BYTES, max_total_bytes=handoff.MAX_TOTAL_BYTES) as reader:
        binding = c.parse(reader.read(witness["binding_path"]))
        c.require(binding.get("kind") == "unaltraweb.retained-product" and type(binding.get("schema_version")) is int and binding["schema_version"] == 1
                  and binding["bundle_sha256"] == witness["bundle_sha256"] and binding["format"] == witness["format"]
                  and binding["path"] == witness["path"] and binding["policy_sha256"] == policy_sha,
                  "Retained binding differs from witness", "storage-retention-stale")
        c.require(binding["domain_profile"] in chosen["profiles"], "Retained profile is no longer selected", "storage-retention-stale")
        if witness["format"] == "directory":
            domain = bundles.check(project, witness["path"] + "/bundle.json", witness["bundle_sha256"])
            manifest = c.parse(reader.read(witness["path"] + "/bundle.json"))
        else:
            if registry is None:
                with manager.registry.locked() as locked:
                    return verify_record(manager, witness, registry=locked)
            identifier = witness.get("archive_verification_id")
            c.require(isinstance(identifier, str) and c.ID_RE.fullmatch(identifier) is not None, "No manager-observed archive verification", "storage-retention-stale")
            verified = registry.read("verifications/" + identifier + ".json")
            c.require(verified.get("binding_id") == manager._binding(registry)["id"]
                      and verified.get("bundle_sha256") == witness["bundle_sha256"] and verified.get("archive_sha256") == witness["content_sha256"]
                      and verified.get("format") == witness["format"] and verified["domain_report"]["validator_sha256"] == bundles.VALIDATOR_SHA256,
                      "Archive evidence is not current manager authority", "storage-retention-stale")
            workspace = handoff.Workspace(str(project))
            try:
                current_sha, size, _ = workspace.read(witness["path"], handoff.MAX_TOTAL_BYTES + c.MAX_DOCUMENT)
                c.require(current_sha == witness["content_sha256"] and size == verified["archive_bytes"], "Retained archive bytes changed", "storage-retention-stale")
            finally:
                workspace.close()
            domain = verified["domain_report"]
            with archive_member(project, witness["path"], witness["format"], "bundle.json") as member:
                manifest = c.parse(member.read(c.MAX_DOCUMENT+1))
        c.require(c.sha256(reader.read(base + "/domain-check.json")) == binding["domain_check_sha256"], "Retained domain evidence changed", "storage-retention-stale")
        c.require(binding["mappings"] == selected_mappings(chosen, manifest, domain), "Native mapping differs from the receiver policy", "storage-retention-stale")
        for mapping in binding["mappings"]:
            c.require(c.sha256(reader.read(mapping["destination"])) == mapping["sha256"], "An exposed authored asset changed", "storage-retention-stale")
        if witness.get("envelope_path"):
            c.require(c.sha256(reader.read(witness["envelope_path"])) == witness["envelope_sha256"], "Retention envelope changed", "storage-retention-stale")
    return domain
