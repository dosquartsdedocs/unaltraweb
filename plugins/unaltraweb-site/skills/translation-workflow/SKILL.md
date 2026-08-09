---
name: translation-workflow
description: Use when editing multilingual unaltraweb content, deciding whether translations are ready, or preparing localization before publication.
---

# translation workflow

Before editing multilingual content, inspect `language_policy` when the MCP is available. The configured default language is the source of truth for drafting and review.

Rules:

- Draft and revise meaningful content in the default language first.
- Track editorial state with `content_status`, usually `draft`, `review`, or `approved`.
- Translate only default-language content whose status is approved.
- Keep `ref` stable across localized versions and set each file's `lang` explicitly.
- Preserve citations, bibliography keys, figure paths, table IDs, code blocks, data field names, permalinks, and resource URLs unless there is a clear reason to localize visible prose.
- Use `translation_plan` before publication to find missing, existing, and blocked translations.

For stale translations, prefer marking `translation_status: needs_review` or reporting the affected files instead of silently rewriting every language during a default-language edit.
