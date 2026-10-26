<!-- @gacontext-owner: provider; @gacontext-origin: seeded-once -->
# Provider-owned MCP implementation

Keep domain-specific CLI/modules, Docker recipes, resources, prompts and tests here,
or map their existing repository-relative directories in `provider.json`.
gaContExt updates do not replace these files, even if they started as seed templates.

`provider.json` separates editable parameters and named dependency links from common
code. Each link is an existing H1 requirement: provider, accepted version/capabilities
and source preference. A task selects the links it needs. Metadata planning does not
install, activate or execute them and does not assert domain compatibility.

Common runtime/storage behavior comes from the verified `gacontext-runtime
0.1.0a7` wheel selected by `src/unaltraweb_mcp/shared-runtime.json`. No local
allocator/ledger/marker/cleanup implementation is added. The canonical
`gacontext/` revision-2 directory is updated only with the installed scaffold CLI.

The existing implementation is explicitly mapped in `provider.json`:
`src/unaltraweb_mcp`, `scripts/manual`, and `prompts`. `mcp-job-storage.json` and
its byte-identical installed copy declare monitored limits within the common
512-MiB/file, 2-GiB/snapshot and 10,000-entry ceilings.

`build` requires explicit `SHARED_OUTPUT`, `SHARED_DOCKER_ENDPOINT`,
`SHARED_DAEMON_ID`, `SHARED_SDK_WHEEL`, and `SHARED_WEB_WHEEL`. It only uses bases
already prepared on that daemon. The direct preparation CLI additionally offers
an explicit `--pull-bases`; ordinary native tools never prepare or pull.

`smoke` requires `SHARED_TEST_ROOT`, `SHARED_EVIDENCE_DIR`,
`SHARED_COMMON_HARNESS`, `SHARED_SDK_WHEEL` and `SHARED_WEB_WHEEL`. It uses a new,
bounded rootless daemon, the canonical common harness and synthetic sources.
Source/package/result evidence is retained and checked before its exact test
caches are retired. Production resources and historical W1 jobs are not targets.

`make -f mcp/Makefile smoke-edition` adds the native QGIS-to-PDF/ZIP flow. It
requires those same variables plus `SHARED_QGIS_BUNDLE` (the qualified synthetic
bundle directory) and `SHARED_VERIFIER_ARCHIVE` (an explicitly saved exact private
controller image). It imports that image into the new isolated daemon and checks
its immutable ID/SDK. It does not pull a private image or recompute GIS.

`stdio` requires the explicit private `UNALTRAWEB_SHARED_JOB_CONTEXT` file and the
original `MCP_CONSUMER_WORKSPACE`. It does not initialize the service or allocate a
new slot. The context binds an existing service, daemon, task, owner, job and SDK
PDF image. `worker_user` records the service host UID/GID; the common admission
check remains authoritative across container UID namespaces. Optional
`worker_timeout_seconds` is an operator-selected integer from 1 to 900 (default
900), fixed at startup and enforced by the SDK. Per-attempt requests and live
render logs remain protected when that deadline terminates a worker.

A7 grants carry manager-owned `docker_ownership` plus a sibling `.docker.json`
sidecar. The controller's read-only service mount must expose both grant files to
`create_args`; the worker still mounts only the unchanged W1 binding. Web uses
the identity-equal mapping without supplying a Docker-factory alias.

For shared editions, the operator must register both the prepared PDF image and
the exact private image in `shared-practice-verifier.json` for the Web provider,
then set `edition_verifier_image` to that accepted image in the startup context.
The source edition must explicitly select `qgis-practice-v3` and the same
package/image/schema pin. Classic v1/v2 selections retain their published contract.

Native checks and composition are separate SDK actors. Full input closure,
approved reading hashes, student/teacher separation and editable resource checks
precede sealed PDF/ZIP output. Completed candidates are installed with atomic
no-clobber publication within the retained volume; partial attempts remain in
protected results/recovery. The returned product awaits explicit common receiver
delivery; it is not a claimed host `dist` path or a teaching approval.

The qualified local slice covers initial/resolved QGIS projects, data/fonts and
editable SVG resources in paired PDF/ZIP deliveries. A required `evidence/control`
export witness remains a concrete classroom-closure refusal. The separate public
QGIS final-ZIP reopen currently fails with the candidate SDK worker's temporal
environment; its evidence and coordination request remain distinct from the
passing shared composition/retention proof.
See `docs/agents/shared-practices-116.md` for exact evidence and remaining gates.
