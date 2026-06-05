---
title: Tools And Requirements
description: What users and maintainers need to work with unaltraweb.
lang: en
ref: tools_requirements
profiles: [unaltredocs]
section: User guides
weight: 20
permalink: /tools/
---

<p class="lede">Most site authors can choose between GitHub-only editing and a local Docker workflow. The local path is intentionally small: Git, Docker and Make.</p>

## User Paths

| Path | Required tools | Best for |
|---|---|---|
| GitHub-only | Browser, GitHub account, repository created from the template | Small content edits, bibliography entries, page text, YAML data and configuration changes |
| Local Docker | Git, Docker, GNU Make | Previewing, larger edits, screenshots, tests and profile comparison |
| Windows local | WSL2, Docker Desktop with WSL integration, Git and Make inside WSL | The supported Windows equivalent of the local Docker path |
| Core maintenance | Docker, Git, GitHub Actions, GHCR access; Ruby/Bundler optional for direct debugging | Changing layouts, plugins, Sass, scripts, workflows and the shared runtime image |

## Local Runtime

The template uses the shared runtime image by default:

```bash
ghcr.io/dosquartsdedocs/unaltraweb:main
```

That image provides Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling needed by local commands. The GHCR package must be public before unauthenticated users can pull it.

## Template Commands

Run these from a child site created from `unaltraweb-template`:

```bash
make serve
make build
make test
make screenshots
make metrics-update
make cv-preview CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
make down
```

## Core Documentation Commands

Run these from the `unaltraweb` repository when working on this reference site:

```bash
make docs-serve DOCKER_IMAGE=unaltraweb:local
make docs-build DOCKER_IMAGE=unaltraweb:local
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
- Diagram rendering currently depends on the configured `diavisuals` path or render image; this is still being simplified.

## Publishing Checklist

- Enable GitHub Pages with GitHub Actions as the source.
- Let the template deploy workflow call `dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@main`.
- After the first Docker publish, make `ghcr.io/dosquartsdedocs/unaltraweb` public.
- Confirm `docker pull ghcr.io/dosquartsdedocs/unaltraweb:main` works without `docker login`.
