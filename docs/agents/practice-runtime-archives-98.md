# Web #98 / D1 #33 — prepared controller and PDF archives

This is a distribution/export path for the hub's existing H2 immutable
Docker-save loader. Web adds no loader, store, registry, allocator or activation
implementation. Images are already prepared; export neither rebuilds nor renders.

## Current create-only handoff

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
      --worker-images {"manual_pdf":{"reference":"PDF_ID","expected_image_id":"PDF_ID"}}
```

Replace the schematic values with the full `sha256:...` IDs from the manifest.
For a one-shot CLI/Make without an active MCP runtime, explicitly pass
`MANUAL_PDF_IMAGE=PDF_ID` as well. The published BOM/workflow digest is not rewritten.
If an operation requires the registry digest to be present locally, the native
alternative is explicit preparation/pull of that exact GHCR reference and an
ID check; no new resolver or silent build/pull fallback is introduced.

## Public release assets and the existing publisher boundary

The language-package publisher accepts only its exact wheel/gem inventory and
its strict `release-candidates.json` fields. Docker archives must not be inserted
into that staging directory, its `SHA256SUMS`, or the old container receipt rows.

At the authorised release turn, publish the two archives and their separate
`runtime-archives.json`/ready receipt as **additional GitHub Release assets**, with
a separate `RUNTIME-SHA256SUMS`, through the existing native `gh release upload`
operation. Use new asset names and never `--clobber`; retain the immutable GHCR
references and provenance alongside them. This is artifact attachment, not a new
runtime manager or a modification of the PyPI/RubyGems publisher.

For the final tool release, export its newly reviewed controller and record its
own producing commit. Reuse the selected PDF 0.7.1 archive/digest and producer
`b7ec1d…` honestly; do not attribute those existing bytes to C072 or retag them as
a newly built PDF. The current candidate archives and receipts stay unchanged.
Until those release assets exist, the two native routes remain the verified local
H2 handoff above or explicit acquisition from the recorded GHCR digest.
