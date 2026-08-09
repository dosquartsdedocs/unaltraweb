---
name: bibliometrics-maintenance
description: Use when checking or updating static bibliometrics, Scimago cache state, citation counts, OpenAlex/Crossref fields, or _data/metrics.yml.
---

# bibliometrics maintenance

The public site build must remain static. Bibliometrics are fetched before build time and written into versionable files.

Use `bibliometrics_check` for offline validation. Use `bibliometrics_update` only when the user expects `_bibliography/*.bib` and `_data/metrics.yml` changes. Use `bibliometrics_fetch_scimago` or `fetch_scimago=True` when local Scimago data must be refreshed.

Keep `.cache/scimago`, `tmp/metrics-report.json`, and unmatched diagnostics out of durable content unless the repository explicitly versions them. Prefer reporting uncertain matches over writing misleading metric fields.
