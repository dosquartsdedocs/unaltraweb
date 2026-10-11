"""Web-owned bridge to the prepared private QGIS controller's native CLI.

Only transport, identity and bounded execution live here. No QGIS algorithms,
private imports, wheel installation or runtime acquisition are implemented.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import uuid

from . import runtime_lifecycle as lifecycle
from .artifact_handoff_v1 import parse_json, safe_path
from .docker_mount import docker_bind_mount
from .processes import run_process

CONTRACT = Path(__file__).with_name("practice-verifier-runtime.json")
WORKER = "practice_verifier"
ROLE = "practice-verifier"
IMAGE_ENV = "PRACTICE_VERIFIER_IMAGE"


def runtime_contract():
    from .runtime_identity import code_bytes
    raw = code_bytes(CONTRACT)
    if len(raw) > 65536:
        raise ValueError("Private verifier descriptor exceeds its bound")
    value = parse_json(raw)
    if (type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or value.get("kind") != "unaltraweb-private-practice-verifier"
            or value.get("origin") != "prepared-image" or value["provider"]["name"] != "unaltracaptura-qgis"
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["provider"]["version"])
            or not lifecycle.IMAGE_ID.fullmatch(value["provider"]["installed_revision"])
            or not lifecycle.IMAGE_ID.fullmatch(value["controller"]["image_id"])
            or not lifecycle.IMAGE_ID.fullmatch(value["engine"]["image_id"])
            or set(value["profiles"]) != {"qgis-practice-v1", "qgis-practice-v2"}
            or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in value["profiles"].values())
            or not re.fullmatch(r"[0-9a-f]{40}", value["release"]["source_commit"])
            or not lifecycle.IMAGE_ID.fullmatch(value["release"]["practice_producer_revision"])
            or not re.fullmatch(r"[0-9a-f]{64}", value["release"]["wheel"]["sha256"])
            or type(value["release"]["wheel"]["bytes"]) is not int or value["release"]["wheel"]["bytes"] <= 0
            or value["acquisition"] != {"visibility": "private", "prepared_by": "hub", "implicit_pull": False,
                                        "public_web_contains_provider_package": False}):
        raise ValueError("Invalid private verifier descriptor")
    return value


def validate_schema_identity(value, contract, profile):
    package = value.get("installed_package", {})
    provider = contract["provider"]
    if (value.get("ok") is not True or value.get("profile") != profile
            or value.get("schema_sha256") != contract["profiles"][profile]
            or any(package.get(key) != provider[key if key != "revision" else "installed_revision"] for key in ("name", "version", "revision"))):
        raise ValueError("Native private verifier package/profile differs from the accepted image contract")


def selected_image():
    from .runtime_identity import active_runtime
    runtime = active_runtime()
    contract = runtime.practice_verifier_contract if runtime else runtime_contract()
    expected = contract["controller"]["image_id"]
    selected = runtime.workers[WORKER] if runtime else {"reference": os.environ.get(IMAGE_ENV) or expected, "expected_image_id": expected}
    if selected["expected_image_id"] != expected or not lifecycle.immutable_reference(selected["reference"]):
        raise ValueError("Private verifier selection differs from the accepted prepared-image contract")
    observed = lifecycle.inspect_image(selected["reference"], expected)
    if observed["state"] != "matched":
        raise RuntimeError(f"Private QGIS verifier runtime is {observed['state']}: {expected}; authenticated hub preparation is required (no pull/build attempted)")
    if (observed.get("os"), observed.get("architecture")) != (contract["controller"]["os"], contract["controller"]["architecture"]):
        raise RuntimeError("Private QGIS verifier platform differs from the accepted runtime")
    return contract, observed


def _arguments(operation, workspace, *, profile=None, bundle=None, sha256=None, selected=(), output=None):
    if operation == "schema":
        if profile not in {"qgis-practice-v1", "qgis-practice-v2"} or any((bundle, sha256, selected, output)):
            raise ValueError("Select one explicit verifier schema profile")
        return ["practice-schema", "--profile", profile]
    if operation not in {"check", "reopen"} or profile is not None:
        raise ValueError("Unsupported native practice verifier operation")
    safe_path(bundle)
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Native practice check requires the exact sender SHA-256")
    if (not isinstance(selected, (tuple, list)) or not 1 <= len(selected) <= 64
            or any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9._-]{0,79}", value) for value in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("Native practice selection must contain bounded unique product IDs")
    arguments = ["practice-" + operation, "--workspace", workspace, "--path", bundle, "--sha256", sha256]
    for value in selected:
        arguments.extend(["--select", value])
    if operation == "reopen":
        safe_path(output)
        arguments.extend(["--output", output])
    elif output is not None:
        raise ValueError("Read-only verification does not accept an output path")
    return arguments


def call(project, operation, *, profile=None, bundle=None, sha256=None, selected=(), output=None):
    from .runtime_identity import active_runtime
    from .site_tools import _cleanup_timed_out_workers, _docker_host_project
    project = Path(project)
    if not project.is_absolute():
        raise ValueError("Private verifier requires an explicit absolute consumer")
    project = project.resolve(strict=True)
    runtime = active_runtime()
    host = _docker_host_project(project)
    if str(Path(host)) != host or ".." in Path(host).parts:
        raise ValueError("Private verifier host mapping must be normalized")
    if runtime is None and host != str(project):
        bound = os.environ.get("MCP_CONSUMER_WORKSPACE", "")
        if not bound or Path(bound).resolve() != project:
            raise ValueError("Private verifier host mapping belongs to another or unknown consumer")
    arguments = _arguments(operation, host, profile=profile, bundle=bundle, sha256=sha256, selected=selected, output=output)
    contract, observed = selected_image()
    if operation == "reopen":
        engine = contract["engine"]["image_id"]
        if lifecycle.inspect_image(engine, engine)["state"] != "matched":
            raise RuntimeError("Private QGIS reopen engine is not prepared; the hub must prepare " + engine)
    token = uuid.uuid4().hex
    project_id = hashlib.sha256(host.encode()).hexdigest()[:16]
    session = runtime.session_id if runtime else os.environ.get("UNALTRAWEB_RUNTIME_SESSION", "")
    command = ["docker", "create", "--rm", "--pull", "never", "--network", "none", "--init", "--read-only",
               "--cpus", "2", "--memory", "4g", "--pids-limit", "512", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912", "--user", f"{os.getuid()}:{os.getgid()}",
               "--name", "unaltraweb-practice-verifier-" + token, "--label", "io.context.mcp-factory=unaltraweb",
               "--label", "io.context.mcp-role=" + ROLE, "--label", "io.context.mcp-project=" + project_id,
               "--label", "io.context.mcp-worker-token=" + token, "-e", "HOME=/tmp"]
    if session:
        if not lifecycle.SESSION_ID.fullmatch(session):
            raise ValueError("Invalid native verifier session binding")
        command.extend(["--label", "io.context.mcp-session=" + session])
    mounts = []
    if operation != "schema":
        command.extend(["--mount", docker_bind_mount(host, host, readonly=operation == "check"), "--workdir", host])
        mounts.append({"source": host, "target": host, "readonly": operation == "check"})
    else:
        command.extend(["--workdir", "/tmp"])
    if operation == "reopen":
        socket = Path(os.environ.get("UNALTRAWEB_DOCKER_SOCKET", "/var/run/docker.sock")).resolve(strict=True)
        if socket.is_relative_to(project):
            raise ValueError("Reopen Docker socket must be outside the selected workspace")
        command.extend(["--group-add", str(socket.stat().st_gid), "--mount", docker_bind_mount(socket, "/var/run/docker.sock")])
        mounts.append({"source": str(socket), "target": "/var/run/docker.sock", "readonly": False})
    command.extend(["--entrypoint", "python3", observed["observed_image_id"], "-I", "-B", "-m", "veure_qgis_mcp.cli", *arguments])
    created = run_process(command, timeout_seconds=30, output_limit=65536)
    if created.returncode or created.timed_out or created.stdout_truncated or created.stderr_truncated:
        raise RuntimeError("Cannot start the prepared private verifier: " + created.stderr[-2000:])
    cid = created.stdout.strip()
    if not lifecycle.CONTAINER_ID.fullmatch(cid):
        raise RuntimeError("Private verifier did not return an exact container ID")
    completed = None
    cleanup = {"ok": True, "resources_released": False, "container_id": cid}
    try:
        completed = run_process(["docker", "start", "--attach", cid], timeout_seconds=300 if operation == "reopen" else 120,
                                output_limit=1024*1024)
    finally:
        if lifecycle.inspect_container(cid) is not None:
            cleanup = {**_cleanup_timed_out_workers(role=ROLE, project_id=project_id, token=token), "container_id": cid}
        cleanup["resources_released"] = lifecycle.inspect_container(cid) is None
    if not cleanup.get("ok") or not cleanup["resources_released"]:
        raise RuntimeError("Private verifier exact teardown is unconfirmed: " + cid)
    if completed.returncode or completed.timed_out or completed.stdout_truncated or completed.stderr_truncated:
        raise RuntimeError("Native private verifier refused or exceeded its bound: " + (completed.stderr or completed.stdout)[-3000:])
    value = parse_json(completed.stdout.encode())
    if value.get("ok") is not True:
        raise RuntimeError("Native private verifier did not certify this operation")
    if operation == "schema":
        validate_schema_identity(value, contract, profile)
    origin = {"kind": "prepared-image", "controller": observed, "release": contract["release"],
              "execution": {"container_id": cid, "operation": operation, "mounts": mounts,
                            "network": "none", "cpus": 2, "memory_mib": 4096, "pids": 512,
                            "timeout_seconds": 300 if operation == "reopen" else 120, "cleanup": cleanup}}
    return {"result": value, "origin": origin}
