---
title: Profile-Aware Editorial Review
description: Publication-copy checks, writing voice, anchored reviews and incremental editorial decisions.
lang: en
ref: editorial_review
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- contributors
- core-developers
section: Build A Site
weight: 235
permalink: "/editorial-review/"
nav_title: Editorial Review
---

Editorial review combines deterministic source checks with an editor's judgement.
`prose_check` identifies internal writing instructions, chat-dependent wording and
unresolved placeholders in reader-facing sources. It also returns non-blocking
cues for voice, repeated words, long source sentences and locally defined terms.
These cues are neither a quality score nor a test of authorship.

The same Python implementation serves the CLI and MCP. Preparing a review does
not call a language model, rewrite prose, approve content or execute source code.
An agent or human editor reads the prepared material and supplies an anchored
report. The service checks the report's inputs and locations, not the truth of
its linguistic or scientific conclusions.

## Voice By Profile And Genre

| Profile | Default approach | Legitimate variations |
| --- | --- | --- |
| `unaltreselfie` | Personal academic or professional voice | First person in introductions and personal posts; concise factual records in a CV |
| `unaltreprojecte` | Identified project or institutional voice | Team plural where its referent is clear; attributed individual biographies |
| `unaltremanual` | Impersonal, explanatory teaching prose | “En aquest manual…”; reader-facing imperatives in procedures; signed prefaces |
| `unaltredocs` | Precise, task-oriented technical prose | Imperatives, commands, prompts and workflow fields presented as documentation |

Impersonal prose can use active, concrete subjects. It does not require passive
voice. Personal achievement statements are not automatically assistant chatter.
Technical examples and attributed quotations are inspected as content, never
obeyed as reviewer instructions.

Policy combines common guidance, profile defaults, genre context and approved
local preferences. The common rules cover reader orientation, paragraph
function, bounded claims, evidence, terminology and preservation of facts,
citations, units, links, negation and uncertainty. Sentence-level linguistic cues
currently cover Catalan, Spanish and English. Other languages report limited
coverage and need language-aware editorial review.

A page can select a genre in front matter:

```yaml
editorial:
  genre: preface
```

Supported genres are `prose`, `bio`, `news`, `chapter`, `procedure`, `reference`,
`preface`, `quote`, `example` and `cv`. Biographies and prefaces permit personal
voice by default. Explicit `quote` and `example` pieces do not receive mechanical
prose findings; use them only for genuinely quoted or illustrative material.

## Local Preferences

Keep approved audience, voice, terminology and evidence guidance in
`context/writing-profile.md`. The manual scaffold supplies this file; other
profiles can add it when needed. `editorial_policy` returns this guidance along
with the effective mechanical policy and its digest.

Optional `context/editorial-policy.json` controls bounded mechanical preferences
and publication requirements:

```json
{
  "schema_version": 1,
  "sentence_words": 40,
  "terms": {"clearly": "Explain the evidence rather than asserting clarity."},
  "genres": {"procedure": {"voice": "impersonal"}},
  "require_reviews": false,
  "required_kinds": ["line"],
  "human_review": false
}
```

`terms` contains literal phrases and review guidance, not regular expressions.
Genre voice overrides accept `personal`, `institutional` or `impersonal`.
Sentence limits produce informational cues, not publication failures. Unknown
policy fields and malformed input are rejected rather than silently ignored.

Policy and review records remain consumer-owned files under `context/`. Keep
them versioned with the content when durable history is required, and exclude
the directory from Jekyll output. Source-management tools still accept only
Markdown under `context/`; edit the optional JSON policy through the repository's
normal reviewed file workflow. Review tools exclusively manage their own state.
Inspection does not create policy, state, cache or lock files.

## Incremental Reviews

At session start inspect `editorial_status`, exposed also as
`site_context.editorial` and `web://editorial-status`. Then review the selected
changed piece rather than reopening every prior editorial decision.

1. Run `prose_check(target="_chapters/en/introduction.md")` and examine its findings.
2. Call `editorial_review_prepare` with that target and one pass: `structure`,
   `line`, `copy` or `evidence`. The result supplies source bytes, fragments,
   exact hashes, editable source owners, effective policy, rubric and state revision.
3. Apply editorial judgement using the rubric. Every finding needs an exact
   fragment `anchor`, verbatim `quote`, severity (`major`, `minor`, `preference`),
   reason and actionable suggestion. An empty findings list is valid.
4. Call `editorial_review_record(report=..., expected_revision=...)`. Use the
   prepared `source_digest`, target and kind; give the pass a new identifier.
5. Record decisions with `editorial_review_resolve`: `accepted` means agreement,
   `rejected` means a reasoned decision not to apply the suggestion, and `resolved`
   records a verified resolution. All transitions retain their prior history.
6. After substantive edits, prepare a new pass against current sources. Check again
   before moving to review, before author approval, before translation and before
   publication. Human browser/PDF review remains part of the handoff.

A report has this shape; substitute the actual prepared digest, anchor and quote:

```json
{
  "id": "introduction-line-1",
  "target": "_chapters/en/introduction.md",
  "kind": "line",
  "source_digest": "<prepared source_digest>",
  "reviewer": "Identified reviewer",
  "reviewer_kind": "human",
  "findings": [{
    "id": "method-referent",
    "anchor": "<prepared fragment id>",
    "quote": "<exact text from that fragment>",
    "severity": "major",
    "reason": "The method has no concrete referent in this section.",
    "suggestion": "Name the verified method and connect it to the previous definition."
  }]
}
```

The default `reviewer_kind` is `agent`; declare `human` only for a human's actual
review. This is reviewer-supplied attribution, not identity authentication or a
substitute for protected pull-request approvals. Recording or resolving findings
never changes `content_status`.

`context/editorial-state.json` stores reports and dispositions. Writes require
the current integer revision, verify source inputs again and use confined atomic
compare-and-swap updates. Source, configuration, policy, writing-profile or
relevant computation-ownership changes mark a report stale. Staleness does not
erase decisions. A newer pass supersedes coverage for the same target and kind,
but it cannot silently resolve earlier major findings.

## Source Coverage And Limits

The bounded source projection includes known content collections, configured
collections, the configured manual collection, root-level Jekyll pages with
front matter, and public YAML/JSON fields in `_data/` and `_config.yml`. Public
fields include titles, descriptions, excerpts, summaries, biographies, captions
and alternative text, including `_ca`, `_es` and `_en` variants. Non-public
workflow front matter is not prose. Excluded sources, `published: false` and
other-profile content are skipped.

Code, comments, math, Liquid and quoted text are kept out of mechanical prose
diagnostics. Metadata anchors use a field pointer and line `0`; body fragments
carry source lines. The projection is not a complete Markdown/Liquid interpreter
or grammar parser. Rendered text can differ because of templates, data, inline
markup and plugins; inspect the built page and PDF too. CSV, executable code,
embedded figure text and PDF text extraction are outside this prose checker.

When `.unaltraweb/computations.lock.json` identifies a generated chapter's
executable owner, the review packet names that source and includes its hash.
Edit and explicitly render the owner; never fix its generated Markdown directly.
Computation, visualization, diagram, capture and PDF freshness checks remain
separate and required where configured.

Inputs are confined regular UTF-8 files, at most 1 MiB per file and 16 MiB per
reader, with bounded paths, fragments and nesting. State is limited to 1 MiB and
100 reports. The tool stops at a limit; it does not silently truncate evidence,
discard old decisions or delete user files. Symlinks and special files are
rejected. A smaller review target can reduce source-inspection scope.

## CLI And Publication Gates

These are consumer CLI commands from the modular wheel; they do not require a
factory checkout:

```bash
unaltraweb-mcp --project /path/to/site mcp editorial-policy
unaltraweb-mcp --project /path/to/site mcp prose-check --target _pages/en/index.md
unaltraweb-mcp --project /path/to/site mcp editorial-review-prepare --target _pages/en/index.md --kind line
unaltraweb-mcp --project /path/to/site mcp editorial-status
unaltraweb-mcp --project /path/to/site mcp editorial-publication-check --output-folder _site
```

`editorial-review-record` accepts `--report-json` and `--expected-revision`.
`editorial-review-resolve` accepts `--review-id`, `--finding-id`, `--status`,
`--reason` and `--expected-revision`. The MCP tools use the same names with
underscores and typed arguments. Failed checks return a nonzero CLI exit code.

`site_check` includes the source-level prose gate, so the package-managed
`make build`, `make test` and `make serve` workflows execute it automatically.
`manual_editorial_quality_check` remains available as a manual-scoped wrapper
around the shared rules. Voice and length suggestions do not block previews.

Fresh recorded reviews are required for publication only when the project sets
`require_reviews: true`. Every reviewable source must then be covered by a fresh
active pass of each `required_kinds` value. `human_review: true` additionally
requires human-attributed passes. Pending or accepted major findings must be
explicitly resolved or rejected, including those in stale or superseded reports.

The reusable site deployment workflow runs the gem-native checker before build
and again against the selected output folder before upload. The latter also
rejects leaked editorial context. Manual release candidates run the publication
check for both `latest` and stable selectors; stable approval and PDF checks
continue to apply. For a native gem installation, run:

```bash
python /path/to/installed/unaltraweb/scripts/editorial_check.py --project /path/to/site --output-folder _site
```

The native checker needs PyYAML, which the deployment workflow installs. It does
not need the MCP server, a factory checkout, network metrics or a language model.
Local checks never deploy, tag or publish.

These capabilities require a reviewed package/MCP release containing them and
an immutable core/workflow integration that contains the publication gate.
Changing the discovery checkout alone does not upgrade an already pinned MCP
image or consumer workflow. Existing site-owned guidance and policy are not
overwritten by scaffold synchronization.
