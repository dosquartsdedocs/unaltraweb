---
title: Develop The Core
description: Safe development and verification workflow for unaltraweb.
lang: en
ref: development_workflow
profiles:
- unaltredocs
documentation_profiles:
- contributors
- core-developers
section: Core Development
weight: 610
permalink: "/development/"
nav_title: Core Development
---
<p class="lede">Validate core changes in layers. Use lightweight checks while editing, then run heavier Docker or Playwright checks only when the machine can handle them.</p>

## Lightweight Checks

```bash
git status --short --branch
git diff --check
```

Use these for documentation-only changes or before deciding whether a heavier build is worth running.

## Docs Deploy

The core repository can publish the `unaltraweb` reference site from `docs/` with the manual `.github/workflows/deploy.yml` workflow and GitHub Pages Actions. This workflow does not need Node/npm and does not build the full inherited core demo site.

The reference site is a real child site of the local `unaltraweb` gem. It uses `theme: unaltraweb`, the shared layouts/includes/Sass, and `unaltraweb.site_profile: unaltredocs`.

```bash
make docs-serve DOCKER_IMAGE=unaltraweb:dev
make docs-build DOCKER_IMAGE=unaltraweb:dev
make docs-publish DOCKER_IMAGE=unaltraweb:dev
```

After the selected versioned Docker image is available, omit `DOCKER_IMAGE=unaltraweb:dev`.

Docs deploys, link checks, publication metrics and all publication workflows remain manual. CodeQL and the repository CI workflow run automatically; neither deploys or publishes anything.

## Automatic CI

`.github/workflows/ci.yml` runs on pull requests and pushes. Its bounded jobs cover Python 3.10/3.13 compile and unit checks, `git diff --check`, workflow policy, structural `distribution-check`, clean wheel and gem checks, and cached Docker builds followed by MCP smoke and docs builds. CodeQL analyzes JavaScript/TypeScript, Python and Ruby for pull requests, default-branch pushes and its weekly schedule.

Automatic CI deliberately uses the structural gate. It verifies that pending companion releases are represented truthfully but does not require them to be published, so normal feature work can remain green before a coordinated release.

`make distribution-release-check` is stricter: it exits nonzero while any selected component is `pending` or `unavailable`. Core artifact workflows use the structural gate while publishing the pending candidates, plus exact ref/version validation and relevant tests before any registry login or image push is reachable. After every immutable artifact exists, update its contract status to `released` and run the strict gate before creating the coordinated release. Starting a manual workflow is still an explicit approval; package preparation only uploads commit-SHA-named workflow artifacts and does not publish to RubyGems/PyPI or create a GitHub release.

## Core Build

The local port convention for working with both repositories is:

- `unaltraweb` core/docs: `http://localhost:4000/unaltraweb/`.
- `unaltreselfie`: `http://localhost:4001/unaltraweb-template/en/`.
- `unaltreprojecte`: `http://localhost:4002/unaltraweb-template/en/`.
- `unaltremanual`: `http://localhost:4003/unaltraweb-template/en/`.
- `unaltredocs`: `http://localhost:4004/unaltraweb-template/en/`.

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

This can be resource-heavy because the inherited demo build minifies JavaScript and can generate many responsive WebP images.

The same Dockerfile is published manually. Consumers select `ghcr.io/dosquartsdedocs/unaltraweb:0.3.0`; the mutable `ghcr.io/dosquartsdedocs/unaltraweb:main` channel and local `unaltraweb:dev` name are explicit maintainer paths. The `unaltraweb` gem remains the source of theme files and plugins.

The root core build excludes `docs/`. The reference site is published from the `docs/` folder through a dedicated workflow so its root-relative permalinks do not collide with the inherited core demo build.

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
