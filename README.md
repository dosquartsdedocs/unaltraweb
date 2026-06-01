# unaltraweb

`unaltraweb` is a reusable Jekyll core for academic, research project, software and documentation websites maintained by `dosquartsdedocs`.

It packages shared layouts, includes, Sass, assets, Jekyll plugins, bibliometric tooling, multilingual behaviour, theme modes and reusable GitHub Actions workflows. Child sites should stay thin and consume this core through the `unaltraweb` gem.

## Current Status

- The core builds successfully as a standalone Jekyll site through Docker.
- The repository is packaged as the `unaltraweb` gem.
- The companion `../unaltraweb-template` repository is the primary integration fixture and starter scaffold.
- The project is still pre-release. Some inherited `al-folio` implementation details remain while the core is being generalized.

## Repository Roles

- `unaltraweb`: reusable code, theme defaults, plugins, styles, scripts, documentation and reusable workflows.
- `unaltraweb-template`: thin starter site, demo content, local Docker workflow and Playwright smoke tests for the gem consumer path.
- `docs/`: a compact documentation/demo site for the core itself.

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

## Documentation

- `docs/index.md`: compact public overview for the core docs/demo site.
- `docs/profiles.md`: prepared site profile overview.
- `docs/template.md`: role of `unaltraweb-template` as starter and integration fixture.
- `docs/development.md`: safe local verification workflow.
- `docs/customization.md`: detailed local customization reference.
- `docs/distribution.md`: core/template split and update model.
- `docs/bibliometrics.md`: static bibliometric metrics pipeline.

The core Jekyll build excludes `docs/`. Publish the docs/demo site separately from the `docs/` folder or through a dedicated workflow.
- `TODO.md`: working state, decisions and next tasks.

## Development

Use the core Docker workflow when checking the core repository itself:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

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

The core repository deploys the compact docs/demo site from `docs/` through `.github/workflows/deploy.yml`. Configure GitHub Pages for GitHub Actions deployments in the repository settings.

## CI Scope

Automatic CI is intentionally limited to the web/docs path and its local link check. Publication metrics run through the manual/reusable `.github/workflows/metrics-update.yml` workflow or local commands. CodeQL is kept as an optional manual workflow.

## Attribution

`unaltraweb` started from the open-source `al-folio` Jekyll theme and is being refactored into a self-owned reusable core for `dosquartsdedocs` sites. Retain upstream attribution where inherited code remains relevant.
