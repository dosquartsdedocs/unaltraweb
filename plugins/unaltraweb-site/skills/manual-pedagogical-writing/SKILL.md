---
name: manual-pedagogical-writing
description: Use when drafting, revising, or auditing unaltremanual course-manual prose for scientific-technical clarity, pedagogical sequence, and author-specific narrative style.
---

# manual pedagogical writing

Before drafting, read the site's local `AGENTS.md`, `manual_authoring_capabilities`, and, when present, `context/writing-profile.md`. Treat local files as the source of truth for voice, terminology, teaching constraints, language policy, and approval workflow; treat the capability catalogue as the source of truth for component syntax and web/PDF support.

Write manuals as teaching texts, not as landing pages or executive summaries. Prefer connected explanatory paragraphs that help a student understand why a concept, dataset, tool operation, or assessment criterion matters. Use bullet lists for procedural steps, rubrics, inventories, or short checks, but do not let bullets replace the conceptual development of a section.

Develop paragraphs with an argument rather than a sequence of assertions. When appropriate, move from topic or reader goal to problem or question, arguments with evidence or examples, discussion of meaning or limits, and a concrete closure or transition. Do not force every move into every paragraph: assign one primary job, improve logic before sentence style, and introduce an example only after its purpose is clear.

Use `##` and `###` for conceptual divisions exposed in the secondary chapter TOC. Use `####` for a cohesive numbered local subsection that should remain out of that TOC, such as a developed source, case, example, or operation. Do not create headings merely to style each short item. Never imitate an `h4` with a standalone bold label and terminal period; a genuine bold run-in stays in the same paragraph as its explanation.

Write only publishable reader-facing body prose. Do not mention the user, their instructions, the assistant, chat history, drafting plans, approval or translation state, internal metadata fields, TODOs, placeholders, or notes to authors and agents. Keep editorial discussion in review output or project context files, never in pages or chapters.

Keep visual material in the manual system. Use definition lists for compact terminology and caption every teaching table and figure. Treat `::: subfigures` as a high-value comparison device for before/after states, controlled alternatives, short sequences, or complementary views that the reader must inspect together. Prefer compact layouts such as `a+b` or `a+b/c`, give the set one explanatory caption and each panel a specific caption, and use the device selectively so it retains emphasis. Do not group images merely because they share a topic or stack consecutive multi-panel blocks when separate figures would read more clearly. Use versioned diagram sources rendered through `diavisuals`; do not use inline Mermaid or PlantUML fences for reusable manual figures. For folder and file structures, prefer PlantUML `@startfiles` sources. Check `manual_authoring_capabilities` before introducing web-only components into a PDF-enabled manual.

Use nested Markdown blockquotes selectively for teaching callouts: `>>` note or tip, `>>>` worked example, `>>>>` warning, `>>>>>` learning objectives, and `>>>>>>` caution or danger. Reserve them for a genuine change of function, such as a concrete operational risk, and do not use consecutive colored boxes as a substitute for explanatory prose.

For each section, prefer this pedagogical order:

1. Name the learning problem or phase of work.
2. Connect it to the course context and the student's expected task.
3. Introduce the scientific, technical, or methodological concept needed for the decision.
4. Explain the practical action with data, software, figures, maps, or written synthesis.
5. State how quality will be recognised or assessed.
6. End with a clear handoff to the next activity or chapter.

When reviewing, diagnose paragraph function before sentence polishing. Assign each paragraph one main role: orientation, concept, technical decision, worked example, practical instruction, assessment criterion, limitation, warning, or transition. Rewrite paragraphs that only summarise, advertise, or list disconnected ideas. Check spelling, grammar, terminology, factual precision, citations, cross-references, and captions, then run `manual_editorial_quality_check`.

Keep claims bounded. Do not invent teaching-guide content, dates, assessment weights, datasets, learning outcomes, or official policies. Mark uncertain official-course claims for author verification and keep Moodle-specific deadlines, announcements, and grading operations out of the manual unless the author explicitly asks for a stable policy to be published.

For visible content changes, build or serve the manual and wait for the human author to approve the rendered browser preview before committing or publishing.
