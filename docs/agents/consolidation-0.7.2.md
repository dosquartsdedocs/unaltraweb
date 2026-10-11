# Web #98 / gaContExt #32 — 0.7.2 source checkpoint

This is a draft consolidation, not a published release or an installed 0.7.2
cohort. It includes private reading/PDF composition, portable bindings and author
resources, independent PDF/ZIP delivery, the host reaper correction, the shared
source-CI control, and preparation of runtime archives for the existing hub loader.
Earlier candidate reports describe their historical checkpoints; their source
snapshots, images, wheels, receipts and retained evidence remain unchanged.

**Current private-runtime decision:** QGIS 0.6.0 is released but private. The earlier
wheel-install plan below is superseded by [native private-runtime delegation](private-practice-verifier-98.md).
Public Web builds now contain only the Web bridge/metadata; the hub prepares the
private QGIS controller. No published/private wheel is downloaded into Web.
The three independent review P2 findings are reproduced and corrected in this
source delta; a new source review and independent runtime check are still required
on its committed HEAD. The H2 contract declares the private producer's hash-bound
`release.json` externally; public runtime archives contain only Web-only and PDF
images. Local acceptance and the external receipt are documented in the linked
bridge and archive contracts.

## Blockers recorded at the original draft checkpoint

The first two entries describe the superseded installer plan at `88dd2518`, not
current requirements to make QGIS public or embed its wheel:

- The final **published QGIS wheel URL and SHA-256 are still missing**. The owner
  reports prepared source `a660dfa54ea6bc6cf5d3d3fbeb12593f62c726e1` and wheel
  `dde653f7a719d8dbb20b4471e3cdb7f9c99cbdfcb116647caba5a08e710c7b76`
  pending re-review. This is not an accepted published pin and is not installed
  or inserted into the BOM by this checkpoint.
- `Dockerfile.mcp` deliberately refuses its verifier installation until that
  released owner component is declared. Docker CI may stop at this gate; no
  check, job or refusal is disabled to manufacture a green result.
- Select the new permanent reviewed core commit after integration. The current
  `consumer_integration.core_sha` remains the previous reviewed `3332e0b…`
  point during this draft, not a claim that it already contains the new tools.
- Final same-source package/image candidates, their acceptance and a new
  receipt-only release checkpoint remain pending. `release-candidates.json`
  still belongs to published 0.7.1 and is not a 0.7.2 authorization.

The coordinated gem/wheel/runtime/MCP declarations now name **0.7.2**. Nothing
re-emits 0.7.1 with new bytes. The checkout launcher and source-checker lane keep
their previously published MCP digest until a new published digest is reviewed.

## Preserved tuple

- Workflow: `3332e0b93933f12317e05f1ce8d38ce80046feab`.
- PDF 0.7.1:
  `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b`.
- Actual PDF producer: `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1`.
- PDF configuration ID:
  `sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa`.
- All nine retained-document checkers remain byte-identical to the reviewed
  core/PDF point. Diavisuals/Vega compatibility is not widened.

## Reproducibility and retained evidence

The publishable wheel carries the source-CI runner, policy schema, common workflow
template and native private-runtime bridge/descriptor. The normal MCP image runs
the factory-owned compositor/scripts and delegates verification to the prepared
private QGIS controller. Neither public entrypoint requires consumers to copy
generic code or inspect a mutable provider checkout.

`prepare_practice_candidate.py`, `prepare_practice_editions_candidate.py` and
their pinned rc fixture defaults are historical acceptance/preparation tools.
They do not replace the normal release pipeline, and their old local candidates
must not be regenerated or relabelled as the final release. Archived source and
image hashes identify those exact historical bytes.

Source-CI/composition tests and synthetic fixture recipes are versioned here.
Datasets, rendered PDFs/ZIPs, Docker-save archives and retained job outputs stay
outside Git. Detailed evidence and transfer hashes are recorded in:

- [Practice editions and bindings](practice-editions-98.md).
- [Runtime archives and independent PDF producer identity](practice-runtime-archives-98.md).
- [Shared public-source CI](source-ci-98.md).
- [Installable practice-PDF acceptance](practice-pdf-installable-98.md).

The source validation before this version declaration passed 706 tests
(679 passed / 27 optional skips), fresh-wheel installation, source/workflow
checks and native bounded source-checker execution. After declaring 0.7.2,
the suite passes 706 cases (678 passed / 28 skips): the additional skipped
Docker mount-parser test requires the not-yet-prepared 0.7.2 MCP image. It was
not redirected to an older image to claim a new-runtime pass. A fresh 0.7.2 wheel
build/install and distribution/workflow/whitespace checks passed at that original
checkpoint; its publication readiness was false because the QGIS pin was absent.

The later private-runtime/P2 checkpoint passes **720 tests (692 passed / 28
skips)** and fresh-wheel installation. Native local evidence verifies Web package
absence, v1/v2 delegation, sealed PDF/ZIP pairs, selected-resource-only engine
mounts and exact teardown. Distribution metadata is now structurally ready while
private checks remain explicitly `not_run` in public CI. The final source's hosted
CI and independent re-review are tracked on PR #104; local evidence is not
relabeled as those gates. The receipt-only H2 addition leaves executable bytes and
selected image/schema identities unchanged, so retained native renders are reused.
None of this publishes or approves the manuals' draft teaching content. W1 draft
PR #103 is outside this consolidation.
