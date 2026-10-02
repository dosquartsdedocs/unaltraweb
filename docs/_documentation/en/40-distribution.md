---
title: Understand The Distribution Model
description: Core/template split and update model for unaltraweb.
lang: en
ref: distribution_model
profiles:
- unaltredocs
documentation_profiles:
- core-developers
section: Core Development
weight: 620
permalink: "/distribution/"
nav_title: Distribution Model
---
`unaltraweb` is the source of truth for reusable code. Template repositories should stay thin and contain only site-specific content, local overrides and small integration files.

## Repository Roles

- `unaltraweb`: layouts, includes, Sass, assets, Jekyll plugins, Python and shell tooling, reusable GitHub Actions workflows, documentation, small internal examples and the shared Docker runtime image.
- `unaltraweb_mcp` package scaffolds: clean profile-specific config, localized home pages, content roots, and native build/serve files used by new sites.
- `unaltraweb-template`: multi-profile demo assets, local Docker workflow, Dependabot config, workflow wrapper and Playwright integration tests.
- `docs/` in `unaltraweb`: public reference site for the platform itself.

The template is the better place to validate gem consumption, centralized styles and shared logic because it runs as a child site. It is not required to create a site: package scaffolds are the supported clean starting point.

## Component Contract

### Pending 0.6.0 retained-letter increment

The source branch prepares a separate 0.6.0 identity for native
[retained-letter import]({{ '/retained-documents/' | relative_url }}).
Gem, wheel, base runtime and MCP are authorized as `ready` for final same-source
candidates. The consumer core selects reviewed integration
`5cf9817489c8dc47cee726bfe42fe3071cd32b85`; the PDF 0.6.0 worker is already
published, signed and tested at immutable digest
`sha256:0ba267cb87f53ebaca4e31805fe00610cd61fdf97a8d2c3692f4655700dceaed`.
The PDF worker changes to include complete retained documents and the same
integrity checkers used by its controller. Computation, capture and visual
companions retain their tested 0.4.0 selections.

The checkout's active launcher remains pinned to the published 0.5.1 MCP digest.
Its receipt and package bytes remain unchanged. Local development images and an
installed wheel exercise the new import without claiming a public 0.6.0 release
or changing real consumer sites. The
[owner acceptance record](https://github.com/dosquartsdedocs/unaltraweb/blob/main/docs/agents/retained-letter-import.md)
records the authenticated Carta packet, receiver mapping and relocation proof.

### Published 0.5.1 release

[**0.5.1**](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.5.1)
delivers the installed Docker launcher and runtime-specific generated Bundler
state. Source `aab5a7b030cd711b40770a3f44ad3a356eab90da` produced the signed
images and verified gem/wheel. Receipt/tag commit
`e842c733c8a274279dd5efdc3618e20669f29037` changes only the receipt from that
first parent. Strict release/publication gates passed before promotion, and
anonymous registry downloads match the receipt. The checkout launcher now selects
`ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:908b4ce54c7bdf355e14ed55b31ed4b9baae319e211af90004a680d1d1cb8692`.

The four-profile populated-cache roundtrip also passed against the actual signed
candidate. The selected PDF stays at its published 0.5.0 digest, and computation,
capture and visual companions retain 0.4.0. See the
[delivery report](https://github.com/dosquartsdedocs/unaltraweb/blob/main/docs/agents/owner-closeout-76.md)
and [issue 76](https://github.com/dosquartsdedocs/unaltraweb/issues/76).
Strict release validation applies to the receipt/tag revision; subsequent
post-release launcher changes are ordinary source revisions, not new receipts.

### Previous 0.5.0 release

The previous coordinated core release is [**0.5.0**](https://github.com/dosquartsdedocs/unaltraweb/releases/tag/v0.5.0). It groups the integrated editorial
review, guided scaffold updates, caption-credit/image behavior and published
Diavisuals/Vegavisuals 0.4.0 acceptance. Source-bound image/package workflows,
tag promotion and both Trusted Publishing jobs passed. Anonymous package downloads
match the receipt and clean native installations were checked.
Unchanged already-published computation and web-capture workers retain their own
0.4.0 versions and digests. New/pending worker candidates must still match the
coordinated release; an old mutable alias cannot qualify for reuse. The selected
consumer tuple must use a reviewed 0.5.0 core revision and tested PDF worker.
The PDF worker passed the
[signed candidate workflow](https://github.com/dosquartsdedocs/unaltraweb/actions/runs/36272762057)
at source `d857f8c9f5fea90cf450c0b30b4e77a37b541275` and is selected by digest
`sha256:9e0b3a45753c170b795e9a9d6df61580085c113436beac5bf6c8de69b6562097` in
both the factory and the consumer tuple. It is already published and tested, so
final candidate receipts cover the remaining ready package/core components.
The 0.5.0 post-release factory launcher selected the MCP digest recorded in receipt
`3fa855378dcc61dc7b84b8b03812698042e02fed`:
`sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98`.
See [issue 69](https://github.com/dosquartsdedocs/unaltraweb/issues/69) for the
candidate, receipt, tag and package evidence.

`src/unaltraweb_mcp/component-contract.json` is the canonical versioned bill of materials. Its `consumer_integration` object is the sole source for the reviewed core Git revision, reusable deploy workflow, manual PDF image digest, and Vega renderer revision. Scaffold templates render that tuple atomically into consumer `Gemfile`, `Gemfile.lock`, and deploy workflow files. `component-contract.schema.json` defines schema version 1. Runtime loading and `scripts/validate_distribution.py` validate the complete document against that schema, then enforce semantic parity between versions, release tags, repositories, references, wheel contents, CLI availability, and consumer integration pins.

The BOM is an interoperability contract, not a bundle. The wheel contains its Python control/inspection modules, schema/BOM, clean package-owned scaffolds and a small host Docker launcher, described below. It does not include Ruby theme assets, Docker image layers, the factory's build/worker implementations, TeX, Chromium, computation environments, `diavisuals`, or `vegavisuals`.

The selected public core release is `0.5.1`; earlier distributions remain immutable. Its BOM reuses immutable PDF, compute and web-capture worker digests and selects published `diavisuals v0.4.0` and `vegavisuals v0.4.0` through SHA-256-pinned wheel URLs. Companion references can describe either a provider/release-matching Git reference or a provider/release/version-matching wheel with its content hash. The wheel boundary remains external. The scaffold's Vega revision is the published `68c0b231402ae9485cc34ce530dc5239cb0ec194` commit. `distribution-check` validates structural integrity for normal CI. `distribution-release-check` blocks coordinated publication while any component is `pending` or `unavailable`; reviewed source authorized to produce final same-commit candidates is `ready`, while an already-published component is `released`. Final receipt values remain immutable after publication.

## Docker-First Hybrid Policy

### 0.5.1 component selection

The coordinated core identity is **0.5.1**: gem, wheel, base runtime and MCP
images were published together. The installed host launcher and runtime-aware
generated Bundler state are included. The unchanged PDF worker retains its
published 0.5.0 digest, alongside the 0.4.0 computation/capture workers and visual
companions. A released PDF can be reused only by full digest; new/pending workers
still require the coordinated version. The historical 0.5.0 receipt remains
unchanged. Signed image/package evidence is recorded in the 0.5.1 receipt;
promotion and anonymous-download checks passed before the post-release launcher
pin was advanced.

### Local delivery

GHCR is the canonical delivery channel for normal local use. The released package scaffold selects `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.5.1`; existing sites can remain on their immutable previous release until deliberately updated. Its `make build`, `make serve` and `make test` targets mount the thin child site and run inside that image. The image contains both the installed Python control plane and the reviewed factory source at `/opt/unaltraweb`, so those targets load the theme as a path gem without downloading PyPI or RubyGems packages.

Factory registration uses a stricter pin. gContExt runs `mcp-build`, which inspects or pulls the full `MCP_RELEASE_IMAGE` digest, and `mcp-stdio` launches that exact image. Checkout builds use local `:dev` names by default through `mcp-image`, `mcp-check` and `mcp-smoke`, so they do not shadow public semver references unless a maintainer explicitly overrides them. The digest is advanced in a separate post-release change after each new receipt exists; candidate source continues to select the last completed release instead of attempting to embed an unknown self-digest.

The distribution keeps native channels for interoperability rather than making them Docker prerequisites:

- `ghcr.io/dosquartsdedocs/unaltraweb` is the lower-level Ruby/Jekyll runtime used to build the MCP image.
- `ghcr.io/dosquartsdedocs/unaltraweb-mcp` is the self-contained normal site and MCP runtime.
- RubyGems publishes the same Jekyll core as a native Bundler adapter for consumers that do not use the Docker path.
- PyPI publishes the small scaffold, control and inspection plane for native Python, `pip` or `uv` use.
- Dedicated GHCR workers keep Chromium, TeX and computation environments out of the normal site image.

These remain real package boundaries: the MCP image installs the Python package and uses the core through Ruby's gem interface. The policy only makes their public registry installation optional for Docker users. It does not combine all toolchains into one image or duplicate worker layers in the wheel or gem.

### Installed Docker launcher

0.5.1 ships **`unaltraweb-mcp-docker`** and a complete host launcher
under the installation prefix's `share/unaltraweb-launcher/`. The published 0.5.0
wheel predates this addition; its receipt and bytes remain unchanged. An installed
wheel containing the launcher can use the already-published full GHCR runtime
without a local core checkout:

```bash
unaltraweb-mcp-docker prepare
unaltraweb-mcp-docker check
unaltraweb-mcp-docker smoke
unaltraweb-mcp-docker serve --project /absolute/consumer
```

The installed default selects its package's full MCP release image, currently
`ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.5.1`. It resolves that selection to the
local immutable image ID before executing. The checkout's `MCP_RELEASE_IMAGE`
is a separate digest pin advanced only after publication; it is not the installed
wheel's default. This avoids sending a new package back to an older MCP while
also avoiding an impossible self-digest in the candidate image/wheel.
`--image` selects a different explicitly prepared image for a test or a reviewed
adoption. `prepare` only inspects/pulls; `check` and `smoke` use the local image ID,
without pulling, building, mounting a consumer or starting a preview. `serve`
requires an explicit consumer or inherited `MCP_CONSUMER_WORKSPACE`; it starts one
labelled stdio container and preserves the canonical host-path mirror for workers.
`down --project /absolute/consumer` uses the same project-scoped cleanup helper.

`unaltraweb-mcp-docker path` locates the installed profile from wheel metadata;
`manifest` prints its discovery descriptor. The profile ships the same native
schema-v1 `mcp-factory.yml`, a small launcher-only Makefile, and the bootstrap,
project-ID, Docker CSV mount and cleanup scripts. Its `${factoryRoot}` is this
installed directory, and the declared `make -C` transport and lifecycle targets
remain usable. That directory can also be relocated as a unit and run with Make,
a POSIX shell, Linux core utilities and Docker, without host Python or Ruby.
The console adapter itself requires the wheel's Python interpreter. Linux/amd64
is the acceptance platform; other host/platform combinations remain unverified.

This adapter launches the **full container runtime**. The native `unaltraweb-mcp`
CLI keeps the exact wheel-only/factory-required boundary declared in the BOM.
Installing the adapter does not install Jekyll, workers or companion servers on
the host, register a client, update a consumer scaffold, or change an active MCP.

### Separate selections and compatibility evidence

The site Makefile's `MCP_IMAGE`, native Gem/core revision, PDF worker, global MCP
registration and companion selections are separate parts of an effective tuple.
TIG/TIGIT retain build defaults 0.4.0; Geodisseny retains 0.5.0. A global MCP
selection does not rewrite those defaults. Tests use synthetic sites,
image-specific test resources and dynamically allocated loopback preview ports.

Compatibility evidence is a set of tested tuples, not a continuous version range.
The [initial owner preparation report](https://github.com/dosquartsdedocs/unaltraweb/blob/main/docs/agents/owner-preparation-2026-09-29.md)
records all four 0.5.0 profiles, manual PDF coverage, the 0.4.0 comparison and
the reproduced retained-cache failure. The 0.5.1 correction is recorded in the
[follow-up report](https://github.com/dosquartsdedocs/unaltraweb/blob/main/docs/agents/owner-followup-76.md).
Range adoption belongs at
the native dependency/version checks, companion receipt checks and atomic
consumer-integration selection. Exact wheel hashes, image digests and published
receipts remain identity evidence even if future compatibility rules accept a
range. Central catalogue/range fields await the accepted hub integration.

### Generated Bundler state

0.5.1 keys generated dependencies by the effective Ruby/platform, Bundler,
installed gem inventory, core inputs and Bundler configuration, rather than a
mutable Docker tag. The offline resolver prepares a verified cache under
`tmp/unaltraweb-bundle/<identity>/`. Returning to an identity reuses its cache;
changing identities does not rewrite another runtime's lock. Credential-bearing
Bundler environment/configuration values contribute only hashes to the receipt.

New native build/preview targets execute with invocation-owned copies of that
generated state. Bundler can complete local default-gem checksum metadata without
rewriting the verified cache or disabling checksum validation. An
explicit `LOCAL_GEMFILE` is author-managed: its existing lock is required and
used frozen. Project `Gemfile`, `Gemfile.lock` and Bundler configuration are
preserved. Edited or incomplete generated caches fail for inspection instead of
being silently repaired. Failed preparation directories remain under `tmp/`.

For unchanged historical package Makefiles, the updated MCP prepares the same
runtime-specific cache and passes invocation-owned Gemfile/lock copies to the
old recipes. The retained `tmp/Gemfile.local.lock` remains untouched, so a later
0.4.0 build can use its original selection. This adapter requires the Makefile to
match its recorded scaffold baseline; authored Makefile customizations retain
their own dependency policy. Those consumers can deliberately adopt the updated
native targets through the normal reviewed scaffold workflow. New native targets
require a containing core/runtime; the already-published 0.4.0 and 0.5.0 images do
not acquire the correction automatically.

## Optional Wheel And Doctor

A clean `unaltraweb-mcp` wheel works without a factory checkout for `version`, `new-web`, top-level `doctor`, constrained source management, scaffold synchronization, `site-doctor`, HTML audit, and pure inspection where feasible. Examples include `mcp list-tools`, `starter-templates`, `detect-site`, `site-context`, `profile-check`, content/language/bibliography inventories, and `build-health`.

```bash
unaltraweb-mcp doctor
unaltraweb-mcp doctor --project /path/to/site
unaltraweb-mcp doctor --project /path/to/site --docker
```

Doctor performs no network requests. It reports limited wheel mode as an informational healthy state, reads `_config.yml`, Gemfile/lock, Make pins, computation settings, capture recipes, PDF enablement, and companion manifests when a project is supplied, and checks only components relevant to those features. `release_ready` is separate from operational `ok`, so any pending or unavailable component release is visible without making package-only inspection unusable. Companion-specific findings retain their stable companion codes; core package and image releases use the generic release codes. `--docker` optionally inspects local Docker and selected image presence; it never pulls or builds. Every finding has stable `code`, `severity`, `expected`, `actual`, and `remediation` fields.

Factory-backed MCP serving, site preflight/build, computations, captures, PDF operations, bibliometrics, and prompt loading still require the checkout or the selected MCP image. A wheel invocation fails those commands explicitly and tells the caller to set `UNALTRAWEB_FACTORY_DIR`; it does not pretend the factory assets were bundled.

## User Paths

### GitHub-only editing

Users can push a site created by `new_web` and edit small content changes in the GitHub web UI. The generated README requires an assigned issue or accepted file reservation, one task branch, one active editing session per repository, and a small Draft pull request. A reservation limits scope rather than permitting overlapping sessions. Editors never change `main` directly; they stop and ask a maintainer when work overlaps or conflicts.

This path is intended for small content edits, bibliography updates, course/manual chapter edits and configuration changes. It does not require Docker, Make or a local development environment. A maintainer checks and renders the branch locally, reviews it, merges it, and only then starts deployment manually.

For `unaltremanual`, `latest` is a manual-only deployment from reviewed `main`; a push does not deploy it. The caller requires the exact locally reviewed commit SHA and an immutable manual PDF worker digest. When PDF output is enabled, its default PDF and cover are generated for deployment rather than versioned. The website marker and PDF both identify the selected channel/version. Stable `vYYYY.MM(.N)` editions use explicit immutable releases, bind the rebuilt assets to the locally reviewed candidate manifest, and reject generated private/runtime trees.

### Local editing

Users who need larger edits can clone their generated site repository and use its package-scaffolded Docker workflow:

```bash
make serve
make build
make test
make down
```

Local editing requires Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run the same commands inside the WSL Linux shell.

The normal targets use the selected MCP image, including its reviewed core at `/opt/unaltraweb`. The committed `Gemfile` and native package entry points remain available for GitHub deployment, integration testing and environments that deliberately choose a non-Docker path; local Docker editing does not need a sibling core checkout or registry package installation.

Theme development can happen side by side by pointing the template at a local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte
```

## Demo Strategy

- Template demo: realistic content for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`, used to validate the gem consumer path.
- Core docs: the `unaltraweb` reference site, focused on concepts, profile capabilities, syntax, customization points, tools and links to the template.
- Avoid duplicating full demo content between the two repositories.

## Core Docs Publishing

The core repository deploy workflow is manual. It builds only `docs/` and publishes it with GitHub Pages Actions. The root core Jekyll build excludes `docs/`, so the reference site can use its own root-relative permalinks without colliding with the internal core demo build.

Reference deployment, link checks, Docker image publishing and publication metrics run manually from GitHub or locally. Repository CI runs for pushes and pull requests, and CodeQL runs for pull requests, default-branch pushes and a weekly schedule. Neither automatic workflow deploys or publishes.

## Updates

Repositories created from a GitHub template are not linked to the template as forks, so template changes are not automatically proposed to users.

For that reason:

- normal local-runtime improvements should ship through a versioned MCP image; native consumers receive corresponding gem or wheel releases when their package boundary changes;
- site repositories can enable Dependabot for Bundler and GitHub Actions, but deploy workflows should remain manual;
- breaking changes should be released with migration notes;
- scaffold changes should be rare; generated sites can explicitly dry-run `scaffold_sync`, which updates unchanged baseline runtime files (including the pull-request template), creates newly managed missing files, and preserves local edits when the upstream file still equals its original baseline. Conflicting local/upstream edits remain blocked. The transaction never deletes paths, stages every output, rechecks adopted, unchanged and preserved files around the manifest write, rolls back on failure, and commits its manifest last. `site_context.update_status` guides the agent's version/update offer; `expected_plan_sha256` binds confirmation to the reviewed proposal. Generated README prose is site-owned and is not overwritten by synchronization.

## Docker Runtime

Release `0.5.1` publishes the selected base/MCP runtime and packages while pinning the verified PDF worker and reusing unchanged specialized workers. Local maintainers continue to use explicit development names such as `unaltraweb:dev`; generated sites select the reviewed semver MCP image rather than `main` or `latest`.

The base runtime owns Ruby, Jekyll and system dependencies. The MCP image builds on its exact candidate digest and adds the full reviewed factory plus the Python package. Specialized workers remain separate. This keeps each layer focused without adding Chromium, TeX or computation stacks to every site; the coordinated core-image workflow still rebuilds and verifies runtime, MCP and manual PDF candidates together.

Candidate publication remains credential-separated. `build-candidates` builds each image once under only its SHA tag and creates GitHub-signed provenance. A read-only job verifies provenance and revision labels, removes GHCR credentials, and executes the test suite against exact digests. A final package-write job executes no candidate and promotes only tested manifests. The signed source-bound digest, rather than a mutable alias, remains the evidence recorded in `release-candidates.json`.

The pre-build absence lookup is not an atomic no-clobber guarantee: GHCR exposes separate read and tag-write operations, not compare-and-swap. A package administrator could race the lookup or later retagging. Immediate equality checks and post-promotion verification bound that risk, while the signed, source-bound digest tested by the read-only job remains the evidence to record. An immediately following `release-candidates.json` child commit records immutable image digests and package checksums while changing no other path. Validation requires the parent to belong to the default branch, requires each image digest to use the component's declared GHCR repository, and checks exact package names. Before semver promotion, the tag-only job proves that each source commit's SHA tag still resolves to the recorded digest, verifies its GitHub-signed attestation with `receipt.source_commit` as the source digest, and requires the image revision label to equal that commit. It then uses `docker buildx imagetools create` to add and verify semver aliases without rebuilding, executing, or trusting a mutable source tag. Excluding the receipt from image and package contents avoids an impossible self-digest for the MCP. Publication workflows require the reviewed manual PDF image by full digest. Separate worker images keep Chromium, TeX, and computation environments out of ordinary site and wheel installs.

For the Docker-first path, reusable layouts, styles, plugins and scripts travel inside the reviewed MCP image at `/opt/unaltraweb`; generated Make targets expose that directory as a path gem. The independently published gem carries the same reusable core for native Bundler consumers. The wheel provides native bootstrap and inspection but does not carry the theme or worker images.

The `v0.3.0` first-publish checklist is complete: all selected GHCR packages are public, anonymous pulls work, Trusted Publishing delivered the exact gem and wheel to RubyGems and PyPI, anonymous installations matched the receipt, and the GitHub Release archives both package files plus `SHA256SUMS`. Do not rebuild, republish or retag that version.

The receipt uses a full source commit and different evidence by component kind. This abbreviated example shows both forms; the real `components` object must contain exactly every component marked `ready`:

```json
{
  "schema_version": 1,
  "release": "v0.3.0",
  "source_commit": "0123456789abcdef0123456789abcdef01234567",
  "components": {
    "runtime": {
      "reference": "ghcr.io/dosquartsdedocs/unaltraweb@sha256:<64 lowercase hex characters>"
    },
    "gem": {
      "artifact": "unaltraweb-0.3.0.gem",
      "sha256": "<64 lowercase hex characters>"
    }
  }
}
```

The receipt example describes future publication verification; changing the contract does not publish, tag, or release any artifact.

## CI And Release Gates

Automatic `.github/workflows/ci.yml` uses `distribution-check`. It validates schema/version/reference parity and release-status declarations, but permits a selected component to remain explicitly `pending` or `unavailable`. It also runs Python compile/unit/diff checks, wheel/gem checks, workflow policy, MCP smoke and the docs build. CodeQL is an independent automatic security check for JavaScript/TypeScript, Python and Ruby.

`distribution-release-check` is the strict coordinated-release gate. The final reviewed source commit marks authorized candidate components `ready`; already-published components may be `released`, and released containers except MCP must use digest references. Core artifact workflows keep source/package preflights unprivileged and without registry access. Runtime, MCP, and manual PDF use separate signing/package-write build, read-only test, and non-executing package-write promotion jobs. Every SHA-only build gets a GitHub-signed provenance attestation; tests verify its exact digest, signer workflow, and source commit before removing registry credentials and running it; broad aliases receive only successful test-job digest outputs. The receipt-only child commit binds every `ready` component to an immutable image digest or package checksum and binds those candidates to its parent source SHA. An exact semver release tag is rejected unless that complete evidence is valid. Tag jobs reverify SHA-tag equality, signed source provenance, and revision labels before promoting the receipt's manifests rather than rebuilding or executing them, preserving their SBOM and provenance attestations. The MCP candidate consumes the exact runtime digest emitted by the candidate runtime build.

The manual `.github/workflows/package-prepare.yml` builds and checks the gem and wheel, writes `SHA256SUMS`, and uploads an immutable workflow artifact whose name includes the source commit SHA. It does not call RubyGems, PyPI or GitHub Releases. Passing CI, preparing candidates, and later passing the strict coordinated-release gate are evidence for a release, not authorization to publish: tagging, starting a credentialed image workflow, uploading language packages and creating a GitHub release remain separate explicit maintainer approvals.

After a coordinated tag exists, `.github/workflows/package-publish.yml` provides the separately approved optional language-package operation without long-lived registry secrets. The repository uses these one-time identities, first configured for `v0.3.0`:

- GitHub environment `pypi`, allowed only from the default branch; PyPI Trusted Publisher project `unaltraweb-mcp`, owner `dosquartsdedocs`, repository `unaltraweb`, workflow `package-publish.yml`, environment `pypi`.
- GitHub environment `rubygems`, allowed only from the default branch; RubyGems Trusted Publisher gem `unaltraweb`, owner `dosquartsdedocs`, repository `unaltraweb`, workflow `package-publish.yml`, environment `rubygems`.
- Add required environment reviewers and prevent self-review when the maintainer topology allows another person to approve. A sole maintainer should still require the exact reviewed `publisher_sha` input and inspect the run before allowing each environment deployment.

Dispatch the workflow only from the default branch. Supply its current reviewed full commit as `publisher_sha`, the exact `vX.Y.Z` receipt tag, the annotated tag object SHA, the SHA-256 of `release-candidates.json`, the successful `Prepare package candidates` run ID, and `all`. The unprivileged job checks that request before checkout and uses only the reviewed publisher verifier: it never installs or executes code from the release tag. That verifier requires the annotated tag object and receipt hash supplied by the maintainer, checks the receipt-only tag target against its first parent and default-branch ancestry, validates the release-ready component inventory, and binds the selected run to `.github/workflows/package-prepare.yml`, the default branch, the receipt source commit, a successful conclusion, and the one expected unexpired artifact. It then rejects extra files, verifies both package hashes and the exact `SHA256SUMS` contents, and uploads one wheel and one gem as separate same-run artefacts. Only the dependent environment jobs receive `id-token: write`; they download those verified files without checking out source and exchange GitHub's OIDC identity for short-lived registry credentials. They receive no repository write permission and never build or execute candidates. The PyPI job runs the reviewed official publisher image by immutable OCI digest rather than its mutable generated image tag; the RubyGems job uses the hosted runner's preinstalled `gem` command instead of downloading a toolchain after receiving OIDC authority.

If one registry succeeds and the other fails, rerun against `pypi` or `rubygems` only with the same tag object SHA, receipt SHA-256, and package run ID; immutable registries reject duplicate versions. After both package pages and anonymous installations match the receipt checksums, create the GitHub Release with the preserved gem, wheel, and `SHA256SUMS`. Package publication never moves the coordinated tag, creates a release, or deploys a consumer site.

## Verification

Core changes should be validated in two layers:

- Run `make workflow-check`, `make distribution-check`, `make wheel-check`, and `make gem-check` for workflow publication policy, version/schema parity, selected release metadata, CLI/wheel boundaries, clean wheel installation, and built-gem content. Run `make distribution-release-check` after all final-commit candidates are verified and before creating the coordinated tag. `gem-check` uses local RubyGems or an already-local selected runtime image and never pulls implicitly.
- Build the core repository to catch internal Jekyll errors.
- Build or test `../unaltraweb-template` with `LOCAL_CORE=../unaltraweb` to catch consumer-path regressions.

Template Playwright tests and screenshot generation are intentionally heavier than a Jekyll build. Run targeted profiles when machine resources are limited.
