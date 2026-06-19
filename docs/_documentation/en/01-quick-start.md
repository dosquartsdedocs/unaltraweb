---
title: Choose Your unaltraweb Workflow
description: Create and edit an unaltraweb site through GitHub or locally with Docker.
lang: en
ref: quick_start
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Start Here
weight: 10
permalink: "/quick-start/"
nav_title: Start Here
---
<p class="lede">Start from <code>unaltraweb-template</code>. Prefer the local Docker workflow for previews, checks and low-cost publishing. Use GitHub-only editing when contributors cannot work locally, then publish with an explicit manual workflow run.</p>

## Choose A Path

- **Local Docker**: requires Git, Docker and Make. Good for previewing the site, trying profiles, larger edits, validation and publishing to `gh-pages`.
- **GitHub-only**: no local setup. Good for editing pages, posts, bibliography records, project data and small configuration changes; deployment is manual.

## GitHub-only Editing

1. Create a new repository from `dosquartsdedocs/unaltraweb-template`.
2. Edit `_config.yml` in GitHub.
3. Set `url`, `baseurl`, title, languages and `unaltraweb.site_profile`.
4. Edit content files in `_pages/`, `_posts/`, `_projects/`, `_chapters/`, `_bibliography/`, `_data/` and `assets/`.
5. Commit to `main`.
6. Run the manual deploy workflow when the site should be published.

This path is enough for small content updates such as adding a bibliography entry, editing a page, updating project data or correcting text.

## Local Docker Editing

Install Git, Docker and GNU Make, then clone the generated site repository:

```bash
git clone https://github.com/YOUR-ORG/YOUR-SITE.git
cd YOUR-SITE
make serve
```

The template uses `ghcr.io/dosquartsdedocs/unaltraweb:main` as its default Docker runtime. The reusable layouts, styles, plugins and scripts still come from the `unaltraweb` gem declared in the site's `Gemfile`.

Use these commands during normal local work:

```bash
make serve
make build
make publish
make test
make down
```

When developing `unaltraweb` and the template together, use this local port convention:

- `unaltraweb`: `4000`.
- `unaltreselfie`: `4001`.
- `unaltreprojecte`: `4002`.
- `unaltremanual`: `4003`.
- `unaltredocs`: `4004`.

Preview another profile locally without changing the published profile in `_config.yml`:

```bash
make serve SITE_PROFILE=unaltremanual
make serve SITE_PROFILE=unaltredocs
```

## Windows

The supported Windows path is WSL2 with Docker Desktop and Docker's WSL integration enabled. Run the same `make` commands inside the WSL Linux shell.

Native PowerShell without WSL2 is not the primary supported path yet.

## Profiles

Select one profile in `_config.yml`:

```yaml
unaltraweb:
  site_profile: unaltreselfie
```

Available profiles are:

- `unaltreselfie`: personal academic or professional site.
- `unaltreprojecte`: research project site.
- `unaltremanual`: manual, course or book-like site.
- `unaltredocs`: documentation site.

The template contains examples for all four profiles. This documentation site is called `unaltraweb`; it is the reference for the platform and uses real examples of supported behavior.

## Core Development

When changing `unaltraweb` and the template side by side, point the template at the local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make serve-allprofiles LOCAL_CORE=../unaltraweb
```

This is for core/theme development, not for normal content editing.
