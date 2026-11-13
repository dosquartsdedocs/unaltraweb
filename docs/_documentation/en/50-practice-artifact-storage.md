---
title: Per-artifact practice storage
description: Route individual practice PDFs and data packets to GitHub Releases or S3-compatible storage, including S4.
lang: en
ref: practice_artifact_storage
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 685
permalink: /practice-artifact-storage/
---

## Choose a destination for each artifact

One course can keep a student guide in a public GitHub Release, a large data ZIP
in S4, and the resolved teacher packet in private S4. Each logical artifact has
its own explicit target and audience. There is no automatic fallback between
destinations or routing inferred from a filename, recipient, size or extension.

This interface selects **durable practice outputs** already produced by
`manual_practice_compose`: independent PDF guides and ZIP packets, identified by
their exact native edition receipt. It is separate from temporary Actions
candidates and the stable manual/Pages publication protocol. Large practice
materials do not need to enter Git or the Jekyll site to be stored here.

## Project-owned policy

The scaffold includes `.unaltraweb/practice-artifacts.json` v2 with
`consumer_repository:null`, `publication:null` and an empty `artifacts` map.
A maintainer supplies the explicit native consumer repository and actual policy:

```json
{
  "kind": "unaltraweb.practice-artifact-storage",
  "schema_version": 2,
  "consumer_repository": {
    "remote": "origin",
    "host": "github.com",
    "repository": "example/tigit"
  },
  "publication": {
    "kind": "gacontext.publication-policy",
    "schema_version": 1,
    "project_id": "example-course",
    "default_target": "github",
    "targets": {
      "github": {
        "driver": "github-release",
        "repository": "example/tigit",
        "release": "practices-2026",
        "visibility": "public",
        "audiences": ["public", "student"],
        "auth_ref": "course-ci"
      },
      "s4": {
        "driver": "s3",
        "endpoint": "https://s3.eu-barcelona-1.megas4.com",
        "region": "eu-barcelona-1",
        "bucket": "tigit",
        "prefix": "practices/v1",
        "visibility": "private",
        "audiences": ["student", "teacher", "private"],
        "auth_ref": "course-s4"
      }
    }
  },
  "artifacts": {
    "table-ca-student-guide": {
      "target": "github",
      "storage_profile": "anonymous-delivery-v1",
      "audience": "student",
      "receipt": "dist/practiques/table/r1/ca/table-r1-ca.zip.receipt.json",
      "receipt_sha256": "<exact native receipt SHA-256>",
      "format": "pdf"
    },
    "table-ca-student-data": {
      "target": "s4",
      "storage_profile": "authenticated-private-v1",
      "audience": "student",
      "receipt": "dist/practiques/table/r1/ca/table-r1-ca.zip.receipt.json",
      "receipt_sha256": "<exact native receipt SHA-256>",
      "format": "zip"
    },
    "table-ca-teacher-data": {
      "target": "s4",
      "storage_profile": "authenticated-private-v1",
      "audience": "teacher",
      "receipt": "dist/practiques/table/r1/ca/table-docent-r1-ca.zip.receipt.json",
      "receipt_sha256": "<exact native teacher receipt SHA-256>",
      "format": "zip"
    }
  }
}
```

Replace the example repository, Release, bucket and receipt placeholders before
validation. Version the nonsecret configuration. `default_target` is part of the
shared project contract, but Web requires `target` on **every artifact**: changing
the default cannot redirect an existing artifact. A `student` audience can use
either public or private storage. Native `docent` outputs require `teacher` or
`private` and can never enter a public target, even after relabelling the route.

### One repository-named bucket per manual

Every selected S3/S4 bucket must **exactly equal the consumer Git repository
slug**: `tig`, `tigit`, or `geodisseny` for these manuals. The declared remote must
have one native local Git repository URL, and any explicit push URL must agree.
Standard GitHub/Bitbucket HTTPS and Git SSH URL forms are supported. Missing,
unsupported, conflicting or multiple identities are reported explicitly.
The official Bitbucket SSH endpoint `ssh.bitbucket.org` (scp or `ssh://git@`
with an omitted/default port 22) identifies the same logical `bitbucket.org`
repository as its web URL. Explicit default SSH port 22 is also supported on
the other admitted SSH hosts. HTTPS IDs/port rules stay unchanged. Workstation
aliases, lookalike hosts, password-bearing URLs and nondefault SSH ports fail;
repository/bucket spelling is preserved exactly. No remote is rewritten.

The implementation reuses the native confined Git/root helpers; it performs no
remote lookup, SSH repair or URL alias expansion. It does not derive the bucket
from a folder basename, `publication.project_id`, Pages baseurl, the public
artifact target repository, or the Web core. It never lowercases or substitutes
a bucket to make it fit. A prefix partitions artifacts **inside that manual's
bucket**; it cannot stand in for the required bucket identity.

The frozen common policy/product schemas remain v1. The Web route schema v1 is
retained for previous records and GitHub-only selections; new manual S3 selections
require explicit v2 repository metadata and capability selection.

### Explicit storage capability

- `authenticated-private-v1` is private S3/S4 **storage**. It requires actual
  private bucket ACL/policy preflight, authenticated byte/size/MIME/filename
  readback and each stored object's native private ACL. It does not probe or
  construct a usable object URL. Receipts report `public_url:null`,
  `object_url_published:false`, `anonymous_probe_performed:false` and
  `anonymous_object_url_qualified:false` alongside the verified authenticated
  and native-ACL evidence. The profile requires no MEGA account ID.
- `anonymous-delivery-v1` retains object-URL qualification. Public artifacts need
  exact anonymous GET of the same bytes and, for named S3 objects, the same MIME
  and download filename. A selected private URL needs actual 401/403/404 denial.
  An API response **400 InvalidRequest / Signature Version 4 required is not
  anonymous-denial or delivery evidence**. No error switches the selected profile.

The owner's already-qualified S4 API/object-URL distinction motivates the first
profile. Storing private bytes does not activate account-routed/public object
URLs, qualify a public link, or change bucket policy. Host and CI credentials
remain independently selected for this consumer project.

## Plan and stage locally

The public wheel supplies `unaltraweb-practice-artifacts`; it works without a
gaContExt checkout. From the core source, use
`PYTHONPATH=src python3 -m unaltraweb_mcp.artifact_publication` instead.

```bash
unaltraweb-practice-artifacts plan \
  --project /absolute/course \
  --sha256 REVIEWED_CONFIG_SHA256 \
  --artifact table-ca-student-data

unaltraweb-practice-artifacts stage \
  --project /absolute/course \
  --sha256 REVIEWED_CONFIG_SHA256 \
  --artifact table-ca-student-data \
  --stage sandbox/artifacts/table-ca-student-data/review-1
```

`--sha256` binds the exact bytes of `.unaltraweb/practice-artifacts.json`; use
`--config` for another versioned project-relative path. Planning checks the native
receipt and output hash/size, project exclusions and audience, then returns the
destination, policy/destination hashes and backend-independent manifest hash.
It resolves no credentials and performs no network operation.

To review an existing stage after a control-plane upgrade, `plan` also accepts
the pair `--stage <retained-stage> --manifest-sha256 <original-manifest-hash>`.
It verifies the original manifest/files and their match to the selected native
receipt, preserving the old producer revision and **exact manifest bytes**.
`publish`/`verify` use the same retained identity. A v2 route/profile change never
reseals an older stage or changes its logical project/product identity.

Staging is create-only under ignored `sandbox/artifacts/<id>/<run>`. It copies
only the selected native PDF or ZIP, a source-free `artifact.json` sidecar and
the common `product.json` manifest. Native receipts, original source paths,
author Markdown, reconstruction controls and neighbouring files remain local.
The producer revision uses the existing bounded package-code/contract fingerprint,
separate from the consumer's data revision and the native output seals.
An existing stage is never replaced. This Web profile accepts outputs smaller
than 2 GiB, within the existing workspace total-byte budget; the shared schema
has broader limits for other producers.

The workspace contract classifies the routing file as versioned/never-cleanup
and `sandbox/artifacts` as ignored/explicit-cleanup. A successful upload does not
authorise removal of a local stage or a previously published version.

Generated sites expose offline Docker facades `make practice-artifact-plan` and
`make practice-artifact-stage`, using `PRACTICE_ARTIFACT_ID`,
`PRACTICE_ARTIFACT_SHA256` and, for staging, `PRACTICE_ARTIFACT_STAGE`.
Core-maintainer Make targets use the same variables plus an explicit inherited
`MCP_CONSUMER_WORKSPACE`. These commands require a reviewed image containing the
interface; editing a discovery checkout does not update an installed runtime.

## Explicit publication and readback

Create/select the project-owned GitHub Release or S3 bucket/prefix before use.
GitHub needs the project's own CI/host token, independently of S4. S3-compatible
publication uses the optional public SDK extra:

```bash
python3 -m pip install 'unaltraweb-mcp[artifact-publication]'
```

The extra pins `botocore==1.40.75`. S4 uses the `s3` driver with its own endpoint;
it is not a required service for other projects. This durable interface uses
conditional writes and byte readback, without assuming AWS lifecycle, versioning,
Object Lock, public-access-block support or automatic SHA-256 checksums in S4.

Select a user-owned, mode-0600 authentication binding outside versioned sources:

```json
{
  "kind": "gacontext.publication-auth",
  "schema_version": 1,
  "project_id": "example-course",
  "bindings": {
    "course-ci": {
      "driver": "github-release",
      "destination_sha256": "<GitHub destination hash from plan>",
      "token_env": "COURSE_GITHUB_TOKEN"
    },
    "course-s4": {
      "driver": "s3",
      "destination_sha256": "<S4 destination hash from plan>",
      "access_key_env": "COURSE_S4_ACCESS_KEY",
      "secret_key_env": "COURSE_S4_SECRET_KEY"
    }
  }
}
```

Set those named environment variables in the selected host/CI process. Optional
S3 `session_token_env` names an explicit temporary credential. The client does
not discover AWS profiles, instance metadata, `gh auth`, memory credentials or
another project's keys. Changing a target requires its matching destination hash.

```bash
unaltraweb-practice-artifacts publish \
  --project /absolute/course \
  --sha256 REVIEWED_CONFIG_SHA256 \
  --artifact table-ca-student-data \
  --stage sandbox/artifacts/table-ca-student-data/review-1 \
  --manifest-sha256 REVIEWED_MANIFEST_SHA256 \
  --auth-file /absolute/private/course-publication-auth.json
```

Use `verify` with the same flags for remote read-only verification; it never
creates a missing object. The provider preflight checks actual repository/bucket
visibility. GitHub uses immutable hash-derived flat asset names in an existing
nondraft Release. S3 uses the shared named-v1 layout, preserving native filenames,
MIME and Content-Disposition, with the canonical common restore manifest:

```text
<prefix>/named/v1/<project-id>/<artifact-id>/<manifest-sha>/<filename>
<prefix>/manifests/<manifest-sha>.json
```

Every output and the final manifest require exact authenticated SHA-256/size
readback. The explicitly selected capability adds native private-ACL proof or
strict anonymous delivery qualification as described above. A private physical
locator is not a public download link. S3 streams PUTs, uses 16-MiB multipart parts from
64 MiB upward and conditional completion, and attempts to abort only its own
failed multipart upload. There are no automatic write retries or provider
fallbacks. Failed/uncertain attempts preserve the local stage for explicit review.

The JSON result is a Web-owned verified receipt with logical identity, exact
configuration/destination/manifest hashes, locators and access evidence. It
reports `catalogue_updated:false`. Updating reader-facing links/catalogues remains
a separate owner action after qualification. Existing URLs and stored editions
are retained when choosing a new target; publication never deletes/reuploads an
old asset to emulate CAS or frees storage implicitly.

## Private local S3 attempt evidence

S3 `publish` and remote-read-only `verify` retain a new local attempt under
`sandbox/artifact-attempts/<random-id>/`, outside the immutable three-file product
stage. The user-owned directory is mode 0700; `intent.json` and append-only
`events.jsonl` are mode 0600, ignored and explicit-retention evidence. They are
never included in a ZIP, product manifest, upload list or remote record.

Before a mutating request, fsynced intent and observations bind the workspace,
operation, source hashes/size, reviewed config, destination/policy, original
manifest and exact object keys. An observed multipart UploadId is fsynced with
its **exact bucket/key/id tuple before sending any part**. Progress records
contain bounded acknowledged counts/bytes and phases, not source bodies,
credentials, auth-file contents or provider error/response bodies. The log is
bounded to 1 MiB/1024 observations with a hash chain; evidence and source/control
bindings are checked before mutations. Failures retain the last durable state.

- Lost create response: the UploadId is **unknown**; none is invented and no
  guessed abort is sent.
- Failed part: the observed owned tuple is retained before an owned abort request.
  An acknowledged abort is recorded as such, not as verified absence/cleanup.
  A failed/lost abort keeps the exact tuple and `abort-uncertain` state.
- Failed/lost completion: final object bytes may already exist. Record
  `completion-uncertain` and send no automatic abort, retry or resume.
- Readback failure: retain the acknowledged/uncertain write and exact readback key.
  Readback failure never authorises overwrite, delete/reupload or another backend.
- Changed evidence or source/configuration/destination binding: stop further
  mutation. A damaged/unsettled journal is not labelled intact or cleaned up.

Successful results and safe CLI failures include a `local_attempt` pointer with
the relative directory, intent hash, full event-log hash and last phase. Raw SDK
errors are replaced with a fixed message and pointer. Compare the hashes to the
retained result when inspecting the records; local evidence is not a provider
receipt, independent author approval or recovery authority.

```bash
unaltraweb-practice-artifacts inspect-attempt \
  --project /absolute/course \
  --attempt sandbox/artifact-attempts/EXACT_ATTEMPT_ID \
  --intent-sha256 RETAINED_INTENT_SHA256 \
  --attempt-sha256 RETAINED_EVENTS_SHA256
```

This inspection is confined and local-only: it reads the bound files/hashes and
observation chain, and never resolves credentials or connects to a provider.
It validates historical local evidence, not current source freshness or remote state.
`verify` with the original stage/manifest/config pins performs explicit remote
read-only inspection and retains its own new local evidence. If a completed
output exists but later product metadata is missing, its exact bytes can be
verified while the complete product remains refused; verification does not
repair it. Inspect the exact tuple/phase before any separately authorised action.
There is no autonomous recovery, registry, upload listing, retry/resume/abort
executor or blanket cleanup operation. Keep earlier attempts and old stages.

Interruption or local disk failure can leave an incomplete last observation;
no further mutation is admitted after an evidence write/check failure. Such a
record grants no ownership or cleanup claim beyond its actual durable observations.
The mechanism changes local/Web receipts only, preserving the original remote
product schema, manifest/producer identity and bytes, including old retained stages.

## Shared contract and adoption

The packaged product and publication schemas are byte-identical to gaContExt
revision `3c094009819785135bc8851b4fddd4723dbfe693`, from
[gaContExt #89](https://github.com/dosquartsdedocs/gacontext/issues/89). The Web-only
route map extends selection granularity without changing either common schema
or embedding destination information in `product.json`. A closed stage can also
be inspected/planned with the common CLI and a standalone copy of the inner
`publication` policy. S3 named delivery includes the common restore manifest.
The existing common authenticated named-v1 reader can reconstruct these exact
files/manifests using authenticated requests and download headers, without an
activated object URL. Web's CLI supplies planning/staging/publication/verification;
this slice does not add a second restore engine or claim common `files-v1` layout.

MCP discovery retains `web://practice-artifact-storage-schema` for v1 and adds
`web://practice-artifact-storage-v2-schema`, alongside
`web://product-publication-schema` and `web://publication-policy-schema`. Planning,
staging and explicit transfer are public Python/CLI interfaces; publication does
not become an automatic MCP session-start or Jekyll-build action.

Synthetic native ZIP/PDF fixtures, HTTP/S3 doubles and the real pinned SDK model
exercise mixed targets, recipient isolation, corruption/absence, no-clobber,
visibility, multipart failure and destination changes. Real practice storage
requires owner selection of the bucket/prefix or Release, scoped credentials,
provider qualification and a reviewed runtime/workflow adoption. The core source
does not select or upload actual course materials merely by adding this interface.

## Existing manual intake

Read-only observation of TIGIT, TIG and Geodisseny is recorded in
[the owner readiness report](../../agents/web-s4-manuals-readiness.md). All three
still require deliberate runtime/configuration adoption. TIGIT/TIG need a closed
native practice product before upload. Geodisseny's existing simple local
`manifest.json` is not a typed Web edition receipt: preserve its exact files and
proofs. The additional [retained paired-output private intake](../retained-private-intake/)
can plan/admit this class locally for private archive only, emitting a new honest
receipt without relabelling the original manifest or approving teaching material.
Actual owner request/evidence selection and containing source/runtime adoption
remain separate gates; `human_approved:false` stays false.
