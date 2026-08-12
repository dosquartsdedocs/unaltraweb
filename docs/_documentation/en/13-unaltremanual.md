---
title: Build A Manual With unaltremanual
description: Manuals, courses and book-like teaching sites.
lang: en
ref: profile_unaltremanual
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Build A Site
weight: 250
permalink: "/profiles/unaltremanual/"
nav_title: Manual Site
---
Use `unaltremanual` for long-form teaching material, course manuals and book-like documentation.

```yaml
unaltraweb:
  site_profile: unaltremanual
  manual:
    collection: chapters
    cover_image: /assets/img/manual-cover.png
    show_chapter_index: true
  figure_captions:
    enabled: true
    collections: [chapters]
```

Typical content:

- Localized manual home pages with `layout: manual-home`.
- Chapters under `_chapters/<lang>/`.
- Callouts, figures, subfigures, numbered tables and Mermaid diagrams.
- Optional manual bibliography.

The profile includes a sticky chapter sidebar, right-hand table of contents, reader font controls and search index.

The manual home lists chapter cards by default. Set `unaltraweb.manual.show_chapter_index: false` globally, or `show_chapter_index: false` in a manual home page's front matter, when the sidebar is sufficient and the home should contain only introductory material.

Unlike `unaltredocs`, `unaltremanual` keeps linear reading affordances such as previous/next chapter navigation. Use it when the primary path through the content is sequential.

## Executable Chapters

An executable chapter has an authoritative Quarto, R, Python, or notebook source and a versioned same-stem Markdown result. Ordinary Jekyll and PDF builds consume the committed Markdown and figures; they never execute the analysis automatically.

Supported sources are `.qmd`, `.Rmd`, `.R`, `.py`, and `.ipynb`. Keep sources under a configured source root such as `_chapters/`. A default render publishes:

- `chapter.qmd` as `chapter.md` beside its source.
- Figures under `assets/img/generated/<lang>/<ref>/`.
- Provenance and artifact signatures in `.unaltraweb/computations.lock.json`.

Commit the executable source, generated Markdown, generated figures, and lock together. When an executable source exists, edit it rather than the generated `.md`.

### Chapter Metadata

Every executable chapter requires `title`, `lang`, and `ref`. A `.qmd` must also select exactly one engine:

```yaml
---
layout: manual-chapter
title: Computed chapter
lang: en
ref: computed-chapter
weight: 60
unaltraweb_compute:
  engine: python
  inputs:
    - data/source.csv
---
```

`.Rmd` and `.R` infer R; `.py` and `.ipynb` infer Python. Use normal YAML front matter in `.qmd` and `.Rmd`, a `#' ---` roxygen block in `.R`, and a commented `# ---` block in `.py`. A notebook can store the mapping in `metadata.unaltraweb_front_matter` or in the first raw or Markdown cell.

Optional `unaltraweb_compute` fields are `inputs`, `output`, `figures`, and `enabled`. Paths must be project-relative and cannot escape the repository. Generated Markdown must remain under one configured `source_roots` directory; figures must use a strict subdirectory of `generated_assets_root`. Source roots cannot be the project root, cannot overlap each other, and cannot overlap the generated assets root. A custom source root is both a discovery root and a Jekyll source-exclusion root, so keep executable sources and their same-tree Markdown outputs together. `enabled: false` excludes one source. Computation-private metadata is removed from the generated Markdown while public chapter metadata is preserved.

### Project Configuration

Use `.unaltraweb/computations.yml` to define discovery roots, generated assets, images, and environment dependencies:

```yaml
version: 1
enabled: true
source_roots:
  - _chapters
generated_assets_root: assets/img/generated
engines:
  python:
    image: ghcr.io/dosquartsdedocs/unaltraweb-compute-python:main
    lockfiles:
      - requirements-compute.txt
    fingerprint_paths:
      - analysis/helpers
  r:
    image: ghcr.io/dosquartsdedocs/unaltraweb-compute-r:main
    lockfiles:
      - renv.lock
```

`unaltraweb_compute.inputs` declares source-specific non-code inputs. Engine `lockfiles` and `fingerprint_paths` describe shared environment dependencies. Files and directories are fingerprinted recursively. Changing a source, declared input, Dockerfile, lockfile, fingerprint path, configuration, or available selected-image identity makes its results stale.

The execution container has no network, a read-only root filesystem, dropped capabilities, and resource limits, but the entire project is mounted read-write so Quarto can stage results. Declared inputs provide provenance and freshness checks; they are not a filesystem access policy. Run only trusted chapter code and review the working tree after rendering.

### Render And Check

The consumer Makefile exposes the stable workflow:

```bash
make manual-compute-status
make manual-compute-check
make manual-compute-render
make manual-compute-render COMPUTE_SOURCE=_chapters/en/chapter.qmd
```

`status` prints JSON and remains informational even when `ok` is false. `check` exits nonzero for missing, stale, modified, or orphaned results. `render` executes explicitly, stages output, serializes publication per project, and replaces managed Markdown and figures with rollback on ordinary errors. Rendering runs without network access and with Quarto caches disabled.

The first render refuses to overwrite an existing same-stem Markdown file or figure directory that is not recorded in the computation lock. Review the collision before an intentional takeover:

```bash
make manual-compute-render COMPUTE_CONFIRM_OVERWRITE=1
```

Do not use that confirmation as a permanent default. Do not edit `.unaltraweb/computations.lock.json` manually; review it as generated provenance.

Deleting or disabling a source leaves its lock record and generated artifacts as an orphan, so publication remains blocked. Review and remove the old generated Markdown and figure directory, then run a full `manual-compute-render`; the renderer removes an orphan lock record only after both managed paths are absent.

`make serve`, `make build`, profile previews, Playwright checks, PDF operations, and the reusable Pages workflow reject stale results. CI checks committed artifacts without recalculating them. Equivalent MCP tools are `manual_computation_status`, `manual_computation_check`, and `manual_computation_render`.

## PDF Edition

The optional PDF builder runs in a dedicated Docker image containing Pandoc, XeLaTeX, multilingual TeX packages, SVG conversion and Poppler. It reads the same localized manual home and chapter sources as Jekyll, orders chapters by `weight`, resolves rendered Mermaid and PlantUML SVGs, converts Jekyll Scholar citations, and extracts the first PDF page as the web cover.

```yaml
unaltraweb:
  manual:
    bibliography: true
    bibliography_file: manual.bib
    metadata:
      short_title: COURSE
      series: Course materials
      subject: Full course name
      teaching_guides:
        - degree: First degree name
          subject_code: "COURSE-01"
        - degree: Second degree name
          subject_code: "COURSE-02"
      institution: University name
      academic_year: 2026/2027
      revision_date:
        en: August 11, 2026
      instructors:
        - name: First Teacher
    pdf:
      enabled: true
      languages: [en]
      output: assets/pdf/manual-{lang}.pdf
      cover_output: assets/img/manual-cover-{lang}.png
      cover:
        image: assets/img/manual-cover-background.jpg
        institution_logo: assets/img/institution-logo.pdf
        band_color: "990000"
```

The cover deliberately contains only structural publication elements: series, title, instructors, main image, institutional logo, and bands. Course codes, teaching guides, department, faculty, academic year, revision date, and other consumer metadata are rendered on a localized details page inside the PDF.

The PDF workflow checks executable chapters before reading their generated Markdown:

```bash
make manual-pdf-status
make manual-pdf-build
make manual-pdf-publish                 # dry-run by default
make manual-pdf-publish MANUAL_PDF_PUBLISH_DRY_RUN=0
```

Builds remain under `tmp/manual-pdf/<lang>/`. Each language build creates both the PDF and a PNG extracted from its first page. Publication copies those reviewed artefacts together into the configured project-relative public paths; it does not commit, push, deploy, or write outside the site. The download button appears automatically when the configured PDF exists among the site's static files, so it cannot point to a missing build. Chapters can opt out with `pdf: false`.
