---
title: Template Role
description: Why unaltraweb-template is the primary integration demo.
lang: en
ref: template_role
profiles: [unaltredocs]
section: Developers
weight: 310
permalink: /template/
---

<p class="lede"><code>unaltraweb-template</code> is the starter repository and integration fixture. It should stay thin, but it is the best place to prove that the gem works for real child sites.</p>

## Why The Template Matters

- It consumes `unaltraweb` as an external dependency.
- It contains realistic demo content for `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs` profiles.
- It owns the local Docker workflow for child sites.
- It uses the shared `ghcr.io/dosquartsdedocs/unaltraweb:main` runtime image by default.
- It runs Playwright smoke tests and screenshots across profiles, themes and responsive layouts.
- It keeps starter-site content out of the reusable core.

The core `docs/` site is different: it is an `unaltredocs`-style documentation site for explaining `unaltraweb` itself. The template is the place where all four profile starters are shown together.

## What Should Stay In The Core

- Shared layouts and includes.
- Sass and static assets that every child site can reuse.
- Jekyll plugins and Liquid helpers.
- Bibliometric, CV and documentation tooling.
- Reusable GitHub Actions workflows.
- The `unaltraweb` reference site under `docs/`.

## What Should Stay In The Template

- Editable `_config.yml` defaults.
- Demo pages, posts, projects, chapters and bibliography records.
- Local `_sass/_site-custom.scss` examples.
- Local Makefile and Docker wrapper for child-site workflows.
- Render smoke tests and screenshots.

## Local Core Validation

```bash
cd ../unaltraweb-template
make build LOCAL_CORE=../unaltraweb
make test LOCAL_CORE=../unaltraweb SITE_PROFILE=unaltreprojecte
```

On constrained machines, prefer `make build` first and run only the profile-specific browser test needed for the change.
