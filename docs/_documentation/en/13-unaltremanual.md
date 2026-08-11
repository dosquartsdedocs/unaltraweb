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

The consumer site's Makefile exposes the stable workflow:

```bash
make manual-pdf-status
make manual-pdf-build
make manual-pdf-publish                 # dry-run by default
make manual-pdf-publish MANUAL_PDF_PUBLISH_DRY_RUN=0
```

Builds remain under `tmp/manual-pdf/<lang>/`. Each language build creates both the PDF and a PNG extracted from its first page. Publication copies those reviewed artefacts together into the configured project-relative public paths; it does not commit, push, deploy, or write outside the site. The download button appears automatically when the configured PDF exists among the site's static files, so it cannot point to a missing build. Chapters can opt out with `pdf: false`.
