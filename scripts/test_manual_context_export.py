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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test"))
from test_manual_context import fixture, write, commit  # noqa: E402


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


async def export(project, name):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    def payload(result):
        return result.structuredContent or json.loads("\n".join(row.text for row in result.content if hasattr(row, "text")))
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "unaltraweb_mcp.cli", "mcp", "serve"],
        env={"PATH": os.environ["PATH"], "HOME": str(project), "PYTHONPATH": str(ROOT / "src"),
             "MCP_CONSUMER_WORKSPACE": str(project), "UNALTRAWEB_FACTORY_DIR": str(ROOT)})
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
            return {"identity": identity, "export": result, "create_only_refusal": again}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--single", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output != args.output or not output.is_relative_to(ROOT / "tmp") or not output.parent.is_dir():
        raise ValueError("Use a new absolute output directory below the factory tmp with an existing parent")
    output.mkdir(mode=0o700)
    project = output / "manual-fixture"
    project.mkdir()
    fixture(project)
    first = asyncio.run(export(project, "v1"))
    save(output / "producer-v1.json", first)
    result = {"ok": True, "synthetic_manual": True, "producer_export_invoked": True, "transport": "mcp-stdio",
              "first": first["export"], "questions_generated": 0}
    if not args.single:
        original = (project / "_chapters/ca/first.md").read_text()
        write(project, "_chapters/ca/first.md", original + "\nSegona versió: text afegit.\n")
        write(project, "_chapters/ca/second.md", "---\ntitle: Segon\nref: second\nlang: ca\nweight: 20\n---\nCapítol afegit en la segona versió.\n")
        commit(project, ["_chapters/ca/first.md", "_chapters/ca/second.md"], "Second fixture revision")
        second = asyncio.run(export(project, "v2"))
        save(output / "producer-v2.json", second)
        result["next"] = second["export"]
        assert first["export"]["manual"]["id"] == second["export"]["manual"]["id"]
        assert first["export"]["manual"]["revision"] != second["export"]["manual"]["revision"]
    save(output / "producer-receipt.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
