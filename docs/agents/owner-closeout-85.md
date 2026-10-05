# unaltraweb 0.7.0 D0 delivery closeout

Published **2026-10-05 21:45:13 UTC**:
[v0.7.0](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.7.0).
Owner: [issue 85](https://github.com/dosquartsdedocs/unaltraweb/issues/85).
Coordination: [gaContExt 15](https://github.com/dosquartsdedocs/gacontext/issues/15).
Requirements: gaContExt `5634ea2e3e42122bb365992dfca9f248feb89dec`.
This report supersedes the chronological candidate state in the
[native API contract](d0-runtime-identity.md).

## Review and exact source

The owner explicitly authorized the complete review/PR/integration, gated
publication and separate post-release checkout pin. Work used only
`/home/benizar/git/unaltraweb`, ordinary serial branches and synthetic consumers.
Existing releases, authored state and unrelated client registrations were retained.

| Role | Revision / evidence |
| --- | --- |
| Reviewed D0 implementation | `0c87e8c276e58ac9c747833df69cdb439aa6132b` |
| Integrated core selected by consumers | `216ab2e8b6b8b45a5bb7da0a54bffd10edee895d`, [PR 87](https://github.com/dosquartsdedocs/unaltraweb/pull/87) |
| Core selection commit | `2881a37dd6e5071d71c30cb44aa9af6faba5e886` |
| Final artifact-producing source | `b44818c67eecef159f7aa0f825b0416cd511bc43`, [PR 88](https://github.com/dosquartsdedocs/unaltraweb/pull/88) |
| Receipt-only child | `6dc13638c49bfb53a1c456e9e6b30aec7b3fd713` |
| Receipt integration / tag target | `9fc84ac7fd01c78c6fe15fe862beb6a5d1633a9e`, [PR 89](https://github.com/dosquartsdedocs/unaltraweb/pull/89) |
| Annotated tag object | `28a2a40b4b633be2fefb3f1c753cf95db1c7bdf6` |

Review records are explicitly agent-attributed, not human approval. The receipt
integration's first parent is the artifact source; its first-parent diff contains
only `release-candidates.json`. Native package authorization, exact staging,
strict distribution/publication-ref checks and annotated-tag verification passed
before privileged publication. These release checks apply to the receipt/tag
revision, not later ordinary post-release commits.

## Receipt, packages and images

[Tagged receipt](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.7.0/release-candidates.json):
schema 1, source `b44818c67eecef159f7aa0f825b0416cd511bc43`, SHA-256
`92b4feafbf822ff5b0d9fc6534f963e68c2a28a875d4e2e841c051e7c619e7dc`.
It contains exactly the four components marked `ready` in the source BOM.

| Component | Artifact / repository | SHA-256 / OCI index digest |
| --- | --- | --- |
| Gem | `unaltraweb-0.7.0.gem` | `1f4c71fc03bc3025018873eae73f7a2274e46b87ac678805e4150b8351b9ff0c` |
| Wheel | `unaltraweb_mcp-0.7.0-py3-none-any.whl` | `3c9cd477e8c2fa0f69c1309c9302b110b73032600e8cf040c4818169863dd868` |
| Base runtime | `ghcr.io/dosquartsdedocs/unaltraweb` | `sha256:ce67aa8fb90899e3c770c4ec8952b760cc8cafb3ed203e8e15266a9623bb3d31` |
| MCP | `ghcr.io/dosquartsdedocs/unaltraweb-mcp` | `sha256:b84cdb404ba7bab5ff0b14fa8a7ee93d7293e829cf32e28ff0dacaa8afff4677` |

Both OCI aliases `0.7.0` and `v0.7.0` were inspected anonymously and match these
digests. Local Linux/amd64 configuration IDs are distinct:

- Runtime: `sha256:beec5459bc7aa159af428fbad5d14a4527f3143e5062ec305a00619c31aae706`.
- MCP: `sha256:b03e463343abcd0d5891f68ec423256f970d7c1fb35dc875e089e0f745cfe39a`.

Their revision labels equal the artifact source. The image workflow verified
GitHub-signed provenance, signer workflow, source revision and labels before
executing the exact candidates. Semver promotion reverified those identities and
reused the tested manifests without rebuilding.

The package workflow artifact is `11329540867`, named
`unaltraweb-0.7.0-b44818c67eecef159f7aa0f825b0416cd511bc43`; its archive digest is
`sha256:9af51fb8447cf77691ffd362a752b247a9a1ee45a351f44b8de8ac60d62317c9`.
The publisher authorized the exact successful run, source and inventory, then
verified/staged the recorded hashes. Separate OIDC jobs published those bytes.
Anonymous PyPI/RubyGems metadata and downloads match them. Downloaded GitHub
Release assets also pass `SHA256SUMS`, whose SHA-256 is
`4abdefd44dd6cce44262fd19e224a54ca7a1d1b7ada66071d5b737d94f9270ab`.

## Reused workers and accepted helpers

The selected PDF remains the published, signed 0.6.0 specialization:
`ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed`.
Its configuration ID is
`sha256:d7e7d3243616270fc9e6eed7f8238c412dbe3d9ffc18d2832d17d66ca630d139`.
It is `released`, outside the four-component receipt. The source-bound workflow
also tested PDF candidate
`sha256:d6d866cd16eab156e7dc3fea2fd7e649d8b91dca2916b45cd5c2218184d5928b`;
that verification-only candidate received no 0.7.0 semver promotion and is not
the selected worker.

Computation and capture keep their 0.4.0 immutable BOM references. The retained D0
observation reports Python compute as prepared; R compute and web capture were
locally missing and remained explicitly `missing`, without fallback. This
acceptance executes web/manual-PDF work, not every optional computation/capture
workflow. An adapter enabling those features must prepare and verify their exact
workers separately.

| Accepted helper | Wheel SHA-256 | Renderer configuration ID |
| --- | --- | --- |
| Diavisuals 0.5.0 | `f52e20f20f1fb3a2418f07adb8d6a68a5567d0c321fb7c0ccc0f4db04917b96b` | `sha256:5a6887b372a0e1c386a7b54981d11ae1910215baeb6a12dfd0706b3e85ef0846` |
| Vega 0.5.1 | `5aba4f267a37179c520b3cd164e1cec62ac5561872aa33b069cce73442dc52b1` | `sha256:695125943d0fbc3aa7c877babb9a11a6501bbc7ac265b0975bb5657c60439d98` |

Native selection uses Diavisuals `--runtime-image` / `--runtime-expected-id` and
Vega `--renderer-image-id`. Actual Mermaid, PlantUML, Vega-Lite/CSV and Vega renders
passed receipt verification, tamper refusal and consumer relocation. Existing
renderer aliases were unchanged. Exact 0.4.0 static receipt compatibility retains
all input/output/request integrity checks; no continuous version range is inferred.

## Live identity and installed acceptance

The actual serving process provides `runtime_identity` and
`web://runtime-identity`; both agreed on the backend instance. Native profile
`unaltraweb-docker-stdio-v1` uses one connection per backend, one operation at a
time, explicit drain and scoped orphan recovery. Host commands `session-status`
and `reap-session` consume the retained consumer/session/container tuple.

The initial accepted backend instance was `400244b6784c46498aadd3ec3b9c088f`, with
inner PID 7 in `pid:[4026533734]`, start ticks `65541450`, Python 3.13.5 and
executable `/usr/bin/python3`. Container
`3feb725c68984e69fe208d56bdf06ec2dfcff4d43f1071045ebc0eadf3779ffe` had daemon init
PID `3938960`; these PIDs belong to different namespaces. The canonical consumer
binding was `/tmp/opencode/unaltraweb-d0-85/candidate-d0-proof/consumer A`.
Reconnection produced instance `9c9d94e47c324be89abff5e80defb024` while the second
consumer retained instance `413e89f4ebd34e5d8570b1db6a8360af`.

The installed engine root was `/usr/local/lib/python3.13/dist-packages/unaltraweb_mcp`.
Loaded version 0.7.0 and startup code fingerprint
`5fdfb154f82d01bb5dcc5a35d74ba2f384b36e60a5111b63831b6216adfb8996` remained fixed
when metadata in the disposable container overlay changed to 99.0.0. Current
bytes reported drift; the prepared image was unchanged. Observed canonical
component-contract hash:
`d2cddda50780f00ec3af47826a93341e014d4811146195ed09a9bf1ee5fcdf81`;
profile hash:
`6c9305143f2f5e3dee831f3d5bf2b5413e51f24e3f28310fa21019c645532481`.
Selection hashes additionally bind each consumer/worker tuple and are retained in
the evidence. These observations are not permanent process attestations.

`test/d0_runtime_smoke.py` passed all eight stages against the downloaded CI wheel
and signed MCP: reconnect/scope, loaded-versus-disk, busy drain, backend-crash
recovery, offline launch, explicit nested daemon mapping, wrong worker and missing
worker. Wrong/missing controller images were also refused. A real PDF job was
observed **busy after backend death**; recovery waited until it became eligible,
then proved resource absence while another live backend remained connected.
EOF/drain released only the retired session's resources.

The real 0.6.0 → 0.7.0 → 0.6.0 roundtrip preserved authored files and old generated
cache entries. The unrelated registration sentinel retained SHA-256
`2705c6065bbc5665798be533b1057070b6efeae289cab3e800579cb6b5608afb`.
The historical 0.6.0 process lacks live identity and remains an explicitly
**partial** point, not a second D0-capable release.

## Retained Carta and populated Bundler regressions

`test/artifact_import_smoke.py` consumed the authenticated published Carta packet.
Bundle hash `aeaa757ee1be19bfe56dc9af8dd1178032929b4a2bec2dad2ebb621b158ad999`
and the 12-file seal remain intact. The mapping from `payload/output/letter.pdf`
to `assets/documents/carta.pdf` retains original PDF hash
`4a661740a18fe1cf75b84aa0d8532511fd105eb5484a5af700e11e8e30828ea4`.
Integration record hash:
`995e213e9c5677763809b4d108b84882e1821be58796e0823b8260c22f891a18`.

The copied producer and incoming tree were removed, author prose survived
reimport, and the receiver moved before native/generic checking and a forced PDF
rebuild. Web/HTTP passed at both locations. Both 11-page PDFs have SHA-256
`026552039659771d73a26875dc628c5dbccb8da2d4c32bcf0a199929efdd60e2`; the unchanged
letter appears on page 10. Generic verification confirmed one bundle, one mapping
and 14 files; the native checker also bound the chapter and rendered page.

`test/bundler_transition_smoke.py` passed all four profiles using actual immutable
0.4.0, unpatched 0.5.0 and new 0.7.0 MCP references. The known failure was
reproduced on a separate copy. Each 0.7.0 activation and return to 0.4.0 passed
two builds and a preview. All six author/cache files kept their hashes, with no
cache clearing. `test/published_companion_smoke.py` passed with the published
helper wheels and explicit renderer IDs above. The downloaded CI gem passed
`scripts/test_gem_build.py:inspect_gem`, including isolated native helper closure.

## CI and retained evidence

| Gate | Successful run |
| --- | --- |
| Implementation PR CI / CodeQL | [37271200816](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37271200816) / [37271200817](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37271200817) |
| Core selection PR CI / CodeQL | [37272201763](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37272201763) / [37272201726](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37272201726) |
| Final artifact source CI / CodeQL | [37272717370](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37272717370) / [37272717381](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37272717381) |
| Signed candidate image build/test | [37273192732](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37273192732) |
| Package preparation | [37273195884](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37273195884) |
| Receipt PR CI / CodeQL | [37371882737](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37371882737) / [37371882776](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37371882776) |
| Receipt integration CI / CodeQL | [37375549493](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37375549493) / [37375549627](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37375549627) |
| Tag CI | [37376786630](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37376786630) |
| Semver image promotion | [37377435437](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37377435437) |
| PyPI/RubyGems Trusted Publishing | [37377438226](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37377438226) |

Two first-attempt receipt PR jobs were not acquired by hosted runners and ran no
steps. Their retry passed without source changes; original attempts remain in
the local evidence. The local source suite passed 608 Python cases, with 30
optional/environment skips. No failed job was bypassed for merge or publication.

Evidence root: `/tmp/opencode/unaltraweb-d0-85/`.

| Retained result | SHA-256 |
| --- | --- |
| `image-evidence/tested-images.json` | `6c38a1d08511d0cb6554905bc236de58a9f594b255553361d36e6caa4622335d` |
| `candidate-d0-proof/evidence.json` | `e8140ef8cf47e4329f7691b8a3733377a17269b83c2cf2e9b444c94ce22621f6` |
| `candidate-carta-proof/evidence.json` | `c1b12f80b1a3c0d31a83fa015f050f0897923ef578ecac9c20f95e4acaa6fca0` |
| `candidate-bundler-proof/evidence.json` | `8206e1a9e4a88123390dad30ba314d0b2fa00820a5af426164f060050be3ab4d` |
| `candidate-helpers-proof/evidence.json` | `df994ccd8afaff45a7e3cfa9b6a29b650c9d01d63db2c9c36e59c31834273473` |
| `published-packages/verified.json` | `e892bbb22c35ea3eef3b2abbbd6351e4a290e76d322c91ac3de6fb212965909f` |
| `public-images.json` | `f123c2dc096405bde004cfd6cbce206a0f56925f436731e575830cf111d26314` |
| `post-pin-proof/evidence.json` | `0944b95eec8d0e1103f4895595c77780d27ebc1a3e64626f421b960be8efd144` |

## Public installation and checkout selection

A fresh public-wheel venv passed default `prepare`, `check` and real stdio
`smoke`, with the expected MCP configuration ID. That public installation also
rechecked the relocated Carta source/rendered mapping. The public gem installed
in an isolated gem home and activated as 0.7.0 with the runtime's existing Ruby
dependencies, including Ruby's default gem paths; this is not a network-fresh
dependency installation claim.

The separate `chore/85-pin-published-mcp-0.7.0` source change selects the published
digest in Make/bootstrap and updates its existing pin regression and current docs.
It does not alter the published BOM, receipt, tag or artifact bytes. Its PR/merge
and final protected-CI state are returned in issue 85.

The actual `MCP_CONSUMER_WORKSPACE=… make mcp-stdio` transport started a synthetic
consumer with live instance `2ebdbd20c32649c48bf309dc469f2c8b`. Tool/resource
identity agreed, loaded 0.7.0 and the published image matched, and drain/close
followed by exact retained-tuple inspection confirmed resource release.
`make mcp-build` and the bootstrap's `--check` selected that public image directly.

Post-pin local checks passed 608 Python cases (579 passed, 29 optional skips),
`make distribution-check workflow-check`, the fresh `make wheel-check`, prose
checks, `editorial-publication-check` and `git diff --check`. The prose checker
reported only existing informational sentence-length cues, not blocking findings.
The source Make targets were exercised with independently owned development names:

```bash
make mcp-check mcp-smoke \
  MCP_RUNTIME_IMAGE=unaltraweb-d0-85-runtime:post-pin \
  MCP_IMAGE=unaltraweb-d0-85-mcp:post-pin \
  MANUAL_PDF_DEV_IMAGE=unaltraweb-d0-85-pdf:post-pin \
  MCP_SMOKE_MANUAL_PDF_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed
make docs-build \
  DOCKER_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb@sha256:ce67aa8fb90899e3c770c4ec8952b760cc8cafb3ed203e8e15266a9623bb3d31
```

Both commands passed. Development outputs remain separate from the signed
artifact acceptance and did not replace public semver images or retained caches.

## Remaining gates and scope

**The complete coordinator dependency graph is not declared managed-ready.**
Selected Diavisuals 0.5.0 lacks full serving-process identity;
[Diavisuals 14](https://github.com/dosquartsdedocs/diavisuals/issues/14) remains the
external owner correction. The hub must observe each independent helper process,
prepare feature-specific workers and accept the native adapter before activation.

The acceptance platform is Linux/amd64 and the claimed backend profile is Docker
stdio, one connection per instance. Shared HTTP backend reattachment and a fully
D0-capable two-release roundtrip are not claimed. Arbitrary direct controller
layouts remain [issue 31](https://github.com/dosquartsdedocs/unaltraweb/issues/31);
only canonical host and explicitly mapped nested launchers were proved. Retained
Carta coverage is the published English one-page leaf, not Diapora composition.
Real manuals, author artifacts and existing client registrations were not migrated.
Already-running clients retain their loaded runtime until explicit reconnection.
