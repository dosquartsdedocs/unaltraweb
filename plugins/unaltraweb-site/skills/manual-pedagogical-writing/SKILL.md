---
name: manual-pedagogical-writing
description: Use when drafting, revising, or auditing unaltremanual course-manual prose for scientific-technical clarity, pedagogical sequence, and author-specific narrative style.
---

# manual pedagogical writing

Before drafting, read the site's local `AGENTS.md` and, when present, `context/writing-profile.md`. Treat those local files as the source of truth for voice, terminology, teaching constraints, language policy, and approval workflow.

Write manuals as teaching texts, not as landing pages or executive summaries. Prefer connected explanatory paragraphs that help a student understand why a concept, dataset, tool operation, or assessment criterion matters. Use bullet lists for procedural steps, rubrics, inventories, or short checks, but do not let bullets replace the conceptual development of a section.

Keep visual material in the manual system. Every teaching table must be wrapped in a captioned `::: table "Caption"` block. Every figure should have a caption, normally through the Markdown image title or the include's `caption` parameter. Use versioned diagram sources rendered through `diavisuals`; do not use inline Mermaid or PlantUML fences for reusable manual figures. For folder and file structures, prefer PlantUML `@startfiles` sources.

For each section, prefer this pedagogical order:

1. Name the learning problem or phase of work.
2. Connect it to the course context and the student's expected task.
3. Introduce the scientific, technical, or methodological concept needed for the decision.
4. Explain the practical action with data, software, figures, maps, or written synthesis.
5. State how quality will be recognised or assessed.
6. End with a clear handoff to the next activity or chapter.

When reviewing, diagnose paragraph function before sentence polishing. Assign each paragraph one main role: orientation, concept, technical decision, worked example, practical instruction, assessment criterion, limitation, warning, or transition. Rewrite paragraphs that only summarise, advertise, or list disconnected ideas.

Keep claims bounded. Do not invent teaching-guide content, dates, assessment weights, datasets, learning outcomes, or official policies. Mark uncertain official-course claims for author verification and keep Moodle-specific deadlines, announcements, and grading operations out of the manual unless the author explicitly asks for a stable policy to be published.

For visible content changes, build or serve the manual and wait for the human author to approve the rendered browser preview before committing or publishing.
