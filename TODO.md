# TODO

## Purpose

`unaltraweb` is the reusable Jekyll core/platform for `dosquartsdedocs` websites. It should provide layouts, includes, styles, plugins, bibliography tooling, multilingual behavior, theme modes, and documentation that can be consumed by thin child repositories such as `../unaltraweb-template`.

Use the term **site profile** for prepared website families such as `personal`, `project`, `software`, `manual`, and `course`. Avoid calling these layouts or includes, because those words already have precise Jekyll meanings.

The goal is not to maintain one personal site here. The goal is to make this repo a self-owned alternative to the inherited al-folio base, supporting academic personal sites, research project sites, and later GitBook-style documentation/course sites.

## Current Shape

- Core repo: `/home/benizar/git/unaltraweb`.
- Template repo: `/home/benizar/git/unaltraweb-template`.
- Legacy personal-site reference: `/home/benizar/git/benizar.github.io`.
- Legacy GitBook/course reference: `/home/benizar/git/tig`.
- Remote for this repo: `git@github.com:dosquartsdedocs/unaltraweb.git`.
- Latest pushed core commit: `cbbd12e Add personal profile and theme customization support`.

## Design Decisions

- Keep Jekyll builds static. Do not call OpenAlex, Crossref, Scimago, Google Scholar, Medium, or other external services during `jekyll build`.
- Metrics update scripts may fetch data manually, locally, or through an explicit manual workflow, but normal builds must use local files only.
- Keep reusable functionality in `unaltraweb`; keep `unaltraweb-template` thin.
- Use Docker-first commands for child sites so users can run `make serve`, `make build`, `make test`, and `make down` without remembering Docker details.
- Do not add backward-compatibility branches unless there is a concrete persisted-data, shipped-behavior, or external-consumer need.
- Preserve small, minimal changes where possible. Avoid building broad abstractions before there is a clear second consumer.
- Move away from al-folio identity and demo defaults over time, while keeping useful inherited code until it is replaced.

## Implemented Recently

- Packaged `unaltraweb` as a reusable Jekyll theme/plugin gem.
- Exposed core `_config.yml` and `requirements.txt` in the gem.
- Made core stylesheet/cache-busting behavior safe when used as a theme gem.
- Added static bibliometrics tooling and docs under `scripts/biblio/` and `docs/bibliometrics.md`.
- Disabled inherited `external_sources` by default so builds do not fetch Medium/Google posts.
- Added `profile` layout and `profile-card` include for personal-site home pages.
- Refined the personal profile layout toward a Minimal Mistakes-style sidebar: circular avatar, vertical contact links, no duplicate page title when the page title matches the author name.
- Added profile i18n keys in English, Spanish, and Catalan.
- Added `site.unaltraweb.site_profile` DOM markers: `data-site-profile` on `<html>` and `site-profile-*` on `<body>`. `data-site-type`/`site-type-*` are still emitted as compatibility aliases for now.
- Added config-driven feature navigation: pages can declare `feature: blog`, `feature: cv`, `feature: projects`, `feature: publications`, etc.; if `site.unaltraweb.features.<feature>` is `false`, the page is hidden from navigation.
- Added theme mode rotation: `system -> light -> sepia -> dark -> system`.
- Added `data-theme-setting`, `data-theme`, `data-theme-integration`, and `unaltraweb:themechange` for tests and local scripts.
- Added `_sass/_site-custom.scss` as a local child-site style extension point and documented it in `docs/customization.md`.
- Added named Docker Compose project/container for this repo.
- Added a persistent Docker Compose Bundler volume so separate core `bundle install` and `bundle exec jekyll build` containers share installed gems.
- Added reusable personal-site blog archives, direct-link project cards, and CV PDF download/preview card components.
- Added optional blog pagination support in `blog-list.liquid` through `paginator.posts`.
- Project cards now use a project `hero` image as a very light degraded card background.
- Project resources now render as icon badges on cards and in `layout: project` pages. The current demo uses Zenodo, DOI, dataset, code, documentation, map, report, and website resource types.
- Abandoned the multi-profile fake preview approach. It caused regressions because it tried to simulate alternate Jekyll sites after Liquid had already rendered one real configuration. Developer mode is now only a small indicator of the active real build profile.
- Added a profile page filter plugin: pages/documents with `profiles: [...]` are kept only when they match `site.unaltraweb.site_profile`. This makes `SITE_PROFILE=project` a real single-profile build instead of a personal site with hidden project mockups.
- Added `profile-highlights.liquid` for richer personal home pages with selected publications, active projects, and recent posts.
- Added `scripts/cv/render_pdf_preview.sh` for first-page PDF preview generation. It prefers `pdftoppm`, then `mutool`, then ImageMagick with Ghostscript.

## Companion Template State

`../unaltraweb-template` is the thin scaffold used to prove the core works as a dependency. It currently has local uncommitted work that should be reviewed, tested, committed, and pushed separately when ready.

Important template changes currently expected:

- Personal demo profile uses Roger Tomlinson as placeholder content.
- Localized home pages `/en/`, `/es/`, `/ca/` use `layout: profile`.
- Default localized `about` pages were removed from the personal-mode scaffold.
- Optional localized `blog`, `CV`, and `projects` pages were added to exercise feature toggles.
- Demo project entries live in `_projects/`.
- Demo blog entries live in `_posts/`.
- Blog pagination is enabled in the template demo with four posts per page so `/en/blog/page/2/` and equivalent localized pages are generated.
- The Canada GIS demo project has a project image under `assets/img/projects/canada-gis.svg` to demonstrate the softened card background.
- Demo CV PDF and generated first-page preview live in `assets/pdf/cv.pdf` and `assets/img/cv-preview.jpg`.
- Personal profile avatars now fall back to the core `assets/img/profile-placeholder.svg`, a neutral grey/white silhouette placeholder. Child sites can override this with `author.avatar`.
- Template Docker workflow now uses persistent `tmp/` caches for Bundler and pip so repeated `make serve`/`make build` runs do not reinstall everything. A custom prebuilt Docker image can still be added later if startup time remains too high.
- Template `make cv-preview` installs `poppler-utils` inside the temporary Docker container when no PDF renderer is available, then writes the generated preview back as the host user.
- Default pagination and search are disabled in the core config to avoid warning noise and missing generated search assets in child sites. Re-enable them only when the relevant generated pages/assets are configured.
- Template `Makefile` defaults to `/en/`, keeps Docker-first targets, and supports `SITE_PROFILE=project` for real project builds/tests.
- Playwright render smoke tests verify the personal profile by default and the project profile with `SITE_PROFILE=project`; the project test hits real Jekyll pages for home, team, outputs, publications and resources.
- Template config uses `unaltraweb.features.blog: true`, `cv: true`, `projects: true`, `publications: true`, and `metrics: true`.
- Template config sets `external_sources: []` to keep builds static.

## Next Work

- In `../unaltraweb-template`, review all local changes, then commit and push the template scaffold update when requested.
- Review all local core changes, then commit and push the core update when requested.
- Consider simplifying template `Makefile` further by hiding or removing old alias targets if they are no longer useful.
- Add clearer docs for `site_profile: personal`, `site_profile: project`, `site_profile: software`, and future manual/course mode.
- Continue refining config-driven behavior for personal sites: profile home, optional blog, CV, projects, publications, social links, and navigation defaults.
- Define config-driven behavior for project sites: project home, outputs, publications, team, resources, and news.
- Rework search as a generated core feature before enabling it by default again. It currently stays disabled by default to avoid missing `assets/js/search-data.js` requests from child sites.
- Later, integrate GitBook/docs mode using `/home/benizar/git/tig` as reference: sidebar collections, previous/next navigation, search, course/slides affordances.
- Continue replacing al-folio labels, comments, demo data, and Docker image assumptions with `unaltraweb` identity.
- Address broader Sass deprecation warnings eventually, but they are non-blocking.

## Verification Commands

Core repo:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

To prove the core Bundler cache is persisted across containers:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc 'bundle install'" jekyll
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc 'bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

Template repo:

```bash
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb PORT=4019
make build LOCAL_CORE=../unaltraweb SITE_PROFILE=project
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=project PORT=4020
make cv-preview LOCAL_CORE=../unaltraweb CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
make down
```

## Operating Notes For Agents

- Build context first. This codebase still contains inherited al-folio pieces and project-specific content; do not assume every file is already generalized.
- Prefer changes in core only when they are reusable. Put site-specific demo content in `../unaltraweb-template`.
- Do not revert unrelated dirty work in either repo.
- Do not commit unless the user explicitly asks.
- If asked to commit this repo, verify `origin` still points to `dosquartsdedocs/unaltraweb` before pushing.
