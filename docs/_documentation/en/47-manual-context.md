---
title: Export Manual Context for Itemarium
description: Portable, producer-resolved manual text and figures with immutable provenance.
lang: en
ref: manual_context_export
profiles:
  - unaltredocs
documentation_profiles:
  - site-authors
  - core-developers
section: Manuals
weight: 470
permalink: /manual-context/
---

The **0.8.0 development source** introduces `manual_context_export`. Published
0.7.4 and already-running MCP sessions do not acquire it from a checkout edit.
Implementation and interoperability are tracked in
[issue #121](https://github.com/dosquartsdedocs/unaltraweb/issues/121).

## Select the manual

Use a connection bound to the manual workspace. Set a stable, author-owned
`unaltraweb.manual.id` in `_config.yml`; retain it across revisions and relocation.
The title is `unaltraweb.manual.title`, falling back to the site title. Each
chapter needs a unique `ref`, a title, and its configured language. Explicit
heading IDs such as `## Method {#method}` remain stable across title edits.

```python
manual_context_export(name="itemarium-review-01", language="ca", chapters=["first"])
```

The equivalent factory-backed CLI is:

```bash
unaltraweb-mcp --project /absolute/manual mcp manual-context-export \
  --name itemarium-review-01 --language ca --chapter first
```

`--chapter` is repeatable and preserves manual order. `--section first#method`
selects one **exact block**, not its descendants; repeat it for additional blocks.
The MCP arguments are `chapters` and `sections` arrays. Omitting them selects all
chapters/blocks in the requested language. Unknown or duplicate selections fail.

## Delivery and retention

Exports are retained under `tmp/manual-context/<name>/`: `content/`, the flat
`manual-context.tar.gz` and a receipt sealed last. This directory must be ignored
by Git. An existing name is never replaced, even after a failed or interrupted
export. The result returns the workspace-relative `path`, actual `sha256`, receipt
path/hash, producer/manual identities and counts. Only the tar and its SHA are
needed by Itemarium; no source checkout access is necessary.

The archive contains exactly `manual-context.json`, `sections/...md`, and
`figures/...`. Image references use `/figures/...`. The schema is available at
`web://manual-context-schema`. Each heading's file ends before the next heading,
so parent blocks do not duplicate descendant prose. Order is explicit rather
than inferred from filenames. Numbered chapters precede reference chapters, as
in the native manual resolver; public `pdf: false` chapters remain available.

The exporter resolves native figures, localized variants/fallback and the
existing output precedence on a bounded no-follow snapshot. It reuses native
computation status (including generated chapters), complete companion receipts
for diagrams/Vega, and web-capture status. These project-wide completeness checks
also reject unrelated stale/orphaned records; selecting a chapter cannot bypass
a required producer gate. Unmanaged generated outputs are not freshness evidence.

Literal Markdown/HTML includes without parameters, manual bibliography includes,
`cite` tags, tables, subfigures, listings, callouts and definition lists are
projected to portable prose. Captions, credits and bibliography fields/links are
retained; the exporter does not emulate a CSL citation style. Code examples stay
literal. HTML comments are not reader-facing context. Arbitrary Liquid, dynamic
includes and active/interactive HTML need an explicitly prepared portable source
and fail with a diagnostic rather than disappearing.

No renderer or download runs implicitly. Standalone PNG/JPEG/GIF/WebP/SVG images
are accepted. The current receiver rejects SVG `<image>`, even embedded PNG data
in capture SVGs, and excludes PDF. A current native web-capture SVG can pass only
if its effective bytes meet this standalone boundary. QGIS capture provenance
has no native context-v1 adapter in this increment: recognizable QGIS captures
are refused with a diagnostic, not relabelled as static. Its profile/receipt
integration and receiver support for raster-bearing SVG require coordinated
follow-up. Edited captures are never silently substituted with original rasters.

Diagrams use the provider's exact effective-artifact receipt. Vega uses exactly
the output declared in `.vegavisuals.yml` (including an edited output only when
that is the declared, verified output). Computation SVG overrides must postdate
their current source and generated base. Web captures use their native embedded
PNG/fingerprint checks. The exporter records fresh resolution evidence binding
the native check **and the actual effective bytes**; `receipt_sha256` refers to
that evidence in the retained export receipt, not an older renderer receipt
misattributed to new edited bytes.

`manual.revision` is the actual Git HEAD and `dirty` is explicit. Clean source
dates use the commit date; dirty snapshots use the latest consumed file mtime,
with an explicit timezone. The source fingerprint is SHA256 of canonical UTF-8
JSON (sorted keys, compact separators, no trailing newline) mapping consumed
project-relative paths to their hashes: configuration, manual collection inputs,
referenced includes/bibliography, original and effective visuals, dependency
files, native locks and complete provider check inventories. Only resolved text
and registered images enter the transport archive; executable/data/check inputs
are represented by fingerprints in the producer receipt. Absent variant probes are retained in
the external producer receipt and rechecked before sealing. The package's direct
file hashes independently bind every delivered byte. Producer revision is a
code fingerprint of the package and native resolver/check scripts, not a claim
that a development build is a published release.

## Interoperability test

Core maintainers can produce retained synthetic manuals through the actual MCP:

```bash
python scripts/test_manual_context_export.py --output /absolute/unaltraweb/tmp/context-run-01
```

The script emits first/next package paths and sender hashes. Pass those exact
files to Itemarium's `tools/desktop/manual_package_conformance.py`, using an
Itemarium-capable Python and a new output directory under unaltraweb's `tmp/`.
The producer receipt proves exporter invocation; the independent consumer receipt
proves schema/closure, import, preservation and backup/reopening. Neither test
creates questions or certifies a teaching bank's quality.
