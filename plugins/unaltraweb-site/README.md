# unaltraweb site agent plugin

This plugin bundles reusable agent roles and skills for `unaltraweb` website workspaces. It complements the stdio MCP server declared by `mcp-factory.yml`; client registration is normally handled by ContExt or another MCP factory manager.

Agent roles:

- `unaltraweb-bootstrap`: create a new website workspace from a package-owned profile scaffold.
- `unaltraweb-site-editor`: general content and navigation edits.
- `unaltraweb-manual-teacher`: teaching manuals, chapters, readings, exercises, and resources.
- `unaltraweb-manual-style-reviewer`: paragraph-function, argument-structure, scientific-technical, pedagogical, and component-choice review for teaching manuals.
- `unaltraweb-docs-maintainer`: technical and operational documentation.
- `unaltraweb-project-communicator`: research project pages, outputs, team, repositories, and news.
- `unaltraweb-publication-curator`: bibliography and bibliometrics workflow.
- `unaltraweb-personal-profile-editor`: personal academic/profile sites, CV material, highlights, and selected publications.
- `unaltraweb-translation-editor`: pre-publication localization from approved default-language content.

Bundled skills cover profile contracts, package-owned site creation, conservative profile pruning for legacy mixed-profile sites, language/translation workflow, bibliography curation, bibliometrics maintenance, and manual pedagogical writing. The MCP exposes the active component catalogue through `manual_authoring_capabilities` and `web://manual-authoring-components`. The `unaltremanual` scaffold includes a default `context/writing-profile.md`; local sites should revise it and add their own `AGENTS.md` when they have project-specific editorial rules.
