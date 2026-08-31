# TODO

## Purpose

`unaltraweb` is the reusable Jekyll core/platform for `dosquartsdedocs` websites. It provides shared layouts, includes, styles, plugins, bibliography tooling, multilingual behaviour, theme modes, documentation and reusable workflows for thin child repositories such as `../unaltraweb-template`.

Use the term **site profile** for prepared website families such as `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`. Avoid calling these layouts or includes, because those words already have precise Jekyll meanings.

The goal is not to maintain one personal site here. The goal is to make a self-owned alternative to the inherited `al-folio` base, supporting academic personal sites, research project sites and documentation/course sites.

## Current Shape

- Core repo: `/home/benizar/git/unaltraweb`.
- Template repo: `/home/benizar/git/unaltraweb-template`.
- Legacy personal-site reference: `/home/benizar/git/benizar.github.io`.
- Acceptance manual `tig`: intentionally absent; recreate it from the package-owned scaffold when testing on another machine.
- Remote for this repo: `git@github.com:dosquartsdedocs/unaltraweb.git`.
- Baseline before the current documentation cleanup: `842e9ee Improve multilingual blog and footer defaults`.
- Baseline companion template commit: `1877e52 Localize personal blog demo content`.

## Repository Split

- `unaltraweb` owns reusable code: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows and core documentation.
- `unaltraweb_mcp` owns clean package scaffolds for all four profiles; `unaltraweb-template` owns richer demo content, local workflow glue and Playwright integration tests.
- The template is the preferred place to prove gem consumption and centralized style/logic behaviour because it exercises `unaltraweb` as an external dependency.
- `docs/` in this repo contains the public `unaltraweb` reference site. It should explain tools, requirements, usage, profiles, themes and syntax without duplicating the template's full demo.

## Design Decisions

- Keep Jekyll builds static. Do not call OpenAlex, Crossref, Scimago, Google Scholar, Medium or other external services during `jekyll build`.
- Metrics update scripts may fetch data manually, locally or through an explicit workflow, but normal builds must use local files only.
- Keep reusable functionality in `unaltraweb`; keep `unaltraweb-template` thin.
- Use Docker-first commands for child sites so users can run `make serve`, `make build`, `make test` and `make down` without remembering Docker details. The package-owned common scaffold now provides this contract through the MCP image.
- Do not add backward-compatibility branches unless there is a concrete persisted-data, shipped-behaviour or external-consumer need.
- Preserve small, minimal changes where possible. Avoid broad abstractions before there is a clear second consumer.
- Move away from `al-folio` identity and demo defaults over time, while keeping useful inherited code until it is replaced.

## Implemented Recently

- Packaged `unaltraweb` as a reusable Jekyll theme/plugin gem.
- Exposed core `_config.yml` and `requirements.txt` in the gem.
- Made core stylesheet/cache-busting behaviour safe when used as a theme gem.
- Added static bibliometrics tooling and docs under `scripts/biblio/` and `docs/bibliometrics.md`.
- Disabled inherited `external_sources` by default so builds do not fetch Medium/Google posts.
- Added `profile` layout, `profile-card` include and `profile-highlights.liquid` for personal-site home pages.
- Added profile i18n keys in English, Spanish and Catalan.
- Added `site.unaltraweb.site_profile` DOM markers: `data-site-profile` on `<html>` and `site-profile-*` on `<body>`.
- Added config-driven feature navigation through `site.unaltraweb.features`.
- Added theme mode rotation: `system -> light -> coffee -> dark -> system`.
- Added `data-theme-setting`, `data-theme`, `data-theme-integration` and `unaltraweb:themechange` for tests and local scripts.
- Added `_sass/_site-custom.scss` as a local child-site style extension point and documented it in `docs/customization.md`.
- Added reusable personal-site blog archives, direct-link project cards, project resource badges and CV PDF download/preview card components.
- Added real profile filtering for pages/documents through `profiles: [...]` and `site.unaltraweb.site_profile`.
- Added manual profile support: manual home/chapter layouts, sticky sidebar, right rail TOC, localized chapter routing, teacher blocks, figure/table numbering, manual bibliography mode, manual search index and reader font controls.
- Added reusable deploy workflow at `.github/workflows/site-deploy.yml`.
- Replaced inherited top-level user docs with short `unaltraweb`-specific `README.md`, `INSTALL.md`, `CUSTOMIZE.md`, `FAQ.md` and `CONTRIBUTING.md`.
- Added and expanded the `unaltraweb` reference site under `docs/` with overview, quick start, tools, usage, profiles, syntax, themes, customization, template role and development pages.
- Replaced the core repo deploy workflow with a lightweight GitHub Pages Actions workflow that builds `docs/` only.
- Replaced the post-deploy link checker with a docs-only offline link check.
- Added a manual/reusable publication metrics workflow at `.github/workflows/metrics-update.yml`.
- Kept publication metrics PRs focused on versionable generated data: `_bibliography/**/*.bib` and `_data/metrics.yml`. Scimago caches and diagnostics remain unversioned.
- Added automatic multi-language CodeQL and bounded PR/push CI without enabling automatic publication.
- Fixed `scripts/biblio/fetch_scimago_csv.sh` so it validates Scimago data through its own script directory when called from child repositories.
- Added clearer metrics failure reporting for missing Scimago data and OpenAlex/Crossref request errors.
- Exposed local `METRICS_ARGS` and `SCIMAGO_INPUT` Makefile controls in both core and template repos.
- Added a GHCR Docker image workflow for `ghcr.io/dosquartsdedocs/unaltraweb` and switched core/template local Docker defaults away from the inherited `al-folio` image.
- Added quick-start documentation for GitHub-only editing, local Docker/Make work, Windows WSL2 usage, GHCR public-image requirements and the core/template/demo split.
- Set the local port convention to `4000` for `unaltraweb` and `4001`-`4004` for the four template profile servers.
- Added an initial feature/syntax coverage map for the `unaltraweb` reference site.
- Expanded the `unaltraweb` reference site with tools/requirements, usage, profile screenshots, content syntax, theme modes and customization pages.

## Companion Template State

`../unaltraweb-template` is the integration fixture for this core and currently exercises all four site profiles plus generated diagram assets.

Important current template behaviour:

- Personal demo profile uses fictional John Doe/Juan Nadie/Joan Ningu placeholder content.
- Localized home pages `/en/`, `/es/`, `/ca/` use `layout: profile`.
- Optional localized `blog`, `CV`, `projects`, `publications`, `outputs`, `repositories`, `readings`, `team` and manual pages exercise feature/profile routing.
- Demo project entries live in `_projects/`.
- Demo blog entries live in `_posts/`.
- Demo manual chapters live in `_chapters/` for English, Spanish and Catalan.
- Blog pagination is enabled in the template demo.
- Demo CV PDF and generated first-page preview live in `assets/pdf/cv.pdf` and `assets/img/cv-preview.jpg`.
- The template Makefile supports `LOCAL_CORE=../unaltraweb` and `SITE_PROFILE=unaltreselfie|unaltreprojecte|unaltremanual|unaltredocs`.
- Playwright render smoke tests verify `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs` profiles, desktop/mobile rendering, theme modes and screenshots.
- The template deploy workflow calls `.github/workflows/site-deploy.yml` from this core.
- The template manual `Update publication metrics` workflow calls `.github/workflows/metrics-update.yml` from this core.
- The package scaffold local runtime defaults to the selected `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0`; the external template fixture should align its consumer defaults while `LOCAL_CORE=../unaltraweb` remains the side-by-side development path.
- The template README explains the four profiles, the GitHub-only content workflow and the local Docker workflow.

## Next Work

### 0.3.0 Handoff

The platform checks pass, but six `0.3.0` components remain `pending`: `gem`, `wheel`, `runtime`, `mcp`, `manual_pdf` and `web_capture`. The selected Python/R computation images and both visual companions are already released. Do not create a release tag or `release-candidates.json` before the pending candidates exist.

On the next machine:

1. Clone this repository, check out the pushed feature branch, and rerun `make workflow-check`, `make distribution-check`, `make gem-check`, `make wheel-check`, `make mcp-check`, `make mcp-smoke` and `make docs-build`.
2. Review and merge the branch into the default branch. Candidate workflows deliberately reject other branches.
3. Recreate the acceptance manual with `unaltraweb-mcp --project /path/to/tig new-web --site-profile unaltremanual --title TIG --baseurl /tig --default-lang ca --languages ca`, then run `make test` inside it. Start a preview and verify both `/tig/` and `/tig/ca/`; the generated files must belong to the host user and the root redirect must not appear in content search.
4. In the final reviewed source commit, change only the six pending component statuses to `ready`. MCP remains `ready` permanently because embedding its own release digest would be self-referential. Commit and push that source state before producing candidates.
5. Manually run `Prepare package candidates`, `Docker images` and `Web capture image` from that exact default-branch commit. Preserve the package workflow's gem/wheel files and `SHA256SUMS`; record the immutable GHCR digests for runtime, MCP, manual PDF and web capture.
6. Add `release-candidates.json` in one immediate child commit and change no other path. Set `source_commit` to the candidate source SHA. Include the exact gem/wheel basenames and checksums plus the four official `ghcr.io/dosquartsdedocs/...@sha256:...` references. Run `make distribution-release-check`; it validates the receipt, default-branch ancestry, package identities and image repositories.
7. Tag the receipt commit as `v0.3.0`. Run the image workflows from that exact tag; they verify that each full-SHA candidate tag still resolves to the recorded digest and promote the recorded manifests without rebuilding.
8. Publish the recorded gem and wheel through the separately approved RubyGems/PyPI operations, make every new GHCR package public, and verify unauthenticated pulls/installations. No workflow in this repository performs those language-package uploads automatically.
9. Prove the user path from a clean checkout with no sibling core: create a new manual, run `make test`, start/stop its MCP preview, and confirm `unaltraweb (= 0.3.0)` and `unaltraweb-mcp==0.3.0` resolve remotely.

Residual external checks: run `actionlint` if available and inspect the first live GitHub Actions/GHCR promotion carefully. The local suite cannot exercise credentialed registry mutation. `tigit` was clean and synchronized at `ecb5dc8` at the end of the previous session; do not mix its editorial history into the core release.

### MCP Contract

- Initial stdio MCP scaffold exists under `src/unaltraweb_mcp/`, with `mcp-factory.yml`, Make targets, reusable prompts, and a plugin skeleton under `plugins/unaltraweb-site/`.
- The `unaltraweb` MCP is for agent-assisted site maintenance: updating pages/posts/news, adding bibliography entries, editing project/output/team data, checking profile-specific content contracts and preparing deploy-safe content changes.
- The MCP declares `diavisuals` as a required MCP dependency instead of embedding Mermaid, PlantUML, Chromium or Java in this repository.
- The dependency manifest should use the shared fields understood by ContExt:

```yaml
mcp_dependencies:
  - name: diavisuals
    role: shared-diagram-renderer
    required: true
    install: true
    build: true
    init: false
    remote: https://github.com/dosquartsdedocs/diavisuals.git
    package: diavisuals
    version: 0.3.1
    release: v0.3.1
    release_status: released
    extras:
      - mcp
    required_tools:
      - project_check
      - render_diagram
      - render_diagram_text
    suggested_path: ../diavisuals
```

- Diagram-editing MCP tools should prefer SVG output. When a source diagram has a matching `*.edited.svg`, the tool must ask the user whether to preserve the edited SVG or replace it with a regenerated SVG before changing or discarding that author-edited file.
- Normal Jekyll builds should stay non-interactive: the Jekyll filter may render a missing/stale generated SVG through `diavisuals` when available, but it must never overwrite `*.edited.svg`.

### Docker-First Distribution And Child-Site Contract

- The recommended new-site workflow is the package-owned `new_web` operation exposed through API, CLI, Make, and MCP. It creates one clean profile and never depends on a sibling checkout.
- Treat `unaltraweb-template` as a multi-profile demo and integration fixture, not as the product or a runtime dependency. Real child sites should keep content, configuration and local assets; reusable layouts, includes, plugins, Sass, JS and build scripts should stay centralized in `unaltraweb`.
- Define the stable child-site contract: profile config, collections, front matter keys, local data files, bibliography/books/projects/content assets, `site-custom` extension points and generated diagram sources. Also define what remains explicitly non-contractual and can change inside the core.
- Audit which JS/CSS/assets currently live in child repos versus the gem/core. Any copied core code in child sites should either move into `unaltraweb` or be marked as a deliberate local override.
- Continue hardening Docker as the primary user-facing runtime: users should only need Docker plus Git for normal local `make serve`, `make build` and `make test` flows.
- Decide whether future images should preinstall the `unaltraweb` gem or keep the current split where the image owns runtime dependencies and the child `Gemfile` owns theme/plugin code.
- The versioned component BOM now selects release images and exact companion releases; mutable `main`/`latest` channels are documented as maintainer-only. Ensure every GHCR package is public after its first approved publish.
- Keep a developer path for local core work: `LOCAL_CORE=../unaltraweb` and possibly a Git-based gem dependency remain useful for testing, but should not be the normal user setup.
- Decide how `diavisuals` is distributed for users. Preferred direction: `unaltraweb diagrams` works without cloning `diavisuals`, either by packaging the style/render tooling into the core image or by invoking a versioned render image.
- Add update commands with clear semantics: `make update-core` or `unaltraweb update` pulls the Docker image/tag and runs `doctor`; optional git-upstream updates should be limited to starter/template migrations, not core code.
- Distribution doctor now validates release/factory/project pins and feature selection offline. Extend it later with explicit copied-core-asset detection and generated-asset synchronization checks rather than conflating those with distribution health.
- Revisit documentation pages for creating a new site after the keep/sync commands exist. Current docs already cover: choose profile, edit content/config, and serve/build through Docker.

- Next-session focus for `unaltremanual`: make the manual content usable as a student-facing downloadable/printable PDF, likely through LaTeX/Pandoc. Treat PDF output as a first-class target, and mark web-only enhancements so they degrade cleanly or are omitted in PDF builds.
- Next-session focus for richer teaching sites: support per-topic slides and downloadable resources, probably surfaced as compact top-left toolbar icons; add configurable hero images for main navigation pages, excluding collection/content pages; confirm or add a stable public downloads folder; explore GeoJSON syntactic sugar for loading a file from a folder and rendering it with styles; define how executable R/Python content coexists with static builds; confirm math notation support for formulas.
- Resolve the Quarto/manual-computation adoption issue documented in `docs/agents/quarto-computation-adoption.md`: child repos need an obvious `manual-compute-*` path, project-specific compute Dockerfiles should be the normal place for non-general dependencies, and figure-only Quarto sources may need an explicit contract rather than being forced into chapter-shaped generated Markdown.
- Enable GitHub Pages in repository settings with GitHub Actions as the source, so `.github/workflows/deploy.yml` can publish `docs/`.
- Continue replacing remaining `al-folio` labels, comments, demo data and Docker image assumptions with `unaltraweb` identity.
- Regenerate `package-lock.json` with `npm install` on a machine with Node/npm available; do not hand-edit dependency integrity data.
- If Node/npm work becomes routine, add a separate lightweight Node tooling path instead of putting npm into every Jekyll runtime image.
- Add clearer docs for `site_profile: unaltreselfie`, `site_profile: unaltreprojecte`, `site_profile: unaltredocs` and `site_profile: unaltremanual`.
- Continue turning `docs/feature-reference.md`, `docs/syntax.md` and `docs/customization.md` into a complete rendered reference for every reusable feature and syntax rule.
- Rework general site search as a generated core feature before enabling it by default again.
- Continue refining config-driven behaviour for the four named site profiles.
- Continue validating GitBook/docs behaviour with a freshly generated `tig` acceptance manual: sidebar collections, previous/next navigation, search and course/slides affordances.
- Address broader Sass deprecation warnings eventually; they are non-blocking.

## Verification Commands

Core repo:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

Template repo:

```bash
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreselfie PORT=4018
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte PORT=4019
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual PORT=4020
make down
```

Resource note: full core Docker builds and template Playwright tests can be heavy. On constrained machines, run a targeted template profile or a build-only check first.

Manual publication metrics workflow:

```yaml
jobs:
  metrics:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/metrics-update.yml@main
    with:
      fetch_scimago: true
      create_pull_request: true
```

## Operating Notes For Agents

- Build context first. This codebase still contains inherited `al-folio` pieces and project-specific content; do not assume every file is already generalized.
- Prefer changes in core only when they are reusable. Put site-specific demo content in `../unaltraweb-template`.
- Do not revert unrelated dirty work in either repo.
- Do not commit unless the user explicitly asks.
- If asked to commit this repo, verify `origin` still points to `dosquartsdedocs/unaltraweb` before pushing.
