# Installing And Deploying

`unaltraweb` is intended to be consumed from a child site, normally `dosquartsdedocs/unaltraweb-template`.

## Create A Site

Use local Docker when you need previews, larger edits, screenshots, tests or low-cost publishing. Use GitHub-only editing when you only need content changes and can publish with an explicit manual workflow.

### GitHub-only

1. Create a new repository from `dosquartsdedocs/unaltraweb-template`.
2. Edit `_config.yml` with the public `url`, `baseurl`, title, language settings and `unaltraweb.site_profile`.
3. Edit content in `_pages/`, `_posts/`, `_projects/`, `_chapters/`, `_bibliography/`, `_data/` and `assets/`.
4. Commit to `main`.
5. Publish explicitly, either by running the manual deploy workflow in GitHub Actions or by cloning locally and running `make publish`.

This path requires no local install. It is appropriate for adding bibliography entries, editing pages, updating posts and changing structured data.

## Local Template Workflow

Install Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run these commands inside the WSL Linux shell.

```bash
cd ../unaltraweb-template
make serve
make build
make publish
make test
make down
```

The template pulls `ghcr.io/dosquartsdedocs/unaltraweb:main` by default. That GHCR package must be public before unauthenticated users can pull it. The image is only the local runtime; layouts, styles and plugins still come from the `unaltraweb` gem.

When running the core documentation and all template profiles together, use the convention `4000` for `unaltraweb` and `4001` through `4004` for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`.

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

This core repository publishes its own `unaltraweb` reference site from `docs/` with the manual `.github/workflows/deploy.yml` workflow. In GitHub repository settings, Pages should use GitHub Actions as the deployment source when using this workflow.

The reference site uses the real `unaltredocs` profile from the local `unaltraweb` gem:

```bash
make docs-serve DOCKER_IMAGE=unaltraweb:local
make docs-build DOCKER_IMAGE=unaltraweb:local
make docs-publish DOCKER_IMAGE=unaltraweb:local
```

Publication metrics are intentionally separate from automatic deploys. Run them locally or through the manual/reusable `.github/workflows/metrics-update.yml` workflow.

## Child Site Deployment

Child sites should prefer local publishing when possible:

```bash
make publish
```

Configure GitHub Pages to deploy from the `gh-pages` branch and `/` folder. The branch is generated and can be replaced by each new local publish.

When a team needs GitHub-hosted publishing, the child site can keep a manual workflow wrapper around the reusable workflow:

```yaml
jobs:
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@main
```

See `docs/distribution.md` for the update model and `../unaltraweb-template/.github/workflows/deploy.yml` for the current wrapper.
