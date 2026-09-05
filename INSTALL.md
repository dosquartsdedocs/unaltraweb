# Installing And Deploying

`unaltraweb` is intended to be consumed from a thin child site created by the package-owned `new_web` operation.

## Create A Site

Use local Docker when you need previews, larger edits, screenshots, tests, or rendered-output review. Use GitHub-only editing when you only need content changes and can publish with an explicit manual workflow.

Create a clean profile-specific repository locally or through the MCP:

```bash
unaltraweb-mcp --project ./my-site new-web --site-profile unaltredocs --title "Project documentation" --default-lang en
```

The command is idempotent for identical inputs and refuses differing files, symlinks, and unsafe language paths. It records exactly nine package-managed scaffold controls in `.unaltraweb/scaffold.json`: `.gitignore`, `.unaltraweb/docker-mount.sh`, `.github/CONTRIBUTING.md`, `.github/dependabot.yml`, `Makefile`, `Gemfile`, `Gemfile.lock`, `.github/pull_request_template.md`, and `.github/workflows/deploy.yml`. An explicit `scaffold_sync` dry-run can later update files that remain unchanged from their baseline and adopt exact current package bytes without rewriting them. Synchronization is all-or-nothing when a managed file conflicts, and retired paths are removed only from the baseline without deleting project files. `README.md`, `AGENTS.md`, `_config.yml`, and content remain site-owned. The command does not require or inspect `unaltraweb-template`.

The wheel can verify its own modular distribution and a generated site without a factory checkout:

```bash
unaltraweb-mcp doctor
unaltraweb-mcp doctor --project ./my-site
```

Add `--docker` only when local presence of the selected feature images should be inspected. Doctor never pulls images. Factory-backed build, computation, capture, PDF, bibliometrics, prompt, and MCP serve commands require `UNALTRAWEB_FACTORY_DIR` or the published MCP container.

### GitHub-only

1. Push a site created by `new_web` to a new repository. A fork of `dosquartsdedocs/unaltraweb-template` is an optional alternative when its full demo and workflow files are wanted.
2. Read the generated `README.md`, open an issue, and get assigned or reserve the exact files with maintainer acceptance.
3. Create one task branch, edit only its profile-appropriate content paths, and open a small Draft pull request. Never edit `main` directly, and allow only one active editor per file.
4. Stop and ask the maintainer if work overlaps or GitHub reports a conflict.
5. The maintainer runs local checks and renders, reviews and merges the pull request, and only then publishes explicitly with the manual deploy workflow in GitHub Actions.

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

These targets run through the pinned MCP Docker image; Ruby and Bundler are not required on the host. `make test` also audits generated HTML links, fragments, IDs, Liquid residue, image alt attributes, title, and language without fetching external URLs. The native targets remain available inside the MCP runtime. Layouts, styles and plugins still come from the `unaltraweb` gem/core mounted in that image.

When running the core documentation and all template profiles together, use the convention `4000` for `unaltraweb` and `4001` through `4004` for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs`.

While developing the core locally:

```bash
cd ../unaltraweb-template
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltremanual
```

For a configured `unaltremanual` PDF edition, Docker remains the only runtime prerequisite. Package-created sites use the factory-backed MCP tools rather than copying PDF targets into their small Makefile:

```text
manual_pdf_status
manual_pdf_build
manual_pdf_publish
manual_pdf_publish(dry_run=false, confirm_publish=true)
```

PDF status and checks are offline and do not pull or start a Docker image. Build, publish, and sync use the selected PDF worker. MCP publication is a local dry-run by default; a real copy into the configured `assets/pdf/` and cover paths requires both `dry_run=false` and `confirm_publish=true`. Factory maintainers can use the corresponding `make -C /path/to/unaltraweb manual-pdf-*` targets with `MCP_CONSUMER_WORKSPACE=/path/to/site`; Make publication requires `MANUAL_PDF_PUBLISH_DRY_RUN=0`. Review the generated files under `tmp/manual-pdf/` first. The default public PDF and cover outputs are ignored deployment products rather than versioned files. If an older repository already tracks them, remove only those configured outputs from the index once with `git rm --cached -- <pdf-path> <cover-path>` and review that commit before deployment.

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
make docs-serve DOCKER_IMAGE=unaltraweb:dev
make docs-build DOCKER_IMAGE=unaltraweb:dev
make docs-publish DOCKER_IMAGE=unaltraweb:dev
```

Publication metrics and deployment are intentionally separate manual actions. Run metrics locally or through the manual/reusable `.github/workflows/metrics-update.yml` workflow.

## Child Site Deployment

Sites created by `new_web` include a manual workflow wrapper around the reusable GitHub Pages workflow. Configure GitHub Pages to use GitHub Actions as its source, then run the workflow explicitly when reviewed content should go live:

```yaml
jobs:
  deploy:
    uses: <consumer_integration.site_deploy_workflow>@<consumer_integration.core_sha>
    with:
      reviewed_sha: ${{ inputs.reviewed_sha }}
      manual-pdf-image: "<consumer_integration.manual_pdf_image>"
      check-manual-pdf: false
      sync-manual-pdf: true
      vegavisuals-sha: "<consumer_integration.vegavisuals_sha>"
```

The generated wrapper first requires `reviewed_sha` to equal the selected `main` commit, then passes the same value to the reusable workflow for an independent source check. The `consumer_integration` object in `src/unaltraweb_mcp/component-contract.json` is the sole source for the reviewed core, workflow, PDF worker, and Vega revisions rendered into `Gemfile`, `Gemfile.lock`, and the caller. Future provider updates must repeat the M -> D -> B order: merge the provider, build D from that permanent commit, then update the tuple atomically in a separate change. Do not use a mutable workflow ref or a version-tagged image as a substitute for either pin.

See `docs/_documentation/en/40-distribution.md` for the update model and `src/unaltraweb_mcp/scaffolds/common/.github/workflows/deploy.yml.tmpl` for the packaged wrapper template.
