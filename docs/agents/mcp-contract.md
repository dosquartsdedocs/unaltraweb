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
| `web://language-policy` | Default language, configured languages, and editorial translation workflow settings. |
| `web://content-approval` | Local editorial approval status for default-language and translated content. |
| `web://translation-plan` | Missing translations for approved default-language content before publication. |
| `web://bibliography` | BibTeX files, entry counts, types, duplicate citekeys, and update dates. |
| `web://bibliometrics` | Static bibliometrics summary state and bibliography update dates. |
| `web://build-health` | Existing `_site` build artefacts without starting a server. |
| `web://prompts` | Reusable website workflow prompts. |
| `web://manual-writing-guidance` | Generic drafting and style-review prompts combined with the site's `context/writing-profile.md` when available. |
| `web://manual-authoring-components` | Supported prose structures and component syntax, including callouts, definition lists, figure layouts, tables, diagrams, citations, and web/PDF compatibility. |

## Tools

| Tool | Notes |
| --- | --- |
| `starter_templates` | Discover available starter templates, usually `../unaltraweb-template`. |
| `initialize_site` | Copy a starter site into the workspace and set profile/title/baseurl/url. Existing files are skipped unless overwrite is explicitly forced and confirmed. |
| `site_context` | Read the main local state for an agent session. |
| `site_check` | Run profile, freshness, bibliography, bibliometrics, and build-state checks without network. |
| `profile_check` | Check current profile and expected content/config paths. |
| `manual_source_quality_check` | For `unaltremanual`, check captioned table blocks, captioned figures, and external Mermaid/PlantUML diagram sources. |
| `manual_editorial_quality_check` | Reject non-publishable metatext, user/agent instructions, workflow markers, drafting notes, and placeholders in manual bodies; return the editorial review checklist and local writing-profile path. |
| `manual_authoring_capabilities` | Return the paragraph-development model and structured component catalogue an MCP writing assistant must use. |
| `manual_pdf_status` | Inspect PDF configuration, sources, generated artefacts, published paths, and freshness without writing files. |
| `manual_pdf_build` | Build one or all configured language PDFs and first-page cover previews under `tmp/`. |
| `manual_pdf_publish` | Copy built PDFs and covers to configured public assets. Defaults to dry-run; real publication requires explicit confirmation. |
| `profile_prune_plan` | List content files whose explicit `profiles:` front matter excludes the selected profile. |
| `profile_prune` | Remove those profile-specific files only after reviewing the plan and passing `confirm_prune=true`. Defaults to dry-run. |
| `content_inventory` | Inventory pages, posts, chapters, documentation, data, and assets. |
| `language_policy` | Inspect `lang`, `default_lang`, `languages`, and the default-language-first editorial workflow. |
| `content_approval_inventory` | Summarize `content_status` values, approved default-language sources, and pending default-language content. |
| `translation_plan` | List approved default-language sources, missing target-language files, existing translations, and blocked unapproved sources. |
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

Manual PDF publication is a local workspace operation: it copies reviewed artefacts from `tmp/manual-pdf/` to configured paths such as `assets/pdf/` and `assets/img/`. It never commits, pushes, creates releases, or writes outside the consumer workspace. Run `manual_source_quality_check`, `manual_editorial_quality_check`, `manual_pdf_status`, `manual_pdf_build`, and a `manual_pdf_publish` dry-run before calling `manual_pdf_publish(dry_run=false, confirm_publish=true)`.

## New Site Initialization

`initialize_site` is intended for empty or nearly-empty website repositories. It copies a starter template into the consumer workspace, skips generated folders such as `_site`, `.jekyll-cache`, `.bundle`, `.cache`, `node_modules`, `tmp`, and `vendor`, and updates `_config.yml` with the selected `unaltraweb.site_profile`, `title`, `baseurl`, and `url`.

It can also set `lang`, `default_lang`, and `languages` so a new site has an explicit source language from the first commit.

By default it does not overwrite existing files. Overwrites require both `force=true` and `confirm_overwrite=true`, and agents should only use that combination after explicit user approval.

Use `profile_prune_plan` after initialization when the starter should be reduced to one profile. The prune rule is deliberately conservative: it only targets Markdown/HTML content files with explicit `profiles:` front matter that does not include the selected profile. It does not remove assets, bibliography, `_data`, or unprofiled content. Destructive pruning requires `profile_prune(dry_run=false, confirm_prune=true)` after the plan has been reviewed.

## Language And Translation Discipline

Each website should have an explicit default language in `_config.yml`, using `default_lang` and usually `lang` as the HTML fallback. `languages` lists the language variants that are actively maintained.

Agents should draft and edit meaningful content in the default language first. Use `content_status: draft`, `content_status: review`, or `content_status: approved` to make editorial state visible. `translation_plan` treats only default-language files with the approved value as ready for translation, then reports missing target-language files by shared `ref`.

Translations are a pre-publication task. They should preserve `ref`, citations, bibliography keys, figures, links, code, data field names, and routing metadata. Existing translations should not be silently rewritten while the default-language source is still changing; mark or report them as stale instead.

## HTTP Preview

Jekyll may serve a local HTTP preview, but the MCP itself should stay stdio for now. Agents can build from files, inspect `_site`, or call `http_check` against a preview started by the normal site workflow. This avoids persistent MCP services, port collisions, and `mcp-up`/`mcp-down` complexity.

If a future workflow needs a persistent preview controller, add explicit Make targets such as `mcp-up`, `mcp-down`, and `mcp-status`, and use `context.toggle_mode: service` in `mcp-factory.yml`.

## Bibliography And Bibliometrics Discipline

Agents must not invent BibTeX metadata, DOIs, citekeys, journal details, or bibliometric values. Add entries only from author-provided or verified metadata. Static bibliometrics updates belong in versionable outputs such as `_bibliography/*.bib` and `_data/metrics.yml`; local Scimago caches and diagnostics stay unversioned.
