# unaltraweb 0.6.0 delivery closeout

Published **2026-10-02 17:28:14 UTC**:
[v0.6.0](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.6.0).
Owner coordination: [issue 80](https://github.com/dosquartsdedocs/unaltraweb/issues/80).
This report supersedes the pending delivery state in the chronological
[preparation record](retained-letter-import.md). Issue 76 and release 0.5.1
remain closed and immutable.

## Review, source and integration

The owner explicitly authorized commits, push, PR review/integration, signed
candidate workflows, gated publication and the post-release launcher pin. The
checkout was reconciled against all existing unit-80 paths; no unrelated edits
were found. Work used one checkout and ordinary serial branches.

| Role | Revision / evidence |
| --- | --- |
| Reviewed implementation | `7af652fb83629e959af05c407a34a2f5a15f7936` |
| Integrated core selected by consumers | `5cf9817489c8dc47cee726bfe42fe3071cd32b85`, [PR 81](https://github.com/dosquartsdedocs/unaltraweb/pull/81) |
| Immutable core/PDF selection | `8e93b8b808204faef54cccaee622699f04a11805` |
| Final artifact-producing source | `de52db351490e94939aac20c6af264f22a6a1678`, [PR 82](https://github.com/dosquartsdedocs/unaltraweb/pull/82) |
| Receipt-only child | `3ce7606bc6148aee19d067c559823d8c5b52db5d` |
| Receipt integration and tag target | `ec6dcb28e890d32718aa173934527a7b4213a042`, [PR 83](https://github.com/dosquartsdedocs/unaltraweb/pull/83) |
| Annotated tag object | `1605578861a1a09157037e6085020baad4948d72` |

All three PRs have explicit agent review records and protected CI; those records
do not claim human review. Merge commits preserve the reviewed core's ancestry.
The receipt integration's first parent is exactly the artifact-producing source,
and its first-parent diff contains only `release-candidates.json`.

Review closed independent metadata-reference validation, malformed Pandoc-link
handling, internal PDF OpenAction destinations, and direct signed-runtime
acceptance. The vendored v1 verifier/schema still match the established hub pin
byte for byte; 26 reference conformance tests passed against matching fixtures.
Source checks reported 587 Python cases with 30 optional skips. Ruby, actual PDF,
MCP, wheel/gem, workflow/distribution, docs and reproducibility gates passed.

## Receipt and published identities

[Tagged native receipt](https://github.com/dosquartsdedocs/unaltraweb/blob/v0.6.0/release-candidates.json):

```text
schema_version: 1
release: v0.6.0
source_commit: de52db351490e94939aac20c6af264f22a6a1678
receipt SHA-256: 5ed4e6dd615367927e6ea8a3541c9e7dca9dad73a738851705f563e0e6895280
```

Exactly the four `ready` components are bound to that source:

| Component | Registry artifact | SHA-256 / OCI index digest |
| --- | --- | --- |
| Gem | `unaltraweb-0.6.0.gem` | `276d04a71d1170220c3881cce8d0800633c42b0ee7ad07a376f80996c6afd177` |
| Wheel | `unaltraweb_mcp-0.6.0-py3-none-any.whl` | `3effb471ffd264f7fb2a8c88dd6536bc86639eae52806527c2d872653944c85a` |
| Base runtime | `ghcr.io/dosquartsdedocs/unaltraweb` | `sha256:a4e9d82b0e9a72e519c44e09ca449b2dc37964fbb9953ae6e4adff648e39b94b` |
| Full MCP | `ghcr.io/dosquartsdedocs/unaltraweb-mcp` | `sha256:736c4ddd0a543454e3edaeac2e9cfd97a1279ce472923ac54e326c1281b2ba05` |

Both `0.6.0` and `v0.6.0` OCI aliases were inspected anonymously and match those
index digests. The MCP's local configuration ID is
`sha256:73320210b19597243c7183ef255ffa1cbc36a07157e6ab4e1b3d9349fa89a063`;
its revision label is the exact artifact source above. Configuration IDs and
registry index digests are distinct identities.

The selected PDF 0.6.0 is the already-published, signed and tested specialization:
`ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed`.
It was produced from core `5cf9817489c8dc47cee726bfe42fe3071cd32b85` by the
[initial signed image run](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37029374441),
and its local configuration ID is
`sha256:d7e7d3243616270fc9e6eed7f8238c412dbe3d9ffc18d2832d17d66ca630d139`.
The BOM, generated consumer tuple and Make default select that same digest.
It is reused as `released`, outside the four-component coordinated receipt.
The later image workflow also tested a verification-only PDF candidate
`sha256:9b3ae6fe1f04ff7de6c81c258d7c16f79cc7f2857c9b46b0829fc71812ace11f`;
that candidate is not the selected worker and received no coordinated semver
promotion. No self-digest or fabricated core SHA was introduced.

Computation, capture, Diavisuals and Vegavisuals retain the tested 0.4.0 selections.
Their exact immutable references remain in the BOM, and earlier published
artifacts and receipts remain at their original tags.

## CI, signing and publication

| Gate | Successful run |
| --- | --- |
| Implementation PR CI / CodeQL | [37027921742](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37027921742) / [37027922332](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37027922332) |
| Core integration CI | [37028677932](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37028677932) |
| Tuple PR CI / CodeQL | [37032368507](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37032368507) / [37032368609](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37032368609) |
| Final source CI / CodeQL | [37033064607](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37033064607) / [37033064633](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37033064633) |
| Signed final image build/test | [37033593312](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37033593312) |
| Package preparation | [37033596931](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37033596931) |
| Receipt PR CI / CodeQL | [37038403708](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37038403708) / [37038403802](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37038403802) |
| Receipt/tag target CI / CodeQL | [37039075585](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37039075585) / [37039075748](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37039075748) |
| Tag CI | [37039786598](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37039786598) |
| Semver image promotion | [37040420721](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37040420721) |
| PyPI/RubyGems Trusted Publishing | [37040424945](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37040424945) |

The signed image workflows checked exact OCI digests, signer workflow, source
revision and labels before executing candidates. Promotion reverified those
bindings and reused the tested manifests without rebuilding. The package
authorizer bound workflow/run/source, immutable artifact ID `11237594327`, exact
inventory and checksums to the receipt. Its archive digest is
`sha256:79a67d7a8370468abe1f0265b248f3e9d6cf6187ac0bc891a0b3801e5a9931a6`.
OIDC jobs published only the staged verified gem and wheel.

The actual receipt-only branch, merged target and annotated tag passed strict
`distribution-release-check` and publication-ref/ancestry gates. Native package
run authorization, exact staging and `verify_package_publish.py release` passed
before privileged publication. Strict release checks apply to the receipt/tag
revision, not subsequent ordinary post-release source commits.

## Real retained-letter and rollback proofs

Acceptance consumed the authenticated published Carta 0.3.0rc1 packet, not a local
producer checkout or synthetic unit fixture. The sender bundle hash is
`aeaa757ee1be19bfe56dc9af8dd1178032929b4a2bec2dad2ebb621b158ad999`.
All 12 seal files remain under `.unaltraweb/artifacts/carta/bundle/`.
The mapping `payload/output/letter.pdf` → `assets/documents/carta.pdf` retains
SHA-256 `4a661740a18fe1cf75b84aa0d8532511fd105eb5484a5af700e11e8e30828ea4`.
The native chapter is `_chapters/en/carta.md`, with its separate binding and
standard-v1 integration record outside the seal.

The downloaded final CI wheel ran against the exact signed MCP and selected PDF
digests above, without deriving another controller image. Both copied producer
and incoming trees were removed, author prose survived an identical reimport,
and the receiver was moved before native/generic verification and a forced PDF
rebuild. Web/HTTP checks passed at both locations. The complete original letter
appears on page 10 of an 11-page composed manual. Both composed PDFs have hash
`416e96f66bb6608b1e20bf5e36b6b16133bd4018c17e6c079e8987b736fe9cae`.
The integration record hash is
`ebe07ee10ad740a2bbbd36d532f336374cf4bb19ccb373b6590b2279f664a222`.
Generic verification confirms one bundle, one mapping and 14 verified files;
the native checker additionally binds the source and rendered page.

Local evidence root: `/tmp/opencode/unaltraweb-closeout-060/`.

| Retained evidence | SHA-256 |
| --- | --- |
| `candidate-letter-proof/evidence.json` | `618573b1a867daf6b1f3023e0d5700c27a6de429abea160b4c51ff8699f86f9c` |
| `candidate-roundtrip/evidence.json` | `23ec8885e8306931fb8ee4899e95b7bff4b3d23d2b63cdd3321e3f68722c3bb8` |
| `published-packages/verified.json` | `073d7ca1bbe46b8be5d89211501ca8fc7b71297d7eb542c4c9cc27ff167aa91e` |

The roundtrip exercised all four profiles using immutable MCP references:
0.4.0 `sha256:389bc585cdb4fc89d3372f4896a55fe26e15df38b46bc114ce44fdb3f1c8deb9`,
unpatched 0.5.0 `sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98`,
then the new 0.6.0 digest. The unpatched failure was reproduced on a separate
copy. Two builds and a preview passed at 0.6.0 and again after returning to 0.4.0.
All six author/cache files retained their hashes; no caches were emptied.

## Public downloads and post-release selection

Anonymous PyPI and RubyGems metadata and package bytes match the receipt exactly.
GitHub Release assets were downloaded again and pass `SHA256SUMS`, whose own hash
is `60d80d6e0803154a7b5c98c1731f4bec905def3a481152d4e59d7daf8932fc1a`.
A fresh public-wheel venv passed default `prepare`, `check` and real stdio `smoke`,
selecting the expected MCP configuration ID without a local factory dependency.
That public installation rechecked the relocated receiver and rendered mapping.
The public gem installed into an isolated gem home and activated as 0.6.0 using
the runtime's existing Ruby dependencies; this is not a network-fresh dependency
installation claim. The downloaded candidate gem also passed isolated native
helper-closure inspection.

The source-only post-release branch `chore/80-pin-published-mcp-0.6.0` selects the
published MCP digest in `Makefile` and `scripts/unaltraweb-mcp-bootstrap.sh`, updates
the pin regression and current docs, and accompanies this report. Its PR/merge
and final clean-main confirmation are recorded in issue 80 after protected CI.
It does not rebuild or alter the published receipt, tag or packages.

The post-pin local recheck passed 587 Python cases (558 passed, 29 optional
skips), distribution/workflow/wheel and prose checks, `mcp-check`, real
`mcp-smoke` with the selected public PDF, docs build and whitespace checks.
Development builds used only `unaltraweb-closeout-060-*:post-pin` resources.
The actual `MCP_CONSUMER_WORKSPACE`-bound `make mcp-stdio` transport also initialized
a fresh synthetic consumer and exposed both native import tools; Docker inspection
confirmed the published MCP configuration ID above. Its retained result is
`/tmp/opencode/unaltraweb-closeout-060/post-pin-proof/evidence.json` and the session
exited normally. `mcp-build` and the bootstrap's `--check` selected the public
runtime directly.

Acceptance covers the exact Linux/amd64 tuple and published English one-page
Carta sample. The generic conformance tests do not establish Diapora composition
or other domain imports. Active IDE processes keep their loaded runtime until
reconnected. No real manual, author artifact, client registration or helper
selection was migrated. Consumer adoption and hub catalogue integration remain
separate owner actions; this report supplies their verified intake evidence.
