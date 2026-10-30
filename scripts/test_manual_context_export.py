"""Retained fixture acceptance through the real producer MCP, never a fabricated tar.

Run Itemarium's independent conformance command on the returned paths/hashes.
This script itself has no Itemarium dependency and uses no teaching workspace.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test"))
from test_manual_context import fixture, write, commit  # noqa: E402


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


async def export(project, name, image=""):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    def payload(result):
        return result.structuredContent or json.loads("\n".join(row.text for row in result.content if hasattr(row, "text")))
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "unaltraweb_mcp.cli", "mcp", "serve"],
        env={"PATH": os.environ["PATH"], "HOME": str(project), "PYTHONPATH": str(ROOT / "src"),
             "MCP_CONSUMER_WORKSPACE": str(project), "UNALTRAWEB_FACTORY_DIR": str(ROOT)})
    container = ""
    image_id = ""
    if image:
        from unaltraweb_mcp.docker_mount import docker_bind_mount
        image_id = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], check=True,
                                  capture_output=True, text=True, timeout=20).stdout.strip()
        container = "unaltraweb-context-121-" + uuid.uuid4().hex
        parameters = StdioServerParameters(command="docker", args=["run", "--rm", "-i", "--pull", "never",
            "--name", container, "--network", "none", "--read-only", "--user", f"{os.getuid()}:{os.getgid()}",
            "--cpus", "2", "--memory", "2g", "--pids-limit", "256", "--tmpfs", "/tmp:rw,nosuid,nodev,size=268435456",
            "--label", "io.context.mcp-factory=unaltraweb", "--label", "io.context.mcp-role=context-acceptance",
            "--mount", docker_bind_mount(project, "/workspace"), "-e", "HOME=/tmp",
            "-e", "UNALTRAWEB_DOCKER_ROOT=" + str(project), "-e", "UNALTRAWEB_MCP_IMAGE=" + image_id,
            "--entrypoint", "unaltraweb-mcp", image_id, "--project", "/workspace", "mcp", "serve"])
    async with stdio_client(parameters) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as client:
            await client.initialize()
            tools = await client.list_tools()
            tool = next(row for row in tools.tools if row.name == "manual_context_export")
            assert not {"root", "project", "workspace"} & tool.inputSchema["properties"].keys()
            identity = payload(await client.call_tool("runtime_identity", {}))
            result = payload(await client.call_tool("manual_context_export", {"name": name, "language": "ca"}))
            assert result["ok"], result
            again = payload(await client.call_tool("manual_context_export", {"name": name, "language": "ca"}))
            assert not again["ok"] and "already exists" in again["error"], again
            await client.call_tool("runtime_drain", {"confirm": True})
            result["absolute_path"] = str(project / result["path"])
            assert hashlib.sha256(Path(result["absolute_path"]).read_bytes()).hexdigest() == result["sha256"]
            observed = {"identity": identity, "export": result, "create_only_refusal": again}
    if image:
        assert identity["package"]["mode"] == "installed" and not identity["package"]["drift"]
        absent = subprocess.run(["docker", "container", "inspect", container], capture_output=True, timeout=20)
        assert absent.returncode != 0, "Fixture MCP container remains after stdio close"
        observed.update(image_id=image_id, exact_container_absent=True)
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--single", action="store_true")
    parser.add_argument("--image", default="", help="Already-built MCP image; pull-never, network-disabled fixture stdio")
    args = parser.parse_args()
    output = args.output.resolve()
    if output != args.output or not output.is_relative_to(ROOT / "tmp") or not output.parent.is_dir():
        raise ValueError("Use a new absolute output directory below the factory tmp with an existing parent")
    output.mkdir(mode=0o700)
    project = output / "manual-fixture"
    project.mkdir()
    fixture(project)
    first = asyncio.run(export(project, "v1", args.image))
    save(output / "producer-v1.json", first)
    command = [sys.executable, "-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "manual-context-export",
               "--name", "cli-block", "--language", "ca", "--chapter", "first", "--section", "first#method"]
    completed = subprocess.run(command, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "UNALTRAWEB_FACTORY_DIR": str(ROOT)},
                               check=True, capture_output=True, text=True, timeout=120)
    cli = json.loads(completed.stdout)
    assert cli["ok"] and cli["sections"] == 1 and cli["figures"] == 1, cli
    save(output / "producer-cli.json", {"command": command, "result": cli})
    result = {"ok": True, "synthetic_manual": True, "producer_export_invoked": True, "transport": "mcp-stdio",
              "first": first["export"], "cli_verified": True, "questions_generated": 0}
    if not args.single:
        original = (project / "_chapters/ca/first.md").read_text()
        write(project, "_chapters/ca/first.md", original + "\nSegona versió: text afegit.\n")
        write(project, "_chapters/ca/second.md", "---\ntitle: Segon\nref: second\nlang: ca\nweight: 20\n---\nCapítol afegit en la segona versió.\n")
        commit(project, ["_chapters/ca/first.md", "_chapters/ca/second.md"], "Second fixture revision")
        second = asyncio.run(export(project, "v2", args.image))
        save(output / "producer-v2.json", second)
        result["next"] = second["export"]
        assert first["export"]["manual"]["id"] == second["export"]["manual"]["id"]
        assert first["export"]["manual"]["revision"] != second["export"]["manual"]["revision"]
    save(output / "producer-receipt.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
