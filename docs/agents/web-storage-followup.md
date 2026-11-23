# Bounded storage follow-up before real manual adoption

## Separate source scopes

The established Web owner continues from `710c73765e44ef57e57b0b638dd4eeb9ea53d706`
in the same primary checkout/local branch. Existing-WIP checkpoint admission
selects only intended technical files with hooks and preservation verification.

- #114 is a separate two-file checkpoint
  `385fd396a68889d05c231da9153bfb8fdff0174f`, reviewed in
  [Draft PR132](https://github.com/dosquartsdedocs/unaltraweb/pull/132), based on
  PR131's immutable source. It prunes explicitly excluded private roots before
  snapshot traversal and retains source/index/blob/implementation-input safety.
  Live socket/source/receipt regressions and the full 821-test established-tree
  suite (28 skips) pass before that checkpoint. `TODO.md` stays separate WIP.
- The transport follow-up is separately stacked on that checkpoint. It corrects
  official Bitbucket URL interpretation and retains local S3 uncertainty evidence;
  it does not recreate the adapter, alter frozen product/route schemas or admit
  Geodisseny's untyped outputs. PR129/130/131 review sources retain their heads.

## Native repository parser

Official `git@ssh.bitbucket.org:<workspace>/<repo>.git` and
`ssh://git@ssh.bitbucket.org[:22]/<workspace>/<repo>.git` identify logical
`bitbucket.org/<workspace>/<repo>`. Standard existing hosts and explicit default
SSH port 22 are admitted. HTTPS/web IDs retain their old host/port/credential
rules. Fetch/push declarations must still agree with native consumer metadata;
repo/bucket spelling remains exact. No workstation alias, lookalike host,
password-bearing URL, nondefault port, remote rewrite or SSH repair is added.

## Small local uncertainty record

The existing source/config/destination/manifest checks and named-v1 transfer stay
authoritative. A new private attempt directory outside the immutable stage holds
only whitelisted intent metadata and an append-only, fsynced observation chain.
Before requests it binds exact source/config/policy/destination/manifest identity;
once an UploadId is observed, its exact bucket/key/id is retained before parts.
Acknowledged part counts/bytes and create/complete/readback/abort phases are bounded.

The source review reports Geodisseny candidate metadata of 32 PDF/ZIP files,
437,022,560 bytes total and a 101,583,048-byte maximum. This exceeds the existing
64-MiB multipart threshold and makes lost abort/complete observations a real
readiness concern. This unit reuses that read-only metadata; tests use small
synthetic providers and the pinned SDK model, with no real bucket fixture.

Lost create responses retain an unknown ID. Failed parts can request abort of
the exact observed owned tuple after retaining intent; abort ACK is distinguished
from remote absence/verified cleanup. Abort uncertainty retains the tuple. After
completion uncertainty no automatic abort or retry is attempted: final bytes may
already exist and can be inspected read-only. Evidence or binding tampering stops
further mutation. Safe failures expose only fixed messages, phases and private
receipt pointers, excluding provider bodies, credentials and teacher content.

`inspect-attempt` verifies local intent/event hashes and the bounded chain; it
does not resolve auth, call a provider or recover anything. Explicit `verify`
may establish exact existing output bytes while still refusing missing later
metadata. Success/repeat creates separate local evidence without rewriting old
stages, producer/manifest identity or prior attempt records. No journal is uploaded.
Local evidence is not a remote registry, ownership inference, recovery executor
or cleanup permission. A partial/damaged local record is not claimed complete.

## Qualification boundaries

Selected source/PR/CI/checkpoint/test/schema/CLI/evidence pins are returned in
the new ignored `sandbox/coordination/web-storage-followup-return.json`.
Matching source-containing MCP/PDF and public wheel/docs checks qualify source,
not a containing published release or a real manual pilot. Existing earlier
mismatched PDF tuple evidence remains retained; freshness and companion pins are
not bypassed.

TIGIT/TIG still need closed native products. Geodisseny's current simple manifests
and author/proof state require the separately bounded native-intake gate already
reported. Actual project-scoped bucket/auth/readback/ACL/restore/link qualification,
reviewed runtime publication/adoption and author/native acceptance remain owner
work. This slice performs no real S4/Meum/teaching upload, bucket creation, public
URL activation, consumer edit, client cutover, merge/tag/release or new SSH script.

## Local source verification

- Full required source suite: **836 tests, 28 explicit skips**, with the declared
  public dependency environment. The two new repository parser regressions and
  thirteen attempt-evidence regressions include the real pinned Botocore multipart
  part/abort failure model, and synthetic lost-create/uncertain-complete/readback,
  source/config/destination/evidence tampering, symlink confinement, privacy and
  idempotent stage-preservation cases.
- Distribution/workflow/wheel/whitespace checks pass. The public wheel includes
  the local evidence helper and factory-free CLI inspection interface.
- Independent native common inspector/planner/named-v1 fetch still reconstructs
  two ZIPs and one private PDF exactly, with object-URL methods unavailable. Local
  journals never enter the three-file product or its four remote objects.
- A source-containing local MCP check, full MCP/PDF/practice/preview smoke and docs
  build pass. Both local MCP/PDF builders use SHA-256
  `d3d580ef5810383fa195da5633137123f55164b059766950dd204deba01a30bf`.
  Matching development source and earlier failed published-worker evidence remain
  distinct from any published runtime selection.

Committed-tree CI, exact source/driver/helper pins and checkpoint preservation
evidence are recorded in the new owner return after technical publication.
