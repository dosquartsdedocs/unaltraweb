# Customization

`unaltraweb` is intended to be customized from the site repository, not by editing the core theme files.

## Local Styles

Create `_sass/_site-custom.scss` in your site repository. It is imported after the core styles, so local rules can override CSS custom properties or add small components while still receiving upstream `unaltraweb` updates.

```scss
:root {
  --global-theme-color: #2f6f5e;
  --global-hover-color: #2f6f5e;
}

html[data-theme="sepia"] {
  --global-theme-color: #6f4e1f;
}
```

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
  site_profile: personal
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
  sort_field: date
  sort_reverse: true
```

```yaml
---
title: Blog
pagination:
  enabled: true
---
```

`blog-list.liquid` uses `paginator.posts` when Jekyll generates paginated pages and falls back to the localized post archive otherwise.

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

Supported built-in icon types include `zenodo`, `doi`, `dataset`, `data`, `code`, `github`, `repository`, `documentation`, `docs`, `manual`, `map`, `publication`, `paper`, `report`, `website`, and `link`. A resource can override the icon with an explicit class, for example `icon: fa-solid fa-chart-line`.

## CV Preview Cards

Use `cv-download-card.liquid` on CV pages when the PDF is the source of truth and the page should show a first-page preview plus a download button.

```yaml
---
cv_pdf: /assets/pdf/cv.pdf
cv_preview: /assets/img/cv-preview.jpg
---
```

```liquid
{% include cv-download-card.liquid pdf=page.cv_pdf preview=page.cv_preview title="CV" %}
```

Child sites can generate the preview with their template `Makefile` target:

```bash
make cv-preview CV_PDF=assets/pdf/cv.pdf CV_PREVIEW=assets/img/cv-preview.jpg
```

## Theme Modes

The built-in theme switch supports `system`, `light`, `sepia`, and `dark` settings. `system` follows the browser preference and resolves to light or dark; `sepia` is an explicit reading mode inspired by GitBook's sepia palette.

Theme changes are observable from JavaScript through the `unaltraweb:themechange` event:

```js
document.addEventListener("unaltraweb:themechange", (event) => {
  console.log(event.detail.theme, event.detail.themeSetting);
});
```

The active values are also available on `<html>` as `data-theme`, `data-theme-setting`, `data-theme-integration`, and `data-site-profile`. These attributes are stable enough for local styles and automated browser tests.

## Developer Mode

Child sites can enable `unaltraweb.developer_mode` in a development-only config file. When `JEKYLL_ENV` is not `production`, this displays a floating indicator showing the real profile used by the current build.

```yaml
unaltraweb:
  developer_mode: true
```

Keep this setting out of production builds. The template `Makefile` writes it to `tmp/_config.development.yml` for `make serve`, while `make build` uses the normal production config.

Do not rely on client-side preview shells for alternate profiles. Jekyll renders one real configuration per build, so profiles should be tested by rebuilding with a config overlay, for example `make serve SITE_PROFILE=project` in the template. Pages can declare `profiles: [personal]` or `profiles: [project]`; the core filters non-matching pages before writing the site.
