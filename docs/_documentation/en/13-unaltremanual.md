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

Unlike `unaltredocs`, `unaltremanual` keeps linear reading affordances such as previous/next chapter navigation. Use it when the primary path through the content is sequential.
