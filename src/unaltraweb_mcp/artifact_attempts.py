"""Bounded private local intent/observations, never a remote recovery executor."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from . import artifact_handoff_v1 as h, manual_pdf_preview as fs
from .editorial_sources import strict_json

ROOT = "sandbox/artifact-attempts"
MAX_BYTES = 1024**2
MAX_EVENTS = 1024
PHASES = set("intent-retained preflight-started preflight-verified object-check object-absent create-requested create-uncertain upload-observed part-requested part-acknowledged part-uncertain complete-requested complete-acknowledged completion-uncertain put-requested put-acknowledged put-uncertain readback-requested readback-verified readback-uncertain access-requested access-verified access-uncertain abort-requested abort-acknowledged abort-uncertain binding-changed object-verified verified failed".split())
MUTATIONS = {"put-requested", "create-requested", "part-requested", "complete-requested", "abort-requested"}
FIELDS = {"key", "owned_upload", "part_number", "acknowledged_parts", "bytes_acknowledged", "after_phase"}


class EvidenceError(ValueError):
    pass


class TransferFailure(RuntimeError):
    def __init__(self, pointer, phase):
        super().__init__("Artifact transfer failed; inspect the retained local attempt before any explicit retry")
        self.attempt, self.phase = pointer, phase


def require(value, message):
    if not value:
        raise EvidenceError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def event_shape(event, intent, owned):
    require(set(event) == {"sequence", "previous_sha256", "phase", "data"} and event["phase"] in PHASES, "Invalid local attempt event")
    data = event["data"]
    require(isinstance(data, dict) and data.keys() <= FIELDS, "Unknown local attempt fields")
    if "key" in data:
        require(data["key"] in {row["key"] for row in intent["objects"]}, "Attempt object differs from its source binding")
    if "owned_upload" in data:
        upload = data["owned_upload"]
        require(isinstance(upload, dict) and set(upload) == {"bucket", "key", "upload_id"}
                and upload["bucket"] == intent["destination"]["bucket"] and upload["key"] == data.get("key"), "Unbound owned upload tuple")
        identifier = upload["upload_id"]
        require(isinstance(identifier, str) and 0 < len(identifier) <= 2048
                and all(32 < ord(char) < 127 for char in identifier), "Unqualified owned upload ID")
        if event["phase"] == "upload-observed":
            require(upload["key"] not in owned, "Duplicate owned upload observation")
            owned[upload["key"]] = identifier
        else:
            require(owned.get(upload["key"]) == identifier, "Owned upload ID differs from its observed binding")
    for key in ("part_number", "acknowledged_parts", "bytes_acknowledged"):
        if key in data:
            require(type(data[key]) is int and 0 <= data[key] <= 2 * 1024**3, "Invalid bounded attempt progress")
    require("after_phase" not in data or data["after_phase"] in PHASES, "Unknown failed attempt phase")


def _private(info):
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600, "Attempt records must be private user-owned ordinary files")


class Attempt:
    def __init__(self, project, context, guard):
        self.project, self.guard = project, guard
        self.workspace = h.Workspace(str(project))
        self.directory = self.intent_fd = self.events_fd = None
        self.history, self.owned, self.sequence, self.phase = b"", {}, 0, "intent-retained"
        self.mutation_requested = False
        try:
            fs._require_generated_path(project, Path(ROOT), label="Local artifact attempt evidence")
            parent = fs._open_directory(self.workspace.fd, Path("sandbox"), create=True)
            try:
                try:
                    os.mkdir("artifact-attempts", mode=0o700, dir_fd=parent)
                    os.fsync(parent)
                except FileExistsError:
                    pass
                namespace = os.open("artifact-attempts", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            finally:
                os.close(parent)
            try:
                info = os.fstat(namespace)
                require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, "Attempt namespace must be private")
                identifier = uuid.uuid4().hex
                self.path = ROOT + "/" + identifier
                os.mkdir(identifier, mode=0o700, dir_fd=namespace)
                self.directory = os.open(identifier, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=namespace)
                os.fsync(namespace)
            finally:
                os.close(namespace)
            self.intent = {"kind": "unaltraweb.artifact-attempt", "schema_version": 1, "attempt_id": identifier,
                           "workspace": str(project), "created_at_ns": time.time_ns(), **context}
            self.raw_intent = encoded(self.intent)
            require(len(self.raw_intent) <= 65536, "Attempt intent exceeds its local bound")
            self.intent_sha256 = sha(self.raw_intent)
            for name, raw in (("intent.json", self.raw_intent), ("events.jsonl", b"")):
                fd = os.open(name, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.directory)
                if name == "intent.json":
                    self.intent_fd = fd
                else:
                    self.events_fd = fd
                with os.fdopen(os.dup(fd), "wb") as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
            os.fsync(self.directory)
            self.record("intent-retained")
        except BaseException:
            self.close()
            raise

    def check(self):
        require(encoded(self.intent) == self.raw_intent, "Local attempt binding changed in memory")
        with self.workspace.directory(self.path) as observed:
            require(fs._identity(os.fstat(observed)) == fs._identity(os.fstat(self.directory)), "Attempt directory changed")
        for name, fd, expected in (("intent.json", self.intent_fd, self.raw_intent), ("events.jsonl", self.events_fd, self.history)):
            before = os.fstat(fd)
            _private(before)
            require(before.st_size <= MAX_BYTES and os.pread(fd, MAX_BYTES + 1, 0) == expected
                    and h.signature(before) == h.signature(os.fstat(fd))
                    == h.signature(os.stat(name, dir_fd=self.directory, follow_symlinks=False)), "Local attempt evidence changed")

    def record(self, phase, **data):
        self.check()
        event = {"sequence": self.sequence + 1, "previous_sha256": sha(self.history.splitlines(keepends=True)[-1]) if self.history else self.intent_sha256,
                 "phase": phase, "data": data}
        next_owned = self.owned.copy()
        event_shape(event, self.intent, next_owned)
        raw = encoded(event)
        require(len(raw) <= 8192 and self.sequence < MAX_EVENTS and len(self.history) + len(raw) <= MAX_BYTES, "Local attempt evidence exceeds its bound")
        view = memoryview(raw)
        while view:
            written = os.write(self.events_fd, view)
            require(written > 0, "Local attempt observation could not be written")
            view = view[written:]
        os.fsync(self.events_fd)
        self.history += raw
        self.sequence, self.phase, self.owned = event["sequence"], phase, next_owned
        self.mutation_requested |= phase in MUTATIONS
        self.check()

    def before(self, phase, **data):
        try:
            self.guard()
        except Exception:
            self.record("binding-changed", after_phase=self.phase)
            raise EvidenceError("Artifact source/configuration binding changed") from None
        self.record(phase, **data)

    def pointer(self, *, intact=True):
        return {"path": self.path, "intent_sha256": self.intent_sha256, "events_sha256": sha(self.history),
                "phase": self.phase, "evidence_intact": intact, "remote_mutation_requested": self.mutation_requested}

    def failure(self):
        phase, intact = self.phase, True
        try:
            self.record("failed", after_phase=phase)
        except (ValueError, OSError, h.HandoffError):
            intact = False
        return TransferFailure(self.pointer(intact=intact), phase)

    def close(self):
        for name in ("intent_fd", "events_fd", "directory"):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)
        if getattr(self, "workspace", None) is not None:
            self.workspace.close()
            self.workspace = None


def inspect(project, path, intent_sha256, events_sha256):
    """Read local evidence against retained hashes; never resolve auth or recover."""
    fs._require_git_root(project)
    require(re.fullmatch(r"sandbox/artifact-attempts/[0-9a-f]{32}", path), "Select an exact local attempt directory")
    fs._require_generated_path(project, Path(path), label="Local attempt evidence")
    with closing(h.Workspace(str(project))) as workspace:
        values = []
        for name, expected in (("intent.json", intent_sha256), ("events.jsonl", events_sha256)):
            actual, _, raw = workspace.read(path + "/" + name, MAX_BYTES, collect=True)
            with workspace.directory(path) as directory:
                _private(os.stat(name, dir_fd=directory, follow_symlinks=False))
            require(actual == expected, "Local attempt differs from its retained hash")
            values.append(raw)
        intent = strict_json(values[0].decode())
        require(intent.get("kind") == "unaltraweb.artifact-attempt" and type(intent.get("schema_version")) is int
                and intent["schema_version"] == 1 and intent["attempt_id"] == Path(path).name
                and intent["workspace"] == str(project), "Local attempt has another workspace binding")
        previous, owned, events = intent_sha256, {}, []
        for line in values[1].splitlines(keepends=True):
            require(line.endswith(b"\n") and len(line) <= 8192 and len(events) < MAX_EVENTS, "Incomplete or excessive local attempt evidence")
            event = strict_json(line.decode())
            require(type(event.get("sequence")) is int and event["sequence"] == len(events) + 1
                    and event.get("previous_sha256") == previous, "Broken local attempt observation chain")
            event_shape(event, intent, owned)
            events.append(event)
            previous = sha(line)
        workspace.recheck()
    return {"ok": True, "read_only": True, "local_only": True, "remote_inspection_performed": False,
            "recovery_performed": False, "current_sources_verified": False, "historical_observations_only": True,
            "intent": intent, "events": events, "owned_uploads_observed": owned,
            "intent_sha256": intent_sha256, "events_sha256": events_sha256,
            "guidance": "Compare exact bindings; inspect the selected remote bytes read-only. This record grants no retry, resume, abort or cleanup authority."}
