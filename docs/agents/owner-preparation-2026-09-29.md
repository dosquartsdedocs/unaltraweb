# Checkout-free MCP launcher: owner preparation report

Date: 2026-09-29. Hub handoff: **unaltraweb owner preparation**, following
`gacontext/src/bash/mcp_factories/handoffs/owner-preparation-prompts.md` and its
existing-manual baseline. Tracking: [issue 76](https://github.com/dosquartsdedocs/unaltraweb/issues/76).

## Source and delivery status

- Primary checkout: `unaltraweb`; branch `feat/76-distributed-mcp-launcher`.
- Base/source checkpoint: `260271e41b17be0f95dcb8047014c35cb97142ee`.
- Implementation is an **uncommitted owner working-tree change**, not a release,
  tag, pushed branch or PR. The hub can ingest this report without changing its
  catalogue or activating a client registration.
- The full published 0.5.0 GHCR runtime already contains the factory and supports
  checkout-free site work. No replacement image release is needed to run it.
- The published 0.5.0 wheel lacks the standalone host launcher. The new wheel
  contents require a future reviewed package release under a new version. The
  local test wheel still reports source version 0.5.0 and must never replace the
  published wheel of that name.

Changed paths:

```text
Makefile
pyproject.toml
packaging/launcher/Makefile
src/unaltraweb_mcp/docker_launcher.py
scripts/unaltraweb-mcp-bootstrap.sh
scripts/test_wheel_install.py
scripts/validate_distribution.py
test/test_distributed_launcher.py
test/distributed_launcher_smoke.py
docs/_documentation/en/40-distribution.md
docs/agents/mcp-contract.md
docs/agents/owner-preparation-2026-09-29.md
```

The source `mcp-factory.yml`, component BOM/schema, published receipt, managed
consumer scaffolds and their version selections are unchanged. Preserved hashes:

| File | SHA-256 |
| --- | --- |
| `src/unaltraweb_mcp/component-contract.json` | `f3de4b289fc6ae66ddc86bf6a701b3a2cfaed66ab6303f64252c92639a7aab98` |
| `release-candidates.json` | `e57a9dbb041c1e7fcd781cd1524f4de0317382e0f7303bb36bfa59c0b6d1cb9b` |

## Native installed profile and capability boundary

The wheel installs `share/unaltraweb-launcher/Makefile`, the **byte-identical native
schema-v1 `mcp-factory.yml`**, and the existing bootstrap, project-ID, CSV mount and
cleanup scripts under `scripts/`. It uses the current `runtime.kind: container`,
`runtime.package_manager: docker`, consumer binding, `transport.command` with
`make -C ${factoryRoot} mcp-stdio`, and inherited `MCP_CONSUMER_WORKSPACE`.
Here `${factoryRoot}` names the installed launcher directory. No new H1 fields or
alternative central schema were introduced. Companion lifecycle flags and exact
tool/resource inventories remain those in the native manifest.

`unaltraweb-mcp-docker path` resolves that directory from installed wheel metadata.
`manifest` prints the descriptor. `prepare`, `check`, `smoke`, `serve` and `down`
delegate to packaged shell scripts. Preparation may pull; check/smoke require a
local image, use its immutable local ID and mount neither source nor consumer.
Serve requires an explicit consumer and preserves both canonical host-path mounts
and the original factory/project labels. Cleanup retains its exact project scope.

The profile directory is independently relocatable with Make, POSIX shell, Linux
core utilities and Docker. The console adapter requires Python. The native
`unaltraweb-mcp` CLI retains the BOM's exact package-only and factory-required
inventories: shipping a Docker adapter does not put Ruby/core/TeX/Chromium or
worker/companion implementations into the wheel. `new-web`, doctor and inspection
remain usable natively; full MCP serving and build/PDF orchestration execute in
the selected GHCR image.

## Published identities and dependency closure

Native identities use existing BOM `kind`, `version`, `release`, `reference` and
`image_repository`, and manifest `mcp_dependencies[].uv_spec`. Container references
below are in `ghcr.io/dosquartsdedocs/`; each hash is an OCI repository digest,
not a Docker image configuration ID.

| Component / repository | Version | Exact selected digest |
| --- | --- | --- |
| Full MCP `unaltraweb-mcp` | 0.5.0 | `sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98` |
| Base Ruby/Jekyll `unaltraweb` (receipt) | 0.5.0 | `sha256:4c7bfa51b8f936993ca5a1350d8b63ac3af77f88e97065a9b4a223583528fa8e` |
| PDF `unaltraweb-manual-pdf` | 0.5.0 | `sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097` |
| Python `unaltraweb-compute-python` | 0.4.0 | `sha256:18cb269811bd4005800382da25a480ec2bca7eac8d0501ad1ef36bad1c0f8cd9` |
| R `unaltraweb-compute-r` | 0.4.0 | `sha256:928ffb93f221e09e8b929157dee473b838e061915a2eb67224e4124b85f81837` |
| Chromium `unaltraweb-web-capture` | 0.4.0 | `sha256:0bf1bc67fe63e1440bffe708a168beefa11c54441650a871ab99380d362f7c1e` |
| Historical full MCP `unaltraweb-mcp` | 0.4.0 | `sha256:389bc585cdb4fc89d3372f4896a55fe26e15df38b46bc114ce44fdb3f1c8deb9` |
| Historical PDF `unaltraweb-manual-pdf` | 0.4.0 tuple | `sha256:bb3e373f8a512495eeed684c23ad904d298c2e20a6dc3ade0d0a60c7ec9a9f11` |

The runtime layer is embedded in the full MCP image. The four workers remain
separate feature-selected containers; compute/capture were inventoried, not
rendered again in this preparation. Companions remain separate MCP servers:

| Companion | Native selected wheel and SHA-256 |
| --- | --- |
| Diavisuals 0.4.0 | `diavisuals[mcp] @ https://github.com/dosquartsdedocs/diavisuals/releases/download/v0.4.0/diavisuals-0.4.0-py3-none-any.whl#sha256=bfedcc9e2554f25ce4a1c33e556f352210848fccb8da800d1c3900dd86c48c93` |
| Vegavisuals 0.4.0 | `vegavisuals[mcp] @ https://github.com/dosquartsdedocs/vegavisuals/releases/download/v0.4.0/vegavisuals-0.4.0-py3-none-linux_x86_64.whl#sha256=b52ffa743643dd6b5e0320e7a9aa0cd500ea06262b7d5098c0c3f94a379bc0ea` |

Both dependencies retain `required/install/build/check/smoke: true` and
`init/update: false`. Their renderer archive identities and earlier real receipt
acceptance are in [visual-companions-0.4.0.md](visual-companions-0.4.0.md); that
2026-09-26 evidence is not presented as a new rendering run here. Historical core
0.4.0 selects companions 0.3.1; the 0.5.0 receipt verifier does not promise to accept
those older provider identities.

## Synthetic acceptance and isolation

Platform: Linux/amd64, host Python 3.12, Docker 27.2.0. A non-editable wheel was
installed with `--no-deps --no-index` into
`/tmp/opencode/unaltraweb-owner-20260929/venv`. Its launcher metadata resolved
outside the source checkout. The retained test wheel SHA-256 is
`a8b2136ffb23970980b86b70e64d509e2e24500f1e032b023f857cde22a7988f`.

All acceptance consumers, Git indexes, caches, generated PDFs and Jekyll outputs
are synthetic under `/tmp/opencode/unaltraweb-owner-20260929/`. No host core was
mounted. Preview inspection verified only the synthetic consumer bind and no
Docker socket. Ports were allocated on loopback; preview stop and digest-bound
PDF preview cleanup passed. Full stdio sessions used the installed launcher.

| Scaffold / host build | Active MCP / PDF | Profile coverage | Result |
| --- | --- | --- | --- |
| 0.5.0 / MCP build | 0.5.0 / 0.5.0 | All four profiles | Empty detection, creation, site check, build, preview, HTTP and HTML audit pass; manual PDF/cover pass. Ports 32770–32773. |
| 0.4.0 / 0.4.0 host build | 0.4.0 / historical pinned PDF | `unaltremanual` | Host build/PDF, MCP build, preview, HTTP and HTML audit pass. Port 32776. New image-background and update-advisory tools are absent as expected. |
| 0.4.0 / no earlier host build cache | 0.5.0 / 0.5.0 | `unaltremanual` | Pass with fresh synthetic runtime cache, port 32774. Update advisory reports `update_available`; no sync is applied. |
| 0.4.0 / successful 0.4.0 host build first | 0.5.0 / 0.5.0 | `unaltremanual` | Site check and PDF pass; MCP build fails because retained `tmp/Gemfile.local.lock` selects `google-protobuf (4.36.1)`, unavailable in the 0.5.0 image. No automatic cache deletion or pin migration. |

Evidence directories are `released-050-full`, `released-040-manual-full`,
`mixed-fresh-040-050`, and `mixed-retained-lock-final`. Runs retain `evidence.json`,
server stderr and actual outputs, including the reproduced mixed-cache failure's
MCP response, host-build log and generated lock. The initial
four-profile run hit the terminal's 120-second limit after one profile; its owned
test session was cleaned by exact consumer identity and the complete run passed
with a 600-second outer limit. An initial historical runner call to the newer
`image_background_check` was corrected to inspect actual capabilities; it was a
test-driver mismatch, not a claimed 0.4.0 feature.

Retained PDF hashes:

- 0.5.0 and fresh 0.4.0-scaffold/0.5.0 runtime:
  `4e6e405ed690caf075ec33ea04090d2a5c4bfbf0fb0a49a35cdab819c6f40939`.
- Historical host/runtime 0.4.0:
  `68f067addf5e009364edb42042de2410af5ce8c38543556852d4498bd9663a75`.

Both covers were visually inspected. The 0.5.0 PDF has nine pages including the
synthetic Coordinates chapter, contents and expected draft marker. This is
technical acceptance, not human publication approval.

## Owner gates and exact reproduction

Passed:

```bash
PYTHONPATH=src python3 -m unittest discover -s test -p 'test_*.py'
make distribution-check
make workflow-check
make wheel-check
make mcp-check mcp-smoke \
  MCP_RUNTIME_IMAGE=unaltraweb-owner-76-runtime:20260929 \
  MCP_IMAGE=unaltraweb-owner-76-mcp:20260929-final \
  MANUAL_PDF_DEV_IMAGE=unaltraweb-owner-76-pdf:20260929 \
  MCP_SMOKE_MANUAL_PDF_IMAGE=unaltraweb-owner-76-pdf:20260929 \
  MCP_SMOKE_PROJECT=/tmp/opencode/unaltraweb-owner-20260929/owner-preview-final
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  --entrypoint make unaltraweb-owner-76-mcp:20260929 -C /opt/unaltraweb gem-check
make --silent --no-print-directory \
  -C /tmp/opencode/unaltraweb-owner-20260929/venv/share/unaltraweb-launcher \
  mcp-check mcp-smoke
PYTHONPATH=src python3 -m unaltraweb_mcp.cli --project docs mcp prose-check \
  --target _documentation/en/40-distribution.md
make docs-build DOCKER_IMAGE=unaltraweb-owner-76-runtime:20260929
git diff --check
```

Unit suite: **553 tests, 30 optional skips**. `wheel-check` verifies all four
factory-free native scaffolds and every byte of the launcher/helper closure.
The installed-profile smoke uses the published image, no socket/source mount and
`--network none`. Owner source smoke additionally runs a real stale PDF worker and
a socket-free persistent preview. Docker's content-addressed build cache reused
existing layers; test image tags and consumer/Python/Jekyll caches were separate.
The owner smoke now creates a fresh unique fixture by default and refuses any
existing explicit `MCP_SMOKE_PROJECT`, preventing its fixture reset from touching
prior work. Prose check reports only one pre-existing informational long-sentence
finding in the publication-workflow paragraph; docs build and diff check pass.
Existing `:dev`, manual build and TIGIT local worker image IDs were rechecked and
preserved. Test image configuration IDs:

- `unaltraweb-owner-76-runtime:20260929`: `sha256:df6a55511b5e40c3fde8a10326263cc7a87723b8c090e8333d64bf848c3a853f`.
- `unaltraweb-owner-76-mcp:20260929`: `sha256:dd795ad90dc30547ae09c9175e06f296af1072f4277a2b02d8122000c7378e07`.
- Final source gate `unaltraweb-owner-76-mcp:20260929-final`: `sha256:1ef3d4e7ac5fbb60b66103415c87c30bb432802016ccc30b46b896de3bf35a1b`.
- `unaltraweb-owner-76-pdf:20260929`: `sha256:6c7c5411b4f570fcdcfb1f984a9d9a0e36cc54d606bf459ca67929af0bc0d145`.

The host `make gem-check` initially refused the absent semver-tagged base image;
the exact gate then passed inside the isolated owner image using its local Ruby.
`make distribution-release-check` correctly **fails** at this post-release source
checkpoint: it is not the receipt-only child of the recorded candidate source.
The published receipt is preserved rather than rewritten to make a source
preparation look publication-ready.

Acceptance driver (fresh output directories are required):

```bash
L=/tmp/opencode/unaltraweb-owner-20260929/venv/bin/unaltraweb-mcp-docker
MCP05=ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98
MCP04=ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:389bc585cdb4fc89d3372f4896a55fe26e15df38b46bc114ce44fdb3f1c8deb9
python3 test/distributed_launcher_smoke.py --launcher "$L" --image "$MCP05" \
  --output /tmp/opencode/unaltraweb-owner-20260929/released-050-full
python3 test/distributed_launcher_smoke.py --launcher "$L" --image "$MCP04" \
  --profiles unaltremanual --host-build \
  --output /tmp/opencode/unaltraweb-owner-20260929/released-040-manual-full
python3 test/distributed_launcher_smoke.py --launcher "$L" --image "$MCP05" \
  --scaffold-image "$MCP04" --profiles unaltremanual \
  --output /tmp/opencode/unaltraweb-owner-20260929/mixed-fresh-040-050
python3 test/distributed_launcher_smoke.py --launcher "$L" --image "$MCP05" \
  --scaffold-image "$MCP04" --profiles unaltremanual --host-build \
  --output /tmp/opencode/unaltraweb-owner-20260929/mixed-retained-lock-final
```

The final command intentionally reproduces the retained-lock failure in a new
output directory. The original `mixed-040-050` run used the driver's then-default
host-build step before that option was made explicit.

## Range adoption points, gaps and next action for the hub

1. **Install/discovery:** map the installed `path` and existing descriptor into the
   accepted hub contract. Do not treat a source checkout's `make mcp-check` (which
   builds) as equivalent to the installed profile's prepared-image check.
2. **Compatibility versus exact selection:** `mcp_dependencies` and
   `distribution.py:companion_dependency_requirements` currently select exact
   provider versions/wheels; `site_tools.py` receipt validation also requires exact
   provider version/release. A future accepted range must be tested there without
   weakening request/input/artifact hashes or equating wheel hashes with images.
3. **Consumer tuple:** `consumer_integration`, scaffold rendering/update planning,
   the Make image selection and native Gemfile pins remain atomic reviewed
   selections. Preserve their concrete revision and hashes after any future range
   resolution. Fix/test runtime-specific generated Bundler-cache handling before
   promising transparent switching across the mixed 0.4.0/0.5.0 tuple.
4. **Coverage:** tested endpoints are 0.4.0 and 0.5.0, not a promised `[0.4,0.6)`
   interval. The other three 0.4.0 profiles, non-Linux/amd64 platforms, independent
   new compute/capture/companion rendering and stable publication channels were
   not covered by this preparation.
5. **Delivery:** review the owner diff, assign a new package version through the
   normal release procedure, bind final artifacts to new receipt evidence, then
   adopt the installed profile in a separate synthetic hub pilot. The full 0.5.0
   image can remain selected. Client activation and each real-manual upgrade need
   their own later owner session.

TIG/TIGIT retain 0.4.0 build defaults; Geodisseny retains 0.5.0. Their sources,
generated artifacts, registrations and worker identities were not migrated.
During this session the author separately approved storage cleanup: five stopped
old test containers were removed, and exact unused/unshared unaltraweb cache IDs
were submitted to BuildKit pruning (131.1 kB actually reclaimed). Active stdio
containers, manual previews, images and volumes were not removed by that cleanup.
Other concurrent Docker activity changed disk availability; its reclaimed space
is not attributed to this preparation.
