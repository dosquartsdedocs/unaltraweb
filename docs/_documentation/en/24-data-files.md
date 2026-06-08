---
title: Data Files Reference
description: Structured data files commonly used by unaltraweb child sites.
lang: en
ref: data_files_reference
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- site-designers
- contributors
- core-developers
section: Reference
weight: 910
permalink: "/data-files/"
nav_title: Data Files
---
Use `_data/` for structured content that should not live inside prose pages.

| File | Typical use |
|---|---|
| `_data/i18n/*.yml` | Interface labels and local translations. |
| `_data/metrics.yml` | Generated publication metrics summary. |
| `_data/metrics-overrides.yml` | Manual metric corrections. |
| `_data/repositories.yml` | Repository cards and links. |
| `_data/team.yml` or local equivalents | Team members for project pages. |

Keep generated data reviewable. Metrics workflows should commit versionable outputs such as `_data/metrics.yml`, not local caches.
