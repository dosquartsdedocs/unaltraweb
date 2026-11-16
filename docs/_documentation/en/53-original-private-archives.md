---
title: Original private archive admission
description: New byte/provenance admission of an existing original ZIP without invented PDF or native practice lineage.
lang: en
ref: original_private_archives
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 700
permalink: /original-private-archives/
---

## Archive an original as itself

An existing initial-project/data ZIP can be useful private archival input without
being a paired teaching edition. The original-archive class admits **one exact
original ZIP as itself**, preserving bytes, filename, internal roots and original
metadata. No missing PDF, worker receipt, formal role/language/approval, native
reopen or full-offline certificate is invented.

This is a **new byte/CRC/member/reference admission**. Caller classification is
labelled `caller-selection-not-original-seal`; scripts, README/licence/provenance
and project files are DATA, never executed or interpreted as instructions. No
teaching/author/native/scientific/public approval or offline qualification is
granted. Plan/snapshot perform no GIS, rendering, authoring, network, credential,
storage or catalogue operation.

The existing paired intake remains strict about PDF/worker/member lineage. The
retained-letter importer likewise requires its own authentic native bundle and
rendering profile. This additional class fills only the original-ZIP admission
gap, reusing shared confinement, ZIP verification, selected copy, atomic install,
native product/stage/private files-v1/S3/auth/attempt machinery.

## Explicit request/schema and CLI

The public wheel packages `original-private-archive-v1.schema.json`, also exposed
at `web://original-private-archive-schema`. A consumer owner can version a request
such as `.unaltraweb/original-archive.json`:

```json
{
  "kind": "unaltraweb.original-private-archive",
  "schema_version": 1,
  "purpose": "private-archive",
  "consumer_repository": {
    "remote": "origin", "host": "github.com", "repository": "example/course"
  },
  "archive_id": "original-starter",
  "archive": {
    "path": "assets/projects/city/original-starter.zip",
    "sha256": "<exact ORIGINAL ZIP SHA-256>",
    "bytes": 58051
  },
  "snapshot": "sandbox/original-archives/original-starter/owner-trial",
  "classification": {
    "kind": "initial-project",
    "role": "unknown",
    "language": "unknown",
    "human_approval": "unknown",
    "native_reopen": "not-performed",
    "scientific_validation": "not-performed",
    "full_offline": "requires-network"
  },
  "evidence": [],
  "member_references": [],
  "checksums": []
}
```

Replace all example identities/pins/counts with owner-inspected exact values.
The ZIP can be an original tracked asset or retained source, not a forced practice/
version directory. The control request is versioned/non-ignored; source/evidence
paths are normalized project-relative no-follow reads. Native local Git metadata
binds the explicit consumer repository/bucket, never a basename or guessed ID.

Classification kinds are `initial-project`/`data-archive`, roles
`unknown`/`private`/`student`/`teacher`, languages `unknown`/`ca`/`es`/`en` (known
languages must be enabled by the site). These are **caller selections**, not
original seals inferred from prose/files. Approval/reopen/science/offline fields
accept unknown/not-performed/not-qualified/requires-network or explicit
caller-reported states, never an invented `approved`/`qualified` certificate.

Optional local evidence (up to eight items) declares an ID, role and exact pin:

```json
{"id":"original-note","role":"provenance",
 "file":{"path":"context/original-note.md","sha256":"<exact SHA>","bytes":123}}
```

Roles are `provenance`, `metadata` or `checksums`. Selected JSON, Markdown, text
or SHA256SUMS bodies stay local and bounded to 1 MiB/file, 8 MiB total. JSON is
parsed as bounded data. Optional `member_references` pins exact regular members:

```json
{"role":"provenance","path":"starter/README.md","sha256":"<exact member SHA>"}
```

Complete member hashes are freshly observed, not represented as an old seal.
Optional checksum references explicitly name origin, scope and reference base:

```json
{"source":"member","path":"starter/SHA256SUMS","scope":"members","base":"starter"}
```

`source:evidence` names an explicit evidence ID instead. `scope:members` checks
each declared checksum against the exact observed ZIP member using the explicit
base (empty means ZIP root). `scope:archive` checks the original outer ZIP path/
hash using an explicit consumer-relative base; other unselected lines are not
claimed as freshly checked inputs. Missing/corrupt/mismatched references fail.

```bash
unaltraweb-original-archive plan \
  --project /absolute/course --request .unaltraweb/original-archive.json \
  --sha256 REVIEWED_REQUEST_SHA256

unaltraweb-original-archive snapshot \
  --project /absolute/course --request .unaltraweb/original-archive.json \
  --sha256 REVIEWED_REQUEST_SHA256 --expected-plan-sha256 REVIEWED_PLAN_SHA256
```

Python APIs are `original_archive.plan(project, request_path, sha256)` and
`snapshot(project, request_path, sha256, expected_plan_sha256)`; from core source
use `PYTHONPATH=src python3 -m unaltraweb_mcp.original_archive`. The public wheel
has no private hub/MEGA/GIS/renderer dependency for this local interface.

## Read-only plan and honest create-only receipt

The stable digest binds exact request/archive/evidence pins, caller classification,
explicit reference origins, native repository, Jekyll privacy controls, freshly
observed complete ZIP member SHA/size/CRC and producer code. Existing shared bounds
apply: 512 MiB input, 2-GiB expanded/workspace budget, 10,000 entries and bounded
central-directory preflight. Links/special files/path escapes/aliases/unsupported
encryption or compression/corrupt CRC/hash/limits fail. Hashing does not extract
members or certify GeoJSON/GPKG/QGZ semantics; WMS dependencies stay declared
limitations, not requests or full-offline claims.

The separate expected-plan-bound action rechecks unchanged inputs and uses native
selected-copy/atomic create-only install helpers in ignored
`sandbox/original-archives/<id>/<run>`, root0700/files0600. Only the original ZIP and
finite necessary local request/evidence are copied unchanged. Originals are never
moved/renamed/normalized/repackaged. Failed private candidates stay inspectable;
the namespace retention policy does not grant cleanup authority.

A new `unaltraweb-original-private-archive-admission` v1 `admission.json` retains
that plan; `receipt.json` is a new `unaltraweb-original-private-archive-receipt`
v1 bound to its hash. It is not an original PDF/GIS/edition certificate. Subsequent
planning verifies the copied request, original ZIP/evidence/member/checksum graph,
classification and fixed truth flags. Unknown declarations cannot become native
approval; complete snapshots can outlive hot original source files.

## Existing private files-v1 stage/publication/fetch

Route the new exact receipt/path/SHA as `format:zip`, route v3
`delivery_layout:files-v1`, private S3 and `authenticated-private-v1`. Unknown or
private role requires audience `private`; caller-selected student/teacher allows
only that role or private. Native Git bucket identity and project/destination auth
remain exact. No named-v1/public/anonymous delivery admits this class.

The source-free local sidecar/native format is
`unaltraweb-original-private-archive-v1`: archive ID, safe classification and
explicit new-byte-admission/no-original-seal/no-approval/no-reopen/science/offline
qualification. Original body/path/script/README/worker/proof evidence is not
exported as control metadata. All sidecars/inventories/receipts/delivery seals and
attempts stay local; only `<explicit-prefix>/<original-filename>.zip` is stored.

Existing conditional create/reuse, refusal of different object/header collisions,
native byte/header/private ACL readback and no-replay/tamper/uncertainty guards are
reused. Common authenticated files-v1 fetch uses retained LOCAL inventory and
restores only exact selected outputs plus optional local-input inventory. Native
ZIP/member/script bytes can be compared; no PDF or new recovery engine is needed.
Remote-only/full metadata reconstruction is not promised.

## Minimum consumer reservation/adoption

In its existing session, the owner selects its genuine original ZIP/evidence and
reserves only the versioned original-archive request plus existing route policy
entry, with existing ignore/privacy controls adequate. No original course material,
missing historic paired output or native receipt is reconstructed to satisfy this
class. Qualify an exact public wheel/source for this consumer without replacing
other consumers' frozen batch producers. Review PLAN/digest, explicitly snapshot,
review receipt/stage/policy, then separately bind project auth for real storage/
readback/common fetch. Source CI is not a release/global client cutover; native
reopen/science/offline qualification stays with its owning workflow.
