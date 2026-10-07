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

This intake records requirements and scope. Implementation, native API mapping,
descriptor SHA-256, Docker evidence, PR/release references and supported-profile
limits will be recorded here as they are actually established.
