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

The scaffold includes `.unaltraweb/practice-artifacts.json` with `publication:null`
and an empty `artifacts` map. A maintainer supplies the actual policy. For example:

```json
{
  "kind": "unaltraweb.practice-artifact-storage",
  "schema_version": 1,
  "publication": {
    "kind": "gacontext.publication-policy",
    "schema_version": 1,
    "project_id": "example-course",
    "default_target": "github",
    "targets": {
      "github": {
        "driver": "github-release",
        "repository": "example/course",
        "release": "practices-2026",
        "visibility": "public",
        "audiences": ["public", "student"],
        "auth_ref": "course-ci"
      },
      "s4": {
        "driver": "s3",
        "endpoint": "https://s3.eu-barcelona-1.megas4.com",
        "region": "eu-barcelona-1",
        "bucket": "example-private-practices",
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
      "audience": "student",
      "receipt": "dist/practiques/table/r1/ca/table-r1-ca.zip.receipt.json",
      "receipt_sha256": "<exact native receipt SHA-256>",
      "format": "pdf"
    },
    "table-ca-student-data": {
      "target": "s4",
      "audience": "student",
      "receipt": "dist/practiques/table/r1/ca/table-r1-ca.zip.receipt.json",
      "receipt_sha256": "<exact native receipt SHA-256>",
      "format": "zip"
    },
    "table-ca-teacher-data": {
      "target": "s4",
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
readback. Public delivery also requires actual anonymous GET of the exact bytes;
private delivery requires anonymous GET denial. A private physical locator is
not a public download link. S3 streams PUTs, uses 16-MiB multipart parts from
64 MiB upward and conditional completion, and attempts to abort only its own
failed multipart upload. There are no automatic write retries or provider
fallbacks. Failed/uncertain attempts preserve the local stage for explicit review.

The JSON result is a Web-owned verified receipt with logical identity, exact
configuration/destination/manifest hashes, locators and access evidence. It
reports `catalogue_updated:false`. Updating reader-facing links/catalogues remains
a separate owner action after qualification. Existing URLs and stored editions
are retained when choosing a new target; publication never deletes/reuploads an
old asset to emulate CAS or frees storage implicitly.

## Shared contract and adoption

The packaged product and publication schemas are byte-identical to gaContExt
revision `3c094009819785135bc8851b4fddd4723dbfe693`, from
[gaContExt #89](https://github.com/dosquartsdedocs/gacontext/issues/89). The Web-only
route map extends selection granularity without changing either common schema
or embedding destination information in `product.json`. A closed stage can also
be inspected/planned with the common CLI and a standalone copy of the inner
`publication` policy. S3 named delivery includes the common restore manifest.

MCP discovery exposes `web://practice-artifact-storage-schema`,
`web://product-publication-schema` and `web://publication-policy-schema`. Planning,
staging and explicit transfer are public Python/CLI interfaces; publication does
not become an automatic MCP session-start or Jekyll-build action.

Synthetic native ZIP/PDF fixtures, HTTP/S3 doubles and the real pinned SDK model
exercise mixed targets, recipient isolation, corruption/absence, no-clobber,
visibility, multipart failure and destination changes. Real practice storage
requires owner selection of the bucket/prefix or Release, scoped credentials,
provider qualification and a reviewed runtime/workflow adoption. The core source
does not select or upload actual course materials merely by adding this interface.
