---
title: FAQ
description: Common questions about unaltraweb sites.
lang: en
ref: faq
profiles: [unaltredocs]
section: FAQs
weight: 500
permalink: /faq/
---

## Do content editors need Docker?

No. Small edits can be done in GitHub. Docker is for local preview, tests and larger edits.

## Does a child site need to copy layouts?

No. Layouts, includes, Sass, plugins and scripts should come from the `unaltraweb` gem. Copy files only for deliberate local overrides.

## Why use site profiles?

Profiles choose a real build shape before Jekyll writes the site. They are not client-side previews.

## Can one repository contain all profiles?

The template does, because it is a starter and integration fixture. Real sites should normally keep one published profile and only the content they need.
