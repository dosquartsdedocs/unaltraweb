# Installing And Deploying

`unaltraweb` is intended to be consumed from a child site, normally `dosquartsdedocs/unaltraweb-template`.

## Create A Site

1. Create a new repository from `dosquartsdedocs/unaltraweb-template`.
2. Edit `_config.yml` with the public `url`, `baseurl`, title, language settings and `unaltraweb.site_profile`.
3. Edit content in `_pages/`, `_posts/`, `_projects/`, `_chapters/`, `_bibliography/`, `_data/` and `assets/`.
4. Push to `main`. The template deploy workflow calls the reusable workflow from this core repository.

## Local Template Workflow

```bash
cd ../unaltraweb-template
make bootstrap
make serve
make build
make test
make down
```

While developing the core locally:

```bash
cd ../unaltraweb-template
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual
```

## Core Development Workflow

Use this repository directly when changing shared layouts, includes, Sass, plugins, scripts or docs:

```bash
docker compose -f docker-compose.yml run --rm --entrypoint "bash -lc '(bundle check || bundle install) && bundle exec jekyll build --trace'" jekyll
docker compose -f docker-compose.yml down --remove-orphans
```

This can be resource-heavy because the core demo build minifies JavaScript and generates responsive images. On constrained machines, avoid running full Docker builds unless needed.

## Deployment

This core repository publishes its own compact documentation/demo site from `docs/` with `.github/workflows/deploy.yml`. In GitHub repository settings, Pages should use GitHub Actions as the deployment source.

Publication metrics are intentionally separate from automatic deploys. Run them locally or through the manual/reusable `.github/workflows/metrics-update.yml` workflow.

## Child Site Deployment

Child sites should use the reusable workflow:

```yaml
jobs:
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@main
```

See `docs/distribution.md` for the update model and `../unaltraweb-template/.github/workflows/deploy.yml` for the current wrapper.
