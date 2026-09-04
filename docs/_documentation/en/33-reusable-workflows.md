---
title: Use Reusable GitHub Workflows
description: GitHub Actions workflows provided by the unaltraweb core.
lang: en
ref: reusable_workflows
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- contributors
- core-developers
section: Publish With GitHub
weight: 70
permalink: "/reusable-workflows/"
nav_title: GitHub Workflows
---
Child sites should keep workflow files thin and call reusable workflows from the core repository.

These wrappers should normally be manual-only. Use `workflow_dispatch` so a push or Dependabot pull request does not start a deploy unless someone explicitly asks for it.

## Site deploy

{% raw %}
```yaml
jobs:
  validate:
    # Generated callers fail unless reviewed_sha equals the selected main commit.
    # Keep this generated job unchanged.
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@<reviewed-commit-sha>
    with:
      reviewed_sha: "${{ inputs.reviewed_sha }}"
      manual-pdf-image: "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:<reviewed-digest>"
      check-manual-pdf: false
      sync-manual-pdf: true
      vegavisuals-sha: "<reviewed-vegavisuals-commit-sha>"
```
{% endraw %}

Pin the reusable workflow to a reviewed commit because it receives Pages and OIDC permissions. The generated caller accepts only `workflow_dispatch`, requires the full locally reviewed SHA, and fails unless the selected ref is `refs/heads/main` at exactly that SHA. The reusable workflow repeats that source check, requires the PDF worker by immutable GHCR digest, rejects configured PDF/cover outputs already tracked by Git, installs Ruby dependencies, rejects stale computations, web captures and manifest-backed Vega visualizations, builds with the `unaltraweb` gem config and deploys to GitHub Pages. The checks are no-ops when their source configuration is absent. Set `check-computations`, `check-web-captures` or `check-visualizations` to `false` only when another freshness gate intentionally owns that source type.

A site with `.vegavisuals.yml` must pass `vegavisuals-sha` as the full lowercase 40-character SHA of a reviewed commit. The workflow installs that exact revision from the fixed public repository URL before checking freshness; it does not accept a mutable tag, branch, or caller-supplied URL. Deployment only checks committed visualization outputs; run `make visualization-render` locally rather than rendering in CI.

For `unaltremanual`, the `latest` channel is a manual-only deployment from the reviewed `main` branch. PDF output is disabled in a fresh manual scaffold until a maintainer configures it. When enabled, deployment deterministically rebuilds every configured language and places the current PDF and cover into the site artifact before Jekyll publishes it. The default `assets/pdf/manual-<lang>.pdf` and `assets/img/manual-cover-<lang>.png` outputs are generated deployment products and are not committed. Existing tracked copies require a reviewed one-time `git rm --cached`. The resulting website and PDF display `latest`; release checks reject generated `legacy/` or `sandbox/` content.

Clean package scaffolds include a manual GitHub Pages wrapper pinned to a reviewed workflow revision. It has no push deployment trigger: a maintainer runs it only after local checks/renders and human review. The optional integration template retains additional local publishing experiments, but generated sites do not publish from local validation targets.

The current provider change is commit M before M's permanent SHA and matching manual PDF image digest exist. Its bootstrap scaffold therefore remains pinned to immutable, workspace-compatible ancestor `6427c5963d6d32845cd774dd8537fe935b42d381`, passes only that workflow's compatible `check-manual-pdf: false` and `sync-manual-pdf: true` inputs, and relies on the generated caller's own `main`/`reviewed_sha` validation. It must not pass inputs unsupported by that old workflow; `vegavisuals-sha` may be added only when the pinned workflow and generated caller both support the reviewed value.

As soon as M and its digest-pinned manual PDF image D exist, mandatory immediate follow-up B is a pin-only integration change. The M -> D -> B order remains required: D must be built from M's permanent identity, and B cannot pin M and D before both immutable values exist. B updates the reviewed scaffold caller pin to M and wires the existing caller `reviewed_sha` plus D into the reusable call; it changes no publication policy or provider implementation. Do not defer B, use `@main`, or substitute an assumed `v0.3.0` image. Only after B does the defense-in-depth source check run at both caller and provider boundaries.

## Stable manual releases

`.github/workflows/site-release.yml` is a separate `workflow_call`-only boundary for future `vYYYY.MM` and `vYYYY.MM.N` releases. Its preparation job has only `contents: read`: it checks the reviewed `main` SHA, checks out an immutable core revision, requires digest-pinned manual PDF and MCP site-build images, records the Python runtime from the site-build image, derives `SOURCE_DATE_EPOCH` from the reviewed consumer commit, and runs Jekyll offline inside the same MCP image used for local candidate review. When `.vegavisuals.yml` exists, the job runs the freshness check from the exact reviewed vegavisuals checkout rather than merely recording its SHA. It then requires the rebuilt version-2 `release-manifest.json` SHA-256 to equal the locally reviewed candidate digest supplied by the caller, assembles a deterministic web archive, writes checksums, and uploads a same-run Actions artifact. Only the dependent `publish` job receives `contents: write`. That job requires the `stable-release` GitHub environment and consists only of pinned artifact download, immutable verifier checkout, exact Python setup, and the reviewed publisher. The publisher verifies the asset allowlist, source/runtime identity, site tree fingerprint and PDF hashes, creates a lightweight tag at the reviewed source SHA, and addresses one matching draft by numeric release ID. A retry resets that draft's canonical metadata and assets, downloads them, compares every byte with the prepared candidate, confirms that the remote asset inventory and tag have not changed, and publishes the draft last.

Prepare and check the stable candidate locally from the exact clean `main` commit, then obtain the caller input with `sha256sum tmp/manual-release/<selector>/release-manifest.json`. CI is the authoritative offline rebuild; any network-dependent local difference changes the manifest digest and fails before any job has publication authority. Before enabling a stable caller, protect `main` against direct changes, enable immutable releases in repository settings, protect `v*` tags while allowing only the approved release workflow to create them, and configure required reviewers with self-review and bypass disabled for the repository's `stable-release` environment. Restrict that environment to protected `main`. No stable caller is installed by the current scaffold because the reusable workflow must first exist at a reviewed immutable commit. Use two commits:

1. Merge the reusable workflow and every helper it executes; call the resulting permanent commit `A`.
2. In a follow-up change, add the consumer caller and pin both its `uses:` and `core_sha` to `A`. Require `reviewed_sha`, `candidate_manifest_sha256`, and the reviewed PDF and MCP site-build image digests as dispatch inputs. Never use `@main`, and do not squash or rebase `A` away.

This is deliberate: a workflow cannot truthfully pin itself to the commit being created. Preparing a local candidate or passing the read-only job is evidence, not publication authorization. Do not dispatch a stable release until a stable edition is intentionally approved.

A future caller should keep the reviewed core revision static and grant write authority only to the reusable job:

{% raw %}
```yaml
on:
  workflow_dispatch:
    inputs:
      selector:
        required: true
        type: string
      reviewed_sha:
        required: true
        type: string
      candidate_manifest_sha256:
        required: true
        type: string

permissions:
  contents: read

jobs:
  release:
    permissions:
      contents: write
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-release.yml@<commit-A>
    with:
      selector: "${{ inputs.selector }}"
      reviewed_sha: "${{ inputs.reviewed_sha }}"
      candidate_manifest_sha256: "${{ inputs.candidate_manifest_sha256 }}"
      core_sha: "<commit-A>"
      manual_pdf_image: "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:<reviewed-digest>"
      site_build_image: "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:<reviewed-digest>"
```
{% endraw %}

## Publication metrics

```yaml
jobs:
  metrics:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/metrics-update.yml@main
```

Metrics updates are manual and explicit. Normal site deploys remain static.

## Project computation images

Projects that extend a core computation image can publish a separate GHCR package without copying the factory workflow:

```yaml
name: Publish Python computation image

on:
  workflow_dispatch:

permissions:
  contents: read
  packages: write

jobs:
  image:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/project-compute-image.yml@<reviewed-commit-sha>
    with:
      engine: python
      image: example-compute-python
      dockerfile: Dockerfile.compute-python
      context: .
      base_image: ghcr.io/dosquartsdedocs/unaltraweb-compute-python@sha256:<digest>
      test_command: make test-compute-image
```

Pin the reusable workflow to a reviewed commit because it receives the caller's package-write token. The provider checkout is bound to the defining job's `workflow_repository` and `workflow_sha`, not caller-controlled workflow identity. Before a login is possible, default-branch candidate publication checks that provider revision with `distribution-check`, while an exact `vX.Y.Z` tag publication uses `distribution-release-check`. The workflow also requires a digest-pinned `base_image`, validates confined build paths and the selected ref, runs the optional project test command, and completes a no-push image build. Only the dependent publication job can publish `main` and `sha-*` under the consumer repository owner or semver/release-tag metadata from a release tag. Published images include SBOM and provenance attestations. Keep engine-specific dependencies and lockfiles in that project; for example, a TIGIT site should publish `tigit-compute-r`, not a TIGIT variant of the core package.

After publication, make the package public or authenticate Docker, select its full GHCR digest in `.unaltraweb/computations.yml`, run `manual-compute-render`, and commit the updated generated artifacts and computation lock. Publishing an extension does not select or rerender it automatically.
