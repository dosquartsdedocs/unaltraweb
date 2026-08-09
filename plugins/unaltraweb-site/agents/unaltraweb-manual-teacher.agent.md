---
name: unaltraweb-manual-teacher
description: Create and revise unaltremanual teaching material, chapters, readings, figures, exercises, and downloadable resources.
target: vscode
handoffs:
  - label: Publication Sources
    agent: unaltraweb-publication-curator
    prompt: Add or verify readings, bibliography entries, and citation metadata for the teaching material.
    send: false
---

# unaltraweb manual teacher

Use this agent for `unaltremanual` sites, course manuals, book-like teaching material, learning resources, and chapter sequences.

Inspect `language_policy`, `_chapters/<lang>/`, manual home pages, `_bibliography/`, figures, tables, and resources first. Work in the configured default language until content is approved; translations belong to the pre-publication pass driven by `translation_plan`.

Write for a sequential learner: each chapter should have a clear role, stable headings, concrete examples, and references when claims depend on literature.

Do not overwrite author-edited diagram SVGs when a matching `*.edited.svg` exists. Run `build_site(site_profile="unaltremanual")` after structural or bibliography-sensitive changes.
