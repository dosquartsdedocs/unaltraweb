---
title: Development
description: Safe development and verification workflow for unaltraweb.
permalink: /development/
---

# Development

<p class="lede">Validate core changes in layers. Use lightweight checks while editing, then run heavier Docker or Playwright checks only when the machine can handle them.</p>

## Lightweight Checks

```bash
git status --short --branch
git diff --check
```

Use these for documentation-only changes or before deciding whether a heavier build is worth running.

## Docs Deploy

The core repository publishes the compact docs/demo site from `docs/` with `.github/workflows/deploy.yml` and GitHub Pages Actions. This workflow does not need Node/npm and does not build the full core demo site.

Automatic CI is intentionally scoped to docs/web publication and local link checking. CodeQL remains available as a manual workflow.

## Core Build

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

This can be resource-heavy because the inherited demo build minifies JavaScript and can generate many responsive WebP images.

The root core build excludes `docs/`. The compact docs/demo site is intended to be published from the `docs/` folder or by a dedicated workflow so its root-relative permalinks do not collide with the core demo build.

## Template Consumer Checks

```bash
cd ../unaltraweb-template
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreselfie PORT=4018
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte PORT=4019
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual PORT=4020
make down
```

Run the smallest relevant profile when resources are limited.

## Static Builds

Normal Jekyll builds must not fetch external services. Metrics updates are explicit pre-build tasks that write local data files.

```bash
make metrics-scimago-fetch
make metrics-update
make metrics-check
```

Local metrics commands accept the same safety checks used in CI:

```bash
make metrics-update METRICS_ARGS="--strict-external --require-scimago"
make metrics-scimago-fetch SCIMAGO_INPUT=path/to/scimagojr.csv
```

Publication metrics can also run through the manual/reusable `.github/workflows/metrics-update.yml` workflow. By default it uploads diagnostics and does not open a pull request. Set `create_pull_request: true` when you want GitHub to propose generated metrics changes. Generated Scimago caches and diagnostics stay out of PRs; `_bibliography/**/*.bib` and `_data/metrics.yml` are the versionable outputs.

## Formatting Lockfile

`package.json` declares Prettier and the Liquid plugin. Regenerate `package-lock.json` with `npm install` on a machine with Node/npm available. Do not hand-edit dependency integrity data.

`npm` is development tooling rather than Jekyll runtime. If containerized npm commands become necessary, use a small dedicated Node tooling image or a GitHub Action instead of adding npm to every Jekyll build path.
