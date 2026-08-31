from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from . import calibre_import
from .distribution import distribution_doctor
from . import site_tools as tools


PACKAGE_ONLY_COMMANDS = {"doctor", "import-calibre", "new-web", "version"}
FACTORY_REQUIRED_COMMANDS = {"factory-dir"}
FACTORY_REQUIRED_MCP_COMMANDS = {
    "serve",
    "site-check",
    "manual-computation-status",
    "manual-computation-check",
    "manual-computation-render",
    "manual-computation-render-figures",
    "web-capture-status",
    "web-capture-check",
    "web-capture-render",
    "manual-pdf-status",
    "manual-pdf-build",
    "manual-pdf-publish",
    "bibliometrics-check",
    "bibliometrics-fetch-scimago",
    "bibliometrics-update",
    "build-site",
    "prompts",
}
PACKAGE_ONLY_MCP_COMMANDS = {
    "bibliography-add-entry",
    "bibliography-inventory",
    "build-health",
    "content-approval-inventory",
    "content-freshness-check",
    "content-inventory",
    "detect-site",
    "html-audit",
    "http-check",
    "initialize-site",
    "language-policy",
    "list-tools",
    "manual-authoring-capabilities",
    "manual-editorial-quality-check",
    "manual-source-quality-check",
    "new-web",
    "preview-start",
    "preview-status",
    "preview-stop",
    "profile-check",
    "profile-prune",
    "profile-prune-plan",
    "scaffold-sync",
    "site-context",
    "site-doctor",
    "site-source-delete",
    "site-source-read",
    "site-source-write",
    "starter-templates",
    "translation-plan",
}
ALL_MCP_COMMANDS = FACTORY_REQUIRED_MCP_COMMANDS | PACKAGE_ONLY_MCP_COMMANDS


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_factory_dir() -> Path | None:
    candidates = []
    configured = os.environ.get("UNALTRAWEB_FACTORY_DIR", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path.cwd())
    candidates.append(source_root())
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        manifest_path = resolved / "mcp-factory.yml"
        if not manifest_path.is_file():
            continue
        try:
            manifest = tools.load_yaml_file(manifest_path)
        except Exception:
            # YAML parser failures do not share one exception base across optional loaders.
            continue
        if manifest.get("name") == "unaltraweb":
            return resolved
    return None


def factory_dir(command: str = "") -> Path:
    factory = find_factory_dir()
    if factory is not None:
        return factory
    label = f"MCP command '{command}'" if command else "This command"
    raise SystemExit(
        f"{label} requires the unaltraweb factory checkout. The modular wheel provides version, doctor, new-web, import-calibre, "
        "and package-only inspection without factory assets; set UNALTRAWEB_FACTORY_DIR to a checkout containing mcp-factory.yml."
    )


def project_dir(raw: str | None) -> Path:
    return tools.project_path(raw)


def print_json(payload: object, *, enforce_ok: bool = False) -> int:
    print(tools.dumps(payload), end="")
    return 1 if enforce_ok and isinstance(payload, dict) and payload.get("ok") is False else 0


def cmd_version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def cmd_factory_dir(_: argparse.Namespace) -> int:
    print(factory_dir("factory-dir"))
    return 0


def cmd_new_web(args: argparse.Namespace) -> int:
    return print_json(
        tools.new_web(
            Path(args.project or os.getcwd()),
            site_profile_value=args.site_profile,
            title=args.title,
            baseurl=args.baseurl,
            url=args.url,
            default_lang=args.default_lang,
            languages=args.languages,
        ),
        enforce_ok=True,
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    raw_project = args.doctor_project if args.doctor_project is not None else args.project
    project = project_dir(raw_project) if raw_project is not None else None
    return print_json(
        distribution_doctor(project=project, factory=find_factory_dir(), check_docker=args.docker),
        enforce_ok=True,
    )


def cmd_import_calibre(args: argparse.Namespace) -> int:
    labels = {
        lang: label
        for lang, label in {
            "en": args.collection_en,
            "es": args.collection_es,
            "ca": args.collection_ca,
        }.items()
        if label
    }
    result = calibre_import.import_calibre(
        project_dir(args.project),
        library=args.library,
        source_key=args.source_key,
        collection_name=args.collection_name,
        collection_ref=args.collection_ref,
        collection_labels=labels,
        profiles=args.profiles,
        ids=args.ids,
        lang=args.lang,
        status=args.status,
        rating=args.rating,
        limit=args.limit,
        write=args.write,
        refresh_existing=args.refresh_existing,
    )
    calibre_import.print_summary(result)
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    project = project_dir(args.project)
    command = args.mcp_command
    factory = factory_dir(command) if command in FACTORY_REQUIRED_MCP_COMMANDS else find_factory_dir()
    if command == "serve":
        from .mcp_server import run_server

        run_server(project=project, factory=factory)
        return 0
    if command == "list-tools":
        return print_json(tools.list_tools())
    if command == "starter-templates":
        return print_json(tools.starter_templates(factory))
    if command == "detect-site":
        return print_json(tools.detect_site(project))
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
    if command == "new-web":
        return cmd_new_web(args)
    if command == "site-context":
        return print_json(tools.site_context(project, factory))
    if command == "site-doctor":
        return print_json(tools.site_doctor(project, factory), enforce_ok=True)
    if command == "site-check":
        return print_json(tools.site_check(project, factory), enforce_ok=True)
    if command == "site-source-read":
        return print_json(tools.site_source_read(project, args.path))
    if command == "site-source-write":
        return print_json(
            tools.site_source_write(
                project,
                args.path,
                args.content,
                expected_sha256=args.expected_sha256,
                create_only=args.create_only,
                dry_run=not args.apply,
            )
        )
    if command == "site-source-delete":
        return print_json(
            tools.site_source_delete(
                project,
                args.path,
                expected_sha256=args.expected_sha256,
                dry_run=not args.apply,
                confirm_delete=args.confirm_delete,
            )
        )
    if command == "scaffold-sync":
        return print_json(
            tools.scaffold_sync(project, dry_run=not args.apply, confirm_sync=args.confirm_sync),
            enforce_ok=True,
        )
    if command == "profile-check":
        return print_json(tools.profile_check(project), enforce_ok=True)
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
        return print_json(tools.manual_computation_render(project, factory, source=args.source, confirm_overwrite=args.confirm_overwrite, stale_only=args.stale_only))
    if command == "manual-computation-render-figures":
        return print_json(tools.manual_computation_render_figures(project, factory))
    if command == "web-capture-status":
        return print_json(tools.web_capture_status(project, factory, source=args.source))
    if command == "web-capture-check":
        return print_json(tools.web_capture_check(project, factory, source=args.source), enforce_ok=True)
    if command == "web-capture-render":
        return print_json(tools.web_capture_render(project, factory, source=args.source, confirm_overwrite=args.confirm_overwrite))
    if command == "manual-pdf-status":
        return print_json(tools.manual_pdf_status(project, factory, language=args.language))
    if command == "manual-pdf-build":
        return print_json(tools.manual_pdf_build(project, factory, language=args.language))
    if command == "manual-pdf-publish":
        return print_json(tools.manual_pdf_publish(project, factory, language=args.language, dry_run=not args.apply, confirm_publish=args.confirm_publish))
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
        return print_json(tools.bibliometrics_check(project, factory))
    if command == "bibliometrics-fetch-scimago":
        return print_json(tools.bibliometrics_fetch_scimago(project, factory, scimago_input=args.scimago_input))
    if command == "bibliometrics-update":
        return print_json(
            tools.bibliometrics_update(
                project,
                factory,
                fetch_scimago=args.fetch_scimago,
                offline=args.offline,
                dry_run=args.dry_run,
                strict_external=args.strict_external,
                require_scimago=args.require_scimago,
            )
        )
    if command == "build-site":
        return print_json(tools.build_site(project, factory, site_profile=args.site_profile), enforce_ok=True)
    if command == "build-health":
        return print_json(tools.build_health(project))
    if command == "html-audit":
        return print_json(tools.html_audit(project), enforce_ok=True)
    if command == "preview-start":
        return print_json(tools.preview_start(project, port=args.port, site_profile=args.site_profile, timeout_seconds=args.timeout_seconds))
    if command == "preview-status":
        return print_json(tools.preview_status(project, include_logs=args.include_logs))
    if command == "preview-stop":
        return print_json(tools.preview_stop(project))
    if command == "http-check":
        return print_json(tools.http_check(project, paths=args.paths, timeout_seconds=args.timeout_seconds), enforce_ok=True)
    if command == "prompts":
        return print_json(tools.prompt_inventory(factory))
    raise SystemExit(f"unsupported mcp command: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unaltraweb-mcp")
    parser.add_argument("--project", default=None, help="Consumer website workspace. Defaults to current directory for project commands.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version").set_defaults(func=cmd_version)
    sub.add_parser("factory-dir").set_defaults(func=cmd_factory_dir)

    doctor = sub.add_parser("doctor", help="Inspect the modular distribution contract without network access")
    doctor.add_argument("--project", dest="doctor_project", default=None, help="Optional consumer project to inspect.")
    doctor.add_argument("--docker", action="store_true", help="Inspect selected local Docker images without pulling.")
    doctor.set_defaults(func=cmd_doctor)

    new_web = sub.add_parser("new-web", help="Create a website from a package-owned profile scaffold")
    _add_new_web_arguments(new_web)
    new_web.set_defaults(func=cmd_new_web)

    calibre = sub.add_parser(
        "import-calibre",
        help="Import Calibre metadata and covers from a host library (dry-run unless --write is passed)",
    )
    _add_calibre_arguments(calibre)
    calibre.set_defaults(func=cmd_import_calibre)

    mcp = sub.add_parser("mcp", help="MCP server and JSON helper commands")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    for name in ["serve", "list-tools", "starter-templates", "detect-site", "site-context", "site-doctor", "site-check", "profile-check", "manual-source-quality-check", "manual-editorial-quality-check", "manual-authoring-capabilities", "content-inventory", "language-policy", "bibliography-inventory", "bibliometrics-check", "build-health", "html-audit", "preview-stop", "prompts"]:
        mcp_sub.add_parser(name)

    source_read = mcp_sub.add_parser("site-source-read")
    source_read.add_argument("--path", required=True)

    source_write = mcp_sub.add_parser("site-source-write")
    source_write.add_argument("--path", required=True)
    source_write.add_argument("--content", required=True)
    source_write.add_argument("--expected-sha256", default="")
    source_write.add_argument("--create-only", action="store_true")
    source_write.add_argument("--apply", action="store_true")

    source_delete = mcp_sub.add_parser("site-source-delete")
    source_delete.add_argument("--path", required=True)
    source_delete.add_argument("--expected-sha256", required=True)
    source_delete.add_argument("--apply", action="store_true")
    source_delete.add_argument("--confirm-delete", action="store_true")

    scaffold_sync = mcp_sub.add_parser("scaffold-sync")
    scaffold_sync.add_argument("--apply", action="store_true")
    scaffold_sync.add_argument("--confirm-sync", action="store_true")

    mcp_new_web = mcp_sub.add_parser("new-web")
    _add_new_web_arguments(mcp_new_web)

    for name in ["manual-computation-status", "manual-computation-check"]:
        computation = mcp_sub.add_parser(name)
        computation.add_argument("--source", default="")

    computation_render = mcp_sub.add_parser("manual-computation-render")
    computation_render.add_argument("--source", default="")
    computation_render.add_argument("--confirm-overwrite", action="store_true")
    computation_render.add_argument("--stale-only", action="store_true")

    mcp_sub.add_parser("manual-computation-render-figures")

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
    add_bib.add_argument("--path", default="")
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

    preview_start = mcp_sub.add_parser("preview-start")
    preview_start.add_argument("--port", type=int, default=4000)
    preview_start.add_argument("--site-profile", default="")
    preview_start.add_argument("--timeout-seconds", type=float, default=60.0)

    preview_status = mcp_sub.add_parser("preview-status")
    preview_status.add_argument("--include-logs", action="store_true")

    http = mcp_sub.add_parser("http-check")
    http.add_argument("--paths", nargs="*", default=None)
    http.add_argument("--timeout-seconds", type=float, default=3.0)

    mcp.set_defaults(func=cmd_mcp)
    return parser


def _add_new_web_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--site-profile", choices=sorted(tools.PROFILE_CONTRACTS), default="unaltreselfie")
    parser.add_argument("--title", default="")
    parser.add_argument("--baseurl", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--default-lang", default="")
    parser.add_argument("--languages", default="")


def _add_calibre_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library", required=True, type=Path, help="Calibre library directory")
    parser.add_argument("--source-key", required=True, type=calibre_import.parse_source_key, help="Stable source key, for example gis")
    parser.add_argument("--collection-name", required=True, help="Reading collection name")
    parser.add_argument("--collection-ref", help="Stable reading collection key")
    parser.add_argument("--collection-en", help="English reading collection label")
    parser.add_argument("--collection-es", help="Spanish reading collection label")
    parser.add_argument("--collection-ca", help="Catalan reading collection label")
    parser.add_argument("--profiles", required=True, type=calibre_import.parse_profiles, help="Comma-separated profiles")
    parser.add_argument("--ids", type=calibre_import.parse_ids, help="Comma-separated Calibre book IDs to import")
    parser.add_argument("--lang", type=calibre_import.parse_language, help="Generated page language; defaults to the site's default language")
    parser.add_argument("--status", default="queued", help="Reading status")
    parser.add_argument(
        "--rating",
        type=calibre_import.parse_rating,
        help="Manual project rating from 0 to 5; Calibre ratings are never imported",
    )
    parser.add_argument("--limit", type=calibre_import.parse_limit, help="Limit number of new books")
    parser.add_argument("--write", action="store_true", help="Write Markdown files and copy covers")
    parser.add_argument("--refresh-existing", action="store_true", help="Rewrite matching imported Markdown files")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
