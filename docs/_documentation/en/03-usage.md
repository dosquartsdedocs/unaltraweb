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

1. Create a repository from `dosquartsdedocs/unaltraweb-template`.
2. Edit `_config.yml`.
3. Choose one `unaltraweb.site_profile`.
4. Edit content and data files.
5. Commit to `main`.
6. Publish locally with `make publish`, or run the manual GitHub deploy workflow when local publishing is not possible.

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
make publish
make test
```

Preview a different profile without changing what GitHub Pages publishes:

```bash
make serve SITE_PROFILE=unaltreprojecte
make build SITE_PROFILE=unaltremanual
```

Run all profile demos together:

```bash
make serve-allprofiles
```

## Update Model

- Gem updates change layouts, includes, Sass, plugins and scripts.
- Docker image updates change local runtime dependencies and are published manually.
- Reusable workflow updates change optional GitHub build and deploy behavior.
- Template changes affect new sites, but existing GitHub-template repositories do not automatically inherit scaffold changes.

Dependabot can stay enabled for Bundler and GitHub Actions in child sites, but deploy workflows should remain manual so dependency pull requests do not consume deploy minutes automatically.

## Content-Only Work

The GitHub web UI is enough for common edits:

- add or correct a BibTeX record;
- edit a Markdown page;
- add a post or news item;
- update a team member in `_data/`;
- change profile feature flags in `_config.yml`.

Use local Docker when you need to inspect the rendered result before committing or publish the generated site to `gh-pages`.
