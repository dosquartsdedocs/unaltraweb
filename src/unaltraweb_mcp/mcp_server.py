from __future__ import annotations

from pathlib import Path
from typing import Any

from . import site_tools as tools


PROMPT_FILES = {
    "start_site_session": "00-start-site-session.txt",
    "content_update": "10-content-update.txt",
    "edit_default_content": "15-edit-default-content.txt",
    "manual_teaching_materials": "20-manual-teaching-materials.txt",
    "translation_prepublish": "25-translation-prepublish.txt",
    "project_site_update": "30-project-site-update.txt",
    "documentation_update": "40-documentation-update.txt",
    "bibliography_entry": "50-bibliography-entry.txt",
    "bibliometrics_refresh": "60-bibliometrics-refresh.txt",
    "build_and_review": "70-build-and-review.txt",
}


def _prompt_text(factory: Path, name: str) -> str:
    filename = PROMPT_FILES.get(name, "")
    path = factory / "docs" / "agents" / "action-prompts" / filename
    if filename and path.is_file():
        return path.read_text(encoding="utf-8")
    return f"Prompt `{name}` is not available in this unaltraweb checkout."


def run_server(project: Path, factory: Path) -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("The unaltraweb MCP server requires the optional dependency. Install with: uv tool install 'unaltraweb-mcp[mcp]' or install mcp in this environment.") from exc

    mcp = FastMCP("unaltraweb")

    @mcp.resource("web://site-context")
    def site_context_resource() -> str:
        """Current unaltraweb site profile, features, content, bibliography, bibliometrics, and build state."""
        return tools.dumps(tools.site_context(project, factory))

    @mcp.resource("web://starter-templates")
    def starter_templates_resource() -> str:
        """Available starter website templates usable by initialize_site."""
        return tools.dumps(tools.starter_templates(factory))

    @mcp.resource("web://profile-contract")
    def profile_contract_resource() -> str:
        """Profile-specific contract checks for unaltreselfie, unaltreprojecte, unaltremanual, and unaltredocs."""
        return tools.dumps(tools.profile_check(project))

    @mcp.resource("web://profile-prune-plan")
    def profile_prune_plan_resource() -> str:
        """Dry-run list of profile-specific content files that can be removed from the current profile."""
        return tools.dumps(tools.profile_prune_plan(project))

    @mcp.resource("web://content-inventory")
    def content_inventory_resource() -> str:
        """Inventory of pages, posts, news, projects, outputs, chapters, documentation, books, theses, data, and assets."""
        return tools.dumps(tools.content_inventory(project))

    @mcp.resource("web://language-policy")
    def language_policy_resource() -> str:
        """Default language, configured languages, and the approved-before-translation workflow."""
        return tools.dumps(tools.language_policy(project))

    @mcp.resource("web://content-approval")
    def content_approval_resource() -> str:
        """Editorial approval status for default-language and translated content."""
        return tools.dumps(tools.content_approval_inventory(project))

    @mcp.resource("web://translation-plan")
    def translation_plan_resource() -> str:
        """Pre-publication translation plan for approved default-language content."""
        return tools.dumps(tools.translation_plan(project))

    @mcp.resource("web://bibliography")
    def bibliography_resource() -> str:
        """BibTeX files, entry counts, types, duplicates, and bibliometrics update dates."""
        return tools.dumps(tools.bibliography_inventory(project))

    @mcp.resource("web://bibliometrics")
    def bibliometrics_resource() -> str:
        """Versioned bibliometrics summary state and bibliography-side update dates."""
        return tools.dumps(tools.bibliometrics_status(project))

    @mcp.resource("web://build-health")
    def build_health_resource() -> str:
        """Local _site build artefact state without starting a server."""
        return tools.dumps(tools.build_health(project))

    @mcp.resource("web://prompts")
    def prompts_resource() -> str:
        """Reusable unaltraweb workflow prompt inventory."""
        return tools.dumps(tools.prompt_inventory(factory))

    @mcp.prompt()
    def start_site_session() -> str:
        """Start or resume work in an unaltraweb website workspace."""
        return _prompt_text(factory, "start_site_session")

    @mcp.prompt()
    def content_update(target: str = "next content item") -> str:
        """Update one page, post, news item, project, output, or structured data file."""
        return _prompt_text(factory, "content_update") + f"\n\nCurrent target: {target}\n"

    @mcp.prompt()
    def edit_default_content(target: str = "default-language content item") -> str:
        """Draft, revise, and approve content in the configured default language before localization."""
        return _prompt_text(factory, "edit_default_content") + f"\n\nCurrent target: {target}\n"

    @mcp.prompt()
    def manual_teaching_materials(target: str = "manual chapter or teaching resource") -> str:
        """Create or revise teaching/manual content for unaltremanual sites."""
        return _prompt_text(factory, "manual_teaching_materials") + f"\n\nCurrent target: {target}\n"

    @mcp.prompt()
    def translation_prepublish(target_language: str = "") -> str:
        """Prepare approved default-language content for translation shortly before publication."""
        suffix = f"\n\nTarget language: {target_language}\n" if target_language else ""
        return _prompt_text(factory, "translation_prepublish") + suffix

    @mcp.prompt()
    def project_site_update(target: str = "project site section") -> str:
        """Update research project content, outputs, repositories, team data, or news."""
        return _prompt_text(factory, "project_site_update") + f"\n\nCurrent target: {target}\n"

    @mcp.prompt()
    def documentation_update(target: str = "documentation page") -> str:
        """Update technical or operational documentation."""
        return _prompt_text(factory, "documentation_update") + f"\n\nCurrent target: {target}\n"

    @mcp.prompt()
    def bibliography_entry(source: str = "verified source metadata") -> str:
        """Add or revise bibliography entries without inventing metadata."""
        return _prompt_text(factory, "bibliography_entry") + f"\n\nSource basis: {source}\n"

    @mcp.prompt()
    def bibliometrics_refresh() -> str:
        """Check and update static bibliometrics data."""
        return _prompt_text(factory, "bibliometrics_refresh")

    @mcp.prompt()
    def build_and_review(site_profile: str = "") -> str:
        """Build the site and review local rendered output or a running preview."""
        suffix = f"\n\nSite profile override: {site_profile}\n" if site_profile else ""
        return _prompt_text(factory, "build_and_review") + suffix

    @mcp.tool()
    def starter_templates() -> dict[str, Any]:
        """Return available starter website templates discovered from the unaltraweb factory checkout."""
        return tools.starter_templates(factory)

    @mcp.tool()
    def initialize_site(template_path: str = "", site_profile: str = "unaltreselfie", title: str = "", baseurl: str = "", url: str = "", default_lang: str = "", languages: str = "", force: bool = False, confirm_overwrite: bool = False) -> dict[str, Any]:
        """Initialize the current workspace from a starter template. Existing files are skipped unless force and confirm_overwrite are both true."""
        return tools.initialize_site(project, factory, template_path=template_path, site_profile_value=site_profile, title=title, baseurl=baseurl, url=url, default_lang=default_lang, languages=languages, force=force, confirm_overwrite=confirm_overwrite)

    @mcp.tool()
    def site_context() -> dict[str, Any]:
        """Return site profile, features, content, bibliography, bibliometrics, and build state."""
        return tools.site_context(project, factory)

    @mcp.tool()
    def site_check(max_bibliometrics_age_days: int = 180) -> dict[str, Any]:
        """Run local profile, freshness, bibliography, bibliometrics, and build-state checks without network access."""
        return {"profile": tools.profile_check(project), "language": tools.language_policy(project), "approval": tools.content_approval_inventory(project), "translation": tools.translation_plan(project), "freshness": tools.content_freshness_check(project, max_bibliometrics_age_days), "bibliography": tools.bibliography_inventory(project), "build_health": tools.build_health(project)}

    @mcp.tool()
    def profile_check() -> dict[str, Any]:
        """Check the current site against the configured unaltraweb profile contract."""
        return tools.profile_check(project)

    @mcp.tool()
    def profile_prune_plan(site_profile: str = "") -> dict[str, Any]:
        """List profile-specific content files that would be removed by profile_prune."""
        return tools.profile_prune_plan(project, site_profile_value=site_profile)

    @mcp.tool()
    def profile_prune(site_profile: str = "", dry_run: bool = True, confirm_prune: bool = False) -> dict[str, Any]:
        """Remove content files whose explicit profiles front matter does not include the selected profile. Destructive runs require confirm_prune=True."""
        return tools.profile_prune(project, site_profile_value=site_profile, dry_run=dry_run, confirm_prune=confirm_prune)

    @mcp.tool()
    def content_inventory() -> dict[str, Any]:
        """List editable site collections, data files, and assets."""
        return tools.content_inventory(project)

    @mcp.tool()
    def language_policy() -> dict[str, Any]:
        """Return default language, configured languages, and editorial translation workflow settings."""
        return tools.language_policy(project)

    @mcp.tool()
    def content_approval_inventory(status_field: str = "", approved_value: str = "") -> dict[str, Any]:
        """Summarize local content approval status before translation or publication."""
        return tools.content_approval_inventory(project, status_field=status_field, approved_value=approved_value)

    @mcp.tool()
    def translation_plan(target_langs: list[str] | None = None, status_field: str = "", approved_value: str = "") -> dict[str, Any]:
        """List approved default-language sources and missing translations for pre-publication localization."""
        return tools.translation_plan(project, target_langs=target_langs, status_field=status_field, approved_value=approved_value)

    @mcp.tool()
    def content_freshness_check(max_bibliometrics_age_days: int = 180) -> dict[str, Any]:
        """Check stale bibliometrics dates and future-dated posts/news from local files."""
        return tools.content_freshness_check(project, max_bibliometrics_age_days)

    @mcp.tool()
    def bibliography_inventory() -> dict[str, Any]:
        """List BibTeX files, entries, types, duplicate citekeys, and bibliometrics update dates."""
        return tools.bibliography_inventory(project)

    @mcp.tool()
    def bibliography_add_entry(bibtex: str, path: str = "_bibliography/papers.bib", replace: bool = False) -> dict[str, Any]:
        """Append a verified BibTeX entry under _bibliography/. Replacements require replace=True."""
        return tools.bibliography_add_entry(project, bibtex, path=path, replace=replace)

    @mcp.tool()
    def bibliometrics_check() -> dict[str, Any]:
        """Run the site's offline bibliometrics check target."""
        return tools.bibliometrics_check(project)

    @mcp.tool()
    def bibliometrics_fetch_scimago(scimago_input: str = "") -> dict[str, Any]:
        """Fetch or validate local Scimago data through the site Make contract."""
        return tools.bibliometrics_fetch_scimago(project, scimago_input=scimago_input)

    @mcp.tool()
    def bibliometrics_update(fetch_scimago: bool = False, offline: bool = False, dry_run: bool = False, strict_external: bool = False, require_scimago: bool = False) -> dict[str, Any]:
        """Update static bibliography and bibliometrics outputs through the site Make contract."""
        return tools.bibliometrics_update(project, fetch_scimago=fetch_scimago, offline=offline, dry_run=dry_run, strict_external=strict_external, require_scimago=require_scimago)

    @mcp.tool()
    def build_site(site_profile: str = "") -> dict[str, Any]:
        """Run make build in the website workspace, optionally overriding SITE_PROFILE."""
        return tools.build_site(project, site_profile=site_profile)

    @mcp.tool()
    def build_health() -> dict[str, Any]:
        """Inspect existing _site build artefacts without running Jekyll."""
        return tools.build_health(project)

    @mcp.tool()
    def http_check(base_url: str = "http://127.0.0.1:4000", paths: list[str] | None = None, timeout_seconds: float = 5.0) -> dict[str, Any]:
        """Check whether a running Jekyll preview responds over HTTP. This does not make the MCP itself an HTTP server."""
        return tools.http_check(base_url, paths=paths, timeout_seconds=timeout_seconds)

    mcp.run()
