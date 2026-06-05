---
title: Front matter reference
description: Common front matter keys used by unaltraweb pages and collections.
lang: en
ref: front_matter_reference
profiles: [unaltredocs]
section: Standards
weight: 230
permalink: /front-matter/
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
permalink: /installation/
---
```
