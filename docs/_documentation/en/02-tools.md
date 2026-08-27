---
title: Tools For Local Work
description: What users and maintainers need to work with unaltraweb.
lang: en
ref: tools_requirements
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- contributors
- core-developers
section: Work Locally
weight: 110
permalink: "/tools/"
nav_title: Local Tools
---
<p class="lede">Most site authors can choose between the preferred local Docker workflow and a GitHub-only workflow for contributors who cannot work locally. The local path is intentionally small: Git, Docker and Make.</p>

## User Paths

| Path | Required tools | Best for |
|---|---|---|
| Local Docker | Git, Docker, GNU Make | Previewing, larger edits, screenshots, tests, and rendered-output review |
| GitHub-only | Browser, GitHub account, repository created from the template | Small content edits, bibliography entries, page text, YAML data and configuration changes, followed by a manual deploy workflow |
| Windows local | WSL2, Docker Desktop with WSL integration, Git and Make inside WSL | The supported Windows equivalent of the local Docker path |
| Core maintenance | Docker, Git, GitHub Actions, GHCR access; Ruby/Bundler optional for direct debugging | Changing layouts, plugins, Sass, scripts, workflows and the shared runtime image |

## Local Runtime

The template uses the shared runtime image by default:

```bash
ghcr.io/dosquartsdedocs/unaltraweb:0.3.0
```

That image provides Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling needed by local commands. The GHCR package must be public before unauthenticated users can pull it.

## Generated Site Commands

Clean sites created by `new_web` expose the Dockerized core workflow:

```bash
make serve
make build
make test
make down
```

Inspect the selected component contract and local project pins without network access:

```bash
unaltraweb-mcp doctor --project .
unaltraweb-mcp doctor --project . --docker  # local image inspection only; never pulls
unaltraweb-mcp --project . mcp site-doctor
unaltraweb-mcp --project . mcp scaffold-sync
unaltraweb-mcp --project . mcp html-audit
```

The generated `make test` builds and runs the offline HTML audit. `build_site` returns the same audit after a successful build. External URLs are inventoried but never fetched.

## Integration Template Commands

Run these from a child site created from `unaltraweb-template`:

```bash
make serve
make build
make publish
make test
make screenshots
make web-capture-status
make web-capture-render WEB_CAPTURE_SOURCE=assets/captures/chapter.capture.yml
make web-capture-check
make visualization-status
make visualization-render
make visualization-check
make metrics-update
make cv-preview CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
make down
```

## Core Documentation Commands

Run these from the `unaltraweb` repository when working on this reference site:

```bash
make docs-serve DOCKER_IMAGE=unaltraweb:dev
make docs-build DOCKER_IMAGE=unaltraweb:dev
make docs-publish DOCKER_IMAGE=unaltraweb:dev
make docs-down
```

After the GHCR image is public, `DOCKER_IMAGE` can be omitted.

Useful profile commands:

```bash
make serve SITE_PROFILE=unaltremanual
make serve-unaltreselfie
make serve-unaltreprojecte
make serve-unaltremanual
make serve-unaltredocs
make serve-allprofiles
```

## Ports

When the core docs and all template profiles are running together, use this convention:

- `4000`: `unaltraweb` documentation.
- `4001`: `unaltreselfie`.
- `4002`: `unaltreprojecte`.
- `4003`: `unaltremanual`.
- `4004`: `unaltredocs`.

## Optional Tools

- Node/npm are only needed for formatting and frontend development tasks in the core repository.
- Playwright is pulled through its Docker image by the template tests; users do not need to install browsers manually.
- Python dependencies are installed inside the local workflow for metrics and bibliography tooling.
- Diagram rendering is delegated to the shared `diavisuals` MCP/CLI renderer. Jekyll rewrites diagram text sources to SVG and keeps `*.edited.svg` files as author-owned overrides.
- Static Vega-Lite and Vega rendering is delegated to the shared `vegavisuals` MCP/CLI factory. Set `VEGAVISUALS_PATH` to a sibling checkout or `VEGAVISUALS_CLI` to an installed executable when a project contains `.vegavisuals.yml`; projects without a manifest skip these commands.

## Publishing Checklist

- Generated-site route: enable GitHub Pages with GitHub Actions as the source and run the manual deploy workflow when needed.
- Keep deploy workflows as thin `workflow_dispatch` wrappers pinned to a reviewed full commit SHA of `dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml`.
- The optional integration template may retain its local `gh-pages` publishing target for testing that separate workflow.
- After the first Docker publish, make `ghcr.io/dosquartsdedocs/unaltraweb` public.
- Confirm `docker pull ghcr.io/dosquartsdedocs/unaltraweb:0.3.0` works without `docker login`.
