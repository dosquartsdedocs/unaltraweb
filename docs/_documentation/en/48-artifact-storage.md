---
title: Project artifact storage
description: Select bounded temporary candidate transport without changing native publication or Pages formats.
lang: en
ref: artifact_storage
profiles: [unaltredocs]
documentation_profiles: [core-developers]
section: Core Development
weight: 675
permalink: /artifact-storage/
---

## Separate artifact classes

The version-1 storage selector controls **temporary `release_candidate` transport**
between `site-release.yml`'s prepare and publish jobs. It does not select a public
delivery destination. A candidate expires; a published edition remains available
at its published URLs while those URLs are referenced.

| Class | Delivery and lifetime |
| --- | --- |
| Temporary release candidate/evidence | GitHub Actions v4 by default, or project-selected private S3; 1–14 days. |
| Durable stable manual | Existing reviewed GitHub Release assets; no latest-only deletion or renaming. Public S3 delivery requires a separate explicitly selected and qualified contract. |
| Private practice packet | Existing ignored, retained practice editions for the named recipient; never made public by this selector. |
| GitHub Pages site | Native `upload-pages-artifact` / `deploy-pages` protocol, unchanged. |

## Project-owned policy

New package scaffolds include `.unaltraweb/artifact-storage.json`. This is an
editable project selection, not a managed pin and not a `publication.json` file.
Existing sites without this file retain the same GitHub default without installing
an S3 SDK or configuring an S3 account:

```json
{
  "schema_version": 1,
  "release_candidate": {
    "transport": "github-actions",
    "retention_days": 14
  }
}
```

The package owns `artifact-storage-v1.schema.json` and the
`unaltraweb-candidate-storage` CLI (`plan`, `seal`, `verify`, `receive`,
`s3-upload`, `s3-download`). The shared workflow freezes the reviewed project's
selection before executing builds, then passes that frozen policy to the
publisher. Unknown schema versions, classes, fields and transports fail closed.
The MCP inventory and existing consumer runtime/image pins are unchanged.

## Private S3-compatible selection

```json
{
  "schema_version": 1,
  "release_candidate": {
    "transport": "s3-private",
    "retention_days": 14,
    "s3": {
      "profile": "s3",
      "endpoint_url": "https://s3.example.invalid",
      "region": "example-1",
      "bucket": "project-private",
      "prefix": "web-candidates",
      "addressing_style": "path",
      "lifecycle_rule_id": "expire-candidates"
    }
  }
}
```

`profile: s4` selects the same S3 API and byte format; it does not create a new
artifact format or make S4 a dependency of other sites. HTTPS origins cannot
contain embedded credentials. No project account or destination is selected by
this example.

Before using S3, the project owner must provision and qualify:

1. A private bucket/prefix and CI-scoped credentials, preferably short-lived.
   Pass only the reusable workflow's optional `candidate_s3_access_key_id`,
   `candidate_s3_secret_access_key`, and `candidate_s3_session_token` secrets.
   The adapter accepts their corresponding `UNALTRAWEB_S3_*` environment variables
   for explicit CI/native use. It never consults personal profiles, host files,
   instance metadata, a private hub repository, or MEGA credentials.
2. Permission to read the bucket public-access-block/lifecycle/versioning configuration and to
   `PutObject`/`GetObject` only in the selected candidate namespace. The publisher
   needs read access there; neither role needs delete, ACL or lifecycle-write
   authority. All four bucket public-access-block settings must be enabled and
   observable through the S3 API; an endpoint without this proof is unqualified
   and refused, including an S4 profile. No public-read ACL is requested.
3. An enabled lifecycle rule with the exact ID and isolated `<prefix>/` filter,
   `Expiration.Days` no greater than the selected retention. Versioned or suspended
   buckets must also bound `NoncurrentVersionExpiration.NoncurrentDays`. The
   adapter verifies these rules; it never edits bucket policy or deletes editions.
   Service lifecycle expiration is asynchronous, so expired candidates are also
   refused by the reader at the exact envelope deadline.
4. HTTPS/private-access, conditional `If-None-Match: *` writes, real readback,
   lifecycle and CI credential qualification against the chosen provider. S3
   compatibility is not inferred from an endpoint's name. OIDC trust/role setup
   and token exchange are project CI responsibilities; pass the resulting
   temporary credentials. This unit does not provision an OIDC trust or host key.

The optional public SDK closure is pinned in
`scripts/manual/candidate-storage-s3-requirements.txt` (Boto3/Botocore 1.40.75,
urllib3 2.8.0).
It is installed only for S3 workflow steps. The public wheel offers the
`artifact-storage` extra for native integrations. No private code is copied into
consumer sites.

## Exact bytes, identity and verification

Both transports carry the same `release-transfer/` directory: a separate
`candidate-transfer.json` v1 envelope and untouched `release-assets/` containing
PDFs, the deterministic site tar.gz, `release-manifest.json`, the **native schema2
`publication.json`**, and `SHA256SUMS`. The envelope inventories every filename,
SHA-256 and byte count, including the checksums file. Its hash and size are
prepare-job outputs, not selected by the receiving storage service.

The envelope binds repository, selector, full source SHA, run ID, run attempt,
policy digest and expiration. The GitHub artifact name retains all those build
selectors; transfer/readback requires its exact positive numeric artifact ID,
`merge-multiple: true` to retain the package root for ID downloads, and
`overwrite: false`. The Python 3.13 CI lane performs an actual synthetic v4
upload/download followed by envelope and native-format verification. S3 uses:

```text
<prefix>/release_candidate/<owner>/<repo>/<selector>/<source-sha>/<run-id>/<run-attempt>/<asset-name>
```

S3 publishes the envelope last, uses conditional create-only writes and reads
back every uploaded object to verify size and SHA. It streams large files rather
than buffering the site archive in RAM. Retries are bounded to three attempts for
transient server/network errors; absent objects, permission failures, corruption,
conflicts and expired evidence do not trigger another backend, public URL, older
attempt or different build. A failed/uncertain upload may leave a partial prefix;
it is not publication authority and remains bounded by lifecycle retention.

After download, the same envelope verifier checks the complete package and only
then copies native assets to the publisher. The existing native release verifier
still validates formats, site/PDF hashes, reviewed source and runtime identities.
Its privileged Release readback/byte comparison and final publication gates are
unchanged. Storage configuration can never replace native publication metadata.

## Adoption gates

The source change is reviewable without selecting S3. Synthetic tests exercise
both transports, exact native-verifier acceptance, hash/size failures, absence,
authentication denial, retries, no-clobber and retention. They do not qualify a
real private endpoint. Consumers must explicitly select the reviewed workflow
commit after its CI/review, retain their accepted runtime/helper pins, and test
their chosen transport. No release, tag, image publication, Pages deployment or
manual content adoption is performed by this implementation.
