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

## Computation Images

Executable manual chapters use separate images from the Jekyll runtime and PDF builder:

```text
ghcr.io/dosquartsdedocs/unaltraweb-compute-python:main
ghcr.io/dosquartsdedocs/unaltraweb-compute-r:main
```

The Python image provides Quarto, Jupyter, NumPy, pandas, Matplotlib, GeoPandas, and geospatial libraries. The R image builds on `rocker/geospatial`, preserves RStudio Server, and adds Quarto, `knitr`, `rmarkdown`, `renv`, and the computation driver.

Prepare the selected images with:

```bash
make manual-compute-image-python
make manual-compute-image-r
make manual-compute-images
```

An image already available locally is reused. Otherwise the target pulls a selected published image or builds a configured project extension.

### Select An Image

Image resolution uses this precedence:

1. `COMPUTE_PYTHON_IMAGE` or `COMPUTE_R_IMAGE` from Make or the environment.
2. `engines.<engine>.environments.<COMPUTE_ENV>` in `computations.yml`.
3. A configured `local_image` with a project Dockerfile in the local environment.
4. `engines.<engine>.image` in `computations.yml`.
5. The corresponding core GHCR image.

`COMPUTE_ENV` defaults to `ci` when `CI` is true and to `local` otherwise. Keep environment selection in `computations.yml`:

```yaml
engines:
  python:
    environments:
      local: my-manual-compute-python:local
      ci: ghcr.io/example/my-manual-compute-python@sha256:<digest>
```

Use `COMPUTE_PYTHON_IMAGE` or `COMPUTE_R_IMAGE` only as an explicit one-command override. Prefer digest-pinned CI images when the remote image identity must be independently reproducible.

### Extend An Image

Keep project-specific packages outside the core. Configure a Dockerfile and version its dependency lock:

```yaml
engines:
  python:
    dockerfile: Dockerfile.compute-python
    context: .
    base_image: ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:<digest>
    local_image: example-compute-python:local
    lockfiles:
      - requirements-compute.txt
```

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

COPY requirements-compute.txt /tmp/requirements-compute.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-compute.txt
```

The builder passes `BASE_IMAGE`, defaults the context to the project root, and builds a lowercase, Docker-safe `<project>-compute-<engine>:local` name when `local_image` is omitted. Pin the base image by digest when reproducible project-image builds matter. The Dockerfile and declared lockfiles participate in freshness checks. Extend the base image instead of copying the core renderer.

If a local Docker installation cannot reach package repositories through its default bridge, select another build network explicitly rather than hard-coding it in the Dockerfile:

```bash
make manual-compute-image-r COMPUTE_DOCKER_BUILD_NETWORK=host
```

### Offline Execution

Source execution uses `--network none`, a read-only container root, dropped Linux capabilities, `no-new-privileges`, process/CPU/memory limits, a temporary `/tmp`, a read-write project mount, and a staging directory under `tmp/manual-computations`. Pulling or building an image can require network access, but the actual render cannot fetch remote data. The project mount means trusted source code can still modify repository files; review the working tree after execution. Prepare images and version local inputs before an offline session.

Ordinary web and PDF builds need only committed Markdown and figures. Their freshness check can run without Docker by using the image identity recorded at render time as a provenance trust anchor and validating artifact signatures. It does not resolve a mutable remote tag without network access. A locally available image takes precedence and detects a rebuilt mutable tag; use a digest-pinned image when remote identity must also be immutable.

### RStudio Server

Start the selected R image as a loopback-only authoring environment:

```bash
make manual-compute-rstudio
make manual-compute-rstudio RSTUDIO_PORT=8788
```

The target prepares the image, mounts the project at `/home/rstudio/project`, maps the current user and group, and starts Rocker's `/init` with authentication disabled. Keep the `127.0.0.1` bind. RStudio is an authoring aid; publishable results must still come from `manual-compute-render` and pass `manual-compute-check`.

### Publish To GHCR

Core maintainers publish both base images with the manual `Compute images` workflow in `.github/workflows/compute-images.yml`. Its matrix produces separate Python and R packages with default-branch `main`, commit `sha-*`, and release-tag metadata. Packages intended for child sites must allow unauthenticated pulls.

Projects can call `.github/workflows/project-compute-image.yml` to publish their own extension package. Use a separate package name such as `example-compute-r`; do not encode project dependencies as variants of `unaltraweb-compute-r`.

The current publication workflows build `linux/amd64` images. ARM authors need Docker emulation or a separately published compatible image; image IDs recorded in the computation lock are platform-specific.

## Web Capture Image

Selector-based screenshot authoring uses a separate Playwright image rather than adding Chromium to the Jekyll runtime:

```text
ghcr.io/dosquartsdedocs/unaltraweb-web-capture
```

The image contains pinned Playwright/Chromium, the capture worker, the Python status controller, and the core visual sources used in fingerprints. `make web-capture-image` builds the local image; the manual `Web capture image` workflow publishes default-branch, commit, and release tags to GHCR.

Rendering creates an ephemeral Docker `--internal` network shared only by Jekyll and Chromium, keeps browser requests on the preview origin, blocks service workers, popups, and WebSockets, drops Linux capabilities, uses a read-only container root and bounded resources, and writes only the declared PNG/SVG outputs under the mounted project. Ordinary checks run without browser execution or network access.
