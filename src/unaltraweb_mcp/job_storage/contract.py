"""Bounded W1 envelopes. Validation is separate from native storage authority.

Normative schema/reference: gaContExt 83cb0d3e2f424759475ae70b423a0f8dca8520b2.
The schema is byte-preserved; this owner performs its own native observations
and mutations rather than treating the upstream read-only planner as an executor.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .. import artifact_handoff_v1 as handoff

CONTRACT = "docker-job-volumes-v1"
SCHEMA_SHA256 = "25e2bf047715e170ad8975ca3fd81d0597bdb0fead9ac6c52e8a777b3fb6434c"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "job-storage-v1.schema.json"
MAX_DOCUMENT = 1024 * 1024
FRESH_SECONDS = 30
ID_RE = re.compile(r"[0-9a-f]{32}\Z")
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
POLICIES = {
    "inputs": ("input-snapshots", "resolved-retention"),
    "results": ("results", "resolved-retention"),
    "exports": ("sealed-products", "resolved-retention"),
    "recovery": ("recovery", "resolved-retention"),
    "scratch": ("regenerable", "on-release"),
}
KINDS = {"gacontext.job-storage-provider": "provider", "gacontext.job-storage-state": "state",
         "gacontext.job-product-retention": "retention", "gacontext.job-storage-binding": "binding",
         "gacontext.job-storage-request": "request"}


class StorageError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message[:4096])


def require(condition: bool, message: str, code: str = "invalid-storage-contract") -> None:
    if not condition:
        raise StorageError(code, message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse(raw: bytes) -> dict[str, Any]:
    require(isinstance(raw, bytes) and len(raw) <= MAX_DOCUMENT, "Storage JSON exceeds its byte limit")
    try:
        return handoff.parse_json(raw)
    except handoff.HandoffError as exc:
        raise StorageError("invalid-storage-contract", str(exc)) from exc


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def timestamp(value: str) -> dt.datetime:
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value) is not None,
            "Storage times must be UTC RFC3339 with Z")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise StorageError("invalid-storage-contract", "Invalid storage time") from exc


def fresh(value: str, observed: str | None = None) -> bool:
    return 0 <= (timestamp(observed or now()) - timestamp(value)).total_seconds() <= FRESH_SECONDS


def relative_path(value: str) -> str:
    try:
        return handoff.safe_path(value)
    except handoff.HandoffError as exc:
        raise StorageError("storage-path-invalid", str(exc)) from exc


@lru_cache(maxsize=1)
def schema() -> dict[str, Any]:
    raw = SCHEMA_PATH.read_bytes()
    require(sha256(raw) == SCHEMA_SHA256, "The packaged W1 schema differs from its pinned authority")
    return parse(raw)


def shape(value: Any, rule: dict[str, Any], definitions: dict[str, Any]) -> None:
    if "$ref" in rule:
        return shape(value, definitions[rule["$ref"].removeprefix("#/$defs/")], definitions)
    if "oneOf" in rule:
        matches = 0
        for alternative in rule["oneOf"]:
            try:
                shape(value, alternative, definitions)
                matches += 1
            except StorageError:
                pass
        require(matches == 1, "Expected exactly one supported W1 shape")
    types = {"object": dict, "array": list, "integer": int, "string": str, "boolean": bool, "null": type(None)}
    if "type" in rule:
        require(type(value) is types[rule["type"]], "Invalid W1 field type")
    for constraint in ("const", "enum"):
        if constraint in rule:
            choices = [rule[constraint]] if constraint == "const" else rule[constraint]
            require(any(type(value) is type(choice) and value == choice for choice in choices), "Unsupported W1 field value")
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        require(set(rule.get("required", [])) <= value.keys(), "Missing W1 fields")
        if rule.get("additionalProperties") is False:
            require(value.keys() <= properties.keys(), "Unknown W1 fields")
        for key, item in value.items():
            if key in properties:
                shape(item, properties[key], definitions)
    elif isinstance(value, list):
        require(rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", 4096), "W1 array exceeds bounds")
        if rule.get("uniqueItems"):
            require(len({canonical(item) for item in value}) == len(value), "Duplicate W1 array entries")
        for item in value:
            shape(item, rule["items"], definitions)
    elif isinstance(value, str):
        require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", 8192), "W1 string exceeds bounds")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"], value) is not None, "Invalid W1 field spelling")
        if rule.get("format") == "date-time":
            timestamp(value)
    elif type(value) is int:
        require(rule.get("minimum", value) <= value <= rule.get("maximum", value), "W1 integer exceeds bounds")


def labels(state: dict[str, Any], volume: dict[str, Any]) -> dict[str, str]:
    fields = {"contract": CONTRACT, "registry": state["registry_id"], "provider": state["provider"],
              "binding": state["binding_id"], "job": state["job_id"], "volume": volume["id"], "role": volume["role"]}
    return {"io.context.mcp-storage." + key: value for key, value in fields.items()}


def validate(value: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(value, dict) and isinstance(value.get("kind"), str) and value["kind"] in KINDS,
            "Unsupported W1 document")
    # Bound depth/nodes before recursive shape evaluation or canonical encoding.
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(depth <= 32 and count <= 100000, "W1 document exceeds depth/node bounds")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    kind = KINDS[value["kind"]]
    definitions = schema()["$defs"]
    shape(value, definitions[kind], definitions)
    require(len(canonical(value)) <= MAX_DOCUMENT, "W1 document exceeds its byte limit")
    if kind == "provider":
        policies = {item["path"]: (item["role"], item["cleanup"]) for item in value["path_policies"]}
        require(policies == POLICIES, "W1 must classify its five roots exactly")
    elif kind == "state":
        for field in ("leases", "volumes", "products", "holds"):
            identifiers = [item["id"] for item in value[field]]
            require(len(identifiers) == len(set(identifiers)), "Duplicate W1 identities")
        require({item["role"] for item in value["volumes"]} == {"scratch", "retained"}, "W1 requires both volume roles")
        for volume in value["volumes"]:
            require(volume["name"] == "gacontext-job-" + volume["id"], "Volume name differs from its incarnation")
            require(volume["labels"] == labels(value, volume), "Volume labels differ from the registered job")
            require(volume["daemon_id"] == value["daemon_id"], "Volume daemon differs from its job")
            require(timestamp(volume["created_at"]) <= timestamp(volume["observed_at"]), "Volume observation predates creation")
            require(volume["state"] != "absent" or (volume["attachments_complete"] and not volume["attachments"]),
                    "An absent volume cannot have unknown/present attachments")
        for product in value["products"]:
            decision = product["decision"]
            if product["disposition"] == "pending":
                require(decision is None, "Pending product has a completed decision")
            else:
                require(decision is not None and decision["bundle_sha256"] == product["bundle_sha256"], "Decision does not bind the sealed product")
                require(decision["kind"] == ("retention" if product["disposition"] == "acknowledged" else "user-discard"), "Wrong product decision kind")
        inventory = value["protected_inventory"]
        require(inventory["state"] != "verified" or inventory["tree_sha256"] is not None, "Verified inventory needs its digest")
        if value["phase"] == "released":
            require(value["activity"] == "idle" and value["leases_complete"]
                    and all(item["state"] == "released" for item in value["leases"])
                    and all(item["state"] == "absent" for item in value["volumes"])
                    and not value["holds"] and inventory["state"] == "verified" and inventory["unresolved_entries"] == 0
                    and all(item["disposition"] != "pending" and item["decision"]["status"] == "verified" for item in value["products"]),
                    "Released job still has resources or obligations")
    elif kind == "retention":
        relative_path(value["destination"]["path"])
        if value["destination"]["format"] == "directory":
            require(value["destination"]["content_sha256"] == value["bundle_sha256"], "Directory retention must bind the exact bundle")
    elif kind == "binding":
        mounts = value["mounts"]
        roles = {"retained"} if value["access"] == "read-only" else {"retained", "scratch"}
        require(len(mounts) == len(roles) and {item["role"] for item in mounts} == roles, "Invalid access-specific mount set")
        require(len({item["id"] for item in mounts}) == len(mounts), "Duplicate bound volume incarnation")
        require(all(item["name"] == "gacontext-job-" + item["id"] for item in mounts), "Bound volume name mismatch")
    return value


def check_request(request: dict[str, Any], state: dict[str, Any]) -> None:
    validate(request)
    validate(state)
    require(request["kind"] == "gacontext.job-storage-request" and state["kind"] == "gacontext.job-storage-state", "Expected a request and state")
    require(all(request[key] == state[key] for key in ("registry_id", "job_id")), "Request addresses another job", "storage-binding-mismatch")
    if request["operation"] != "status":
        require(request["expected_revision"] == state["revision"] and request["expected_epoch"] == state["epoch"],
                "Storage revision or epoch changed", "storage-revision-conflict")
        require(state["phase"] in ({"open"} if request["operation"] == "seal" else {"open", "draining", "closed"}),
                "Storage admission is closed", "storage-admission-closed")
        if request["operation"] == "seal":
            require(state["activity"] == "idle", "Domain work is not idle", "storage-busy")


def check_binding(binding: dict[str, Any], state: dict[str, Any]) -> None:
    validate(binding)
    validate(state)
    require(binding["kind"] == "gacontext.job-storage-binding", "Expected a W1 binding")
    require(all(binding[key] == state[key] for key in ("registry_id", "job_id", "binding_id", "provider", "provider_sha256", "daemon_id", "epoch")),
            "Storage binding or fencing epoch differs", "storage-binding-mismatch")
    writable = binding["access"] == "read-write"
    require(state["leases_complete"] and state["phase"] in ({"open"} if writable else {"open", "draining", "closed"}),
            "Lease inventory or admission is not eligible", "storage-admission-closed")
    leases = [item for item in state["leases"] if item["id"] == binding["lease_id"]]
    require(len(leases) == 1 and leases[0]["state"] == "active" and leases[0]["kind"] in ({"writer"} if writable else {"reader", "transfer"}),
            "Missing active access lease", "storage-lease-mismatch")
    for mount in binding["mounts"]:
        volume = next(item for item in state["volumes"] if item["role"] == mount["role"])
        require(volume["state"] == "verified" and all(mount[key] == volume[key] for key in ("id", "name", "marker_sha256")),
                "Mount differs from registered volume", "storage-volume-mismatch")
