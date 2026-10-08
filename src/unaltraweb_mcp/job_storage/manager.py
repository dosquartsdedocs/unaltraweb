"""Standalone manager authority for this provider's explicitly owned registry.

The common hook returns W1 state. Native manager operations own allocation,
leases, live observations and retirement; a reference plan is never executed by
assuming caller-supplied observations or acknowledgements are authoritative.
"""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tarfile
import uuid

from .. import runtime_identity
from .. import artifact_handoff_v1 as handoff
from .. import __version__
from ..distribution import component_reference
from . import contract as c
from .docker import Docker, docker_time
from .registry import Registry, identity

CLI_INSTANCE = uuid.uuid4().hex


def provider():
    raw = Path(__file__).with_name("provider.json").read_bytes()
    return c.validate(c.parse(raw)), c.sha256(raw), raw


def effective_limits(declaration, stricter=None):
    limits = dict(declaration["limits"])
    if stricter:
        c.require(isinstance(stricter, dict) and stricter.keys() <= limits.keys(), "Unsupported storage limit override")
        for key, value in stricter.items():
            if key == "quota_enforcement":
                c.require(value == "monitored", "Hard filesystem quotas are not available in the standard local-volume profile", "storage-quota-unsupported")
            else:
                c.require(type(value) is int and (value >= limits[key] if key == "min_free_bytes" else 1 <= value <= limits[key]),
                          "Storage policy may only tighten the provider limits", "storage-budget-invalid")
            limits[key] = value
    c.shape(limits, c.schema()["$defs"]["limits"], c.schema()["$defs"])
    return limits


@dataclass(frozen=True)
class Origin:
    project: Path
    host_project: str
    client_id: str
    session_id: str
    process: dict
    container_id: str | None

    @classmethod
    def selected(cls, project):
        project = Path(project).resolve(strict=True)
        active = runtime_identity.active_runtime()
        if active is not None:
            c.require(project == active.project, "Operation differs from the startup-selected consumer", "storage-binding-mismatch")
            observed = active.observe()
            c.require(observed["package"]["drift"] is False, "Reconnect after package code changes", "storage-code-drift")
            container = observed["runtime"]["container"]
            if active.container_name:
                c.require(container.get("state") == "matched", "The serving container binding is not verified", "storage-observation-unknown")
            process = dict(active.process)
            process["daemon_init_pid"] = container.get("daemon_init_pid")
            process["image_id"] = container.get("image_id")
            process["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            return cls(project, active.host_project, active.instance_id, active.session_id, process, container.get("id"))
        process = runtime_identity.process_start()
        process["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return cls(project, os.environ.get("UNALTRAWEB_DOCKER_ROOT") or str(project), CLI_INSTANCE,
                   os.environ.get("UNALTRAWEB_RUNTIME_SESSION", ""), process, None)

    def key(self):
        return c.sha256(c.canonical({"host_project": self.host_project, "root_identity": identity(self.project.stat())}))

    def evidence(self):
        return {"client_id": self.client_id, "session_id": self.session_id, "process": self.process,
                "container_id": self.container_id, "host_project": self.host_project,
                "controller_project": str(self.project), "root_identity": identity(self.project.stat())}


class Manager:
    def __init__(self, project, *, state_root=None, utility_image=None, docker=None):
        self.origin = Origin.selected(project)
        self.docker = docker or Docker()
        active = runtime_identity.active_runtime()
        default_state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "unaltraweb/job-storage-v1"
        if active is not None:
            selected_state = active.env.get("UNALTRAWEB_JOB_STORAGE_STATE")
            c.require(selected_state, "Reconnect with the native persistent storage registry selected by the launcher", "storage-registry-not-configured")
            c.require(state_root is None or Path(state_root) == Path(selected_state), "Runtime registry override differs from startup", "storage-binding-mismatch")
            state_root = Path(selected_state)
            if active.container_name:
                observed = self.docker.inspect("container", self.origin.container_id)
                host_state = active.env.get("UNALTRAWEB_JOB_STORAGE_HOST_STATE")
                c.require(observed is not None and any(m.get("Type") == "bind" and m.get("Source") == host_state
                          and m.get("Destination") == selected_state and m.get("RW") is True for m in observed["mounts"]),
                          "Persistent registry has no verified startup bind mount", "storage-binding-mismatch")
                metadata = state_root.stat()
                c.require(active.env.get("UNALTRAWEB_JOB_STORAGE_ROOT_IDENTITY") == f"{metadata.st_dev}:{metadata.st_ino}",
                          "Persistent registry mount differs from the launcher observation", "storage-binding-mismatch")
        self.registry = Registry(Path(state_root or os.environ.get("UNALTRAWEB_JOB_STORAGE_STATE") or default_state))
        c.require(not self.registry.root.is_relative_to(self.origin.project), "Private registry must be outside the consumer", "storage-registry-unsafe")
        self.declaration, self.declaration_sha, self.declaration_bytes = provider()
        self.utility_reference = utility_image or (active.env if active else os.environ).get("UNALTRAWEB_JOB_STORAGE_IMAGE") or (
            active.selected_image if active is not None and active.selected_image else component_reference("mcp"))

    def _binding(self, registry, create=False):
        key = self.origin.key()
        binding = registry.record["bindings"].get(key)
        if binding is None:
            c.require(create, "No manager binding for this selected consumer", "storage-binding-mismatch")
            binding = {"id": uuid.uuid4().hex, "host_project": self.origin.host_project,
                       "root_identity": identity(self.origin.project.stat())}
            registry.record["bindings"][key] = binding
            registry.save_registry()
        c.require(binding["host_project"] == self.origin.host_project
                  and binding["root_identity"] == identity(self.origin.project.stat()),
                  "Selected consumer identity changed", "storage-binding-mismatch")
        return binding

    def _job(self, registry, job_id, registry_id=None):
        c.require(isinstance(job_id, str) and c.ID_RE.fullmatch(job_id) is not None, "Invalid job identifier")
        c.require(registry_id in {None, registry.record["id"]}, "Job belongs to another registry", "storage-binding-mismatch")
        job = registry.read("jobs/" + job_id + ".json")
        binding = self._binding(registry)
        c.require(job.get("binding_id") == binding["id"] and job.get("registry_id") == registry.record["id"]
                  and job.get("job_id") == job_id and job.get("provider") == "unaltraweb",
                  "Job is not authorized for the selected consumer", "storage-binding-mismatch")
        return job

    def _save(self, registry, job, *, initial=False):
        if not initial:
            job["revision"] += 1
        registry.write("jobs/" + job["job_id"] + ".json", job, create_only=initial)

    def _track_interest(self, job):
        active = runtime_identity.active_runtime()
        if active is not None:
            active.register_storage(job["registry_id"], job["job_id"])

    def _worker_labels(self, registry_id, *, job=None, lease_id=None):
        labels = {"io.context.mcp-factory": "unaltraweb", "io.context.mcp-role": "job-storage",
                  "io.context.mcp-project": hashlib.sha256(self.origin.host_project.encode()).hexdigest()[:16],
                  "io.context.mcp-storage.registry": registry_id}
        if self.origin.session_id:
            labels["io.context.mcp-session"] = self.origin.session_id
        if job is not None:
            labels.update({"io.context.mcp-storage.contract": c.CONTRACT, "io.context.mcp-storage.provider": "unaltraweb",
                           "io.context.mcp-storage.binding": job["binding_id"], "io.context.mcp-storage.job": job["job_id"]})
        if lease_id:
            labels["io.context.mcp-storage.lease"] = lease_id
            labels["io.context.mcp-worker-token"] = lease_id[:16]
        return labels

    def _control_worker(self, registry, request, mounts, *, job=None, role="maintenance"):
        """Short manager-owned operation under the registry admission lock."""
        operation_id = uuid.uuid4().hex
        guard = registry.acquire_guard(operation_id)
        record = {"id": operation_id, "role": role, "kind": "reader" if request["operation"] in {"observe", "capacity"} else "writer",
                  "client": self.origin.evidence(), "container_id": None,
                  "container_name": "unaltraweb-w1-" + operation_id, "phase": "creating", "job_id": job["job_id"] if job else None}
        if job is not None:
            job.setdefault("operations", []).append(record)
            self._save(registry, job)
        else:
            registry.write("operations/" + operation_id + ".json", record, create_only=True)
        labels = self._worker_labels(registry.record["id"], job=job, lease_id=operation_id)
        try:
            image = self.docker.prepared_image(self.utility_reference)["id"]
            if job is not None and request["operation"] == "seal":
                request = {**request, "binding": self._mount_binding(job, operation_id)}
                c.check_binding(request["binding"], self._state(registry, job))
            identifier = self.docker.create_worker(name=record["container_name"], image_id=image,
                                                   request=request, mounts=mounts, labels=labels, guard_fds=(guard,))
            record.update(container_id=identifier, phase="running", image_id=image)
            if job is not None:
                self._save(registry, job)
            else:
                registry.write("operations/" + operation_id + ".json", record)
            result = self.docker.start_worker(identifier, guard_fds=(guard,), timeout=120)
            observed = self.docker.inspect("container", identifier)
            c.require(observed is not None and not observed["running"], "Manager worker did not terminate", "storage-busy")
            c.require(not result.returncode and observed["exit_code"] == 0 and not result.timed_out
                      and not result.stdout_truncated and not result.stderr_truncated,
                      "Manager worker failed; its operation and volumes are retained: " + result.stderr[-1500:], "storage-observation-unknown")
            value = c.parse(result.stdout.encode())
            self.docker.remove_stopped_container(identifier, labels)
            record.update(phase="completed", result_sha256=c.sha256(c.canonical(value)), completed_at=c.now())
            if job is not None:
                self._save(registry, job)
            else:
                registry.write("operations/" + operation_id + ".json", record)
            return value
        finally:
            os.close(guard)

    def _capacity(self, registry):
        probe = registry.record.get("capacity_probe")
        if probe is None:
            probe = {"name": "unaltraweb-storage-capacity-" + uuid.uuid4().hex, "native": None, "marker": None, "phase": "allocating"}
            registry.record["capacity_probe"] = probe
            registry.save_registry()
            labels = {"io.context.mcp-factory": "unaltraweb", "io.context.mcp-role": "storage-capacity",
                      "io.context.mcp-storage.registry": registry.record["id"]}
            probe["native"] = self.docker.create_volume(probe["name"], labels)
            document = {"kind": "unaltraweb.storage-capacity-marker", "registry_id": registry.record["id"],
                        "daemon_id": registry.record["daemon_id"], "volume": probe["native"], "nonce": uuid.uuid4().hex}
            probe["marker"] = {"document": document, "sha256": c.sha256(c.canonical(document))}
            probe["phase"] = "initializing"
            registry.save_registry()
            value = self._control_worker(registry, {"operation": "capacity-init", "marker": probe["marker"]},
                                         [(probe["name"], "/capacity", False)], role="capacity-init")
            probe["phase"] = "ready"
            registry.save_registry()
            return value
        c.require(probe.get("phase") == "ready", "Capacity preparation is incomplete; preserve and inspect its journal", "storage-allocation-incomplete")
        c.require(self.docker.verify_volume(probe["native"]) is not None, "Capacity volume is missing", "storage-observation-unknown")
        return self._control_worker(registry, {"operation": "capacity", "marker": probe["marker"]},
                                    [(probe["name"], "/capacity", True)], role="capacity-observation")

    def begin(self, kind, *, limits=None):
        c.require(kind in {"site-build", "manual-pdf", "practice-pdf", "web-capture", "compute-python", "compute-r", "preview", "reception"},
                  "Unsupported native job kind")
        effective = effective_limits(self.declaration, limits)
        self.docker.prepared_image(self.utility_reference)
        daemon_id = self.docker.daemon()
        with self.registry.locked(write=True, create=True, daemon_id=daemon_id) as registry:
            capacity = self._capacity(registry)
            outstanding = [registry.read("jobs/" + identifier + ".json") for identifier in registry.record["jobs"]]
            active = [job for job in outstanding if job.get("phase") != "released"]
            job_ceiling = min([effective["max_jobs"], *(job["limits"]["max_jobs"] for job in active)])
            c.require(len(active) < job_ceiling, "Concurrent retained/job budget is exhausted", "storage-budget-exceeded")
            reserved = sum(sum(job["limits"]["max_"+role+"_bytes"] for role in ("scratch", "retained")
                               if job.get("volumes", {}).get(role, {}).get("state") != "absent") for job in active)
            requested = effective["max_scratch_bytes"] + effective["max_retained_bytes"]
            c.require(capacity["free_bytes"] >= effective["min_free_bytes"] + reserved + requested,
                      "Observed Docker filesystem capacity cannot cover outstanding reservations", "storage-budget-exceeded")
            binding = self._binding(registry, create=True)
            descriptor_path = "descriptors/" + self.declaration_sha + ".json"
            existing = registry.read_bytes(descriptor_path, optional=True)
            if existing is None:
                registry.write_bytes(descriptor_path, self.declaration_bytes, create_only=True)
            else:
                c.require(existing == self.declaration_bytes, "Stored declaration changed", "storage-registry-unsafe")
            job_id = uuid.uuid4().hex
            job = {"registry_id": registry.record["id"], "job_id": job_id, "binding_id": binding["id"],
                   "provider": "unaltraweb", "provider_sha256": self.declaration_sha, "daemon_id": daemon_id,
                   "revision": 1, "epoch": 1, "phase": "open", "allocation": "allocating", "kind": kind,
                   "origin": self.origin.evidence(), "limits": effective, "volumes": {}, "leases": [], "products": [],
                   "holds": [], "observation": None, "operations": [], "created_at": c.now()}
            self._save(registry, job, initial=True)
            registry.record["jobs"].append(job_id)
            registry.save_registry()
            for role in ("retained", "scratch"):
                volume_id = uuid.uuid4().hex
                record = {"id": volume_id, "name": "gacontext-job-" + volume_id, "role": role, "state": "allocating", "native": None}
                job["volumes"][role] = record
                self._save(registry, job)
                labels = c.labels(job, record)
                native = self.docker.create_volume(record["name"], labels)
                document = {"kind": "unaltraweb.job-volume-marker", "schema_version": 1,
                            **{key: job[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id")},
                            "contract": c.CONTRACT, "volume_id": volume_id, "role": role,
                            "created_at": native["created_at"], "nonce": uuid.uuid4().hex}
                record.update(native=native, marker={"document": document, "sha256": c.sha256(c.canonical(document))}, state="initializing")
                self._save(registry, job)
            request = {"operation": "initialize", "markers": {role: value["marker"] for role, value in job["volumes"].items()}, "limits": effective}
            mounts = [(job["volumes"]["retained"]["name"], "/work", False), (job["volumes"]["scratch"]["name"], "/work/scratch", False)]
            observation = self._control_worker(registry, request, mounts, job=job, role="job-initialize")
            for record in job["volumes"].values():
                record["state"] = "verified"
            job.update(allocation="ready", observation=observation)
            job["leases"].append({"id": uuid.uuid4().hex, "kind": "client", "state": "active", "client": self.origin.evidence(), "epoch": 1})
            self._save(registry, job)
            self._track_interest(job)
            return self._state(registry, job)

    def _state(self, registry, job):
        c.require(job.get("allocation") == "ready", "Job allocation is incomplete; preserve its volumes and journal", "storage-allocation-incomplete")
        self.docker.require_daemon(job["daemon_id"])
        observed_at = c.now()
        observation = job["observation"]
        volumes, activity = [], "idle"
        for role, record in job["volumes"].items():
            try:
                actual = self.docker.verify_volume(record["native"])
                attached = self.docker.attachments(record["name"]) if actual is not None else []
                volume_state = "absent" if actual is None else record["state"]
                complete = True
                if attached:
                    activity = "busy"
            except c.StorageError:
                attached, volume_state, complete, activity = [], "unknown", False, "unknown"
            metric = observation.get("metrics", {}).get(role, {})
            volumes.append({"id": record["id"], "name": record["name"], "role": role,
                            "daemon_id": job["daemon_id"], "driver": "local",
                            "created_at": docker_time(record["native"]["created_at"]),
                            "marker_sha256": record["marker"]["sha256"], "labels": record["native"]["labels"],
                            "state": volume_state, "observed_at": observed_at if volume_state == "absent" else observation["observed_at"],
                            "attachments_complete": complete, "attachments": [item["id"] for item in attached],
                            "bytes": 0 if volume_state == "absent" else metric.get("bytes")})
        leases = self._leases(registry, job)
        if any(item["state"] == "unknown" for item in leases):
            activity = "unknown"
        elif any(item["kind"] == "writer" and item["state"] == "active" for item in leases):
            activity = "busy"
        state = {"kind": "gacontext.job-storage-state", "schema_version": 1, "contract": c.CONTRACT,
                 **{key: job[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id", "revision", "epoch", "phase", "limits")},
                 "observed_at": observed_at, "activity": activity,
                 "leases_complete": all(item["state"] != "unknown" for item in leases), "leases": leases,
                 "volumes": volumes, "products": [{key: product[key] for key in ("id", "bundle_sha256", "disposition", "decision")} for product in job["products"]],
                 "holds": job["holds"], "protected_inventory": observation["protected_inventory"]}
        return c.validate(state)

    def status(self, registry_id, job_id):
        # No directory/lease creation, volume mount, probe or source read.
        with self.registry.locked() as registry:
            return self._state(registry, self._job(registry, job_id, registry_id))

    def _mount_binding(self, job, lease_id, access="read-write"):
        roles = {"retained", "scratch"} if access == "read-write" else {"retained"}
        binding = {"kind": "gacontext.job-storage-binding", "schema_version": 1,
                   **{key: job[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id", "epoch")},
                   "lease_id": lease_id, "access": access, "job_root": "/work",
                   "mounts": [{"id": value["id"], "name": value["name"], "role": role,
                               "marker_sha256": value["marker"]["sha256"]} for role, value in job["volumes"].items() if role in roles]}
        return c.validate(binding)

    def _perform_write(self, registry_id, job_id, expected_revision, expected_epoch, request_fields, *, image=None, input_chunks=None):
        prepared = self.docker.prepared_image(image or self.utility_reference)["id"]
        guard = None
        operation_id = uuid.uuid4().hex
        try:
            with self.registry.locked(write=True, wait_seconds=5) as registry:
                job = self._job(registry, job_id, registry_id)
                c.require((job["revision"], job["epoch"]) == (expected_revision, expected_epoch),
                          "Storage revision or epoch changed", "storage-revision-conflict")
                c.require(job["phase"] == "open", "New work is fenced", "storage-admission-closed")
                self._recover_gone(registry, job)
                existing = self._leases(registry, job)
                c.require(not any(lease["kind"] == "writer" and lease["state"] != "released" for lease in existing),
                          "Another writer still owns this job", "storage-busy")
                c.require(all(lease["state"] != "unknown" for lease in existing), "Job lease ownership is unknown", "storage-observation-unknown")
                c.require(len(existing) < 250, "Job lease history is bounded", "storage-budget-exceeded")
                if not any(lease["state"] == "active" and lease["client"]["client_id"] == self.origin.client_id for lease in job["leases"]):
                    job["leases"].append({"id": uuid.uuid4().hex, "kind": "client", "state": "active",
                                          "client": self.origin.evidence(), "epoch": job["epoch"]})
                for volume in job["volumes"].values():
                    c.require(self.docker.verify_volume(volume["native"]) is not None, "A required job volume is missing", "storage-volume-mismatch")
                guard = registry.acquire_guard(operation_id)
                operation = {"id": operation_id, "kind": "writer", "role": request_fields["operation"], "phase": "creating",
                             "client": self.origin.evidence(), "container_id": None, "container_name": "unaltraweb-w1-" + operation_id,
                             "image_id": prepared, "epoch": job["epoch"]}
                job["operations"].append(operation)
                self._save(registry, job)
                binding = self._mount_binding(job, operation_id)
                c.check_binding(binding, self._state(registry, job))
                request = {**request_fields, "binding": binding, "limits": job["limits"], "operation_id": operation_id,
                           "consumer": self.origin.host_project, "markers": {role: value["marker"] for role, value in job["volumes"].items()}}
                labels = self._worker_labels(registry_id, job=job, lease_id=operation_id)
                mounts = [(job["volumes"]["retained"]["name"], "/work", False), (job["volumes"]["scratch"]["name"], "/work/scratch", False)]
                identifier = self.docker.create_worker(name=operation["container_name"], image_id=prepared, request=request,
                                                       mounts=mounts, labels=labels, guard_fds=(guard,))
                operation.update(container_id=identifier, phase="running")
                self._save(registry, job)
                self._track_interest(job)
            # Long native work runs outside the registry lock. The lease guard is
            # inherited by the Docker command and the exact container is journalled.
            completed = self.docker.start_worker(identifier, guard_fds=(guard,), input_chunks=input_chunks,
                                                  timeout=request_fields.get("timeout_seconds", 1800) + 10)
            with self.registry.locked(write=True, wait_seconds=5) as registry:
                job = self._job(registry, job_id, registry_id)
                operation = next(item for item in job["operations"] if item["id"] == operation_id)
                observed = self.docker.inspect("container", identifier)
                c.require(observed is not None and not observed["running"], "Domain worker is still running", "storage-busy")
                lines = completed.stdout.strip().splitlines()
                report = c.parse(lines[-1].encode()) if lines and not completed.stdout_truncated else None
                self.docker.remove_stopped_container(identifier, labels)
                operation.update(phase="completed", completed_at=c.now(), exit_code=observed["exit_code"])
                job["observation"]["protected_inventory"] = {"state": "unknown", "tree_sha256": None, "unresolved_entries": 1}
                job["holds"] = [{"id": uuid.uuid5(uuid.UUID(job_id), "unsealed-result").hex, "reason": "unsealed-result"}]
                if isinstance(report, dict) and "protected_inventory" in report:
                    job["observation"] = report
                elif isinstance(report, dict) and "metrics" in report:
                    job["observation"].update(metrics=report["metrics"], observed_at=report["observed_at"])
                self._save(registry, job)
                c.require(not completed.returncode and not completed.timed_out and observed["exit_code"] == 0 and report is not None,
                          "Native work failed; its inputs/results remain retained: " + completed.stderr[-1500:], "storage-operation-incomplete")
                if report.get("pressure_or_timeout"):
                    job["phase"] = "draining"
                    self._save(registry, job)
                return {"report": report, "state": self._state(registry, job), "container_id": identifier}
        finally:
            if guard is not None:
                os.close(guard)

    def stage(self, registry_id, job_id, expected_revision, expected_epoch, paths, *, parameters=None):
        c.require(isinstance(paths, list) and len(paths) <= 10000 and all(isinstance(path, str) for path in paths), "Invalid selected input inventory")
        handoff.unique_paths(paths)
        entries = []
        workspace = handoff.Workspace(str(self.origin.project))
        try:
            for relative in sorted(paths):
                hashed, size, _ = workspace.read(relative, handoff.MAX_FILE_BYTES)
                entries.append({"path": "project/" + relative, "source": relative, "sha256": hashed, "bytes": size})
        finally:
            workspace.close()
        manifest = c.canonical({"kind": "unaltraweb.job-request", "schema_version": 1,
                                "parameters": parameters or {}, "inputs": entries})
        c.require(len(manifest) <= c.MAX_DOCUMENT, "Selected input manifest exceeds its bound")

        def chunks():
            info = tarfile.TarInfo("request.json")
            info.size, info.mode = len(manifest), 0o444
            yield info.tobuf(format=tarfile.PAX_FORMAT)
            for offset in range(0, len(manifest), 65536):
                yield manifest[offset:offset+65536]
            yield b"\0" * (-len(manifest) % 512)
            workspace = handoff.Workspace(str(self.origin.project))
            try:
                for entry in entries:
                    parent, _, name = entry["source"].rpartition("/")
                    with workspace.directory(parent) as parent_fd:
                        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
                        try:
                            before = os.fstat(fd)
                            c.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == entry["bytes"],
                                      "Selected input changed", "storage-input-changed")
                            info = tarfile.TarInfo(entry["path"])
                            info.size, info.mode = entry["bytes"], 0o444 | (before.st_mode & 0o111)
                            yield info.tobuf(format=tarfile.PAX_FORMAT)
                            hasher, remaining = hashlib.sha256(), entry["bytes"]
                            while remaining:
                                piece = os.read(fd, min(65536, remaining))
                                c.require(bool(piece), "Input was truncated", "storage-input-changed")
                                hasher.update(piece)
                                remaining -= len(piece)
                                yield piece
                            c.require(hasher.hexdigest() == entry["sha256"] and handoff.signature(before) == handoff.signature(os.fstat(fd))
                                      == handoff.signature(os.stat(name, dir_fd=parent_fd, follow_symlinks=False)),
                                      "Input changed during streaming", "storage-input-changed")
                            yield b"\0" * (-entry["bytes"] % 512)
                        finally:
                            os.close(fd)
                yield b"\0" * 1024
            finally:
                workspace.close()
        return self._perform_write(registry_id, job_id, expected_revision, expected_epoch,
                                   {"operation": "stage", "manifest": "inputs/request.json"}, input_chunks=chunks())

    def prepare_workspace(self, registry_id, job_id, expected_revision, expected_epoch):
        return self._perform_write(registry_id, job_id, expected_revision, expected_epoch,
                                   {"operation": "prepare-workspace", "source": "inputs/project", "destination": "results/project"})

    def run(self, registry_id, job_id, expected_revision, expected_epoch, command, *, image=None,
            cwd="results/project", environment=None, timeout_seconds=1800):
        # This is a trusted pipeline primitive, never an MCP arbitrary-command tool.
        return self._perform_write(registry_id, job_id, expected_revision, expected_epoch,
                                   {"operation": "run", "command": command, "cwd": cwd, "environment": environment or {},
                                    "timeout_seconds": timeout_seconds}, image=image)

    def export_product(self, registry_id, job_id, product_id, format_name, consumer):
        """Manager-authorized read transfer, including after scratch retirement."""
        c.require(format_name in {"directory", "zip", "tar-gzip"}, "Unsupported receiver retention format")
        c.require(isinstance(product_id, str) and c.ID_RE.fullmatch(product_id) is not None, "Invalid product identity")
        guard = None
        operation_id = uuid.uuid4().hex
        try:
            with self.registry.locked(write=True) as registry:
                job = self._job(registry, job_id, registry_id)
                c.require(job["phase"] in {"open", "draining", "closed"}, "Read transfer admission is fenced", "storage-admission-closed")
                self._recover_gone(registry, job)
                product = next((item for item in job["products"] if item["id"] == product_id), None)
                c.require(product is not None, "Unknown registered product", "storage-binding-mismatch")
                c.require(self.docker.verify_volume(job["volumes"]["retained"]["native"]) is not None,
                          "Producer retained volume is unavailable", "storage-volume-mismatch")
                guard = registry.acquire_guard(operation_id)
                operation = {"id": operation_id, "kind": "transfer", "role": "export", "phase": "creating",
                             "client": self.origin.evidence(), "container_name": "unaltraweb-w1-"+operation_id,
                             "container_id": None, "product_id": product_id, "epoch": job["epoch"]}
                job["operations"].append(operation)
                self._save(registry, job)
                binding = self._mount_binding(job, operation_id, "read-only")
                c.check_binding(binding, self._state(registry, job))
                request = {"operation": "export", "format": format_name, "binding": binding,
                           "bundle_path": product["bundle_path"], "bundle_sha256": product["bundle_sha256"],
                           "markers": {"retained": job["volumes"]["retained"]["marker"]}, "limits": job["limits"]}
                labels = self._worker_labels(registry_id, job=job, lease_id=operation_id)
                image = self.docker.prepared_image(self.utility_reference)["id"]
                identifier = self.docker.create_worker(name=operation["container_name"], image_id=image, request=request,
                                                       mounts=[(job["volumes"]["retained"]["name"], "/work", True)],
                                                       labels=labels, guard_fds=(guard,))
                operation.update(phase="running", container_id=identifier, image_id=image)
                self._save(registry, job)
            result = self.docker.start_worker(identifier, guard_fds=(guard,), stdout_consumer=consumer, timeout=300)
            with self.registry.locked(write=True, wait_seconds=5) as registry:
                job = self._job(registry, job_id, registry_id)
                operation = next(item for item in job["operations"] if item["id"] == operation_id)
                observed = self.docker.inspect("container", identifier)
                c.require(observed is not None and not observed["running"], "Read transfer has not terminated", "storage-busy")
                self.docker.remove_stopped_container(identifier, labels)
                operation.update(phase="completed", completed_at=c.now())
                self._save(registry, job)
                c.require(not result.returncode and not result.timed_out and not result.stderr_truncated,
                          "Product transfer failed; retain the source and partial destination", "storage-export-incomplete")
                report = c.parse(result.stderr.encode())
                c.require(report.get("bundle_sha256") == product["bundle_sha256"], "Transferred product identity differs", "storage-binding-mismatch")
                return {"product": copy.deepcopy(product), "export_check": report, "state": self._state(registry, job)}
        finally:
            if guard is not None:
                os.close(guard)

    def verify_archive(self, relative, format_name, bundle_sha256, archive_sha256, archive_bytes):
        """Verify receiver-selected archive bytes using fresh managed scratch."""
        c.relative_path(relative)
        c.require(format_name in {"zip", "tar-gzip"}, "Unsupported archive format")
        source = handoff.Workspace(str(self.origin.project))
        try:
            observed, size, _ = source.read(relative, handoff.MAX_TOTAL_BYTES + c.MAX_DOCUMENT)
            c.require((observed, size) == (archive_sha256, archive_bytes), "Receiver archive changed", "storage-copy-incomplete")
        finally:
            source.close()
        state = self.begin("reception")
        product_id, verification_id = uuid.uuid4().hex, uuid.uuid4().hex
        def chunks():
            workspace = handoff.Workspace(str(self.origin.project))
            try:
                parent, _, name = relative.rpartition("/")
                with workspace.directory(parent) as directory:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                    try:
                        before = os.fstat(fd)
                        hasher, count = hashlib.sha256(), 0
                        while chunk := os.read(fd, 65536):
                            count += len(chunk)
                            c.require(count <= archive_bytes, "Receiver archive grew during transfer", "storage-copy-incomplete")
                            hasher.update(chunk)
                            yield chunk
                        c.require(count == archive_bytes and hasher.hexdigest() == archive_sha256
                                  and handoff.signature(before) == handoff.signature(os.fstat(fd)),
                                  "Receiver archive changed during verification transfer", "storage-copy-incomplete")
                    finally:
                        os.close(fd)
            finally:
                workspace.close()
        outcome = self._perform_write(state["registry_id"], state["job_id"], state["revision"], state["epoch"],
                                      {"operation": "verify-archive", "format": format_name, "bundle_sha256": bundle_sha256,
                                       "archive_sha256": archive_sha256, "archive_bytes": archive_bytes, "product_id": product_id}, input_chunks=chunks())
        report = outcome["report"]
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, state["job_id"], state["registry_id"])
            product = {"id": product_id, "bundle_path": report["bundle_path"], "bundle_sha256": bundle_sha256,
                       "domain_profile": report["domain_report"]["domain_profile"], "disposition": "pending", "decision": None,
                       "representations": [{"path": report["archive_path"], "sha256": archive_sha256, "bytes": archive_bytes}]}
            job["products"].append(product)
            self._save(registry, job)
            registry.write("verifications/" + verification_id + ".json", {
                "kind": "unaltraweb.archive-verification", "schema_version": 1,
                "binding_id": job["binding_id"], "job_id": job["job_id"], "product_id": product_id,
                "archive_sha256": archive_sha256, "archive_bytes": archive_bytes, "format": format_name,
                "bundle_sha256": bundle_sha256, "domain_report": report["domain_report"],
                "worker_container_id": outcome["container_id"], "observed_at": c.now()}, create_only=True)
            self._refresh(registry, job)
            return {"verification_id": verification_id, "job_id": job["job_id"], "registry_id": job["registry_id"],
                    "product_id": product_id, "report": report["domain_report"], "state": self._state(registry, job)}

    def _client_liveness(self, client):
        try:
            if client.get("container_id"):
                current = self.docker.inspect("container", client["container_id"])
                if current is None or not current["running"]:
                    return "dead"
                if (current["pid"] != client["process"].get("daemon_init_pid")
                        or current["image_id"] != client["process"].get("image_id")):
                    return "dead"
                return "alive"
            process = client["process"]
            if process.get("pid_namespace") != os.readlink("/proc/self/ns/pid"):
                return "unknown"
            if process.get("boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
                return "dead"
            pid = process.get("pid")
            c.require(type(pid) is int and pid > 0, "Invalid recorded process identity")
            try:
                fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            except FileNotFoundError:
                return "dead"
            return "alive" if int(fields[19]) == process["start_ticks"] and fields[0] != "Z" else "dead"
        except (OSError, ValueError, KeyError, IndexError, c.StorageError):
            return "unknown"

    def _leases(self, registry, job):
        values = []
        for lease in job["leases"]:
            state = lease["state"]
            if state != "released" and self._client_liveness(lease["client"]) != "alive":
                state = "unknown"
            values.append({"id": lease["id"], "kind": lease["kind"], "state": state})
        for operation in job.get("operations", []):
            if operation["phase"] in {"completed", "recovered"}:
                state = "released"
            else:
                guard = registry.guard_state(operation["id"])
                container = self.docker.inspect("container", operation["container_id"]) if operation.get("container_id") else None
                state = "active" if guard == "held" or (container and container["running"]) else "unknown"
            values.append({"id": operation["id"], "kind": operation["kind"], "state": state})
        c.require(len(values) <= 256, "Job lease history reached its bound; retain and explicitly finish this job", "storage-budget-exceeded")
        return values

    def _recover_gone(self, registry, job):
        changed = False
        for lease in job["leases"]:
            if lease["kind"] == "client" and lease["state"] != "released" and self._client_liveness(lease["client"]) == "dead":
                lease.update(state="released", verified_dead_at=c.now())
                changed = True
        for operation in job.get("operations", []):
            if operation["phase"] in {"completed", "recovered"}:
                continue
            recoverable_owner = self._client_liveness(operation["client"]) == "dead" or operation["client"]["client_id"] == self.origin.client_id
            if registry.guard_state(operation["id"]) != "unlocked" or not recoverable_owner:
                continue
            identifier = operation.get("container_id")
            if not identifier and operation.get("container_name"):
                # An interrupted create can be resolved only by its exact issued
                # name and independently checked labels/image/mount observations.
                observed = self.docker.inspect("container", operation["container_name"])
                if observed is not None:
                    identifier = observed["id"]
            if identifier:
                observed = self.docker.inspect("container", identifier)
                if observed is not None:
                    if observed["running"]:
                        continue
                    labels = self._worker_labels(job["registry_id"], job=job, lease_id=operation["id"])
                    # Session/project belong to the recorded creator, not the reaper.
                    labels["io.context.mcp-project"] = hashlib.sha256(operation["client"]["host_project"].encode()).hexdigest()[:16]
                    if operation["client"].get("session_id"):
                        labels["io.context.mcp-session"] = operation["client"]["session_id"]
                    else:
                        labels.pop("io.context.mcp-session", None)
                    c.require(not operation.get("image_id") or observed["image_id"] == operation["image_id"],
                              "Recovery worker image differs from its recorded identity", "storage-binding-mismatch")
                    self.docker.remove_stopped_container(identifier, labels)
            operation.update(phase="recovered", recovered_at=c.now())
            changed = True
        if changed:
            self._save(registry, job)

    def _refresh(self, registry, job):
        markers, mounts = {}, []
        for role, record in job["volumes"].items():
            actual = self.docker.verify_volume(record["native"])
            if actual is None:
                record["state"] = "absent"
                continue
            c.require(not self.docker.attachments(record["name"]), "Storage observation waits for attached containers", "storage-busy")
            markers[role] = record["marker"]
            mounts.append((record["name"], "/work" if role == "retained" else "/work/scratch", True))
        if "retained" in markers:
            products = [{"bundle_path": item["bundle_path"], "bundle_sha256": item["bundle_sha256"],
                         "representations": item.get("representations", [])} for item in job["products"]]
            result = self._control_worker(registry, {"operation": "observe", "markers": markers, "limits": job["limits"], "products": products}, mounts,
                                          job=job, role="inventory-observation")
            job["observation"] = result
            reason_for_root = {"inputs": "unsealed-source", "results": "unsealed-result", "exports": "unsealed-result",
                               "recovery": "recovery", "unknown": "unknown-content"}
            job["holds"] = [{"id": uuid.uuid5(uuid.UUID(job["job_id"]), reason).hex, "reason": reason}
                            for reason in sorted({reason_for_root.get(root, "unknown-content")
                                                  for root, count in result.get("unresolved_by_root", {}).items() if count})]
            for role in markers:
                job["volumes"][role]["state"] = "verified"
        else:
            c.require(job["phase"] in {"closed", "releasing", "released"}, "Protected volume disappeared before close", "storage-observation-unknown")
        self._save(registry, job)

    def detach(self, registry_id, job_id, expected_revision, expected_epoch):
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, job_id, registry_id)
            c.require((expected_revision, expected_epoch) == (job["revision"], job["epoch"]), "Storage revision changed", "storage-revision-conflict")
            changed = False
            for lease in job["leases"]:
                if lease["client"]["client_id"] == self.origin.client_id and lease["state"] == "active":
                    lease.update(state="released", released_at=c.now())
                    changed = True
            if changed:
                self._save(registry, job)
            return self._state(registry, job)

    def attach(self, registry_id, job_id, expected_revision, expected_epoch):
        """Register another authenticated client's interest; never reopen implicitly."""
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, job_id, registry_id)
            c.require((job["revision"], job["epoch"]) == (expected_revision, expected_epoch), "Storage revision changed", "storage-revision-conflict")
            c.require(job["phase"] == "open", "Job write admission is closed", "storage-admission-closed")
            if not any(lease["state"] == "active" and lease["client"]["client_id"] == self.origin.client_id for lease in job["leases"]):
                c.require(len(self._leases(registry, job)) < 240, "Job lease budget is exhausted", "storage-budget-exceeded")
                job["leases"].append({"id": uuid.uuid4().hex, "kind": "client", "state": "active",
                                      "client": self.origin.evidence(), "epoch": job["epoch"]})
                self._save(registry, job)
            self._track_interest(job)
            return self._state(registry, job)

    def toggle_off(self, handles):
        """Drop only this client's interests and reclaim independently eligible jobs."""
        c.require(isinstance(handles, list) and len(handles) <= 64, "Invalid bounded job selection")
        outcomes = []
        for registry_id, job_id in handles:
            try:
                state = self.status(registry_id, job_id)
                if state["phase"] == "released":
                    outcomes.append({"ok": True, "state": state, "removed": []})
                    continue
                state = self.detach(registry_id, job_id, state["revision"], state["epoch"])
                with self.registry.locked(write=True) as registry:
                    job = self._job(registry, job_id, registry_id)
                    self._recover_gone(registry, job)
                    state = self._state(registry, job)
                    demanded = any(lease["kind"] == "client" and lease["state"] != "released" for lease in state["leases"])
                if demanded:
                    outcomes.append({"ok": True, "state": state, "removed": [], "kept": "other-or-unknown-client-interest"})
                    continue
                if state["phase"] in {"open", "draining"}:
                    state = self.control({"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "quiesce",
                                          "registry_id": registry_id, "job_id": job_id,
                                          "expected_revision": state["revision"], "expected_epoch": state["epoch"]})
                if state["phase"] in {"closed", "releasing"}:
                    plan = self.plan_release(registry_id, job_id)
                    outcomes.append(self.apply_release(plan["plan"], plan["plan_sha256"]))
                else:
                    outcomes.append({"ok": True, "state": state, "removed": [], "kept": "busy-or-unknown"})
            except (c.StorageError, OSError) as exc:
                outcomes.append({"ok": False, "registry_id": registry_id, "job_id": job_id,
                                 "code": getattr(exc, "code", "storage-observation-unknown"), "error": str(exc)[:4096]})
        return {"ok": all(item["ok"] for item in outcomes), "jobs": outcomes}

    def reap_session(self, session_id, container_id):
        """Host-side completion after a transport's forced EOF/termination.

        Select only interests/operations recorded for this exact dead backend.
        A client transport can kill the process before its graceful cleanup ends;
        the external registry remains the authority for continuing that cleanup.
        """
        c.require(isinstance(session_id, str) and c.ID_RE.fullmatch(session_id) is not None
                  and isinstance(container_id, str) and c.HASH_RE.fullmatch(container_id) is not None,
                  "Exact session and backend IDs are required")
        backend = self.docker.inspect("container", container_id)
        if backend is not None:
            labels = backend.get("labels") or {}
            c.require(labels.get("io.context.mcp-factory") == "unaltraweb" and labels.get("io.context.mcp-role") == "stdio"
                      and labels.get("io.context.mcp-session") == session_id
                      and labels.get("io.context.mcp-project") == hashlib.sha256(self.origin.host_project.encode()).hexdigest()[:16],
                      "Backend differs from the retained session identity", "storage-binding-mismatch")
            c.require(not backend["running"], "Backend still owns its session", "storage-busy")
        handles = []
        try:
            with self.registry.locked() as registry:
                self.docker.require_daemon(registry.record["daemon_id"])
                binding = registry.record["bindings"].get(self.origin.key())
                if binding is None:
                    return {"ok": True, "scope": "session", "jobs": [], "registered": False}
                for identifier in registry.record["jobs"]:
                    job = registry.read("jobs/" + identifier + ".json")
                    if job["binding_id"] != binding["id"]:
                        continue
                    clients = [job["origin"], *(item["client"] for item in job["leases"]),
                               *(item["client"] for item in job["operations"])]
                    if any(client.get("session_id") == session_id and client.get("container_id") == container_id for client in clients):
                        handles.append((registry.record["id"], identifier))
                c.require(len(handles) <= 64, "Session job selection exceeds its bound", "storage-budget-exceeded")
        except FileNotFoundError:
            return {"ok": True, "scope": "session", "jobs": [], "registered": False}
        return {**self.toggle_off(handles), "scope": "session", "registered": True}

    @staticmethod
    def _release_plan(state):
        planned_at = c.now()
        common = []
        if state["phase"] not in {"closed", "releasing", "released"}:
            common.append("admission-not-closed")
        if state["activity"] != "idle":
            common.append("job-busy-or-unknown")
        if not state["leases_complete"] or any(lease["state"] != "released" for lease in state["leases"]):
            common.append("active-or-unknown-lease")
        obligations = []
        if state["holds"]:
            obligations.append("retention-holds")
        inventory = state["protected_inventory"]
        if inventory["state"] != "verified" or inventory["unresolved_entries"]:
            obligations.append("unresolved-protected-content")
        for product in state["products"]:
            if product["disposition"] == "pending":
                obligations.append("pending-product")
            elif state["phase"] != "released" and (product["decision"]["status"] != "verified" or not c.fresh(product["decision"]["verified_at"], planned_at)):
                obligations.append("unverified-retention-or-discard")
        volumes = []
        for volume in sorted(state["volumes"], key=lambda row: row["role"]):
            blockers = list(common)
            if not c.fresh(volume["observed_at"], planned_at):
                blockers.append("stale-volume-observation")
            if volume["state"] == "unknown":
                blockers.append("volume-identity-unknown")
            if not volume["attachments_complete"] or volume["attachments"]:
                blockers.append("attached-or-unknown-container")
            if volume["role"] == "retained":
                blockers.extend(obligations)
                if volume["state"] == "absent" and obligations:
                    blockers.append("missing-protected-volume")
            action = "blocked" if blockers else "already-absent" if volume["state"] == "absent" else "remove-volume"
            volumes.append({"id": volume["id"], "name": volume["name"], "role": volume["role"], "action": action,
                            "estimated_bytes": volume["bytes"], "blockers": sorted(set(blockers))})
        plan = {"kind": "unaltraweb.job-storage-release-plan", "schema_version": 1,
                **{key: state[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id")},
                "expected_revision": state["revision"], "expected_epoch": state["epoch"],
                "state_sha256": c.sha256(c.canonical(state)), "planned_at": planned_at,
                "expires_at": (c.timestamp(planned_at) + dt.timedelta(seconds=c.FRESH_SECONDS)).isoformat().replace("+00:00", "Z"),
                "read_only": True, "execution_supported": True, "requires_live_revalidation": True,
                "volumes": volumes, "retention_resolved": not obligations,
                "all_releasable": all(volume["action"] != "blocked" for volume in volumes)}
        return {"plan": plan, "plan_sha256": c.sha256(c.canonical(plan))}

    def _refresh_decisions(self, registry, job):
        # A producer/agent-authored JSON acknowledgement is never sufficient.
        # Reception/discard witnesses are independently checked by their owner.
        changed = False
        for product in job["products"]:
            if product["disposition"] == "pending":
                continue
            product["decision"]["status"] = "unknown"
            changed = True
            if product["disposition"] == "acknowledged":
                try:
                    from . import reception
                    record = registry.read("decisions/" + product["decision"]["id"] + ".json")
                    c.require(record.get("kind") == "unaltraweb.retention-witness" and record.get("job_id") == job["job_id"]
                              and record.get("product_id") == product["id"] and record.get("bundle_sha256") == product["bundle_sha256"]
                              and record.get("envelope_sha256") == product["decision"]["evidence_sha256"], "Retention witness identity differs")
                    with reception.receiver_lock(self.origin.project):
                        current = reception.verify_record(self, record["witness"], registry=registry)
                    product["decision"].update(status="verified", verified_at=c.now())
                    product["last_domain_check_sha256"] = current["evidence_sha256"]
                except (OSError, ValueError, KeyError, c.StorageError, handoff.HandoffError):
                    pass
        if changed:
            self._save(registry, job)

    def _acknowledge(self, registry_id, job_id, product_id, retained):
        from . import reception
        envelope, witness = retained["envelope"], retained["witness"]
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, job_id, registry_id)
            c.require(job["phase"] not in {"releasing", "released"}, "A retirement tombstone cannot accept a new delivery decision", "storage-admission-closed")
            product = next((item for item in job["products"] if item["id"] == product_id), None)
            c.require(product is not None and product["bundle_sha256"] == envelope["bundle_sha256"]
                      and envelope["registry_id"] == registry_id and envelope["job_id"] == job_id
                      and envelope["product_id"] == product_id and envelope["receiver_binding_id"] == self._binding(registry)["id"],
                      "Durable acknowledgement differs from the registered product", "storage-binding-mismatch")
            with reception.receiver_lock(self.origin.project):
                actual = reception.verify_record(self, witness, registry=registry)
            identifier = uuid.uuid4().hex
            registry.write("decisions/" + identifier + ".json", {
                "kind": "unaltraweb.retention-witness", "schema_version": 1, "job_id": job_id, "product_id": product_id,
                "bundle_sha256": product["bundle_sha256"], "envelope_sha256": witness["envelope_sha256"],
                "witness": witness, "recorded_at": c.now(), "recorded_by": self.origin.evidence()}, create_only=True)
            product["disposition"] = "acknowledged"
            product["decision"] = {"id": identifier, "kind": "retention", "evidence_sha256": witness["envelope_sha256"],
                                   "bundle_sha256": product["bundle_sha256"], "status": "verified", "verified_at": c.now()}
            product["last_domain_check_sha256"] = actual["evidence_sha256"]
            self._save(registry, job)
            return self._state(registry, job)

    def _finish_verification(self, verification, witness):
        if verification is None:
            return None
        from . import reception
        registry_id, job_id, product_id = (verification[key] for key in ("registry_id", "job_id", "product_id"))
        with reception.receiver_lock(self.origin.project) as root:
            domain = reception.verify_record(self, witness)
            retained = reception.acknowledge(self, root, witness, domain, registry_id, job_id, product_id)
        state = self._acknowledge(registry_id, job_id, product_id, retained)
        state = self.detach(registry_id, job_id, state["revision"], state["epoch"])
        self.control({"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "quiesce",
                      "registry_id": registry_id, "job_id": job_id, "expected_revision": state["revision"], "expected_epoch": state["epoch"]})
        plan = self.plan_release(registry_id, job_id)
        return self.apply_release(plan["plan"], plan["plan_sha256"])

    def receive_product(self, registry_id, job_id, product_id):
        from . import reception
        retained = reception.receive_product(self, registry_id, job_id, product_id)
        state = self._acknowledge(registry_id, job_id, product_id, retained)
        verification_release = self._finish_verification(retained.get("verification_job"), retained["witness"])
        return {"ok": True, "retention": retained["envelope"], "retention_sha256": retained["witness"]["envelope_sha256"],
                "state": state, "verification_job_release": verification_release, "reused": retained["reused"]}

    def check_retained(self, bundle_sha256):
        """Explicit receiver-selected revalidation, also after moving the site.

        Establish a new local binding; never copy/adopt another registry or grant
        authority over the old producer. Archive extraction stays on job volumes.
        """
        from . import reception
        reception.policy(self.origin.project)
        reception.durable_binding(self)
        with self.registry.locked(write=True, create=True, daemon_id=self.docker.daemon()) as registry:
            self._binding(registry, create=True)
        with reception.receiver_lock(self.origin.project):
            observed = reception.observe_stored(self, bundle_sha256)
        release = self._finish_verification(observed["verification_job"], observed["witness"])
        return {"ok": True, "domain": observed["domain"], "receiver_binding_id": observed["witness"]["receiver_binding_id"],
                "verification_job_release": release}

    def plan_release(self, registry_id, job_id):
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, job_id, registry_id)
            if job["phase"] == "releasing":
                self._recover_gone(registry, job)
            state = self._state(registry, job)
            if job["phase"] in {"closed", "releasing"} and state["activity"] == "idle" and all(item["state"] == "released" for item in state["leases"]):
                self._refresh(registry, job)
                self._refresh_decisions(registry, job)
                state = self._state(registry, job)
            return self._release_plan(state)

    def apply_release(self, plan, plan_sha256):
        c.require(isinstance(plan, dict) and c.sha256(c.canonical(plan)) == plan_sha256
                  and plan.get("kind") == "unaltraweb.job-storage-release-plan" and type(plan.get("schema_version")) is int
                  and plan["schema_version"] == 1, "Release plan differs from its reviewed bytes", "storage-revision-conflict")
        c.require(c.fresh(plan["planned_at"]) and c.timestamp(c.now()) <= c.timestamp(plan["expires_at"]),
                  "Release plan expired", "storage-revision-conflict")
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, plan["job_id"], plan["registry_id"])
            c.require((job["revision"], job["epoch"]) == (plan["expected_revision"], plan["expected_epoch"]),
                      "Release revision or epoch changed", "storage-revision-conflict")
            c.require(all(plan[key] == job[key] for key in ("binding_id", "provider", "provider_sha256", "daemon_id")),
                      "Release plan belongs to another binding or daemon", "storage-binding-mismatch")
            state = self._state(registry, job)
            if job["phase"] == "released":
                return {"ok": True, "removed": [], "state": state}
            c.require(job["phase"] in {"closed", "releasing"} and state["activity"] == "idle"
                      and state["leases_complete"] and all(item["state"] == "released" for item in state["leases"]),
                      "Release requires closed, independently idle storage", "storage-busy")
            self._refresh(registry, job)
            self._refresh_decisions(registry, job)
            current = self._release_plan(self._state(registry, job))["plan"]
            expected = {row["role"]: row for row in current["volumes"]}
            c.require({row["role"] for row in plan["volumes"]} == set(expected)
                      and len(plan["volumes"]) == len(expected), "Release volume inventory differs", "storage-binding-mismatch")
            for row in plan["volumes"]:
                actual = expected[row["role"]]
                c.require(all(row[key] == actual[key] for key in ("id", "name", "action")),
                          "Live release decisions differ; inspect a fresh plan", "storage-revision-conflict")
            removed = []
            release_id = uuid.uuid4().hex
            guard = registry.acquire_guard(release_id)
            operation = {"id": release_id, "kind": "task", "role": "release", "phase": "running",
                         "client": self.origin.evidence(), "container_id": None, "job_id": job["job_id"]}
            job.setdefault("operations", []).append(operation)
            job["release_journal"] = {"plan_sha256": plan_sha256, "started_at": c.now(), "removed": [],
                                      "pending_role": None, "guard_id": release_id,
                                      "verified_products": copy.deepcopy(job["products"])}
            job["phase"] = "releasing"
            self._save(registry, job)
            try:
                for role in ("scratch", "retained"):
                    action = expected[role]["action"]
                    if action == "blocked":
                        continue
                    # A scratch removal can take time, or the receiver can change
                    # after it. Recheck the full native barrier for *each* volume,
                    # disregarding only this executor's own guarded release task.
                    self._refresh(registry, job)
                    self._refresh_decisions(registry, job)
                    live = self._state(registry, job)
                    live["leases"] = [lease for lease in live["leases"] if lease["id"] != release_id]
                    live_plan = self._release_plan(live)["plan"]
                    live_action = next(row for row in live_plan["volumes"] if row["role"] == role)
                    c.require(live_action["action"] != "blocked" and live_action["id"] == expected[role]["id"],
                              "Storage or durable receiver changed before exact removal", "storage-release-blocked")
                    c.require(c.fresh(plan["planned_at"]), "Release plan expired during application", "storage-revision-conflict")
                    job["release_journal"]["pending_role"] = role
                    self._save(registry, job)
                    record = job["volumes"][role]
                    if self.docker.remove_volume(record["native"], job["daemon_id"], guard_fds=(guard,)):
                        removed.append(record["name"])
                    record["state"] = "absent"
                    job["release_journal"]["removed"].append(record["id"])
                    job["release_journal"]["pending_role"] = None
                    self._save(registry, job)
                operation["phase"] = "completed"
            except BaseException:
                operation["phase"] = "interrupted"
                self._save(registry, job)
                raise
            finally:
                os.close(guard)
            fully_released = all(record["state"] == "absent" for record in job["volumes"].values())
            job["phase"] = "released" if fully_released else "closed"
            job["release_journal"]["finished_at"] = c.now()
            self._save(registry, job)
            return {"ok": True, "removed": removed, "state": self._state(registry, job)}

    def control(self, request):
        c.validate(request)
        c.require(request["kind"] == "gacontext.job-storage-request", "Expected a native storage request")
        if request["operation"] == "status":
            return self.status(request["registry_id"], request["job_id"])
        with self.registry.locked(write=True) as registry:
            job = self._job(registry, request["job_id"], request["registry_id"])
            state = self._state(registry, job)
            c.check_request(request, state)
            if request["operation"] == "seal":
                self._refresh(registry, job)
                unchanged = next((item for item in job["products"] if item.get("work_tree_sha256") == job["observation"]["work_tree_sha256"]), None)
                if unchanged is not None or job["observation"]["protected_inventory"]["unresolved_entries"] == 0:
                    return self._state(registry, job)
                images = sorted({item["image_id"] for item in job["operations"] if item.get("image_id")})
                implementation = c.sha256(b"".join(path.read_bytes() for path in sorted(Path(__file__).parent.glob("*.py"))))
                producer = {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + implementation,
                            "runtimes": [{"name": f"toolchain-{index}", "revision": image} for index, image in enumerate(images)]}
                product_id = uuid.uuid4().hex
                operation = {"operation": "seal", "product_id": product_id, "producer": producer,
                             "markers": {role: value["marker"] for role, value in job["volumes"].items()}, "limits": job["limits"]}
                mounts = [(job["volumes"]["retained"]["name"], "/work", False),
                          (job["volumes"]["scratch"]["name"], "/work/scratch", False)]
                sealed = self._control_worker(registry, operation, mounts, job=job, role="product-seal")
                self._track_interest(job)
                job["products"].append({"id": product_id, "bundle_sha256": sealed["bundle_sha256"], "bundle_path": sealed["bundle_path"],
                                         "disposition": "pending", "decision": None, "domain_profile": "unaltraweb-job-v1",
                                         "work_tree_sha256": sealed["work_tree_sha256"]})
                self._save(registry, job)
                self._refresh(registry, job)
                return self._state(registry, job)
            self._recover_gone(registry, job)
            if job["phase"] == "closed":
                return self._state(registry, job)
            if job["phase"] == "open":
                job["phase"] = "draining"
                self._save(registry, job)
            if any(item["state"] != "released" and item["kind"] != "client" for item in self._leases(registry, job)):
                return self._state(registry, job)
            self._refresh(registry, job)
            job["phase"] = "closed"
            job["epoch"] += 1
            self._save(registry, job)
            return self._state(registry, job)
