---
title: Content Syntax
description: unaltraweb syntax beyond standard Markdown.
lang: en
ref: content_syntax
profiles: [unaltredocs]
section: Standards
weight: 200
permalink: /syntax/
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

## Figures And Captions

For pages with figure captions enabled, use the Markdown image title as the caption:

```markdown
![Digitizing workflow]({{ site.baseurl }}/assets/img/workflow.svg "Main editing steps")
```

Multi-panel figures use a fenced subfigure block:

```markdown
::: subfigures a+b/c "Three views of the same exercise"
![Interface]({{ site.baseurl }}/assets/img/interface.svg "Interface")
![Map]({{ site.baseurl }}/assets/img/map.svg "Map")
![Diagram]({{ site.baseurl }}/assets/img/diagram.svg "Diagram")
:::
```

The layout string uses `/` for rows and `+` for columns. The example above renders panels `a`, `b` and `c` as one numbered figure.

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

## Mermaid Diagrams

Reference Mermaid source files as images. The build rewrites `.mmd` references to generated SVG files when available:

```markdown
![Vector workflow]({{ site.baseurl }}/assets/diagrams/vector-workflow.mmd "Vector workflow")
```

The lookup order prefers edited diagrams first:

```text
vector-workflow.mmd.edited.svg
vector-workflow.mmd.svg
```

## Code Fences

Use language names for syntax highlighting. Common teaching languages are supported through Rouge:

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
````

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
---
```

## Static Metrics

Publication metrics are updated before builds and written to local files. Jekyll builds do not call OpenAlex, Crossref, Scimago or Google Scholar.

```bash
make metrics-update
make metrics-check METRICS_ARGS="--offline --dry-run"
```
