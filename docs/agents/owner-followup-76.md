# Owner follow-up 76: populated Bundler transitions and 0.5.1 preparation

This follows the immutable historical intake in
[owner-preparation-2026-09-29.md](owner-preparation-2026-09-29.md) and the hub's
`owner-followups/05-unaltraweb.txt`. Tracking and final execution results:
[issue 76](https://github.com/dosquartsdedocs/unaltraweb/issues/76).

## Correction and source identity

Implementation commit: `c23e12b0e1567d18a7f9dd225dc062ddc77dad8b`, on the existing
`feat/76-distributed-mcp-launcher` primary checkout. Local commits were explicitly
authorized. The following integration commit pins `consumer_integration.core_sha`
to this real 0.5.1 core, so the generated Gemfile/lock/workflow tuple no longer
combines a 0.5.1 gem version with a 0.5.0 source revision.

The correction lives in `src/unaltraweb_mcp/bundler_runtime.py` and is included in
both wheel and gem. It keys generated state by the actual Ruby/platform, Bundler,
installed gem inventory, core dependency inputs and hashed Bundler configuration.
No mutable Docker alias or project build default acts as the cache identity.

- Offline `bundle lock --local` and `bundle check` prepare a new identity cache
  under `tmp/unaltraweb-bundle/<hash>/` and record exact Gemfile/lock hashes.
- Reuse verifies that receipt. Edited, unsafe or incomplete caches are retained
  and rejected rather than silently reset. No old generated tree is removed.
- Each build/preview gets private invocation copies. This also accommodates
  Bundler 4's local default-gem checksum completion without disabling checksums
  or changing a cached or authored lock. An initially attempted frozen generated
  lock exposed empty `rake` CHECKSUMS entries in the owner runtime; private copies
  fixed that additional regression. Explicit author Gemfiles require an existing
  lock and run with `BUNDLE_FROZEN=true`.
- Updated package scaffolds use the helper in native build/test/serve targets.
- MCP build and same-image preview adapt unchanged historical Makefiles only
  when their bytes match the recorded package scaffold baseline. They pass
  `LOCAL_GEMFILE` pointing to an invocation copy. The original
  `tmp/Gemfile.local.lock`, project Gemfile/lock, Makefile and scaffold manifest
  remain byte-identical. Custom Makefiles retain their own dependency policy;
  adopting the new native targets remains an explicit scaffold update.

The already-published 0.5.0 image is still unpatched. The roundtrip fixture retains
its exact Ruby/gem layers and adds the new owner controls as a separately named
test image; this proves the correction against the problematic 0.5.0 inventory,
not a new empty cache or an unrelated fresh Ruby installation.

## Component decision

| Component | 0.5.1 preparation |
| --- | --- |
| Core gem | New 0.5.1: ships the runtime helper and updated controls/docs. |
| Python wheel | New 0.5.1: installed Docker launcher, cache orchestration, scaffolds and integration tuple. |
| Full MCP image | New 0.5.1: required to run the correction without a local core. |
| Base Ruby/Jekyll image | Coordinated 0.5.1 candidate under the existing image workflow. The Dockerfile/toolchain recipe itself is unchanged. |
| Manual PDF | Reuse published 0.5.0 digest `sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097`. |
| Python/R computation, web capture | Retain their published 0.4.0 versions/digests. |
| Diavisuals/Vegavisuals | Retain published hashed 0.4.0 wheels and current receipt contract. |

The native validator now permits a released, digest-pinned PDF to retain its
actual version across a coordinated core patch. Pending/ready PDF candidates,
mutable aliases and other repositories do not receive that exception. The
existing source image workflow may build a PDF verification candidate; it does
not thereby replace the selected released worker or put it in the new receipt.
The new receipt must contain exactly `gem`, `wheel`, `runtime`, `mcp` when those
four components remain `ready`.

The 0.5.0 receipt is unchanged, SHA-256
`e57a9dbb041c1e7fcd781cd1524f4de0317382e0f7303bb36bfa59c0b6d1cb9b`.
Historical tags and published packages are untouched. The launcher retains the
last published MCP digest until a separately reviewed post-release selection.
Local 0.5.1 artifacts have new names and are not registry-published candidates.

## Regressions and pre-integration owner gates

Executed on Linux/amd64:

- All four historical profiles: successful 0.4.0 host build first, containing
  `google-protobuf (4.36.1-x86_64-linux-gnu)` in the retained generated lock.
- Unpatched 0.5.0 fails with the known missing `google-protobuf (4.36.1)` on a
  disposable copy of each populated consumer; this negative control is required.
- Corrected controls on 0.5.0 Ruby layers: two builds, preview and HTTP pass.
- Return to unchanged published 0.4.0: two builds, preview and HTTP pass.
- Hash comparisons verify preservation of both authored and retained generated
  Gemfile/lock pairs, Makefile and scaffold baseline across the roundtrip.
- The manual additionally builds/stages real PDFs and performs receipt-bound
  preview cleanup. No source mount or real manual is used.
- Unit regressions cover populated A→B→A cache reuse, modified generated locks,
  symlink ancestors, author Makefile overrides, frozen author locks, credential
  hashing, and private checksum-completion copies.

Initial evidence is retained under
`/tmp/opencode/unaltraweb-followup-76/all-profiles-first/` (three completed
profiles) and `manual-first-roundtrip/` (completed manual). The first combined
run reached its 20-minute terminal limit during the final historical preview;
the manual was rerun to completion. No test container remained from that timeout.

Before integration: **562 unit tests, 30 optional skips**; distribution, workflow,
wheel, gem, MCP CLI, MCP stdio/manual-preview, prose and docs-build gates passed.
The final native smoke passed using `unaltraweb-followup-76-mcp:precommit3`; the
earlier frozen-generated-lock attempts remain failed intermediate evidence.
The old report's 0.5.0-labelled local wheel is not a release artifact.

## Final-version artifact gate protocol

After pinning the corrected core, build the final 0.5.1 wheel and gem from that
clean integration commit, retain their hashes, install the wheel non-editably,
and repeat the gates against those bytes. Retain final outcomes and immutable
local image IDs in issue 76 rather than inserting a self-referential artifact
digest into its own source. Evidence belongs under
`/tmp/opencode/unaltraweb-followup-76/final-artifacts/` and
`/tmp/opencode/unaltraweb-followup-76/final-roundtrip/`.

The reproducible populated-cache command is:

```bash
python3 test/bundler_transition_smoke.py \
  --launcher /tmp/opencode/unaltraweb-followup-76/final-venv/bin/unaltraweb-mcp-docker \
  --legacy-image ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:389bc585cdb4fc89d3372f4896a55fe26e15df38b46bc114ce44fdb3f1c8deb9 \
  --broken-image ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98 \
  --fixed-image unaltraweb-followup-76:051-on-050-final \
  --output /tmp/opencode/unaltraweb-followup-76/final-roundtrip
```

Use a fresh output directory and a sufficiently long outer deadline; the driver
never clears a populated fixture to obtain a pass. The test overlay is built
with `test/bundler_transition.Dockerfile`, the exact published 0.5.0 base digest,
and a named `wheel` build context containing the final wheel. Installation uses
`--no-index --no-deps`, and the build uses `--network none`. Ordinary owner
`mcp-check`/`mcp-smoke` also run against separate test tags and fresh fixtures.

## Publication status and next gate

Issue 76 stays open until integration and release. No PR, push, tag, workflow
dispatch, registry upload or consumer activation is authorized by the local
commit approval. The native schema remains unchanged; H1 range/catalogue fields
are not invented here. Tested points are the explicit tuples above, not a
continuous semver compatibility interval.

The strict `distribution-release-check` is mandatory and must remain blocking
until there is a new 0.5.1 receipt-only child commit with the correct default-branch
candidate ancestry, signed image digests and verified package checksums. The
retained 0.5.0 receipt cannot satisfy that gate and is not rewritten to do so.
Next: reviewed branch integration (preserving or deliberately refreshing the
core pin), approved signed candidate/package preparation on the resulting source,
new receipt-only commit, strict gate, then separately approved promotion and
post-release launcher selection. TIG, TIGIT, Geodisseny, their active registrations
and their image/worker selections are outside this test and adoption scope.
