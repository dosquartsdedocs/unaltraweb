# unaltraweb 0.7.1 delivery closeout

Published **2026-10-07 12:33:20 UTC**:
[v0.7.1](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.7.1).
Owner: [issue 93](https://github.com/dosquartsdedocs/unaltraweb/issues/93).
This report supersedes the chronological preparation states in
[deployment-integration-0.7.1.md](deployment-integration-0.7.1.md).

## Delivered behavior

The package owns independent immutable core/workflow pins and exact PDF
digest/producer records. The reusable workflow fetches bounded strict JSON from
its own defining provider revision, not the consumer checkout. Release readiness
checks that selected workflow and its records. CI generates a caller, executes
its actual selected provenance gates and compares retained-document verifier
bytes across the selected core, controller and PDF worker.

The exact issue-86 hotfix is recognized by the original baseline hash and current
file hash, listed in the update plan and bound to its SHA. Extra local edits
remain conflicts; existing confinement, staging, CAS and rollback are retained.
The new/upgrade/hotfix installed acceptance preserves author and generated-cache
hashes while building and probing actual web/PDF output.

The owner explicitly authorized the full 0.7.1 review, integration, gated
publication and post-release pin. Work used one authoritative checkout and serial
ordinary branches. Reviews are agent-attributed, not human approval. Published
earlier artifacts and real consumer selections remain intact.

## Source and receipt lineage

| Role | Revision / evidence |
| --- | --- |
| Implementation | `2133b8fa2f668e14d603a36d15584eed63e4386a`, [PR 94](https://github.com/dosquartsdedocs/unaltraweb/pull/94) |
| Initial implementation integration | `2ff27f27c274eb09b2c53ef8bd374f333702d8ee` |
| Initial candidate source, later rejected as a core tuple | `b7ec1d7a139c65b3b0b88699cdbeb19080f13be1`, [PR 95](https://github.com/dosquartsdedocs/unaltraweb/pull/95) |
| Worker-record/checker-closure correction | `1ce0e2039e3cb59ed57dbef7961193c7de9ea751`, [PR 96](https://github.com/dosquartsdedocs/unaltraweb/pull/96) |
| Selected reviewed core and workflow | `3332e0b93933f12317e05f1ce8d38ce80046feab` |
| Final tuple selection | `18d8d20ba92e397b8341f91207ae05cb6146473b`, [PR 97](https://github.com/dosquartsdedocs/unaltraweb/pull/97) |
| Final artifact-producing source | `ae5dab1d99804e7f73da82930199c1e2f3c08f61` |
| Receipt-only child | `24834dcc3e2e03f0bb76b5f18c2fbe346b143455` |
| Receipt integration / tag target | `1ff25c6956458c3a99436312466e9cc588ed34b9`, [PR 99](https://github.com/dosquartsdedocs/unaltraweb/pull/99) |
| Annotated tag object | `6e8d7f107a6bfa013a400db0e2a3cb6269d37e38` |

The tag target's first parent is exactly the final artifact source; its
first-parent diff contains only `release-candidates.json`. Native package-run
authorization/staging, strict distribution/ancestry/publication-ref checks and
annotated-tag verification passed before publication.

[Tagged receipt](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.7.1/release-candidates.json)
SHA-256: `feda4f19b4133e60b4dae3cf88367ae8089c88077b4ac3fcfccc76d153411f2e`.

| Component | Artifact / repository | SHA-256 / OCI index digest |
| --- | --- | --- |
| Gem | `unaltraweb-0.7.1.gem` | `6371e502601f970bc30711868b0eb2a29f429e1b78e21ac71ac09696b108baee` |
| Wheel | `unaltraweb_mcp-0.7.1-py3-none-any.whl` | `cd2a06a2d2e16758c916d640e71210b16285fe3848cc987651801ff324a50a8e` |
| Base runtime | `ghcr.io/dosquartsdedocs/unaltraweb` | `sha256:af776cfcd79f2778d36e179dccba63792d820d1939fd89187b7af7089e11247a` |
| MCP | `ghcr.io/dosquartsdedocs/unaltraweb-mcp` | `sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6` |

Linux/amd64 configuration IDs, distinct from registry index digests:

- Runtime: `sha256:7b58b0ad1e7fdfd00087b6702c7002b4a4d393072077def17ff5fb1e198c8cfb`.
- MCP: `sha256:f0e7915527fa68a67448287e131ec431aeae902b8269856e4e219e67faade146`.

Both revision labels identify the final artifact source. Both `0.7.1` and
`v0.7.1` aliases were inspected anonymously and match the receipt. Public registry
downloads and downloaded GitHub assets match their hashes. `SHA256SUMS` itself
has SHA-256 `10938774ef08dabd24cbd7853abd2d72957e75c750418ac8ebe7af7c1ce4553b`.

## The PDF compatibility failure was caught before release

The first core candidates reused PDF 0.6.0. Plain manuals passed, but retained
Carta freshness failed because the verifier closure includes the changed
`distribution.py` and component schema. The old worker's successful PDF output
was not accepted as fresh by the new controller. No manifest was edited and no
freshness check was disabled to force a pass.

The signed specialization from the initial image run has the correct 0.7.1
checker bytes and is now selected by immutable digest:

```text
ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b
producer: b7ec1d7a139c65b3b0b88699cdbeb19080f13be1
configuration ID: sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa
native package version: 0.7.1
```

The final four-component receipt reuses this separately verified digest. The
later image workflow also built verification PDF
`sha256:6bc7342a9ad6eb4edfff0d022d7157370e9c9bcba2b87bb80532389cfded62d4`;
it is not the selected worker and received no coordinated semver promotion.
The rejected initial core candidate tuple and local diagnostic overlay remain
clearly separated from final signed-byte acceptance.

## CI, signing and publication

| Gate | Successful run |
| --- | --- |
| Implementation PR CI / CodeQL | [37526811887](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37526811887) / [37526811747](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37526811747) |
| Initial signed images / packages | [37530306398](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37530306398) / [37530310332](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37530310332) |
| Worker-record PR CI / CodeQL | [37534571592](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37534571592) / [37534571578](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37534571578) |
| Corrected tuple PR CI / CodeQL | [37613153175](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37613153175) / [37613153240](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37613153240) |
| Final source CI / CodeQL | [37613808731](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37613808731) / [37613808758](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37613808758) |
| Final signed images / packages | [37614367552](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37614367552) / [37614371507](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37614371507) |
| Receipt PR CI / CodeQL | [37619948216](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37619948216) / [37619948348](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37619948348) |
| Receipt integration CI / CodeQL | [37620746600](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37620746600) / [37620746542](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37620746542) |
| Tag CI | [37620758376](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37620758376) |
| Image promotion | [37621482487](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37621482487) |
| PyPI/RubyGems Trusted Publishing | [37621486444](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37621486444) |

Final package artifact `11479132691` has archive digest
`sha256:648e84e49abc0af299f7caf1b1d50931da42439d0a58ceb0839ebfa99524893b`.
The signing/test/promotion jobs verified exact digest, source and signer bindings.
The package publisher authorized the run/source/inventory and published only the
staged recorded bytes. Promotion reused the tested image manifests.

## Installed final-byte proofs

The final downloaded wheel and exact signed MCP, without a derived controller,
passed all of these gates:

- `deployment_integration_smoke.py`: new manual, populated 0.5.0 upgrade and exact
  reviewed hotfix. Author/cache hashes were preserved, plans applied, PDF/web/HTTP
  passed and the actual generated workflow pin was exercised.
- `artifact_import_smoke.py`: authenticated Carta seal, original PDF, author prose,
  copied-producer retirement, receiver relocation and forced rebuild. Both composed
  PDFs have 11 pages and hash `1b942d003847126cfdbc14630059bb6ede5512751400b3701dab85a7d37b78a7`;
  the unchanged original letter is on page 10. Integration record hash:
  `e80d504b19677ace36c512f758161d3d5663d38d0979ef8c36bc87be765f9e40`.
- `d0_runtime_smoke.py`: live identity, reconnect/scope, disk drift, busy drain,
  real worker crash recovery, offline/mapping/mismatch checks and actual
  0.7.0 → 0.7.1 → 0.7.0 rollback with retained state.
- `bundler_transition_smoke.py`: all four populated 0.4.0 → 0.7.1 → 0.4.0 profiles,
  two builds and a preview per point, unchanged author/cache files and separate
  reproduction of the known unpatched 0.5.0 failure.
- Published Diavisuals 0.5.0 / Vega 0.5.1 rendering, receipts, tampering and relocation;
  downloaded-gem isolated helper closure. Earlier exact 0.4.0 static receipts retain
  their integrity-checked compatibility point.

Evidence root: `/tmp/opencode/unaltraweb-071-93/`.

| Result | SHA-256 |
| --- | --- |
| `final-integration/evidence.json` | `dcfce02ed10e7567a1030c1c93fc31fb7d75dfc73281fe8f1c4ee6b46038b6da` |
| `final-carta/evidence.json` | `c456b5e72d72bc224a7416589805c7d80c50d7fafe8747c86cd31ecb782cd308` |
| `final-d0/evidence.json` | `989603ed0a09fd6af9ca659ffbb824ab46907cb4538d094dcf32e34c8ea77c25` |
| `final-bundler/evidence.json` | `352fe35a81f36b2b44fbfe92f000d9179053d45f572b37f48485c82dd4c7c949` |
| `final-helpers/evidence.json` | `df994ccd8afaff45a7e3cfa9b6a29b650c9d01d63db2c9c36e59c31834273473` |
| `published-packages/verified.json` | `39b322784e5eef0ccde89ad8883e495c66ec9df23213fbe3301fb91862cb2c2c` |
| `public-images.json` | `6c2f54a877728dabbf39f2f2b0432beb5fe4c50c98769b22e06b6e1c562d7f77` |
| `post-pin-proof/evidence.json` | `f9168183e859e842b4bc236cca126edc2e9bd5464eb2527450302cc9342121c6` |

A fresh public-wheel venv passed default prepare/check/stdio smoke with the exact
expected configuration ID and rechecked the relocated Carta mapping. The public
gem installed in an isolated gem home and activated as 0.7.1 using the runtime's
existing dependency set; this is not a network-fresh dependency installation claim.

The actual checkout `MCP_CONSUMER_WORKSPACE=… make mcp-stdio` transport reported
instance `effcd7bce6cb477da6c49107a5582e02`, loaded 0.7.1 and the expected image.
Tool/resource identity agreed, the scaffold target selected the reviewed workflow,
and drain/close followed by exact session inspection proved resource release.
The post-release pin/report PR and clean-main CI result are recorded in issue 93.

The post-pin local suite passed 629 cases (599 passed, 30 optional skips),
distribution/workflow/fresh-wheel gates, prose/publication-copy checks and
whitespace checks. `make mcp-check mcp-smoke` used owned
`unaltraweb-071-93-*:post-pin` development images and the selected public PDF;
`make docs-build` used the exact published runtime digest. Both passed. These
development builds are separate from the signed-byte acceptance above.

## Consumer and hub boundaries

TIG independently adopted the earlier issue-86 hotfix in
[geourv/tig#24](https://github.com/geourv/tig/pull/24) and deployed reviewed main
`f5ddfabe650c95c10a99f3656a7cfc09e885dcbf` in successful run
[37523692990](https://github.com/geourv/tig/actions/runs/37523692990).
Its owner verified the public 311-page PDF byte-for-byte against the approved
copy, SHA-256 `3d58d63b7315099ac3518401415c35f0a0acf4a3f7f41ee6270716f394309bc4`.
That is hosted proof of its existing 0.5.0/hotfix combination, not a 0.7.1 migration.

This release's acceptance covers Linux/amd64 installed web/PDF work and selected
workflow preflights; real-manual hosted adoption remains per-consumer. The full
managed helper graph still needs composing-owner acceptance of the published
Diavisuals 0.6.0 correction; selected rendering compatibility remains 0.5.0.
gaContExt catalogue/advisory/activation work and deliberate client reconnection
remain separate. Earlier releases, author data and client registrations are preserved.
