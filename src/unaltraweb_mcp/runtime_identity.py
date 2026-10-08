"""Identity and cooperative lifetime of the process serving one MCP connection."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import threading
import uuid

from . import __version__
from .distribution import distribution_contract
from . import runtime_lifecycle as lifecycle

REQUIREMENTS_REVISION = "5634ea2e3e42122bb365992dfca9f248feb89dec"
PROFILE = {"name": "unaltraweb-docker-stdio-v1", "identity_schema": 1,
           "requirements_revision": REQUIREMENTS_REVISION, "connections_per_backend": 1,
           "operation_concurrency": 1, "shutdown": "drain-then-close-stdio",
           "admitted_operation_bound": 16,
           "preview_scope": "session", "disk_cleanup": "separate-explicit-operation",
           "container_limits": {"controller": {"cpus": 2, "memory_mib": 4096, "pids": 512},
                                "preview": {"cpus": 2, "memory_mib": 2048, "pids": 256},
                                "manual_pdf": {"cpus": 2, "memory_mib": 2048, "pids": 256},
                                "web_capture": {"cpus": 2, "memory_mib": 2048, "pids": 256},
                                "computation": {"cpus": 4, "memory_mib": 8192, "pids": 512}},
           "worker_timeout_seconds": {"manual_pdf": 1800, "web_capture": 900, "computation": 1800},
           "timeout_scope": "per bounded worker invocation; a request may compose several jobs"}
WORKER_ENV = {"manual_pdf": "MANUAL_PDF_IMAGE", "web_capture": "WEB_CAPTURE_IMAGE",
              "compute_python": "COMPUTE_PYTHON_IMAGE", "compute_r": "COMPUTE_R_IMAGE"}
_ACTIVE = None


def active_runtime():
    return _ACTIVE


def install_runtime(runtime):
    global _ACTIVE
    _ACTIVE = runtime


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def code_bytes(path, *, directory_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 2 * 1024 * 1024:
            raise ValueError("Unverifiable package member")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        after = os.stat(path, dir_fd=directory_fd, follow_symlinks=False)
        signature = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if len(data) > 2 * 1024 * 1024 or signature(before) != signature(os.fstat(fd)) or signature(before) != signature(after):
            raise ValueError("Package member changed during observation")
        return data
    finally:
        os.close(fd)


def fingerprint(root, expected_root=None):
    """Only bounded package code/contracts; never traverse consumer content."""
    directory = None
    storage_directory = None
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        before = os.fstat(directory)
        if expected_root and (before.st_dev, before.st_ino) != expected_root:
            raise ValueError("Package root was replaced")
        files = sorted(name for name in os.listdir(directory) if Path(name).suffix in {".py", ".json"})
        if "job_storage" in os.listdir(directory):
            storage_directory = os.open("job_storage", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            storage_before = os.fstat(storage_directory)
            files.extend("job_storage/" + name for name in sorted(os.listdir(storage_directory)) if Path(name).suffix in {".py", ".json"})
        if not 1 <= len(files) <= 128:
            raise ValueError("Package inventory exceeds bounds")
        hashes = {}
        total = 0
        metadata_version = None
        for path in files:
            if path.startswith("job_storage/"):
                data = code_bytes(path.removeprefix("job_storage/"), directory_fd=storage_directory)
            else:
                data = code_bytes(path, directory_fd=directory)
            total += len(data)
            if total > 16 * 1024 * 1024:
                raise ValueError("Package exceeds observation bounds")
            hashes[path] = hashlib.sha256(data).hexdigest()
            if path == "component-contract.json":
                try:
                    value = json.loads(data)["release"]["version"]
                    if isinstance(value, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]{0,40}", value):
                        metadata_version = value
                except (ValueError, KeyError, TypeError, RecursionError):
                    pass
        after = root.lstat()
        if (after.st_dev, after.st_ino, after.st_mtime_ns) != (before.st_dev, before.st_ino, before.st_mtime_ns):
            raise ValueError("Package root changed during inspection")
        if storage_directory is not None:
            after_storage = os.stat("job_storage", dir_fd=directory, follow_symlinks=False)
            if (after_storage.st_dev, after_storage.st_ino, after_storage.st_mtime_ns) != (storage_before.st_dev, storage_before.st_ino, storage_before.st_mtime_ns):
                raise ValueError("Storage package changed during inspection")
        return {"available": True, "sha256": hashlib.sha256(canonical(hashes)).hexdigest(), "files": hashes, "metadata_version": metadata_version}
    except (OSError, ValueError):
        return {"available": False, "sha256": None, "reason": "Package bytes cannot be observed safely"}
    finally:
        if storage_directory is not None:
            os.close(storage_directory)
        if directory is not None:
            os.close(directory)


def process_start():
    result = {"pid": os.getpid(), "pid_namespace": None, "start_ticks": None}
    try:
        result["pid_namespace"] = os.readlink("/proc/self/ns/pid")
        result["start_ticks"] = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        pass
    return result


class RuntimeIdentity:
    def __init__(self, project, factory, *, environment=None, package_root=None):
        values = os.environ if environment is None else environment
        keys = {"UNALTRAWEB_DOCKER_ROOT", "UNALTRAWEB_RUNTIME_SESSION", "UNALTRAWEB_MANAGED_RUNTIME",
                "UNALTRAWEB_MCP_REQUESTED_IMAGE", "UNALTRAWEB_MCP_IMAGE_REFERENCE", "UNALTRAWEB_MCP_IMAGE",
                "UNALTRAWEB_EXPECTED_IMAGE_ID", "UNALTRAWEB_WORKER_IMAGES", "UNALTRAWEB_LAUNCHER_PROJECT", "UNALTRAWEB_RUNTIME_NETWORK",
                "UNALTRAWEB_JOB_STORAGE_STATE", "UNALTRAWEB_JOB_STORAGE_HOST_STATE", "UNALTRAWEB_JOB_STORAGE_ROOT_IDENTITY",
                "UNALTRAWEB_JOB_STORAGE_IMAGE", *WORKER_ENV.values()}
        self.env = {key: values[key] for key in keys if key in values}
        self.project = Path(project).resolve()
        self.factory = Path(factory).resolve()
        self.package_root = package_root or Path(__file__).resolve().parent
        root_info = self.package_root.stat()
        self.package_root_identity = (root_info.st_dev, root_info.st_ino)
        self.host_project = self.env.get("UNALTRAWEB_DOCKER_ROOT") or str(self.project)
        if not Path(self.host_project).is_absolute() or any(c in self.host_project for c in "\r\n"):
            raise ValueError("Invalid startup host workspace binding")
        self.project_id = hashlib.sha256(self.host_project.encode()).hexdigest()[:16]
        self.session_id = self.env.get("UNALTRAWEB_RUNTIME_SESSION", "")
        if self.session_id and not lifecycle.SESSION_ID.fullmatch(self.session_id):
            raise ValueError("Invalid startup session ID")
        self.container_name = f"unaltraweb-stdio-{self.session_id}" if self.session_id else ""
        self.managed = self.env.get("UNALTRAWEB_MANAGED_RUNTIME") == "1"
        self.instance_id = uuid.uuid4().hex
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.process = process_start()
        self.executable = sys.executable
        self.python = platform.python_version()
        self.loaded_version = __version__
        self.startup_package = fingerprint(self.package_root)
        self.contract = distribution_contract()
        self.contract_hash = hashlib.sha256(canonical(self.contract)).hexdigest()
        self.profile_hash = hashlib.sha256(canonical(PROFILE)).hexdigest()
        self.requested_image = self.env.get("UNALTRAWEB_MCP_REQUESTED_IMAGE") or self.env.get("UNALTRAWEB_MCP_IMAGE_REFERENCE", "")
        self.selected_image = self.env.get("UNALTRAWEB_MCP_IMAGE", "")
        self.expected_image = self.env.get("UNALTRAWEB_EXPECTED_IMAGE_ID", "")
        self.workers = {key: {"reference": self.env.get(variable) or self.contract["components"][key]["reference"], "expected_image_id": ""}
                        for key, variable in WORKER_ENV.items()}
        raw_overrides = self.env.get("UNALTRAWEB_WORKER_IMAGES", "{}")
        if len(raw_overrides) > 8192:
            raise ValueError("Worker selection metadata exceeds its bound")
        def unique(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError("Duplicate worker selection key")
                value[key] = item
            return value
        overrides = json.loads(raw_overrides, object_pairs_hook=unique)
        if not isinstance(overrides, dict) or not overrides.keys() <= self.workers.keys():
            raise ValueError("Worker selections must name only supported workers")
        for key, value in overrides.items():
            if not isinstance(value, dict) or set(value) != {"reference", "expected_image_id"}:
                raise ValueError("Worker selection requires a reference and exact expected image ID")
            if not isinstance(value["expected_image_id"], str) or not lifecycle.IMAGE_ID.fullmatch(value["expected_image_id"]):
                raise ValueError("Explicit worker selection requires a full expected image ID")
            self.workers[key] = dict(value)
        for value in self.workers.values():
            lifecycle.image_reference(value["reference"])
            if value["expected_image_id"] and not lifecycle.IMAGE_ID.fullmatch(value["expected_image_id"]):
                raise ValueError("Invalid expected worker image ID")
            if self.managed and not (lifecycle.immutable_reference(value["reference"]) or value["expected_image_id"]):
                raise ValueError("Managed worker selection requires an immutable reference or expected image ID")
        self.selection_hash = hashlib.sha256(canonical({"image": self.selected_image, "requested": self.requested_image,
            "expected": self.expected_image, "workers": self.workers, "project": str(self.project), "host_project": self.host_project})).hexdigest()
        self.lock = threading.RLock()
        self.operation = None
        self.admitted = 0
        self.draining = False
        self.closed = False
        self.resources = set()
        self.networks = set()
        self.storage_jobs = set()
        self.storage_release = None

    @contextmanager
    def admit(self, *, allow_draining=False):
        with self.lock:
            if self.closed or (self.draining and not allow_draining):
                raise RuntimeError("This MCP instance is draining; reconnect before starting new work")
            if self.admitted >= 16:
                raise RuntimeError("This MCP instance is busy; the bounded operation queue is full")
            self.admitted += 1
        try:
            yield
        finally:
            with self.lock:
                self.admitted -= 1

    @contextmanager
    def job(self, name):
        with self.lock:
            if self.draining or self.closed:
                raise RuntimeError("This MCP instance is draining; reconnect before starting new work")
            if self.operation:
                raise RuntimeError("This MCP instance is busy; operation concurrency is bounded to one")
            if self.managed and str(self.project) != self.host_project:
                raise RuntimeError("Managed workers require the verified canonical host-path mirror; this controller mapping is unsupported")
            self.operation = {"id": uuid.uuid4().hex, "name": name, "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            yield
        finally:
            with self.lock:
                self.operation = None

    def drain(self, confirm=False):
        if not confirm:
            return {"ok": False, "error": "Draining requires confirm=true", "scope": "connection"}
        with self.lock:
            self.draining = True
            return {"ok": True, "scope": "connection", "state": "draining", "instance_id": self.instance_id,
                    "session_id": self.session_id or None, "active_operations": max(self.admitted, int(self.operation is not None)),
                    "resources_released": False, "next": "Close this stdio connection; wait for the exact container and owned jobs to terminate."}

    def register_resource(self, container_id):
        if not lifecycle.CONTAINER_ID.fullmatch(container_id):
            raise RuntimeError("Cannot retain an invalid resource identity")
        with self.lock:
            self.resources.add(container_id)

    def register_network(self, network_id):
        if not lifecycle.CONTAINER_ID.fullmatch(network_id):
            raise RuntimeError("Cannot retain an invalid network identity")
        with self.lock:
            self.networks.add(network_id)

    def register_storage(self, registry_id, job_id):
        if not all(isinstance(value, str) and lifecycle.SESSION_ID.fullmatch(value) for value in (registry_id, job_id)):
            raise RuntimeError("Cannot track invalid storage identities")
        with self.lock:
            if len(self.storage_jobs) >= 64 and (registry_id, job_id) not in self.storage_jobs:
                raise RuntimeError("Connection storage history reached its bound")
            self.storage_jobs.add((registry_id, job_id))

    def close(self):
        with self.lock:
            self.draining = True
            if self.operation or self.admitted:
                raise RuntimeError("Cannot release resources while an operation remains active")
        if self.storage_jobs:
            from .job_storage.manager import Manager
            self.storage_release = Manager(self.project).toggle_off(sorted(self.storage_jobs))
        for cid in sorted(self.resources):
            lifecycle.remove_idle_container(cid, self.project_id, self.session_id)
        for nid in sorted(self.networks):
            lifecycle.remove_idle_network(nid, self.project_id, self.session_id)
        self.closed = True

    def worker(self, key):
        selected = self.workers[key]
        observed = lifecycle.inspect_image(selected["reference"], selected["expected_image_id"])
        if observed["state"] != "matched":
            raise RuntimeError(f"Selected {key} image is {observed['state']}; prepare that exact worker explicitly")
        return observed["observed_image_id"]

    def observe(self):
        current = fingerprint(self.package_root, self.package_root_identity)
        diagnostics = []
        drift = None
        if self.startup_package["available"] and current["available"]:
            drift = current["sha256"] != self.startup_package["sha256"]
            if drift:
                diagnostics.append("package-bytes-changed-since-startup")
        else:
            diagnostics.append("package-observation-unavailable")
        current_version = current.get("metadata_version")
        if current_version is None:
            diagnostics.append("current-version-unavailable")
        container = {"state": "unavailable", "namespace": "docker-daemon"}
        if self.container_name:
            try:
                info = lifecycle.inspect_container(self.container_name)
                if info is None or not lifecycle.owned(info, self.project_id, self.session_id, {"stdio"}):
                    raise RuntimeError("Serving container ownership cannot be correlated")
                matches = info["image_id"] == self.selected_image and (not self.expected_image or info["image_id"] == self.expected_image)
                mounts = [{"source": m.get("Source"), "destination": m.get("Destination")} for m in info.get("mounts", [])
                          if m.get("Destination") in {str(self.project), "/workspace"}]
                matches = matches and any(m["source"] == self.host_project and m["destination"] == str(self.project) for m in mounts)
                if self.managed:
                    matches = matches and info.get("memory_bytes") == 4096 * 1024 * 1024 and info.get("nano_cpus") == 2_000_000_000 and info.get("pids_limit") == 512
                container = {"state": "matched" if matches else "mismatch", "id": info["id"], "image_id": info["image_id"],
                             "daemon_init_pid": info["daemon_init_pid"], "pid_namespace": "docker-daemon-host", "mounts": mounts,
                             "source_revision": info.get("source_revision"), "network_mode": info.get("network_mode"),
                             "limits": {"memory_bytes": info.get("memory_bytes"), "nano_cpus": info.get("nano_cpus"), "pids_limit": info.get("pids_limit")}}
                if not matches:
                    diagnostics.append("container-image-or-binding-mismatch")
            except (OSError, ValueError, RuntimeError, KeyError, TypeError):
                diagnostics.append("serving-container-observation-unavailable")
        workers = {key: lifecycle.inspect_image(value["reference"], value["expected_image_id"]) for key, value in self.workers.items()}
        helpers = {name: {"version": self.contract["components"][name]["version"], "reference": self.contract["components"][name]["reference"],
                          "live_observation": "requires the separate serving helper connection"} for name in ("diavisuals", "vegavisuals")}
        if helpers["diavisuals"]["version"] == "0.5.0":
            helpers["diavisuals"]["d0_blocker"] = "Published 0.5.0 lacks full live process identity; owner issue diavisuals#14 remains required"
        with self.lock:
            state = "stopped" if self.closed else "draining" if self.draining else "busy" if self.operation else "connected"
            operation = dict(self.operation) if self.operation else None
            queued = self.admitted - int(self.operation is not None) if self.admitted else 0
        return {"ok": True, "schema_version": 1, "factory": "unaltraweb", "component": "mcp", "observation": "live-serving-process",
                "instance_id": self.instance_id, "session_id": self.session_id or None, "started_at": self.started_at,
                "process": {**self.process, "executable": self.executable, "python": self.python},
                "package": {"root": str(self.package_root), "loaded_version": self.loaded_version,
                            "loaded_revision": "sha256:" + self.startup_package["sha256"] if self.startup_package["sha256"] else None,
                            "mode": "installed" if "site-packages" in str(self.package_root) or "dist-packages" in str(self.package_root) else "development",
                            "startup": self.startup_package, "current": current, "current_version": current_version, "drift": drift},
                "binding": {"consumer": str(self.project), "effective_project": str(self.project), "daemon_host_project": self.host_project,
                            "launcher_project": self.env.get("UNALTRAWEB_LAUNCHER_PROJECT", str(self.project)), "project_id": self.project_id},
                "runtime": {"requested_reference": self.requested_image or None, "selected_image_id": self.selected_image or None,
                            "selected_reference": self.env.get("UNALTRAWEB_MCP_IMAGE_REFERENCE") or None,
                            "expected_image_id": self.expected_image or None, "container": container, "workers": workers},
                "helpers": helpers,
                "coordinator_closure": "not attested by this process; compose the independent helper observations",
                "contract": {"requirements_revision": REQUIREMENTS_REVISION, "component_contract_sha256": self.contract_hash,
                             "profile": PROFILE, "profile_sha256": self.profile_hash, "selection_sha256": self.selection_hash},
                "lifecycle": {"state": state, "scope": "connection", "active_operation": operation,
                              "queued_operations": queued, "admitted_operation_bound": 16,
                              "operation_concurrency": 1, "idle_expiry": "stdio EOF after active work drains", "resources_released": False,
                              "storage_jobs": [{"registry_id": registry, "job_id": job} for registry, job in sorted(self.storage_jobs)],
                              "storage_release": self.storage_release},
                "managed": self.managed, "diagnostics": diagnostics,
                "note": "Bounded observation, not permanent attestation. Host/container PIDs occupy distinct namespaces; helpers are separate processes."}
