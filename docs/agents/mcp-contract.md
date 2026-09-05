# MCP Contract

`unaltraweb` exposes one global, on-demand stdio MCP server for website workspaces. Every client session starts an independently named Dockerized MCP process and mounts its current consumer project at `/workspace` and at its canonical host path. Stable factory, role, and project labels preserve project-scoped lifecycle control without forcing concurrent sessions to share a deterministic container name. The image includes both FastMCP and the Jekyll runtime, so the host does not need Python, the optional `mcp` package, Ruby, or Bundler.

The client registration should launch:

```bash
make --silent --no-print-directory -C ${factoryRoot} mcp-stdio
```

The opened workspace is the consumer website repository. The pending distribution contract selects `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` for the factory logic, without asserting that the remote image exists yet. The launcher reuses it locally or attempts to pull it; an unavailable pending release fails visibly rather than triggering a local fallback build. This is the canonical ContExt command from `mcp-factory.yml`; the transport also sets `MCP_CONSUMER_WORKSPACE=${workspaceFolder}` in the child environment:

```bash
MCP_CONSUMER_WORKSPACE="$PWD" make --silent --no-print-directory -C /path/to/unaltraweb mcp-stdio
```

Replace `/path/to/unaltraweb` with the checkout's absolute path. The bootstrap canonicalizes the inherited environment value after process launch; neither Make nor generated shell source evaluates consumer path text. The declared launcher remains `make`, which ContExt permits for a container runtime without a `runtime.allowed_host_launchers` exception. Restart clients such as OpenCode after changing their MCP registration.

ContExt dependency preparation builds the runtime and required companions but does not initialize consumer content. The transport passes `${workspaceFolder}` only through `MCP_CONSUMER_WORKSPACE`; it never sets `transport.cwd` or embeds the consumer path in a Make assignment. The factory command may therefore use `make -C` without changing or reparsing the selected consumer root. Companion-aware checks and smoke tests include both required providers, while provider updates remain explicit. The manifest does not advertise an `init` command, and both companion dependencies set `init: false`. Use `new_web` explicitly when a new consumer site should be created. Restart long-lived MCP clients after registration, rebuilds, or provider upgrades so their stdio processes use the selected releases.

For a new agent-driven workspace, create or select the empty Git repository first, open that directory in the IDE, register the factory, restart the client, and then call `new_web`. The tool remains confined to the configured project root and does not accept an arbitrary destination. Generated sites include user-owned `README.md` and `AGENTS.md`, profile-specific source directories, and a managed runtime baseline; `scaffold_sync` never rewrites those user-owned guidance or content files.

The Python wheel remains modular. Without a factory checkout it supports `version`, `new-web`, top-level `doctor`, the host-only `import-calibre` command, and the exact package-only MCP inventory declared in `component-contract.json`. The complementary exact inventory fails clearly with `UNALTRAWEB_FACTORY_DIR` remediation. The BOM selects the published `diavisuals v0.3.1` and `vegavisuals v0.3.1` releases. Its `consumer_integration` object is also the single source for the immutable core, workflow, PDF worker, and Vega revisions rendered into consumer scaffolds. Neither companion is bundled in the wheel or MCP server namespace.

Static Vega-Lite and Vega rendering remains owned by the required companion `vegavisuals` MCP dependency. Use its `visualization_status`, `visualization_check`, `render_visualizations`, and `vegavisuals://project/*` resources directly; `unaltraweb` exposes the authoring syntax but does not proxy those tools into the `web://` server.

When companion-owned sources exist, unaltraweb does not accept a caller-provided success boolean and does not proxy the provider implementation. The provider must write `.unaltraweb/receipts/vegavisuals.json` or `.unaltraweb/receipts/diavisuals.json`; `site_check`, `site_doctor`, and `build_site` independently verify the provider identity/version/release, current request hash, exact expected input and artifact inventories, and every input and artifact SHA-256. Missing, stale, malformed, non-finite, oversized, symlinked, inventory-mismatched, or hash-mismatched receipts block the required gate.

A version-1 receipt contains only the provider result contract: `schema_version`, `provider`, `provider_version`, `release`, `request_sha256`, `ok: true`, `inputs`, and `artifacts`. Each non-source input and each artifact has exactly `path` and lowercase `sha256`; unaltraweb independently derives the complete expected input set and rehashes every entry, so omission or modification of a dataset invalidates the receipt. For vegavisuals, expected inputs are the union of top-level manifest `inputs`, each `visualizations[].inputs`, and every project-relative static `data.url` recursively found in the strict JSON specifications. Recursion is bounded. Remote URLs, dynamic URL values or interpolation, query/fragment URLs, absolute paths, traversal, missing files, and symlinked paths are unverifiable errors. For diavisuals, expected inputs are exactly empty until a versioned local-include contract is defined.

The request digest is SHA-256 over `unaltraweb-companion-receipt-v1\0OWNER\0`, followed for each sorted provider source by its UTF-8 project-relative path and bytes, each prefixed by an unsigned eight-byte big-endian length. Vega sources are the manifest and all project Vega/Vega-Lite specifications; diagram sources are all supported Mermaid and PlantUML files. Receipt publication remains provider-owned, but a provider cannot expand or reduce the input inventory accepted by unaltraweb.

## Resources

| Resource | Description |
| --- | --- |
| `web://distribution` | Package-owned component BOM plus offline, feature-aware doctor findings for the current factory and project. |
| `web://site-context` | Site profile, feature flags, content inventory, bibliography, bibliometrics, and build state. |
| `web://site-doctor` | Read-only offline distribution, project-contract, freshness, scaffold-drift, and core-override findings. |
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
| `distribution_doctor` | Return offline component/factory/project findings with stable codes and optional local Docker image inspection that never pulls. |
| `new_web` | Create a profile-specific site from package-owned assets after a complete collision, path, and symlink preflight. |
| `starter_templates` | List package-owned profile scaffolds under the legacy inventory name. |
| `initialize_site` | Compatibility alias for `new_web`; external templates and overwrite mode are rejected. |
| `detect_site` | Detect an unaltraweb consumer from `_config.yml` and `Gemfile`, and report whether its Makefile exposes the native build/serve contract. |
| `site_context` | Read the main local state for an agent session. |
| `site_doctor` | Combine distribution doctor with strict project config, identity/language, generated Make contract, scaffold drift, required generated-output/receipt status, existing HTML audit, companion actions, and core override inventory. Unknown required status is blocking. Read-only and offline. |
| `site_check` | Run profile, freshness, companion visualization/diagram receipt, bibliography, bibliometrics, and build-state checks without network. |
| `site_source_read` | Read one allowed UTF-8 site source and return its exact SHA-256. |
| `site_source_write` | Dry-run or atomically create/update one allowed source. Creates require `create_only`; updates require the exact SHA-256 returned by a read. |
| `site_source_delete` | Dry-run or delete one allowed source with exact SHA-256 and explicit confirmation. It never deletes `_config.yml` or directories. |
| `scaffold_sync` | Dry-run or transactionally synchronize the nine package-managed scaffold controls, including the collaboration contract, Dependabot policy, pull-request template, dependency pins, and deploy caller, against `.unaltraweb/scaffold.json`; edited files are conflicts, exact current package bytes may be adopted without a rewrite, every output is staged, adopted and unchanged files are rechecked before and after the last manifest write, and rollback covers partial apply. README prose remains site-owned. |
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
| `manual_pdf_status` | Inspect PDF configuration, sources, generated artefacts, published paths, selector, and freshness without Docker, network, or writes. |
| `manual_pdf_build` | Build one or all configured language PDFs and first-page cover previews under `tmp/`; `release_selector` defaults to `latest` and is part of the PDF fingerprint. |
| `manual_pdf_publish` | Copy built PDFs and covers to configured public assets. Defaults to dry-run; real publication requires explicit confirmation, and the selector must match the build. |
| `manual_release_status` | Offline, read-only inspection of selector-bound build receipt, HTML audit, PDF evidence, stable policy, and local candidate state. |
| `manual_release_check` | Fail unless the selector-bound candidate exactly matches the current verified source, site, PDF, cover, manifest, and checksums. |
| `manual_release_prepare` | Dry-run or prepare only `tmp/manual-release/<selector>/`. Apply requires explicit confirmation and never tags, pushes, deploys, or creates a GitHub release. Stable local paths are no-clobber evidence, not durable publication. |
| `profile_prune_plan` | List content files whose explicit `profiles:` front matter excludes the selected profile. |
| `profile_prune` | Remove those profile-specific files only after reviewing the plan and passing `confirm_prune=true`. Empty-directory cleanup is descriptor-relative and never follows collection-root or ancestor symlinks. Defaults to dry-run. |
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
| `build_site` | Verify required companion provider receipts, snapshot manual sources, run `make build-native LOCAL_CORE=/opt/unaltraweb` inside the current MCP container, optionally with `SITE_PROFILE` and a release selector, require unchanged sources and `_site` around a clean `html_audit`, then write the selector-bound receipt for `unaltremanual`; this never launches a nested Jekyll container. |
| `build_health` | Inspect existing `_site` artefacts without running Jekyll. |
| `html_audit` | Audit `_site` internal links/assets/fragments, duplicate IDs, unresolved Liquid, image alt attributes, title, and HTML language; inventory external links without fetching them. |
| `preview_start` | Start the single labelled preview container for the current project and wait for HTTP readiness. Port `0` (the default) publishes internal port `4000` on a Docker-assigned loopback host port; a nonzero port requests a fixed host port. |
| `preview_status` | Inspect that project's preview, including browser and container-internal URLs and optional recent logs. |
| `preview_stop` | Remove only that project's labelled preview container. |
| `http_check` | Probe bounded safe paths on the current project's owned labelled preview. The origin is derived internally; redirects and arbitrary origins are rejected. |

Advanced computation, capture, PDF, and bibliometrics tools delegate to factory-owned Make targets against the consumer project. Fresh package scaffolds therefore do not need to copy those implementation targets into each website. A new `unaltremanual` does include a consumer-owned `.unaltraweb/computations.yml` that selects the release's R and Python workers; the first render reuses a local image or pulls that selected image automatically. The worker layers remain external distribution components and are not copied into the wheel or site. The tool names use `bibliometrics_*` even though factory Make targets retain `metrics-*` for backwards compatibility.

`distribution_doctor` findings always include `code`, `severity`, `expected`, `actual`, and `remediation`. Missing factory assets in a direct wheel install produce healthy limited wheel mode, not a false failure. When Docker checks are requested, doctor uses only `docker version` and `docker image inspect`; it does not pull, build, start, or remove anything.

Manual PDF publication is a local workspace operation: it copies reviewed artefacts from `tmp/manual-pdf/` to configured paths such as `assets/pdf/` and `assets/img/`. It never commits, pushes, creates releases, or writes outside the consumer workspace. Use one selector consistently across `manual_pdf_build`, `manual_pdf_publish`, `build_site`, and `manual_release_prepare`. `latest` is the default; stable selectors use `vYYYY.MM(.N)` and require the consumer repository root to be an exact clean Git checkout without nested repositories, submodules, or clean/smudge filters. Stable Jekyll builds run in an MCP image selected by immutable digest, derive `SOURCE_DATE_EPOCH` from the consumer commit, and record both identities in their version-2 candidate manifest. Run `manual_source_quality_check`, `manual_editorial_quality_check`, `manual_pdf_status`, `manual_pdf_build`, and a `manual_pdf_publish` dry-run before calling `manual_pdf_publish(dry_run=false, confirm_publish=true)`. A stable caller additionally submits the SHA-256 of its checked local `tmp/manual-release/<selector>/release-manifest.json`; only the GitHub workflow has tag and release authority.

## New Site Initialization

`new_web` is intended for empty or nearly-empty website repositories. It creates common runtime files, profile-specific configuration, localized home pages, the content paths required by the selected profile, and `.unaltraweb/scaffold.json`. All scaffold assets are shipped inside the `unaltraweb_mcp` Python package and MCP Docker image; environment variables, sibling checkouts, and arbitrary template paths are not consulted.

The `unaltremanual` scaffold also creates `context/writing-profile.md` with a usable default editorial policy and `.unaltraweb/computations.yml` with both BOM-selected workers, `_chapters` and `assets/quarto` source roots, and a generated-asset root. Customize the writing profile for the manual's audience, voice, terminology, evidence policy, language workflow, and review requirements. Computation configuration is consumer-owned rather than scaffold-managed so a project can add lockfiles, dependency paths, or extension Dockerfiles without creating scaffold-sync conflicts. PDF generation and Vega manifests remain opt-in project configuration.

It sets `lang`, `default_lang`, and `languages` so a new site has an explicit source language from the first commit. The default is a single English home page; every configured language gets a localized home-page source and route.

Before writing, it validates every managed path, rejects destination symlinks, and compares existing files with the complete rendered scaffold through bounded regular-file reads. Identical files make repeated calls idempotent. Any differing file or file/directory collision detected during preflight aborts the whole operation before website files are written. Descriptor-relative, no-clobber writes and a final descriptor-relative content check prevent raced paths from being followed or overwritten; overwrite mode is not available. The baseline manifest is created after every other scaffold file.

The baseline records exactly `.gitignore`, `.unaltraweb/docker-mount.sh`, `.github/CONTRIBUTING.md`, `.github/dependabot.yml`, `Makefile`, `Gemfile`, `Gemfile.lock`, `.github/pull_request_template.md`, and `.github/workflows/deploy.yml`. `scaffold_sync` updates one of these while its bytes still match the recorded baseline, adopts it when its bytes already equal the current package payload, creates a newly managed path only when it is absent, and reports other local edits or deletions as conflicts. Any conflict prevents every apply. It removes retired paths only from the baseline and never deletes their project files; it also never changes site-owned README/agent guidance, config, seed content, bibliography, data, or assets. A real synchronization requires `dry_run=false` and `confirm_sync=true`; adopted and unchanged files are included in the final rechecks around the manifest-last commit.

Each scaffold is already reduced to one profile, so `profile_prune_plan` is not part of new-site creation. The prune rule remains available for existing mixed-profile sites.

## Constrained Source Management

The source tools are not generic filesystem operations. Their complete write scope is `_config.yml`; Markdown/HTML under the known content collections; YAML, JSON, or CSV below `_data/`; and Markdown below `context/`. Workflows, Makefiles, Gemfiles, layouts, includes, plugins, Sass, bibliography, binary assets, generated paths, symlinks, directories, absolute paths, and traversal are outside this API.

All operations use project-confined descriptor-relative no-follow traversal. Nonblocking open rejects FIFOs/devices before reading, size is checked before allocation, and files/proposed content are limited to 1 MiB. Text must be UTF-8 without NUL bytes; YAML and JSON reject duplicate keys, and JSON rejects non-finite numbers. Reads return SHA-256. Existing writes require that exact digest; new writes require `create_only=true`. Apply takes an advisory parent lock, moves the expected object to a private backup, verifies content and identity before and after publication, and restores the backup when a final-window edit is detected. Deletes use the equivalent verified tombstone flow. `_config.yml` is never deletable.

## Language And Translation Discipline

Each website should have an explicit default language in `_config.yml`, using `default_lang` and usually `lang` as the HTML fallback. `languages` lists the language variants that are actively maintained.

The language selector is hidden when `languages` contains one language. With multiple languages, the current item is exposed through `aria-current` and the configured default is visibly identified. Visual assets use the same language policy: the unsuffixed source belongs to the default language, a translated source inserts `.<lang>` before its complete suffix, and a missing translated source falls back to the unsuffixed one on web and PDF.

Agents should draft and edit meaningful content in the default language first. Use `content_status: draft`, `content_status: review`, or `content_status: approved` to make editorial state visible. `translation_plan` treats only default-language files with the approved value as ready for translation, then reports missing target-language files by shared `ref`.

Translations are a pre-publication task. They should preserve `ref`, citations, bibliography keys, figures, links, code, data field names, and routing metadata. Existing translations should not be silently rewritten while the default-language source is still changing; mark or report them as stale instead.

## Docker Runtime And Preview

`make mcp-build` builds `ghcr.io/dosquartsdedocs/unaltraweb:0.3.0` and then `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` locally. `make mcp-smoke` runs a real MCP client/server stdio exchange, compiles a temporary minimal site, and exercises preview start/status/stop. `mcp-stdio` remains dormant until a client launches it; dependency preparation never invokes it.

Run `site_doctor` and `site_check`, then resolve any blocking validation result before compiling. `build_site` reuses the active MCP container and the consumer's `build-native` target, and runs the local HTML audit after a successful Jekyll process. The generated `test-native` target also runs `html_audit`. This is intentionally different from the consumer's normal host-side `make build`, which starts a Jekyll container and would create a nested runtime when called from MCP.

Make delegation and feasible Docker control calls use one bounded subprocess runner. Status and control commands have short deadlines, builds/renders have target-specific longer deadlines, timeout terminates the process group and returns code `124`, and retained stdout/stderr is capped with explicit truncation fields. Factory commands that promise JSON fail closed when output is empty, malformed, non-object, non-finite, or truncated. Every bind source and target is encoded as a quoted Docker CSV field, so commas or quotes in host paths cannot introduce duplicate mount fields; carriage-return and newline path characters are rejected before canonicalization or mount construction. Computation, capture, and PDF containers carry factory, worker-role, project, and invocation-token labels plus cidfiles; after timeout cleanup selects all four labels and cannot remove unrelated containers.

A preview must outlive one MCP tool invocation, so it runs in a separate container made from the same MCP/Jekyll image. Its deterministic name is derived from the canonical host project path and it carries the factory, role, and project labels. Its isolated container always listens on port `4000`; the default host port is allocated atomically by Docker on loopback and is reported as `preview_status.port`, preventing the old cross-project collision on host port `4000`. Starting an already-running preview probes it again instead of creating a duplicate. A preview created under the former fixed-port default is accepted as compatible with the new automatic default until it is stopped; its next start uses dynamic allocation. Changing an explicit requested port or profile still requires stopping first. Stdio session containers intentionally have Docker-generated names so independent clients can run simultaneously, but carry the same stable project ID and labels as previews and capture resources. Stop and cleanup operations select ownership labels before removing anything.

`preview_status.url` is the browser URL published on host loopback. `preview_status.internal_url` is informational; callers do not pass it to `http_check`. That tool verifies preview ownership, derives the exact container-internal HTTP origin, disables environment proxies, accepts at most 20 local paths within a bounded timeout and response-read budget, and rejects absolute URLs, protocol-relative forms, traversal, fragments, hostile characters, non-2xx results, and redirects. Preview readiness checks the configured home permalink and generated root candidates rather than guessing a language route. `MCP_CONSUMER_WORKSPACE=/canonical/consumer/path make mcp-down` removes containers and networks selected by both `io.context.mcp-factory=unaltraweb` and the stable project label. A simultaneous `MCP_PROJECT_ID` must match that canonical live path. If the original path has moved or disappeared, pass the absent path with the retained ID or explicitly clear `MCP_CONSUMER_WORKSPACE`; only then is the retained ID accepted without path access. `make mcp-down-all` is the explicit maintainer cleanup for every resource carrying the factory label. Neither target deletes images or touches unlabelled resources.

The Docker socket gives the MCP container authority equivalent to the host Docker user. Enable this factory only for trusted unaltraweb repositories and trusted local images; project Makefiles execute as part of explicit build and authoring tools.

## Bibliography And Bibliometrics Discipline

Agents must not invent BibTeX metadata, DOIs, citekeys, journal details, or bibliometric values. Add entries only from author-provided or verified metadata. Static bibliometrics updates belong in versionable outputs such as `_bibliography/*.bib` and `_data/metrics.yml`; local Scimago caches and diagnostics stay unversioned.
