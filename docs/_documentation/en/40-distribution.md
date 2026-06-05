---
title: Distribution Model
description: Core/template split and update model for unaltraweb.
lang: en
ref: distribution_model
profiles: [unaltredocs]
section: Operations
weight: 400
permalink: /distribution/
---

`unaltraweb` is the source of truth for reusable code. Template repositories should stay thin and contain only site-specific content, local overrides and small integration files.

## Repository Roles

- `unaltraweb`: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows, documentation, small internal examples and the shared Docker runtime image.
- `unaltraweb-template`: `_config.yml`, editable content, local overrides, demo assets, local Docker workflow, Dependabot config, workflow wrapper and Playwright smoke tests.
- `docs/` in `unaltraweb`: public reference site for the platform itself.

The template is the better place to validate gem consumption, centralized styles and shared logic because it runs as a child site. The core docs site should explain and showcase the platform, not replace the starter template.

## User Paths

### GitHub-only editing

Users can create a site from `dosquartsdedocs/unaltraweb-template`, edit content in the GitHub web UI and let GitHub Actions build and publish the site.

This path is intended for small content edits, bibliography updates, course/manual chapter edits and configuration changes. It does not require Docker, Make or a local development environment.

### Local editing

Users who need larger edits can clone their generated site repository and use the local Docker workflow from the template:

```bash
make serve
make build
make test
```

Local editing requires Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run the same commands inside the WSL Linux shell.

Theme development can happen side by side by pointing the template at a local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte
```

## Demo Strategy

- Template demo: realistic starter content for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`, used to validate the gem consumer path.
- Core docs: the `unaltraweb` reference site, focused on concepts, profile capabilities, syntax, customization points, tools and links to the template.
- Avoid duplicating full demo content between the two repositories.

## Core Docs Publishing

The core repository deploy workflow builds only `docs/` and publishes it with GitHub Pages Actions. The root core Jekyll build excludes `docs/`, so the reference site can use its own root-relative permalinks without colliding with the internal core demo build.

Automatic CI is limited to docs/web publication and a local docs link check. Publication metrics run manually from GitHub or locally, and CodeQL is available as a manual workflow.

## Updates

Repositories created from a GitHub template are not linked to the template as forks, so template changes are not automatically proposed to users.

For that reason:

- normal improvements should ship through the `unaltraweb` gem or reusable workflows;
- site repositories should enable Dependabot for Bundler and GitHub Actions;
- breaking changes should be released with migration notes;
- scaffold changes should be rare and, when needed, delivered as explicit pull requests or a future `unaltraweb sync` command.

## Docker Runtime

The shared runtime image is published from the core repository as `ghcr.io/dosquartsdedocs/unaltraweb:main` and `ghcr.io/dosquartsdedocs/unaltraweb:latest` on pushes to `main`, plus tag and SHA variants. It carries Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling needed by local builds. The GHCR package must be public before unauthenticated template users can pull it.

The image is not the source of layouts or styles. Child sites still get those from the `unaltraweb` gem declared in their `Gemfile`. This keeps updates centralized in two places:

- gem updates change reusable site behaviour, layouts, Sass, plugins and scripts;
- Docker image updates change the local build/runtime environment.

Before recommending the local Docker workflow to unauthenticated users, complete this first-publish checklist:

- Push the core workflow to `main` and let `.github/workflows/docker-image.yml` publish the image.
- Open the `ghcr.io/dosquartsdedocs/unaltraweb` package settings in GitHub.
- Make the package public.
- Confirm that `docker pull ghcr.io/dosquartsdedocs/unaltraweb:main` works without `docker login`.

## Verification

Core changes should be validated in two layers:

- Build the core repository to catch internal Jekyll errors.
- Build or test `../unaltraweb-template` with `LOCAL_CORE=../unaltraweb` to catch consumer-path regressions.

Template Playwright tests and screenshot generation are intentionally heavier than a Jekyll build. Run targeted profiles when machine resources are limited.
