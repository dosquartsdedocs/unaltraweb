# Published visual companions: native acceptance and release handoff

Tracking: [issue 67](https://github.com/dosquartsdedocs/unaltraweb/issues/67).
Owner branch: `fix/67-published-visual-companions`, based on
`bfabaa2738ddd24725f5e386d60b58a9a8294316` after an eligible primary-checkout
preflight. This is next-release source, not a replacement for published core 0.4.0.

## Selected artifacts

| Provider | Integrated published source | Wheel SHA-256 |
| --- | --- | --- |
| Diavisuals v0.4.0 | `1e842967eabbad4cdb7dcb081493c1c25772dc5f` | `bfedcc9e2554f25ce4a1c33e556f352210848fccb8da800d1c3900dd86c48c93` |
| Vegavisuals v0.4.0 | `68c0b231402ae9485cc34ce530dc5239cb0ec194` | `b52ffa743643dd6b5e0320e7a9aa0cd500ea06262b7d5098c0c3f94a379bc0ea` |

Canonical URLs are in `components.<provider>.reference`; dependency `uv_spec`
values derive from them. Validation binds a wheel's repository, release path,
package/version filename and nonzero SHA-256. Existing exact Git references
remain accepted. No additional component-contract field or wire version is needed.
The published Vega wheel/renderer archive targets Linux/amd64.

Native lifecycle flags, tools/resources and the complete dependency closure are
preserved. Vega consumer scaffold revision now comes from its published commit.
The current native receipts retain their original provider-owned semantics.
This unit does not add a v1 artifact importer or claim domain bundle compatibility.

## Executed acceptance — 2026-09-26

- `make distribution-check`: passed.
- `PYTHONPATH=src python3 -m unittest discover -s test -p 'test_*.py'`:
  544 discovered, 515 passed, 29 optional cases skipped.
- `make wheel-check`: passed against a clean factory-free installed wheel.
- `make mcp-check mcp-smoke`: passed through the owner Docker development images,
  including real stdio and preview/manual-PDF paths.
- `make docs-build`: passed in the published core runtime.
- `test/published_companion_smoke.py`: passed with separate installed published
  wheel CLIs, their tested renderer images and a new temporary consumer with spaces.
  It renders Mermaid, PlantUML, Vega-Lite with retained CSV data, and raw Vega;
  checks actual provider receipts through `site_check`; rejects modified data and
  diagram bytes; then accepts the relocated consumer. No receipt is fabricated.
- `git diff --check`: passed.

Reproduce the provider acceptance after installing the exact BOM wheel URLs and
loading/verifying the renderer archives from their releases:

```bash
PYTHONPATH=src python3 test/published_companion_smoke.py \
  --diavisuals /absolute/published-diavisuals/bin/diavisuals \
  --vegavisuals /absolute/published-vegavisuals/bin/vegavisuals
```

Tested renderer IDs:
`sha256:5a6887b372a0e1c386a7b54981d11ae1910215baeb6a12dfd0706b3e85ef0846`
(Diavisuals) and
`sha256:695125943d0fbc3aa7c877babb9a11a6501bbc7ac265b0975bb5657c60439d98`
(Vega). These identify the release archives' images, not OCI registry RepoDigests.

## Activation and publication order

1. Review/integrate this owner PR and choose the next coordinated core release
   version. Do not rebuild or republish the existing 0.4.0 artifacts under this
   changed BOM. Keep other already integrated editorial/scaffold changes in scope
   when preparing that coherent release.
2. Run the normal candidate/receipt/signing/package release procedure in
   `docs/_documentation/en/40-distribution.md`. Verify installed runtime and
   native receipts against the exact candidate digests; unchanged workers can
   retain their existing reviewed identities.
3. Advance `MCP_RELEASE_IMAGE` only in the normal post-release change, using its
   new receipt. It currently remains
   `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:389bc585cdb4fc89d3372f4896a55fe26e15df38b46bc114ce44fdb3f1c8deb9`.
   A green development manifest does not mean that this older running image has
   acquired the new companion contract.
4. Reconcile hub dependency state and repair the existing unaltraweb client drift
   through normal dependency-aware installation. Reconnect clients and inspect the
   selected runtime's own manifest before updating real consumer scaffolds.
