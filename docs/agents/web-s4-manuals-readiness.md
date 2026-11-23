# Minimal S4/manual readiness — owner continuation

## Source and authority

This unit continues the existing Web owner checkout on
`feat/web-b-practice-preparation-v1`, from `7bcd48f8900c059c465e29fffc55a62fe0b957fb`.
The owner authorises tested technical commits, push and PR through the explicit
existing-WIP checkpoint protocol. The first verified checkpoint is
`b9b05b18ef1d9e42bc30b1f83d5fdeab1eb8bb30`: 22 storage-related paths selected,
all 25 WIP entries preserved, empty final index. `TODO.md` and the #114
`manual_release.py` / `test_manual_release.py` changes remain separate WIP.

PR129 owns temporary candidates; PR130 owns early preparation/tabular editions.
This storage source is a stacked review unit based on PR130's exact source, with
its route v2 delta in a separate commit. Its shared packaging/Make/MCP/docs
touchpoints require explicit integration; neither a combined runtime nor consumer
adoption follows from the source review. The checkpoint/publication procedure
keeps this checkout on its existing local branch/worktree and retains other WIP.

## Bounded implementation

The existing publication/transport adapter remains authoritative. Route v2 adds:

1. Explicit `consumer_repository: {remote, host, repository}` verified against
   native local Git remote URLs through the existing confined Git/root helpers.
   Selected S3 bucket equals the **exact repository slug**, independently of
   physical checkout name, logical `project_id`, public target repository or
   prefix. Missing/multiple/conflicting identities have stable diagnostic codes;
   no bucket normalisation or core-repository fallback is admitted.
2. Per-artifact `storage_profile`. `authenticated-private-v1` requires private
   bucket ACL/policy and authenticated SHA/size/MIME/Content-Disposition plus
   native object ACL for outputs, metadata and both manifests. It emits no public
   URL and claims no anonymous qualification. It never sends an unsigned object
   request or requires a MEGA account identifier. `anonymous-delivery-v1` retains
   exact public anonymous bytes/headers and actual private URL denial; arbitrary
   HTTP 400, including the observed S4 SigV4 error, fails that qualification.
3. Explicit retained-stage planning/transfer by the original manifest SHA. Old
   producer revision and exact manifest/output bytes are validated and retained
   when the control plane or route/profile changes. The frozen common product/
   policy schemas and original Web route v1 schema are not rewritten.

The owner's Meum host evidence already distinguishes authenticated S4 API storage
from disabled/account-routed object URLs. This unit uses that requirement and
offline tests; it performs **zero real S4 endpoint operations** and imports no
Meum/hub credentials. Native named-v1 filenames, headers and canonical restore
manifest stay compatible with the existing authenticated common reader. Web does
not label this projection `files-v1` or introduce a domain/restore engine.

## Read-only consumer intake matrix

| Consumer | Observed source | Expected bucket | Current intake | Next native gate |
| --- | --- | --- | --- | --- |
| TIGIT (`geourv/tigit`) | `7a8b314d743b62699232c66d7024387f86f59281` | `tigit` | Resource/source list exists; no current `dist/practiques` tree. | Owner prepares exact inputs/readings and a native sealed edition before selecting PDF/ZIP outputs. A resource list is not a closed product. |
| TIG (`geourv/tig`) | `c045d46a8e7139adf9f060eeeaf4e47781dfd355` | `tig` | No current `dist/practiques` tree. | Owner completes native reading/edition preparation from the retained inputs/proofs, then byte/recipient/extracted-packet acceptance. |
| Geodisseny (`geourv/geodisseny`) | `7b1c4fcd3e21062c7be19e322a000170cf9b0ba0` | `geodisseny` | Eight simple current practice directories, 56 files at `dist/practiques/<activity>/ca/`. Existing untyped local `manifest.json` is **not** Web edition receipt v1. | Separate bounded native intake/resealing contract preserving original ZIP/PDF bytes, historical proof, recipient mapping and author-approval state. |

All three currently select MCP 0.7.4 / PDF worker `1bb3f2da…`, lack the new route
configuration and artifact plan/stage Make facade, and need an explicit reviewed
runtime/config adoption. Read-only remote metadata identifies their `origin` as
the corresponding consumer repository. No consumer source, config, ignore rule,
Makefile, runtime pin or teaching output is changed by this unit.

Geodisseny's current seven-file layout is `<activity>.zip`,
`<activity>-docent.zip`, `LLEGIU-ME.pdf`, `LLEGIU-ME-docent.pdf`,
`ENUNCIAT-MOODLE.md`, `manifest.json`, `SHA256SUMS`. Its manifest contains activity,
version, run, packages with recipient/archive/member/reading/PDF-receipt hashes,
proof/proof hash, Moodle statement hash, `human_approved`,
`exact_historical_bundle` and `local_candidate`. Read-only metadata reports
`human_approved:false` in all eight current manifests. These files/proofs must not be renamed,
repackaged, given forged Web receipt kinds, or treated as a GIS/author approval.

The smallest follow-up is an owner-approved **native common Web intake** design
for existing paired outputs: validate the exact retained manifest/proof/reading
seals and recipient ZIP closure, establish an explicit version identity and
retained typed receipt beside the originals without changing their bytes. Native
GIS verification and human approval remain their owners' gates. Until that
interface is separately agreed/tested, this Web planner deliberately refuses
the untyped simple manifest. It does not invent a Geodisseny-specific engine.

## Priority and adoption order

1. Resolve build blockers and qualify a **matching** source-containing MCP/PDF
   tuple before consumer cutover. The #114 excluded-private-socket correction is
   preserved as separate local WIP; the earlier published-PDF/checkout builder
   mismatch remains recorded in `practice-artifact-storage-review.md`.
2. Prepare/admit closed native practices and resolve required author/recipient
   review. These inputs are more urgent than an upload for the three consumers.
3. Integrate/test/release the reviewed Web source through the ordinary owner
   process; companion/QGIS closure and Diavisuals selections have their own gates.
4. In a separate scoped operation select the repository-named bucket, project-
   scoped credentials and actual retained artifacts; qualify authenticated readback,
   headers, private native ACL and restore. Select public object links only after
   their independently authorised exact anonymous qualification. Storage success
   does not update a catalogue, approve teaching material or imply a public URL.

No merge, tag/release, runtime/client cutover, bucket creation, real practice
upload, public teaching/CV/site delivery or SSH repair is authorised by this unit.
Actual source/PR/CI/test/schema/CLI pins and remaining gates are returned in the
new ignored `sandbox/coordination/web-s4-manuals-readiness-return.json`.

## Local verification

- Full required source suite: **821 tests, 28 explicit skips**. Ten additional
  native/offline regressions cover exact repository buckets, missing/ambiguous/
  mismatched/core identity, protocol spelling without bucket normalisation,
  explicit private capability, PDF/ZIP readback, actual ACL/header/byte failures,
  raw API 400 refusal, preserved v1 stage identity and untyped intake refusal.
- Real pinned Botocore model/Stubber exercises authenticated conditional PUT,
  exact GET metadata and GetObjectAcl. No real storage endpoint is contacted.
- Distribution, workflow, wheel and whitespace checks pass. Public Python CI now
  installs the optional artifact SDK so this model case runs there as well.
- Independent common product/destination inspection accepts mixed GitHub/S4
  artifacts. The existing native common S3Store/named-v1 fetch reconstructs two
  ZIPs and one private practice PDF in new temporary roots, with exact manifests,
  metadata and files, while object-URL methods are explicitly unavailable.
- Source-containing local `mcp-check`, real MCP/PDF/practice/preview smoke and
  `docs-build` pass. The MCP image layers current source on the reviewed 0.8.1
  base; the existing matching local PDF development image is used. Both expose
  builder SHA-256 `d3d580ef5810383fa195da5633137123f55164b059766950dd204deba01a30bf`
  and identical PDF Dockerfile/filter/template bytes. Earlier mismatched public
  worker evidence remains in the previous review record.

These local tests use the established working tree, including preserved #114
WIP. The selected committed-tree CI is a separate source qualification; actual
head/PR/check IDs are retained in the owner return. Development images are local
test fixtures, not published runtime pins or consumer-cutover evidence.
