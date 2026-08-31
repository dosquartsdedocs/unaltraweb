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

`src/unaltraweb_mcp/component-contract.json` is the canonical versioned bill of materials. `component-contract.schema.json` defines schema version 1. Runtime loading and `scripts/validate_distribution.py` validate the complete document against that schema, then enforce semantic parity between versions, release tags, repositories, references, wheel contents, and CLI availability.

The BOM is an interoperability contract, not a bundle. The wheel contains only its Python control/inspection modules, schema/BOM, and clean package-owned scaffolds. In particular it does not contain Ruby theme assets, Docker image layers, factory Make/scripts/docs, TeX, Chromium, computation environments, `diavisuals`, or `vegavisuals`.

For the selected release, the core-owned container references use `0.3.0`; the BOM selects the published `diavisuals v0.3.1` and `vegavisuals v0.3.1` releases. Current checkouts can be used through `suggested_path`, while immutable release references remain the distribution contract. `distribution-check` validates structural integrity for normal CI. `distribution-release-check` blocks coordinated publication while any component is `pending` or `unavailable`; reviewed source authorized to produce the final same-commit candidates is `ready`, while an already-published component is `released`.

## Wheel And Doctor

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

Users can push a site created by `new_web`, edit content in the GitHub web UI, and run its configured deploy workflow when the site should be published. Forking `dosquartsdedocs/unaltraweb-template` remains an optional path for users who want its full demo and workflow wrapper.

This path is intended for small content edits, bibliography updates, course/manual chapter edits and configuration changes. It does not require Docker, Make or a local development environment.

### Local editing

Users who need larger edits can clone their generated site repository and use its package-scaffolded Docker workflow:

```bash
make serve
make build
make test
make down
```

Local editing requires Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run the same commands inside the WSL Linux shell.

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

- normal improvements should ship through the `unaltraweb` gem or reusable workflows;
- site repositories can enable Dependabot for Bundler and GitHub Actions, but deploy workflows should remain manual;
- breaking changes should be released with migration notes;
- scaffold changes should be rare; generated sites can explicitly dry-run `scaffold_sync`, which updates only unchanged baseline runtime files, creates newly managed missing files, reports conflicts, never deletes paths, stages every output, rechecks adopted and unchanged files around the manifest write, rolls the whole transaction back on failure, and commits its manifest last.

## Docker Runtime

The pending `0.3.0` contract names the intended semver runtime target. Before release, a maintainer may manually run the Docker workflow from the final reviewed default-branch commit to publish `main`, `latest`, and a `sha-<full-commit>` candidate. Local maintainer images use explicit names such as `unaltraweb:dev`.

The same rule applies to workers. The final reviewed source commit marks components `ready` before candidate publication. Default-branch workflows publish candidates from that exact SHA. Their immutable image digests and package checksums are recorded in a `release-candidates.json` child commit that may change no other path. Validation requires the parent to belong to the default branch, requires each image digest to use the component's declared GHCR repository, and checks exact package names. Before promotion, each workflow also proves that the source commit's candidate tag still resolves to the recorded digest. Tag workflows then use `docker buildx imagetools create` to add semver aliases without rebuilding or trusting a moved tag. Excluding the receipt from image and package contents avoids an impossible self-digest for the MCP.

The image is not the source of layouts or styles. Child sites still get those from the `unaltraweb` gem declared in their `Gemfile`. This keeps updates centralized in two places:

- gem updates change reusable site behaviour, layouts, Sass, plugins and scripts;
- Docker image updates change the local build/runtime environment.

Before recommending the local Docker workflow to unauthenticated users, complete this first-publish checklist:

- Mark the components `ready` in the final reviewed source commit.
- Run the image and package-preparation workflows from that exact default-branch commit to publish `sha-<full-commit>` images and prepare the gem/wheel candidates without creating a release tag.
- Add only `release-candidates.json` in the next commit, recording the parent source SHA, immutable image references, package basenames and SHA-256 checksums.
- Run `make distribution-release-check`, create the exact release tag on the receipt commit, then run the image workflows from the tag to promote the recorded manifests to semver aliases.
- Open the `ghcr.io/dosquartsdedocs/unaltraweb` package settings in GitHub.
- Make the package public.
- Confirm that `docker pull ghcr.io/dosquartsdedocs/unaltraweb:0.3.0` works without `docker login`.
- Make the `ghcr.io/dosquartsdedocs/unaltraweb-mcp` package public after its first publication.
- Confirm that `docker pull ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` works without `docker login`.

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

This checklist describes future publication verification; changing the contract does not publish, tag, or release any artifact.

## CI And Release Gates

Automatic `.github/workflows/ci.yml` uses `distribution-check`. It validates schema/version/reference parity and release-status declarations, but permits a selected component to remain explicitly `pending` or `unavailable`. It also runs Python compile/unit/diff checks, wheel/gem checks, workflow policy, MCP smoke and the docs build. CodeQL is an independent automatic security check for JavaScript/TypeScript, Python and Ruby.

`distribution-release-check` is the strict coordinated-release gate. The final reviewed source commit marks authorized candidate components `ready`; already-published components may be `released`, and released containers except MCP must use digest references. Core artifact workflows prepare or publish candidates only after tests and a no-push preflight. The receipt-only child commit binds every `ready` component to an immutable image digest or package checksum and binds those candidates to its parent source SHA. An exact semver release tag is rejected unless that complete evidence is valid. Tag jobs promote the receipt's manifests rather than rebuilding, preserving their SBOM and provenance attestations. The MCP candidate consumes the exact runtime digest emitted by the candidate runtime build.

The manual `.github/workflows/package-prepare.yml` builds and checks the gem and wheel, writes `SHA256SUMS`, and uploads an immutable workflow artifact whose name includes the source commit SHA. It does not call RubyGems, PyPI or GitHub Releases. Passing CI, preparing candidates, and later passing the strict coordinated-release gate are evidence for a release, not authorization to publish: tagging, starting a credentialed image workflow, uploading language packages and creating a GitHub release remain separate explicit maintainer approvals.

## Verification

Core changes should be validated in two layers:

- Run `make workflow-check`, `make distribution-check`, `make wheel-check`, and `make gem-check` for workflow publication policy, version/schema parity, selected release metadata, CLI/wheel boundaries, clean wheel installation, and built-gem content. Run `make distribution-release-check` after all final-commit candidates are verified and before creating the coordinated tag. `gem-check` uses local RubyGems or an already-local selected runtime image and never pulls implicitly.
- Build the core repository to catch internal Jekyll errors.
- Build or test `../unaltraweb-template` with `LOCAL_CORE=../unaltraweb` to catch consumer-path regressions.

Template Playwright tests and screenshot generation are intentionally heavier than a Jekyll build. Run targeted profiles when machine resources are limited.
