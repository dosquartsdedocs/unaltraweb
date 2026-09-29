"""Real, populated 0.4 -> patched 0.5 Ruby runtime -> 0.4 acceptance. No source mounts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from distributed_launcher_smoke import Client


def hashes(project, paths):
    return {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--legacy-image", required=True)
    parser.add_argument("--fixed-image", required=True)
    parser.add_argument("--broken-image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", default=["unaltreselfie", "unaltreprojecte", "unaltredocs", "unaltremanual"])
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    evidence = []
    for profile in args.profiles:
        project = output / profile
        project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        client = Client(args.launcher, project, args.legacy_image, output / f"{profile}-create.log")
        try:
            client.tool("new_web", site_profile=profile, title="Populated Bundler transition", baseurl=f"/{profile}")
            if profile == "unaltremanual":
                source = client.tool("site_source_read", path="_config.yml")
                client.tool("site_source_write", path="_config.yml", content=source["content"].replace("      enabled: false\n", "      enabled: true\n", 1), expected_sha256=source["sha256"], dry_run=False)
                client.tool("site_source_write", path="_chapters/en/coordinates.md", create_only=True, dry_run=False,
                            content="---\nlayout: manual-chapter\ntitle: Coordinates\nlang: en\nref: coordinates\nweight: 1\npermalink: /en/chapters/coordinates/\n---\n\nA coordinate identifies a position relative to an origin.\n")
        finally:
            client.close()
        subprocess.run(["git", "-C", str(project), "add", "--", "."], check=True)
        with (output / f"{profile}-host-040.log").open("w") as log:
            subprocess.run(["make", "--silent", "build", f"MCP_IMAGE={args.legacy_image}"], cwd=project, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
        retained = ["Gemfile", "Gemfile.lock", "Makefile", ".unaltraweb/scaffold.json", "tmp/Gemfile.local", "tmp/Gemfile.local.lock"]
        before = hashes(project, retained)
        assert "google-protobuf (4.36.1" in (project / "tmp/Gemfile.local.lock").read_text()
        record = {"profile": profile, "before": before, "steps": []}
        broken = output / f"{profile}-unpatched"
        shutil.copytree(project, broken)
        client = Client(args.launcher, broken, args.broken_image, output / f"{profile}-unpatched-050.log")
        try:
            client.tool("site_check")
            try:
                client.tool("build_site")
            except AssertionError as exc:
                assert "google-protobuf (4.36.1)" in str(exc), exc
                record["unpatched_failure"] = str(exc)
            else:
                raise AssertionError("Expected the real unpatched retained-lock failure")
        finally:
            client.close()
        # The unpatched reproduction used a disposable copy of the populated
        # cache, so the real roundtrip starts with the untouched 0.4 lock.
        before_fixed = hashes(project, retained)
        assert before_fixed == before
        for stage, image in (("fixed-050", args.fixed_image), ("return-040", args.legacy_image)):
            client = Client(args.launcher, project, image, output / f"{profile}-{stage}.log")
            try:
                if profile == "unaltremanual":
                    assert not client.tool("manual_pdf_preview_prepare")["publishes"]
                assert client.tool("site_check")["ok"]
                for iteration in range(2):
                    assert client.tool("build_site")["ok"]
                started = client.tool("preview_start", timeout_seconds=180)
                assert started["ready"] and started["requested_port"] == 0
                client.tool("http_check", paths=[started["ready_path"]])
                record["steps"].append({"stage": stage, "image": image, "port": started["port"], "after": hashes(project, retained)})
                assert hashes(project, retained) == before_fixed, record
            finally:
                try:
                    client.tool("preview_stop")
                    if profile == "unaltremanual":
                        plan = client.tool("manual_pdf_preview_clean")
                        client.tool("manual_pdf_preview_clean", dry_run=False, confirm_clean=True, expected_receipt_sha256=plan["receipt_sha256"])
                finally:
                    client.close()
        record["runtime_receipts"] = {str(path.relative_to(project)): json.loads(path.read_text()) for path in sorted(project.glob("tmp/unaltraweb-bundle/*/receipt.json")) if not path.parent.name.startswith(".prepare-")}
        assert len(record["runtime_receipts"]) == 1, record["runtime_receipts"]
        evidence.append(record)
        (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({"profile": profile, "ok": True, "retained_locks_unchanged": True, "builds_per_runtime": 2}), flush=True)


if __name__ == "__main__":
    main()
