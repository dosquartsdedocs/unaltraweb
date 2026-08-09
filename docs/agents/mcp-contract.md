# MCP Contract

`unaltraweb` exposes an on-demand stdio MCP server for website workspaces. The MCP is a protocol front end over the same files and Make targets used by child sites; it does not replace Jekyll, and it does not need to run as an HTTP MCP service.

The client registration should launch:

```bash
make -C ${factoryRoot} mcp-stdio PROJECT=${workspaceFolder}
```

The opened workspace is the consumer website repository. Factory logic remains in the `unaltraweb` checkout.

## Resources

| Resource | Description |
| --- | --- |
| `web://site-context` | Site profile, feature flags, content inventory, bibliography, bibliometrics, and build state. |
| `web://starter-templates` | Starter website templates available to initialize a new workspace. |
| `web://profile-contract` | Checks for `unaltreselfie`, `unaltreprojecte`, `unaltremanual`, and `unaltredocs`. |
| `web://profile-prune-plan` | Dry-run list of profile-specific content that can be removed from the active profile. |
| `web://content-inventory` | Local editable collections, `_data/`, and assets. |
| `web://bibliography` | BibTeX files, entry counts, types, duplicate citekeys, and update dates. |
| `web://bibliometrics` | Static bibliometrics summary state and bibliography update dates. |
| `web://build-health` | Existing `_site` build artefacts without starting a server. |
| `web://prompts` | Reusable website workflow prompts. |

## Tools

| Tool | Notes |
| --- | --- |
| `starter_templates` | Discover available starter templates, usually `../unaltraweb-template`. |
| `initialize_site` | Copy a starter site into the workspace and set profile/title/baseurl/url. Existing files are skipped unless overwrite is explicitly forced and confirmed. |
| `site_context` | Read the main local state for an agent session. |
| `site_check` | Run profile, freshness, bibliography, bibliometrics, and build-state checks without network. |
| `profile_check` | Check current profile and expected content/config paths. |
| `profile_prune_plan` | List content files whose explicit `profiles:` front matter excludes the selected profile. |
| `profile_prune` | Remove those profile-specific files only after reviewing the plan and passing `confirm_prune=true`. Defaults to dry-run. |
| `content_inventory` | Inventory pages, posts, chapters, documentation, data, and assets. |
| `content_freshness_check` | Detect stale bibliometrics and future-dated posts/news from local files. |
| `bibliography_inventory` | Inspect BibTeX files and duplicate citekeys. |
| `bibliography_add_entry` | Append a verified BibTeX entry under `_bibliography/`. |
| `bibliometrics_check` | Run `make metrics-check` in the consumer site. |
| `bibliometrics_fetch_scimago` | Run `make metrics-scimago-fetch`. |
| `bibliometrics_update` | Run `make metrics-update` or `make metrics-update-all`. |
| `build_site` | Run `make build`, optionally with `SITE_PROFILE`. |
| `build_health` | Inspect existing `_site` artefacts without running Jekyll. |
| `http_check` | Probe an already-running Jekyll preview over HTTP. |

The tool names use `bibliometrics_*` even though existing Make targets still use `metrics-*` for backwards compatibility.

## New Site Initialization

`initialize_site` is intended for empty or nearly-empty website repositories. It copies a starter template into the consumer workspace, skips generated folders such as `_site`, `.jekyll-cache`, `.bundle`, `.cache`, `node_modules`, `tmp`, and `vendor`, and updates `_config.yml` with the selected `unaltraweb.site_profile`, `title`, `baseurl`, and `url`.

By default it does not overwrite existing files. Overwrites require both `force=true` and `confirm_overwrite=true`, and agents should only use that combination after explicit user approval.

Use `profile_prune_plan` after initialization when the starter should be reduced to one profile. The prune rule is deliberately conservative: it only targets Markdown/HTML content files with explicit `profiles:` front matter that does not include the selected profile. It does not remove assets, bibliography, `_data`, or unprofiled content. Destructive pruning requires `profile_prune(dry_run=false, confirm_prune=true)` after the plan has been reviewed.

## HTTP Preview

Jekyll may serve a local HTTP preview, but the MCP itself should stay stdio for now. Agents can build from files, inspect `_site`, or call `http_check` against a preview started by the normal site workflow. This avoids persistent MCP services, port collisions, and `mcp-up`/`mcp-down` complexity.

If a future workflow needs a persistent preview controller, add explicit Make targets such as `mcp-up`, `mcp-down`, and `mcp-status`, and use `context.toggle_mode: service` in `mcp-factory.yml`.

## Bibliography And Bibliometrics Discipline

Agents must not invent BibTeX metadata, DOIs, citekeys, journal details, or bibliometric values. Add entries only from author-provided or verified metadata. Static bibliometrics updates belong in versionable outputs such as `_bibliography/*.bib` and `_data/metrics.yml`; local Scimago caches and diagnostics stay unversioned.
