---
title: ZIP-only private selected-file storage
description: Explicit files-v1 plain private paths with original outputs and local-only metadata.
lang: en
ref: selected_file_private_storage
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 695
permalink: /selected-file-private-storage/
---

## Original ZIPs, simple private paths

When an original student/teacher ZIP already contains its PDF reading, select
**only those ZIP outputs** for remote archive. Keep standalone PDFs, worker/source
receipts and editorial/proof evidence locally. This changes remote selection,
not native packaging, original ZIP roots/names, language, recipient or approval.

The existing per-artifact CLI/API adds an explicit route-v3
`delivery_layout:"files-v1"`. It stores each selected `role:output` at exactly:

```text
<repository-named-bucket>/<explicit-policy-prefix>/<original-relative-filename>
```

For example:

```text
geodisseny/practiques/ca/avaluacio-multicriteri.zip
geodisseny/practiques/ca/avaluacio-multicriteri-docent.zip
```

There is no project/artifact/hash/version/control tree added by this profile.
Manifests, artifact sidecars, restore aliases, original receipts and attempt
journals remain **local**. This bounded opt-in supports private S3 with explicit
`authenticated-private-v1` only; it does not qualify public object URLs.

## Explicit route v3

The public wheel and `web://practice-artifact-storage-v3-schema` expose the same
`practice-artifact-storage-v3.schema.json`. V1/v2 routes retain their original
named-v1 behavior; scaffold defaults remain v2/unconfigured. V3 requires an
explicit `delivery_layout` on every route, choosing `named-v1` or `files-v1`.
The frozen common product/policy schemas remain v1.

```json
{
  "kind": "unaltraweb.practice-artifact-storage",
  "schema_version": 3,
  "consumer_repository": {
    "remote": "origin",
    "host": "github.com",
    "repository": "geourv/geodisseny"
  },
  "publication": {
    "kind": "gacontext.publication-policy",
    "schema_version": 1,
    "project_id": "geodisseny",
    "default_target": "s4-private",
    "targets": {
      "s4-private": {
        "driver": "s3",
        "endpoint": "https://s3.eu-barcelona-1.megas4.com",
        "region": "eu-barcelona-1",
        "bucket": "geodisseny",
        "prefix": "practiques/ca",
        "visibility": "private",
        "audiences": ["student", "teacher", "private"],
        "auth_ref": "geodisseny-private"
      }
    }
  },
  "artifacts": {
    "amc-ca-student-zip": {
      "target": "s4-private",
      "audience": "student",
      "format": "zip",
      "storage_profile": "authenticated-private-v1",
      "delivery_layout": "files-v1",
      "receipt": "<exact selected original-ZIP native/private-admission receipt path>",
      "receipt_sha256": "<exact selected receipt SHA-256>"
    },
    "amc-ca-teacher-zip": {
      "target": "s4-private",
      "audience": "teacher",
      "format": "zip",
      "storage_profile": "authenticated-private-v1",
      "delivery_layout": "files-v1",
      "receipt": "<exact selected teacher-ZIP native/private-admission receipt path>",
      "receipt_sha256": "<exact selected teacher receipt SHA-256>"
    }
  }
}
```

Use the actual reviewed project ID, region/endpoint, prefix, auth binding and
original receipt pins; example labels are not credential selections. The native
repository/bucket rule stays exact, and teacher artifacts remain teacher/private.
The profile does not infer audience, rename files or choose a fallback provider.

[Retained intake](../retained-private-intake/) already supports ZIP-only `selected`
entries for each original recipient package. Its original standalone PDF, worker
and ZIP member evidence still bind the ZIP bytes locally. The course owner proves
actual PDF containment and selects its own student/teacher candidates; Web does
not execute a new exporter or alter a course handoff/source/receipt.

## Same plan/stage/publish interface

```bash
unaltraweb-practice-artifacts plan \
  --project /absolute/manual --sha256 REVIEWED_ROUTE_SHA256 \
  --artifact amc-ca-student-zip

unaltraweb-practice-artifacts stage \
  --project /absolute/manual --sha256 REVIEWED_ROUTE_SHA256 \
  --artifact amc-ca-student-zip --stage sandbox/artifacts/amc-student/new-files-stage
```

Planning returns the exact plain remote key and local-inventory requirements,
without auth/network. A new files-v1 stage retains the same native `product.json`,
`artifact.json` and original output bytes, plus a private **local** `delivery.json`
seal binding files-v1, the exact manifest hash and selected output paths. Delivery
layout is outside native product identity. The seal is not a remote object or a
file in the common product manifest.

An existing named-v1 stage cannot be silently flattened by changing configuration:
the reviewed files-v1 stage needs that local seal. Conversely named-v1 rejects a
files-v1 stage as a layout mismatch. Make a new create-only stage; preserve earlier
stages, manifests, producer identities and named journals.

After explicit reviewed stage/manifest and project auth binding, the same
`publish`/`verify` operations use native S3 conditional create, authenticated
SHA/size/MIME/download-filename/private ACL readback and bounded local attempt
evidence. Only manifest entries with `role:output` are transferred. Each private
intent lists only the actual selected plain keys, with layout/source/config/
destination guards and exact owned multipart tuples. Local sidecars/seals and
metadata hashes remain guarded before mutations even though they are not uploaded.

Receipts report `layout:files-v1`, the selected output observations,
`remote_metadata_created:false`, `remote_deletes:0`, `metadata_location:local-only`,
`local_inventory_required_for_fetch:true` and
`full_remote_metadata_restoration:false`. There is no catalogue/content/native/
public approval inferred from storage.

### Existing different objects are a separate action

Identical bytes **and headers** are verified and reused. Absent keys use
`IfNoneMatch:*` for PUT or multipart completion. A different/corrupt object,
different headers, denied/unverifiable/private-ACL mismatch or a concurrent
conditional-create collision safely refuses; this increment does not grant
conditional-ETag replacement. It never blindly overwrites, deletes or reuploads a
different existing key. Resolve a collision through a separately reviewed exact
per-file update contract rather than changing the source bytes/name to force it.

No automatic retry/resume/abort follows uncertain completion. Existing local
evidence and no-replay/tamper/owned-upload guards apply to the plain key. An
explicit read-only verification may qualify final bytes observed after uncertainty.

## Common authenticated files-v1 fetch uses LOCAL inventory

The existing common files-v1 interface consumes the retained **local** original
product manifest and policy/target, exact expected manifest/policy hashes and a
new confined local destination. It authenticates, verifies selected output bytes,
MIME/download headers and private ACL, and reconstructs only selected outputs.
It performs no remote manifest/alias lookup. A local `product.json` may be retained
alongside restored files; that inventory came from the local input, not the cloud.

Web's per-artifact manifest includes local evidence `artifact.json`, so this
output-only fetch honestly reports an incomplete full product when evidence is
not fetched. ZIP byte identity and the embedded PDF can still be natively checked
exactly. Remote-only reconstruction/full metadata restoration is not promised;
preserve local inventories, receipts, stages and journals. The common reader stays
factory-owned and is not copied into a consumer or made a private dependency of
the public Web wheel.

## Owner adoption and old pilot retirement

After a qualified corrected public wheel/source is selected, the Geo owner can
verify original ZIP/PDF containment, explicitly select original student and teacher
ZIPs in a new reviewed intake request, and use route v3/private files-v1 with prefix
`practiques/ca`. Review new plan/snapshot/stage hashes and host destination/auth
binding, then publish/verify the two original ZIP keys and perform common
local-inventory files-v1 fetch plus native ZIP/PDF byte checks.

The previous named-v1 pilot and its eight objects remain their original readable
format. Verify the new replacements first; any retirement of those exact old/test
objects requires a separate inspected object set and owner decision. No automatic
cleanup, runtime/release/client cutover or actual cloud operation is part of this
source change.
