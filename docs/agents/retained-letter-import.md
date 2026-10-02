# Native retained-letter import — issue 80

Delivery completed on 2026-10-02; see [the 0.6.0 closeout](owner-closeout-80.md)
for final revisions, receipts, registry downloads and the post-release pin.
The following sections retain the chronological preparation and review evidence.

## Scope and release state

This is a separate 0.6.0 development increment after the administrative closeout
of issue 76. Gem, wheel, runtime, MCP and PDF worker are pending. The 0.5.1 release,
receipt and active checkout launcher pin remain unchanged. Consumer core/PDF
integration and publication need their own reviewed immutable selections. The
tested computation, capture and visual companion selections remain 0.4.0.

The native receiver accepts Carta 0.3.0rc1 leaf `letter-pdf-v1` units. It retains
the entire bundle, maps the original PDF byte for byte, creates a native draft
page/chapter and checks its source and rendered references. The manual PDF
builder includes all pages with `pdfpages`; every retained dependency and checker
contributes to freshness. Nothing executes the retained producer recipe.
Composite profiles, edited PDF variants and Diapora are outside this acceptance.

## Protocol and provenance

The wire v1 verifier and schema are byte-identical copies pinned to hub revision
`9167e3efb5968a64bb9100792163a179c1491860` (integration
`fc8745db950b04013c73eb49acf6781a26eb83f8`). Their respective SHA-256 values are
`48368035f242f4d4446cbbe1363f8a01a7c17fa164ffef21abadd878b288d82d` and
`b52a32b3bcfeed28cf34a9ec1557665a94466b51c451ccad47d2e87f6e23f9aa`.
No envelope fields were added. `binding.json` is a separate native record.
The integration actor identifies the importer by a hash of its code inventory,
not an invented or uncommitted Git revision.

Acceptance uses the final published
[Carta v0.3.0rc1 packet](https://github.com/dosquartsdedocs/unaltracarta/releases/tag/v0.3.0rc1),
revision `84258b6869689ea5f1a49a55abc2b865573fb512`:

| Artifact | SHA-256 |
| --- | --- |
| `distribution.json` | `9d94b918db086b445e4d8a3ece2435622e0f9f9893bcd50708b4d13f5ca0ad44` |
| `acceptance-0.3.0rc1.json` | `1bc7c467f3e35abf9fa5c27583dd8cc3ad4d4372f930c4be60ed142122158504` |
| `acceptance-0.3.0rc1.tar.gz` | `8764a717bda33e15b48b3a06fe6fbe5dc075abedf4fd52bd37fdf4ed70896179` |
| Published wheel | `0afab176ea0815d242f6e19021232bafdc63f9bb68cbacbd63b73f99b666b7c3` |
| Wheel bundle manifest | `aeaa757ee1be19bfe56dc9af8dd1178032929b4a2bec2dad2ebb621b158ad999` |
| Retained original PDF | `4a661740a18fe1cf75b84aa0d8532511fd105eb5484a5af700e11e8e30828ea4` |

The original producer job was
`.unaltracarta-handoff/jobs/a0794f7909a943eb844c87bb14002691/bundle/`.
Its renderer identity is
`sha256:ba2453fb42542433f68efd8888d628b95f256cefb9c545b3b35034d33296e340`.
The installed test authenticates the packet before bounded extraction and checks
every declared evidence file. Earlier release-candidate bytes are not inputs.

## Installed acceptance

`test/artifact_import_smoke.py` uses a wheel-installed CLI and Docker launcher,
without a host factory dependency. It creates a synthetic manual, imports the
published wheel bundle, edits surrounding prose, verifies an identical reimport
preserves that prose and removes both the extracted producer copy and incoming
copy. It then builds the web and PDF, checks the served page/PDF, moves the
receiver, runs both native and generic v1 checks, and explicitly rebuilds the
PDF in the moved receiver. Every original page must occur in order in the
composed PDF; comparison uses the original font encoding, including ligatures.

The passing local run is retained at
`/tmp/opencode/unaltraweb-import-80/installed-proof-final/evidence.json`.
Its receiver is `relocated-receiver/` in that directory. This is local owner
evidence from development images, not a signed release receipt.

| Tested identity | Value |
| --- | --- |
| Installed unaltraweb wheel SHA-256 | `407b1275d1de558da891f391454287d1b3e76fbef0e45460695e9731932b9e39` |
| Controller image ID | `sha256:81f1da616455c7378ba3400b9d638eb8e67fce9605f18353d49a796020d9b6fa` |
| PDF worker image ID | `sha256:b7b8f5b774a528cadb2ab7aa313b9ddbffa6d54c9d3b42bd6ff59a664be8ccf6` |
| Integration record SHA-256 | `79ede9c8701eedf6ca4f182dc4fd1c9df3b56581138c677e0315310d8b998d1c` |
| Composed PDF before and after relocation | `14b0ef586874704b6d1b045d6dde1f32ee08c8a9107006e06cfe2e8147f54621` |

The receiver retains all 12 seal files under
`.unaltraweb/artifacts/carta/bundle/`. Its mapping is
`payload/output/letter.pdf` → `assets/documents/carta.pdf`, with native content at
`_chapters/en/carta.md` and permalink `/en/retained/carta/` under `/letter-proof`.
The original one-page letter appears on page 10 of the 11-page composed manual.
Both web/HTTP checks passed; the non-web archive was absent from `_site`.
Generic verification after relocation passed with one bundle, one mapping and
14 verified files. Preview copies were cleaned through their exact receipts.

Intermediate failures are retained separately: missing explicit gem plugin
registration, an overly broad rendered-HTML scan, mismatched controller/worker
checker bytes, and an assertion that ignored the original PDF's ligature
encoding. Corrections preserve strict integrity/freshness gates. In particular,
the installed-image fixture force-reinstalls its supplied wheel even when its
development version equals the base image's version.

## Reproduction and boundaries

Prepare an installed wheel, the matching source-containing MCP image, and a PDF
worker built from the repository root with `scripts/manual/Dockerfile`. The test
controller in `test/artifact_import.Dockerfile` binds `MANUAL_PDF_IMAGE` to the
worker image ID. Then run:

```bash
python test/artifact_import_smoke.py \
  --packet "$PUBLISHED_CARTA_PACKET" --output "$NEW_EVIDENCE_DIRECTORY" \
  --cli "$INSTALLED/bin/unaltraweb-mcp" \
  --launcher "$INSTALLED/bin/unaltraweb-mcp-docker" \
  --image "$TEST_CONTROLLER" --pdf-image "$TEST_PDF_WORKER"
```

The output directory must not exist. Only copies created by the test are retired.
Unit-test bundles in `test/test_artifact_imports.py` are synthetic security and
transaction fixtures, not published-producer acceptance. They cover tampering,
incomplete resources, hidden references, symlinks/hardlinks, no-overwrite,
interruption/retry, generated-source ownership, PDF action aliases/chains,
rendered URL binding, native PDF inclusion and dependency closure.

The imported unit is portable because its seal, record, mapped PDF and content
all use receiver-relative paths. The integration does not depend on the incoming
directory, producer process, absolute source location or ignored recovery tree.
Failed publication retains prepared and partial files; there is no destructive
rollback. Reimport adopts only identical existing bytes and preserves authored
prose when the binding remains valid.

Final release gates must additionally bind the reviewed core/PDF consumer tuple
and same-source package/image candidates. A local acceptance run does not update
those pins, authenticate a public 0.6.0 release, authorize real-manual adoption,
or grant author approval to the draft content.

The gem and PDF worker include a regular Python package initializer and its
stdlib-only version/contract module. This prevents an unrelated installed wheel
from shadowing the gem's helpers. The extracted-gem gate asserts the actual
module paths. Checker code and schemas enter PDF freshness; the validated BOM's
worker/self pins do not, avoiding a worker that would need to contain its own
future digest. The integration actor separately hashes the full BOM metadata.

## Owner regression gates

- Python suite: 584 tests, 30 environment-dependent skips, no failures. The
  focused importer suite covers 22 cases; the PDF builder suite covers 88.
- Ruby plugin suites: 64 tests and 334 assertions, no failures.
- Actual PDF toolchain integrations: 16 tests, no failures.
- `distribution-check`, `workflow-check`, `wheel-check`, `gem-check`,
  `mcp-check`, `mcp-smoke`, `docs-build`, and fixed-epoch
  `reproducible-site-check` passed on local owner resources. Distribution remains
  structurally valid and explicitly not release-ready.
- The extracted-gem package gate exercises synthetic native retention using only
  the gem's Python helper closure, with isolated Python and no wheel/core path.
  Native deployment installs its parser dependencies before PDF/Jekyll checks.
- Populated Bundler roundtrip passed for `unaltreselfie`, `unaltreprojecte`,
  `unaltredocs` and `unaltremanual`, with two builds and a preview per runtime.
  It first reproduces the published unpatched 0.5.0 `google-protobuf (4.36.1)`
  failure on a separate copy, then tests 0.4.0 → development 0.6.0 → 0.4.0.
  The historical driver labels its patched step `fixed-050`; the recorded
  image is the 0.6.0 test controller. All six retained author/cache paths keep
  their initial hashes; no cache cleaning is used to obtain a pass.

Roundtrip evidence is retained at
`/tmp/opencode/unaltraweb-import-80/bundler-roundtrip-final/evidence.json`, using
the same final controller and worker IDs as the installed letter acceptance.
The source discovery descriptor additionally declares `.unaltraweb/artifacts`
as optional versioned source state with `cleanup: never`; `tmp` keeps its existing
ignored, explicit-cleanup policy. This final metadata-only addition is checked by
the path-policy and fresh-wheel gates and does not alter the tested import code.

## Closeout review — 2026-10-02

The owner explicitly authorized the full 0.6.0 commit/PR/integration, signed
candidate, gated publication and post-release pin flow. The session preflight
reported only the known unit-80 working tree and no competing session. Review
covered every tracked/untracked unit path; no unrelated changes were identified.

The two vendored protocol files match the exact established Git pin. The pinned
reference tests and fixture payloads were also checked (the later fixture README
only renames the integrated contract), and all 26 conformance tests pass. These
generic synthetic tests do not add a composite domain to the native importer.
The retained installed wheel/PDF hashes above and the moved receiver's native
web/PDF mapping were independently rechecked before editing.

Resolved review findings:

- Metadata could contain a local link or image while retained Pandoc evidence
  remained stale. Renderable metadata now receives the independent text-reference
  check; effective metadata rejects render-option fields outside the supported
  author/stamp projection. Malformed Pandoc link evidence returns a structured
  domain failure instead of an uncaught indexing error.
- A PDF OpenAction internal destination array was treated as an action array.
  Internal destinations are supported while chained action arrays retain their
  stricter checks. Regression tests cover both cases.
- The acceptance driver required a derived test-controller image. It now also
  verifies the immutable PDF selection declared by the actual installed MCP image
  and records the exact image references and source label, allowing signed bytes
  to be exercised directly.

The corrected source passes 587 Python tests (30 optional skips), including 25
native import cases, plus distribution/workflow/fresh-wheel gates. The historical
local evidence above remains retained; signed-candidate and public-download
acceptance must record their own revisions and hashes. The consumer core/PDF
tuple is closed only after the reviewed integrated core and signed PDF digest
exist; no guessed source or self-digest is inserted into the BOM.

## Reviewed immutable consumer tuple

PR [81](https://github.com/dosquartsdedocs/unaltraweb/pull/81) integrated reviewed
implementation `7af652fb83629e959af05c407a34a2f5a15f7936` as
`5cf9817489c8dc47cee726bfe42fe3071cd32b85`. Protected PR CI
[37027921742](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37027921742)
and CodeQL [37027922332](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37027922332)
passed, followed by integrated-source CI
[37028677932](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37028677932)
and CodeQL [37028678347](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37028678347).
The PR contains an explicit agent review, not an attributed human approval.

Signed image workflow
[37029374441](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37029374441)
then published, attested and tested the PDF from that exact source. Its read-only
test job verified the signer workflow/source digest before executing the exact
image, including 16 PDF integrations and real MCP preparation. The selected
PDF 0.6.0 identity is
`ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed`.
The BOM and Make contract now select that same digest and integrated core SHA.

That public signed PDF is recorded as `released` and reused by digest. The four
core/package components are `ready` for final same-commit candidates; their strict
gate still requires a new receipt-only child of the final artifact source.
Subsequent verification-only PDF builds are not substituted for this selected
worker or promoted under an assumed identity. The earlier 0.5.1 receipt and
active launcher pin remain intact until the authorized 0.6.0 closeout completes.

The tuple was exercised before its pin PR using an installed wheel and a local
MCP containing the new BOM with the actual signed PDF above. Evidence is retained
at `/tmp/opencode/unaltraweb-closeout-060/tuple-letter-proof/evidence.json`:
integration `ebe07ee10ad740a2bbbd36d532f336374cf4bb19ccb373b6590b2279f664a222`,
composed PDF `416e96f66bb6608b1e20bf5e36b6b16133bd4018c17e6c079e8987b736fe9cae`
both before and after the forced relocated rebuild. The PDF's inspected local
image ID is `sha256:d7e7d3243616270fc9e6eed7f8238c412dbe3d9ffc18d2832d17d66ca630d139`,
with the exact integrated source revision label. This preparation proof does not
substitute for the final signed MCP and downloaded package acceptance.
