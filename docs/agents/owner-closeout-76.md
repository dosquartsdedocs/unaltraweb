# unaltraweb 0.5.1 delivery closeout

Publication: **2026-09-30**, [v0.5.1](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.5.1).
Owner coordination: [issue 76](https://github.com/dosquartsdedocs/unaltraweb/issues/76).
This supersedes the pending-publication status of the retained preparation and
follow-up reports without changing their historical bytes.

## Revisions, review and integration

| Role | Revision / evidence |
| --- | --- |
| Initial accepted local source | `217340cadc9db85aa717e020682068b9ce0ef379` |
| Bundler/core implementation, retained consumer pin | `c23e12b0e1567d18a7f9dd225dc062ddc77dad8b` |
| Closeout installed-launcher default correction | `1640572ccd9156037b9a4c0018b4c849a027296f` |
| Integrated source producing the release artifacts | `aab5a7b030cd711b40770a3f44ad3a356eab90da`, [PR 77](https://github.com/dosquartsdedocs/unaltraweb/pull/77) |
| Receipt-only branch commit | `8a0b6ce0d0c875ac6a8b86d9e354b8a388b5d038`, direct child of the source above |
| Receipt integration and release tag target | `e842c733c8a274279dd5efdc3618e20669f29037`, [PR 78](https://github.com/dosquartsdedocs/unaltraweb/pull/78) |
| Annotated `v0.5.1` tag object | `c4901b583c777a050cd53e1e96643ad53b7c0f64` |

Both integrations used merge commits, preserving the approved core's ancestry.
The receipt integration's first parent is exactly the artifact source; its diff
from that parent contains only `release-candidates.json`. The source pin still
names the real approved core implementation. The later closeout correction
changes host-launcher selection, not that Jekyll/Bundler core implementation.

All preparation commits and the complete base diff were reviewed. The remaining
delivery finding was that the installed 0.5.1 launcher still selected the older
0.5.0 MCP. Commit `1640572` fixes that: the console adapter uses explicit
`--image`, then `UNALTRAWEB_MCP_IMAGE`, then its own BOM release image. The installed
Make profile also defaults to its own release. The checkout's stricter digest
pin remains a separate post-release operation. Default and override precedence
are exercised by the factory-free wheel gate.

Agent review records are attached to both PRs; they do not claim human review.
Copilot could not review because of quota exhaustion and was not counted as a
completed review. Explicit owner authorization covered integration and, in two
later approvals, credentialed candidate preparation and final publication.
All protected checks and conversation requirements passed without bypass.

## Published receipt and artifacts

[Tagged native receipt](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.5.1/release-candidates.json):

```text
schema_version: 1
release: v0.5.1
source_commit: aab5a7b030cd711b40770a3f44ad3a356eab90da
receipt SHA-256: 0e9d8f0589fa1ebf3aa067f0558523868fec29210927d1715f22e16e72cb30ec
```

Exactly four ready components are recorded:

| Component | Published name / repository | SHA-256 / OCI repository digest |
| --- | --- | --- |
| Gem | `unaltraweb-0.5.1.gem` | `818bfbb53af4de16383a211e4224ab7ab77a2647afe8703f9c3f7c1ebd123c64` |
| Wheel | `unaltraweb_mcp-0.5.1-py3-none-any.whl` | `354bff5894073d66e064b5bcd0887c5963f58035ee2b1751b541722f345cf08f` |
| Base runtime | `ghcr.io/dosquartsdedocs/unaltraweb` | `sha256:3712453bf30289f02181cff0c095ecda563306e1d8a8f2a0e087c65ea9c8d730` |
| Full MCP | `ghcr.io/dosquartsdedocs/unaltraweb-mcp` | `sha256:908b4ce54c7bdf355e14ed55b31ed4b9baae319e211af90004a680d1d1cb8692` |

The GitHub Release retains both packages and `SHA256SUMS`; that checksum file's
SHA-256 is `5cd3be237015841b65583b9b54b9df37c8a4b642e9231e6ee522d8d37d90821a`.
These are the newly downloaded workflow/publication bytes, not the earlier local
0.5.1 candidates whose hashes appear in the follow-up report.

Native component selections retained unchanged:

- PDF 0.5.0:
  `ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097`.
- Python 0.4.0:
  `ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:18cb269811bd4005800382da25a480ec2bca7eac8d0501ad1ef36bad1c0f8cd9`.
- R 0.4.0:
  `ghcr.io/dosquartsdedocs/unaltraweb-compute-r@sha256:928ffb93f221e09e8b929157dee473b838e061915a2eb67224e4124b85f81837`.
- Web capture 0.4.0:
  `ghcr.io/dosquartsdedocs/unaltraweb-web-capture@sha256:0bf1bc67fe63e1440bffe708a168beefa11c54441650a871ab99380d362f7c1e`.
- Diavisuals/Vegavisuals 0.4.0: the same BOM-selected hashed wheels and provider
  receipt contract. Their exact references remain in `component-contract.json`.

The image workflow additionally built/tested a PDF verification candidate
`sha256:55c88a6e805f0612b8dced992868aab8443f077d72ecc9aaf7ff1bf862a154a6`.
It is not selected by the BOM, not included in this receipt, and was not promoted
as a 0.5.1 PDF component. The original 0.5.0 receipt remains at its existing tag,
with SHA-256 `e57a9dbb041c1e7fcd781cd1524f4de0317382e0f7303bb36bfa59c0b6d1cb9b`.

## CI, signing and publication gates

| Gate | Successful run |
| --- | --- |
| Integration PR CI | [36780877307](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36780877307) |
| Integration PR CodeQL | [36780877311](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36780877311) |
| Integrated-source CI | [36785554970](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36785554970) |
| Signed image build, verification, tests | [36785858325](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36785858325) |
| Package preparation | [36785861424](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36785861424) |
| Receipt PR CI | [36788752930](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36788752930) |
| Receipt/tag target CI | [36789293544](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36789293544) |
| Tag CI | [36791298216](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36791298216) |
| Semver image promotion | [36791298413](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36791298413) |
| PyPI and RubyGems Trusted Publishing | [36791301396](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36791301396) |

GitHub-signed OCI provenance was verified against the owner workflow and exact
source digest in the candidate and promotion jobs. Local inspection additionally
confirmed the OCI digests and source revision labels. The package workflow's
immutable artifact ID is `11129633290`, archive digest
`sha256:60a68862dcedec3747ed49112b66d10e697765a0ab5d6f249b33690aa5c5a3c5`.
The publication verifier bound that run, source, artifact inventory and checksums
to the receipt and annotated tag object before granting OIDC publishing authority.

Before promotion, both the actual receipt-only branch and merged tag target
passed `make distribution-release-check`. The merged `main` and then the annotated
tag passed `--require-release-ready --validate-publish-ref --components
gem,wheel,runtime,mcp,manual_pdf`. `verify_package_publish.py release` and exact
package staging also passed. The old receipt was never substituted as evidence
for the new version. Strict release validation refers to this receipt/tag
revision, not to later ordinary post-release source commits.

## Populated-cache evidence

The previous final evidence was first rehashed at intake: gem, wheel and
`final-roundtrip/evidence.json` matched the follow-up report. All six preserved
files still matched in every profile, and the manual PDF matched its manifest.

The actual signed candidate and downloaded CI wheel then passed a new full
roundtrip in **all four profiles**: `unaltreselfie`, `unaltreprojecte`,
`unaltredocs`, `unaltremanual`.

1. A real 0.4.0 build populated the generated lock with `google-protobuf 4.36.1`.
2. Unpatched 0.5.0 failed as expected on a separate populated copy.
3. The signed corrected full MCP passed two builds, preview and HTTP.
4. Returning to the unchanged published 0.4.0 passed two builds, preview and HTTP.
5. Gemfile, Gemfile.lock, Makefile, scaffold baseline and both historical generated
   Gemfile/lock files retained their original SHA-256 values throughout.

New evidence:
`/tmp/opencode/unaltraweb-closeout-051/candidate-roundtrip/evidence.json`, SHA-256
`b5a2935359103983ff497760d8e9c367318ed9f77741ae1c5404a56449547179`.
An external recording wrapper ran the unchanged owner driver and retained the
manual tool responses plus PDF/cover bytes for both stages; it did not change
arguments, caches or runtime behavior.

| Manual artifact | SHA-256 |
| --- | --- |
| Corrected stage PDF | `203b39def968b644d1d0d3999827516e0e00aa8dd6b85202b33167d68dcb150e` |
| Return-0.4 PDF | `aba2802d4e0d978c8acc0cfbfc26a84607739b0953756a6bdb16fabbc43defa0` |
| Both stage covers | `afc3ba16ca919a7879f4629023e6316b77e31e56403e82edb7168f3181a3dc9d` |

The responses report `ok: true`, `publishes: false`; preview cleanup remained
receipt-bound. No cache was emptied to obtain a pass. The historical image
selections and reproduction command remain in `owner-followup-76.md`; this run
used the receipt's full MCP digest as `--fixed-image` and the downloaded CI wheel.

## Public-download and installed acceptance

Artifacts are retained under `/tmp/opencode/unaltraweb-closeout-051/`:
`packages/`, `verified-packages/`, `published/`, `github-release/`,
`installed-candidate/`, `installed-published/`, and `candidate-roundtrip/`.

- Anonymous PyPI and RubyGems downloads match the receipt exactly; metadata and
  downloaded bytes were independently compared.
- Both `0.5.1` and `v0.5.1` GHCR aliases were checked with an empty Docker client
  configuration and match the expected OCI index digests.
- GitHub Release assets were downloaded again and pass their `SHA256SUMS`.
- The public wheel was installed non-editably in a new venv. Its default
  `prepare`/`check` selects and runs MCP 0.5.1 without a local core.
- The public gem installs into an isolated gem home and activates as 0.5.1 using
  the image's preinstalled Ruby dependencies. An initial probe artificially
  omitted standard gem paths and failed to find `rexml`; retaining `Gem.path`
  corrected the probe. This is not a claim of a network-fresh dependency install.
- The host's older Buildx did not render the requested digest-only template;
  anonymous verification instead checked the exact top-level `Digest:` field.
- Closeout source tests reported **562 cases, 532 passed, 30 optional skips**;
  distribution, workflow, wheel and prose checks passed. CI additionally ran its
  Python matrix, Ruby, PDF, MCP, reproducibility and docs gates.
- The post-pin local recheck reported **562 cases, 533 passed, 29 optional skips**
  after the public image became available. Distribution, workflow, wheel,
  `mcp-check`, `mcp-smoke`, docs build and diff gates passed with isolated
  `unaltraweb-closeout-051-*:post-pin` tags and a fresh smoke fixture. The smoke
  used the selected published PDF digest. These local development builds do not
  replace the published release artifacts.

Observed local configuration IDs (distinct from OCI repository digests):
runtime `sha256:5c406a7981118203070517b6689f2f4f03ac7fd2b5626b52ed96fe14009d67b9`;
full MCP `sha256:e7b2bd34751c2d3a30f9974f46c64e30a1a2fbd9ba412279234a5f24ff197eda`.

## Post-release pin and remaining adoption scope

The post-release source change on `chore/76-pin-published-mcp-0.5.1` accompanies
this report. `Makefile` and `scripts/unaltraweb-mcp-bootstrap.sh` select
`ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:908b4ce54c7bdf355e14ed55b31ed4b9baae319e211af90004a680d1d1cb8692`;
the pin regression and current documentation are updated. Its PR/merge and final
clean-main confirmation are recorded in issue 76 after protected CI completes.
Published packages, receipt and tag are not rebuilt by this source update.

An actual `MCP_CONSUMER_WORKSPACE`-bound `make mcp-stdio` session was launched from
the post-pin checkout against a new empty synthetic consumer. Initialize and
`detect_site` succeeded, and Docker inspection proved the session used the public
MCP configuration ID `sha256:e7b2bd34751c2d3a30f9974f46c64e30a1a2fbd9ba412279234a5f24ff197eda`.
The temporary session exited cleanly. The post-pin `mcp-build` and bootstrap
`--check` also selected the published image without rebuilding it.

The installed package already selects its own release; existing MCP processes
keep their image until reconnected. No real manual, client registration or shared
authoring worker was migrated. Historical Makefile adaptation remains restricted
to matching baselines; customized Makefiles require explicit owner integration.
The accepted evidence covers these exact Linux/amd64 tuples, not an untested
version interval or architecture. No new H1 fields were introduced. Consumer
adoption and central catalogue integration remain their own later sessions.
