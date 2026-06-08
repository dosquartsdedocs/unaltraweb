---
title: Front Matter Reference
description: Common front matter keys used by unaltraweb pages and collections.
lang: en
ref: front_matter_reference
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Reference
weight: 900
permalink: "/front-matter/"
nav_title: Front Matter
---
Common keys:

| Key | Purpose |
|---|---|
| `layout` | Selects the reusable layout. |
| `title` | Page or document title. |
| `description` | Summary used by cards, search and metadata. |
| `lang` | Content language. |
| `ref` | Stable cross-language identity. |
| `permalink` | Public URL. |
| `profiles` | Profiles where the item is rendered. |
| `feature` | Feature flag controlling navigation. |
| `nav`, `nav_order`, `nav_title` | Top navigation controls. |
| `section`, `weight` | Documentation sidebar controls. |
| `documentation_profiles` | Optional `unaltredocs` reader profiles that should include the page. |
| `introduced_in`, `changed_in`, `deprecated_in`, `removed_in` | Optional version annotations for documentation pages. |
| `hero` | Page or project hero image configuration. |

Example:

```yaml
---
title: Installation
description: Local Docker workflow for contributors.
lang: en
ref: installation
profiles: [unaltredocs]
section: User guides
weight: 30
documentation_profiles: [local-authors]
permalink: /installation/
---
```
