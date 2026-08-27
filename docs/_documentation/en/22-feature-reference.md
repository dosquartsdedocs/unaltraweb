---
title: Feature Reference
description: Map of reusable unaltraweb features, syntax and examples.
lang: en
ref: feature_reference
profiles:
- unaltredocs
documentation_profiles:
- site-designers
- contributors
- core-developers
section: Design And Customize
weight: 340
permalink: "/features/"
nav_title: Feature Reference
---
<p class="lede">This page maps reusable <code>unaltraweb</code> features to the documentation pages and template examples that demonstrate them.</p>

The companion `unaltraweb-template` repository contains full-profile demos because it exercises the core as a real child site. This site is the `unaltraweb` reference: it explains the platform and shows the syntax users should copy.

## Covered Now

- **Profiles**: `unaltreselfie`, `unaltreprojecte`, `unaltremanual` and `unaltredocs` are documented conceptually.
- **Distribution**: gem, Docker image, template repository and reusable workflow responsibilities are documented.
- **Customization**: local Sass, layouts, feature gates, manual syntax, project resources, CV previews, theme modes and developer mode have starter examples.

## Feature Map

| Feature | Where documented | Where demonstrated |
|---|---|---|
| Profiles and feature flags | [Profiles]({{ '/profiles/' | relative_url }}), [Usage]({{ '/usage/' | relative_url }}) | Template home pages and localized navigation |
| Tools and local runtime | [Tools]({{ '/tools/' | relative_url }}), [Quick Start]({{ '/quick-start/' | relative_url }}) | Template Makefile and Docker Compose files |
| Callouts, figures, tables and Mermaid | [Syntax]({{ '/syntax/' | relative_url }}), [Customization]({{ '/customization/' | relative_url }}) | Template manual and project resource pages |
| Theme modes | [Themes]({{ '/themes/' | relative_url }}) | Template Playwright screenshots for light, coffee and dark modes |
| Bibliometrics | [Bibliometrics]({{ '/bibliometrics/' | relative_url }}) | Template publications pages and metrics workflow wrapper |
| Deployment and updates | [Distribution]({{ '/distribution/' | relative_url }}), [Development]({{ '/development/' | relative_url }}) | Reusable workflows and Dependabot configuration |

## Still To Complete

- Add rendered examples for every syntax item above inside this `unaltraweb` reference site.
- Add a compact front matter reference for pages, posts, projects, chapters, documentation pages, outputs, books, theses and bibliography entries.
- Add a data-file reference for `_data/` files used by team, repositories, metrics, readings and profile-specific pages.
- Add profile-specific checklists for creating real sites from the template.
- Add screenshots or visual examples for the four profiles without duplicating the full template demo.
- Keep future `keep`/`sync` behavior separate from the existing offline distribution `doctor`; document migrations only when those commands exist.
- Expand manual/PDF guidance once printable manual output becomes a first-class target.

## Where To Look Today

- [Customization](../customization/) contains most current syntax examples.
- [Content syntax](../syntax/) contains copyable examples for syntax beyond standard Markdown.
- [Themes](../themes/) documents theme modes and local CSS/JS integration.
- [Site profiles](../profiles/) documents the four prepared website families.
- [Quick start](../quick-start/) covers GitHub-only and local Docker workflows.
- [Distribution model](../distribution/) explains gem, Docker and template responsibilities.
- `unaltraweb-template` contains the current full-profile demo content and Playwright screenshots.
