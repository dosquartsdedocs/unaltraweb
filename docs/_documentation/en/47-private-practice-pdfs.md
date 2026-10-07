---
title: Private Practice PDFs
description: Build landscape practice readings with shared manual typography, course metadata and retained private outputs.
lang: en
ref: private_practice_pdfs
profiles:
- unaltredocs
documentation_profiles:
- core-developers
section: Core Development
weight: 665
permalink: "/private-practice-pdfs/"
nav_title: Practice PDFs
---

The `manual_practice_pdf_build` tool creates a private A4-landscape reading from
one Markdown source. It uses the manual's typography and site metadata, including
the course name, degree, instructors and configured logos. The first page includes
the course codes in parentheses beside the subject and the practice version.
The academic year is omitted. Logos appear only on the first page.

## Prepare a reading

Keep editable sources in the manual repository:

```text
practiques/accessibility/ca/alumnat/LLEGIU-ME.md
practiques/accessibility/ca/docent/LLEGIU-ME.md
```

Use `LEEME.md` for Spanish and `README.md` for English. The language must be
enabled in the site configuration. `alumnat` and `docent` identify separate
readings; the tool does not infer or produce a teacher solution.

```markdown
---
title: Compare two routes
lang: en
content_status: draft
---

# Open the project

1. Open the prepared project.
2. Compare the routes between the same origin and destination.

![The two routes on the same map](assets/img/routes.png "Open and closed crossing scenarios")

| Scenario | Crossing |
| --- | --- |
| Open | Available |
| Closed | Unavailable |

Table: Conditions used in each scenario.
```

The initial reading format supports ordinary Pandoc Markdown, links, maths,
fenced code, captioned tables and standalone PNG, JPEG or PDF images. Image paths
are project-relative, with a fallback to the source directory. Absolute paths,
parent traversal, symlinks and remote images are rejected. Render other visual
formats through their owning provider and select a printable output first.
Liquid, manual-only component wrappers and automatic bibliography assembly are
not part of this standalone reading format.

Figures keep their original proportions and fit the usable page automatically.
Their captions are measured before allocating image height. A complete figure
moves to the next page when it cannot fit; it is not reduced to fill a small
space at the bottom. Tables are centred, with repeated headers and captions on
continued pages. Review long tables and dense screenshots at the intended size.

## Keep the material private

Merge these entries into the existing `exclude` list in `_config.yml`:

```yaml
exclude:
  - practiques/
  - sandbox/
  - dist/
```

Keep the existing exclusions. Add `sandbox/practiques/` and `dist/practiques/`
to `.gitignore` if broader rules do not already cover them. Version the editable
practice sources. Git ignore rules do not exclude files from Jekyll by themselves.
The profile check rejects missing web exclusions when practice sources exist.

## Build with MCP or the CLI

Use a runtime whose tool inventory advertises `manual_practice_pdf_build`.
Existing connections keep their loaded code until the client reconnects to an
updated runtime. Prepare the selected PDF image explicitly before the first run.

```text
manual_practice_pdf_build(
  source="practiques/accessibility/en/alumnat/README.md",
  version="2026-10-r1"
)
```

The equivalent factory-backed CLI command is:

```bash
unaltraweb-mcp --project "$PWD" mcp manual-practice-pdf-build \
  --source practiques/accessibility/en/alumnat/README.md \
  --version 2026-10-r1
```

Use `--dry-run` for a read-only plan. `--run review-2` selects a named review or
retry while retaining an earlier attempt. The result gives the PDF, first-page
preview, receipt and job paths under `sandbox/practiques/<slug>/`.

For a maintainer testing a core checkout, the corresponding factory target is:

```bash
MCP_CONSUMER_WORKSPACE="$PWD" make -C /path/to/unaltraweb \
  manual-practice-pdf-build \
  PRACTICE_SOURCE=practiques/accessibility/en/alumnat/README.md \
  PRACTICE_VERSION=2026-10-r1
```

The worker runs without network access, with a read-only input snapshot and one
writable output directory. A repeated request verifies and reuses an unchanged
sealed job. Changed inputs produce another job; edited or incomplete attempts
are retained. Updating only the MCP package version does not invalidate a reading
whose effective inputs and rendering controls are unchanged.

The command returns `publishes: false`. Review the PDF before distributing it.
Practice versions are independent of the manual's `latest` or stable release
selectors. Compiling a reading does not analyse GIS data, assemble Moodle ZIPs,
upload files or publish material on the website.
