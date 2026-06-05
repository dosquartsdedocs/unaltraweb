---
title: Pages, collections and navigation
description: How editable content becomes navigation and rendered pages.
lang: en
ref: pages_collections_navigation
profiles: [unaltredocs]
section: User guides
weight: 50
permalink: /pages-collections-navigation/
---

Child sites keep navigation pages in `_pages/` and structured entries in collections.

## Navigation Pages

Set `nav: true` to add a page to the top navigation for profiles that use standard nav.

```yaml
---
title: Publications
layout: bib
lang: en
ref: publications
profiles: [unaltreselfie]
feature: publications
nav: true
nav_order: 40
permalink: /en/publications/
---
```

## Profile Filtering

Use `profiles` to keep a multi-profile starter repository without publishing every page in every profile.

```yaml
profiles: [unaltreprojecte]
```

## Feature Flags

Feature flags hide standard sections from navigation without deleting content.

```yaml
unaltraweb:
  features:
    publications: true
    blog: false
```

## Documentation Pages

Documentation pages use the `documentation` collection and a `section` value for the left index.

```yaml
---
title: Install and run locally
section: User guides
weight: 30
---
```
