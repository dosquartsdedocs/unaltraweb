from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from unaltraweb_mcp import site_tools


def tool_payload(result: object) -> dict[str, object]:
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    for item in getattr(result, "content", []):
        text = getattr(item, "text", "")
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    raise AssertionError("MCP tool call did not return a JSON object")


async def smoke() -> None:
    factory = Path(os.environ.get("UNALTRAWEB_FACTORY_DIR", "/opt/unaltraweb")).resolve()
    with tempfile.TemporaryDirectory(prefix="unaltraweb-mcp-smoke-") as temporary:
        project = Path(temporary)

        env = os.environ.copy()
        env["UNALTRAWEB_FACTORY_DIR"] = str(factory)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "serve"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = {tool.name for tool in (await session.list_tools()).tools}
                for name in ["distribution_doctor", "new_web", "detect_site", "site_doctor", "site_source_read", "site_source_write", "site_source_delete", "scaffold_sync", "content_inventory", "build_site", "html_audit", "preview_start", "preview_status", "preview_stop"]:
                    assert name in tools, name

                resources = {str(resource.uri) for resource in (await session.list_resources()).resources}
                assert "web://distribution" in resources
                assert "web://site-context" in resources
                assert "web://new-web-scaffolds" in resources
                assert "web://content-inventory" in resources

                prompt_items = (await session.list_prompts()).prompts
                prompts = {prompt.name: prompt for prompt in prompt_items}
                assert set(prompts) == set(site_tools.PROMPT_SPECS)
                for name, spec in site_tools.PROMPT_SPECS.items():
                    assert prompts[name].description == spec["description"]
                    assert [argument.name for argument in (prompts[name].arguments or [])] == [argument["name"] for argument in spec["arguments"]]

                initialized = tool_payload(await session.call_tool("new_web", {}))
                assert initialized["ok"] is True, initialized
                assert (project / "_config.yml").is_file()
                assert (project / "Makefile").is_file()
                assert (project / ".unaltraweb/scaffold.json").is_file()

                detection = tool_payload(await session.call_tool("detect_site", {}))
                assert detection["is_unaltraweb_site"] is True
                assert detection["project"] == str(project)

                distribution = tool_payload(await session.call_tool("distribution_doctor", {}))
                assert distribution["ok"] is True, distribution
                assert distribution["mode"] == "factory"
                assert distribution["project"]["profile"] == "unaltreselfie"

                inventory = tool_payload(await session.call_tool("content_inventory", {}))
                assert inventory["collections"]["_pages"]["documents"] == 1

                home = tool_payload(await session.call_tool("site_source_read", {"path": "_pages/en/index.md"}))
                source_dry_run = tool_payload(await session.call_tool("site_source_write", {
                    "path": "_pages/en/index.md",
                    "content": home["content"] + "\nMCP source smoke.\n",
                    "expected_sha256": home["sha256"],
                }))
                assert source_dry_run["dry_run"] is True
                assert (project / "_pages/en/index.md").read_text(encoding="utf-8") == home["content"]

                scaffold = tool_payload(await session.call_tool("scaffold_sync", {}))
                assert scaffold["ok"] is True, scaffold
                assert scaffold["dry_run"] is True

                doctor = tool_payload(await session.call_tool("site_doctor", {}))
                assert doctor["ok"] is True, doctor
                assert doctor["offline"] is True

                build = tool_payload(await session.call_tool("build_site", {}))
                assert build["ok"] is True, build
                assert build["nested_container"] is False
                assert build["html_audit"]["ok"] is True, build["html_audit"]
                assert (project / "_site/index.html").is_file()

                checks = tool_payload(await session.call_tool("site_check", {}))
                assert checks["ok"] is True, checks
                assert checks["web_captures"]["ok"] is True, checks["web_captures"]
                assert checks["visualizations"]["owner"] == "vegavisuals"


if __name__ == "__main__":
    asyncio.run(smoke())
