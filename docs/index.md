---
title: Overview
description: Public documentation and compact demo for the unaltraweb core.
permalink: /
---

# unaltraweb core

<p class="lede"><code>unaltraweb</code> is a reusable Jekyll core for academic, research project, software and documentation websites. It centralizes shared layouts, includes, Sass, plugins, multilingual behaviour, theme modes, bibliometric tooling and reusable deployment workflows.</p>

This `docs/` site is intentionally compact. It documents and demonstrates the core platform. The full starter demo and integration tests live in `unaltraweb-template`, where the gem is consumed like a real child site.

## What Lives Here

<div class="cards">
  <section class="card">
    <h3>Core Concepts</h3>
    <p>Site profiles, feature flags, reusable layouts, theme modes and static build rules.</p>
  </section>
  <section class="card">
    <h3>Distribution</h3>
    <p>The split between reusable core code and thin child repositories.</p>
  </section>
  <section class="card">
    <h3>Development Notes</h3>
    <p>How to validate the core directly and through the companion template.</p>
  </section>
</div>

## Primary Repositories

- Core: `dosquartsdedocs/unaltraweb`.
- Starter and integration fixture: `dosquartsdedocs/unaltraweb-template`.

## Read Next

- [Site profiles](profiles/) explains the prepared website families.
- [Template role](template/) explains why most demo content belongs in the template.
- [Development](development/) lists the lightweight and heavyweight checks.
- [Distribution model](distribution/) documents the core/template update model.
- [Customization](https://github.com/dosquartsdedocs/unaltraweb/blob/main/docs/customization.md) contains the detailed core customization reference.
- [Bibliometrics](bibliometrics/) documents the static metrics pipeline.
