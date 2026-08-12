---
title: Use Reusable GitHub Workflows
description: GitHub Actions workflows provided by the unaltraweb core.
lang: en
ref: reusable_workflows
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- contributors
- core-developers
section: Publish With GitHub
weight: 70
permalink: "/reusable-workflows/"
nav_title: GitHub Workflows
---
Child sites should keep workflow files thin and call reusable workflows from the core repository.

These wrappers should normally be manual-only. Use `workflow_dispatch` so a push or Dependabot pull request does not start a deploy unless someone explicitly asks for it.

## Site deploy

```yaml
jobs:
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@<reviewed-commit-sha>
```

Pin the reusable workflow to a reviewed commit because it receives Pages and OIDC permissions. The workflow checks out the site, installs Ruby dependencies, rejects stale computational results, builds with the `unaltraweb` gem config and deploys to GitHub Pages. Set `check-computations: false` only for a site that intentionally uses another freshness gate.

For lower-cost publishing, prefer the template's local `make publish` target and configure GitHub Pages to serve the generated `gh-pages` branch.

## Publication metrics

```yaml
jobs:
  metrics:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/metrics-update.yml@main
```

Metrics updates are manual and explicit. Normal site deploys remain static.

## Project computation images

Projects that extend a core computation image can publish a separate GHCR package without copying the factory workflow:

```yaml
name: Publish Python computation image

on:
  workflow_dispatch:

permissions:
  contents: read
  packages: write

jobs:
  image:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/project-compute-image.yml@<reviewed-commit-sha>
    with:
      engine: python
      image: example-compute-python
      dockerfile: Dockerfile.compute-python
      context: .
      base_image: ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:<digest>
```

Pin the reusable workflow to a reviewed commit because it receives the caller's package-write token. The workflow checks out the consumer repository, passes `BASE_IMAGE`, and publishes `main` and `sha-*` under the consumer repository owner. It also publishes release-tag metadata when invoked from a tag ref. Keep engine-specific dependencies and lockfiles in that project; for example, a TIGIT site should publish `tigit-compute-r`, not a TIGIT variant of the core package.

After publication, make the package public or authenticate Docker, select its full GHCR digest in `.unaltraweb/computations.yml`, run `manual-compute-render`, and commit the updated generated artifacts and computation lock. Publishing an extension does not select or rerender it automatically.
