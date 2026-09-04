# Quarto computation adoption note

This note records the TIGIT ColorBrewer figure incident from 13 August 2026 and turns it into follow-up work for `unaltraweb`.

## What happened

While editing `/home/benizar/git/tigit`, a Quarto source was added for a manual figure:

- `assets/quarto/color-cartography/palette-reference-swatches.qmd`
- intended output: `assets/img/color-cartography/palette-reference-swatches.svg`

The source was rendered directly with the host `quarto render` command, outside the `unaltraweb` computation workflow. That failed for three independent environment reasons:

1. Quarto tried to create a Jupyter transport directory below `/run/user/1000/jt`, which was read-only in the agent sandbox.
2. The host Python environment did not include `nbclient`; installing it locally also required network access.
3. After redirecting Quarto state to project-local `tmp/` directories, Jupyter still needed to open a local socket, which the sandbox denied.

The immediate failure is therefore not a Jekyll or Markdown rendering bug. It is a workflow problem: executable manual sources should not be run ad hoc on the host environment.

## What is already implemented in unaltraweb

The core already has the right architectural direction:

- `manual-compute-status`, `manual-compute-check`, `manual-compute-render`
- `.unaltraweb/computations.yml`
- `.unaltraweb/computations.lock.json`
- Python and R computation images under `scripts/computations/`
- project-specific image extension through `engines.<engine>.dockerfile`, `context`, `base_image`, `local_image`, `lockfiles`, and `fingerprint_paths`
- explicit image resolution through `COMPUTE_PYTHON_IMAGE`, `COMPUTE_R_IMAGE`, `COMPUTE_ENV`, and configured `environments`

That means the TIGIT issue is not a request to invent repo-specific Docker support from scratch. The support exists in the factory/core, but the child repo workflow must adopt it and the failure mode should be documented more clearly.

## General versus project-specific

There are two layers.

The general `unaltraweb` layer should provide the common computation contract: Quarto, Jupyter, Python, R, rendering, provenance locks, stale-output checks, no-network execution, and safe publication of generated Markdown and figures.

Each child repo should declare non-general dependencies in its own computation image. For TIGIT this may include packages or system libraries used for cartographic figures, geospatial transformations, QGIS-adjacent processing, color science utilities, or any dataset-specific helper library that does not belong in the shared image.

So the ColorBrewer example is a specific TIGIT use case, but the missing adoption path is a general unaltraweb/template concern.

## Desired child-repo pattern

A child repo should be able to keep a small, project-owned Dockerfile:

```yaml
# .unaltraweb/computations.yml
version: 1
enabled: true
source_roots:
  - _chapters
  - assets/quarto
generated_assets_root: assets/img/generated
engines:
  python:
    dockerfile: Dockerfile.compute-python
    context: .
    base_image: ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:18cb269811bd4005800382da25a480ec2bca7eac8d0501ad1ef36bad1c0f8cd9
    local_image: tigit-compute-python:local
    lockfiles:
      - requirements-compute.txt
```

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

COPY requirements-compute.txt /tmp/requirements-compute.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-compute.txt
```

Then the authoring workflow should be:

```bash
MCP_CONSUMER_WORKSPACE="$PWD" make -C ../unaltraweb manual-compute-image-python
MCP_CONSUMER_WORKSPACE="$PWD" make -C ../unaltraweb manual-compute-render COMPUTE_SOURCE=assets/quarto/color-cartography/palette-reference-swatches.qmd
make build
```

or through equivalent child-repo `make` targets once the template Makefile exposes the computation commands directly.

## Follow-up work

1. Verify the synced `../unaltraweb-template` `manual-compute-*` targets in a real child repository after template updates are pulled into that repository. The template now exposes direct targets and uses a local `unaltraweb` checkout for routine status/check when available.
2. Keep the troubleshooting note visible in child docs: if direct host `quarto render` fails with missing Jupyter packages, read-only runtime directories, or socket errors, use `manual-compute-render` instead.
3. Confirm the `mode: figure` path in a real child repository for computation sources outside `_chapters`, such as `assets/quarto/**.qmd`, when listed in `source_roots`.
4. Use figure-only Quarto sources as first-class compute records when the source exists to generate reusable SVG/PNG assets embedded in ordinary Markdown chapters.
5. Add a compact example to the manual documentation showing a project-specific Python computation image with `requirements-compute.txt`.
6. Add or verify a doctor/check message that detects executable sources in a child repo without `.unaltraweb/computations.yml`, or sources that are being kept outside configured roots.

## Figure mode now first class

Items 3 and 4 are closed in TIGIT and the factory:

- `computation_figure_images` (Jekyll plugin) rewrites Markdown/HTML image references that point at a compute source (`.qmd`, `.rmd`, `.r`, `.py`, `.ipynb`) into the source's declared `mode: figure` output. An author-owned `*.edited.svg` override wins and is never overwritten. Builds fail when the referenced source is missing or its output has not been rendered.
- `render.py` supports `--mode figure --stale-only` (wired as `manual_computation_render_figures` through MCP and `manual-compute-render-figures` in the factory Makefile). Rendering is explicit, and package-scaffolded build/test runs reject stale outputs. Present-but-unrecorded outputs are treated as author-managed and are never auto-replaced.
- TIGIT chapter `03` demonstrates the workflow with R `mode: figure` sources under `assets/quarto/data-visualization/`.

## Open design question

The computation renderer now supports an explicit `unaltraweb_compute.mode: figure` contract. It records source, inputs, declared output assets and provenance without manufacturing a chapter Markdown file.
