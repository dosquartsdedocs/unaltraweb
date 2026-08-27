---
title: Frequently Asked Questions
description: Common questions about unaltraweb sites.
lang: en
ref: faq
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Reference
weight: 920
permalink: "/faq/"
nav_title: FAQ
---
## Do content editors need Docker?

No. Small edits can be done in GitHub. Docker is for local preview, tests and larger edits.

## Does a child site need to copy layouts?

No. Layouts, includes, Sass, plugins and scripts should come from the `unaltraweb` gem. Copy files only for deliberate local overrides.

## Why use site profiles?

Profiles choose a real build shape before Jekyll writes the site. They are not client-side previews.

## Can one repository contain all profiles?

The integration template does so it can test every profile. `new_web` creates real sites with one selected profile and only its required content paths.
