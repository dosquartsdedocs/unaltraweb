# Web #98 / gaContExt #32 — 0.7.2 source checkpoint

This is a draft consolidation, not a published release or an installed 0.7.2
cohort. It includes private reading/PDF composition, portable bindings and author
resources, independent PDF/ZIP delivery, the host reaper correction, the shared
source-CI control, and preparation of runtime archives for the existing hub loader.
Earlier candidate reports describe their historical checkpoints; their source
snapshots, images, wheels, receipts and retained evidence remain unchanged.

## Publication blockers

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

The publishable wheel carries the source-CI runner, policy schema and common
workflow template. The normal MCP image installs the released QGIS verifier from
the BOM and runs the factory-owned compositor/scripts. Neither public entrypoint
requires consumers to copy generic code or inspect a mutable provider checkout.

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
build/install and distribution/workflow/whitespace checks pass; publication
readiness remains false because the QGIS pin is absent. Hosted CI status is
recorded in the draft PR. None of this publishes or approves the manuals' draft
teaching content. W1 draft PR #103 is outside this consolidation.
