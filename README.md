# unaltraweb

`unaltraweb` is a reusable Jekyll core for academic, research project, software and documentation websites maintained by `dosquartsdedocs`.

It packages shared layouts, includes, Sass, assets, Jekyll plugins, bibliometric tooling, multilingual behaviour, theme modes and reusable GitHub Actions workflows. Child sites should stay thin and consume this core through the `unaltraweb` gem.

## Current Status

- The core builds successfully as a standalone Jekyll site through Docker.
- The repository is packaged as the `unaltraweb` gem and publishes the shared Docker runtime image as `ghcr.io/dosquartsdedocs/unaltraweb`.
- The companion `../unaltraweb-template` repository is the primary integration fixture and starter scaffold.
- The project is still pre-release. Some inherited `al-folio` implementation details remain while the core is being generalized.

## Repository Roles

- `unaltraweb`: reusable code, theme defaults, plugins, styles, scripts, documentation, reusable workflows and the Docker runtime image.
- `unaltraweb-template`: thin starter site, demo content, local Docker workflow and Playwright smoke tests for the gem consumer path.
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

Use `dosquartsdedocs/unaltraweb-template` to create child sites. There are two supported user paths:

- Local Docker editing for previews, larger edits, screenshots, tests and low-cost publishing to `gh-pages`.
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
make docs-serve DOCKER_IMAGE=unaltraweb:local
make docs-build DOCKER_IMAGE=unaltraweb:local
```

The published runtime image is `ghcr.io/dosquartsdedocs/unaltraweb:main`. It replaces the inherited `al-folio` image for local template workflows while the gem remains the source of the theme code.

The GHCR image is a shared runtime, not the source of the theme. Publish it only through the manual Docker image workflow when runtime dependencies change.

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

Child sites should prefer local publishing when possible:

```bash
make publish
```

That builds locally and pushes the generated site to the replaceable `gh-pages` branch.

## CI Scope

Build, deploy, link-check, Docker image, publication metrics and CodeQL workflows are intentionally manual. Publication metrics run through the manual/reusable `.github/workflows/metrics-update.yml` workflow or local commands.

## Attribution

`unaltraweb` started from the open-source `al-folio` Jekyll theme and is being refactored into a self-owned reusable core for `dosquartsdedocs` sites. Retain upstream attribution where inherited code remains relevant.
