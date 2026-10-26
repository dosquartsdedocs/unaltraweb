"""Opt-in installed-package scaffold migration and real Git/Bundler acceptance.

Uses synthetic consumers only. Old/new interpreters and an already-prepared Ruby
image are explicit; all evidence is create-only. Native Git/gem fetching during
the Bundler check is explicit, not part of normal site builds or scaffold plans.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def execute(command, *, env=None, timeout=180, expected=0):
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
    if expected is not None and result.returncode != expected:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n{result.stdout[-8000:]}\n{result.stderr[-8000:]}")
    return result


def cli(python, project, *arguments, expected=0):
    result = execute([str(python), "-I", "-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), *arguments], expected=expected)
    return json.loads(result.stdout)


async def mcp_roundtrip(python, project, factory, review, plan_hash):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    def payload(result):
        return result.structuredContent or json.loads("\n".join(row.text for row in result.content if hasattr(row, "text")))
    params = StdioServerParameters(command=str(python), args=["-I", "-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "serve"],
        env={"UNALTRAWEB_FACTORY_DIR": str(factory), "HOME": str(project), "PATH": os.environ["PATH"]})
    async with stdio_client(params) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as client:
            await client.initialize()
            identity = payload(await client.call_tool("runtime_identity", {}))
            assert identity["package"]["mode"] == "installed" and not identity["package"]["drift"]
            result = payload(await client.call_tool("scaffold_sync", {"review": review, "dry_run": False, "confirm_sync": True, "expected_plan_sha256": plan_hash}))
            assert result["ok"] and result["applied"], result
            following = payload(await client.call_tool("site_context", {}))["update_status"]
            assert following["state"] == "current_customized" and not following["update_available"], following
            await client.call_tool("runtime_drain", {"confirm": True})
            return {"identity": identity, "applied": result, "following": following}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-python", "new-python", "output", "factory"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--runtime-image", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    assert root == args.output and root.is_relative_to(args.factory / "tmp") and root.parent.is_dir()
    root.mkdir(mode=0o700)
    project, fresh = root / "upgrade", root / "fresh"
    for python, path in ((args.old_python, project), (args.new_python, fresh)):
        assert cli(python, path, "new-web", "--site-profile", "unaltremanual")["ok"]
    original_baseline = sha(project / ".unaltraweb/scaffold.json")
    ignore = project / ".gitignore"
    ignore.write_bytes(ignore.read_bytes() + b"\n/dist/\n/.unaltracaptura-qgis/jobs/\n/.unaltracaptura-qgis/probes/\n/.unaltracaptura-qgis/render-locks/\n/.unaltracaptura-qgis/runtime/\n/notes/*\n!/notes/public/\n")
    for name in ("source-checks.yml", "deploy.yml"):
        path = project / ".github/workflows" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # A local workflow with the official controls plus an author guard and
        # previous pins; its older package baseline remains untouched.
        current = (fresh / ".github/workflows" / name).read_text()
        current = current.replace("unaltraweb-mcp==0.7.4", "unaltraweb-mcp==0.7.3")
        current += "\n  author-guard:\n    runs-on: ubuntu-latest\n    steps:\n      - run: test -f _config.yml\n"
        path.write_text(current)
    assert sha(project / ".unaltraweb/scaffold.json") == original_baseline
    ignored_before = ignore.read_bytes()
    plan = cli(args.new_python, project, "mcp", "scaffold-sync", expected=None)
    save(root / "initial-plan.json", plan)
    assert not plan["ok"] and {row["path"] for row in plan["conflicts"]} == {".gitignore", ".github/workflows/deploy.yml", ".github/workflows/source-checks.yml"}, plan
    modes = {".gitignore": "keep", ".github/workflows/deploy.yml": "pins-only", ".github/workflows/source-checks.yml": "pins-only"}
    decisions = [{key: value for key, value in row.items() if key != "content"} | {"reason": "Preserve synthetic author rules and controls; accept exact package pins"}
                 for row in plan["resolution_options"] if modes.get(row["path"]) == row["mode"]]
    assert len(decisions) == 3
    review = {"schema_version": 1, "kind": "unaltraweb-scaffold-review", "base_plan_sha256": plan["plan_sha256"], "files": decisions}
    save(root / "review.json", review)
    resolved = cli(args.new_python, project, "mcp", "scaffold-sync", "--review-json", json.dumps(review))
    save(root / "resolved-plan.json", resolved)
    assert resolved["ok"] and not resolved["applied"]
    applied = asyncio.run(mcp_roundtrip(args.new_python, project, args.factory, review, resolved["plan_sha256"]))
    save(root / "installed-mcp.json", applied)
    assert ignore.read_bytes() == ignored_before
    for name in ("source-checks.yml", "deploy.yml"):
        assert "author-guard:" in (project / ".github/workflows" / name).read_text()
    stale = execute([str(args.new_python), "-I", "-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "scaffold-sync",
                     "--review-json", json.dumps(review), "--apply", "--confirm-sync", "--expected-plan-sha256", resolved["plan_sha256"]], expected=None)
    assert stale.returncode != 0
    assert cli(args.new_python, fresh, "mcp", "site-context")["update_status"]["state"] == "current"
    snapshots = {name: sha(project / name) for name in ("Gemfile", "Gemfile.lock", ".gitignore", ".unaltraweb/scaffold.json")}
    ruby = '''require "json"; require "unaltraweb/version"; require "open3"; s=Gem.loaded_specs.fetch("unaltraweb"); revision,status=Open3.capture2("git","-C",s.full_gem_path,"rev-parse","HEAD"); abort "missing git source" unless status.success?; puts JSON.generate({version: Unaltraweb::VERSION, gem_version: s.version.to_s, revision: revision.strip, path: s.full_gem_path})'''
    command = ["docker", "run", "--rm", "--pull=never", "--network=bridge", "--cpus=2", "--memory=2g", "--pids-limit=256",
        "--env", "HOME=/tmp", "--env", "BUNDLE_FROZEN=true", "--env", "BUNDLE_APP_CONFIG=/site/tmp/bundle-config",
        "--label", "io.context.mcp-factory=unaltraweb", "--label", "io.context.mcp-role=scaffold-118-bundler",
        "--mount", "type=bind,source=" + str(project) + ",target=/site", "--workdir", "/site", "--entrypoint", "bash", args.runtime_image,
        "-lc", "bundle install && bundle exec ruby -e \"$1\" && core=\"$(bundle info --path unaltraweb)\" && bundle exec jekyll build --config \"$core/_config.yml,_config.yml\" --disable-disk-cache --trace", "acceptance", ruby]
    built = execute(command, timeout=900, expected=None)
    (root / "bundler.log").write_text(built.stdout + built.stderr)
    assert built.returncode == 0, built.stderr[-8000:] + built.stdout[-8000:]
    observed = next(json.loads(line) for line in built.stdout.splitlines() if line.startswith('{"version":'))
    assert observed["version"] == observed["gem_version"] == resolved["target"]["core_gem_version"]
    assert observed["revision"] == resolved["target"]["core_sha"]
    assert all(sha(project / name) == expected for name, expected in snapshots.items())
    assert (project / "_site/index.html").is_file()
    record = {"ok": True, "synthetic_only": True, "native_bundler": observed, "target": resolved["target"],
              "old_baseline_sha256": original_baseline, "initial_plan_sha256": plan["plan_sha256"],
              "resolved_plan_sha256": resolved["plan_sha256"], "managed_bytes_unchanged_by_bundler": snapshots,
              "following": applied["following"], "stale_review_refused": True}
    save(root / "acceptance.json", record)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
