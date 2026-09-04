# unaltraweb

`unaltraweb` is a reusable Jekyll core for academic, research project, software and documentation websites maintained by `dosquartsdedocs`.

## Content Editors: Start Here

If you have been invited to edit a generated site, start with that repository's `README.md`. It identifies the selected profile, lists the content paths you may edit, and puts the browser-only workflow before local technical setup.

For every GitHub Web edit:

1. Work from an assigned issue or an explicit file reservation accepted by the maintainer. Only one active editor may work on a file.
2. Create one branch per task and never edit `main` directly.
3. Open a small Draft pull request early. If a conflict appears, stop and ask the maintainer instead of overwriting work.
4. The maintainer runs local checks and required renders, reviews the result, merges the pull request, and only then starts deployment manually.

See [Edit Safely In GitHub Web](docs/_documentation/en/06-github-web-editing.md) for the full coordination, image-upload, file-safety, and publication protocol.

## Four Site Profiles

| Profile | Use it for | Main editor-owned paths |
|---|---|---|
| `unaltreselfie` | A personal academic or professional site | `_pages/`, `_posts/`, `_news/`, `_projects/`, `_books/`, `_bibliography/`, approved profile assets |
| `unaltreprojecte` | A research project, group, infrastructure, or output site | `_pages/`, `_news/`, `_projects/`, `_outputs/`, `_books/`, `_data/team.yml`, `_data/repositories.yml`, approved project assets |
| `unaltremanual` | A manual, course, handbook, or book-like publication | `_pages/`, `_chapters/`, `_bibliography/`, `context/writing-profile.md`, approved source images |
| `unaltredocs` | Technical or operational documentation | `_pages/`, `_documentation/`, public `_data/` files, approved screenshots |

## Technical Overview

The core packages shared layouts, includes, Sass, assets, Jekyll plugins, bibliometric tooling, multilingual behaviour, theme modes and reusable GitHub Actions workflows. Child sites should stay thin and consume this core through the `unaltraweb` gem.

`unaltremanual` sites can also build language-specific PDF editions and matching web-cover images in an isolated Pandoc/XeLaTeX container. PDF status is offline; build and local review are available through Make and the MCP control plane. When PDF output is enabled, default generated PDF and cover outputs are not versioned. The selected `latest` or stable selector is rendered into both the website and PDF metadata.

## Current Status

- The core builds successfully as a standalone Jekyll site through Docker.
- The repository is packaged as the `unaltraweb` gem and publishes the shared Docker runtime image as `ghcr.io/dosquartsdedocs/unaltraweb`.
- The modular MCP wheel contains profile-specific scaffolds, the versioned component BOM, doctor, and local inspection; it does not bundle the gem, factory checkout, worker images, or companion renderers.
- The companion `../unaltraweb-template` repository remains the full-profile integration fixture and visual demo.
- The project is still pre-release. Some inherited `al-folio` implementation details remain while the core is being generalized.

## Repository Roles

- `unaltraweb`: reusable code, theme defaults, plugins, styles, scripts, documentation, reusable workflows and the Docker runtime image.
- `unaltraweb-template`: full-profile demo and Playwright integration fixture for the gem consumer path.
- `docs/`: the public reference site for `unaltraweb`.

The template is the better place to validate gem consumption, centralized styles and shared logic because it exercises `unaltraweb` as an external dependency instead of relying on the core checkout itself.

## Profile Configuration

Prepared site families are called site profiles. The four profiles and their editor-owned paths are summarized near the top of this README.

Select a profile in a child site's `_config.yml`:

```yaml
unaltraweb:
  site_profile: unaltreselfie
  features:
    blog: true
    cv: true
    projects: true
    publications: true
    metrics: true
```

## Quick Start

Create a child site with the `new_web` MCP tool or the package CLI:

```bash
unaltraweb-mcp --project ./my-site new-web --site-profile unaltreselfie --title "My site" --default-lang en
```

From this factory checkout, the equivalent command is:

```bash
MCP_CONSUMER_WORKSPACE=./my-site make mcp-new-web NEW_WEB_PROFILE=unaltreselfie SITE_TITLE="My site" DEFAULT_LANG=en
```

The operation uses only assets shipped in `unaltraweb_mcp`, preflights all managed paths, writes `.unaltraweb/scaffold.json`, and never overwrites differing files. Later `scaffold_sync` calls can update only unchanged baseline runtime files, including the pull-request template, and never touch config, README prose, or content. `dosquartsdedocs/unaltraweb-template` remains available when a full multi-profile demo with Playwright tests is more useful than a clean profile-specific site.

After creation, there are two supported editing paths:

- Local Docker editing for previews, larger edits, screenshots, tests, and rendered-output review before publication.
- GitHub-only editing for small content changes, bibliography updates, page edits and simple configuration changes, followed by an explicit manual workflow run when GitHub Pages must publish the site.

Local editing is intended to require only Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run `make` commands inside the WSL Linux shell.

## Documentation

- `docs/_pages/en/index.md`: public overview for the `unaltraweb` reference site.
- `docs/_documentation/en/`: reference pages for quick start, tools, usage, profiles, syntax, themes, customization, distribution and development.
- `docs/Gemfile`: local child-site Gemfile that consumes this checkout as the `unaltraweb` gem.
- `docs/_config.yml`: docs site config using `theme: unaltraweb` and `site_profile: unaltredocs`.

The core Jekyll build excludes `docs/`. Publish the reference site separately from the `docs/` folder or through a dedicated workflow.
- `TODO.md`: working state, decisions and next tasks.

## Development

Use the core Docker workflow when checking the core repository itself:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

Use the `unaltraweb` reference-site workflow when checking `docs/` through the real `unaltredocs` profile:

```bash
make docs-serve DOCKER_IMAGE=unaltraweb:dev
make docs-build DOCKER_IMAGE=unaltraweb:dev
```

The pending distribution contract selects `ghcr.io/dosquartsdedocs/unaltraweb:0.3.0` as the eventual consumer runtime; it does not assert that this remote tag exists yet. The mutable `:main` channel is reserved for explicit maintainer testing; locally built core images use the `:dev` name. The gem remains the source of theme code.

The independent manual PDF runtime is built from `scripts/manual/Dockerfile`; it is deliberately separate from the Jekyll image so normal site builds do not carry Pandoc and TeX Live.

The GHCR image is a shared runtime, not the source of the theme. Publish it only through the manual Docker image workflow when runtime dependencies change. That workflow does not receive package-write permissions until its strict release preflight, source/package tests, image builds, MCP smoke test and docs build have all passed.

When running the core and the template profiles together, keep `unaltraweb` on port `4000` and the template profile servers on `4001` through `4004`.

Use the template when validating the gem consumer path:

```bash
cd ../unaltraweb-template
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreselfie PORT=4018
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte PORT=4019
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual PORT=4020
make down
```

The template tests are intentionally heavier because they run browser smoke tests and screenshots. On constrained machines, prefer `make build` first and run Playwright only when needed.

## Modular Wheel And Doctor

The `unaltraweb-mcp` wheel is intentionally a small control and inspection package. A wheel-only install supports `version`, `new-web`, top-level `doctor`, the host-only `import-calibre` command, constrained SHA-256 source edits, baseline-aware `scaffold_sync`, `site-doctor`, `html-audit`, and package-only inspections such as `detect-site`, `profile-check`, `content-inventory`, and `build-health`. Commands that execute factory Make targets or serve MCP require a factory checkout and fail with an explicit `UNALTRAWEB_FACTORY_DIR` remediation when it is absent.

```bash
unaltraweb-mcp version
unaltraweb-mcp doctor
unaltraweb-mcp doctor --project /path/to/site
unaltraweb-mcp doctor --project /path/to/site --docker
```

Doctor is offline. The optional `--docker` mode only calls local Docker version/image inspection and never pulls. Its findings have stable `code`, `severity`, `expected`, `actual`, and `remediation` fields. `src/unaltraweb_mcp/component-contract.json` is the canonical release BOM; the adjacent versioned JSON Schema defines its machine-readable contract.

## Global Dockerized MCP

`unaltraweb` provides one global, on-demand stdio MCP whose containers are scoped to the current consumer workspace. Each client session gets an independent Docker-generated container name plus stable factory, role, and project labels, so concurrent sessions for the same project do not collide. The launcher reuses or attempts to pull the selected `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` image; while that component is `pending`, the pull may fail rather than silently building under the remote release reference. To build and test the image explicitly from this checkout instead:

```bash
make mcp-build
make mcp-smoke
```

ContExt reads the canonical manifest transport `make -C ${factoryRoot} mcp-stdio` and supplies `MCP_CONSUMER_WORKSPACE=${workspaceFolder}` through the process environment. The manifest continues to use `make`, an allowed container host launcher, but no consumer path is parsed by Make or interpolated into shell source. An equivalent direct launch is:

```bash
MCP_CONSUMER_WORKSPACE="$PWD" make --silent --no-print-directory -C /path/to/unaltraweb mcp-stdio
```

Replace `/path/to/unaltraweb` with this checkout's absolute path and restart the client after changing its configuration. Each session canonicalizes the inherited workspace after launch, then mounts it at `/workspace` and at its canonical host path, so Docker-backed authoring tools pass valid bind paths to the host daemon. `build_site` runs Jekyll directly in that MCP runtime and returns the offline HTML audit. `preview_start`, `preview_status`, and `preview_stop` manage one labelled preview container per project. By default, Docker publishes container port `4000` on a free loopback host port, so previews from distinct workspaces can run concurrently; pass a nonzero `port` only when a fixed host port is required. A running preview created by the former fixed-port default remains idempotently usable until stopped, after which the dynamic default applies. `http_check` derives its origin only from that owned preview and never accepts an arbitrary URL.

Dependency preparation builds images and required companions only; it does not initialize a consumer website, and companion `init` aggregation is disabled. Create a site explicitly with the `new_web` MCP tool. To clean up one consumer project, pass the same canonical project path used at launch:

```bash
MCP_CONSUMER_WORKSPACE=/path/to/consumer make mcp-down
# If the path was moved or deleted:
MCP_CONSUMER_WORKSPACE=/old/absent/path MCP_PROJECT_ID=0123456789abcdef make mcp-down
# Or explicitly remove a stale inherited workspace binding:
env -u MCP_CONSUMER_WORKSPACE MCP_PROJECT_ID=0123456789abcdef make mcp-down
```

When the workspace is live, a supplied `MCP_PROJECT_ID` must match its canonical path. A retained ID is accepted only without a live workspace, making stale-resource cleanup explicit. Cleanup selects only resources carrying both `io.context.mcp-factory=unaltraweb` and that project's stable `io.context.mcp-project` label. Maintainers can deliberately clean every labelled unaltraweb MCP resource with `make mcp-down-all`; neither target deletes images or touches unlabelled containers and networks.
Replace the example retained ID with the 16-hex value from that project's `io.context.mcp-project` Docker label.

## Bibliometrics

Normal Jekyll builds must stay static. External metrics are fetched only through explicit update commands and written back to local data files before build time.

```bash
make metrics-scimago-fetch
make metrics-update
make metrics-check
```

Use `METRICS_ARGS` and `SCIMAGO_INPUT` for local safety checks and local Scimago files:

```bash
make metrics-update METRICS_ARGS="--strict-external --require-scimago"
make metrics-scimago-fetch SCIMAGO_INPUT=path/to/scimagojr.csv
```

The manual metrics workflow keeps Scimago caches and temporary diagnostics out of pull requests. When PR creation is enabled, it includes only versionable generated data: `_bibliography/**/*.bib` and `_data/metrics.yml`.

## Formatting

`package.json` declares Prettier and the Liquid plugin. Regenerate `package-lock.json` with `npm install` on a machine with Node/npm available; do not hand-edit dependency integrity data.

`npm` is development tooling, not part of the docs deploy or normal Jekyll runtime. If we need a containerized workflow for it, prefer a small dedicated Node tooling image or GitHub Action over adding Node/npm to every Jekyll build path.

## Publishing Docs

The core repository can deploy the `unaltraweb` reference site from `docs/` through the manual `.github/workflows/deploy.yml` workflow. Configure GitHub Pages for GitHub Actions deployments when using that route.

It can also publish the reference site locally to `gh-pages`:

```bash
make docs-publish
```

Sites created by `new_web` include a manual GitHub Pages workflow that requires the full locally reviewed `main` commit SHA before delegating to the reusable core workflow. The current reusable publication contract also requires the manual PDF worker by full image digest. Local `make build` and `make test` validate the site without publishing or changing Git history.

## CI Scope

`.github/workflows/ci.yml` runs automatically for pushes and pull requests. It compiles and unit-tests supported Python versions, checks patch whitespace, validates workflow and distribution structure, builds/tests the wheel and gem, then uses cached Docker builds for the MCP smoke test and reference docs. This normal CI intentionally runs `distribution-check`, not the strict release gate, so truthful `pending` releases do not block ordinary development.

CodeQL separately analyzes JavaScript/TypeScript, Python and Ruby on pull requests, default-branch pushes and a weekly schedule. Docs deployment, link checks, publication metrics, package preparation and image publication remain manual.

Core artifact workflows run `distribution-check` while selected candidates are truthfully `pending`, validate the selected ref against the BOM version, and keep their preflight jobs credential-free. Once the final source and release intent are reviewed, mark its components `ready` and commit that state. Runtime, MCP, and manual PDF publication separates authority across a signing/package-write build job that never runs candidates, a read-only test job that verifies GitHub-signed digest/source provenance and removes GHCR credentials before execution, and a package-write promotion job that executes no candidate. Every image is built once under only its SHA tag; only the exact digests that pass all Ruby, PDF, reproducibility, MCP, and docs gates can reach verified `sha-*`, `main`, and `latest` aliases. GHCR does not make the initial absence lookup and later tag write atomic, so the signed tested digest, not a claim of compare-and-swap no-clobber, is the trust anchor. Record those digests and package checksums in a versioned `release-candidates.json` child commit; validation requires that receipt to be the only change. After `distribution-release-check`, tag the receipt commit. The tag-only job verifies SHA-tag equality, signed provenance and the revision label against the receipt's `source_commit`, then promotes only the receipt's manifests to checked semver aliases without rebuilding or executing them. `released` remains available for already-published components; released containers other than the self-describing MCP must be digest-pinned. Package preparation never uploads to RubyGems or PyPI, creates a GitHub release, tags the repository or publishes an image; those operations require separate explicit maintainer approval.

## Attribution

`unaltraweb` started from the open-source `al-folio` Jekyll theme and is being refactored into a self-owned reusable core for `dosquartsdedocs` sites. Retain upstream attribution where inherited code remains relevant.
