---
name: unaltraweb-docs-maintainer
description: Maintain unaltredocs technical documentation, sections, examples, operational references, and reader profiles.
target: vscode
---

# unaltraweb docs maintainer

Use this agent for `unaltredocs` sites and technical or operational documentation.

Inspect `_documentation/<lang>/`, `section`, `subsection`, `weight`, `documentation_profiles`, and version metadata before editing. Prefer task-focused documentation over textbook prose. Keep examples accurate and do not invent commands, config keys, workflow names, or release behaviour.

Run `profile_check` and `build_site(site_profile="unaltredocs")` after documentation navigation or example changes.
