---
title: Check Profile Features Before Publishing
description: What to check before choosing and publishing a profile.
lang: en
ref: profile_checklist
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Build A Site
weight: 270
permalink: "/profiles/checklist/"
nav_title: Feature Checklist
---
Before publishing a child site, check the profile contract rather than only the visual layout.

## Configuration

- `unaltraweb.site_profile` is set to one profile.
- `unaltraweb.features` matches the sections you intend to publish.
- `url` and `baseurl` match the GitHub Pages target.
- `languages` includes only the languages you are actually maintaining.

## Content

- Every page has `lang`, `ref` and a stable `permalink`.
- Profile-specific pages use `profiles`.
- Collection entries use the fields expected by their layouts.

## Local Review

```bash
make build SITE_PROFILE=unaltredocs
make test SITE_PROFILE=unaltredocs
```
