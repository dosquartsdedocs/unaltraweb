# unaltraweb site agent plugin

This plugin bundles reusable agent roles and skills for `unaltraweb` website workspaces. It complements the stdio MCP server declared by `mcp-factory.yml`; client registration is normally handled by ContExt or another MCP factory manager.

Agent roles:

- `unaltraweb-bootstrap`: initialize a new website workspace from a starter template.
- `unaltraweb-site-editor`: general content and navigation edits.
- `unaltraweb-manual-teacher`: teaching manuals, chapters, readings, exercises, and resources.
- `unaltraweb-manual-style-reviewer`: paragraph-function, argument-structure, scientific-technical, pedagogical, and component-choice review for teaching manuals.
- `unaltraweb-docs-maintainer`: technical and operational documentation.
- `unaltraweb-project-communicator`: research project pages, outputs, team, repositories, and news.
- `unaltraweb-publication-curator`: bibliography and bibliometrics workflow.
- `unaltraweb-personal-profile-editor`: personal academic/profile sites, CV material, highlights, and selected publications.
- `unaltraweb-translation-editor`: pre-publication localization from approved default-language content.

Bundled skills cover profile contracts, starter initialization, conservative profile pruning, language/translation workflow, bibliography curation, bibliometrics maintenance, and manual pedagogical writing. The MCP exposes the active component catalogue through `manual_authoring_capabilities` and `web://manual-authoring-components`. Local site repositories should still keep their own `AGENTS.md` and `context/writing-profile.md` when they have project-specific editorial rules.
