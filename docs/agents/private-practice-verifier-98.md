# Web #104 — native private QGIS delegation and independent-review corrections

PR #104 source adaptation authorized after QGIS 0.6.0 release. No private QGIS wheel,
parser or implementation is bundled into the public Web wheel/image. Acquisition
and authenticated admission of the private controller/engine belong to the hub.
The Web bridge only transports bounded structured requests to the existing native
producer CLI. Independent review of the corrected HEAD and publication remain
separate gates.

## Exact, distinct identities

The package-owned `practice-verifier-runtime.json` is exposed read-only through
`web://practice-verifier-runtime`. It distinguishes:

- Prepared private controller:
  `sha256:1fe4a54a42cbac4a6eea596be73425985ab3bca5f28f5871d2fa66d7c0a05f8b`.
- Native `practice-schema` installed-package identity: `unaltracaptura-qgis 0.6.0`,
  revision `sha256:4dcd2c40bca4836a202c0c5cc400553b0f134925023b7300e0c0ff2fff1d8492`.
- V1 schema `9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445`;
  v2 schema `528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb`.
- Engine `sha256:1003721d96abe9607d8337b36851f9b29f84c2f8f92b377d1a73ff03c9d15cd2`.
- Owner release source/tag: `ba68ebaf57d6066e1922bc79e76aec451c24084e`, `v0.6.0`.
- Release practice-producer revision:
  `sha256:2e4d6e1eb5a364162770921fc416f9cf64c60540868c0d4c907b993a779d0cc9`.
- Release wheel: 331788 bytes,
  `dde653f7a719d8dbb20b4471e3cdb7f9c99cbdfcb116647caba5a08e710c7b76`.

The OCI source label is actually absent (`null`). It is not relabelled as the
release Git commit. The release wheel and practice-producer identities are owner
release declarations, not fabricated pip installation evidence. Native schemas
report the verifier's installed-package revision `4dcd…`, independently confirmed
by the hub; using producer revision `2e4…` as that verifier pin is refused.

## External release receipt for H2

`release.receipt` declares the producer's external private receipt:

```text
https://github.com/dosquartsdedocs/unaltracaptura-qgis/releases/download/v0.6.0/release.json
Bytes: 1251
SHA-256: 45db1e016e666126e5a51f157be0be1066aaa08f32042f5907d46e0e7da1e404
```

The authenticated asset bytes were checked against this hash. The receipt agrees
on source, wheel, practice-producer revision and both image IDs above. Its
`mcp_image.archive` identifies the private, two-image Docker-save asset
`unaltracaptura-qgis-0.6.0-docker.tar.gz`: 1372004858 bytes, SHA-256
`d8570bdf350d7fa59fef787aca3c4b1be841ac14e5246586748aefef51a1d31f`.

The hub acquires and validates that receipt/archive through its authenticated
preparation path before H2 loading and activation. Web ships only the external
declaration; public CI does not fetch it. The receipt is QGIS-owned provenance,
not a Web attestation or a claim that Web has republished those private bytes.
The declared archive source also does not replace the actually absent OCI label.

## Selection and native boundary

The existing launcher accepts both startup-fixed entries together, as one JSON
argument to `serve --worker-images` after the hub has prepared the images:

```json
{
  "manual_pdf": {
    "reference": "sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa",
    "expected_image_id": "sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa"
  },
  "practice_verifier": {
    "reference": "sha256:1fe4a54a42cbac4a6eea596be73425985ab3bca5f28f5871d2fa66d7c0a05f8b",
    "expected_image_id": "sha256:1fe4a54a42cbac4a6eea596be73425985ab3bca5f28f5871d2fa66d7c0a05f8b"
  }
}
```

Configuration-ID references remain usable after Docker-save loading even when
registry `RepoDigests` are absent. The published PDF digest and producer remain
unchanged. A direct CLI uses the same package-owned accepted QGIS image; optional
`PRACTICE_VERIFIER_IMAGE` must still resolve to that exact expected ID. For a direct
CLI using the loaded PDF by ID, also set `MANUAL_PDF_IMAGE` explicitly. Edition
content cannot choose an arbitrary executable or image implementation.

The live `runtime_identity` tool/resource exposes these observations under
`runtime.workers.manual_pdf` and `runtime.workers.practice_verifier`: `reference`,
`expected_image_id`, `observed_image_id`, and `state` (`matched`, `missing`,
`mismatch`, `unknown`), plus available `registry_digests`, `source_revision`, `os`
and `architecture`. Observation inspects local images without pulling or invoking
private code. A matched image is not a native schema, bundle or reopen acceptance.

The QGIS engine is the descriptor's separate `engine.image_id`, not an additional
Web worker selectable by `--worker-images`. The bridge checks that exact engine
before explicit `reopen`; QGIS owns its execution and native observations.
`web://practice-verifier-runtime` supplies declared release/package/profile pins,
while schema calls and operation receipts retain the separate native observations.

The bridge uses `python3 -I -B -m veure_qgis_mcp.cli` **inside** the private image:
`practice-schema --profile ...`, `practice-check`, and explicit `practice-reopen`.
Requests are built from bounded typed fields, not consumer command strings.
There is no private Python import in Web and no local-wheel fallback.

All invocations select an already prepared image with `--pull never`, network
`none`, readonly container root, 2 CPU / 4 GiB / 512 PIDs and bounded output/time.
Schema inspection has no consumer mount; checks have one readonly consumer mount
and no Docker socket. Explicit reopen uses its own receiver workspace and a Docker
socket to let the producer launch the already prepared engine. Reopen algorithms
and engine resource handling remain QGIS-owned. Existing mount encoding, bounded
subprocesses, startup consumer binding and token/session-scoped worker cleanup
are reused; `practice-verifier` is an owned worker role, not a new manager.

A missing private image returns an explicit authenticated-hub-preparation blocker.
No pull, build, token lookup or credential forwarding is attempted. Cleanup must
confirm exact-container absence before any successful operation is returned.

## New edition origin and legacy preservation

For a new v2 edition, the verifier portion is:

```yaml
gis:
  profile: qgis-practice-v2
  verifier:
    origin: prepared-image
    package: unaltracaptura-qgis
    version: 0.6.0
    revision: sha256:4dcd2c40bca4836a202c0c5cc400553b0f134925023b7300e0c0ff2fff1d8492
    image_id: sha256:1fe4a54a42cbac4a6eea596be73425985ab3bca5f28f5871d2fa66d7c0a05f8b
    schema_sha256: 528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb
```

V1 uses its own profile/schema hash above. The independent `gis.bundle` and sender
seal still refer to the original producer, including retained rc2/rc1 bundles.
Legacy installed-wheel configuration shapes remain schema-valid but execution
through this new public runtime explicitly refuses them. Keep their configuration,
receipts and original candidate intact; create a new configuration/edition for the
new origin instead of rewriting history or inventing a `direct_url`.

Web validates the complete common bundle before any product selection. Native
selection must agree with that inventory, include its complete dependency closure,
and satisfy recipient policy. Receipts retain the original producer report and a
separate image/native-execution origin, including bounded execution and teardown.

## Public CI and local acceptance

`Dockerfile.mcp` no longer installs QGIS. The private dependency is declared in
the BOM as external release metadata; the runtime descriptor supplies image pins.
`scripts/check_practice_verifier_runtime.py` checks metadata by default and reports
private checks as `not_run`, even on a machine with private images already present.
`--check-runtime --project ABSOLUTE_ROOT` explicitly opts into native schema/identity
checks. Full bundle/reopen acceptance and independent review remain distinct gates.

The owner built a new **local, unpublished public-Web probe image** from the
already public 0.7.1 base, with only Web source/wheel changes and network disabled.
Absence of the private distribution and `veure_qgis_mcp` module was asserted inside
the public image. It then delegated to the prepared private image above.

Local Web probe configuration ID:
`sha256:555bea3744354cde3f64e5ac7e4a4fd01ff71d8cfcf923336bdb577c89ed809a`;
public source snapshot:
`0de3ebb5bffb0b93291b7144daa3e6b0fbd3f45beed64ed9580f13626fff91f8`.
Its manifest is retained under `tmp/private-verifier-98/public-probe-02/`.
This is an owner acceptance build, not a published or independently reviewed image.

Earlier candidate-04 `17ef…` contains the old embedded private wheel and remains
a private/local historical artifact. Its saved archive must not be attached to
the public Web release. New public release archives must use the Web-only source
boundary and provider-package-absence check exercised here.

Local evidence:

```text
/home/benizar/git/unaltraweb/tmp/private-verifier-98/acceptance-01/evidence.json
SHA-256 99878f6caa002dd3ab22f6559d462418465cc4b12fe36195b39c401065302b97
/home/benizar/git/unaltraweb/tmp/private-verifier-98/acceptance-01/supplement.json
SHA-256 9351c8e7943d7dafdb77f482acdef0e102b5f211c2dca68678bac9e494e7d27a
```

The native v2 composition produces the two PDF/ZIP pairs. Extracted ZIP bytes
replace every selected resource in a new receiver before reopen. Observed engine
mounts contain only the exact selected readonly packet plus provider controls and
output, not the full private bundle/original consumer. Missing/altered final ZIP
dependencies remain refused even after the ZIP hash is recalculated. Native
observations confirm embedded `inici`, 600×640 MDT/ortho, themes and distinct
15,000/75,000 layout frames. Retained v1 data also verifies through the same image.
Wrong image/profile, a producer revision used as verifier identity, legacy origin
and an unavailable runtime are refused. Original fixtures/rc2 configurations remain
unchanged. This is local owner acceptance, not a public-CI or independent-review pass.

## Independent review P2 corrections

The review of PR #104 at `88dd2518` reported three issues; all reproduced before
the fixes (`tmp/private-verifier-98/review-p2-before.log`):

1. PDF delivery now uses hashes returned by the build's original PDF/receipt seal.
   Composition checks and snapshots that seal immediately, before building the
   other recipient. Late PDF edits or replacement/resealing of its receipt cannot
   become authoritative new output hashes. Atomic no-replace publication remains.
2. Existing TinyCSS2 tokenization now covers URL-bearing SVG presentation values,
   including escaped `u\72l(...)`; escaped imports are rejected by token identity.
   Declared local dependencies remain usable. No private producer parser was copied.
3. The shared privacy check includes actual/mapped `_practices` roots, requires
   exclusion and rejects explicit/glob includes, also in standalone PDF preparation.

Regression negatives rehash the edited SVG and replace the PDF receipt to exercise
real resealing attempts. Both output copies must match the original reading seal.
The corrected source needs independent re-review on its committed HEAD. The
external receipt reference was added after the retained local probe; it does not
change executable bridge/compositor bytes or the accepted image/schema selections.
