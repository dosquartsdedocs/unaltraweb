from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
                for name in ["new_web", "detect_site", "content_inventory", "build_site", "preview_start", "preview_status", "preview_stop"]:
                    assert name in tools, name

                resources = {str(resource.uri) for resource in (await session.list_resources()).resources}
                assert "web://site-context" in resources
                assert "web://new-web-scaffolds" in resources
                assert "web://content-inventory" in resources

                prompts = {prompt.name for prompt in (await session.list_prompts()).prompts}
                assert "start_site_session" in prompts
                assert "create_new_web" in prompts
                assert "build_and_review" in prompts

                initialized = tool_payload(await session.call_tool("new_web", {}))
                assert initialized["ok"] is True, initialized
                assert (project / "_config.yml").is_file()
                assert (project / "Makefile").is_file()

                detection = tool_payload(await session.call_tool("detect_site", {}))
                assert detection["is_unaltraweb_site"] is True
                assert detection["project"] == str(project)

                inventory = tool_payload(await session.call_tool("content_inventory", {}))
                assert inventory["collections"]["_pages"]["documents"] == 1

                build = tool_payload(await session.call_tool("build_site", {}))
                assert build["ok"] is True, build
                assert build["nested_container"] is False
                assert (project / "_site/index.html").is_file()

                checks = tool_payload(await session.call_tool("site_check", {}))
                assert checks["ok"] is True, checks
                assert checks["web_captures"]["ok"] is True, checks["web_captures"]
                assert checks["visualizations"]["owner"] == "vegavisuals"


if __name__ == "__main__":
    asyncio.run(smoke())
