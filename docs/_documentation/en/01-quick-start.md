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
<p class="lede">Create a clean profile-specific site with the package-owned <code>new_web</code> operation. Its generated README starts with the GitHub Web workflow for content editors; maintainers use local Docker for previews, checks, and renders.</p>

## Choose A Path

- **Local Docker**: requires Git, Docker and Make. Good for previewing the site, larger edits, validation, and rendered-output review.
- **GitHub-only**: no local setup. Good for editing pages, posts, bibliography records, project data and small configuration changes; deployment is manual.

## GitHub-only Editing

1. Push a site created by `new_web` to a new repository.
2. Read its generated `README.md` to confirm the selected profile, editable paths, image rules, and paths that must not be changed in GitHub Web.
3. Open an issue and get assigned, or make an explicit file reservation and wait for maintainer acceptance. Only one active editor works on a file.
4. Create one branch for the task and never edit `main` directly.
5. Make a small content change in the profile-appropriate paths and open a Draft pull request linked to the issue.
6. If a conflict appears, stop and ask the maintainer rather than overwriting work.
7. The maintainer checks the branch locally, runs required renders, reviews the result, and merges it.
8. The maintainer runs the manual deploy workflow only when the reviewed `main` branch should be published.

This path is enough for small content updates such as adding a bibliography entry, editing a page, updating project data or correcting text. The detailed protocol is in [Edit Safely In GitHub Web](../github-web-editing/).

## Local Docker Editing

For an agent-first IDE session, create or select an empty Git repository, open that directory as the workspace, register the `unaltraweb` factory, and restart the IDE so `${workspaceFolder}` is used as the confined consumer root. Then call `new_web`; the generated `AGENTS.md` is the durable local contract for subsequent agents.

Create the site through the MCP, the installed package CLI, or this factory checkout:

```bash
unaltraweb-mcp --project ./my-site new-web --site-profile unaltreselfie --title "My site" --default-lang en
# or: MCP_CONSUMER_WORKSPACE=./my-site make mcp-new-web NEW_WEB_PROFILE=unaltreselfie SITE_TITLE="My site" DEFAULT_LANG=en
```

The scaffold is bundled with the Python package and MCP image. Creation aborts before writing when a managed path is a symlink or a differing file already exists. A manual also receives a default-language chapter directory, computation source/output roots, `README.md`, `AGENTS.md`, and a package baseline for conservative runtime updates. After pushing the generated site, install Git, Docker and GNU Make, then clone it normally:

```bash
git clone https://github.com/YOUR-ORG/YOUR-SITE.git
cd YOUR-SITE
make serve
```

The reusable layouts, styles, plugins and scripts come from the `unaltraweb` gem declared in the site's `Gemfile`. The selected MCP image provides the normal containerized build runtime. When working against an unpublished core candidate, build that image explicitly in the factory checkout first; a generated site reports this remediation instead of silently falling back to another version.

Use these commands during normal local work:

```bash
make serve
make build
make test
make down
```

The generated GitHub Actions workflow publishes to Pages only when a maintainer starts it manually. A push, local build, or local render does not deploy the site.

When developing `unaltraweb` and the template together, use this local port convention:

- `unaltraweb`: `4000`.
- `unaltreselfie`: `4001`.
- `unaltreprojecte`: `4002`.
- `unaltremanual`: `4003`.
- `unaltredocs`: `4004`.

Each generated repository has one profile-specific scaffold. Create a separate temporary site when comparing another profile instead of mixing profile content into the published repository.

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

`new_web` provides a separate clean scaffold for every profile. The optional `unaltraweb-template` fixture contains richer examples for all four profiles. This documentation site is called `unaltraweb`; it is the reference for the platform and uses real examples of supported behavior.

## Core Development

When changing `unaltraweb` and the template side by side, point the template at the local core checkout:

```bash
make serve LOCAL_CORE=../unaltraweb
make build LOCAL_CORE=../unaltraweb
make serve-allprofiles LOCAL_CORE=../unaltraweb
```

This is for core/theme development, not for normal content editing.
