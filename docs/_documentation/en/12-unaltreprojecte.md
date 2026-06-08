---
title: Build A Project Site With unaltreprojecte
description: Research project and infrastructure sites.
lang: en
ref: profile_unaltreprojecte
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
section: Build A Site
weight: 240
permalink: "/profiles/unaltreprojecte/"
nav_title: Project Site
---
Use `unaltreprojecte` for a funded project, lab infrastructure, consortium or research output site.

```yaml
unaltraweb:
  site_profile: unaltreprojecte
  features:
    publications: true
    readings: true
    news: true
```

Typical content:

- Project landing pages in `_pages/`.
- Team data in `_data/`.
- `_outputs/` for reports, datasets, maps and policy briefs.
- `_projects/` for related or previous projects.
- Repository and resource pages.

Project cards can use `hero` images and `resources` badges for DOI, GitHub, documentation and datasets.
