---
title: Run And Preview A Site
description: How to create, edit, preview and publish unaltraweb sites.
lang: en
ref: usage_workflow
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- site-designers
- contributors
- core-developers
section: Work Locally
weight: 120
permalink: "/usage/"
nav_title: Run And Preview
---
<p class="lede">An <code>unaltraweb</code> site should keep content and local choices in the child repository. Shared rendering, styles, plugins, scripts and workflows stay in the core.</p>

## Create A Site

1. Call `new_web` with one `unaltraweb.site_profile` and the site identity/language settings.
2. Inspect the generated `_config.yml` and localized home page.
3. Reserve a focused task, create one branch, and open a small Draft pull request. Never edit `main` directly, and allow only one active editor per file.
4. Edit content and data files. MCP agents should read a source hash, review the default `site_source_write` dry-run, then apply the exact CAS update.
5. Stop and ask the maintainer if another task overlaps or a conflict appears.
6. The maintainer runs `site_doctor`, `profile_check`, `site_check`, `build_site`, and required renderers, then reviews the returned HTML audit and rendered outputs.
7. After review, the maintainer merges the pull request and manually runs the generated GitHub Pages workflow when publication is intended.

CLI equivalent:

```bash
unaltraweb-mcp --project ./example-site new-web --site-profile unaltreselfie --title "Example Site" --url https://example.github.io --baseurl /example-site
```

Minimal profile selection:

```yaml
title: Example Site
url: https://example.github.io
baseurl: /example-site

unaltraweb:
  site_profile: unaltreselfie
```

## What To Edit

| Path | Purpose |
|---|---|
| `_config.yml` | Site identity, URL, languages, profile, feature flags and profile-specific options |
| `_pages/` | Home, navigation pages, profile pages, manuals and documentation landing pages |
| `_posts/` and `_news/` | Blog posts and short dated announcements |
| `_projects/`, `_outputs/`, `_books/`, `_theses/` | Structured collections rendered by reusable layouts |
| `_chapters/` and `_documentation/` | Manual chapters and documentation pages |
| `_bibliography/` | Publication and manual bibliography BibTeX files |
| `_data/` | Team, metrics, repositories, translations and other structured data |
| `_sass/_site-custom.scss` | Local colors, type, spacing and small component overrides |
| `assets/` | Images, PDFs, diagrams, downloads and generated previews |

## What Not To Copy

Do not copy core `_layouts`, `_includes`, `_sass` or plugin files into a child site unless you are intentionally making a local override. Copying core code blocks future updates from the gem.

Use local overrides only when the site genuinely needs different behavior:

```text
_layouts/my-local-page.liquid
_sass/_site-custom.scss
assets/img/local-brand.svg
```

## Preview And Build Locally

```bash
make serve
make build
make test
make down
```

The generated repository contains one profile. Create a separate temporary site with `new_web` to compare another profile. Publication runs through the generated manual GitHub Pages workflow and is never triggered by a push or these local commands.

## Update Model

- Gem updates change layouts, includes, Sass, plugins and scripts.
- Docker image updates change local runtime dependencies and are published manually.
- Reusable workflow updates change optional GitHub build and deploy behavior.
- Package scaffold changes affect newly generated sites. Existing generated repositories can review `scaffold_sync`, which manages exactly `.gitignore`, `.unaltraweb/docker-mount.sh`, `.github/CONTRIBUTING.md`, `.github/dependabot.yml`, `Makefile`, `Gemfile`, `Gemfile.lock`, `.github/pull_request_template.md`, and `.github/workflows/deploy.yml` from `.unaltraweb/scaffold.json`. It can adopt bytes that already equal the current package payload without rewriting the file. A conflict aborts the entire apply, and retired entries are removed from the baseline without deleting project files. Synchronization never changes site-owned README/agent guidance, config, or content.

## Safe MCP Editing

`site_source_read`, `site_source_write`, and `site_source_delete` are deliberately restricted to `_config.yml`, Markdown/HTML content collections, YAML/JSON/CSV below `_data/`, and Markdown below `context/`. They do not expose generic filesystem access and cannot mutate workflows, runtime files, core overrides, bibliography, assets, or generated output. Writes default to dry-run and use SHA-256 optimistic concurrency; destructive deletes additionally require explicit confirmation and can never remove `_config.yml`.

Dependabot can stay enabled for Bundler and GitHub Actions in child sites, but deploy workflows should remain manual so dependency pull requests do not consume deploy minutes automatically.

## Content-Only Work

The GitHub web UI is enough for common edits when editors follow the [issue, reservation, branch, and Draft pull request protocol](../github-web-editing/):

- add or correct a BibTeX record;
- edit a Markdown page;
- add a post or news item;
- update a team member in `_data/`;
- change profile feature flags in `_config.yml`.

The maintainer uses local Docker to inspect the rendered result before merge. Publication remains an explicit manual workflow action after the reviewed change reaches `main`.
