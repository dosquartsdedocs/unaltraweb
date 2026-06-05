---
title: unaltremanual profile
description: Manuals, courses and book-like teaching sites.
lang: en
ref: profile_unaltremanual
profiles: [unaltredocs]
section: Profiles
weight: 130
permalink: /profiles/unaltremanual/
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
