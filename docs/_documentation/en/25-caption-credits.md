---
title: Figure And Table Captions With Credits
description: Separate automatic numbering, descriptive captions and source credits, with concise PDF indexes.
lang: en
ref: caption_credits
profiles: [unaltredocs]
documentation_profiles: [github-publishers, local-authors, site-designers, contributors]
section: Design And Customize
weight: 315
permalink: "/caption-credits/"
nav_title: Captions And Credits
---

A caption has three distinct parts: its automatic label and number, the
description of the figure or table, and optional source or creator credits.
Credits remain part of the visible caption but use a smaller italic style. In a
manual PDF, only the number and description enter the list of figures or tables.

## Figure

Keep the descriptive caption in the Markdown image title and add
`data-caption-source` to its attribute block. Alternative text describes the
image independently of its caption and credits.

```markdown
![Three boxes connected from left to right](assets/img/caption-credits-demo.svg "Three linked stages"){: data-figure-width-web="34rem" data-figure-width-pdf="78%" data-caption-source="Source: original schematic for this example. Credits: unaltraweb."}
```

![Three boxes A, B and C connected from left to right]({{ site.baseurl }}/assets/img/caption-credits-demo.svg "Three linked stages"){: data-figure-width-web="34rem" data-figure-width-pdf="78%" data-caption-source="Source: original schematic for this example. Credits: unaltraweb."}

The label receives the numbering style, the description is normal caption text,
and the source continues inline in its own styled span. Normal wrapping can move
the source onto the next line; it is not a separate numbered item.

## Table

Use the same attribute after the opening caption. This example contains
synthetic values solely to illustrate the presentation.

```markdown
::: table "Example values" {: data-caption-source="Source: synthetic demonstration data. Credits: unaltraweb."}
| Element | Value |
| --- | ---: |
| A | 10 |
| B | 25 |
| C | 40 |
:::
```

::: table "Example values" {: data-caption-source="Source: synthetic demonstration data. Credits: unaltraweb."}
| Element | Value |
| --- | ---: |
| A | 10 |
| B | 25 |
| C | 40 |
:::

## Links And Attribution

The credit field accepts inline Markdown, including links and emphasis, and the
existing bibliography citation syntax. Supply the label appropriate to the
content language, such as “Source”, “Font”, “Fuente” or “Credits”. Attribution
must describe the actual origin and licence of the material.

::: table "Caption components" {: data-caption-source="Credits: [unaltraweb](https://github.com/dosquartsdedocs/unaltraweb), documentation example."}
| Component | Purpose |
| --- | --- |
| Label and number | Automatically identify the figure or table |
| Description | Explain what the reader should observe |
| Source or credits | Identify origin, authorship or licence |
:::

Use single quotes around the attribute if the credit text contains literal double
quotes. Liquid citations such as `{% raw %}{% cite verifiedKey %}{% endraw %}`
follow the usual verified-bibliography workflow. Keep credits in the attribute,
rather than concatenating them into the descriptive title.

## Multi-Panel Figures

The attribute can credit the whole group or an individual panel:

```markdown
::: subfigures a+b "Two views of the same schematic" {: data-caption-source="Source: original demonstration schematic."}
![First view](assets/img/caption-credits-demo.svg "First view"){: data-caption-source="Credits: unaltraweb."}
![Second view](assets/img/caption-credits-demo.svg "Second view")
:::
```

::: subfigures a+b "Two views of the same schematic" {: data-caption-source="Source: original demonstration schematic."}
![First view]({{ site.baseurl }}/assets/img/caption-credits-demo.svg "First view"){: data-caption-source="Credits: unaltraweb."}
![Second view]({{ site.baseurl }}/assets/img/caption-credits-demo.svg "Second view")
:::

## Existing Captions

Existing captions remain valid. The renderer does not guess where a source starts
in an old caption, since words such as “source” can be part of the description.
Move attribution into `data-caption-source` explicitly to obtain separate styling
and shorter PDF index entries.

::: table "A caption without separate credits"
| Element | Category |
| --- | --- |
| A | Initial |
| B | Intermediate |
:::

## PDF Index Entries

For the figure above, the list of figures contains **Three linked stages**. Its
source and creator attribution remain beside the full caption in the chapter.
For the first table, the list of tables contains **Example values**, without the
synthetic-data attribution. Figure/table numbering continues to follow the
manual's normal chapter numbering.

The web exposes `.figlabel`, `.md-caption-text` and `.md-caption-source` for these
roles. The PDF renderer preserves inline formatting and links in the full caption
and supplies a description-only short caption to LaTeX. These semantics apply to
normal images, diagrams and generated figures referenced through the same image
syntax; source generation and freshness remain owned by their respective tools.
