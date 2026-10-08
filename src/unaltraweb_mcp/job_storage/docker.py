"""Bounded native Docker operations; never access a private host Mountpoint.

Object names originate in the private registry. A protocol UUID supplied to an
MCP tool is resolved and authorized by the manager before reaching this layer.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import re
from typing import Any

from ..processes import run_process
from ..runtime_lifecycle import image_reference
from .contract import HASH_RE, StorageError, canonical, parse, require

VOLUME_RE = re.compile(r"(?:gacontext-job-|unaltraweb-storage-capacity-)[0-9a-f]{32}\Z")
CONTAINER_NAME_RE = re.compile(r"unaltraweb-w1-[0-9a-f]{32}\Z")
VOLUME_FORMAT = ('{"name":{{json .Name}},"driver":{{json .Driver}},"scope":{{json .Scope}},'
                 '"options":{{json .Options}},"labels":{{json .Labels}},"created_at":{{json .CreatedAt}}}')
CONTAINER_FORMAT = ('{"id":{{json .Id}},"image_id":{{json .Image}},"running":{{json .State.Running}},'
                    '"status":{{json .State.Status}},"pid":{{json .State.Pid}},"exit_code":{{json .State.ExitCode}},'
                    '"started_at":{{json .State.StartedAt}},"labels":{{json .Config.Labels}},'
                    '"mounts":{{json .Mounts}},"network_mode":{{json .HostConfig.NetworkMode}}}')
IMAGE_FORMAT = ('{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}},'
                '"revision":{{if .Config.Labels}}{{json (index .Config.Labels "org.opencontainers.image.revision")}}{{else}}null{{end}}}')


def docker_time(value: str) -> str:
    try:
        instant = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(instant.tzinfo is not None, "Docker creation time has no timezone", "storage-observation-unknown")
        return instant.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, TypeError, AttributeError) as exc:
        raise StorageError("storage-observation-unknown", "Docker creation time is not observable") from exc


class Docker:
    def __init__(self, *, environment: dict[str, str] | None = None):
        self.environment = dict(os.environ if environment is None else environment)

    def call(self, arguments: list[str], *, timeout: float = 30, input_data: bytes | None = None,
             guard_fds: tuple[int, ...] = (), output_limit: int = 1024*1024, input_chunks=None, stdout_consumer=None):
        try:
            return run_process(["docker", *arguments], env=self.environment, timeout_seconds=timeout,
                               input_data=input_data, input_chunks=input_chunks, stdout_consumer=stdout_consumer,
                               output_limit=output_limit, pass_fds=guard_fds)
        except OSError as exc:
            raise StorageError("storage-observation-unknown", "Docker is unavailable") from exc

    def object(self, arguments: list[str]) -> dict[str, Any]:
        result = self.call(arguments)
        require(not result.returncode and not result.timed_out and not result.stdout_truncated and not result.stderr_truncated,
                "Docker observation failed or exceeded its bound", "storage-observation-unknown")
        return parse(result.stdout.encode())

    def daemon(self) -> str:
        value = self.object(["info", "--format", '{"id":{{json .ID}}}']).get("id")
        require(isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9:._-]{8,128}", value) is not None,
                "Docker daemon identity is unknown", "storage-observation-unknown")
        return value

    def require_daemon(self, expected: str) -> None:
        require(self.daemon() == expected, "Selected Docker daemon changed", "storage-binding-mismatch")

    def inspect(self, kind: str, name: str) -> dict[str, Any] | None:
        if kind == "volume":
            require(VOLUME_RE.fullmatch(name) is not None, "Invalid registered volume name")
            template = VOLUME_FORMAT
        elif kind == "container":
            require(HASH_RE.fullmatch(name) is not None or CONTAINER_NAME_RE.fullmatch(name) is not None,
                    "Container observation requires an exact ID or manager-issued name")
            template = CONTAINER_FORMAT
        elif kind == "image":
            image_reference(name)
            template = IMAGE_FORMAT
        else:
            raise StorageError("invalid-storage-contract", "Unsupported Docker object kind")
        result = self.call([kind, "inspect", "--format", template, name])
        require(not result.timed_out and not result.stdout_truncated and not result.stderr_truncated,
                "Docker observation exceeded its bound", "storage-observation-unknown")
        if result.returncode:
            message = result.stderr.casefold()
            if f"no such {kind}" in message or "no such object" in message:
                return None
            raise StorageError("storage-observation-unknown", "Docker object cannot be observed")
        return parse(result.stdout.encode())

    def prepared_image(self, reference: str, expected: str = "") -> dict[str, Any]:
        value = self.inspect("image", reference)
        require(value is not None and isinstance(value.get("id"), str)
                and re.fullmatch(r"sha256:[0-9a-f]{64}", value["id"]) is not None,
                "Prepare the exact selected storage/worker image explicitly", "storage-image-unavailable")
        require(not expected or expected == value["id"], "Prepared image differs from the expected ID", "storage-image-mismatch")
        if reference.startswith("sha256:"):
            require(reference == value["id"], "Prepared image ID differs from its selection", "storage-image-mismatch")
        if "@sha256:" in reference:
            require(reference in (value.get("repo_digests") or []), "Prepared image digest differs from its selection", "storage-image-mismatch")
        return value

    def create_volume(self, name: str, labels: dict[str, str], *, guard_fds: tuple[int, ...] = ()) -> dict[str, Any]:
        require(self.inspect("volume", name) is None, "Never adopt or recreate an existing volume name", "storage-volume-conflict")
        command = ["volume", "create", "--driver", "local"]
        for key, value in sorted(labels.items()):
            require(isinstance(key, str) and isinstance(value, str) and "\n" not in key + value,
                    "Invalid volume label")
            command.extend(["--label", f"{key}={value}"])
        result = self.call([*command, name], guard_fds=guard_fds)
        require(not result.returncode and not result.timed_out and result.stdout.strip() == name,
                "Volume allocation did not complete; retain its journal for recovery", "storage-allocation-incomplete")
        observed = self.inspect("volume", name)
        require(observed is not None and observed.get("name") == name and observed.get("driver") == "local"
                and observed.get("scope") == "local" and not observed.get("options") and observed.get("labels") == labels,
                "Allocated volume has unknown ownership or storage options", "storage-volume-mismatch")
        docker_time(observed["created_at"])
        return observed

    def verify_volume(self, expected: dict[str, Any]) -> dict[str, Any] | None:
        actual = self.inspect("volume", expected["name"])
        if actual is None:
            return None
        require(all(actual.get(key) == expected.get(key) for key in ("name", "driver", "scope", "options", "labels", "created_at")),
                "Volume incarnation, labels or storage configuration changed", "storage-volume-mismatch")
        return actual

    def attachments(self, name: str) -> list[dict[str, Any]]:
        require(VOLUME_RE.fullmatch(name) is not None, "Invalid registered volume name")
        result = self.call(["ps", "-a", "-q", "--no-trunc", "--filter", "volume=" + name])
        require(not result.returncode and not result.timed_out and not result.stdout_truncated and not result.stderr_truncated,
                "Container attachment inventory is incomplete", "storage-observation-unknown")
        identifiers = result.stdout.split()
        require(len(identifiers) <= 256 and len(identifiers) == len(set(identifiers))
                and all(HASH_RE.fullmatch(identifier) is not None for identifier in identifiers),
                "Container attachment inventory exceeds its bound", "storage-observation-unknown")
        attached = []
        for identifier in identifiers:
            info = self.inspect("container", identifier)
            if info is not None and any(mount.get("Type") == "volume" and mount.get("Name") == name for mount in info["mounts"]):
                attached.append(info)
        return attached

    def remove_volume(self, expected: dict[str, Any], daemon_id: str, *, guard_fds: tuple[int, ...] = ()) -> bool:
        """Low-level final step; the manager must already have fenced/verified retention."""
        self.require_daemon(daemon_id)
        if self.verify_volume(expected) is None:
            return False
        require(not self.attachments(expected["name"]), "A container still references this volume", "storage-busy")
        self.require_daemon(daemon_id)
        # Exact name, deliberately no force. A concurrent Docker attachment wins.
        result = self.call(["volume", "rm", expected["name"]], guard_fds=guard_fds)
        require(not result.returncode and not result.timed_out,
                "Docker did not confirm volume removal", "storage-release-incomplete")
        self.require_daemon(daemon_id)
        require(self.inspect("volume", expected["name"]) is None,
                "Volume absence was not observed", "storage-release-incomplete")
        return True

    def remove_stopped_container(self, identifier: str, required_labels: dict[str, str]) -> bool:
        require(HASH_RE.fullmatch(identifier) is not None, "Container removal requires an exact ID")
        value = self.inspect("container", identifier)
        if value is None:
            return False
        require(not value["running"] and all((value.get("labels") or {}).get(key) == expected for key, expected in required_labels.items()),
                "Container is busy, foreign or changed", "storage-busy")
        result = self.call(["rm", identifier])
        require(not result.returncode and not result.timed_out and self.inspect("container", identifier) is None,
                "Owned stopped container termination is not confirmed", "storage-release-incomplete")
        return True

    def create_worker(self, *, name: str, image_id: str, request: dict[str, Any],
                      mounts: list[tuple[str, str, bool]], labels: dict[str, str],
                      guard_fds: tuple[int, ...] = (), network: str = "none") -> str:
        require(CONTAINER_NAME_RE.fullmatch(name) is not None, "Worker name must be manager-issued")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is not None, "Worker requires an exact prepared image ID")
        require(network == "none" or re.fullmatch(r"[0-9a-f]{64}", network) is not None,
                "Worker network must be none or an exact manager-owned network ID")
        require(self.inspect("container", name) is None, "Worker name collision", "storage-resource-conflict")
        worker_source = Path(__file__).with_name("worker.py").read_text(encoding="utf-8")
        bundle_source = Path(__file__).with_name("bundles.py").read_text(encoding="utf-8")
        from .contract import sha256
        code = ("import importlib.util,sys;"
                "sys.path.extend(['/opt/unaltraweb/src'] if importlib.util.find_spec('unaltraweb_mcp') is None else []);"
                "_bundle_scope={'__name__':'unaltraweb_w1_bundle_checker','_SOURCE_SHA256':" + repr(sha256(bundle_source.encode())) + "};"
                "exec(" + repr(bundle_source) + ",_bundle_scope);domain_check=_bundle_scope['check'];exec(" + repr(worker_source) + ")")
        require(len(code.encode()) < 96*1024 and len(canonical(request)) < 64*1024, "Worker control exceeds its argument bound")
        command = ["create", "--name", name, "--interactive", "--pull", "never", "--network", network,
                   "--read-only", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
                   "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "DAC_OVERRIDE",
                    "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "KILL", "--security-opt", "no-new-privileges",
                   "--user", "0:0", "--log-driver", "local", "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                   "--tmpfs", "/run:rw,nosuid,nodev,size=16777216", "--tmpfs", "/tmp:rw,nosuid,nodev,size=16777216",
                   "--env", "HOME=/tmp", "--env", "UNALTRAWEB_W1_REQUEST=" + canonical(request).decode()]
        for key, value in sorted(labels.items()):
            require(isinstance(key, str) and isinstance(value, str) and "\n" not in key + value, "Invalid worker label")
            command.extend(["--label", f"{key}={value}"])
        for volume, destination, readonly in mounts:
            require(VOLUME_RE.fullmatch(volume) is not None and destination in {"/work", "/work/scratch", "/capacity"}, "Invalid registered worker mount")
            mount = f"type=volume,source={volume},target={destination},volume-nocopy"
            command.extend(["--mount", mount + (",readonly" if readonly else "")])
        command.extend(["--entrypoint", "python3", image_id, "-I", "-c", code])
        result = self.call(command, guard_fds=guard_fds)
        identifier = result.stdout.strip()
        require(not result.returncode and not result.timed_out and HASH_RE.fullmatch(identifier) is not None,
                "Worker creation is incomplete; retain its operation journal", "storage-operation-incomplete")
        observed = self.inspect("container", identifier)
        expected_mounts = {(volume, destination, not readonly) for volume, destination, readonly in mounts}
        actual_mounts = {(item.get("Name"), item.get("Destination"), item.get("RW"))
                         for item in (observed or {}).get("mounts", []) if item.get("Type") == "volume"}
        require(observed is not None and observed["image_id"] == image_id
                and all((observed.get("labels") or {}).get(key) == value for key, value in labels.items())
                and expected_mounts == actual_mounts, "Created worker mounts or identity differ", "storage-binding-mismatch")
        return identifier

    def start_worker(self, identifier: str, *, guard_fds: tuple[int, ...] = (), input_data: bytes | None = None,
                     timeout: float = 1800, input_chunks=None, stdout_consumer=None):
        require(HASH_RE.fullmatch(identifier) is not None, "Starting a worker requires its exact registered ID")
        return self.call(["start", "--attach", "--interactive", identifier], guard_fds=guard_fds,
                         input_data=(input_data or b"") if input_chunks is None else None,
                         input_chunks=input_chunks, stdout_consumer=stdout_consumer, timeout=timeout)
