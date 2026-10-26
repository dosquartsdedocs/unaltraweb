"""Controller-only consumer advice, separate from frozen retained-PDF checkers.

The distribution/checker module remains byte-identical to the selected core and
PDF worker. Native Git gem selection is a controller/scaffold concern, not a
reason to silently broaden that independently published checker closure.
"""
from __future__ import annotations

from pathlib import Path
import re

from . import distribution as base
from .editorial_sources import Reader


def consumer_core_policy():
    value = base._strict_json(Path(__file__).with_name("consumer-core.json"))
    if (not isinstance(value, dict) or set(value) != {"schema_version", "kind", "core_sha", "gem_version"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["kind"] != "unaltraweb-consumer-core"
            or not isinstance(value["core_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["core_sha"])
            or not isinstance(value["gem_version"], str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["gem_version"])):
        raise ValueError("Invalid controller consumer-core policy")
    return value


def consumer_integration():
    value = base.consumer_integration()
    policy = consumer_core_policy()
    if policy["core_sha"] != value["core_sha"]:
        raise ValueError("Consumer-core policy differs from the immutable BOM core selection")
    value["core_gem_version"] = policy["gem_version"]
    return value


def distribution_doctor(*, project=None, factory=None, check_docker=False):
    result = base.distribution_doctor(project=project, factory=factory, check_docker=check_docker)
    integration = consumer_integration()
    result["consumer_integration"] = integration
    version = integration["core_gem_version"]
    if project is None or version == base.component("gem")["version"]:
        return result
    for index, finding in enumerate(result["findings"]):
        if finding["code"] != "UW-DIST-PROJECT-GEM-PIN":
            continue
        with Reader(Path(project).expanduser().resolve()) as reader:
            gemfile = reader.text("Gemfile", optional=True) or ""
            lock = reader.text("Gemfile.lock", optional=True) or ""
        declaration = base._ruby_without_comments(base._gemfile_declaration(gemfile, "unaltraweb"))
        exact = bool(re.search(rf"(?m)^\s*gem\s+['\"]unaltraweb['\"]\s*,\s*['\"](?:=\s*)?{re.escape(version)}['\"]", declaration))
        repositories = re.findall(r"\bgit:\s*['\"]([^'\"]+)['\"]", declaration)
        references = re.findall(r"\bref:\s*['\"]([^'\"]+)['\"]", declaration)
        repository = repositories[0] if len(repositories) == 1 else ""
        reference = references[0] if len(references) == 1 else ""
        locked = re.search(r"(?m)^\s{2}unaltraweb \(= ([^)]+)\)!?\s*$", lock)
        locked_version = locked.group(1) if locked else ""
        lock_repository, revision, lock_ref, spec_version = base._bundler_git_pin(lock, "unaltraweb")
        good = (exact and repository == lock_repository == integration["core_repository"]
                and reference == revision == lock_ref == integration["core_sha"]
                and locked_version == spec_version == version)
        actual = {"version_exact": exact, "repository": "ambiguous" if len(repositories) > 1 else repository or "missing",
                  "gemfile_revision": "ambiguous" if len(references) > 1 else reference or "missing",
                  "lock_version": locked_version or "missing", "lock_repository": lock_repository or "missing",
                  "lock_revision": revision or "missing", "lock_ref": lock_ref or "missing", "lock_spec_version": spec_version or "missing"}
        result["findings"][index] = base._finding(finding["code"], "info" if good else "warning",
            {"version": version, "repository": integration["core_repository"], "revision": integration["core_sha"]}, actual,
            "No action required." if good else "Use scaffold_sync to restore the reviewed consumer integration tuple.", component_id="gem")
    result["summary"] = {severity: sum(row["severity"] == severity for row in result["findings"]) for severity in ("error", "warning", "info")}
    return result
