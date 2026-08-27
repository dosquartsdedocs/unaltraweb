---
title: Understand The Distribution Model
description: Core/template split and update model for unaltraweb.
lang: en
ref: distribution_model
profiles:
- unaltredocs
documentation_profiles:
- core-developers
section: Core Development
weight: 620
permalink: "/distribution/"
nav_title: Distribution Model
---
`unaltraweb` is the source of truth for reusable code. Template repositories should stay thin and contain only site-specific content, local overrides and small integration files.

## Repository Roles

- `unaltraweb`: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows, documentation, small internal examples and the shared Docker runtime image.
- `unaltraweb_mcp` package scaffolds: clean profile-specific config, localized home pages, content roots, and native build/serve files used by new sites.
- `unaltraweb-template`: multi-profile demo assets, local Docker workflow, Dependabot config, workflow wrapper and Playwright integration tests.
- `docs/` in `unaltraweb`: public reference site for the platform itself.

The template is the better place to validate gem consumption, centralized styles and shared logic because it runs as a child site. It is not required to create a site: package scaffolds are the supported clean starting point.

## User Paths

### GitHub-only editing

Users can push a site created by `new_web`, edit content in the GitHub web UI, and run its configured deploy workflow when the site should be published. Forking `dosquartsdedocs/unaltraweb-template` remains an optional path for users who want its full demo and workflow wrapper.

This path is intended for small content edits, bibliography updates, course/manual chapter edits and configuration changes. It does not require Docker, Make or a local development environment.

### Local editing

Users who need larger edits can clone their generated site repository and use its package-scaffolded Docker workflow:

```bash
make serve
make build
make test
make down
```

Local editing requires Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run the same commands inside the WSL Linux shell.

Theme development can happen side by side by pointing the template at a local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte
```

## Demo Strategy

- Template demo: realistic content for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`, used to validate the gem consumer path.
- Core docs: the `unaltraweb` reference site, focused on concepts, profile capabilities, syntax, customization points, tools and links to the template.
- Avoid duplicating full demo content between the two repositories.

## Core Docs Publishing

The core repository deploy workflow is manual. It builds only `docs/` and publishes it with GitHub Pages Actions. The root core Jekyll build excludes `docs/`, so the reference site can use its own root-relative permalinks without colliding with the internal core demo build.

Deploys, link checks, Docker image publishing, publication metrics and CodeQL run manually from GitHub or locally.

## Updates

Repositories created from a GitHub template are not linked to the template as forks, so template changes are not automatically proposed to users.

For that reason:

- normal improvements should ship through the `unaltraweb` gem or reusable workflows;
- site repositories can enable Dependabot for Bundler and GitHub Actions, but deploy workflows should remain manual;
- breaking changes should be released with migration notes;
- scaffold changes should be rare and, when needed, delivered as explicit pull requests or a future `unaltraweb sync` command.

## Docker Runtime

The shared runtime image is published from the core repository as `ghcr.io/dosquartsdedocs/unaltraweb:main` and `ghcr.io/dosquartsdedocs/unaltraweb:latest` by the manual Docker image workflow. Release tags are available when the workflow is run from a `v*` tag. The workflow avoids default SHA image tags and uses GitHub Actions caches for repeat builds. The image carries Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling needed by local builds. The GHCR package must be public before unauthenticated template users can pull it.

The image is not the source of layouts or styles. Child sites still get those from the `unaltraweb` gem declared in their `Gemfile`. This keeps updates centralized in two places:

- gem updates change reusable site behaviour, layouts, Sass, plugins and scripts;
- Docker image updates change the local build/runtime environment.

Before recommending the local Docker workflow to unauthenticated users, complete this first-publish checklist:

- Create the release tag, then run the manual `.github/workflows/docker-image.yml` workflow from `v0.3.0` to publish both versioned images.
- Open the `ghcr.io/dosquartsdedocs/unaltraweb` package settings in GitHub.
- Make the package public.
- Confirm that `docker pull ghcr.io/dosquartsdedocs/unaltraweb:main` works without `docker login`.
- Make the `ghcr.io/dosquartsdedocs/unaltraweb-mcp` package public after its first publication.
- Confirm that `docker pull ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` works without `docker login`.

## Verification

Core changes should be validated in two layers:

- Build the core repository to catch internal Jekyll errors.
- Build or test `../unaltraweb-template` with `LOCAL_CORE=../unaltraweb` to catch consumer-path regressions.

Template Playwright tests and screenshot generation are intentionally heavier than a Jekyll build. Run targeted profiles when machine resources are limited.
