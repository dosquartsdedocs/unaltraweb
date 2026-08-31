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
3. Edit content and data files. MCP agents should read a source hash, review the default `site_source_write` dry-run, then apply the exact CAS update.
4. Run `site_doctor`, `profile_check`, `site_check`, and `build_site`; review the returned HTML audit.
5. Commit the reviewed site to `main`.
6. Run the generated manual GitHub Pages workflow, or replace it with the workflow required by another host.

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

The generated repository contains one profile. Create a separate temporary site with `new_web` to compare another profile. Publication runs through the generated manual GitHub Pages workflow and is never triggered by these local commands.

## Update Model

- Gem updates change layouts, includes, Sass, plugins and scripts.
- Docker image updates change local runtime dependencies and are published manually.
- Reusable workflow updates change optional GitHub build and deploy behavior.
- Package scaffold changes affect newly generated sites. Existing generated repositories can review `scaffold_sync`, which manages only `.gitignore`, Makefile, and Gemfile/lock from `.unaltraweb/scaffold.json`; it never overwrites conflicts or changes config/content. The deploy workflow remains project-owned so each site can retain its reviewed core pin and optional inputs.

## Safe MCP Editing

`site_source_read`, `site_source_write`, and `site_source_delete` are deliberately restricted to `_config.yml`, Markdown/HTML content collections, YAML/JSON/CSV below `_data/`, and Markdown below `context/`. They do not expose generic filesystem access and cannot mutate workflows, runtime files, core overrides, bibliography, assets, or generated output. Writes default to dry-run and use SHA-256 optimistic concurrency; destructive deletes additionally require explicit confirmation and can never remove `_config.yml`.

Dependabot can stay enabled for Bundler and GitHub Actions in child sites, but deploy workflows should remain manual so dependency pull requests do not consume deploy minutes automatically.

## Content-Only Work

The GitHub web UI is enough for common edits:

- add or correct a BibTeX record;
- edit a Markdown page;
- add a post or news item;
- update a team member in `_data/`;
- change profile feature flags in `_config.yml`.

Use local Docker when you need to inspect the rendered result before committing. Publication remains an explicit manual workflow action.
