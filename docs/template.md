---
title: Template Role
description: Why unaltraweb-template is the primary integration demo.
permalink: /template/
---

# Template role

<p class="lede"><code>unaltraweb-template</code> is the starter repository and integration fixture. It should stay thin, but it is the best place to prove that the gem works for real child sites.</p>

## Why The Template Matters

- It consumes `unaltraweb` as an external dependency.
- It contains realistic demo content for `unaltreselfie`, `unaltreprojecte` and `unaltremanual` profiles.
- It owns the local Docker workflow for child sites.
- It runs Playwright smoke tests and screenshots across profiles, themes and responsive layouts.
- It keeps starter-site content out of the reusable core.

## What Should Stay In The Core

- Shared layouts and includes.
- Sass and static assets that every child site can reuse.
- Jekyll plugins and Liquid helpers.
- Bibliometric, CV and documentation tooling.
- Reusable GitHub Actions workflows.
- Conceptual documentation and the compact core docs/demo site.

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
