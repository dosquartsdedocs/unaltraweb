from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from unaltraweb_mcp import manual_pdf_preview, site_tools


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.twitter_title: dict[str, str | None] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == "twitter:title":
            self.twitter_title = values


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


def seed_fresh_manual_pdf(factory: Path, project: Path) -> list[dict[str, str]]:
    builder_path = factory / "scripts/manual/build_pdf.py"
    spec = importlib.util.spec_from_file_location("unaltraweb_manual_pdf_smoke", builder_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not load manual PDF builder: {builder_path}")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    config = builder.read_yaml(project / "_config.yml")
    pdf_config = builder.nested(config, "unaltraweb", "manual", "pdf")
    languages = builder.language_list(config, pdf_config)
    seeded: list[dict[str, str]] = []
    pdf_content = b"%PDF-1.4\n% local preview smoke\n%%EOF\n"
    cover_content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    release = builder.release_metadata()
    for language in languages:
        paths = builder.artifact_paths(project, config, language)
        paths["build_dir"].mkdir(parents=True, exist_ok=True)
        paths["pdf"].write_bytes(pdf_content)
        paths["cover"].write_bytes(cover_content)
        _, _, _, _, _, _, _, fingerprint = builder.prepare_build(project, config, language)
        manifest = {
            "language": language,
            "fingerprint": fingerprint,
            "pdf": str(paths["pdf"].relative_to(project)),
            "cover": str(paths["cover"].relative_to(project)),
            "public_pdf": str(paths["public_pdf"].relative_to(project)),
            "public_cover": str(paths["public_cover"].relative_to(project)),
            "release_selector": release["release-selector"],
            "release_channel": release["release-channel"],
            "artifacts": {
                "pdf": builder.file_signature(paths["pdf"]),
                "cover": builder.file_signature(paths["cover"]),
            },
        }
        paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        seeded.append({
            "pdf": str(paths["public_pdf"].relative_to(project)),
            "cover": str(paths["public_cover"].relative_to(project)),
        })
    return seeded


async def consumer_update_smoke(factory: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="unaltraweb-mcp-update-") as temporary:
        project = Path(temporary)
        replacements = site_tools._common_scaffold_replacements()
        replacements.update({
            "GEM_VERSION": "0.3.0",
            "MCP_IMAGE": "ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0",
            "CORE_SHA": "1" * 40,
        })
        with patch.object(site_tools, "_common_scaffold_replacements", return_value=replacements):
            assert site_tools.new_web(project)["ok"] is True
        ignore = project / ".gitignore"
        original_ignore = ignore.read_bytes() + b"\n/private-notes/\n"
        ignore.write_bytes(original_ignore)
        home = project / "_pages/en/index.md"
        original_home = home.read_bytes() + b"\nAuthor-owned content.\n"
        home.write_bytes(original_home)
        before = {path.relative_to(project).as_posix(): path.read_bytes() for path in project.rglob("*") if path.is_file()}
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "serve"],
            env={**os.environ, "UNALTRAWEB_FACTORY_DIR": str(factory)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                context = tool_payload(await session.call_tool("site_context", {}))
                update = context["update_status"]
                assert update["state"] == "update_available" and update["can_apply"], update
                assert update["current_versions"]["mcp_version"] == "0.3.0"
                refused = await session.call_tool("scaffold_sync", {
                    "dry_run": False, "expected_plan_sha256": update["plan_sha256"],
                })
                assert refused.isError is True, refused
                assert {path.relative_to(project).as_posix(): path.read_bytes() for path in project.rglob("*") if path.is_file()} == before
                applied = tool_payload(await session.call_tool("scaffold_sync", update["apply_arguments"]))
                assert applied["ok"] and applied["applied"], applied
                assert applied["preserved"] == [".gitignore"], applied
                current = tool_payload(await session.call_tool("site_context", {}))
                assert current["update_status"]["state"] == "current_customized", current
                assert ignore.read_bytes() == original_ignore
                assert home.read_bytes() == original_home
                checked = tool_payload(await session.call_tool("site_check", {}))
                assert checked["ok"], checked


async def smoke() -> None:
    factory = Path(os.environ.get("UNALTRAWEB_FACTORY_DIR", "/opt/unaltraweb")).resolve()
    await consumer_update_smoke(factory)
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
                for name in ["distribution_doctor", "new_web", "detect_site", "site_doctor", "site_source_read", "site_source_write", "site_source_delete", "scaffold_sync", "content_inventory", "manual_pdf_preview_prepare", "manual_pdf_preview_clean", "build_site", "html_audit", "preview_start", "preview_status", "preview_stop"]:
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

                initialized = tool_payload(await session.call_tool("new_web", {"site_profile": "unaltremanual"}))
                assert initialized["ok"] is True, initialized
                assert (project / "_config.yml").is_file()
                assert (project / "Makefile").is_file()
                assert (project / ".unaltraweb/scaffold.json").is_file()
                assert (project / ".unaltraweb/computations.yml").is_file()

                detection = tool_payload(await session.call_tool("detect_site", {}))
                assert detection["is_unaltraweb_site"] is True
                assert detection["project"] == str(project)

                context = tool_payload(await session.call_tool("site_context", {}))
                assert context["update_status"]["state"] == "current", context
                assert context["update_status"]["can_apply"] is False

                distribution = tool_payload(await session.call_tool("distribution_doctor", {}))
                assert distribution["ok"] is True, distribution
                assert distribution["mode"] == "factory"
                assert distribution["project"]["profile"] == "unaltremanual"
                assert {"compute_python", "compute_r"}.issubset(distribution["selected_components"])

                inventory = tool_payload(await session.call_tool("content_inventory", {}))
                assert inventory["collections"]["_pages"]["documents"] == 2

                home = tool_payload(await session.call_tool("site_source_read", {"path": "_pages/en/index.md"}))
                source_dry_run = tool_payload(await session.call_tool("site_source_write", {
                    "path": "_pages/en/index.md",
                    "content": home["content"] + "\nMCP source smoke.\n",
                    "expected_sha256": home["sha256"],
                }))
                assert source_dry_run["dry_run"] is True
                assert (project / "_pages/en/index.md").read_text(encoding="utf-8") == home["content"]

                hostile_title = 'A "</script><img src=x onerror=alert(1)>" title'
                source_write = tool_payload(await session.call_tool("site_source_write", {
                    "path": "_pages/en/metadata-hostile.md",
                    "content": (
                        "---\nlayout: default\nlang: en\nprofiles: [unaltremanual]\n"
                        "permalink: /en/metadata-hostile/\n"
                        f"title: '{hostile_title}'\nredirect: javascript:alert(1)\n---\n"
                    ),
                    "create_only": True,
                    "dry_run": False,
                }))
                assert source_write["ok"] is True, source_write
                config = tool_payload(await session.call_tool("site_source_read", {"path": "_config.yml"}))
                config_write = tool_payload(await session.call_tool("site_source_write", {
                    "path": "_config.yml",
                    "content": config["content"].replace("      enabled: false\n", "      enabled: true\n", 1) + "\nserve_og_meta: true\nserve_schema_org: true\n",
                    "expected_sha256": config["sha256"],
                    "dry_run": False,
                }))
                assert config_write["ok"] is True, config_write
                chapter_write = tool_payload(await session.call_tool("site_source_write", {
                    "path": "_chapters/en/chapter-0.md",
                    "content": (
                        "---\nlayout: manual-chapter\ntitle: Chapter 0\nlang: en\n"
                        "ref: chapter-0\nweight: 0\npermalink: /en/chapters/chapter-0/\n---\n\n"
                        "MCP smoke chapter zero.\n"
                    ),
                    "create_only": True,
                    "dry_run": False,
                }))
                assert chapter_write["ok"] is True, chapter_write

                scaffold = tool_payload(await session.call_tool("scaffold_sync", {}))
                assert scaffold["ok"] is True, scaffold
                assert scaffold["dry_run"] is True
                confirmed = tool_payload(await session.call_tool("scaffold_sync", {
                    "dry_run": False, "confirm_sync": True,
                    "expected_plan_sha256": scaffold["plan_sha256"],
                }))
                assert confirmed["applied"] is True, confirmed

                doctor = tool_payload(await session.call_tool("site_doctor", {}))
                assert doctor["ok"] is True, doctor
                assert doctor["offline"] is True

                subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)
                subprocess.run(["git", "config", "user.email", "smoke@example.test"], cwd=project, check=True)
                subprocess.run(["git", "config", "user.name", "MCP Smoke"], cwd=project, check=True)
                subprocess.run(["git", "add", "--all"], cwd=project, check=True)
                subprocess.run(["git", "commit", "--quiet", "-m", "Initialize smoke site"], cwd=project, check=True)
                public_artifacts = seed_fresh_manual_pdf(factory, project)

                preview_pdf = tool_payload(await session.call_tool("manual_pdf_preview_prepare", {}))
                assert preview_pdf["ok"] is True, preview_pdf
                assert preview_pdf["publishes"] is False, preview_pdf
                assert preview_pdf["built_languages"] == [], preview_pdf
                assert (project / manual_pdf_preview.RECEIPT_PATH).is_file()
                assert not (project / manual_pdf_preview.PUBLICATION_INTENT_PATH).exists()
                assert not (project / manual_pdf_preview.PUBLICATION_RECEIPT_PATH).exists()
                for artifact in public_artifacts:
                    assert (project / artifact["pdf"]).is_file(), artifact
                    assert (project / artifact["cover"]).is_file(), artifact
                    assert subprocess.run(
                        ["git", "check-ignore", "--quiet", "--no-index", "--", artifact["pdf"]],
                        cwd=project,
                        check=False,
                    ).returncode == 0
                    assert subprocess.run(
                        ["git", "ls-files", "--error-unmatch", "--", artifact["pdf"]],
                        cwd=project,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    ).returncode != 0

                build = tool_payload(await session.call_tool("build_site", {}))
                assert build["ok"] is True, build
                assert build["nested_container"] is False
                assert build["html_audit"]["ok"] is True, build["html_audit"]
                assert (project / "_site/index.html").is_file()
                assert (project / "_site/en/index.html").is_file()
                assert (project / "_site/en/chapters/chapter-0/index.html").is_file()
                search_index = json.loads((project / "_site/assets/js/content-search-index.json").read_text(encoding="utf-8"))
                assert all(entry["url"] != "/" for entry in search_index)
                rendered_home = (project / "_site/en/metadata-hostile/index.html").read_text(encoding="utf-8")
                metadata_parser = MetadataParser()
                metadata_parser.feed(rendered_home)
                assert metadata_parser.twitter_title == {"name": "twitter:title", "content": hostile_title}
                assert "javascript:alert(1)" not in rendered_home
                assert "</script><img" not in rendered_home
                schema_match = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', rendered_home, re.DOTALL)
                assert schema_match is not None
                assert json.loads(schema_match.group(1))["headline"] == hostile_title
                manual_home = (project / "_site/en/index.html").read_text(encoding="utf-8")
                assert 'class="manual-download"' in manual_home
                assert "assets/img/manual-cover-en.png" in manual_home
                assert (project / "_site/assets/pdf/manual-en.pdf").is_file()
                assert (project / "_site/assets/img/manual-cover-en.png").is_file()

                checks = tool_payload(await session.call_tool("site_check", {}))
                assert checks["ok"] is True, checks
                assert checks["web_captures"]["ok"] is True, checks["web_captures"]
                assert checks["visualizations"]["owner"] == "vegavisuals"

                cleanup_plan = tool_payload(await session.call_tool("manual_pdf_preview_clean", {}))
                assert cleanup_plan["ok"] is True, cleanup_plan
                assert cleanup_plan["dry_run"] is True, cleanup_plan
                cleaned = tool_payload(await session.call_tool("manual_pdf_preview_clean", {
                    "dry_run": False,
                    "confirm_clean": True,
                    "expected_receipt_sha256": cleanup_plan["receipt_sha256"],
                }))
                assert cleaned["ok"] is True, cleaned
                assert cleaned["publishes"] is False, cleaned
                assert not (project / manual_pdf_preview.PUBLICATION_INTENT_PATH).exists()
                assert not (project / manual_pdf_preview.PUBLICATION_RECEIPT_PATH).exists()
                for artifact in public_artifacts:
                    assert not (project / artifact["pdf"]).exists(), artifact
                    assert not (project / artifact["cover"]).exists(), artifact
                assert subprocess.run(
                    ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                    cwd=project,
                    check=True,
                    stdout=subprocess.PIPE,
                    text=True,
                ).stdout == ""


if __name__ == "__main__":
    asyncio.run(smoke())
