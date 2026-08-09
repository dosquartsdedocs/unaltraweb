---
name: profile-contract
description: Use when checking or editing unaltraweb profile-specific content, front matter, navigation, collection structure, or feature flags.
---

# profile contract

Before editing, identify `unaltraweb.site_profile` and enabled features. Use `profile_check` and `content_inventory` when the MCP is available.

For newly initialized starter sites, use `profile_prune_plan` to review out-of-profile content. Destructive pruning requires explicit approval and `profile_prune(dry_run=false, confirm_prune=true)`.

Profile focus:

- `unaltreselfie`: author config, profile pages, posts/news, projects, bibliography, CV assets.
- `unaltreprojecte`: pages, outputs, team data, repositories, resources, publications, news.
- `unaltremanual`: chapters, manual home, teaching blocks, readings, figures, tables, manual bibliography.
- `unaltredocs`: documentation collection, section/subsection/weight, documentation profiles, examples.

Preserve front matter keys that control routing and cross-language identity: `lang`, `ref`, `permalink`, `profiles`, `feature`, `nav`, `section`, `subsection`, and `weight`.
