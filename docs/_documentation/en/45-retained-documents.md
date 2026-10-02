---
title: Import A Retained Letter
description: Verify and retain a Carta letter bundle, display its PDF on the web and include it in a manual.
lang: en
ref: retained_documents
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- core-developers
section: Build A Site
weight: 240
permalink: /retained-documents/
nav_title: Retained Documents
---

A retained letter combines its original PDF with the source, rendering inputs and
provenance needed to inspect its origin. The importer keeps that complete unit in
the receiving repository and creates a native page or chapter referencing the PDF.
The website displays the original; a manual PDF includes all its pages.

This capability ships in **0.6.0**. It requires a
containing Python package and Jekyll core, plus the matching PDF worker for manual
output. The published 0.5.1 runtime predates it. Changing the global MCP selection
does not update a site's Gemfile, Makefile or PDF-worker selection.

Native gem builds need Python with `PyYAML>=6,<7`, `pypdf>=6,<7` and
`markdown-it-py>=3,<5`. The containing MCP/PDF images provide these dependencies;
the containing reusable deployment workflow installs the PDF/text parsers when
retained imports are present.

## Supported Input

The receiving profile accepts leaf `letter-pdf-v1` bundles from **Carta
0.3.0rc1**, using the existing artifact handoff v1 envelope. Verification covers
the supplied sender SHA-256, complete file inventory, retained render recipe,
templates, source references, drawable resources and renderer identity. PDF
inspection is bounded and rejects encrypted files, embedded or external files,
JavaScript and unsupported actions. Internal destinations and textual HTTP,
HTTPS and email links are supported.

Renderable metadata is checked independently of the retained Pandoc AST. A
resealed bundle with an unretained local link in a subject or author field is
rejected even when its older parsing evidence does not mention that link.

Limits are 64 MiB for the payload unit, 32 MiB for the PDF and 1–64 pages. The
supported source subset excludes body images, raw markup, TeX, math and citations;
attachments remain text labels. Composite bundles, edited PDF variants and
Diapora composition require separate receiving profiles.

Obtain the bundle's expected SHA-256 through the sender's trusted handoff. A hash
computed only from an unknown local manifest establishes consistency, not its
origin. Importing never executes the retained recipe or contacts the producer.

## Import Into A Consumer

Start with an initialized consumer Git repository. Place the complete incoming
bundle under a workspace-relative directory such as `tmp/incoming/letter/`.
The recovery area under `tmp/` must be ignored and untracked; durable destinations
must be eligible for version control.

Review a plan using the installed CLI. Here `BUNDLE_SHA` is the sender's verified
manifest digest:

```bash
unaltraweb-mcp --project /absolute/consumer mcp import-artifact-bundle \
  --path tmp/incoming/letter/bundle.json --sha256 "$BUNDLE_SHA" \
  --import-id correspondence --content-path _chapters/en/correspondence.md \
  --title "Retained correspondence"
```

To apply the reviewed request, repeat it with `--apply --confirm-import`.
The MCP equivalent is `import_artifact_bundle` with `dry_run=false` and
`confirm_import=true`; its default is a read-only plan.

Choose a new Markdown destination under `_pages/`, or `_chapters/` for a manual,
or `_documentation/` for a documentation site. An executable source owning the
same Markdown basename blocks creation. The generated document starts as a draft
in the consumer's default language, with a literal local permalink.

The resulting paths are:

| Path | Purpose |
| --- | --- |
| `.unaltraweb/artifacts/correspondence/bundle/` | Complete, unchanged incoming seal, outside the web output |
| `.unaltraweb/artifacts/correspondence/integration.json` | Standard v1 integration record and byte-preserving PDF mapping |
| `.unaltraweb/artifacts/correspondence/binding.json` | Native content path and integration-record digest |
| `assets/documents/correspondence.pdf` | Public PDF, identical to the retained original |
| `_chapters/en/correspondence.md` | Native chapter with the retained-document component |

Version the complete durable unit together. The incoming directory and ignored
recovery journal are not runtime dependencies. The retained archive is excluded
from website output, but remains ordinary repository content.

## Edit And Render The Native Document

Add explanatory prose to the generated page or chapter while preserving its
literal permalink and component:

{% raw %}
```liquid
{% retained_document correspondence %}
```
{% endraw %}

On the web, the component renders a PDF object with a labelled download link.
The build checks the bound page's exact local PDF URL and the emitted PDF bytes.
Exposing the retained archive in the website is an error. In a manual, the PDF
builder includes every original page and fingerprints the entire retained unit
and its checker implementation. A controller/worker mismatch therefore fails
freshness verification rather than silently accepting an older checker.

Run `artifact_import_check` or the CLI equivalent before building:

```bash
unaltraweb-mcp --project /absolute/consumer mcp artifact-import-check
unaltraweb-mcp --project /absolute/consumer mcp artifact-import-check --output-folder _site
```

`site_check` and `site_doctor` include the native integrity check. For a local
manual review, use `manual_pdf_preview_prepare`, then `build_site` and
`preview_start`. Review the web page and composed PDF, then clean only the
receipt-owned preview copies through `manual_pdf_preview_clean`.

## Preservation And Recovery

An identical reimport preserves authored prose. A changed mapped PDF, conflicting
destination, unsafe path or modified seal blocks the operation; existing files
are never overwritten. After an interrupted import, unchanged partial files may
be adopted by an explicit retry of the same request. Differing partial files
require inspection. The operation retains its prepared tree and journal under
`tmp/unaltraweb-artifact-imports/` and performs no destructive rollback.

The native check verifies references and content after the incoming producer copy
has been removed or the receiving repository has moved. It also detects missing
content, incomplete retention and altered mappings. The generic v1 verifier can
independently inspect `integration.json`; it does not replace the native source
and rendered-output checks.
