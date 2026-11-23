---
title: Practice inputs and editions
description: Prepare immutable inputs before freshness and compose explicit tabular or native GIS private editions.
lang: en
ref: practice_inputs_editions
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 680
permalink: /practice-inputs-editions/
---

## Existing practice paths stay stable

Editable sources stay in `practiques/<slug>/`. Retained data and attempts stay in
ignored `sandbox/practiques/<slug>/<run>/`; final private deliveries stay in
ignored `dist/practiques/<slug>/<version>/<lang>/`. Exclude `practiques/`,
`sandbox/` and `dist/` from Jekyll. An ignore or exclusion grants no cleanup or
publication permission.

Use `ca/<alumnat|docent>/LLEGIU-ME.md`,
`es/<alumnat|docent>/LEEME.md`, or `en/<alumnat|docent>/README.md` beneath the
practice. Existing explicit `unaltraweb.practices.readings` mappings remain
available for legacy sources. See [private practice PDFs]({{ '/private-practice-pdfs/' | relative_url }})
for metadata, approvals, the retained PDF worker and reading bindings.

## Prepare pinned data before freshness

`site-deploy.yml` checks generated computation, Vega and PDF freshness **before**
`build-command`. Data hydration belongs in the new optional `prepare-inputs` and
`prepare-inputs-sha256` inputs, not in that late build command. Stable
`site-release.yml` accepts the same pair as `prepare_inputs` and
`prepare_inputs_sha256`. Both fields must be selected together; omitted fields
retain existing behavior.

The provider-owned helper runs from the immutable workflow revision before the
checks. It does not render, run a project script, disable checks, copy data to
`_site`, or access a private hub. Source-only CI is unchanged and never hydrates
datasets or renders a manual.

New scaffolds include a project-owned `.unaltraweb/input-preparation.json` with
an empty `resources` list. To select an existing versioned resource inventory:

```json
{
  "schema_version": 1,
  "resources": [
    {
      "profile": "immutable-github-files-v1",
      "manifest": "practiques/example/recursos.yml",
      "sha256": "<reviewed resource-manifest SHA-256>"
    }
  ]
}
```

The resource manifest is YAML or JSON with this exact shape. This profile reuses
the existing TIGIT inventory vocabulary instead of invoking or copying its
domain-specific preparer:

```yaml
schema_version: 1
kind: unaltraweb-prepared-inputs
version: 2026-11-r1
source_commit: <full immutable Git commit>
source_prefix: archived-inputs/example/
source_url: https://raw.githubusercontent.com/owner/repository/<same-commit>/archived-inputs/example/
snapshot: sandbox/practiques/example/inputs/2026-11-r1
files:
  - path: data/table.csv
    sha256: <exact file SHA-256>
    bytes: 1234
```

`kind` is retained provenance, not a claim that Web produced those domain bytes.
The top plan and resource manifests must be versioned, non-ignored files. The
reviewed SHA of the top plan is an explicit invocation/workflow input. The only
network origin in this profile is HTTPS GitHub raw at the exact full commit and
prefix; moving refs, redirects, live statistical queries and embedded credentials
are refused. Other providers/private input acquisition require a separately
qualified profile; they are not inferred from arbitrary URLs.

```bash
unaltraweb-prepare-inputs --project "$PWD" \
  --config .unaltraweb/input-preparation.json \
  --sha256 "$REVIEWED_INPUT_PLAN_SHA256" --fetch

unaltraweb-prepare-inputs --project "$PWD" \
  --config .unaltraweb/input-preparation.json \
  --sha256 "$REVIEWED_INPUT_PLAN_SHA256" --check
```

For an adopted generated Docker runtime, the explicit local equivalent is:

```bash
make manual-inputs-prepare \
  INPUT_PREPARATION_SHA256=<reviewed-hash> INPUT_PREPARATION_FETCH=1
```

Omit `INPUT_PREPARATION_FETCH=1` for a readonly check. Normal source checks and
build targets never imply fetch. A new snapshot is create-only and independently
read back. Existing exact bytes are reused without rewriting receipts; a changed
or partial snapshot is preserved and refused. Partial attempts remain retained.
The data can be reconstructed from its pinned origin outside Git; the helper does
not execute workbook/GIS models or recalculate a statistical source.

## Explicit tabular editions

The original edition v1 schema remains the GIS contract, including native
producer verification and its accepted profiles. To compose spreadsheet/table
materials without GIS, explicitly select `schema_version: 2, mode: tabular`.
`web://practice-tabular-edition-schema` exposes this separate package-owned schema;
the existing `manual_practice_compose` tool/CLI dispatches by declared version.

```yaml
schema_version: 2
kind: unaltraweb-practice-edition
mode: tabular
slug: example
version: 2026-11-r1
language: ca
materials:
  - id: initial
    path: sandbox/practiques/example/inputs/2026-11-r1/data/table.csv
    destination: resources/table.csv
    sha256: <exact file SHA-256>
    bytes: 1234
    role: initial-data
    recipients: [alumnat, docent]
selection:
  alumnat: [initial]
  docent: [initial]
readings:
  alumnat:
    source: practiques/example/ca/alumnat/LLEGIU-ME.md
    approved_sha256: <approved reading SHA-256>
  docent:
    source: practiques/example/ca/docent/LLEGIU-ME.md
    approved_sha256: <approved reading SHA-256>
```

Tabular roles are `initial-data` (CSV/CSVT/TSV), `initial-workbook`,
`resolved-workbook`, `demonstration-workbook` (XLSX/ODS), and
`reference-document` (PDF/PNG/JPEG). Resolved workbooks are teacher-only;
demonstrations shared with students must be explicitly selected and labelled as
such. Scripts, caches, logs, arbitrary job trees and GIS files are not tabular
classroom materials. Editable SVGs still use the existing explicit `resources`
and dependency closure contract. No neighbouring file is inferred.

The composer verifies selected hashes, sizes, destinations and recipients. It
does not calculate or semantically validate a workbook and does not fabricate a
GIS bundle. Both schemas use approved reading hashes, the native PDF build/seal,
portable resource links and the same create-only ZIP/PDF copy and receipt path.

Output names stay `<slug>[-docent]-<version>-<lang>.pdf` and `.zip`, with external
receipts. Inside each ZIP the reading is `LLEGIU-ME.pdf`, `LEEME.pdf` or
`README.pdf`; the independent PDF has exactly those sealed bytes. Reusing a
version never overwrites an edition. The operation always reports
`publishes: false`; Moodle and public-site publication remain separate decisions.

## Adoption and qualification

Consumers adopt reviewed workflow/runtime pins explicitly. Synchronizing a
scaffold does not upgrade an accepted image or QGIS helper. Owners then bind
their exact manifests/approved readings, reproduce hydration from a clean source
checkout, run existing freshness/PDF/build checks, and qualify the final extracted
packet with its native producer. Synthetic core tests do not replace those gates.
The technical requirement audit is retained in
`docs/agents/web-practices-reconciliation.md`; it distinguishes implemented paths
from consumer migration, provider qualification and teaching review still pending.
