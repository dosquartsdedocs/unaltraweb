# Manual context 0.8.1 publication (#121)

Authorized closeout `gacontext-family-closeout-20261104-unaltraweb-release-436ccc8f65f641eda40c258aa79a70bf`.

## Source and review

- PR125 review merge: `02b3c0872f20b85e83a636a073c2d94fc38c2af6`.
- PR126 final head: `0163e6648092c36e06dd9fdd408902ace5dd4d6e`.
- PR126 source merge: **`b29691ed196295b9f1f1cb64eea6650ab8ff76d1`**.
- PR127 receipt-only merge / tag target: **`499af3dfebee2d2bd061ce0df24ee4200f7c2786`**.
- Annotated `v0.8.1` object: `a5a8ef3cef95906c0d972cb8777ae4b0667d7d63`.
- Receipt SHA-256: `642485365b890f678e348a6765bc8cbd9ea11aad8a1e6ae5bf1a43e207eeb520`.

Review discussion4471006805 was reproduced and resolved, not dismissed on green
CI: anchored YAML computation data is opaque, while configuration reads still
validate YAML even after an opaque copy. Full local suite: 774 tests, 28 skipped.
Distribution/workflow/diff, MCP check/smoke and docs build pass. Final PR126 CI
41888685623 and CodeQL41888685571 pass; receipt PR127 CI41891258122 passes.

## Published tuple

[Release](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.8.1).
The complete URL/SHA-256/size inventory, descriptors, independent component BOM,
runtime archive metadata and original producer/receiver evidence are in
[release-handoff.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.1/release-handoff.json),
SHA-256 **`c1f137a6b83c97787d5677b3410a825e3dbe629f1e40e5a0862ada345ad7d2c7`**.

- MCP OCI: `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:a4f4f1b61f30bfef550f23a33ec3ef0aa789539adf3981a08e549ff2354d05ec`.
- MCP config ID: `sha256:9201cae3d14965614f660b7473ba621838542fe69c7db0c2329d5a72d30ba19f`.
- Runtime OCI: `ghcr.io/dosquartsdedocs/unaltraweb@sha256:9bde840b54fb2166e25d3b14381540b955036f2a67d598abc3f1d8536e85bd7f`.
- Wheel SHA-256: `1f90ecc5499094f12e1cf1c07b6ac614c04bb4f55b70f1c6239f11f97a18012e`.
- Gem artifact SHA-256: `6ff08588653e4797282dbaf3c1a1caef2fc0c63663cfe20f1c72c7361a8c00dd`.
- Controller Docker-save archive: 489218314 bytes, SHA-256 `1e6135749e8f28896666d0c2ae0673acd4e5b28c0f46681352ed59b366682342`.

Signed image workflow41889676280, package preparation41889682943, trusted
publication41892295272, OCI promotion41892301647 and tag CI41892270973 pass.
All 77 installed package files equal the recorded wheel. Independent pins stay
core9d97197/native gem0.7.3, workflow3332e0b, PDF0.7.1 and classic QGIS0.6.1.
PDF archive bytes are reused from the existing v0.8.0 URL and enrolled keeper;
`runtime-archives.json`, `ready.json` and the handoff record that external URL.
No redundant PDF transfer archive is created for this release.

## Published-byte and cold-install proof

Anonymous streamed verification covered all 20 initial release assets plus the
reused PDF URL, and matched PyPI/RubyGems downloads to the recorded candidates.
Large archives were hashed without retaining redundant download copies.

- [public-verification.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.1/public-verification.json):
  `a739426c312a66f54846ce1bda100d168c490fb6861174754390d972ecd6b782`.
- [public-installation.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.1/public-installation.json):
  `c39f1b6c352e5b8113bad964f9c1aa1d7aff338e63b1bfbe21c7b9763f7f77b3`.

The public wheel was installed in a new venv, not editable. Its real MCP
connection reports installed0.8.1/no drift and 65 tools, exports the selected
synthetic chapter, drains and closes. Factory assets are explicitly supplied
from the release source checkout. This does not claim a wheel bundles renderers.

## Original fixture evidence and downstream boundary

Published `fixture-first.tar.gz` SHA-256
`2608c7ccc6c7135bb1713830cc44e6ccfef703d7faad974f22a207dc7d26dc7d`
and `fixture-next.tar.gz` SHA-256
`8b9f948b0112019e8c120cbd7417d7e32a68054299122720e0824516f373668b`
are the original installed-MCP exports with private CSV/YAML and HTML metadata.
Producer revision: `sha256:8034f6b943d13cc1b91b2ee37f192e8721c9f42d5afd771f88dbeb2e8b52211a`.
Itemarium0.6.2 independently passes integrity/import/preservation/backup on these
same bytes; consumer receipt SHA-256
`c80e9f36729ac472d2c8b9bdeddbf55170ac257d52b91d3fe8e6bc1daab4f69b`.

Evidence retained under `tmp/release-081-121/`. Earlier candidate evidence is
historical and remains separately identified. This release is ready for a new
hub intake; admission, manual selection and live client identity remain separate.
TIGIT must export its original real package after adoption. No real banks,
questions or teaching content were changed. PDF/SVG-raster/QGIS-context limits
remain; #116 checkpoint6a8cd85 and WEB-2 work are excluded and preserved.
