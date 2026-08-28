---
title: Write Content With Markdown Extensions
description: unaltraweb syntax beyond standard Markdown.
lang: en
ref: content_syntax
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
section: Design And Customize
weight: 310
permalink: "/syntax/"
nav_title: Markdown Extensions
---
<p class="lede"><code>unaltraweb</code> keeps ordinary Markdown readable, then adds a small set of conventions for profiles, callouts, figures, diagrams, cards and static academic data.</p>

## Profile And Feature Front Matter

Use profile filters when a page should only exist in some site families:

```yaml
---
title: Projects
layout: page
profiles: [unaltreselfie]
feature: projects
nav: true
permalink: /en/projects/
---
```

The page is written only for matching profiles. The `feature` key controls navigation visibility through `_config.yml`:

```yaml
unaltraweb:
  features:
    projects: true
    publications: true
    blog: false
```

## Callouts

Nested blockquotes become teaching callouts in manual-style content. A single `>` remains a normal quotation.

```markdown
>> A note or tip.

>>> A worked example.

>>>> A warning.

>>>>> Learning objectives.

>>>>>> A caution or danger note.
```

Rendered by the same parser:

>> **Note.** Use this for a short conceptual pause.

>>> **Example.** Show the command, formula or reasoning step that makes the concept concrete.

>>>> **Warning.** Flag steps that can damage data, confuse students or break a build.

Use `>>>>>` learning objectives sparingly, normally once after a short chapter or major-section introduction. Do not put them before any orienting prose, and do not use them as repeated mid-section reminders; use prose, tables or ordinary notes for intermediate criteria.

## Manual Heading Levels

Manual chapters number three body levels:

```markdown
## Section
### Subsection
#### Fourth-level subsection
```

The secondary page TOC includes `##` and `###`. A `####` heading remains numbered in the text but is intentionally omitted from that TOC. Use it for a cohesive minor subdivision, not as a formatting substitute for every short item. Do not write standalone fake headings such as `**Source.**`; use a real `####` heading or keep the bold run-in and its explanation in one paragraph.

## Definition Lists

Definition lists render compact terminology as dictionary-style entries on the web and in the manual PDF:

```markdown
Spatial reference system
: Rules and parameters used to interpret coordinates in a defined spatial framework.

Map projection
: Mathematical transformation used to represent a curved surface on a plane.
```

Use them for concise vocabulary. Develop concepts that need arguments, examples, discussion, or limitations in normal paragraphs.

## Figures And Captions

For pages with figure captions enabled, use the Markdown image title as the caption:

```markdown
![Digitizing workflow]({{ site.baseurl }}/assets/img/workflow.svg "Main editing steps")
```

To narrow the space assigned to one figure without changing its height, set a
CSS width with `data-figure-width`. The figure remains centred and cannot exceed
the available width. The PDF builder maps `rem` values against its 60-rem
reading column and caps the result at the printable width:

```markdown
![Project folders](assets/diagrams/folders.puml "Recommended project structure"){: data-figure-width="22rem"}
```

Multi-panel figures use a fenced subfigure block:

```markdown
::: subfigures a+b/c "Three views of the same exercise"
![Interface]({{ site.baseurl }}/assets/img/interface.svg "Interface")
![Map]({{ site.baseurl }}/assets/img/map.svg "Map")
![Diagram]({{ site.baseurl }}/assets/img/diagram.svg "Diagram")
:::
```

The layout string uses `/` for rows and `+` for columns. The example above renders panels `a`, `b` and `c` as one numbered figure on the web and in the PDF.
Use this component when juxtaposition is the teaching task: before/after states, controlled alternatives, a short sequence, or complementary views that need one shared caption. Prefer compact layouts such as `a+b` and `a+b/c`, and use them selectively. Images that merely share a topic should normally remain separate figures.

## Numbered Tables

Manual chapters can number teaching tables with localized labels:

```markdown
::: table "Weekly work rhythm"
| Week | Focus | Output |
| --- | --- | --- |
| 1 | Orientation | Reading notes |
| 2 | Data setup | Working project folder |
:::
```

Cells may contain inline code spans such as `` `=SUM(A2:A10)` ``. The manual renderer preserves these as inline `<code>` elements on the web; if a consumer project still shows literal backticks inside numbered tables, update its `unaltraweb` lock file or use explicit HTML `<code>` as a temporary compatibility fallback.

## Diagram Sources

Reference diagram source files as images. The Jekyll plugin rewrites Mermaid and
PlantUML text sources to SVG files, rendering them through `diavisuals` when the
shared renderer is available:

```markdown
![Vector workflow]({{ site.baseurl }}/assets/diagrams/vector-workflow.mmd "Vector workflow")
```

SVG is the preferred output because it remains editable. The lookup order
prefers edited diagrams first:

```text
vector-workflow.mmd.edited.svg
vector-workflow.mmd.svg
```

When `*.edited.svg` exists, the build keeps using it and does not overwrite it.
Agents changing the diagram source should ask whether to keep the edited SVG or
replace it with a regenerated version.

## Static Vega Sources

Reference a manifest-backed Vega-Lite (`*.vl.json`) or Vega (`*.vg.json`) specification as a captioned image:

```markdown
![Quarterly totals](assets/charts/quarterly.vl.json "Quarterly totals"){: data-figure-width="42rem"}
```

`.vegavisuals.yml` must declare that source exactly once and name its generated output. A source referenced as a web image must produce SVG or PNG; PDF output is valid only for PDF-specific use and cannot be placed in an HTML `img`. Jekyll and the manual PDF builder replace only the image URL, preserving the title caption and Kramdown attributes. SVG is recommended for web/PDF parity. Run `make visualization-render` after source or data changes and `make visualization-check` before publication; rendering and freshness remain owned by the companion `vegavisuals` factory.

## Selector-Based Web Captures

Store a web capture recipe under `assets/` and reference the recipe as the image source:

```markdown
![Chapter navigation](assets/captures/chapter.capture.yml "Annotated chapter navigation")
```

The recipe uses a local preview path and CSS selectors rather than arbitrary browser scripts:

```yaml
version: 1
path: /manual/en/chapter/
viewport: {width: 1440, height: 900}
theme:
  setting: cafe
waits:
  selectors: [.manual-layout]
inputs:
  - _chapters/en/chapter.md
annotations:
  - id: chapter-navigation
    selector: .manual-sidebar
    kind: arrow
    text: Chapter navigation
```

`web_capture_render` starts an ephemeral site and browser on an internal Docker network, keeps the untouched `*.capture.png`, and generates a self-contained `*.capture.svg` with editable vector layers. A manually reviewed `*.capture.edited.svg` wins over the generated SVG and is never overwritten. Commit the recipe, PNG, SVG, and `.unaltraweb/web-captures.lock.json` together. `web_capture_check` blocks stale output and stale edited overrides. Ordinary Jekyll and PDF builds consume only the selected SVG and do not run Chromium.

## Code Fences

Use language names for syntax highlighting. Rouge renders code on the web and Pandoc Skylighting renders the same fenced blocks in manual PDFs. Both outputs add a compact language header and line numbers; web line numbers are hidden from assistive technology and excluded when copying code. A fence declared as `text`, `plaintext`, `plain`, or `txt`, or a fence with no language, uses the localized generic label `Code`, `Codi`, or `Código` without language-specific highlighting. Inline code uses single backticks and is styled separately from prose. Common teaching languages include `bash`, `powershell`, `sql`, `python`, `r`, `haskell`, `javascript`, `yaml`, and `json`:

````markdown
```bash
ogrinfo data/raw/roads.gpkg -so roads
```

```powershell
ogrinfo data\raw\roads.gpkg -so roads
```

```sql
SELECT ST_Area(geom::geography) AS area_m2
FROM protected_areas;
```

```python
import geopandas as gpd
```

```r
library(sf)
```

```
Generic output or a value copied from an application.
```
````

A consumer can replace the generic header through `_data/i18n/<lang>.yml`:

```yaml
code_blocks:
  label: Source code
```

## Links, Citations, And Equations

The web and manual PDF distinguish bibliographic citations, external URLs, and internal links by color. Use Jekyll Scholar for citations, ordinary Markdown for external links, and stable heading identifiers for internal links:

```markdown
{% raw %}{% cite sourceKey %}{% endraw %}
[OGC standards](https://www.ogc.org/)

## Normalization {#normalization}
See [the normalization criteria](#normalization).
```

Inline mathematics uses `$...$`; displayed equations use `$$...$$` on separate lines and are numbered by default. Add a stable `eq:` label when the text refers to an equation; use `equation*` explicitly for an unnumbered display:

```markdown
\begin{equation}
\bar{x}_w = \frac{\sum_i w_i x_i}{\sum_i w_i}
\label{eq:weighted-mean}
\end{equation}

Equation $\eqref{eq:weighted-mean}$ defines the weighted mean.
```

## Hero Images

Pages can use a compact hero image:

```yaml
---
layout: page
title: Example Page
hero:
  image: /assets/img/example-hero.jpg
  alt: Short accessible description
  caption: Optional caption
  source: Optional source name
  source_url: https://example.org/source
  position: center
---
```

Project entries can also define `hero` for cards and project pages.

## Project Resources

Project pages can expose datasets, repositories, papers and documentation as icon badges:

```yaml
---
layout: project
title: Example Project
resources:
  - type: zenodo
    label: Zenodo dataset
    url: https://zenodo.org/records/1000001
    doi: 10.5281/zenodo.1000001
  - type: github
    label: Source code
    url: https://github.com/example/project
  - type: documentation
    label: Technical notes
    url: https://example.org/docs/example
---
```

Built-in resource types include `zenodo`, `doi`, `dataset`, `data`, `code`, `github`, `repository`, `documentation`, `docs`, `map`, `publication`, `paper`, `report`, `website` and `link`.

## CV Preview Cards

Use the CV preview include when a PDF is the source of truth:

```yaml
---
cv_pdf: /assets/pdf/cv.pdf
cv_preview: /assets/img/cv-preview.jpg
---
```

{% raw %}
```liquid
{% include cv-download-card.liquid pdf=page.cv_pdf preview=page.cv_preview title="CV" %}
```
{% endraw %}

Generate the preview locally:

```bash
make cv-preview CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
```

## Documentation Sections

The `unaltredocs` profile uses `_documentation` documents with front matter that drives the left index:

```yaml
---
title: Installation
section: Getting Started
subsection: Local workflow
weight: 20
documentation_profiles: [local-authors]
---
```

## Static Metrics

Publication metrics are updated before builds and written to local files. Jekyll builds do not call OpenAlex, Crossref, Scimago or Google Scholar.

```text
bibliometrics_update
bibliometrics_check
```
