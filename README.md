# unaltraweb

`unaltraweb` is a reusable Jekyll core for academic, research project, software and documentation websites maintained by `dosquartsdedocs`.

It packages shared layouts, includes, Sass, assets, Jekyll plugins, bibliometric tooling, multilingual behaviour, theme modes and reusable GitHub Actions workflows. Child sites should stay thin and consume this core through the `unaltraweb` gem.

`unaltremanual` sites can also build language-specific PDF editions and matching web-cover images in an isolated Pandoc/XeLaTeX container. PDF status, build, and local publication are available through Make and the MCP control plane.

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

## Site Profiles

Prepared site families are called site profiles:

- `unaltreselfie`
- `unaltreprojecte`
- `unaltremanual`
- `unaltredocs`

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
make mcp-new-web PROJECT=./my-site NEW_WEB_PROFILE=unaltreselfie SITE_TITLE="My site" DEFAULT_LANG=en
```

The operation uses only assets shipped in `unaltraweb_mcp`, preflights all managed paths, writes `.unaltraweb/scaffold.json`, and never overwrites differing files. Later `scaffold_sync` calls can update only unchanged baseline runtime files and never touch config or content. `dosquartsdedocs/unaltraweb-template` remains available when a full multi-profile demo with Playwright tests is more useful than a clean profile-specific site.

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

The selected consumer runtime is `ghcr.io/dosquartsdedocs/unaltraweb:0.3.0`. The mutable `:main` channel is reserved for explicit maintainer testing; locally built core images use the `:dev` name. The gem remains the source of theme code.

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

`unaltraweb` provides one global, on-demand stdio MCP whose containers are scoped to the current consumer workspace. Each client session gets an independent Docker-generated container name plus stable factory, role, and project labels, so concurrent sessions for the same project do not collide. The launcher pulls the pinned public image `ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0` when it is not available locally. To build and test the same image from this checkout instead:

```bash
make mcp-build
make mcp-smoke
```

ContExt reads the canonical manifest transport `make -C ${factoryRoot} mcp-stdio PROJECT=${workspaceFolder}`. For global Codex and OpenCode registration, the manager converts the workspace placeholder into a launch-time shell wrapper so `$PWD` is captured before `make -C` changes directory. The manifest itself continues to use `make`, an allowed container host launcher, and does not require a `runtime.allowed_host_launchers` exception. An equivalent OpenCode `command` array is:

```json
[
  "/bin/sh",
  "-c",
  "workspace=$PWD; exec make --silent --no-print-directory -C /path/to/unaltraweb mcp-stdio PROJECT=\"$workspace\""
]
```

Replace `/path/to/unaltraweb` with this checkout's absolute path and restart the client after changing its configuration. Do not use `PROJECT=.` after `make -C` in a global registration. Each session mounts its resolved project at `/workspace` and at its canonical host path, so Docker-backed authoring tools pass valid bind paths to the host daemon. `build_site` runs Jekyll directly in that MCP runtime and returns the offline HTML audit. `preview_start`, `preview_status`, and `preview_stop` manage one labelled preview container per project; `http_check` derives its origin only from that owned preview and never accepts an arbitrary URL.

Dependency preparation builds images and required companions only; it does not initialize a consumer website, and companion `init` aggregation is disabled. Create a site explicitly with the `new_web` MCP tool. To clean up one consumer project, pass the same canonical project path used at launch:

```bash
make mcp-down PROJECT=/path/to/consumer
```

This selects only resources carrying both `io.context.mcp-factory=unaltraweb` and that project's stable `io.context.mcp-project` label. Maintainers can deliberately clean every labelled unaltraweb MCP resource with `make mcp-down-all`; neither target deletes images or touches unlabelled containers and networks.

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

Sites created by `new_web` include a manual GitHub Pages workflow that delegates to the reusable core workflow. Local `make build` and `make test` validate the site without publishing or changing Git history.

## CI Scope

`.github/workflows/ci.yml` runs automatically for pushes and pull requests. It compiles and unit-tests supported Python versions, checks patch whitespace, validates workflow and distribution structure, builds/tests the wheel and gem, then uses cached Docker builds for the MCP smoke test and reference docs. This normal CI intentionally runs `distribution-check`, not the strict release gate, so truthful `pending` releases do not block ordinary development.

CodeQL separately analyzes JavaScript/TypeScript, Python and Ruby on pull requests, default-branch pushes and a weekly schedule. Docs deployment, link checks, publication metrics, package preparation and image publication remain manual.

Core artifact workflows run `distribution-check` while selected candidates are truthfully `pending`; they also validate the selected ref against the BOM version, run relevant tests and build without credentials before a dependent job can log in or push. Once the final source and release intent are reviewed, mark its components `ready` and commit that state. Manual default-branch runs from that commit publish `sha-<full-commit>` images with SBOM/provenance and prepare gem/wheel candidates. Record their immutable digests and checksums in a versioned `release-candidates.json` child commit; validation requires that receipt to be the only change. After `distribution-release-check`, tag the receipt commit. Tag workflows promote the receipt's exact image manifests to semver aliases instead of rebuilding or trusting mutable tags. `released` remains available for already-published components; released containers other than the self-describing MCP must be digest-pinned. Package preparation never uploads to RubyGems or PyPI, creates a GitHub release, tags the repository or publishes an image; those operations require separate explicit maintainer approval.

## Attribution

`unaltraweb` started from the open-source `al-folio` Jekyll theme and is being refactored into a self-owned reusable core for `dosquartsdedocs` sites. Retain upstream attribution where inherited code remains relevant.
