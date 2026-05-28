# TODO

## Purpose

`unaltraweb` is the reusable Jekyll core/platform for `dosquartsdedocs` websites. It provides shared layouts, includes, styles, plugins, bibliography tooling, multilingual behaviour, theme modes, documentation and reusable workflows for thin child repositories such as `../unaltraweb-template`.

Use the term **site profile** for prepared website families such as `personal`, `project`, `software`, `manual` and `course`. Avoid calling these layouts or includes, because those words already have precise Jekyll meanings.

The goal is not to maintain one personal site here. The goal is to make a self-owned alternative to the inherited `al-folio` base, supporting academic personal sites, research project sites and documentation/course sites.

## Current Shape

- Core repo: `/home/benizar/git/unaltraweb`.
- Template repo: `/home/benizar/git/unaltraweb-template`.
- Legacy personal-site reference: `/home/benizar/git/benizar.github.io`.
- Legacy GitBook/course reference: `/home/benizar/git/tig`.
- Remote for this repo: `git@github.com:dosquartsdedocs/unaltraweb.git`.
- Baseline before the current documentation cleanup: `842e9ee Improve multilingual blog and footer defaults`.
- Baseline companion template commit: `1877e52 Localize personal blog demo content`.

## Repository Split

- `unaltraweb` owns reusable code: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows and core documentation.
- `unaltraweb-template` owns the thin starter scaffold: `_config.yml`, editable demo content, local overrides, local workflow glue and Playwright smoke tests.
- The template is the preferred place to prove gem consumption and centralized style/logic behaviour because it exercises `unaltraweb` as an external dependency.
- `docs/` in this repo contains the compact public core documentation/demo site. It should explain the platform rather than duplicate the template's full starter demo.

## Design Decisions

- Keep Jekyll builds static. Do not call OpenAlex, Crossref, Scimago, Google Scholar, Medium or other external services during `jekyll build`.
- Metrics update scripts may fetch data manually, locally or through an explicit workflow, but normal builds must use local files only.
- Keep reusable functionality in `unaltraweb`; keep `unaltraweb-template` thin.
- Use Docker-first commands for child sites so users can run `make serve`, `make build`, `make test` and `make down` without remembering Docker details.
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
- Added `site.unaltraweb.site_profile` DOM markers: `data-site-profile` on `<html>` and `site-profile-*` on `<body>`. `data-site-type`/`site-type-*` remain as temporary compatibility aliases.
- Added config-driven feature navigation through `site.unaltraweb.features`.
- Added theme mode rotation: `system -> light -> sepia -> dark -> system`.
- Added `data-theme-setting`, `data-theme`, `data-theme-integration` and `unaltraweb:themechange` for tests and local scripts.
- Added `_sass/_site-custom.scss` as a local child-site style extension point and documented it in `docs/customization.md`.
- Added reusable personal-site blog archives, direct-link project cards, project resource badges and CV PDF download/preview card components.
- Added real profile filtering for pages/documents through `profiles: [...]` and `site.unaltraweb.site_profile`.
- Added manual profile support: manual home/chapter layouts, sticky sidebar, right rail TOC, localized chapter routing, teacher blocks, figure/table numbering, manual bibliography mode, manual search index and reader font controls.
- Added reusable deploy workflow at `.github/workflows/site-deploy.yml`.
- Replaced inherited top-level user docs with short `unaltraweb`-specific `README.md`, `INSTALL.md`, `CUSTOMIZE.md`, `FAQ.md` and `CONTRIBUTING.md`.
- Added a compact docs/demo site under `docs/` with overview, profiles, template role and development pages.
- Replaced the core repo deploy workflow with a lightweight GitHub Pages Actions workflow that builds `docs/` only.
- Replaced the post-deploy link checker with a docs-only offline link check.
- Added a manual/reusable publication metrics workflow at `.github/workflows/metrics-update.yml`.
- Kept publication metrics PRs focused on versionable generated data: `_bibliography/**/*.bib` and `_data/metrics.yml`. Scimago caches and diagnostics remain unversioned.
- Changed CodeQL to manual-only so automatic CI stays focused on web/docs.
- Fixed `scripts/biblio/fetch_scimago_csv.sh` so it validates Scimago data through its own script directory when called from child repositories.
- Added clearer metrics failure reporting for missing Scimago data and OpenAlex/Crossref request errors.
- Exposed local `METRICS_ARGS` and `SCIMAGO_INPUT` Makefile controls in both core and template repos.

## Companion Template State

`../unaltraweb-template` is currently clean and aligned with `origin/main`. It is the integration fixture for this core.

Important current template behaviour:

- Personal demo profile uses fictional John Doe/Juan Nadie/Joan Ningu placeholder content.
- Localized home pages `/en/`, `/es/`, `/ca/` use `layout: profile`.
- Optional localized `blog`, `CV`, `projects`, `publications`, `outputs`, `repositories`, `readings`, `team` and manual pages exercise feature/profile routing.
- Demo project entries live in `_projects/`.
- Demo blog entries live in `_posts/`.
- Demo manual chapters live in `_chapters/` for English, Spanish and Catalan.
- Blog pagination is enabled in the template demo.
- Demo CV PDF and generated first-page preview live in `assets/pdf/cv.pdf` and `assets/img/cv-preview.jpg`.
- The template Makefile supports `LOCAL_CORE=../unaltraweb` and `SITE_PROFILE=personal|project|manual`.
- Playwright render smoke tests verify personal, project and manual profiles, desktop/mobile rendering, theme modes and screenshots.
- The template deploy workflow calls `.github/workflows/site-deploy.yml` from this core.
- The template manual `Update publication metrics` workflow calls `.github/workflows/metrics-update.yml` from this core.

## Next Work

- Enable GitHub Pages in repository settings with GitHub Actions as the source, so `.github/workflows/deploy.yml` can publish `docs/`.
- Continue replacing remaining `al-folio` labels, comments, demo data and Docker image assumptions with `unaltraweb` identity.
- Regenerate `package-lock.json` with `npm install` on a machine with Node/npm available; do not hand-edit dependency integrity data.
- If Node/npm work becomes routine, add a separate lightweight Node tooling path instead of putting npm into every Jekyll runtime image.
- Add clearer docs for `site_profile: personal`, `site_profile: project`, `site_profile: software`, `site_profile: manual` and future `course` mode.
- Rework general site search as a generated core feature before enabling it by default again.
- Continue refining config-driven behaviour for personal, project, software and manual/course sites.
- Later, integrate GitBook/docs mode using `/home/benizar/git/tig` as reference: sidebar collections, previous/next navigation, search and course/slides affordances.
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
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=personal PORT=4018
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=project PORT=4019
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=manual PORT=4020
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
