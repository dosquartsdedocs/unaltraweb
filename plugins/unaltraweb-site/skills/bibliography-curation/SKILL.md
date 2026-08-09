---
name: bibliography-curation
description: Use when adding, revising, deduplicating, or approving BibTeX entries for unaltraweb sites.
---

# bibliography curation

Use `bibliography_inventory` before changing BibTeX. Never invent authors, titles, venues, years, DOI values, URLs, citekeys, publication status, citation counts, quartiles, or impact metadata.

Add entries only from verified metadata or author-provided BibTeX. If a citekey already exists, ask before replacing it and preserve intentional local fields such as selected/publication preview fields unless the replacement explicitly updates them.

After bibliography changes, run `bibliometrics_check` when feasible and report unresolved duplicates or unmatched publications.
