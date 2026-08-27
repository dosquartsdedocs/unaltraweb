# MCP Contract

`unaltraweb` exposes one global, on-demand stdio MCP server for website workspaces. Every client session starts a Dockerized MCP process and mounts its current consumer project at `/workspace` and at its canonical host path. The image includes both FastMCP and the Jekyll runtime, so the host does not need Python, the optional `mcp` package, Ruby, or Bundler.

The client registration should launch:

```bash
make --silent --no-print-directory -C ${factoryRoot} mcp-stdio 'PROJECT=${workspaceFolder}'
```

The opened workspace is the consumer website repository. Factory logic is embedded in `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0`. The launcher pulls that public image when it is not already present. Global clients that do not substitute `${workspaceFolder}` must preserve their startup directory before `make -C` runs:

```bash
/bin/sh -c 'exec env PROJECT="$PWD" make --silent --no-print-directory -C /path/to/unaltraweb mcp-stdio'
```

Replace `/path/to/unaltraweb` with the checkout's absolute path. `PROJECT=.` is invalid in that global form because it resolves to the factory checkout after `make -C`. Restart clients such as OpenCode after changing their MCP registration.

Static Vega-Lite and Vega rendering remains owned by the required companion `vegavisuals` MCP dependency. Use its `visualization_status`, `visualization_check`, `render_visualizations`, and `vegavisuals://project/*` resources directly; `unaltraweb` exposes the authoring syntax but does not proxy those tools into the `web://` server.

When `.vegavisuals.yml` exists, `site_check` reports the delegated `visualization_check` requirement without trying to execute the companion CLI inside the unaltraweb container. Run that check through the separately registered `vegavisuals` MCP before `build_site`.

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
| `web://prompts` | Registered prompt names, descriptions, arguments, source files, and availability. |
| `web://manual-writing-guidance` | Generic drafting and style-review prompts combined with the site's `context/writing-profile.md` when available. |
| `web://manual-authoring-components` | Supported prose structures and component syntax, including callouts, definition lists, figure layouts, tables, diagrams, citations, and web/PDF compatibility. |
| `web://manual-computations` | Executable manual sources, selected runtime images, generated outputs, and freshness state. |
| `web://web-captures` | Selector-based screenshot recipes, original PNGs, editable SVG layers, edited overrides, and freshness. |
| `web://new-web-scaffolds` | Package-owned scaffold availability and contract paths for every supported site profile. |

## Tools

| Tool | Notes |
| --- | --- |
| `new_web` | Create a profile-specific site from package-owned assets after a complete collision, path, and symlink preflight. |
| `starter_templates` | List package-owned profile scaffolds under the legacy inventory name. |
| `initialize_site` | Compatibility alias for `new_web`; external templates and overwrite mode are rejected. |
| `detect_site` | Detect an unaltraweb consumer from `_config.yml` and `Gemfile`, and report whether its Makefile exposes the native build/serve contract. |
| `site_context` | Read the main local state for an agent session. |
| `site_check` | Run profile, freshness, bibliography, bibliometrics, and build-state checks without network. |
| `profile_check` | Check current profile and expected content/config paths. |
| `manual_source_quality_check` | For `unaltremanual`, check captioned tables and figures, resolve local visual sources, compare embedded SVG text with body text on web/PDF, and suggest support-specific dimensions. |
| `manual_editorial_quality_check` | Reject non-publishable metatext, user/agent instructions, workflow markers, drafting notes, and placeholders in manual bodies; return the editorial review checklist and local writing-profile path. |
| `manual_authoring_capabilities` | Return the paragraph-development model and structured component catalogue an MCP writing assistant must use. |
| `manual_computation_status` | Inspect executable manual sources, selected images, generated outputs, and freshness without executing code. |
| `manual_computation_check` | Reject missing, modified, orphaned, or stale generated Markdown and figures. |
| `manual_computation_render` | Execute trusted sources in network-disabled containers and atomically publish declared outputs. |
| `manual_computation_render_figures` | Render only stale figure-mode computation sources without touching fresh outputs. |
| `web_capture_status` | Inspect `.capture.yml` recipes, PNG/SVG artefacts, edited overrides, and freshness without starting Chromium. |
| `web_capture_check` | Reject missing, modified, stale, orphaned, or obsolete edited capture artefacts. |
| `web_capture_render` | Start Jekyll and Chromium on an ephemeral internal Docker network, then publish original PNG plus editable annotated SVG from declared CSS selectors. |
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
| `bibliometrics_check` | Run the factory's offline metrics check against the consumer project. |
| `bibliometrics_fetch_scimago` | Fetch or validate Scimago input through the factory against the consumer project. |
| `bibliometrics_update` | Run the factory's metrics update against the consumer project. |
| `build_site` | Run `make build-native LOCAL_CORE=/opt/unaltraweb` inside the current MCP container, optionally with `SITE_PROFILE`; this never launches a nested Jekyll container. |
| `build_health` | Inspect existing `_site` artefacts without running Jekyll. |
| `preview_start` | Start the single labelled preview container for the current project and wait for HTTP readiness. |
| `preview_status` | Inspect that project's preview, including browser and container-internal URLs and optional recent logs. |
| `preview_stop` | Remove only that project's labelled preview container. |
| `http_check` | Probe an already-running Jekyll preview over HTTP. |

Advanced computation, capture, PDF, and bibliometrics tools delegate to factory-owned Make targets against the consumer project. Fresh package scaffolds therefore do not need to copy those implementation targets into each website. The tool names use `bibliometrics_*` even though factory Make targets retain `metrics-*` for backwards compatibility.

Manual PDF publication is a local workspace operation: it copies reviewed artefacts from `tmp/manual-pdf/` to configured paths such as `assets/pdf/` and `assets/img/`. It never commits, pushes, creates releases, or writes outside the consumer workspace. Run `manual_source_quality_check`, `manual_editorial_quality_check`, `manual_pdf_status`, `manual_pdf_build`, and a `manual_pdf_publish` dry-run before calling `manual_pdf_publish(dry_run=false, confirm_publish=true)`.

## New Site Initialization

`new_web` is intended for empty or nearly-empty website repositories. It creates common runtime files, profile-specific configuration, localized home pages, and the content paths required by the selected profile. All scaffold assets are shipped inside the `unaltraweb_mcp` Python package and MCP Docker image; environment variables, sibling checkouts, and arbitrary template paths are not consulted.

The `unaltremanual` scaffold also creates `context/writing-profile.md` with a usable default editorial policy. Customize that local file for the manual's audience, voice, terminology, evidence policy, language workflow, and review requirements.

It sets `lang`, `default_lang`, and `languages` so a new site has an explicit source language from the first commit. The default is a single English home page; every configured language gets a localized home-page source and route.

Before writing, it validates every managed path, rejects destination symlinks, and compares existing files with the complete rendered scaffold. Identical files make repeated calls idempotent. Any differing file or file/directory collision detected during preflight aborts the whole operation before website files are written. Descriptor-relative, no-clobber writes and a final descriptor-relative content check prevent raced paths from being followed or overwritten; overwrite mode is not available.

Each scaffold is already reduced to one profile, so `profile_prune_plan` is not part of new-site creation. The prune rule remains available for existing mixed-profile sites.

## Language And Translation Discipline

Each website should have an explicit default language in `_config.yml`, using `default_lang` and usually `lang` as the HTML fallback. `languages` lists the language variants that are actively maintained.

The language selector is hidden when `languages` contains one language. With multiple languages, the current item is exposed through `aria-current` and the configured default is visibly identified. Visual assets use the same language policy: the unsuffixed source belongs to the default language, a translated source inserts `.<lang>` before its complete suffix, and a missing translated source falls back to the unsuffixed one on web and PDF.

Agents should draft and edit meaningful content in the default language first. Use `content_status: draft`, `content_status: review`, or `content_status: approved` to make editorial state visible. `translation_plan` treats only default-language files with the approved value as ready for translation, then reports missing target-language files by shared `ref`.

Translations are a pre-publication task. They should preserve `ref`, citations, bibliography keys, figures, links, code, data field names, and routing metadata. Existing translations should not be silently rewritten while the default-language source is still changing; mark or report them as stale instead.

## Docker Runtime And Preview

`make mcp-build` builds `ghcr.io/dosquartsdedocs/unaltraweb:0.3.0` and then `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` locally. `make mcp-smoke` runs a real MCP client/server stdio exchange, compiles a temporary minimal site, and exercises preview start/status/stop. `mcp-stdio` remains dormant until a client launches it.

Run `site_check` and resolve any blocking validation result before compiling. `build_site` then reuses the active MCP container and the consumer's `build-native` target. This is intentionally different from the consumer's normal host-side `make build`, which starts a Jekyll container and would create a nested runtime when called from MCP.

A preview must outlive one MCP tool invocation, so it runs in a separate container made from the same MCP/Jekyll image. Its deterministic name is derived from the canonical host project path and it carries the factory, role, and project labels. Starting an already-running preview probes it again instead of creating a duplicate; changing its port or profile requires stopping it first. Stop and cleanup operations verify ownership labels before removing anything.

`preview_status.url` is the browser URL published on host loopback. `preview_status.internal_url` is reachable from the MCP container and can be passed to `http_check`. `make mcp-down` force-removes all and only containers selected by `label=io.context.mcp-factory=unaltraweb`; it does not delete images or touch ordinary site containers.

The Docker socket gives the MCP container authority equivalent to the host Docker user. Enable this factory only for trusted unaltraweb repositories and trusted local images; project Makefiles execute as part of explicit build and authoring tools.

## Bibliography And Bibliometrics Discipline

Agents must not invent BibTeX metadata, DOIs, citekeys, journal details, or bibliometric values. Add entries only from author-provided or verified metadata. Static bibliometrics updates belong in versionable outputs such as `_bibliography/*.bib` and `_data/metrics.yml`; local Scimago caches and diagnostics stay unversioned.
