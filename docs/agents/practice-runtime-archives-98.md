# Web #98 / D1 #33 — prepared controller and PDF archives

**Distribution classification superseded by the private-QGIS decision:** the
historical candidate-04 controller below embeds the rc2 QGIS wheel. Keep it as a
private/local retained artifact; **do not publish that controller archive as a
public Web release asset**. The new public Web controller delegates to QGIS and
must prove provider-package absence before public distribution. The existing PDF
0.7.1 archive remains independently public with its original producer. See
[private-practice-verifier-98.md](private-practice-verifier-98.md).

This is a distribution/export path for the hub's existing H2 immutable
Docker-save loader. Web adds no loader, store, registry, allocator or activation
implementation. Images are already prepared; export neither rebuilds nor renders.

## Retained historical create-only handoff

```text
/tmp/opencode/practice32-web-runtime-archives-candidate04/ready.json
SHA-256 665bd8cea160673f010ffc485c7d54a6ab55deb5cfea6671c46efb84b69d8b5a
```

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| `controller.docker.tar.gz` | 525178465 | `392853842dc49dafe15d10d37a7456d52add2d341b90ff3e3fe8142f66a9f9f3` |
| `manual-pdf.docker.tar.gz` | 340849248 | `b96826e2875e449f0b7cf713bfcc0b4176f53ebb435150dff7e6fe861d9e5c46` |

The controller archive is copied byte-for-byte from the sealed candidate-04
delivery. Only the already existing PDF image was newly exported, using the
bounded `export_image` implementation from `prepare_practice_candidate.py`.
Each tar contains one configuration-ID-selected image and no `RepoTags` aliases.
Archive configuration bytes were hashed against the exact image IDs; source
labels, platform and layer presence were checked without loading or extracting.

| Role | Configuration ID | Actual source |
| --- | --- | --- |
| Controller candidate-04 | `sha256:17ef0d24e8611a6802b3c01ff440e6e552eac728343733198056fdbc6cdf379e` | `sha256:8810efd4f4725eea5910996b790b9704786ef42b683c26e1c4d0ae12be24616e` |
| Published PDF 0.7.1 | `sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa` | `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1` |

The PDF registry reference remains:

```text
ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b
```

`runtime-archives.json` records each archive, the pre-export image observation,
its independently checked configuration/producer and the offline selection.
`ready.json` is written last and hashes both archives and that manifest. This
handoff is still candidate-04, not a claim that the future C072 source or the
independent-PDF change is already inside that immutable image.

## Reproduce an export after a reviewed image selection

`scripts/export_practice_runtime_archives.py` accepts an explicit immutable
controller reference, expected configuration ID and expected source label.
It obtains the PDF digest and its separate producer from the existing component
BOM/deployment record. A mismatched PDF source fails before any export.

```bash
python3 scripts/export_practice_runtime_archives.py \
  --output /tmp/opencode/NEW-CREATE-ONLY-ARCHIVE-DELIVERY \
  --controller-image "$CONTROLLER_REFERENCE" \
  --controller-id "$CONTROLLER_ID" \
  --controller-source "$CONTROLLER_SOURCE" \
  --pdf-id "$PDF_ID"
```

Optional `--controller-archive PATH --controller-archive-sha256 SHA` reuses an
already sealed archive exactly. Outputs must be new, non-symlink directories
under factory `tmp/` or `/tmp/opencode/`. The operator supplies reviewed identities;
the command does not discover or pull a replacement image.

## H2/native loading and the digest distinction

The hub verifies `ready.json`, copies the files into its existing persistent
store and invokes H2 with the declared image IDs. H2 owns loading, alias
preservation and activation receipts. Web has not invoked `docker load` here.

Docker-save does not promise to restore registry `RepoDigests` on a fresh host.
The registry digest above is an honest pre-export/provenance record, not an
invented post-load observation. After H2 loading, the existing native selector can
use configuration IDs directly:

```text
serve --project ABSOLUTE_CONSUMER --image CONTROLLER_ID
      --expected-image-id CONTROLLER_ID --managed --offline
      --worker-images '{"manual_pdf":{"reference":"PDF_ID","expected_image_id":"PDF_ID"},"practice_verifier":{"reference":"QGIS_CONTROLLER_ID","expected_image_id":"QGIS_CONTROLLER_ID"}}'
```

For the new Web-only controller, replace the schematic values with the full
`sha256:...` IDs from the public archive manifest and external private-runtime
descriptor. The complete pinned worker JSON and precise `runtime_identity`
observations are documented in
[private-practice-verifier-98.md](private-practice-verifier-98.md#selection-and-native-boundary).
The QGIS engine is declared separately in that descriptor and checked before
native `reopen`; it is not another Web `--worker-images` entry.
For a one-shot CLI/Make without an active MCP runtime, explicitly pass
`MANUAL_PDF_IMAGE=PDF_ID` as well. The published BOM/workflow digest is not rewritten.
If an operation requires the registry digest to be present locally, the native
alternative is explicit preparation/pull of that exact GHCR reference and an
ID check; no new resolver or silent build/pull fallback is introduced.

## External private dependency declaration

The public `runtime-archives.json` image inventory contains only the accepted
Web-only `controller` and the separately produced public `manual_pdf`. The existing
exporter emits those two image rows. Its receipt must never list the private QGIS
archive or any older Web controller that embeds QGIS bytes as public assets.

The exact package-owned `practice-verifier-runtime.json` accompanies the public
handoff as metadata, with its own file hash in the handoff inventory. It declares
QGIS as private and hub-prepared, and `release.receipt` points to:

```text
https://github.com/dosquartsdedocs/unaltracaptura-qgis/releases/download/v0.6.0/release.json
1251 bytes; SHA-256 45db1e016e666126e5a51f157be0be1066aaa08f32042f5907d46e0e7da1e404
```

H2 preparation consumes this external producer receipt through the hub's
authenticated acquisition path, verifies its hash and declared archive, and
checks both prepared image IDs. Web's declaration does not fetch, mirror or
re-export that receipt/archive, and does not create an attestation for QGIS.
The native package/schema identity remains separate from this release provenance.
The descriptor is public metadata; the QGIS wheel, archive and implementation
remain private. No credentials belong in either handoff.

## Public release assets and the existing publisher boundary

The language-package publisher accepts only its exact wheel/gem inventory and
its strict `release-candidates.json` fields. Docker archives must not be inserted
into that staging directory, its `SHA256SUMS`, or the old container receipt rows.

At the authorised release turn, publish only the accepted public Web-only
controller archive and the public PDF archive, with their separate
`runtime-archives.json`/ready receipt and external-dependency descriptor as
**additional GitHub Release assets**, with a separate `RUNTIME-SHA256SUMS`,
through the existing native `gh release upload`
operation. Use new asset names and never `--clobber`; retain the immutable GHCR
references and provenance alongside them. This is artifact attachment, not a new
runtime manager or a modification of the PyPI/RubyGems publisher.

For the final tool release, export its newly reviewed controller and record its
own producing commit. Reuse the selected PDF 0.7.1 archive/digest and producer
`b7ec1d…` honestly; do not attribute those existing bytes to C072 or retag them as
a newly built PDF. The current candidate archives and receipts stay unchanged
and retain the private/local classification above. Until the new public release
assets exist, H2 may use that explicitly private local handoff; public acquisition
uses only already public GHCR images, never private wheel-containing candidates.
