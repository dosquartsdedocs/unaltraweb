"""Bound native adapter to the published common SDK, never a storage manager.

The operator prepares/registers images and selects an existing task/job/owner.
This module does not initialize services, acquire images, allocate replacement
slots, acknowledge arbitrary paths, or implement leases/markers/retirement.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import stat

from .artifact_handoff_v1 import parse_json
from .runtime_identity import code_bytes

ENV = "UNALTRAWEB_SHARED_JOB_CONTEXT"
CONTRACT = Path(__file__).with_name("shared-runtime.json")
PROVIDER = Path(__file__).with_name("shared-job-storage.json")


class SharedError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(value, message, code="shared-binding-invalid"):
    if not value:
        raise SharedError(code, message)


def runtime_contract():
    return parse_json(code_bytes(CONTRACT))


def sdk():
    try:
        import gacontext_runtime
        from gacontext_runtime.api import code_identity
        from gacontext_runtime.client import Client
        from gacontext_runtime.worker import create_args
    except ImportError as exc:
        raise SharedError("shared-runtime-unavailable", "Install the explicitly verified common SDK; no acquisition was attempted") from exc
    expected = runtime_contract()
    require(gacontext_runtime.PACKAGED and gacontext_runtime.__version__ == expected["version"]
            and code_identity() == expected["code_sha256"], "Selected SDK bytes differ from the published dependency", "shared-runtime-mismatch")
    return Client, create_args


def load_context(workspace, filename):
    """Read one explicit private operator binding. Never discover another root."""
    path = Path(filename)
    require(path.is_absolute() and path.resolve() == path, "Shared context must be an explicit canonical file")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "Shared context must be a private owner file")
    raw = code_bytes(path)
    require(len(raw) <= 16384, "Shared context exceeds its metadata bound")
    value = parse_json(raw)
    required = {"schema_version", "kind", "workspace", "service_root", "docker_endpoint", "daemon_id",
                "registry_id", "job_id", "task_id", "owner_id", "pdf_image", "worker_user"}
    require(isinstance(value, dict) and required <= value.keys()
            and not value.keys() - (required | {"receiver_id", "receiver_workspace", "worker_timeout_seconds", "edition_verifier_image"}), "Missing or unknown shared context fields")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["kind"] == "unaltraweb.shared-job-context", "Unsupported shared context")
    require(value["workspace"] == str(workspace), "Shared job belongs to another consumer", "shared-workspace-mismatch")
    for name in ("service_root", "workspace", "receiver_workspace"):
        if name in value:
            root = Path(value[name])
            require(root.is_absolute() and root.resolve() == root and root.is_dir(), "Shared roots must already exist and be canonical")
    root = Path(value["service_root"])
    require(not root.is_relative_to(workspace) and not Path(workspace).is_relative_to(root), "Service and consumer roots must be disjoint")
    require(value["docker_endpoint"].startswith("unix:///"), "Shared execution requires an explicitly selected local Docker socket")
    endpoint = Path(value["docker_endpoint"].removeprefix("unix://"))
    require(endpoint.resolve() == endpoint and not endpoint.is_relative_to(workspace), "Docker endpoint must be canonical and outside the consumer")
    for name in ("registry_id", "job_id", "task_id", "owner_id", "receiver_id"):
        if name in value:
            require(isinstance(value[name], str) and re.fullmatch(r"[0-9a-f]{32}", value[name]), "Shared identifiers must be exact")
    require(isinstance(value["daemon_id"], str) and 0 < len(value["daemon_id"]) <= 256, "Explicit daemon identity is required")
    require(isinstance(value["pdf_image"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value["pdf_image"]), "Shared PDF image must be an exact prepared ID")
    require(isinstance(value["worker_user"], str) and re.fullmatch(r"[0-9]{1,10}:[0-9]{1,10}", value["worker_user"]),
            "Select the common service's host worker UID/GID explicitly")
    require(("receiver_id" in value) == ("receiver_workspace" in value), "Receiver selection must include its explicit root")
    timeout = value.get("worker_timeout_seconds", 900)
    require(type(timeout) is int and 1 <= timeout <= 900, "Worker timeout must be an integer from 1 to 900 seconds")
    if "edition_verifier_image" in value:
        contract = parse_json(code_bytes(Path(__file__).with_name("shared-practice-verifier.json")))
        require(value["edition_verifier_image"] == contract["image_id"], "Shared edition verifier differs from the accepted owner candidate")
    return copy.deepcopy(value)


def selected(project):
    from .runtime_identity import active_runtime
    active = active_runtime()
    if active is not None:
        return copy.deepcopy(getattr(active, "shared_job_context", None))
    filename = os.environ.get(ENV)
    if not filename:
        return None
    from .site_tools import _docker_host_project
    return load_context(Path(_docker_host_project(Path(project))), filename)


class BoundJob:
    def __init__(self, values):
        self.values = copy.deepcopy(values)
        Client, self.create_args = sdk()
        self.client = Client(self.values["service_root"])
        self.workspace = self.values["workspace"]

    def verify_service(self):
        value = self.client.identity()
        expected = runtime_contract()
        require(value.get("ok") and value.get("version") == expected["version"]
                and value.get("loaded_code_sha256") == expected["code_sha256"]
                and value.get("current_code_sha256") == expected["code_sha256"] and value.get("code_drift") is False,
                "Selected service differs from the pinned common SDK", "shared-runtime-mismatch")
        return value

    def call(self, method, **params):
        result = self.client.call(method, workspace=self.workspace, **params)
        if not result.get("ok"):
            error = result.get("error") or {}
            raise SharedError(error.get("code", "shared-operation-failed"), error.get("message", "Common operation failed; preserve the selected job"))
        return result

    def control(self, request):
        require(isinstance(request, dict) and request.get("job_id") == self.values["job_id"]
                and request.get("registry_id") == self.values["registry_id"],
                "Native request addresses another selected job/registry", "shared-job-mismatch")
        # Do not pre-read a revision or emulate CAS. Busy-quiesce changed/state
        # fields, errors and cached status are returned exactly by the SDK.
        return self.client.job_storage(self.workspace, "unaltraweb", copy.deepcopy(request))

    def status(self):
        return self.control({"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "status",
                             "registry_id": self.values["registry_id"], "job_id": self.values["job_id"]})

    def transition(self, operation):
        observed = self.status()
        require(observed.get("ok"), "Selected job cannot be observed", "shared-status-unavailable")
        state = observed["state"]
        return self.control({"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": operation,
                             "registry_id": state["registry_id"], "job_id": state["job_id"],
                             "expected_revision": state["revision"], "expected_epoch": state["epoch"]})


def job_storage(project, request):
    try:
        context = selected(project)
        require(context is not None, "Select an existing common service/task/job explicitly; no initialization was attempted", "shared-runtime-unconfigured")
        return BoundJob(context).control(request)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"ok": False, "error": {"code": getattr(exc, "code", "shared-operation-failed"), "message": str(exc)[:2048]}}
