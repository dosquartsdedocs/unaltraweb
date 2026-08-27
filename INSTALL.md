# Installing And Deploying

`unaltraweb` is intended to be consumed from a thin child site created by the package-owned `new_web` operation.

## Create A Site

Use local Docker when you need previews, larger edits, screenshots, tests, or rendered-output review. Use GitHub-only editing when you only need content changes and can publish with an explicit manual workflow.

Create a clean profile-specific repository locally or through the MCP:

```bash
unaltraweb-mcp --project ./my-site new-web --site-profile unaltredocs --title "Project documentation" --default-lang en
```

The command is idempotent for identical inputs and refuses differing files, symlinks, and unsafe language paths. It does not require or inspect `unaltraweb-template`.

### GitHub-only

1. Push a site created by `new_web` to a new repository. A fork of `dosquartsdedocs/unaltraweb-template` is an optional alternative when its full demo and workflow files are wanted.
2. Edit `_config.yml` with the public `url`, `baseurl`, title, language settings and `unaltraweb.site_profile`.
3. Edit content in `_pages/`, `_posts/`, `_projects/`, `_chapters/`, `_bibliography/`, `_data/` and `assets/`.
4. Commit to `main`.
5. Publish explicitly by running the generated manual deploy workflow in GitHub Actions.

This path requires no local install. It is appropriate for adding bibliography entries, editing pages, updating posts and changing structured data.

## Local Site Workflow

Install Git, Docker and GNU Make. On Windows, use WSL2 with Docker Desktop and run these commands inside the WSL Linux shell.

```bash
cd ./my-site
make serve
make build
make test
make down
```

These targets run through the pinned MCP Docker image; Ruby and Bundler are not required on the host. The native targets remain available inside the MCP runtime. Layouts, styles and plugins still come from the `unaltraweb` gem/core mounted in that image.

When running the core documentation and all template profiles together, use the convention `4000` for `unaltraweb` and `4001` through `4004` for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`.

While developing the core locally:

```bash
cd ../unaltraweb-template
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual
```

For a configured `unaltremanual` PDF edition, Docker remains the only runtime prerequisite:

```bash
make manual-pdf-status LOCAL_CORE=../unaltraweb
make manual-pdf-check LOCAL_CORE=../unaltraweb
make manual-pdf-build LOCAL_CORE=../unaltraweb
make manual-pdf-publish LOCAL_CORE=../unaltraweb
```

The publication command is a local dry-run by default. A real copy into the configured `assets/pdf/` and cover paths requires `MANUAL_PDF_PUBLISH_DRY_RUN=0`; review the generated files under `tmp/manual-pdf/` first. `manual-pdf-check` fails unless those public files match the latest fresh build.

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

Sites created by `new_web` include a manual workflow wrapper around the reusable GitHub Pages workflow. Configure GitHub Pages to use GitHub Actions as its source, then run the workflow explicitly when reviewed content should go live:

```yaml
jobs:
  deploy:
    uses: dosquartsdedocs/unaltraweb/.github/workflows/site-deploy.yml@7855522e00562a43443b2a2e3294bb3c0ce7dc34
```

Keep the reusable workflow pinned to a reviewed full commit SHA because it receives Pages and OIDC permissions.

See `docs/distribution.md` for the update model and `../unaltraweb-template/.github/workflows/deploy.yml` for the current wrapper.
