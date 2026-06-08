---
title: Build A Documentation Portal With unaltredocs
description: Technical documentation portals.
lang: en
ref: profile_unaltredocs
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Build A Site
weight: 260
permalink: "/profiles/unaltredocs/"
nav_title: Documentation Portal
---
Use `unaltredocs` for documentation portals with a left index, search, section cards and operational references.

```yaml
unaltraweb:
  site_profile: unaltredocs
  documentation:
    collection: documentation
```

Typical content:

- A documentation home document with `layout: documentation-home`.
- Documents under `_documentation/<lang>/`.
- `section`, `subsection` and `weight` front matter to build the documentation navigation.
- Optional documentation profile metadata with `documentation_profiles`.
- Optional multilingual home pages and documents.

This `unaltraweb` site is itself built with the `unaltredocs` profile.

## Documentation Profiles

`unaltredocs` can expose a small set of reader profiles as a dropdown at the top of the table of contents. Define the profile choices in site config:

```yaml
unaltraweb:
  documentation:
    profiles:
      - id: local-authors
        label: Local authors
      - id: core-developers
        label: Core developers
```

Then tag pages that belong mainly to one of those profiles:

```yaml
---
title: Installation
section: User guide
weight: 20
documentation_profiles: [local-authors]
---
```

The selected profile is stored in `localStorage` and mirrored to the `doc_profile` query parameter, so profile views can be shared. The first dropdown option shows all documentation. Pages without `documentation_profiles` remain visible for every profile.

Direct page links remain available even if the active profile would normally hide that page from navigation. In that case the page shows a short notice instead of hiding the content.

## Reading Model

`unaltredocs` is not a book. Previous/next links are disabled by default because operational documentation is usually task, reference and troubleshooting oriented. If a documentation site needs a linear path, set:

```yaml
unaltraweb:
  documentation:
    previous_next: true
```

For full manuals, courses or books, prefer `unaltremanual`.

## Version Metadata

Version labels can be recorded in front matter before a site needs full versioned builds:

```yaml
introduced_in: "0.4"
changed_in: "0.6"
deprecated_in:
removed_in:
```

Use these keys to annotate when a page or feature changed. Separate `/latest/`, `/stable/` or `/v1.0/` documentation trees should only be added when a project needs complete historical documentation.
