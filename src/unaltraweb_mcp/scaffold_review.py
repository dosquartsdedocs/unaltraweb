"""Conservative, hash-bound scaffold resolutions; transactions stay in site_tools.

No arbitrary replacement bytes or force mode. Local ignore order is retained;
workflow edits replace only declared scalar pins and retain required controls.
"""
from __future__ import annotations

import copy
import hashlib
import json

LIMIT = 128 * 1024
PINS = {
    ".github/workflows/source-checks.yml": (
        ("jobs", "public-sources", "env", "SOURCE_CHECK_IMAGE"),
        ("jobs", "public-sources", "env", "SOURCE_CHECK_PACKAGE"),
    ),
    ".github/workflows/deploy.yml": (
        ("jobs", "deploy", "uses"), ("jobs", "deploy", "with", "manual-pdf-image"),
        ("jobs", "deploy", "with", "vegavisuals-sha"),
    ),
}
MODES = {".gitignore": ("keep", "prepend-package"), **{path: ("pins-only",) for path in PINS}}
HASH_FIELDS = ("baseline_sha256", "local_sha256", "payload_sha256", "result_sha256")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(raw):
    if len(raw) > LIMIT or b"\0" in raw:
        raise ValueError("Scaffold review requires bounded regular UTF-8 text")
    return raw.decode("utf-8")


def _value(document, path):
    for part in path:
        document = document[part]
    return document


def _without_pins(document, paths):
    result = copy.deepcopy(document)
    for path in paths:
        _value(result, path[:-1])[path[-1]] = "<reviewed-package-pin>"
    return result


def _required_controls(local, package):
    if isinstance(package, dict):
        return isinstance(local, dict) and all(key in local and _required_controls(local[key], value) for key, value in package.items())
    if isinstance(package, list):
        # Required steps must remain exact and ordered. Extra author steps/jobs
        # are preserved, never silently rewritten as part of a pin update.
        if not isinstance(local, list):
            return False
        remaining = iter(local)
        return all(any(item == expected for item in remaining) for expected in package)
    return type(local) is type(package) and local == package


def _workflow_pins(path, local, payload):
    import yaml
    import re
    class WorkflowLoader(yaml.SafeLoader):
        yaml_implicit_resolvers = {key: [(tag, pattern) for tag, pattern in values if tag != "tag:yaml.org,2002:bool"]
                                   for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()}
    WorkflowLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))
    def mapping(loader, node, deep=False):
        value = {}
        for key, item in node.value:
            name = loader.construct_object(key, deep=deep)
            if name in value:
                raise ValueError("Duplicate workflow key")
            value[name] = loader.construct_object(item, deep=deep)
        return value
    WorkflowLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    def load(body):
        return yaml.load(body, Loader=WorkflowLoader)
    current, incoming = text(local), text(payload)
    for body in (current, incoming):
        tokens = list(yaml.scan(body))
        if len(tokens) > 10000 or any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken, yaml.TagToken)) for token in tokens):
            raise ValueError("Workflow review does not accept aliases, anchors, explicit tags or oversized token trees")
    original, target = load(current), load(incoming)
    node = yaml.compose(current, Loader=WorkflowLoader)
    changes = []
    for parts in PINS[path]:
        found = node
        for part in parts:
            if not isinstance(found, yaml.MappingNode):
                raise ValueError("Workflow pin is not a mapping scalar")
            pairs = [value for key, value in found.value if key.value == part]
            if len(pairs) != 1:
                raise ValueError("Workflow pin path is missing or ambiguous")
            found = pairs[0]
        replacement = _value(target, parts)
        if (not isinstance(found, yaml.ScalarNode) or found.tag != "tag:yaml.org,2002:str"
                or found.style not in (None, "'", '"') or not isinstance(replacement, str)
                or "\n" in found.value or "\r" in found.value):
            raise ValueError("Workflow pin must be a single-line string scalar")
        changes.append((found.start_mark.index, found.end_mark.index, json.dumps(replacement)))
    for start, end, replacement in sorted(changes, reverse=True):
        current = current[:start] + replacement + current[end:]
    resolved = load(current)
    if _without_pins(original, PINS[path]) != _without_pins(resolved, PINS[path]):
        raise ValueError("Workflow resolution changed non-pin author behavior")
    if not _required_controls(resolved, target):
        raise ValueError("Workflow lacks required package controls; pins-only resolution is insufficient")
    for key in ("on", "permissions", "concurrency"):
        if key in target and resolved.get(key) != target[key]:
            raise ValueError("Workflow changes required trigger/permission/concurrency controls")
    for name, required_job in target["jobs"].items():
        if set(resolved["jobs"][name]) - set(required_job) - {"name"}:
            raise ValueError("Workflow adds execution modifiers to a required job")
    return current.encode("utf-8")


def resolve(path, mode, local, payload):
    if path not in MODES or mode not in MODES[path]:
        raise ValueError("Unsupported scaffold resolution path or mode")
    text(local)
    text(payload)
    if mode == "keep":
        return local
    if mode == "prepend-package":
        if local.startswith(b"\xef\xbb\xbf"):
            raise ValueError("Prepending to a BOM-prefixed ignore file changes its first rule; review keep instead")
        return payload + (b"" if payload.endswith(b"\n") else b"\n") + local
    import yaml
    try:
        return _workflow_pins(path, local, payload)
    except (KeyError, TypeError, RecursionError, yaml.YAMLError) as exc:
        raise ValueError("Unsupported workflow structure for pins-only review") from exc


def options(path, baseline_sha256, local, payload):
    result = []
    for mode in MODES.get(path, ()):
        try:
            resolved = resolve(path, mode, local, payload)
        except (ValueError, UnicodeError):
            continue
        result.append({"path": path, "mode": mode, "baseline_sha256": baseline_sha256,
                       "local_sha256": sha(local), "payload_sha256": sha(payload), "result_sha256": sha(resolved),
                       "content": resolved.decode("utf-8")})
    return result


def validate_review(review, base_plan_sha256, available):
    if (not isinstance(review, dict) or set(review) != {"schema_version", "kind", "base_plan_sha256", "files"}
            or type(review["schema_version"]) is not int or review["schema_version"] != 1
            or review["kind"] != "unaltraweb-scaffold-review" or review["base_plan_sha256"] != base_plan_sha256
            or not isinstance(review["files"], list) or not 1 <= len(review["files"]) <= len(MODES)):
        raise ValueError("Scaffold review is invalid or stale; prepare a fresh base plan")
    result, seen = [], set()
    for entry in review["files"]:
        if (not isinstance(entry, dict) or set(entry) != {"path", "mode", "reason", *HASH_FIELDS}
                or not isinstance(entry.get("path"), str) or entry["path"] in seen
                or not isinstance(entry.get("reason"), str) or not 1 <= len(entry["reason"].strip()) <= 512
                or "\0" in entry["reason"]):
            raise ValueError("Invalid or duplicate scaffold resolution entry")
        candidate = next((row for row in available if all(entry.get(key) == row.get(key) for key in ("path", "mode", *HASH_FIELDS))), None)
        if candidate is None:
            raise ValueError("Resolution does not match the exact baseline/local/payload/result candidate")
        seen.add(entry["path"])
        result.append({**entry, "content": candidate["content"]})
    return result


def history(value):
    """Retain bounded receipts, never treat them as replacement-file authority."""
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > len(MODES):
        raise ValueError("Invalid scaffold resolution history")
    for path, row in value.items():
        if (path not in MODES or not isinstance(row, dict)
                or set(row) != {"mode", "reason", "base_plan_sha256", *HASH_FIELDS}
                or row["mode"] not in MODES[path] or not isinstance(row["reason"], str) or len(row["reason"]) > 512):
            raise ValueError("Invalid scaffold resolution receipt")
        import re
        for key in ("base_plan_sha256", *HASH_FIELDS):
            if not isinstance(row[key], str) or not re.fullmatch(r"[0-9a-f]{64}", row[key]):
                if key != "baseline_sha256" or row[key] != "":
                    raise ValueError("Invalid scaffold resolution receipt hash")
    return copy.deepcopy(value)
