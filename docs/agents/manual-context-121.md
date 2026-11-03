# Manual context producer — #121

Workspace: `/home/benizar/git/unaltraweb`; branch `feat/121-manual-context-export`.
The initial [PR122](https://github.com/dosquartsdedocs/unaltraweb/pull/122) contained the
post-release pin (`59bd62b`), first bound exporter (`cbf7260`) and resolver/check
continuation. That initial delivery preceded the authorized integration and
publication recorded below.

## Interface and contract

- MCP: `manual_context_export(name, language="", chapters=None, sections=None)`.
- CLI: `unaltraweb-mcp --project /absolute/manual mcp manual-context-export
  --name RUN [--language ca] [--chapter REF ...] [--section REF#ANCHOR ...]`.
- Resource: `web://manual-context-schema`.
- The export uses its connection's workspace; the MCP has no root argument.
- `unaltraweb.manual.id` is an explicit stable logical identity. Text selection
  preserves refs, native order and exact non-overlapping blocks; section selection
  is exact, not an implicit subtree expansion.
- The schema bytes match Itemarium's supplied v1 exactly:
  `e099d6f01af87a9f95ae828a8abc5ef69fb61f8d3fdfb8e5886d478cb60bd1c8`.
- Production has no Itemarium dependency. Native factory helpers are required,
  as declared by the wheel/CLI contract. A bounded snapshot, native statuses,
  complete provider receipts and final source/identity rechecks precede sealing.

See the [author guide](../_documentation/en/47-manual-context.md) for supported
components, fingerprint closure, retention, limits and refusal remediation.

## Acceptance evidence

First actual exporter invocation (one chapter, three blocks, one static PNG):

- `tmp/manual-context-121-first/manual-fixture/tmp/manual-context/v1/manual-context.tar.gz`
- SHA256 `414327f240684aa3e66f609d00017d9e1b8d6ced5a0ec7de4d0d0dd53e0bb256`.
- `tmp/manual-context-121-first-conformance/receipt.json`: consumer check, import
  and backup/reopening passed. This early artifact predates the additional guards
  and generated-resource adapter; it is retained separately from final evidence.

Final producer test used the installed package in an explicitly built, network-
disabled, read-only-root Docker MCP, with only its synthetic manual mounted:

- Image ID `sha256:f01c5e220ad635588d0e545eb3294e8550da71c90a59eaab9a91ad7d334c8873`.
- Producer version **0.8.0 development**; code revision
  `sha256:322eb2f79d7c275c0dc9e6ce554a7d4fa82f63cb8a259cdd4b3413ecc5b3ca56`.
  The host source fingerprint matches this observed installed producer exactly.
- Both stdio instances expose the bound tool, refuse a second use of the export
  name, drain, close and leave their exact fixture container absent.
- The real CLI also exported one selected block with its figure successfully.
- Producer receipt: `tmp/manual-context-121-final/producer-receipt.json`, SHA256
  `8482b2c44dc5885a683a94314f59c0077f104e58c0f6312f2c2454c8512b41a0`.

Packages below `tmp/manual-context-121-final/manual-fixture/`:

| Version | Path | SHA256 |
| --- | --- | --- |
| First: 1 chapter / 3 blocks / 1 figure | `tmp/manual-context/v1/manual-context.tar.gz` | `4ecb3014dc57c66962bead52c8ab42a1233e23c8ddc29c3bb5cecf82cc6801b3` |
| Next: 2 chapters / 4 blocks / 1 figure | `tmp/manual-context/v2/manual-context.tar.gz` | `b60909760352c74b921d077924a05f873d3cf144ae6aabf906e100b9b3a824d4` |

Both have manual ID `fixture-manual-121`, language `ca`, `dirty:false`; source
revisions are `4f507b56ba2fcdb3fc59f727066427639776841d` and
`5165919651d1140b7382d5f148e84fa54feb67fc`. Fingerprints change with the sources;
refs and the prior bank remain stable.

Itemarium's independent runner consumed **these exact two exporter archives**:

- Engine 0.6.2, source SHA256
  `1a8983100c4b0c72bac74912fdde7a4d8ad14ce9970e188f13aae611dbeee813`.
- Receipt: `tmp/manual-context-121-final-conformance/receipt.json`, SHA256
  `f5a5579377f3513f6b1d2e796cb8c99723dabe530f9de6425da517f36e13aad3`.
- PASS: schema/integrity/resource closure; isolated import; preservation of all
  existing bank state when the second version adds one bank; backup reopening in
  a second app after removal of the first fixture app.
- Backup SHA256 `ed8062db688001911bcdca68c23d33135208bfdc89375e1f3a7c1df843016bd0`.
- The consumer's `producer_export_invoked:false` correctly describes its own
  runner; the separate producer receipt proves actual MCP export invocation.
  No manual checkout was supplied to Itemarium. No questions or real teacher data
  were used; functional conformance is not teaching-bank quality certification.

## Checks and observations

- Full suite: **763 cases, 735 passed, 28 expected skips** with the prepared Python
  environment (`PATH=.../public-env/bin:$PATH PYTHONPATH=src python3 -m unittest
  discover -s test -p 'test_*.py'`). The bare system Python lacks existing pypdf /
  tinycss2 dependencies; that failed attempt is not a passing suite.
- 21 exporter cases cover static/HTML figures, language fallback and translated
  diagrams, components/includes/citations, generated chapter/computation checks,
  edited byte evidence, Vega local-data receipts, web captures, stale/modified/
  unmanaged/missing outputs, unsafe resources, concurrent changes and retention.
  Generated-resource unit fixtures carry synthetic native records; they do not
  claim fresh renderer execution.
- `distribution-check`, `workflow-check`, clean installed `wheel-check`: PASS.
- `make mcp-check`, `make mcp-smoke`: PASS.
- `make docs-build DOCKER_IMAGE=unaltraweb:dev`: PASS; prose check of the new guide:
  no findings. The initial default-image docs command refused unpublished 0.8.0.
- Gem build/package inspection: PASS inside the prepared MCP image with its Ruby,
  network disabled and source mounted read-only. The host-only default attempt
  refused the unpublished 0.8.0 runtime rather than pulling it.
- `git diff --check`: PASS. Initial CI's old hardcoded 0.7.3 launcher expectation
  was updated to the verified 0.7.4 digest; no release gate was relaxed.

## Remaining integration boundaries

The receiver refuses all SVG `<image>` nodes, including embedded PNGs, and PDF.
Native capture freshness is checked, but such effective assets are refused rather
than rasterized or substituted. QGIS context-v1 provenance has no adapter in this
increment; recognizable QGIS captures get an explicit unsupported diagnostic.
Interactive/arbitrary Liquid and undeclared outputs also fail closed. These
limitations are recorded on #121 for producer/receiver coordination.

At initial source delivery, version 0.8.0 had publication status **pending**. The checkout
launcher then selected published 0.7.4; observation of this conversation's existing
MCP still showed installed **0.7.3**, instance `ecac06618bd3436794e89c31746b8914`,
bound to this checkout. It was not hot-reloaded or rebound. Hub admission belongs
to gaContExt #52, and real-manual selection/author review remain separate.

The #116 checkpoint remains on `feat/116-common-practice-sdk`; it is not included
in this branch or attributed to these exports.

## Authorized publication follow-up — 2026-11-03

After the source delivery above, the user authorized continuing toward hub
integration. PR122's final source and both CI runs remain green. Itemarium also
independently rechecked the exact exporter archives in network-disabled isolation
with no manual checkout: all four conformance checks passed, receiver receipt
`15b8561e1e55899b57d8e45b8d19b7a8eeaa669808cf729d29eac3589a3231fb`
([receiver return](https://github.com/dosquartsdedocs/unaltraweb/issues/121#issuecomment-6597815786)).

The four new Web components were marked release-ready for the normal signed
candidate, receipt-only merge/tag and trusted publication workflow. Independent
core/gem, workflow, PDF and QGIS selections retain their previously verified
identities. This source readiness is not a claim of published bytes or admission.

GaContExt #52 specifically concerns admitting newer **Itemarium** native builds.
The new Web tuple must also be delivered to the hub owner after publication;
neither publication alone nor the existing consumer conformance receipt proves
hub admission, selected-client activation or an export of a real teaching manual.

## Published 0.8.0 and verified intake

[Release v0.8.0](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.8.0)
is published. PR122 supplies source `54afe7588c36e959a7eb75d5f52763a7456108d7`;
receipt-only PR123 supplies tag target `f71aeea75e11f4c2b15df4451f47ddd8a161bd8b`.
Annotated tag object: `eca74d75783bd6630a47376bd1a3076912a1a087`.
Receipt SHA256: `a2bf883ea62a4f164c925fa477e756378d0590f8dc6bbcdc54c17b645a7896da`.

- Wheel: `4dcec737596b4e4742e04b50a70b81d04ffadf993139e6ba1d1bce665ece4816`.
- Gem: `bbc3dbbc106b69d7a677608c46bf1d4f64d7016a48b27301022ec71e5a378f79`.
- Controller OCI: `ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:8b41abacad9ca2894755db7f3587a6b47c8fa8f536d88a151bdfc4ae53ba7f08`.
- Controller config ID: `sha256:e0502369c85c59f9e512fbd9fdb17dbc128845d057a1423375425e68ce2e79a2`.
- Runtime OCI: `ghcr.io/dosquartsdedocs/unaltraweb@sha256:d58d8f68cf08a76e9b9f3ef238a0917b856cf7152aa5cc4a6f54ca109e1ac3fe`.
- Runtime config ID: `sha256:c0ec72478618c3e7a9444cd7ae9120317a18757019b2fbf8f0438ca451695731`.

Complete [release-handoff.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.0/release-handoff.json),
SHA256 `7a7cab1d48e3302af5f21309e57b540d7ca81eb4d8c0f36c7a5da7099538a53a`,
lists every asset, untagged Docker archive, independent worker and native profile.
Core `9d97197` / gem 0.7.3, workflow `3332e0b`, PDF 0.7.1 and classic QGIS 0.6.1 are preserved.

Signed candidate run `41641425949`, package preparation `41641430158`, Trusted
Publishing `41687937608`, OCI promotion `41687938131` and tag CI `41687888720`
passed. The exact controller's 40 package modules match the CI wheel. Its new
code fingerprint is `sha256:a678d2b2649e3479d0049ca0ca8a500aba5bb3f0a59b070cd7aaf5c0c6b466d0`;
the earlier development image/receipts above are retained as their own evidence.

The exact installed release controller exported two new fixture packages:
`9bc3b4506a3f04c66631e7bcc3617b558879af95ee29f6c3b8fead870826afa7` and
`7225f7c00f0992c922048608b622eec9a9d6d4b6a1c18049b32c2b5ffba7eb40`.
Itemarium 0.6.2 again passed all four checks on these exact bytes. Release assets
`producer-acceptance.json` and `consumer-conformance.json` have SHA256
`4a8ae9db55757b584b24b9b1602ffe94e566cd4531016a073c7afc31e78f4e48` and
`af73eba0cee0c447072df269572c22164dd8aca2eb0ea73e2416170056cd4e63`.

All 18 original assets were downloaded anonymously and hash/size checked,
including both image archives; PyPI/RubyGems copies and OCI aliases matched.
[verification.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.0/verification.json)
has SHA256 `ec04ac1714a1b00c2f8e14f415e0fb0e21a195e42c5848ce53694ce0b85ed403`.
The downloaded public wheel was installed in a fresh environment: actual MCP
discovery reports 65 tools, its bound exporter produces a valid package, and
Itemarium's independent check passes without importing it.
[public-installation.json](https://github.com/dosquartsdedocs/unaltraweb/releases/download/v0.8.0/public-installation.json)
has SHA256 `b94920fd618d50ba384207d3e2a126ccd4b1cf98b697760d4d27c09f6b80cf75`.

Post-release verification of the updated checkout pin passes distribution/workflow
checks, the public-image bootstrap check/smoke and the full local suite: 763 cases,
736 passed and 27 skips in that prepared environment.

The post-release checkout pin now selects the published 0.8.0 controller. The
configured hub's immutable `cbb753e4…` controls still admit Web only through 0.7.4;
this is an observed admission boundary, not a missing producer release. The full
intake is [gaContExt #54](https://github.com/dosquartsdedocs/gacontext/issues/54),
alongside Itemarium's separate #52. No hub registry, other client registration or
real manual was changed here. Source selection, hub admission and live client
activation remain distinct.
