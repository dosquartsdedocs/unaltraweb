# WEB-B — practice requirements reconciled with c87ac4f4

This is a technical adoption map, not approval or publication of teaching copy.
The authoritative source baseline is `c87ac4f4f6e299c3846ae0bd5cd17ca1b981b420`.
No consumer checkout, retained dataset, manual, client configuration, runtime pin,
or private provider was edited during this audit.

## Evidence inspected

- [Web #98](https://github.com/dosquartsdedocs/unaltraweb/issues/98), including
  [6155003975](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6155003975),
  [6155247851](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6155247851),
  and [6178087168](https://github.com/dosquartsdedocs/unaltraweb/issues/98#issuecomment-6178087168).
- [TIGIT #14](https://github.com/geourv/tigit/issues/14), latest owner delivery
  report [6277044214](https://github.com/geourv/tigit/issues/14#issuecomment-6277044214).
  Read-only remote revision `7a8b314d743b62699232c66d7024387f86f59281`:
  `context/practice-migration.md` and
  `practiques/tigit-projecte-territorial/recursos.yml`.
- [Geodisseny #9](https://github.com/geourv/geodisseny/issues/9), read-only remote
  revision `10990377aa9ac5983af0f92055debfd73a4e5456`:
  `context/practice-tools-handoff.md` and
  `practiques/accessibilitat-vilaseca/recursos.yml`.
- TIG read-only remote revision `c045d46a8e7139adf9f060eeeaf4e47781dfd355`:
  `context/practice-tools-handoff.md` and `context/practice-retention.json`.
- Current `practice_pdf.py`, `practice_editions.py`, edition v1 schema,
  `editorial_sources.py`, source-CI, reusable deploy/release workflows, package
  scaffolds, native verifier descriptor, and the pertinent Python/protocol tests.

The older handoffs describe rc/candidate processes and earlier selections. They
are retained evidence, not the currently published Web release or a new QGIS
admission. This change preserves the baseline's independently selected private
QGIS 0.6.1 verifier and accepted `qgis-practice-v1` / `qgis-practice-v2` profiles;
the QGIS development refactor is not adopted as a runtime.

## Requirement map

| Demand | Baseline finding | This unit / remaining owner work |
| --- | --- | --- |
| TIGIT's ignored inputs must exist before Quarto/Vega/PDF freshness. | `build-command` still runs after those gates. No early preparation interface exists. | New explicit hash-bound `prepare-inputs` + `prepare-inputs-sha256` deploy pair, and underscored equivalents for stable release. Provider-owned hydration runs before gates, never instead of them. |
| Reconstruct data outside Git, preserving pinned provenance. | TIGIT already has a tested preparer and an immutable manifest: 21 files, 7,759,191 bytes, historical commit `715944fc…`. Its 13 transitional inputs feed 23 Quarto sources and one Vega source, producing 33 figures. | The `immutable-github-files-v1` adapter reuses that inventory shape and reads its exact bytes via an explicitly hash-pinned top-level plan. No copy of the preparer or statistical/GIS/workbook execution is added. Owners still select the exact input subset/snapshot, update sources and regenerate their own locks/receipts before retiring the 13 inputs/initial ZIP. |
| Tabular editions without a fake GIS descriptor. | Edition v1 still requires `gis`; `resources` only covers explicit editable-SVG closure. Existing standalone PDFs and arbitrary ZIP helpers do not provide a tabular composition contract. | Additional explicit edition **v2 `mode: tabular`**, with file ID/path/destination/hash/size/role/recipient selection. Reuses native approved-reading/PDF seals, ZIP copy/verification and no-clobber delivery. No QGIS or workbook calculation. GIS v1 schema is unchanged. |
| Sources at `practiques/<slug>/`, ignored retained work and deliveries. | Implemented, including exact path policies, Git checks, Jekyll exclusions and no-clobber PDF/edition installation. Legacy mapped `_practices` readings remain supported. | Preserve these boundaries; add a project-owned input plan and explicit local preparation facade. No directory migration or cleanup in consumers. |
| CA/ES/EN reading basenames and recipient-specific sources. | Already `ca/LLEGIU-ME`, `es/LEEME`, `en/README` beneath `alumnat` / `docent`, with canonical validation and explicit legacy mappings. | Retained, with CA/ES/EN fixtures for v2 composition and paired PDF/ZIP contents. No new audience or language naming convention. |
| Geodisseny initially requested `GUIA.pdf`. | The later common #98 contract and existing author sources use `LLEGIU-ME.md/.pdf`, with Spanish/English equivalents. | Keep the later accepted common convention; do not introduce an unversioned `GUIA.pdf` alias or rename authored files. Any additional human delivery alias is an owner selection, not a core rewrite. |
| #98's early examples named outer `alumnat.zip` and `docent.zip`. | The shipped composer retains `<slug>[-docent]-<version>-<lang>.pdf/.zip`; each ZIP contains the language-specific reading basename. | Preserve the shipped versioned outer names and independent byte-identical PDF, under `dist/practiques/<slug>/<version>/<lang>/`, with external receipts. No flat latest-only replacement. |
| Separate initial student materials from resolved teacher material. | GIS closure enforces producer roles; current TIGIT owner also explicitly wants selected resolved workbooks as labelled student demonstrations. | V2 rejects `resolved-workbook` for students; `demonstration-workbook` requires a separate explicit owner selection/recipient label. Byte checking does not assert that workbook contents are pedagogically appropriate or semantically valid. |
| Geodisseny: initial/teacher portable GIS, captures, fonts and sidecars. | Producer v1/v2 closure, SVG dependencies, original PDF seals, recipient bindings and native profile identity already exist. The provenance manifest still contains live/statistical URLs without a complete immutable hash/size inventory. | No GIS/schema/provider reimplementation. Owners must qualify original/normalised bytes, full producer closure and extracted-packet reopening. The new fetch profile must not pretend that a WMS/live URL is an immutable snapshot. |
| TIG: ignored input, initial/resolved project closure and font. | Retention index names a hash-bound local input and complete historic native bundle. Handoff reports missing final practice editions/approval at that observation. | Keep exact local bytes, native check/reopen and explicit reading bindings. No new data generation, reinterpretation of a historic candidate, or automatic final edition. |
| Source-CI must stay source-only. | Current conservation/prose policy intentionally does not acquire datasets or render. | Unchanged source-CI workflow; regression asserts it never calls the new preparation path. Explicit local/deploy hydration is a different operation. |

## Adoption contract

The public API is `unaltraweb_mcp.input_preparation.prepare(project, config,
sha256, allow_fetch=False, check_only=False)` and installed
`unaltraweb-prepare-inputs`. The optional plan uses
`input-preparation-v1.schema.json`; `web://input-preparation-schema` exposes those
exact package bytes. Empty plans are no-ops. The only acquisition profile accepts
public GitHub raw files bound to a full commit, exact prefix, per-file SHA and
size. It refuses redirects, moving refs, commands, symlinks, missing exclusions,
unignored/versioned outputs, changed snapshots and changed control hashes. Failed
attempts remain retained; successful bytes are independently read back. Existing
identical snapshots can be checked/reused without rewriting consumer receipts.

`web://practice-edition-schema` remains the original GIS v1 schema;
`web://practice-tabular-edition-schema` exposes the additional v2 schema. The
existing `manual_practice_compose` API/CLI accepts either version explicitly.
No extra runtime profile is silently inferred. Returned tabular verification
states its actual byte/size/recipient scope rather than attributing a GIS seal.

Consumers must explicitly adopt reviewed source/workflow/runtime revisions that
contain these APIs, reconcile local scaffold edits, bind their approved manifests,
and verify a clean checkout hydration followed by native freshness/PDF/build
checks. For the shared workflow helper, the defining immutable provider revision
is checked out, so an older consumer gem cannot supply a substitute preparer.
The generated local Docker facade requires an independently approved updated image;
its currently accepted pin is not advanced here. Reconnection and helper pin
selection remain owner/coordinator work.

## Verification and qualification limits

Synthetic tests cover immutable-input hydration/readback/reuse, source/config
hashes, absent/corrupt/denied inputs, retained partial attempts, path/Git/Jekyll
boundaries, and no consumer-code execution. CA/ES/EN composition fixtures exercise
real ZIP/PDF copying and receipts with a synthetic native-PDF build boundary.
Existing GIS/profile, private-resource, original-seal and protocol tests remain.
Local tests do not claim real statistical acquisition, workbook calculation,
private GIS verification/reopening, teaching review, or Moodle/Pages publication.
Those are exact pending qualification gates, not bypassed checkers.
