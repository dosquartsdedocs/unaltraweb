"""Opt-in host test of released scaffolds, real Docker MCP and central policies.

Requires the MCP Python client, Docker, Git and an explicit central manager.
Creates only a new external evidence directory; retains fixtures for inspection.
Never installs client configuration or publishes a site.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_smoke import tool_payload
from test_workspace_path_policies import FACTORY, PROFILES, git, initialize_git, snapshot


@contextlib.asynccontextmanager
async def connect(project: Path, image: str):
    environment = os.environ.copy()
    environment["MCP_CONSUMER_WORKSPACE"] = str(project)
    parameters = StdioServerParameters(
        command="make",
        args=["--silent", "--no-print-directory", "-C", str(FACTORY), "mcp-stdio", f"MCP_RELEASE_IMAGE={image}"],
        env=environment,
        cwd=str(FACTORY),
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session


async def call(session, name: str, arguments: dict | None = None, *, success: bool = True) -> dict:
    result = await session.call_tool(name, arguments or {})
    assert not result.isError, result
    payload = tool_payload(result)
    if success:
        assert payload.get("ok") is not False, payload
    return payload


def workspace_check(project: Path, args) -> dict:
    before = snapshot(project)
    command = [sys.executable, str(args.manager), "workspace-check", "--dir", str(args.factories_dir),
               "--factory", "unaltraweb", "--workspace", str(project), "--json"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    result = json.loads(completed.stdout)
    after = snapshot(project)
    assert before == after, "workspace-check changed Git or filesystem state"
    assert completed.returncode == 0 and result["ok"], result
    assert result["summary"]["factory_count"] == 3, result
    assert result["summary"]["dependency_factory_count"] == 2, result
    assert [item["factory"] for item in result["results"]] == ["diavisuals", "vegavisuals", "unaltraweb"]
    for item in result["results"]:
        assert item["binding"] == "consumer" and item["resolved_root"] == str(project), item
    # Save evidence outside the inspected workspace only after the comparison.
    digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    snapshot_path = args.output_root / f"{project.name}-{digest[:12]}-snapshots.json"
    snapshot_path.write_text(
        json.dumps({"before": before, "after": after}, indent=2) + "\n", encoding="utf-8",
    )
    return {"command": command, "returncode": completed.returncode, "result": result,
            "unchanged": True, "snapshot_sha256": digest, "snapshots": str(snapshot_path)}


async def exercise_profile(profile: str, args) -> dict:
    project = args.output_root / profile
    project.mkdir()
    async with connect(project, args.image) as session:
        tools = {tool.name for tool in (await session.list_tools()).tools}
        assert {"new_web", "scaffold_sync", "site_check", "build_site"}.issubset(tools)
        created = await call(session, "new_web", {"site_profile": profile, "title": "Policy review", "default_lang": "en"})
        detected = await call(session, "detect_site")
        assert detected["project"] == str(project) and project != FACTORY, detected
        initialize_git(project)
        before = snapshot(project)
        planned = await call(session, "scaffold_sync", {"dry_run": True})
        assert not planned["updates"] and not planned["creates"] and not planned["manifest_update"], planned
        synced = await call(session, "scaffold_sync", {"dry_run": False, "confirm_sync": True})
        assert synced["applied"] and snapshot(project) == before, synced
        evidence = {"created": created, "detection": detected, "sync": synced,
                    "workspace_check": workspace_check(project, args)}
        checked = await call(session, "site_check")
        assert checked["project"] == str(project), checked
        evidence["site_check"] = checked
        if profile == "unaltremanual":
            await call(session, "manual_authoring_capabilities")
            config = await call(session, "site_source_read", {"path": "_config.yml"})
            enabled = config["content"].replace("      enabled: false\n", "      enabled: true\n", 1)
            assert enabled != config["content"]
            await call(session, "site_source_write", {
                "path": "_config.yml", "content": enabled,
                "expected_sha256": config["sha256"], "dry_run": False,
            })
            await call(session, "site_source_write", {
                "path": "_chapters/en/terrain.md", "create_only": True, "dry_run": False,
                "content": "---\nlayout: manual-chapter\ntitle: Terrain measurements\nlang: en\n"
                           "ref: terrain\nweight: 1\npermalink: /en/terrain/\n---\n\n"
                           "Elevation is measured relative to a vertical reference surface. "
                           "Record that reference when comparing terrain datasets.\n",
            })
            git(project, "add", "--", "_config.yml", "_chapters/en/terrain.md")
            evidence["computations"] = await call(session, "manual_computation_status")
            evidence["site_check"] = await call(session, "site_check")
            prepared = await call(session, "manual_pdf_preview_prepare")
            assert prepared["publishes"] is False, prepared
            evidence["pdf_prepare"] = prepared
            try:
                evidence["site_check_after_prepare"] = await call(session, "site_check")
                build = await call(session, "build_site")
                assert build["nested_container"] is False and build["html_audit"]["ok"], build
                assert (project / "_site/en/terrain/index.html").is_file()
                evidence["build"] = build
                evidence["workspace_check_after_build"] = workspace_check(project, args)
            finally:
                plan = await call(session, "manual_pdf_preview_clean", {"dry_run": True})
                evidence["pdf_clean"] = await call(session, "manual_pdf_preview_clean", {
                    "dry_run": False, "confirm_clean": True, "expected_receipt_sha256": plan["receipt_sha256"],
                })
            assert not (project / ".cache/unaltraweb/manual-pdf-preview.json").exists()
            assert not (project / ".cache/unaltraweb/manual-pdf-publication.json").exists()
        return evidence


async def exercise_previous_scaffold(args) -> dict:
    project = args.output_root / "previous-scaffold"
    project.mkdir()
    async with connect(project, args.previous_image) as session:
        await call(session, "new_web", {"site_profile": "unaltremanual", "default_lang": "en"})
        await call(session, "manual_authoring_capabilities")
    initialize_git(project)
    # Real published package, not a hand-written old baseline.
    with (project / ".gitignore").open("a") as stream:
        stream.write("\n/private-notes/\n")
    with (project / "Makefile").open("a") as stream:
        stream.write("\n# Consumer-owned build note\n")
    editorial = project / "_chapters/en/own.md"
    editorial.parent.mkdir(parents=True, exist_ok=True)
    editorial.write_text("Author-owned material preserved during integration.\n", encoding="utf-8")
    collision = project / "assets/pdf/manual-en.pdf"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_bytes(b"Unmanaged local PDF: preserve these exact bytes\n")
    collision_before = collision.read_bytes()
    before = snapshot(project)
    async with connect(project, args.image) as session:
        results = []
        update = await call(session, "site_context")
        assert update["update_status"]["state"] == "current_customized", update
        for options in ({"dry_run": True}, {"dry_run": False, "confirm_sync": True}):
            result = await call(session, "scaffold_sync", options)
            assert result["ok"] and not result["conflicts"], result
            assert set(result["preserved"]) == {".gitignore", "Makefile"}, result
            assert snapshot(project) == before, "sync modified customized prior scaffold"
            results.append(result)
    assert collision.read_bytes() == collision_before
    return {"previous_image": args.previous_image, "sync": results, "unchanged": True,
            "workspace_check": workspace_check(project, args)}


async def main(args) -> None:
    report = {"image": args.image, "factory": str(FACTORY), "profiles": {}, "ok": False}
    for profile in PROFILES:
        report["profiles"][profile] = await exercise_profile(profile, args)
        print(f"PASS {profile}: real MCP creation, sync, workspace-check and site_check", flush=True)
    report["previous_scaffold"] = await exercise_previous_scaffold(args)
    report["ok"] = True
    path = args.output_root / "evidence.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PASS previous scaffold: customizations and collision preserved; evidence: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manager", type=Path, required=True)
    parser.add_argument("--factories-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True, help="New absolute directory outside the factory; retained as evidence")
    parser.add_argument("--image", required=True, help="Explicit tested MCP image")
    parser.add_argument("--previous-image", required=True, help="Published MCP digest used to create the older consumer")
    args = parser.parse_args()
    if not args.output_root.is_absolute() or FACTORY in args.output_root.resolve().parents or args.output_root.resolve() == FACTORY:
        parser.error("--output-root must be absolute and outside the factory")
    args.output_root.mkdir(exist_ok=False)
    args.output_root = args.output_root.resolve()
    asyncio.run(main(args))
