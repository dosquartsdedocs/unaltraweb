# Manual context producer — #121

Workspace: `/home/benizar/git/unaltraweb`; branch `feat/121-manual-context-export`.
[Draft PR122](https://github.com/dosquartsdedocs/unaltraweb/pull/122) contains the
post-release pin (`59bd62b`), first bound exporter (`cbf7260`) and resolver/check
continuation. No merge or public release is part of this delivery.

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

The source version is 0.8.0 with publication status **pending**. The checkout
launcher now selects published 0.7.4; observation of this conversation's existing
MCP still showed installed **0.7.3**, instance `ecac06618bd3436794e89c31746b8914`,
bound to this checkout. It was not hot-reloaded or rebound. Hub admission belongs
to gaContExt #52, and real-manual selection/author review remain separate.

The #116 checkpoint remains on `feat/116-common-practice-sdk`; it is not included
in this branch or attributed to these exports.
