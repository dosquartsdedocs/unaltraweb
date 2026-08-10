---
title: Customize A Child Site
description: Local customization points for unaltraweb child sites.
lang: en
ref: customization
profiles:
- unaltredocs
documentation_profiles:
- local-authors
- site-designers
- contributors
- core-developers
section: Design And Customize
weight: 330
permalink: "/customization/"
nav_title: Customization
---
`unaltraweb` is intended to be customized from the site repository, not by editing the core theme files.

## Local Styles

Create `_sass/_site-custom.scss` in your site repository. It is imported after the core styles, so local rules can override CSS custom properties or add small components while still receiving upstream `unaltraweb` updates.

```scss
:root {
  --global-theme-color: #2f6f5e;
  --global-hover-color: #2f6f5e;
}

html[data-theme="cafe"] {
  --global-theme-color: #6f4e1f;
}
```

The built-in coffee mode uses `data-theme="cafe"`. Override CSS custom properties in that selector when you want a different brown palette without changing light or dark mode.

For larger local style changes, keep selectors scoped by profile or theme:

```scss
html[data-site-profile="unaltredocs"] .documentation-sidebar {
  --documentation-toc-line: color-mix(in srgb, var(--global-theme-color) 42%, var(--global-divider-color));
}

html[data-theme="dark"] .my-local-card {
  background: #1f2935;
}
```

Do not copy `_sass/` files from `unaltraweb` into a child site. Override tokens and small selectors locally so future gem updates still apply.

## Multilingual Hyphenation

Text hyphenation is enabled globally in the main content area. Browsers use the page language from `lang` (`en`, `es`, `ca`, or another configured language) to choose the hyphenation dictionary.

Use `.no-hyphenate` when a specific word, brand, code-like label or compact block should not be split:

```html
<span class="no-hyphenate">dosquartsdedocs</span>
```

For mixed-language passages, set the appropriate `lang` attribute on the local element so the browser can switch dictionaries.

## Local Layouts

Create a layout in `_layouts/` inside the site repository and reference it from page front matter.

```liquid
---
layout: page
---

<div class="my-local-layout">
  {{ content }}
</div>
```

```yaml
---
layout: my-local-layout
title: Custom Page
---
```

Jekyll resolves site files before theme files, so local layouts can extend or override core layouts without forking `unaltraweb`.

## Site Profiles And Features

Use `site.unaltraweb.site_profile` to select the prepared website profile and `site.unaltraweb.features` to enable or hide standard sections. A site profile is a high-level preset for the kind of website being built; it is not a Jekyll layout or include.

```yaml
unaltraweb:
  site_profile: unaltreselfie
  features:
    blog: true
    cv: true
    projects: true
    publications: true
    metrics: true
```

Navigation pages can opt into a feature gate with front matter:

```yaml
---
title: Projects
ref: projects
feature: projects
nav: true
---
```

If `unaltraweb.features.projects` is `false`, that page is hidden from the navigation. The page still exists if it is published, so users can keep drafts or direct links while changing presets.

## Standard Section Layouts

Several reusable sections are layouts. Child sites should prefer these layouts over copying Liquid loops into their pages:

```yaml
---
layout: outputs
title: Outputs
ref: outputs
permalink: /en/outputs/
---
```

```yaml
---
layout: repositories
title: Repositories
ref: repositories
permalink: /en/repositories/
---
```

```yaml
---
layout: theses
title: Theses
ref: theses
permalink: /en/theses/
---
```

```yaml
---
layout: book-shelf
title: Readings
ref: books
collection: books
permalink: /en/readings/
---
```

The content lives in the site repository: `_outputs/` for output cards, `_data/repositories.yml` for repository cards, `_theses/` for thesis records, and `_books/` for reading notes. The rendering logic stays in `unaltraweb`.

## Callout Shorthand

Use nested Markdown blockquotes for lightweight teaching callouts. A single `>` remains a normal quotation; deeper levels become callouts:

```markdown
>> A note or tip.

>>> A worked example.

>>>> A warning.

>>>>> Learning objectives.

>>>>>> A caution or danger note.
```

The labels are localized through `_data/i18n/*.yml` under `callouts`, and the colors follow the active light, coffee, or dark theme.

## Manual Profile

Use the `unaltremanual` site profile for academic handbooks, course manuals and book-like teaching material. The core profile provides a cover page, a sticky contents sidebar, a right-hand chapter table of contents, multilingual chapter routing, teacher blocks, automatic figure captions for chapters, a full-text manual search index, navbar reader font-size controls and a bibliography section without bibliometric badges.

```yaml
unaltraweb:
  site_profile: unaltremanual
  manual:
    collection: chapters
    cover_image: /assets/img/manual-cover.svg
    logo: /assets/img/brand/dosquartsdedocs-logo.svg
    logo_inverse: /assets/img/brand/dosquartsdedocs-logo-white.svg
  figure_captions:
    enabled: true
    collections: [chapters]

scholar:
  # Optional, useful when porting a GitBook/TIG-style course bibliography.
  style: _bibliography/my-apa-cv-no-access.csl
  bibliography_template: manual-bib
  group_by: none
```

Create one localized home page per language with `layout: manual-home` and `ref: home`, then add chapters to `_chapters/<lang>/`:

```yaml
---
layout: manual-chapter
title: Reading Spatial Data
lang: en
ref: reading-spatial-data
weight: 20
permalink: /en/chapters/reading-spatial-data/
manual_references: true
mermaid:
  enabled: true
  zoomable: true
---
```

Markdown images inside configured chapter collections are wrapped in `<figure>` elements and get localized labels. Use the optional image title as the caption:

```markdown
![Digitizing workflow]({{ site.baseurl }}/assets/img/workflow.svg "Main editing steps")
```

For multi-panel teaching figures, use a compact subfigure block. The layout string uses `/` for rows and `+` for columns, inspired by patchwork-style composition:

```markdown
::: subfigures a+b/c "Three views of the same exercise"
![Interface]({{ site.baseurl }}/assets/img/interface.svg "Interface")
![Map]({{ site.baseurl }}/assets/img/map.svg "Map")
![Diagram]({{ site.baseurl }}/assets/img/diagram.svg "Diagram")
:::
```

This renders one numbered figure with panel labels `a`, `b`, `c`; the contained images remain ordinary Markdown image declarations.

Manual chapters can also number teaching tables with the same localized counter style. Wrap a regular Markdown table in a table block and put the caption in the opening line:

```markdown
::: table "Weekly work rhythm"
| Week | Focus | Output |
| --- | --- | --- |
| 1 | Orientation | Reading notes |
| 2 | Data setup | Working project folder |
:::
```

This renders a numbered table with localized labels such as `Table 1.`, `Taula 1.` or `Tabla 1.`. Tables and figures keep separate counters.

Use fenced code blocks for programming examples. The theme uses Rouge, so common TIG languages such as Bash/Linux shell, Windows PowerShell, SQL/PostGIS, Python, R and Haskell get syntax highlighting when the fence includes the language name:

````markdown
Inline code like `ST_Transform` stays inside the paragraph.

```sql
SELECT ST_Area(geom::geography) AS area_m2
FROM protected_areas;
```

```bash
ogrinfo data/raw/roads.gpkg -so roads
```

```powershell
ogrinfo data\raw\roads.gpkg -so roads
```

```python
import geopandas as gpd
```

```r
library(sf)
```

```haskell
manhattan :: Int -> Int -> Int
```
````

The manual profile also writes `assets/js/manual-search-index.json` during the build so the sidebar search can find terms anywhere in the localized manual.

Mermaid and PlantUML source references are rewritten to SVG outputs. When a
matching `*.edited.svg` exists it wins; otherwise the build targets the generated
`*.svg` file and asks `diavisuals` to render it when the shared renderer is
available. Manual diagram figures also receive diagram surfaces tuned for light,
dark and coffee themes. This keeps generated diagrams and hand-edited diagrams
readable in the same Markdown:

```markdown
![Vector workflow]({{ site.baseurl }}/assets/diagrams/vector-workflow.mmd "Vector workflow")
```

SVG is the first-choice output so authors can edit the figure after generation.
If an agent is asked to change a diagram source while `*.edited.svg` exists, it
should ask whether to preserve that edited SVG or replace it with a new generated
SVG.

## Page Hero Images

Any page that uses `layout: page` or `layout: about` can define a hero image in front matter. The compact form keeps compatibility with older pages:

```yaml
---
layout: page
title: Example Page
hero_image: /assets/img/example-hero.jpg
hero_image_alt: Short accessible description
hero_caption: Optional caption
hero_source: Optional source name
hero_source_url: https://example.org/source
---
```

For new pages, use the grouped `hero` form:

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

## Blog Pagination

Child sites can enable blog pagination without changing the core defaults. Set pagination in the site config and enable it on the blog page that includes `blog-list.liquid`.

```yaml
pagination:
  enabled: true
  collection: posts
  per_page: 4
  permalink: /page/:num/
  title: ":title"
  sort_field: date
  sort_reverse: true
```

```yaml
---
title: Blog
pagination:
  enabled: true
  locale: en
---
```

`blog-list.liquid` uses `paginator.posts` when Jekyll generates paginated pages and falls back to the localized post archive otherwise. For multilingual sites, set the page-level `pagination.locale` and the same `locale` value in each post front matter.

## Project Card Images

Project entries can define a main image with `hero`. In project cards, that image is used as a very light degraded background for the card.

```yaml
---
title: Example Project
description: Short project summary.
hero: /assets/img/projects/example.jpg
---
```

## Project Resources

Project entries can also define `resources`. These links are rendered as icon badges on the project card and in a resources panel inside pages that use `layout: project`.

```yaml
---
layout: project
title: Example Project
resources:
  - type: zenodo
    label: Zenodo dataset
    url: https://zenodo.org/records/1000001
    doi: 10.5281/zenodo.1000001
  - type: dataset
    label: Harmonized data layers
    url: https://example.org/datasets/example
  - type: documentation
    label: Technical notes
    url: https://example.org/docs/example
---
```

Supported built-in icon types include `zenodo`, `doi`, `dataset`, `data`, `code`, `github`, `repository`, `documentation`, `docs`, `unaltremanual`, `map`, `publication`, `paper`, `report`, `website`, and `link`. A resource can override the icon with an explicit class, for example `icon: fa-solid fa-chart-line`.

## CV Preview Cards

Use `cv-download-card.liquid` on CV pages when the PDF is the source of truth and the page should show a first-page preview plus a download button.

```yaml
---
cv_pdf: /assets/pdf/cv.pdf
cv_preview: /assets/img/cv-preview.jpg
---
```

```liquid
{% raw %}{% include cv-download-card.liquid pdf=page.cv_pdf preview=page.cv_preview title="CV" %}{% endraw %}
```

Child sites can generate the preview with their template `Makefile` target:

```bash
make cv-preview CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
```

## Theme Modes

The built-in theme switch supports `system`, `light`, `cafe`, and `dark` settings. `system` follows the browser preference and resolves to light or dark; `cafe` is an explicit coffee reading mode for warm long-form pages.

Theme changes are observable from JavaScript through the `unaltraweb:themechange` event:

```js
document.addEventListener("unaltraweb:themechange", (event) => {
  console.log(event.detail.theme, event.detail.themeSetting);
});
```

The active values are also available on `<html>` as `data-theme`, `data-theme-setting`, `data-theme-integration`, and `data-site-profile`. These attributes are stable enough for local styles and automated browser tests.

## Developer Mode

`unaltraweb-template` can enable `unaltraweb.developer_mode` in a development-only config file. When `JEKYLL_ENV` is not `production`, this displays a floating indicator showing the real profile used by the current build.

```yaml
unaltraweb:
  developer_mode: true
```

Keep this setting out of production builds. The template `Makefile` writes it to `tmp/_config.development.yml` for `make serve` only when working directly in the `unaltraweb-template` checkout, while child sites keep it disabled unless `DEVELOPER_MODE=true` is passed explicitly. `make build` uses the normal production config.

Do not rely on client-side preview shells for alternate profiles. Jekyll renders one real configuration per build, so profiles should be tested by rebuilding with a config overlay, for example `make serve SITE_PROFILE=unaltreprojecte` in the template. Pages can declare `profiles: [unaltreselfie]` or `profiles: [unaltreprojecte]`; the core filters non-matching pages before writing the site.
