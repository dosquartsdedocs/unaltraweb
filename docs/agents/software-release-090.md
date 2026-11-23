# Web 0.9.0 software delivery and source-default follow-up

Owner authorization: 2026-11-23, producer issue 98. This is a new additive
software release, not a replacement of immutable public 0.8.1. The separate
postrelease source-default change below does not rewrite published artifacts.

## Integrated source scope

The original histories of PR129 and the dependency-ordered PR130–139 stack are
retained. Shared packaging/workflow conflicts preserve both implementations and
their refusal tests:

- Optional, expiring release-candidate transport with exact Actions artifact-ID
  readback. Its S3 qualification remains separate from durable practice products.
- Explicit hash-pinned early input preparation and tabular edition v2 without a
  fabricated GIS or spreadsheet-calculation claim.
- Repository-bound per-artifact private delivery, retained local uncertainty
  evidence, explicit files-v1, paired retained intake and honest original ZIP
  admission. Original names, bytes, hash origins, recipient bindings and failed
  attempts remain authoritative.
- The excluded-private-source snapshot correction from issue 114.

The public command interfaces are the original reviewed
`unaltraweb-prepare-inputs`, `unaltraweb-candidate-storage`,
`unaltraweb-practice-artifacts`, `unaltraweb-retained-intake` and
`unaltraweb-original-archive`. No alternative uploader, artifact engine or
recovery implementation is introduced.

## Candidate and tuple boundary

The canonical BOM selects the software version. Protected source checks, signed
candidate procedures, receipt ancestry and exact native package authorization
qualified the final artifact-producing source
`0466b782507dcf3537e25926bbdee59aabdb253e`.

The initial signed candidates from `987412c72bee7f643125c5d7ce2cb1ee75416360` passed image workflow
45185571925, including exact provenance, Ruby/PDF/MCP/docs tests and digest
promotion. The selected new PDF is `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:38f62cba21cd2b50a3512bd00743a3a8413c89b99f51b55d1bb47d1bb72bad3c`,
producer `987412c72bee7f643125c5d7ce2cb1ee75416360`, native source version 0.9.0.
It is not the old 0.7.1 worker. Its record ancestor `7db24abf329ad46395e20665ad718a449b906a1f`
is the independent reviewed core/workflow selection and native gem 0.9.0.
Initial MCP bytes are not the final tuple. The final runtime/MCP digests and
original gem/wheel bytes were retained through receipt-only PR144, without
rebuilding candidates for publication.

Unchanged compute Python/R, capture, classic private QGIS and visual-helper
selections retain their own actual versions and identities. SDK/W1/H2 and full
managed-helper adoption are not silently included.

## Published software and verified public bytes

[Release v0.9.0](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.9.0),
ID `455729358`, delivers exactly three original assets:

| Asset / Release asset ID | Bytes | SHA256 |
| --- | ---: | --- |
| `unaltraweb-0.9.0.gem` / `783790522` | 33578496 | `b3e80760c27d646c125dbcb37e90fbe48a20ea46979dba33e92f590da26ce046` |
| `unaltraweb_mcp-0.9.0-py3-none-any.whl` / `783790520` | 372227 | `76df9c2643b2e071d2c47cc2a24be7e8ddb76bf523dd928a16f75a602ffa40f3` |
| `SHA256SUMS` / `783790521` | 195 | `03b4a2e1e0d5402e05e6cd06ca1f5137be39c56acd0c52b7a0a99f70c370eb4b` |

The tag target is `d9406db1e74facf18f19a5f436bf0e41f19fb839`; annotated tag
object `7cd92e5e0a01dda265fdce16e0fac363e004bf7e`. Its first parent is the
artifact source above; its only first-parent change is `release-candidates.json`,
SHA256 `4bdfbad42dfcdf6047e52028234c76946eb4870a30744cf8fce568545899d0d8`.

Final signed image run `45192808028`, package run `45195192931` / original
artifact `14827357692`, promotion `45216846677` and Trusted Publishing
`45217719156` succeeded at their original attempts. Runtime and MCP immutable
references are:

- `ghcr.io/dosquartsdedocs/unaltraweb@sha256:564d6545cbb7d81f4210d18df6298b63ba517605ba62e5ea99235df67b88b8e4`
- `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:29b1559b4e91b98247baf227039dc553da504e9df1972299bcbb20a2ed5b029c`

Anonymous public registry full-file bytes matched the gem/wheel hashes and
sizes. Their independent hub report has SHA256
`e7a1b8211521a3e3741fe9426b6b019f4530056c01a13c101f4076416b78f265`;
the public wheel BOM matched the tagged canonical bytes. Each of the three
Release assets was also downloaded anonymously once over HTTP200 and checked
against the original full-file hash and size. This is separate channel coverage,
not an inference from a Release URL, tag or successful workflow.

OCI index/platform-manifest/config payload bytes and revision `0466b782...`
were verified without layer downloads. Configuration digests `684ff080...`
(runtime) and `c8bd0857...` (MCP) are not registry index digests or assumed local
Docker IDs. The separately selected PDF38/prod987/core/workflow7db above remains
unchanged; final-build verification PDF3bd19368 was not selected or
coordinated-semver promoted.

The original fourth installed case passed real offline venv/wheel member-byte,
origin/version/PDF guards, isolated native gem activation with original image
dependencies, and unchanged MCP stdio/real selected-PDF preview scripts. No fifth
installed case or public-package reinstall is implied. Earlier ensurepip,
gem-path, stdin, Ruby writer and administrative auditor failures remain distinct
negative observations. Later independent evidence does not relabel them.

## Separate postrelease source-default pin

The immutable 0.9.0 tag and public wheel retain the old 0.8.1 MCP digest fallback
when their bare bootstrap asset is executed without an override. The tagged root
Makefile also retains that old `MCP_RELEASE_IMAGE` default. Normal installed
wheel CLI and installed packaging Make pass 0.9.0 explicitly with `--image`;
the CLI selects its argument, then explicit environment, then the packaged BOM.
These routes must not be described as though all tagged defaults already
selected 0.9.0.

This separate postrelease **source-only** change selects the published immutable
MCP digest `29b1559b4e91b98247baf227039dc553da504e9df1972299bcbb20a2ed5b029c`
for the root Makefile default and bare source bootstrap fallback in later source
uses. It leaves the published tag, wheel, packaging Make, BOM, versions, workers,
core/workflow and ABI unchanged. Exact source PR/head/merge/CI evidence is
recorded in issue98, not manufactured as a replacement release receipt.

For the old tag's source/bare-bootstrap routes, pass the full published
`ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:29b1559b4e91b98247baf227039dc553da504e9df1972299bcbb20a2ed5b029c`
through explicit `--image` or the root Makefile's `MCP_RELEASE_IMAGE`, as
appropriate. The bootstrap's explicit `--image` continues to override its
environment/fallback selection. There is no automatic fallback to another
version. Workspace, managed identity, no-build/pull-in-serve/check/smoke and socket
guards are unchanged; the existing default-selection test changes only its
expected digest.

Publication and source-default selection are not live client adoption. The
authoritative working checkout, client registrations, consumers and manuals were
not moved, reconfigured or reconnected. Delivery covers the three Release assets,
registries and OCI references, not an unpublished tarball, universal H2 admission,
SDK/helper graph, Podman/GC or practice-storage qualification.

## Pending naming and entrypoint work

The owner's intended English technical source directory is `practices/`.
Reviewed existing code and original records still use `practiques/`, with
explicit `_practices/` legacy mappings. Issue 140 contains the earlier naming
proposal and its recorded discrepancy. A compatible producer correction and
separately reserved consumer plans are required; this integration does not
rename originals, sealed runs, ZIP members, receipts or remote keys.

Thin manual Make facades and a factory-free installed context-export closure
remain a separate bounded delta. Existing original-archive and retained-intake
CLI domains and guards are preserved rather than replaced.

## Downstream boundary

Publishing this software does not edit manuals, hydrate real course inputs,
approve teaching prose, upload teaching S4 objects, migrate a consumer, change
its pins, reconnect clients or deploy Pages. The hub receives immutable software
pins and the actual validation limits after publication; each adoption remains
explicit.
