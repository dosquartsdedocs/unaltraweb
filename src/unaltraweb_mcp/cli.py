from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import site_tools as tools


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def project_dir(raw: str | None) -> Path:
    return tools.project_path(raw)


def print_json(payload: object, *, enforce_ok: bool = False) -> int:
    print(tools.dumps(payload), end="")
    return 1 if enforce_ok and isinstance(payload, dict) and payload.get("ok") is False else 0


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def cmd_factory_dir(_: argparse.Namespace) -> int:
    print(source_root())
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    project = project_dir(args.project)
    factory = source_root()
    command = args.mcp_command
    if command == "serve":
        from .mcp_server import run_server

        run_server(project=project, factory=factory)
        return 0
    if command == "list-tools":
        return print_json(tools.list_tools())
    if command == "starter-templates":
        return print_json(tools.starter_templates(factory))
    if command == "initialize-site":
        return print_json(
            tools.initialize_site(
                project,
                factory,
                template_path=args.template_path,
                site_profile_value=args.site_profile,
                title=args.title,
                baseurl=args.baseurl,
                url=args.url,
                default_lang=args.default_lang,
                languages=args.languages,
                force=args.force,
                confirm_overwrite=args.confirm_overwrite,
            )
        )
    if command == "site-context":
        return print_json(tools.site_context(project, factory))
    if command == "site-check":
        return print_json({"profile": tools.profile_check(project), "language": tools.language_policy(project), "approval": tools.content_approval_inventory(project), "translation": tools.translation_plan(project), "freshness": tools.content_freshness_check(project), "computations": tools.manual_computation_status(project, factory), "web_captures": tools.web_capture_status(project, factory), "bibliography": tools.bibliography_inventory(project), "build_health": tools.build_health(project)})
    if command == "profile-check":
        return print_json(tools.profile_check(project))
    if command == "manual-source-quality-check":
        return print_json(tools.manual_source_quality_check(project))
    if command == "manual-editorial-quality-check":
        return print_json(tools.manual_editorial_quality_check(project))
    if command == "manual-authoring-capabilities":
        return print_json(tools.manual_authoring_capabilities(project))
    if command == "manual-computation-status":
        return print_json(tools.manual_computation_status(project, factory, source=args.source))
    if command == "manual-computation-check":
        return print_json(tools.manual_computation_check(project, factory, source=args.source), enforce_ok=True)
    if command == "manual-computation-render":
        return print_json(tools.manual_computation_render(project, factory, source=args.source, confirm_overwrite=args.confirm_overwrite))
    if command == "web-capture-status":
        return print_json(tools.web_capture_status(project, factory, source=args.source))
    if command == "web-capture-check":
        return print_json(tools.web_capture_check(project, factory, source=args.source), enforce_ok=True)
    if command == "web-capture-render":
        return print_json(tools.web_capture_render(project, factory, source=args.source, confirm_overwrite=args.confirm_overwrite))
    if command == "manual-pdf-status":
        return print_json(tools.manual_pdf_status(project, language=args.language))
    if command == "manual-pdf-build":
        return print_json(tools.manual_pdf_build(project, language=args.language))
    if command == "manual-pdf-publish":
        return print_json(tools.manual_pdf_publish(project, language=args.language, dry_run=not args.apply, confirm_publish=args.confirm_publish))
    if command == "profile-prune-plan":
        return print_json(tools.profile_prune_plan(project, site_profile_value=args.site_profile))
    if command == "profile-prune":
        return print_json(tools.profile_prune(project, site_profile_value=args.site_profile, dry_run=not args.apply, confirm_prune=args.confirm_prune))
    if command == "content-inventory":
        return print_json(tools.content_inventory(project))
    if command == "language-policy":
        return print_json(tools.language_policy(project))
    if command == "content-approval-inventory":
        return print_json(tools.content_approval_inventory(project, status_field=args.status_field, approved_value=args.approved_value))
    if command == "translation-plan":
        return print_json(tools.translation_plan(project, target_langs=args.target_langs, status_field=args.status_field, approved_value=args.approved_value))
    if command == "content-freshness-check":
        return print_json(tools.content_freshness_check(project, max_bibliometrics_age_days=args.max_bibliometrics_age_days))
    if command == "bibliography-inventory":
        return print_json(tools.bibliography_inventory(project))
    if command == "bibliography-add-entry":
        return print_json(tools.bibliography_add_entry(project, args.bibtex, path=args.path, replace=args.replace))
    if command == "bibliometrics-check":
        return print_json(tools.bibliometrics_check(project))
    if command == "bibliometrics-fetch-scimago":
        return print_json(tools.bibliometrics_fetch_scimago(project, scimago_input=args.scimago_input))
    if command == "bibliometrics-update":
        return print_json(
            tools.bibliometrics_update(
                project,
                fetch_scimago=args.fetch_scimago,
                offline=args.offline,
                dry_run=args.dry_run,
                strict_external=args.strict_external,
                require_scimago=args.require_scimago,
            )
        )
    if command == "build-site":
        return print_json(tools.build_site(project, site_profile=args.site_profile))
    if command == "build-health":
        return print_json(tools.build_health(project))
    if command == "http-check":
        return print_json(tools.http_check(args.base_url, paths=args.paths, timeout_seconds=args.timeout_seconds))
    if command == "prompts":
        return print_json(tools.prompt_inventory(factory))
    raise SystemExit(f"unsupported mcp command: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unaltraweb-mcp")
    parser.add_argument("--project", default=".", help="Consumer website workspace. Defaults to current directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version").set_defaults(func=cmd_version)
    sub.add_parser("factory-dir").set_defaults(func=cmd_factory_dir)

    mcp = sub.add_parser("mcp", help="MCP server and JSON helper commands")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    for name in ["serve", "list-tools", "starter-templates", "site-context", "site-check", "profile-check", "manual-source-quality-check", "manual-editorial-quality-check", "manual-authoring-capabilities", "content-inventory", "language-policy", "bibliography-inventory", "bibliometrics-check", "build-health", "prompts"]:
        mcp_sub.add_parser(name)

    for name in ["manual-computation-status", "manual-computation-check"]:
        computation = mcp_sub.add_parser(name)
        computation.add_argument("--source", default="")

    computation_render = mcp_sub.add_parser("manual-computation-render")
    computation_render.add_argument("--source", default="")
    computation_render.add_argument("--confirm-overwrite", action="store_true")

    for name in ["web-capture-status", "web-capture-check"]:
        web_capture = mcp_sub.add_parser(name)
        web_capture.add_argument("--source", default="")

    web_capture_render = mcp_sub.add_parser("web-capture-render")
    web_capture_render.add_argument("--source", default="")
    web_capture_render.add_argument("--confirm-overwrite", action="store_true")

    for name in ["manual-pdf-status", "manual-pdf-build"]:
        manual_pdf = mcp_sub.add_parser(name)
        manual_pdf.add_argument("--language", default="")

    manual_pdf_publish = mcp_sub.add_parser("manual-pdf-publish")
    manual_pdf_publish.add_argument("--language", default="")
    manual_pdf_publish.add_argument("--apply", action="store_true")
    manual_pdf_publish.add_argument("--confirm-publish", action="store_true")

    init_site = mcp_sub.add_parser("initialize-site")
    init_site.add_argument("--template-path", default="")
    init_site.add_argument("--site-profile", default="unaltreselfie")
    init_site.add_argument("--title", default="")
    init_site.add_argument("--baseurl", default="")
    init_site.add_argument("--url", default="")
    init_site.add_argument("--default-lang", default="")
    init_site.add_argument("--languages", default="")
    init_site.add_argument("--force", action="store_true")
    init_site.add_argument("--confirm-overwrite", action="store_true")

    approval = mcp_sub.add_parser("content-approval-inventory")
    approval.add_argument("--status-field", default="")
    approval.add_argument("--approved-value", default="")

    translation = mcp_sub.add_parser("translation-plan")
    translation.add_argument("--target-langs", default="")
    translation.add_argument("--status-field", default="")
    translation.add_argument("--approved-value", default="")

    freshness = mcp_sub.add_parser("content-freshness-check")
    freshness.add_argument("--max-bibliometrics-age-days", type=int, default=180)

    prune_plan = mcp_sub.add_parser("profile-prune-plan")
    prune_plan.add_argument("--site-profile", default="")

    prune = mcp_sub.add_parser("profile-prune")
    prune.add_argument("--site-profile", default="")
    prune.add_argument("--apply", action="store_true")
    prune.add_argument("--confirm-prune", action="store_true")

    add_bib = mcp_sub.add_parser("bibliography-add-entry")
    add_bib.add_argument("--bibtex", required=True)
    add_bib.add_argument("--path", default="_bibliography/papers.bib")
    add_bib.add_argument("--replace", action="store_true")

    fetch = mcp_sub.add_parser("bibliometrics-fetch-scimago")
    fetch.add_argument("--scimago-input", default="")

    update = mcp_sub.add_parser("bibliometrics-update")
    update.add_argument("--fetch-scimago", action="store_true")
    update.add_argument("--offline", action="store_true")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--strict-external", action="store_true")
    update.add_argument("--require-scimago", action="store_true")

    build = mcp_sub.add_parser("build-site")
    build.add_argument("--site-profile", default="")

    http = mcp_sub.add_parser("http-check")
    http.add_argument("--base-url", default="http://127.0.0.1:4000")
    http.add_argument("--paths", nargs="*", default=["/"])
    http.add_argument("--timeout-seconds", type=float, default=5.0)

    mcp.set_defaults(func=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
