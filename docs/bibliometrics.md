# Bibliometric metrics pipeline

This project uses a data-first bibliometrics workflow:

- metrics are fetched and written into BibTeX fields (`x_*` + `note`) in a pre-build step,
- aggregated totals are generated into `_data/metrics.yml`,
- Jekyll render remains static (no API calls during `jekyll build`).

## Files

- `scripts/biblio/metrics_update.py`
- `scripts/biblio/metrics_merge_meta.py`
- `scripts/biblio/fetch_scimago_csv.sh`
- `_data/metrics-overrides.yml`
- `_data/metrics.yml` (generated)

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

Equivalent direct commands:

```bash
./scripts/biblio/fetch_scimago_csv.sh
python3 scripts/biblio/metrics_update.py
python3 scripts/biblio/metrics_update.py --offline --dry-run
```

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
