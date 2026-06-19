---
title: Use The Docker Image
description: Runtime image used by local unaltraweb workflows.
lang: en
ref: docker_image
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- core-developers
section: Work Locally
weight: 140
permalink: "/docker-image/"
nav_title: Docker Image
---
The shared image is published from the core repository:

```text
ghcr.io/dosquartsdedocs/unaltraweb:main
```

It provides the runtime environment: Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling.

The image is not the source of layouts and styles. Those come from the `unaltraweb` gem in the child site's `Gemfile`.

The GHCR package is kept because it makes the local Docker workflow cheap and repeatable. Publishing the image is manual: run `.github/workflows/docker-image.yml` only when runtime dependencies change. The workflow publishes `main`/`latest` from the default branch and release tags from tag refs; it does not publish per-commit SHA tags by default.

During local core development, use the locally built image:

```bash
docker build -t unaltraweb:local .
make docs-serve DOCKER_IMAGE=unaltraweb:local
```

After the first GHCR publish, make the package public and confirm unauthenticated pulls work.
