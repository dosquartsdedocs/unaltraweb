---
title: Bibliometric Metrics Pipeline
description: Static bibliometric metrics workflow for unaltraweb sites.
lang: en
ref: bibliometrics
profiles: [unaltredocs]
section: Operations
weight: 410
permalink: /bibliometrics/
---

This project uses a data-first bibliometrics workflow:

- metrics are fetched and written into BibTeX fields (`x_*` + `note`) in a pre-build step,
- aggregated totals are generated into `_data/metrics.yml`,
- Jekyll render remains static (no API calls during `jekyll build`).

## Files

- `scripts/biblio/metrics_update.py`
- `scripts/biblio/metrics_merge_meta.py`
- `scripts/biblio/fetch_scimago_csv.sh`
- `_data/metrics-overrides.yml`
- `_data/metrics.yml` (generated summary; useful for metrics summary components)

## Local data cache (not versioned)

- `.cache/scimago/scimagojr.csv`

Large Scimago datasets are intentionally excluded from git.

## Scimago source

`make metrics-scimago-fetch` downloads the public `sjrdata` R dataset and converts it to CSV:

- source: `https://raw.githubusercontent.com/ikashnitsky/sjrdata/master/data/sjr_journals.rda`
- output: full CSV (all available Scimago columns). Required minimum columns: `year,issn,sjr,sjr_best_quartile,categories`

You can also pass local files:

- `./scripts/biblio/fetch_scimago_csv.sh --input path/to/sjr_journals.rda`
- `./scripts/biblio/fetch_scimago_csv.sh --input path/to/scimagojr.csv`

## Commands

From repository root:

```bash
make metrics-scimago-fetch
make metrics-update
make metrics-update-all
make metrics-check
```

Local commands accept extra script arguments:

```bash
make metrics-update METRICS_ARGS="--strict-external --require-scimago"
make metrics-check METRICS_ARGS="--require-scimago"
make metrics-scimago-fetch SCIMAGO_INPUT=path/to/scimagojr.csv
```

Equivalent direct commands:

```bash
./scripts/biblio/fetch_scimago_csv.sh
python3 scripts/biblio/metrics_update.py
python3 scripts/biblio/metrics_update.py --offline --dry-run
```

## GitHub workflow

Publication metrics are not part of automatic CI. Use the manual/reusable `.github/workflows/metrics-update.yml` workflow when you want GitHub to update or check metrics.

The workflow keeps generated Scimago files and diagnostics out of pull requests. When PR creation is enabled, PRs include only versionable generated data: BibTeX changes under `_bibliography/` and the aggregate `_data/metrics.yml` summary.

Child repositories can add a thin manual wrapper:

```yaml
name: Update publication metrics

on:
  workflow_dispatch:

jobs:
  metrics:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/metrics-update.yml@main
    with:
      fetch_scimago: true
      create_pull_request: true
```

Useful workflow inputs:

- `fetch_scimago`: downloads and validates the local Scimago CSV cache before updating metrics.
- `offline`: skips OpenAlex and Crossref calls.
- `dry_run`: avoids rewriting BibTeX entries while still writing diagnostics.
- `strict_external`: fails the workflow if OpenAlex or Crossref requests fail.
- `require_scimago`: fails when the Scimago CSV is unavailable.
- `create_pull_request`: opens a PR with generated versionable changes.

If `create_pull_request` is `false`, the workflow uploads `_data/metrics.yml` and diagnostics as artifacts but does not persist generated changes.

## Failure modes

- Missing Scimago cache: entries are marked with `scimago-missing` unless `--require-scimago` is set.
- Broken Scimago URL or blocked network: `fetch_scimago` fails with a message suggesting a local `--input` file.
- OpenAlex/Crossref outage: entries are marked with `api-error`, diagnostics include request errors, and `--strict-external` makes the command fail non-zero.

## Overrides

Use `_data/metrics-overrides.yml` to force IDs and values when automatic matching fails.
Supported examples:

- `openalex_id`
- `crossref_cited_by`
- `gs_id`, `gs_cited_by`
- `x_scimago_*`

## Diagnostics

The update script produces:

- `tmp/metrics-report.json`
- `tmp/metrics-unmatched.tsv`

Use these files to review unmatched DOI/ISSN items and stale Scimago matches.

## Build/deploy note

Because metrics are precomputed and saved in repo files, site build does not need runtime access to OpenAlex, Crossref, Scimago, or Google Scholar APIs.

If deploying with GitHub Pages and `jekyll-scholar`, keep using a custom GitHub Actions build (not the restricted native Pages build).
