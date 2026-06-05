---
title: unaltredocs profile
description: Technical documentation portals.
lang: en
ref: profile_unaltredocs
profiles: [unaltredocs]
section: Profiles
weight: 140
permalink: /profiles/unaltredocs/
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
- Optional multilingual home pages and documents.

This `unaltraweb` site is itself built with the `unaltredocs` profile.
