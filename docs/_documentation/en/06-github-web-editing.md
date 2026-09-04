---
title: Edit Safely In GitHub Web
description: A browser-only content workflow that prevents overlapping edits and lost work.
lang: en
ref: github_web_editing
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
section: Start Here
weight: 20
permalink: "/github-web-editing/"
nav_title: GitHub Web Editing
---
<p class="lede">GitHub Web is a supported path for small content updates. Editors coordinate through issues, one-task branches, and Draft pull requests; maintainers own local rendering, merge decisions, and manual deployment.</p>

## Before Editing

1. Open or choose an issue describing one focused task.
2. Be assigned to it, or post an explicit reservation naming every file you intend to edit and wait for maintainer acceptance.
3. Check the issue and open pull requests before starting. There must be only one active editor per file.
4. Create one branch for the task. Never edit or commit directly to `main`.
5. Open a Draft pull request early, link the issue, and list the reserved files.

An issue without an assignee or accepted reservation is not a claim on files. A broad reservation such as "all chapters" should be split into smaller tasks before editing begins.

## While Editing

- Change only reserved files and keep the pull request small enough to review as one task.
- Use a separate issue and branch for unrelated corrections, reorganizations, or formatting.
- Recheck the pull request's **Files changed** tab before requesting review.
- Keep the pull request in Draft while files or content are incomplete.
- If GitHub reports a conflict or another editor needs the same file, stop. Do not choose "accept ours/theirs", recreate the file, or overwrite their work. Ask the maintainer to sequence or reconcile the tasks.

This protocol makes overlap visible before work is lost. Chat messages may help coordination, but the issue or reservation and Draft pull request are the repository record.

## Choose The Right Content Paths

The generated site's `README.md` identifies its selected profile and gives the authoritative editor list. Typical paths are:

| Profile | Purpose | Typical editable content |
|---|---|---|
| `unaltreselfie` | Personal academic or professional site | `_pages/<lang>/`, `_posts/`, `_news/`, `_projects/`, `_books/`, `_bibliography/`, approved profile images and CV files |
| `unaltreprojecte` | Research project, group, infrastructure, or output site | `_pages/<lang>/`, `_news/`, `_projects/`, `_outputs/`, `_books/`, `_data/team.yml`, `_data/repositories.yml`, `_bibliography/`, approved project images |
| `unaltremanual` | Manual, course, handbook, or book-like publication | `_pages/<lang>/`, `_chapters/<lang>/`, `_bibliography/`, `context/writing-profile.md`, approved source images |
| `unaltredocs` | Technical or operational documentation | `_pages/<lang>/`, `_documentation/<lang>/`, public `_data/` files, approved screenshots |

A small change to public title, URL, languages, or profile options in `_config.yml` requires maintainer agreement. Do not restructure configuration in a content pull request.

## Upload Images Safely

1. Reserve the new filename and upload it on the task branch, not on `main`.
2. Put it in `assets/img/` or an established editorial image subfolder. Never upload into `assets/img/generated/`.
3. Use a descriptive lowercase filename and prefer a reasonably sized PNG, JPEG, or WebP. Only use SVG from a reviewed, trusted source.
4. Confirm publication rights and check that the file contains no confidential information, unintended personal data, or sensitive metadata.
5. Prefer a new filename. Replace an existing file only when that exact replacement was reserved.
6. Reference the image in the same pull request and add meaningful alternative text. The maintainer must inspect the rendered page.

## Never Edit These In GitHub Web

- `.github/`, `.unaltraweb/`, `.gitignore`, `Gemfile`, `Gemfile.lock`, and `Makefile` control repository or runtime behaviour.
- `_layouts/`, `_includes/`, `_plugins/`, and `_sass/` are technical theme overrides.
- `_site/`, `tmp/`, `.jekyll-cache/`, `.bundle/`, and `vendor/` are build products or caches.
- `assets/img/generated/`, `.unaltraweb/computations.lock.json`, `.vegavisuals.lock.json`, rendered diagrams/captures, and files marked as generated belong to local renderers.
- A generated `.md` owned by a `.qmd`, `.Rmd`, `.R`, `.py`, or `.ipynb` source must not be hand-edited. A maintainer edits and renders the source locally.
- The default manual outputs `assets/pdf/manual-<lang>.pdf` and `assets/img/manual-cover-<lang>.png` are deployment products, not versioned source files.

Never put passwords, access tokens, API keys, private keys, credentials, or `.env` files in issues, commits, branches, or pull requests. Ask the maintainer about any path not explicitly listed as editable.

## Maintainer Handoff

After the editor requests review, the maintainer:

1. Verifies the issue assignment or reservation, task branch, and changed-file scope.
2. Checks out the branch locally and runs the site checks plus every required computation, diagram, visualization, capture, and PDF render.
3. Reviews the rendered web output and, for a manual, the PDF and cover.
4. Resolves any overlap or conflict with the affected editors, then approves and merges the small pull request.
5. Starts deployment manually only after the reviewed change is on `main` and publication is intended.

Pushing a branch or merging to `main` does not publish a generated site. Local checks and renders do not deploy it either.

## unaltremanual Publishing

- `latest` is a manual-only deployment from the reviewed `main` branch.
- A push or merge to `main` does not deploy it. The maintainer runs local checks/renders and then starts the deploy workflow manually.
- When PDF output is enabled, `assets/pdf/manual-<lang>.pdf` and `assets/img/manual-cover-<lang>.png` are generated during deployment and are not versioned. Existing tracked copies need one reviewed `git rm --cached` migration by a maintainer.
- Stable editions use `vYYYY.MM(.N)`: `vYYYY.MM` for the first edition in a month and `vYYYY.MM.N` for an additional edition. They are deferred to explicit releases, and deploying `latest` does not create one.
- The release selector and channel are visible in the generated manual home, `manual-release.json`, and PDF editorial metadata.
- Release checks reject `legacy/` or `sandbox/` material if it appears in the generated site. Keep it outside current manual content paths.
