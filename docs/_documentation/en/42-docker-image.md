---
title: Docker image
description: Runtime image used by local unaltraweb workflows.
lang: en
ref: docker_image
profiles: [unaltredocs]
section: Operations
weight: 420
permalink: /docker-image/
---

The shared image is published from the core repository:

```text
ghcr.io/dosquartsdedocs/unaltraweb:main
```

It provides the runtime environment: Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling.

The image is not the source of layouts and styles. Those come from the `unaltraweb` gem in the child site's `Gemfile`.

During local core development, use the locally built image:

```bash
docker build -t unaltraweb:local .
make docs-serve DOCKER_IMAGE=unaltraweb:local
```

After the first GHCR publish, make the package public and confirm unauthenticated pulls work.
