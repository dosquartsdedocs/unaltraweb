---
title: Retained paired-output private intake
description: Read-only admission planning and byte-preserving private snapshots of existing paired practice handoffs.
lang: en
ref: retained_private_intake
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 690
permalink: /retained-private-intake/
---

## Private archive first

This producer-owned local interface admits a bounded, explicitly selected
**retained paired-output handoff** for private archival storage. It preserves the
actual editorial state, including `human_approved:false` or unknown approval.
It supplies neither a new scientific/native certificate nor public/Moodle/author
approval. Planning and snapshotting perform no network, credential, transport,
rendering, runtime selection, catalogue or link operation.

It complements the native versioned edition workflow. An original project-local
`manifest.json` is retained as original evidence, never relabelled as
`unaltraweb-practice-edition-receipt`. One current handoff is selected at a time;
the API does not snapshot a whole course or export source trees.

## Explicit request v1

Version a project-owned request, for example `.unaltraweb/retained-intake.json`.
The public wheel packages `retained-private-intake-v1.schema.json`; MCP discovery
exposes the same bytes through `web://retained-private-intake-schema`.

```json
{
  "kind": "unaltraweb.retained-private-intake",
  "schema_version": 1,
  "purpose": "private-archive",
  "consumer_repository": {
    "remote": "origin",
    "host": "github.com",
    "repository": "example/manual"
  },
  "handoff": {
    "slug": "retained-handoff",
    "activity": "different-activity",
    "language": "ca",
    "manifest": {
      "path": "dist/practiques/retained-handoff/ca/manifest.json",
      "sha256": "<exact original manifest SHA-256>",
      "bytes": 1234
    }
  },
  "snapshot": "sandbox/retained-handoffs/retained-handoff/pilot-1",
  "packages": [{
    "recipient": "alumnat",
    "archive": {
      "path": "dist/practiques/retained-handoff/ca/retained-handoff.zip",
      "sha256": "<exact original ZIP SHA-256>",
      "bytes": 1234
    },
    "pdf": {
      "path": "dist/practiques/retained-handoff/ca/LLEGIU-ME.pdf",
      "sha256": "<exact original PDF SHA-256>",
      "bytes": 1234
    },
    "pdf_receipt": {
      "path": "<exact retained PDF worker receipt path>",
      "sha256": "<exact original worker receipt SHA-256>",
      "bytes": 1234
    },
    "pdf_artifact": "<exact outputs/...pdf key in worker artifacts>",
    "reading_member": "<exact PDF member name in the original ZIP>",
    "selected": [{"id": "student-guide", "format": "pdf"}]
  }],
  "evidence": [],
  "sources": []
}
```

Replace every example pin/count/path with independently inspected exact values.
The handoff slug and manifest activity are separate identities: declare both,
even when they differ. Language, original version/run, recipient and output
selection are not inferred from filenames. The original flat source layout
`dist/practiques/<handoff-slug>/<language>/` keeps its filenames and internal ZIP
roots; no version folder or renamed deliverable is imposed on it.

Each package explicitly selects its original ZIP, standalone PDF, worker receipt,
worker PDF artifact key and ZIP reading member. The original manifest's recipient,
archive SHA, reading source/hash and worker-receipt path/hash must agree. The
PDF's exact hash must match both the ZIP reading member declaration and the
original `private-practice-pdf` schema-1 artifact seal. Select PDF and/or ZIP with
independent IDs. `docent` remains teacher/private; role conflicts and duplicate
IDs/formats/paths are refused.

`evidence` contains explicitly pinned local files with role `proof`,
`current-handoff` or `checksums` and a `file:{path,sha256,bytes}` pin. JSON metadata
may be selected from retained `sandbox/`, `tmp/`, `context/` or practice deliveries;
checksums belong to the selected original handoff. These finite local copies are
not a source export. Stronger current-handoff records/proofs stay separately
selected; they do not silently replace an inherited manifest reference.

`sources` contains optional explicit bounded reading-Markdown pins, never copied
into the snapshot or remote product. A selected source must match a declared
reading hash; exact original-path matches are labelled fresh. Unselected or
historically relocated source references remain inherited rather than guessed.
Hash-only/missing old proof paths remain unresolved in the new receipt. A missing
`sealed.json` is not fabricated or required as an invented dependency.

## Read-only plan, then explicit admission

```bash
unaltraweb-retained-intake plan \
  --project /absolute/manual \
  --request .unaltraweb/retained-intake.json \
  --sha256 REVIEWED_REQUEST_SHA256

unaltraweb-retained-intake snapshot \
  --project /absolute/manual \
  --request .unaltraweb/retained-intake.json \
  --sha256 REVIEWED_REQUEST_SHA256 \
  --expected-plan-sha256 REVIEWED_PLAN_SHA256
```

From this core source use `PYTHONPATH=src python3 -m
unaltraweb_mcp.retained_intake`. Python APIs are `plan(project, request, sha256)`
and `snapshot(project, request, sha256, expected_plan_sha256)`; the public wheel
works without a private hub, MEGA account or companion renderer.

The stable plan digest binds the exact request, native-Git-verified consumer
repository, site privacy controls, source/output/evidence pins, explicit selected
outputs, snapshot destination and producer code identity. No inode/timestamp or
random destination is substituted into the review identity. A changed request,
source, evidence, file, role or implementation requires a new review digest.

Fresh checks cover original compressed-byte hashes/sizes, bounded complete ZIP
file-member inventories/content hashes/CRC, the selected PDF header/worker hash,
and selected original worker/source references. ZIPs are read without extraction;
unsafe paths, aliases, links, duplicates, encryption, unsupported compression or
byte limits fail. An untrusted ZIP's single-disk non-ZIP64 end record bounds its
entry count and 16-MiB central-directory allocation before parsing; unsupported
containers fail without rewriting them. This adds fresh byte checks beyond a prior central-directory
inventory, **not** a GIS/native/scientific rerun. PDF structure/semantics and
renderer/effective-source/factory provenance remain inherited, not recertified.

Current bounds are one handoff, up to two recipients/four selected outputs,
512 MiB per input and the existing 2-GiB aggregate workspace/expanded-ZIP budgets.
Selected JSON/checksum evidence is at most 1 MiB/file and 16 MiB per snapshot;
optional reading-source pins are at most 2 MiB each. Unsupported old inputs are
reported; the planner never normalises or repackages them to pass.

The separately explicit snapshot rechecks the expected digest and unchanged
inputs, streams only selected PDF/ZIP bytes plus bounded necessary local request/
manifest/worker/evidence copies, and installs a new private ignored directory
atomically without replacement. Original files/receipts/sources are not moved,
renamed or rewritten. Partial failed candidates are retained for inspection.
The `sandbox/retained-handoffs` policy is ignored/explicit-retention, not cleanup
permission; request creation and consumer/scaffold/runtime migration are separate.

## New honest private receipts

`admission.json` is a new
`unaltraweb-retained-private-handoff-admission` v1 record containing the reviewed
plan, original identities and pinned local lineage. Each selected output gets a
new `receipts/<id>.json` of kind
`unaltraweb-retained-private-artifact-receipt` v1, bound to that admission hash.
These receipts identify the new private byte/provenance admission, not an
approved native teaching edition.

The new records preserve false/unknown editorial values, local-candidate and
historical-bundle declarations with their original origin. Fresh byte/reference
checks are distinguished from inherited renderer/effective-source/factory/proof
claims; source/evidence hashes and unresolved references stay local. Snapshotting
grants no author/scientific approval and selects no runtime or cloud credentials.

## Existing per-artifact private archive

Use the returned **per-output receipt path/SHA** in the existing route-v2
configuration, with its explicit format and recipient audience. The retained
class requires `driver:s3`, `visibility:private` and
`storage_profile:authenticated-private-v1`; student output is student/private,
teacher output teacher/private. GitHub/public or audience laundering is refused,
even if the original manifest declared human approval.

```json
{
  "target": "manual-private",
  "storage_profile": "authenticated-private-v1",
  "audience": "student",
  "receipt": "sandbox/retained-handoffs/retained-handoff/pilot-1/receipts/student-guide.json",
  "receipt_sha256": "<exact returned per-output receipt SHA-256>",
  "format": "pdf"
}
```

The existing `unaltraweb-practice-artifacts plan/stage` verifies the new receipt,
retained closure, original request/manifest/worker lineage, consumer identity and
selected bytes. It emits the same common product/policy v1 and named-v1 layout.
Its new source-free native sidecar format is
`unaltraweb-retained-private-artifact-v1`: safe handoff/activity/version/language/
recipient/format, original approval values and explicit no-intake-approval/no-
scientific-validation status. Private paths, source Markdown, raw original
receipts, evidence bodies and renderer details never enter the remote sidecar.

Original typed edition-v1 composition, ordinary artifact stages and retained
original manifest/producer identities keep their separate formats. This admission
and stage do not call publish or auth. Later actual publication still requires a
separately explicit project-scoped binding, exact repository-named bucket,
reviewed stage/manifest, private authenticated byte/header/ACL readback and
restore qualification. Current sources may disappear after a complete local
snapshot without changing its archived bytes or making old approval fresh.

Source/CI support is not a containing released runtime or actual pilot. Geodisseny
owner preparation, exact original evidence selection and the first small private
archive plan are recorded in the producer's retained-intake owner return.
