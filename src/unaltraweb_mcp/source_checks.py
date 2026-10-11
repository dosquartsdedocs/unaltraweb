"""Shared, non-publishing source CI using the existing profile/prose checkers.

Policy is bounded JSON read from Git blobs, never project Python/shell code.
Only exact owned one-shot containers are used; lifecycle stays in the native
adapter implementation. Models, private data and rendered deliveries are not run.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from . import __version__
from .artifact_handoff_v1 import HandoffError, Workspace, check_shape, parse_json, safe_path
from .docker_mount import docker_bind_mount
from .processes import run_process
from .runtime_lifecycle import inspect_container, session_status

CHECKER_IMAGE = "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6"
POLICY_PATH = ".unaltraweb/source-checks.json"
SCHEMA = Path(__file__).with_name("source-check-policy-v1.schema.json")
TEXT_SUFFIXES = {".md", ".markdown", ".html", ".qmd", ".rmd"}
SOURCE_SUFFIXES = TEXT_SUFFIXES | {".json", ".yml", ".yaml", ".py", ".r", ".ipynb", ".model3", ".qml", ".sld", ".svg",
                                  ".sh", ".bash", ".sql", ".js", ".toml", ".ini", ".cfg", ".txt", ".rst", ".mmd", ".puml"}
SOURCE_NAMES = {"Makefile", "Dockerfile", "Containerfile", ".gitignore", ".gitkeep", "README", "LICENSE"}
NOT_RUN = {name: {"state": "not_run", "reason": "Outside source CI; requires the retained inputs/artifacts and its owner checks."}
           for name in ("models", "datasets", "captures", "pdf", "zip")}


def default_policy(profile):
    roots = {"unaltreselfie": ["_pages"], "unaltreprojecte": ["_pages", "_projects", "_outputs"],
             "unaltremanual": ["_chapters", "_pages"], "unaltredocs": ["_documentation", "_pages"]}
    return {"schema_version": 1, "profile": profile, "public_roots": roots[profile],
            "practice_roots": ["practiques", "_practices"],
            "data_roots": ["sandbox", "dist"] + (["assets/pdf"] if profile == "unaltremanual" else []),
            "allow_empty_public_sources": False}


def policy(raw):
    if len(raw) > 65536:
        raise ValueError("Source-check policy exceeds its bound")
    value = parse_json(raw)
    schema = parse_json(SCHEMA.read_bytes())
    check_shape(value, schema, schema["$defs"])
    for key in ("public_roots", "practice_roots", "data_roots"):
        if len(value[key]) != len(set(value[key])):
            raise ValueError("Source-check policy roots must be unique")
        for path in value[key]:
            safe_path(path)
            if path == ".git" or path.startswith(".git/"):
                raise ValueError("Git internals cannot be a source-policy root")
    if value.get("allow_empty_public_sources") and not value.get("empty_reason", "").strip():
        raise ValueError("An intentionally empty public scope needs a reason")
    if not value["public_roots"] and not value.get("allow_empty_public_sources"):
        raise ValueError("Declare the expected public source roots")
    return value


def effective_policy(current, baseline=None):
    result = dict(current)
    for key, mandatory in (("public_roots", []), ("practice_roots", ["practiques", "_practices"]), ("data_roots", ["sandbox", "dist"])):
        result[key] = sorted(set(current[key]) | set((baseline or {}).get(key, [])) | set(mandatory))
    # A PR cannot waive its own old coverage requirement or remove a data root.
    result["allow_empty_public_sources"] = bool(current.get("allow_empty_public_sources")) and (
        baseline is None or bool(baseline.get("allow_empty_public_sources")))
    return result


def under(path, roots):
    return any(path == root or path.startswith(root + "/") for root in roots)


def conservation_inventory(base, head, selected):
    violations, legacy = [], []
    for path, entry in sorted(head.items()):
        reason = "declared data/output root" if under(path, selected["data_roots"]) else ""
        if not reason and under(path, selected["practice_roots"]):
            if (entry["kind"] != "blob" or entry["mode"] not in {"100644", "100755"}
                    or (Path(path).suffix.lower() not in SOURCE_SUFFIXES and Path(path).name not in SOURCE_NAMES)):
                reason = "practice file is not a declared reproduction-source format"
        if reason:
            record = {"path": path, "reason": reason, "object": entry["object"]}
            (legacy if base.get(path) == entry else violations).append(record)
    return {"state": "fail" if violations else "pass", "violations": violations, "legacy_unchanged": legacy,
            "practice_roots": selected["practice_roots"], "data_roots": selected["data_roots"],
            "rule": "Only unchanged same-path/same-mode Git objects are grandfathered; new or changed data is refused."}


def coverage(head, selected, profile, prose):
    expected = {path for path in head if under(path, selected["public_roots"]) and Path(path).suffix.lower() in TEXT_SUFFIXES}
    sources = prose.get("sources", [])
    if not isinstance(sources, list) or any(not isinstance(path, str) for path in sources):
        raise ValueError("Prose checker returned an invalid source inventory")
    skipped = prose.get("coverage", {}).get("skipped", [])
    if not isinstance(skipped, list) or any(not isinstance(row, dict) or not isinstance(row.get("path"), str) for row in skipped):
        raise ValueError("Prose checker returned an invalid exclusion inventory")
    covered = expected & set(sources)
    excluded = [row for row in skipped if row["path"] in expected]
    omitted = sorted(expected - covered - {row["path"] for row in excluded})
    untracked = sorted(set(sources) - set(head))
    issues = []
    if profile.get("profile") != selected["profile"]:
        issues.append("Observed site profile differs from the declared coverage policy")
    if omitted:
        issues.append("Expected source files were neither checked nor explicitly excluded")
    if untracked:
        issues.append("Checkers read sources outside the selected Git snapshot; use a clean clone")
    if not covered and not selected.get("allow_empty_public_sources"):
        issues.append("Public source coverage is unexpectedly empty; _config.yml alone is not coverage")
    figures = profile.get("manual_source_quality", {}).get("figure_typography", {}).get("references", [])
    unverified = [row for row in figures if row.get("state") == "unverified"]
    unsupported = prose.get("coverage", {}).get("unsupported_languages", [])
    return {"state": "fail" if issues else "empty_declared" if not covered else "checked_with_limits" if excluded or unverified or unsupported else "checked",
            "public_roots": selected["public_roots"], "expected": sorted(expected), "covered": sorted(covered),
            "excluded": excluded, "checker_skipped": skipped, "omitted": omitted, "untracked_checker_sources": untracked,
            "empty_reason": selected.get("empty_reason", "") if not covered else "",
            "figures_unverified": unverified, "unsupported_languages": unsupported, "issues": issues,
            "note": "Only listed sources were inspected. Code syntax/execution and full figure/domain validity are not certified."}


def command(arguments, project, *, timeout=30):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return run_process(arguments, cwd=project, env=environment, timeout_seconds=timeout, output_limit=4*1024*1024)


def git(project, *arguments):
    result = command(["git", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(project), *arguments], project)
    if result.returncode or result.timed_out or result.stdout_truncated or result.stderr_truncated:
        raise ValueError("Read-only Git source inspection failed: " + result.stderr[-1000:])
    return result.stdout


def tree(project, revision):
    result = {}
    for record in git(project, "ls-tree", "-rz", "--full-tree", revision).split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, kind, identity = metadata.split()
        safe_path(path)
        result[path] = {"mode": mode, "kind": kind, "object": identity}
    if len(result) > 10000:
        raise ValueError("Source inventory exceeds its bound")
    return result


def policy_from_tree(project, entries, *, optional=False):
    row = entries.get(POLICY_PATH)
    if row is None and optional:
        return None
    if row is None or row["mode"] not in {"100644", "100755"} or row["kind"] != "blob":
        raise ValueError("Commit the regular JSON policy at " + POLICY_PATH)
    return policy(git(project, "cat-file", "blob", row["object"]).encode())


def verify_tree_files(project, entries, paths):
    """Compare checked text/metadata bytes without running Git filters or code."""
    with closing(Workspace(str(project))) as workspace:
        for path in sorted(set(paths)):
            row = entries.get(path)
            if row is None or row["kind"] != "blob" or row["mode"] not in {"100644", "100755"}:
                raise ValueError("Checked sources must be regular versioned files: " + path)
            _, _, raw = workspace.read(path, 4*1024*1024, collect=True)
            identity = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if identity != row["object"]:
                raise ValueError("Checked source differs from the selected Git snapshot: " + path)
        workspace.recheck()


def checker(project, reports, image, name):
    session = uuid.uuid4().hex
    container_name = "unaltraweb-stdio-" + session
    project_id = hashlib.sha256(str(project).encode()).hexdigest()[:16]
    cid_file = reports / (name + ".cid")
    arguments = ["docker", "run", "--rm", "--pull", "never", "--init", "--network", "none", "--read-only",
                 "--cpus", "2", "--memory", "4g", "--pids-limit", "512", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456",
                 "--user", f"{os.getuid()}:{os.getgid()}", "--name", container_name, "--cidfile", str(cid_file),
                 "--label", "io.context.mcp-factory=unaltraweb", "--label", "io.context.mcp-role=stdio",
                 "--label", "io.context.mcp-project="+project_id, "--label", "io.context.mcp-session="+session,
                 "--mount", docker_bind_mount(project, "/workspace", readonly=True),
                 "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1", "--workdir", "/workspace",
                 "--entrypoint", "python3", image, "-I", "-B", "-m", "unaltraweb_mcp.cli",
                 "--project", "/workspace", "mcp", name]
    completed = command(arguments, project, timeout=180)
    report, error = {}, ""
    try:
        report = parse_json(completed.stdout.encode())
    except HandoffError as exc:
        error = str(exc)
    cid = cid_file.read_text().strip() if cid_file.is_file() and not cid_file.is_symlink() else ""
    if not cid:
        observed = inspect_container(container_name)
        cid = observed["id"] if observed else ""
    cleanup = session_status(str(project), session, cid, reap=True) if cid else {"resources_released": False, "state": "unknown"}
    observation = name == "content-approval-inventory"
    valid = report.get("ok") is True
    if observation:
        counts = report.get("status_counts")
        valid = (type(report.get("content_count")) is int and isinstance(counts, dict)
                 and all(isinstance(key, str) and type(value) is int and value >= 0 for key, value in counts.items())
                 and sum(counts.values()) == report["content_count"])
    ok = (completed.returncode == 0 and not completed.timed_out and not completed.stdout_truncated
          and not completed.stderr_truncated and valid and cleanup.get("resources_released") is True)
    return {"state": ("observed" if observation else "pass") if ok else "fail", "exit_code": completed.returncode, "timed_out": completed.timed_out,
            "stdout_truncated": completed.stdout_truncated, "stderr_truncated": completed.stderr_truncated,
            "report": report, "error": error, "stderr": completed.stderr[-2000:], "cleanup": cleanup}


def write_report(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def check(project, base_sha, reports, image=CHECKER_IMAGE):
    project = Path(project).resolve(strict=True)
    reports = Path(reports).absolute()
    if reports.resolve() != reports or reports.is_relative_to(project):
        raise ValueError("Reports must use a new non-symlink directory outside the checkout")
    reports.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": 1, "scope": "public-source-conservation", "publishes": False,
              "runner_version": __version__, "checker_image": image, "not_run": {key: dict(value) for key, value in NOT_RUN.items()},
              "checks": {name: "not_run" for name in ("profile-check", "prose-check", "content-approval-inventory")},
              "coverage": {"state": "not_run"}, "inventory": {"state": "not_run"}, "drafts": {"state": "not_run"}, "ok": False}
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
            raise ValueError("An explicit full baseline commit SHA is required")
        if not re.fullmatch(r"ghcr\.io/dosquartsdedocs/unaltraweb-mcp@sha256:[0-9a-f]{64}", image):
            raise ValueError("Use the public checker image pinned by immutable digest")
        if git(project, "rev-parse", "--show-toplevel").strip() != str(project):
            raise ValueError("Select the clone root explicitly")
        head_sha = git(project, "rev-parse", "HEAD").strip()
        git(project, "merge-base", "--is-ancestor", base_sha, head_sha)
        base, head = tree(project, base_sha), tree(project, head_sha)
        current, previous = policy_from_tree(project, head), policy_from_tree(project, base, optional=True)
        selected = effective_policy(current, previous)
        source_paths = {path for path in head if under(path, selected["public_roots"]) and Path(path).suffix.lower() in TEXT_SUFFIXES}
        controls = (POLICY_PATH, "_config.yml", "context/writing-profile.md",
                    "context/editorial-policy.json", ".unaltraweb/computations.lock.json")
        for path in controls:
            if path not in head and ((project/path).exists() or (project/path).is_symlink()):
                raise ValueError("Checker metadata is not part of the Git snapshot: " + path)
        source_paths.update(path for path in controls if path in head)
        verify_tree_files(project, head, source_paths)
        result.update(base_sha=base_sha, head_sha=head_sha, policy=selected,
                      inventory=conservation_inventory(base, head, selected))
        checks = {}
        for name in ("profile-check", "prose-check", "content-approval-inventory"):
            checks[name] = checker(project, reports, image, name)
            result["checks"][name] = checks[name]["state"]
            write_report(reports / (name + ".json"), checks[name])
        result["checks"] = {name: value["state"] for name, value in checks.items()}
        result["coverage"] = coverage(head, selected, checks["profile-check"]["report"], checks["prose-check"]["report"])
        approvals = checks["content-approval-inventory"]
        observed = approvals["report"]
        result["drafts"] = {"state": approvals["state"], "status_field": observed.get("status_field"),
                            "status_counts": observed.get("status_counts", {}), "content_count": observed.get("content_count"),
                            "records_sample": observed.get("records_sample", []),
                            "sample_is_partial": observed.get("content_count", 0) > len(observed.get("records_sample", [])),
                            "note": "Existing collection inventory, not author approval; private handouts outside these collections are not certified."}
        result["warnings"] = {name: value["report"].get("warnings", []) for name, value in checks.items()}
        verify_tree_files(project, head, source_paths | set(checks["prose-check"]["report"].get("sources", [])))
        result["ok"] = (result["inventory"]["state"] == "pass" and not result["coverage"]["issues"]
                        and all(value["state"] in {"pass", "observed"} for value in checks.values()))
    except (OSError, ValueError, RuntimeError, HandoffError) as exc:
        result["error"] = str(exc)
    write_report(reports / "summary.json", result)
    with (reports / "summary.md").open("x", encoding="utf-8") as stream:
        stream.write("# Public source conservation\n\n" + ("Checks completed within the declared scope.\n" if result["ok"] else "Source checks failed or are incomplete.\n"))
        for key in ("coverage", "inventory", "drafts", "warnings", "error", "not_run"):
            if key in result:
                stream.write("\n## " + key + "\n\n```json\n" + json.dumps(result[key], ensure_ascii=False, indent=2) + "\n```\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--image", default=CHECKER_IMAGE)
    args = parser.parse_args(argv)
    try:
        result = check(args.project, args.base_sha, args.reports, args.image)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "scope": "public-source-conservation", "not_run": NOT_RUN}))
        return 1
    print(json.dumps({"ok": result["ok"], "reports": str(args.reports), "scope": result["scope"]}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
