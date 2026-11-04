# #121 — review after real-manual pilots, 2026-11-04

## Findings and implementation order

1. **P1, producer defect:** declared computation inputs are incorrectly subjected
   to the public-content root allowlist. This is the first reported TIGIT blocker
   and is reproduced against the published 0.8.0 image, independently of missing
   data, stale output, receiver behavior or an old client connection.
2. **P2, producer defect:** HTML image metadata containing inline code retains
   internal protection tokens in the manifest. This was found by the review's
   synthetic component probe; it is not claimed as a reported TIGIT error.
3. **Coordinated compatibility extension:** SVG embedded rasters are refused by
   both released Web 0.8.0 and Itemarium 0.6.2. Widening Web alone cannot deliver
   a consumable package. Agree a bounded profile/version and update both owners.
4. **Producer provenance extension:** recognizable QGIS capture provenance has
   no context exporter adapter. This is distinct from SVG raster compatibility;
   even a standalone vector SVG can hit this producer gate.

The immediate useful Web increment is **1 + 2**, with the unchanged v1 transport
and an explicit new release/adoption. Then the TIGIT owner reruns the selected
chapter. There is no evidence yet that general Liquid execution or QGIS/raster
support is necessary for that particular chapter to pass its next gate.

This is a review with executable reproductions, not a runtime repair or a new
release. Production modules, schema and pins remain unchanged. The experimental
#116 checkpoint remains `6a8cd85ff75c8ad41dc67f8fb1c3c5a8f8919e53` on
`feat/116-common-practice-sdk`; none of it is used here.

## State: publication, admission and the actual caller

- Web 0.8.0 is published; artifact source
  `54afe7588c36e959a7eb75d5f52763a7456108d7`, controller config ID
  `sha256:e0502369c85c59f9e512fbd9fdb17dbc128845d057a1423375425e68ce2e79a2`,
  OCI digest `sha256:8b41abacad9ca2894755db7f3587a6b47c8fa8f536d88a151bdfc4ae53ba7f08`.
- [gaContExt PR55](https://github.com/dosquartsdedocs/gacontext/pull/55) is integrated
  at `ccbe1610f975faee913044c47b567cfe5b856cc0`. Configured controls are
  `c6b5ab73abc399d47489c199e9b91628254b84868674712a21acf0db42e9d768`.
  Web 0.8.0 and Itemarium 0.6.2 are prepared/enrolled. Managed export/import,
  version preservation and backup/reopening pass. See the
  [hub return](https://github.com/dosquartsdedocs/gacontext/issues/54#issuecomment-6615276920).
- The final fresh readonly TIGIT OpenCode status confirms **revision 5 / Web
  0.8.0**, with matching configuration, deployment `272e7dce…` and the enrolled
  controller above. Its older live connection `4ac20e8829224276a8765beefc71b559`
  still loads **0.7.4**. The initial observation in this review returned the
  preceding revision-4 state; it is superseded by this reobservation and the
  [TIGIT #27 return](https://github.com/geourv/tigit/issues/27#issuecomment-6625078407).
- TIGIT's owner explicitly activated the new point and invoked a bounded managed
  connection with loaded/current 0.8.0, no drift, correct binding and 65 tools.
  Its complete-Catalan export hits the same private-input error, creates no
  package/receipt, then drains/exits and leaves its exact controller absent.
  Restarting the older connection does not repair this confirmed 0.8.0 defect.
- TIGIT's local `_config.yml` already contains `unaltraweb.manual.id: tigit`.
  The old missing-ID diagnosis is obsolete for that inspected working copy.
- Itemarium's 2026-11-04 report observes native **0.6.2 / 63 tools**, unchanged
  frozen bytes, and a separate Web 0.7.4 connection bound to Itemarium. Its actual
  real-manual CLI probe explicitly uses the published 0.8.0 image in a readonly,
  network-disabled mount. It creates no real manual package.

Owner input: `itemarium/docs/handoffs/2026-11-04-manual-adoption-readiness.ca.md`,
SHA256 `1a9438e6c2f412200006f9769069e98fa42d76c101a3556b154dbc6ca6d4195c`;
retained pilot `tmp/manual-readiness-20261104/receipt.json`, SHA256
`551c372cfd0576d1ee71cbb2be0b6f614d4fc783ecc474c06c783822f20d24d2`.
These were inspected read-only while the receiver owner retained its working
changes. No teacher-bank contents were needed for this review.

## P1 — separate check-only dependencies from transported public content

The owner reports identical exit-1 failures for the whole manual and
`--chapter manual-territorial-indicators`:

```text
UW-MANUAL-CONTEXT
Resource is outside the public manual source roots:
_practices/tigit-projecte-territorial/data/processed/tarragones-boundaries-icgc-20260120.gpkg
```

The declaration is present in
`assets/quarto/cartographic-language/minimum-mapping-unit-tarragones.qmd`, lines
13–19. It is a computation input; the declared published output is an SVG under
`assets/img/`. The call chain is
`Sources._computations → dependency → Snapshot.public`, at
[`manual_context_sources.py:40–47`](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.8.0/src/unaltraweb_mcp/manual_context_sources.py#L40-L47).
`Snapshot.public` is appropriate for content entering the transport but rejects
this check-only dependency before native freshness verification.
The TIGIT owner also confirms an existing regular GPKG of **598016 bytes**, below
the exporter's current 10 MiB per-file reader limit. The observed blocker is its
root/role policy, not that size limit.

Published-image reproductions:

- `public-input`: a synthetic declared input under `assets/data/` passes the
  native computation status and actual export. The input itself is absent from
  the transport; only the effective section and SVG are declared.
- `private-input`: the same opaque bytes and valid synthetic native record under
  `_practices/fixture/data/` pass native `status` (`current_count:1`, `ok:true`),
  then fail in the exporter with the reported root error. The file exists; no
  missing-file or GIS-format failure is inferred. No computation is executed.
- `private-input-other-chapter`: the same refusal occurs when selecting a chapter
  that does not reference the computation. This confirms the existing global
  completeness gate, rather than an ineffective chapter selector.
- `changed-public-input` gives `source_or_environment_changed`; `missing-figure`
  gives `Missing editorial input`. These are distinct local-source conditions.
- `private-image` is correctly refused. Adding `_practices` indiscriminately to
  `public_roots` would weaken this required transport boundary.

### Concrete repair and tests

Introduce a separate bounded dependency-read/snapshot path for **explicit native
input declarations**. Keep public-source/image selection on `Snapshot.public`.
Use the existing descriptor-relative reader, literal project-relative validation,
no-follow rules and before/after rechecks. Permit verification of the declared
private input without discovering/copying an entire private repository or sending
its content. Keep native global completeness and fingerprint checks intact.

The two roles must remain separate throughout the snapshot, input fingerprint,
resolution evidence and final transport inventory. Required regression cases:

1. An unchanged declared `_practices/...` input passes native checking/export;
   only selected sections and effective figures appear in the tar and `files`.
2. Sentinel private data, private paths and executable source bytes do not leak
   into transported Markdown/figures/manifest. A private path may remain in the
   producer's external retained check receipt, not the content package.
3. Changed/missing inputs, modified outputs and stale records still fail;
   chapter selection cannot bypass the global check.
4. Traversal, symlinks, undeclared/private image or include references and source
   changes during export still fail before a sealed delivery.
5. Dependency byte budgets remain explicit and bounded. If a real declared input
   exceeds the current reader budget, assess a bounded streaming snapshot/hash
   path separately; do not silently increase the image/text transport limits.

No v1 schema extension is needed for this role correction. Moving the GPKG into
public assets, removing its declaration, skipping global checks or hand-authoring
a package in Itemarium are not a verification of the repair.

## P2 — restore HTML figure metadata before registration

Input used in `html-caption-code`:

```html
<img src="assets/img/plain.svg" alt="Alt `code`" title="Caption `literal`">
```

The real published exporter succeeds but records:

```json
{"alt":"Alt UNALTRAWEBEXPORTPROTECTED0TOKEN",
 "caption":"Caption UNALTRAWEBEXPORTPROTECTED1TOKEN"}
```

[`Projection.text`](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.8.0/src/unaltraweb_mcp/manual_context.py#L261-L326)
restores protected Markdown-image attributes before `figure()`, but
[`html_images`](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.8.0/src/unaltraweb_mcp/manual_context.py#L328-L351)
registers HTML attributes while they still contain placeholders. The final text
restoration does not repair the previously registered manifest or figure ID.

The actual produced package SHA is
`53d065605af60cd90f73553b3c7004a52c6fa6e74ec4a0f88336f879f161296a`.
Itemarium's independent package checker accepts it: byte integrity is correct,
but `caption_preserved:false` exposes the semantic error. This is a producer
fidelity defect, not a malformed source or a receiver checksum failure.

Restore `alt`, caption/title and credits before calculating the registration ID
and storing metadata, or replace placeholder-based attribute handling with a
token-aware path. Add assertions for exact HTML/Markdown metadata parity, quoted
and escaped attributes, inline code in credits, absence of internal markers and
stable figure identity when unrelated code appears earlier in the text.

## Components and Liquid: supported subset versus missing functionality

The `components` case combines a literal include, definitions, a localized
callout, a citation, table, subfigures and `site.baseurl`. Its actual archive is
accepted independently by Itemarium. These are the same principal source forms
observed in TIGIT chapter 2; this does not prove the complete real chapter exports.

`{{ page.title }}` and a parameterized include are refused with the documented
Liquid/include diagnostics. No real pilot return inspected here reaches one of
those errors. They are explicit unsupported producer forms, not evidence that
all Liquid/components fail or that an old client explains the private-input error.

If the subsequent pilot needs another form, record its exact source fragment and
add a deliberately bounded resolver case with source/resource closure and literal
code protection. Do not replace export with unrestricted Jekyll/Liquid execution.
Diagnostics should identify the rejected form and source location distinctly
from a missing include or a stale resource.

## SVG with raster: coordinate producer and receiver policy

`embedded-raster` contains a valid, small PNG embedded as
`<image href="data:image/png;base64,...">` in a standalone SVG. Web rejects it at
`manual_context_media.validate_image`; Itemarium's existing `app.media.read_image`
independently rejects the **same image bytes**, before any package import.
The external-URL raster control is also refused. No alternative transport archive
is fabricated for these checks; they are image-member validator probes only.

Required coordinated work, if the pilot needs these effective figures:

- Agree the compatibility profile/version rather than silently widening v1 or
  adding unrecognized manifest fields. The admitted Itemarium 0.6.2 point rejects
  the current payload even if only Web's allowlist is changed.
- Permit only agreed raster MIME types, verified base64/decoded bytes, dimensions,
  pixel/byte/element budgets and safe image decoding. Preserve XML/DTD/entity,
  active-content and external-network/resource refusals.
- Preserve the selected edited SVG and bind the delivered effective bytes to new
  resolution evidence. Never substitute the original screenshot or rasterize as
  an implicit export side effect.
- Test valid embedded PNG/JPEG, oversized/malformed data, nested SVG data URLs,
  external href/CSS and actual exported-package checking/import/backup in the new
  receiver. New installed bytes need their own release/admission evidence.

## QGIS provenance: a separate gate

`qgis-vector` has only safe vector geometry/text plus synthetic QGIS metadata:
Itemarium's image validator accepts the SVG, but Web refuses missing QGIS capture
provenance. Thus adding raster support alone does not solve this gate.

`qgis-untyped` supplies ordinary static vector bytes with a QGIS-related alt label.
It exports as `resolution.kind: static`. That is not proof of a fresh QGIS output:
the current byte-token/path heuristic is a refusal hint, not a provenance adapter.
Removing metadata to force static treatment is not an acceptable adoption route.

Implement an explicit mapping from a declared QGIS output to an independently
verified producer bundle/receipt, selected original/edited output and complete
required resource closure. Verify hashes, native producer/profile identity and
freshness; bind new evidence to the exact effective bytes. Reject missing/tampered
receipts, stale edits, incomplete resources and mismatched outputs. Exercise native
QGIS verification through an agreed existing interface; do not embed the private
QGIS implementation in Web or trust a caller's success boolean.

The schema already names `qgis-capture`, but no record dispatch in 0.8.0 produces
that verified kind. Pin/qualify the actual classic capture profile separately;
this review does not adopt the #116 shared-job checkpoint or a different QGIS
practice tuple. After provenance works, the effective SVG must still satisfy the
negotiated receiver image policy.

## Reproduction and evidence

Versioned runner: `scripts/review_manual_context_pilots.py`. It requires the two
already-prepared published controller IDs (0.8.0 and 0.7.4), never pulls, and uses
network-disabled/read-only-root containers with no Docker socket and only new
synthetic fixture inputs. The 0.7.4 control rejects the unknown CLI command with
exit 2; this is distinct from the published 0.8.0 content error (exit 1).

```bash
python scripts/review_manual_context_pilots.py \
  --output /absolute/unaltraweb/tmp/context-pilot-review-new \
  --receiver-python /absolute/prepared-python/bin/python \
  --receiver-source /home/benizar/git/itemarium/tools/itemarium
```

The receiver flags are paired and optional. The receiver source is read-only,
bytecode writes are disabled, and its before/after engine fingerprint is checked.
Only archives actually produced by the published exporter reach `check_package`.
There is no app/bank creation or question generation in this review.

Completed run: `tmp/manual-context-pilot-review-20261104-02/`:

- 16 producer scenarios, five actual archives independently accepted by the
  receiver; expected refusals remain failures in the retained domain responses.
- Producer identity `sha256:a678d2b2649e3479d0049ca0ca8a500aba5bb3f0a59b070cd7aaf5c0c6b466d0`.
- `producer-review.json` SHA256
  `3a33b4b844bbc6e41419f420146d45e96b963bede0f04ae1e690c1a09dc25d69`.
- `receiver-review.json` SHA256
  `2c6944d9778e317dda5c0f6dfaf74cda5d7a339e7ad61dfb20f3012df071f521`.
- Receiver source checker: 0.6.2, engine SHA256
  `1a8983100c4b0c72bac74912fdde7a4d8ad14ce9970e188f13aae611dbeee813`.
- Original fixture sources remain unchanged during export, and exact review
  container absence is checked with a responsive Docker daemon.
- The initial `-01` attempt failed in the review harness's root-mounted script
  path calculation before exporter execution. It is retained, corrected in the
  harness and not misclassified as a product failure.
- Full existing suite: 763 cases, 736 passed, 27 skips; `git diff --check` passes.

No live consumer activation, real-manual export, publication or runtime/schema
patch is performed here. TIGIT owns its local sources/adoption and the next real
chapter export; Web owns the two identified producer repairs and coordinated
format/provenance extensions; Itemarium owns receiver changes and eventual
explicit import with bank preservation.
