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
The pending distribution contract selects this eventual shared image, which is published manually from the core repository and may not exist remotely yet:

```text
ghcr.io/dosquartsdedocs/unaltraweb:0.3.0
```

It provides the runtime environment: Ruby, Bundler, Jekyll system dependencies, ImageMagick, Node for ExecJS and Python tooling.

The image is not the source of layouts and styles. Those come from the `unaltraweb` gem in the child site's `Gemfile`.

The GHCR package is kept because it makes the local Docker workflow cheap and repeatable. Publishing is manual. Its unprivileged `preflight` job performs package and source checks without a registry login or Docker build. A default-branch run then crosses three separate credential boundaries:

1. `build-candidates` has package-write, attestation-write, and OIDC signing authority but never executes a candidate. It checks that the runtime, MCP, and manual PDF `sha-<full-commit>` tags are absent, builds and pushes each image exactly once under only its SHA tag, and builds MCP from the runtime build's exact digest. Each build retains BuildKit SBOM and maximum provenance and is immediately followed by a GitHub-signed SLSA build-provenance attestation for the exact repository and digest, stored with the image in GHCR.
2. `test-candidates` has only read permissions. It authenticates to GHCR with its read-scoped token, verifies each exact digest's registry-stored attestation against repository `dosquartsdedocs/unaltraweb`, signer workflow `dosquartsdedocs/unaltraweb/.github/workflows/docker-image.yml`, and the current source commit, then pulls and checks the OCI revision labels. It explicitly logs out and destroys its dedicated Docker credential directory before candidate execution. No `GH_TOKEN` is present while it runs every `test/**/*_test.rb` file from a read-only source mount, all manual PDF integration tests, reproducibility and MCP smoke with the MCP digest, and docs with the runtime digest. Only digests that pass every gate become job outputs.
3. `promote-candidates` regains package-write authority but never executes a candidate. It rechecks the signed attestations, SHA tags, and revision labels, then points `sha-<full-commit>`, `main`, and `latest` at the tested digests with `docker buildx imagetools create` and verifies all resulting tag digests. A failed test run therefore cannot advance broad aliases, and no image is rebuilt after testing.

GHCR does not provide this workflow with a compare-and-swap tag update. The absence check before the build and the equality checks before and after promotion reduce accidental clobbering, but a package administrator can still race those separate registry operations. The durable evidence is the signed, source-bound digest that the read-only job tested, not a claim that the SHA tag update is atomic.

A receipt-only child commit records the immutable candidate digests outside the image contents. On the exact release tag, the package-write `promote-release` job executes no candidate and performs no rebuild. It requires each receipt-derived SHA tag to resolve to the recorded digest, verifies the GitHub-signed provenance with `--source-digest` set to `receipt.source_commit`, checks the revision label against that same commit, and only then creates and verifies version aliases. The hosted runner uses the following verification shape for each digest; an OCI verification requires read authentication to GHCR:

```bash
gh attestation verify oci://ghcr.io/dosquartsdedocs/unaltraweb@sha256:<digest> \
  --bundle-from-oci \
  --repo dosquartsdedocs/unaltraweb \
  --signer-workflow dosquartsdedocs/unaltraweb/.github/workflows/docker-image.yml \
  --source-digest <source-commit>
```

During local core development, use the locally built image:

```bash
docker build -t unaltraweb:dev .
make docs-serve DOCKER_IMAGE=unaltraweb:dev
```

After the first GHCR publish, make the package public and confirm unauthenticated pulls work.

## Computation Images

Executable manual chapters use separate images from the Jekyll runtime and PDF builder:

```text
ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:18cb269811bd4005800382da25a480ec2bca7eac8d0501ad1ef36bad1c0f8cd9
ghcr.io/dosquartsdedocs/unaltraweb-compute-r@sha256:928ffb93f221e09e8b929157dee473b838e061915a2eb67224e4124b85f81837
```

The Python image provides Quarto, Jupyter, NumPy, pandas, Matplotlib, GeoPandas, and geospatial libraries. The R image builds on `rocker/geospatial`, preserves RStudio Server, and adds Quarto, `knitr`, `rmarkdown`, `renv`, and the computation driver.

Prepare the selected images with:

```bash
make manual-compute-image-python
make manual-compute-image-r
make manual-compute-images
```

An image already available locally is reused. Otherwise the target pulls a selected published image or builds a configured project extension. New `unaltremanual` sites select both release workers in `.unaltraweb/computations.yml`, and `manual_computation_render` performs this preparation automatically for each engine that has discovered sources.

The factory owns the `manual-compute-*` Make targets and exposes them to child repositories through the MCP computation tools. Package-created sites keep a small build/serve Makefile instead of copying the computation implementation. Rendering and project image preparation run through the factory because they need the core scripts and Docker contracts.

Do not use host `quarto render` for publishable manual computations. Missing Jupyter packages, read-only runtime directories such as `/run/user/...`, and local socket restrictions are host-environment failures; use `manual_computation_render` instead so the selected computation image supplies Quarto/Jupyter and records provenance.

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

### Figure-Only Sources

Use `unaltraweb_compute.mode: figure` when a Quarto, R, Python, or notebook source owns reusable figures but not a generated manual chapter. Declare every versioned output explicitly:

```yaml
title: Palette reference
lang: en
ref: palette_reference
unaltraweb_compute:
  engine: python
  mode: figure
  outputs:
    - assets/img/generated/en/palette-reference.svg
```

The renderer executes the source in the selected computation image, verifies the declared outputs exist, records their signatures in `.unaltraweb/computations.lock.json`, and marks them stale if source code, inputs, Dockerfiles, lockfiles, image identity, or output bytes change.

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

Core maintainers publish both base images with the manual `Compute images` workflow in `.github/workflows/compute-images.yml`. Its strict, no-credentials preflight and no-push build matrix must complete before its package-write matrix can start. Candidate Python and R images carry SBOM/provenance and default-branch `main` plus full-commit `sha-*` channels; release-tag runs promote a recorded immutable digest instead of rebuilding. Consumer defaults use the digest-pinned references selected by the BOM. Packages intended for child sites must allow unauthenticated pulls.

Projects can call `.github/workflows/project-compute-image.yml` to publish their own extension package. Use a separate package name such as `example-compute-r`; do not encode project dependencies as variants of `unaltraweb-compute-r`.

The current publication workflows build `linux/amd64` images. ARM authors need Docker emulation or a separately published compatible image; image IDs recorded in the computation lock are platform-specific.

## Web Capture Image

Selector-based screenshot authoring uses a separate Playwright image rather than adding Chromium to the Jekyll runtime:

```text
ghcr.io/dosquartsdedocs/unaltraweb-web-capture:0.3.0
```

The image contains pinned Playwright/Chromium, the capture worker, the Python status controller, and the core visual sources used in fingerprints. `make web-capture-image` builds the explicitly named `unaltraweb-web-capture:dev` maintainer image; set `WEB_CAPTURE_IMAGE` to that name when testing it. The manual `Web capture image` workflow publishes default-branch, commit, and semver/release tags to GHCR.

Manual PDF commands similarly consume `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf:0.3.0` by default. `manual-pdf-image` reuses or pulls that selected image instead of rebuilding it locally. A pending release may therefore fail to pull until it is actually published. Maintainers use `make manual-pdf-image-dev` and then pass `MANUAL_PDF_IMAGE=unaltraweb-manual-pdf:dev` for local PDF runtime changes.

Rendering creates an ephemeral Docker `--internal` network shared only by Jekyll and Chromium, keeps browser requests on the preview origin, blocks service workers, popups, and WebSockets, drops Linux capabilities, uses a read-only container root and bounded resources, and writes only the declared PNG/SVG outputs under the mounted project. Ordinary checks run without browser execution or network access.
