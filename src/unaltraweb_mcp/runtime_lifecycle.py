"""Bounded Docker observations and exact, per-session orphan recovery.

This module never prepares images, reads consumer content or removes volumes.
It is also used by the host adapter after a client has drained/closed its MCP.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .processes import run_process

IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
SESSION_ID = re.compile(r"[0-9a-f]{32}")
PREFIX = "io.context.mcp-"
WORKER_ROLES = {"computation", "manual-pdf", "web-capture"}
IDLE_ROLES = {"preview", "web-capture-site"}
CONTAINER_FORMAT = ('{"id":{{json .Id}},"image_id":{{json .Image}},'
    '"network_mode":{{json .HostConfig.NetworkMode}},'
    '"memory_bytes":{{json .HostConfig.Memory}},"nano_cpus":{{json .HostConfig.NanoCpus}},"pids_limit":{{json .HostConfig.PidsLimit}},'
    '"source_revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}},'
    '"running":{{json .State.Running}},"status":{{json .State.Status}},'
    '"daemon_init_pid":{{json .State.Pid}},'
    '"factory":{{json (index .Config.Labels "io.context.mcp-factory")}},'
    '"role":{{json (index .Config.Labels "io.context.mcp-role")}},'
    '"project_id":{{json (index .Config.Labels "io.context.mcp-project")}},'
    '"session_id":{{json (index .Config.Labels "io.context.mcp-session")}},'
    '"worker_token":{{json (index .Config.Labels "io.context.mcp-worker-token")}},'
    '"mounts":{{json .Mounts}}}')
IMAGE_FORMAT = ('{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}},'
    '"os":{{json .Os}},"architecture":{{json .Architecture}},'
    '"source_revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}}}')
NETWORK_FORMAT = ('{"id":{{json .Id}},"containers":{{json .Containers}},'
    '"factory":{{json (index .Labels "io.context.mcp-factory")}},'
    '"role":{{json (index .Labels "io.context.mcp-role")}},'
    '"project_id":{{json (index .Labels "io.context.mcp-project")}},'
    '"session_id":{{json (index .Labels "io.context.mcp-session")}}}')


def image_reference(value):
    if not isinstance(value, str) or len(value) > 300 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/:@-]*", value):
        raise ValueError("Invalid bounded Docker image reference")
    if "@" in value and (value.count("@") != 1 or not IMAGE_ID.fullmatch(value.rsplit("@", 1)[1])):
        raise ValueError("Docker references may contain only a digest suffix, never credentials")
    if "://" in value:
        raise ValueError("Docker references are not URLs")
    return value


def immutable_reference(value):
    return bool(IMAGE_ID.fullmatch(value) or re.fullmatch(r"[a-z0-9][a-z0-9._/:-]*@sha256:[0-9a-f]{64}", value))


def docker(arguments, timeout=10):
    return run_process(["docker", *arguments], timeout_seconds=timeout)


def _inspect(kind, value, template):
    result = docker([kind, "inspect", "--format", template, value])
    if result.timed_out or result.stdout_truncated or result.stderr_truncated:
        raise RuntimeError("Docker observation timed out or exceeded its bound")
    if result.returncode:
        message = result.stderr.lower()
        if f"no such {kind}" in message or "no such object" in message:
            return None
        raise RuntimeError("Docker observation unavailable")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("Invalid Docker observation")
    return data


def inspect_container(value):
    if not CONTAINER_ID.fullmatch(value) and not re.fullmatch(r"unaltraweb-stdio-[0-9a-f]{32}", value):
        raise ValueError("An exact container ID or native session name is required")
    return _inspect("container", value, CONTAINER_FORMAT)


def inspect_image(reference, expected_id=""):
    image_reference(reference)
    if expected_id and not IMAGE_ID.fullmatch(expected_id):
        raise ValueError("Expected image ID must be a full lowercase sha256")
    result = {"reference": reference, "expected_image_id": expected_id or None}
    try:
        info = _inspect("image", reference, IMAGE_FORMAT)
        if info is None:
            return {**result, "state": "missing", "observed_image_id": None}
        actual = info.get("id", "")
        if not IMAGE_ID.fullmatch(actual):
            raise ValueError("Invalid observed Docker image ID")
        digests = info.get("repo_digests") or []
        matches = (not expected_id or actual == expected_id) and (not IMAGE_ID.fullmatch(reference) or actual == reference)
        if "@sha256:" in reference:
            matches = matches and reference in digests
        return {**result, "state": "matched" if matches else "mismatch", "observed_image_id": actual,
                "registry_digests": digests[:32], "source_revision": info.get("source_revision"),
                "os": info.get("os"), "architecture": info.get("architecture")}
    except (OSError, RuntimeError, ValueError, TypeError):
        return {**result, "state": "unknown", "observed_image_id": None}


def owned(info, project_id, session_id, roles):
    return (isinstance(info, dict) and info.get("factory") == "unaltraweb"
            and info.get("project_id") == project_id and info.get("session_id") == session_id
            and info.get("role") in roles and bool(CONTAINER_ID.fullmatch(info.get("id", ""))))


def session_containers(project_id, session_id):
    if not re.fullmatch(r"[0-9a-f]{16}", project_id) or not SESSION_ID.fullmatch(session_id):
        raise ValueError("Invalid project/session identity")
    result = docker(["ps", "-aq", "--no-trunc", "--filter", f"label={PREFIX}factory=unaltraweb",
                     "--filter", f"label={PREFIX}project={project_id}", "--filter", f"label={PREFIX}session={session_id}"])
    ids = result.stdout.split()
    if result.returncode or result.timed_out or result.stdout_truncated or len(ids) > 32 or any(not CONTAINER_ID.fullmatch(cid) for cid in ids):
        raise RuntimeError("Session resource inventory is unavailable or exceeds bounds")
    return [info for cid in ids if (info := inspect_container(cid)) is not None]


def remove_idle_container(cid, project_id, session_id):
    info = inspect_container(cid)
    if info is None:
        return
    if not owned(info, project_id, session_id, IDLE_ROLES) or info["id"] != cid:
        raise RuntimeError("Refusing a changed or foreign session resource")
    result = docker(["rm", "-f", cid], 30)
    if result.returncode or inspect_container(cid) is not None:
        raise RuntimeError("Resource termination is not confirmed")


def session_networks(project_id, session_id):
    result = docker(["network", "ls", "-q", "--no-trunc", "--filter", f"label={PREFIX}factory=unaltraweb",
                     "--filter", f"label={PREFIX}project={project_id}", "--filter", f"label={PREFIX}session={session_id}"])
    ids = result.stdout.split()
    if result.returncode or result.timed_out or result.stdout_truncated or len(ids) > 32 or any(not CONTAINER_ID.fullmatch(cid) for cid in ids):
        raise RuntimeError("Session network inventory unavailable")
    return [info for nid in ids if (info := _inspect("network", nid, NETWORK_FORMAT)) is not None]


def remove_idle_network(nid, project_id, session_id):
    info = _inspect("network", nid, NETWORK_FORMAT)
    if info is None:
        return
    if not owned(info, project_id, session_id, {"web-capture"}) or info.get("containers"):
        raise RuntimeError("Refusing a foreign or occupied network")
    if docker(["network", "rm", nid], 30).returncode or _inspect("network", nid, NETWORK_FORMAT) is not None:
        raise RuntimeError("Network removal is not confirmed")


def session_status(project, session_id, container_id, *, reap=False):
    """Recover only orphan idle resources; never terminate a live backend/job."""
    try:
        if not SESSION_ID.fullmatch(session_id) or not CONTAINER_ID.fullmatch(container_id):
            raise ValueError("Exact session and container IDs are required")
        root = str(Path(project).absolute())
        if str(Path(root)) != root or ".." in Path(root).parts:
            raise ValueError("Project path must be normalized")
        project_id = hashlib.sha256(root.encode()).hexdigest()[:16]
        parent = inspect_container(container_id)
        if parent is not None and not owned(parent, project_id, session_id, {"stdio"}):
            raise RuntimeError("Container does not match the retained session identity")
        resources = session_containers(project_id, session_id)
        networks = session_networks(project_id, session_id)
        if any(not owned(info, project_id, session_id, {"web-capture"}) for info in networks):
            raise RuntimeError("Unknown session network ownership")
        for info in resources:
            if not owned(info, project_id, session_id, WORKER_ROLES | IDLE_ROLES | {"stdio"}):
                raise RuntimeError("Unknown session resource ownership")
            if info["role"] == "stdio" and info["id"] != container_id:
                raise RuntimeError("Session ID was reused by a different backend")
        busy = any(info["running"] and info["role"] in WORKER_ROLES for info in resources)
        connected = parent is not None and parent["running"]
        if reap and not connected and not busy:
            for info in resources:
                if info["role"] in IDLE_ROLES:
                    remove_idle_container(info["id"], project_id, session_id)
                elif not info["running"]:
                    # Exited exact owned objects only; no force or volume flag.
                    current = inspect_container(info["id"])
                    if current is not None:
                        if current != info or docker(["rm", info["id"]]).returncode:
                            raise RuntimeError("Exited resource changed during recovery")
            resources = session_containers(project_id, session_id)
            for info in networks:
                remove_idle_network(info["id"], project_id, session_id)
            networks = session_networks(project_id, session_id)
        state = "busy" if busy else "connected" if connected else "orphaned" if resources or networks else "stopped"
        return {"ok": True, "scope": "session", "session_id": session_id, "container_id": container_id,
                "project": root, "state": state, "resources_released": state == "stopped", "resources": resources, "networks": networks,
                "action": "reap" if reap else "inspect"}
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        return {"ok": False, "scope": "session", "state": "unknown", "resources_released": False, "error": str(exc)}
