# D0 native runtime identity and lifecycle — issue 85

Requirements: gaContExt
`5634ea2e3e42122bb365992dfca9f248feb89dec`,
[NATIVE_RUNTIME_REQUIREMENTS.md](https://github.com/dosquartsdedocs/gacontext/blob/5634ea2e3e42122bb365992dfca9f248feb89dec/src/bash/mcp_factories/NATIVE_RUNTIME_REQUIREMENTS.md).
Owner issue: [85](https://github.com/dosquartsdedocs/unaltraweb/issues/85).
Coordination: [gaContExt 15](https://github.com/dosquartsdedocs/gacontext/issues/15).

Delivery: [0.7.0 is published](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.7.0).
The [signed-byte delivery report](owner-closeout-85.md) supersedes the chronological
development/candidate state below. It retains the full managed-closure blocker and
the partial legacy identity gate; publication alone does not close them.

## Native API mapping

The containing 0.7.0 increment adds `runtime_identity` and
`web://runtime-identity` on the actual serving MCP instance. Both use one
startup-created object, not a helper CLI. It records a random backend instance,
process PID/start ticks/PID namespace, start time, interpreter, loaded package
version and startup package fingerprint. Current bounded package bytes and
metadata are separate observations; changing metadata cannot rename the loaded
version. Only engine code/contracts and allowlisted runtime selections are read,
not site content or arbitrary environment values.

The identity's component/profile/selection hashes bind the fixed requirements,
startup BOM, behavioral profile, worker selections and consumer mapping. The
package fingerprint is a startup code-content observation, not a wheel checksum
or a permanent process attestation. The live container's image ID, source label,
limits and mount mapping are inspected separately. Its daemon-host init PID is
not compared numerically with the inner serving PID. Session ID, exact container
ID, factory/role/project labels and mapping correlate those namespaces.

`runtime_drain(confirm=true)` freezes admission on that connection. Ordinary
tools execute in a bounded one-operation lane, leaving identity/drain responsive
while a worker runs. Closing stdio waits for active work and releases that
session's idle preview/capture resources. A new connection creates a new backend
instance. This profile is **one stdio connection per backend**, not a shared HTTP
service: shared-backend reattachment/idle leases are not claimed.

Host-side installed API:

```text
unaltraweb-mcp-docker prepare --image REF [--expected-image-id SHA256_ID]
unaltraweb-mcp-docker serve --project ROOT --image REF --expected-image-id SHA256_ID --managed
unaltraweb-mcp-docker session-status --project ROOT --session-id SESSION --container-id CONTAINER
unaltraweb-mcp-docker reap-session --project ROOT --session-id SESSION --container-id CONTAINER
```

Preparation may acquire the explicitly selected image. Launch/check/smoke never
build or pull; execution uses its inspected exact configuration ID with
`--pull never`. Managed mutable aliases require the expected full image ID.
Full local IDs and repository digests are immutable selections. Ordinary mutable
local selections without an expected ID remain an explicitly weaker mode.
Archive hashes, repository/index digests and Docker configuration IDs are distinct.

`--offline` disables controller networking; the explicitly mounted local Docker
socket still permits image/owned-container inspection. Preview HTTP probing and
intentional external metrics calls need their documented network access.
`--worker-images` accepts bounded JSON mapping supported worker names to exact
`reference` / `expected_image_id` pairs. Otherwise startup BOM/dedicated image
environment selections apply. Managed execution refuses missing/mismatched
workers and never substitutes a preparation build/pull. Authored computation
image choices must match the approved startup identity before execution.

The normal host launcher canonicalizes the consumer and binds it at its canonical
path and `/workspace`. A containerized launcher must supply `--host-project` (or
its explicit inherited daemon mapping); the child uses that verified canonical
mirror. Identity reports launcher-visible, daemon-host and effective paths.
Other direct controller layouts are not silently inferred. In particular,
[issue 31](https://github.com/dosquartsdedocs/unaltraweb/issues/31) remains a separate
boundary for arbitrary direct `/workspace` controllers and is not automatically
closed by this profile.

## Resource ownership

Each launch has a 32-hex session ID and a uniquely named owned stdio container.
Previews are per-session for these backends. Worker invocation tokens are retained
and augmented with session labels. Cleanup validates full IDs and ownership and
confirms absence before claiming release. Image and volume removal is outside
these APIs.

After EOF or a crash, the caller uses the **retained** binding/session/container
tuple with `session-status`. A live backend is `connected`; a running one-shot
worker is `busy`; idle leftovers are `orphaned`; only proven absence is `stopped`
with `resources_released=true`. Unavailable/changed ownership is `unknown` and
does not authorize removal. `reap-session` preserves a live backend or running
job, and recovers only that retired session's idle resources. Occupied or foreign
networks fail closed. No fresh-helper PID is presented as the backend's PID.

The legacy `down` / `make mcp-down` is an explicit **workspace-wide** shutdown;
`mcp-down-all` is maintainer/factory-wide. Neither is the hub's per-client toggle
operation. The managed sequence is live drain, close this transport, inspect its
exact retained identity, and recover eligible orphans when necessary.

The profile reports controller limits (2 CPUs, 4 GiB, 512 PIDs), preview/PDF/capture
limits (2 CPUs, 2 GiB, 256 PIDs), and managed computation limits (4 CPUs, 8 GiB,
512 PIDs). Existing per-invocation time bounds remain 1800 seconds for PDF/compute
and 900 for captures; requests may compose several bounded jobs. Per-backend
operation concurrency is one. A drain does not falsely claim immediate RAM/CPU
release while a job continues.

## Accepted visual-helper points and remaining closure blocker

Release 0.7.0 selects the published Diavisuals 0.5.0 and Vega 0.5.1 packages:

| Helper | Wheel SHA-256 | Renderer configuration ID |
| --- | --- | --- |
| Diavisuals 0.5.0 | `f52e20f20f1fb3a2418f07adb8d6a68a5567d0c321fb7c0ccc0f4db04917b96b` | `sha256:5a6887b372a0e1c386a7b54981d11ae1910215baeb6a12dfd0706b3e85ef0846` |
| Vega 0.5.1 | `5aba4f267a37179c520b3cd164e1cec62ac5561872aa33b069cce73442dc52b1` | `sha256:695125943d0fbc3aa7c877babb9a11a6501bbc7ac265b0975bb5657c60439d98` |

Native selector mapping is Diavisuals `--runtime-image` plus
`--runtime-expected-id`, and Vega `--renderer-image-id`. Published metadata,
wheel/acceptance hashes and locally prepared renderer IDs were verified. Actual
Mermaid, PlantUML, Vega-Lite/CSV and Vega rendering passed native receipt checks,
tamper refusal and consumer relocation without rewriting renderer aliases.
Retained evidence: `/tmp/opencode/unaltraweb-d0-85/helpers-proof/evidence.json`.

Previously accepted **0.4.0 static receipts remain valid** under the unchanged
input/output/request integrity rules. This is an exact legacy point, not a
continuous version interval or permission to overwrite edited outputs. New work
uses the selected helper points. No existing client or real consumer is migrated
by this source change.

The coordinator does not claim to observe another MCP's serving process. Its live
identity returns the helper selections and requires their independent connection
observations. **Selected Diavisuals 0.5.0 lacks the full live-instance identity**.
[Diavisuals 14](https://github.com/dosquartsdedocs/diavisuals/issues/14#issuecomment-5987114002)
already records the provider correction in published **0.6.0**; the issue remains
open for intake. That newer provider is outside unaltraweb 0.7.0's tested helper
point. The remaining gate is composing-owner compatibility acceptance and a new
reviewed selection of the corrected helper, followed by independent live
observations. It is not an unpublished provider implementation. Rendering
compatibility alone does not make the coordinator dependency graph managed-ready.

## Acceptance and delivery state

`test/d0_runtime_smoke.py` exercises installed launchers, actual images, tool/resource
agreement, independent consumers, reconnect, running-container metadata drift,
busy drain, offline launch, wrong/missing image refusal, manual/web work and
0.6.0 → containing 0.7.0 → 0.6.0 activation with retained authored/generated state.
The published 0.6.0 point accurately remains **partial** for live identity; no
fixture or relabelled package is counted as a second D0-capable release.
Backend-crash/orphan recovery is exercised separately from graceful disconnect.
The existing Carta and populated Bundler acceptance drivers remain release gates.

This is owner development evidence until reviewed source, containing release
receipts, installed signed-byte acceptance and remaining blockers are returned to
the central issue. Published 0.6.0 and its active checkout launcher pin remain
unchanged during candidate development. The worker/data choices and external
Diavisuals identity blocker must remain visible in the hub's adapter decision.

## Retained local acceptance — 2026-10-05

The owner explicitly authorized the full 0.7.0 review/PR/integration, gated
publication and post-release pin flow. No other checkout is a write workspace.

The installed local wheel
`67689b76225511439175c82b6df033005d84e990b147b8fa4875f3adbd7d684f` and owned MCP
image `sha256:d8eafba61a2e1f02bc22b244610d8174879e04d9ea36b47a71e8cd7f993a54b1`
passed eight stages: reconnect/scope, loaded-versus-disk, busy drain, backend
crash recovery, offline launch, explicit daemon mapping, wrong worker and missing
worker. The crash record observed a real PDF job still **busy** after backend
death, then confirmed eligible recovery and resource absence. The other live
instance was preserved. The published 0.6.0 A/B/A point remained explicitly
partial for live identity; authored files and its old cache entries kept their
hashes. This is prepared development evidence, not a signed release identity.

| Local retained evidence under `/tmp/opencode/unaltraweb-d0-85/` | SHA-256 |
| --- | --- |
| `acceptance-final/evidence.json` | `e35457153c5ffe98b4bd231f608735a2c4ad07e9db756699d7446e06e6b0b9c7` |
| `helpers-proof/evidence.json` | `df994ccd8afaff45a7e3cfa9b6a29b650c9d01d63db2c9c36e59c31834273473` |
| `carta-proof/evidence.json` | `ac305ad222a792291ebd27679a72a37a3ff29ab4746301ed9db7f64705ca4755` |
| `bundler-proof/evidence.json` | `b304c4c5abe45ae9295f6eba86eae36be92e348e6be33463fcb50e119550d341` |

The Carta proof retains the published sender seal and unchanged original PDF,
removes the copied producer, relocates the receiver and forces another PDF build.
Both 11-page manuals have SHA-256
`46e50f815c007a97ac59898194023de3fa4e916e77e7eac21b73f8792244713c`; the letter is
on page 10. The four-profile populated Bundler regression passed 0.4.0 → prepared
0.7.0 → 0.4.0, preserving all six tracked author/cache checksums and separately
reproducing the known unpatched 0.5.0 failure. No caches were cleared.

Review additionally tightened Docker absence classification: an unavailable
daemon socket is **unknown**, not evidence that a container was removed. That
source-only correction has a dedicated regression; final release acceptance must
be repeated against the actual source-bound candidates after integration.

The local suite passes 608 tests with 30 optional/environment skips. Distribution,
workflow, fresh-wheel and extracted-gem gates pass, as do the real MCP smoke,
manual preparation, docs build, prose checks and whitespace checks. These checks
do not override the separate signed-candidate/publication gates or the external
helper-process blocker.

## Reviewed core selection

Implementation `0c87e8c276e58ac9c747833df69cdb439aa6132b` was reviewed and
integrated through [PR 87](https://github.com/dosquartsdedocs/unaltraweb/pull/87)
as `216ab2e8b6b8b45a5bb7da0a54bffd10edee895d`. Protected PR CI
[37271200816](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37271200816)
and CodeQL [37271200817](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/37271200817)
passed. The recorded review is agent-attributed.

The next candidate source pins that integrated core and authorizes gem, wheel,
runtime and MCP as `ready` for same-source candidate preparation. The selected
signed PDF 0.6.0 and computation/capture 0.4.0 workers remain unchanged: the new
selection/lifecycle behavior is controller-owned. Strict receipt, ancestry,
candidate, installed-byte and publication gates still apply. This readiness is
for the containing owner release, not approval of the full managed coordinator
closure while the external Diavisuals identity gap remains.
