# Web #109 — QGIS 0.6.1 compatibility point

Web **0.7.3 is prepared locally**, not yet published or selected by a real
consumer. This maintenance point changes the exact external private-QGIS
dependency from 0.6.0 to 0.6.1. Published Web 0.7.2 remains immutable.

Provider handoff: [Web #109](https://github.com/dosquartsdedocs/unaltraweb/issues/109#issuecomment-6283746978).
Hub preparation: [gaContExt #38](https://github.com/dosquartsdedocs/gacontext/issues/38#issuecomment-6301327451).
The latter has prepared/enrolled QGIS independently; it has not selected this new
Web point or changed a real consumer cohort.

## Exact private dependency

All inputs below were downloaded through authenticated GitHub acquisition into
ignored `tmp/qgis-061-adoption-109/assets/`, then checked by bytes and SHA-256.
Only the public metadata descriptor travels in Web; no private source, wheel,
archive or credentials are included in the public wheel or image.

| Identity | Value |
| --- | --- |
| QGIS source/tag | `1ca6ed95195d44097057d7165dc5dc0730cdf1c0`, `v0.6.1` |
| External `release.json` | 1251 bytes, `c09148927767855e6694e246ae38a9bdda4181086d18f78c204999648ec1089c` |
| Private wheel | 334648 bytes, `89998d9e41dcc90b8768ac036bf480e3501138d715824e12f928ab15f75dfbb7` |
| Private two-image archive | 1372056314 bytes, `fa870962e40bf416aeea262047b32a148bb3a73f8ae2dff6cbd4b20426453d1d` |
| Controller configuration ID | `sha256:d06b742c3e7d2e9383cf8a1d22bce928dd806f316a0bcbb1f676f50e22e94b05` |
| Auxiliary QGIS engine | `sha256:1003721d96abe9607d8337b36851f9b29f84c2f8f92b377d1a73ff03c9d15cd2` |
| Release producer revision | `sha256:35443a3343f403892b387c1622656ff3a242044b890fe4ea0cd1e66dd52653e1` |
| Native `practice-schema` revision | `sha256:4604801be887a19747aa74c84a2d99141308fadde44f5cddacb4d821b6861398` |
| Separately scoped published D0 code revision | `sha256:8e5f451cd0669c80e17c6b1b72f3e22dce53dbd405098ef67f6980cf759553bc` |
| Web descriptor SHA-256 | `8f2ff3531ad2a65fab9992ac5ef01d3cec65b88625ee26d5b2149be8ad065b99` |

The canonical private receipt URL is
`https://github.com/dosquartsdedocs/unaltracaptura-qgis/releases/download/v0.6.1/release.json`.
Its source, version, producer, wheel and two images match the Web declaration.
The archive checksum, both configuration hashes, platform and declared layer
presence were checked without extracting/loading/retagging the archive.
The controller OCI source label remains actually absent (`null`), not the Git SHA.

The native practice fingerprint is **4604801b…**, observed both through the
installed provider CLI and inside its pinned controller. The D0 fingerprint
**8e5f451c…** cannot replace it: an initial schema probe using that other scope
was refused. Both v1/v2 probes pass with the native practice revision. Regression
tests reject the old 0.6.0 revision, the D0 revision and the release producer as
substitutes. The schema hashes remain respectively
`9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445` and
`528c8be229c72c346f134ffaa60094f94224094a25b6fb11bcc87802ddc7fffb`.

`practice_verifier` remains the Web startup worker role. `engine.image_id` is the
separate QGIS auxiliary, checked before native reopen, not a `qgis` entry in Web
`--worker-images`. The bridge and lifecycle implementation are unchanged.
PDF 0.7.1, its producer `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1`, core/workflow
`3332e0b93933f12317e05f1ce8d38ce80046feab`, Dia 0.5.0 and Vega 0.5.1 retain their
independent selections. Public CI reports private execution as `not_run`.

## Local synthetic acceptance

`test/qgis_compatibility_smoke.py` accepts explicit already-acquired inputs and
immutable image IDs. Its only GIS input is the provider's pinned
`examples/portable-practice/`: two invented projected points, an 80 m buffer and
a 32×24 synthetic raster. No manual, real dataset or existing screenshot is used.
The provider example stays outside Git/public packages and its source blobs and
hashes are retained alongside the downloaded inputs.

The complete passing run is
`tmp/qgis-061-adoption-109/local-acceptance-03/evidence.json`, SHA-256
`3122e0751813ad24f0f2456adae84c792f7d3b0693bc504f3d9d73a30201a6fc`.

- Local Web-only image: `sha256:765b10855cc70f5cdaf18d998bac8cdbe60621c3a8fcbc90f66bca8a02c0dfc7`.
- Local wheel: `14fca099e7b725a0041f42bc32dfdb80bc34c454d5983bfda9ffbc090fe17827`.
- Descriptor bytes match the source, built wheel and installed Web image.
- Real MCP initialization, both practice `resources/read`, worker identity and
  dry-run/actual composition pass with the fresh installed host launcher.
- The native QGIS run retains eight successful controls, two GeoPackages, one
  raster, two portable projects and its synthetic capture/bundle.
- Each recipient receives a PDF and ZIP. Exact declared ZIP membership, member
  hashes, PDF bytes/receipts, readable pages, recipient-specific text and retained
  original inputs are checked. Repeated composition refuses overwrite.
- Selected packet bytes extracted from each ZIP are rechecked and reopened in
  QGIS. The observed engine uses only the selected readonly packet, network none,
  and its exact CID is absent afterward. Private verifier teardown and Web
  drain/EOF/session-status confirm resource release.

Attempts 01/02 are retained: the acceptance driver initially inherited the host
test `PYTHONPATH` in its wheel-install/session-status subprocesses. The driver now
scrubs that environment, as it already did for the MCP launch. These were test
driver failures, not successful installed acceptance or changes to production
transport. The complete attempt 03 passes with the same Web package/runtime.

Host suite: **731 discovered, 703 passed, 28 explicit optional skips**.
`distribution-check`, `workflow-check`, `wheel-check`, `gem-check`, `mcp-check`
and the full `mcp-smoke` pass. `docs-build` also passes. Docker Make checks use issue-owned development
names (`unaltraweb:issue109-073`, `unaltraweb-mcp:issue109-073` and
`unaltraweb-manual-pdf:issue109-073`), not published aliases. Gem checks execute
inside that prepared Web image with network disabled.
The wheel gate additionally checks descriptor/BOM byte equality and absence of
private QGIS package roots. Exact-head review/CI precede integration and immutable
publication.

## Publication and adoption gates

Use the normal reviewed-source image/package workflows and receipt-only release
commit. Reverify exact downloaded Web artifacts and the same descriptor against
the final candidates; retain the public controller/PDF archives separately from
the private QGIS dependency. Do not publish the private intake directory.

Return final immutable Web/package/descriptor/receipt/image references to
gaContExt #38. The hub then owns new preparation, compatibility curation and any
explicit consumer CAS selection/reload. Local acceptance, verified publication
and actual consumer adoption are distinct states. No teaching approval, scientific
manual recomputation, W1/SDK expansion or automatic consumer migration is claimed.
