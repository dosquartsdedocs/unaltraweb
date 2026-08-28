---
title: Build A Personal Site With unaltreselfie
description: Personal academic and professional sites.
lang: en
ref: profile_unaltreselfie
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
section: Build A Site
weight: 230
permalink: "/profiles/unaltreselfie/"
nav_title: Personal Site
---
Use `unaltreselfie` for a personal academic, researcher or professional website.

```yaml
unaltraweb:
  site_profile: unaltreselfie
  features:
    news: true
    blog: true
    cv: true
    projects: true
    publications: true
    readings: true
```

Typical content:

- `author` block in `_config.yml`.
- Localized home pages using `layout: profile`.
- `_posts/`, `_news/`, `_projects/`, `_bibliography/` and CV assets.

The profile card, social links, highlights and publication summaries come from the core theme.
Bibliographies use curriculum order: year and month descending, with author and title as stable tie-breakers inside the same date.
