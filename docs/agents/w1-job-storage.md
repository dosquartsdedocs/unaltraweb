# W1 job storage and product reception — owner implementation

Owner issue: [unaltraweb #102](https://github.com/dosquartsdedocs/unaltraweb/issues/102).
Coordination: [gaContExt #22](https://github.com/dosquartsdedocs/gacontext/issues/22).
Visual-helper composition remains tracked in [#85](https://github.com/dosquartsdedocs/unaltraweb/issues/85).

## Pinned authority and intake

The normative `docker-job-volumes-v1` contract, schema, examples and reference
tests are selected at gaContExt **83cb0d3e2f424759475ae70b423a0f8dca8520b2**:

- `src/bash/mcp_factories/JOB_STORAGE_CONTRACT.md`
- `src/bash/mcp_factories/job-storage-v1.schema.json`
- `src/bash/mcp_factories/mcp_job_storage/contract.py`
- `src/bash/mcp_factories/mcp_job_storage/planner.py`
- `src/bash/mcp_factories/examples/job-storage/`
- `tests/test_mcp_job_storage.py`

[PR #23](https://github.com/dosquartsdedocs/gacontext/pull/23) merged at
**f847fb118c6f5cd84767c49c87f8b9c65bd790ae** on 2026-10-07. The pinned revision
is its verified merge base, two commits behind that integration, not an
unmerged proposal. Its schema Git blob is
`7ad4eea34479af0bf62a982c736a22ac055e1bd9`.

The Web baseline is published 0.7.1, tag target
`1ff25c6956458c3a99436312466e9cc588ed34b9`. The accepted practice-reading slice
was integrated by [PR #101](https://github.com/dosquartsdedocs/unaltraweb/pull/101)
at `d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0`, after PR/push CI and CodeQL passed.
The W1 branch is `feat/102-w1-job-storage`. Its initial native preflight was
ELIGIBLE, clean, with one checkout and no competing active editing session.
Exact paths are reserved in owner #102; real manuals are outside this session.

## Implementation boundary

This owner implements the contract's permitted **standalone private-registry
manager** while the shared host bridge is pending. The upstream checker/planner
remains a read-only conformance oracle. Source declarations and reference plans
are not evidence of allocation, execution or retirement.

The implementation must provide:

- The installed/source companion `mcp-job-storage.json` and native
  `job_storage(request)` status/quiesce/seal operations, with the exact W1
  envelopes. Volume names never enter legacy Git path policies.
- A bounded external private ledger, authenticated startup-selected consumer
  context, CAS revisions, fencing epochs and independently observed leases.
  Identifiers and public binding documents are not bearer credentials.
- Two unique registered local volumes per domain job: retained at `/work`,
  scratch at `/work/scratch`, with no copy-up and checked immutable markers.
  Actual daemon, creation, labels and all container attachments participate in
  retirement. Docker private host Mountpoints are not application paths.
- Volume-backed site/PDF/practice builds, previews, captures and computation.
  Selected source snapshots and successful results survive scratch removal.
  Ordinary workers do not use a writable consumer/factory checkout as staging.
- Receiver-selected durable paths, exposed assets and directory/zip/tar-gzip
  retention. Complete common/domain validation precedes an acknowledgement.
  The manager re-observes final retained bytes independently; an agent-supplied
  acknowledgement or a temporary preview cannot resolve retention obligations.
- Monitored budgets with actual daemon-filesystem observations, outstanding
  reservations and bounded measurement intervals. Hard quota support must not
  be invented for ordinary Docker local volumes.
- Exact, non-force, journalled volume removal after fresh ownership, marker,
  attachment, lease, inventory and durable-witness checks. Unknown or pending
  sources/results remain retained; interrupted retirement resumes from actual
  observations and preserves terminal tombstones.

Existing repository jobs and authored SVG variants are not retroactively owned
or cleaned up. Authored site state, explicit final publication and durable
receiver selection remain separate from disposable execution workspaces.

## Acceptance and release gates

Acceptance uses synthetic sites and actual workers, including figures and real
web/PDF output. Required evidence covers each advertised retention format,
freshness, relocation after producer retirement, partial copies, author edits,
pending products, two clients/busy work, crash/orphan recovery, disk pressure,
stale epochs/plans, foreign/replaced volume identities and stopped attachments.
Report observed resource absence and hashes; preserve unresolved material.

The composing-owner target is actual published Diavisuals 0.6.0 with its native
reference/expected-ID selector. Preserve Vega 0.5.1 and integrity-checked
historical Diavisuals 0.4.0/0.5.0 receipts. Core, reusable workflow and PDF producer
identities stay independent. Changed published bytes require the normal
component/receipt/release flow; no old release is rewritten.

## Native storage increment (development, 2026-10-08)

The source implementation and installed test runtime now provide the native
storage manager and receiver. This is an increment on draft PR #103, not a W1
release or acceptance of all the domain pipelines listed above.

### Declaration and API

- Companion SHA-256:
  `abba9be2d362665dfb4a3108e4061b5b632140e0dfb70a50c910f33142d47108`.
  The launcher companion and `unaltraweb_mcp/job_storage/provider.json` are
  byte-identical. `web://job-storage-provider` serves those exact installed bytes.
- Pinned schema SHA-256:
  `25e2bf047715e170ad8975ca3fd81d0597bdb0fead9ac6c52e8a777b3fb6434c`.
- `job_storage(request)` and package-only CLI
  `unaltraweb-mcp --project PATH mcp job-storage --request-json JSON` expose
  status/quiesce/seal. Unknown fields, workspace overrides and stale CAS values
  are refused. Errors have bounded `code`/`error` fields and `ok:false`.
- Native `Manager` operations implement admission, input streaming, execution,
  sealing, read-only delivery, independently checked acknowledgement, exact
  release plans/application, client attachment/detachment and scoped recovery.
  These Python operations are internal authority, not an arbitrary-command MCP.

The host launcher selects a private persistent registry outside the consumer,
defaulting to `$XDG_STATE_HOME/unaltraweb/job-storage-v1` (or the corresponding
`$HOME/.local/state` path). `--storage-state` selects an explicit alternative.
The controller receives a checked bind at `/var/lib/unaltraweb-job-storage` and
the observed directory identity; the server fixes that selection at startup.
Containerized launchers additionally need the explicit `--host-storage-state`
mapping for W1. A connection without that mapping can still use non-storage
operations; it cannot allocate jobs using an ephemeral controller HOME.

The registry uses private descriptor-relative files, CAS, process-held lease
guards and bounded logs/metadata. Native workers have read-only container roots,
registered no-copy volume mounts, no consumer/factory checkout or Docker socket,
and run domain code as UID 65532. The supervisor can signal its own isolated
domain process group when monitored limits are exceeded. Ordinary local volumes
provide monitored limits, not hard quotas. Capacity is observed using a separately
registered small persistent probe volume on the actual Docker storage filesystem.

### Receiver policy and preservation

The current accepted domain is **`unaltraweb-job-v1`**. A site selects its durable
layout once, for example:

```yaml
unaltraweb:
  product_retention:
    enabled: true
    root: .unaltraweb/products
    format: zip
    profiles: [unaltraweb-job-v1]
    assets:
      root: assets/received
      roles: [rendered-visual, edited-visual, document]
```

Directory, ZIP and gzip-compressed tar retain the complete common bundle and
native input inventory. Archive extraction and domain checks use fresh managed
job volumes. Archive-byte and inner-bundle hashes remain distinct. Selected
assets include the transitive resource closure and an edited SVG's original.
Publication is create-only/no-replace, with retained partial candidates on error.
An existing destination is revalidated before reuse; authored collisions are
preserved. A relocated copy receives a fresh independent receiver binding and
complete checks, not authority copied from the original registry.

`runtime_drain` stops admission. Graceful EOF drops the connection's tracked
interests; other clients keep their jobs. Client SDKs can force termination before
graceful storage cleanup completes. The standalone host manager therefore also
supports exact post-termination recovery through
`unaltraweb-mcp-docker reap-session --project PATH --session-id ID --container-id ID`
with the selected `--storage-state` and prepared utility `--image` when needed.
It selects only jobs recorded for that exact backend, proves backend death,
reconciles operation leases, and then applies the normal retention gates.
The ordinary D0 reaper observes W1 workers but cannot bypass their private journal.
Runtime absence and retained pending storage are reported separately.

### Observed evidence

`test/job_storage_smoke.py` is an opt-in native test with create-only synthetic
fixtures. Failed runs and unresolved jobs remain available for inspection.

- `tmp/w1-102/native-acceptance-10/`: actual directory, ZIP and tar-gzip delivery,
  idempotent reuse, producer volume retirement, independent verification of all
  11 files afterward, receiver relocation, and preservation/refusal of an authored
  SVG change. All three formats used actual Docker volumes and native stdio.
- The same run's `faults/evidence.json`: two independent native client processes,
  a busy worker, actual controller kill, scoped orphan recovery, monitored
  scratch-pressure cancellation and admission refusal against observed daemon
  capacity. Pending source/result volumes remain retained; eligible scratch is
  observed absent. An unsupported hard-quota request is refused.
- `tmp/w1-102/native-eof-recovery-11/evidence.json`: real installed MCP seal,
  status available after drain, actual backend termination and external-manager
  completion after the SDK's bounded EOF grace period. Pending job
  `372529e5fd3e4c0881f59b9a0f33f232` is closed with scratch absent and its complete
  sealed product retained. The earlier interrupted EOF in run 10 also recovered
  through the exact recorded backend identity (`pending-eof/recovery-evidence.json`).
- Prepared development MCP configuration ID used for these installed tests:
  `sha256:1119be0bde21e03c07c4ab9b66659104dbf38fd2d70e8699ffe2a7910c499437`.
  It is a development image, not a replacement for published 0.7.1.
- Focused unit coverage includes archive traversal/link/duplicate/case-alias and
  truncation refusal, missing resources, reduced source/mapping inventories,
  policy/binding staleness, author preservation, receiver/registry locks, stream
  failure/timeout and inherited guard descriptors. Current full suite: **690
  cases, 663 passed and 27 optional skips**. Wheel packaging/clean installation,
  distribution validation, native MCP check/smoke and whitespace checks have passed.

### Remaining W1 gates

The existing site/PDF/practice/preview/capture/computation APIs still use their
previous execution paths. Their migration to the native jobs, complete real
web/PDF figure acceptance and new component/release tuple remain work in this PR.
The increment does not yet accept other producers' domain bundles, implement
explicit reopen/user-discard, or establish the full native fault matrix for
foreign/replaced resources, interrupted release and concurrent delivery. The
upstream read-only planner remains an independent conformance gate to exercise.
Diavisuals 0.6.0 composition and historical receipt acceptance remain tracked in
#85. No complete W1 adoption, hub activation, real-manual migration or new public
release is claimed by these storage-layer results.
