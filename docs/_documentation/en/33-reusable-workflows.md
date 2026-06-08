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

## Site deploy

```yaml
jobs:
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@main
```

The reusable workflow checks out the site, installs Ruby dependencies, builds with the `unaltraweb` gem config and deploys to GitHub Pages.

## Publication metrics

```yaml
jobs:
  metrics:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/metrics-update.yml@main
```

Metrics updates are manual and explicit. Normal site deploys remain static.
