---
title: Choose A Site Profile
description: Prepared website families supported by unaltraweb.
lang: en
ref: site_profiles
profiles:
- unaltredocs
documentation_profiles:
- github-publishers
- local-authors
- site-designers
- contributors
- core-developers
section: Build A Site
weight: 220
permalink: "/profiles/"
nav_title: Site Profiles
---
<p class="lede">A site profile is a high-level prepared website family. It is not a Jekyll layout or include. Profiles select the real build shape before Jekyll writes the site.</p>

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

## Current Profiles

- **unaltreselfie**: academic or professional personal sites with profile home, optional blog, CV, projects, publications, readings and social links.
- **unaltreprojecte**: research project sites with home pages, team, outputs, publications, resources, repositories and news.
- **unaltremanual**: book-like manuals with localized chapters, sidebar navigation, right-hand table of contents, manual search and teaching blocks.
- **unaltredocs**: technical documentation sites with left-hand index, search, reusable examples and operational pages.

## Screenshots

These screenshots come from the companion template render smoke tests and are generated from working profile builds.

<div class="row g-4">
  <div class="col-md-6">
  <figure class="figure">
    <img class="figure-img img-fluid rounded border" src="https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb-template/main/assets/img/screenshots/home-light-chromium.png" alt="unaltreselfie profile home page screenshot" loading="lazy">
    <figcaption class="figure-caption"><strong>unaltreselfie.</strong> Personal academic homepage with profile card, highlights, posts, publications and projects.</figcaption>
  </figure>
  </div>
  <div class="col-md-6">
  <figure class="figure">
    <img class="figure-img img-fluid rounded border" src="https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb-template/main/assets/img/screenshots/project-home-chromium.png" alt="unaltreprojecte profile home page screenshot" loading="lazy">
    <figcaption class="figure-caption"><strong>unaltreprojecte.</strong> Research project homepage with project navigation, team, outputs and resources.</figcaption>
  </figure>
  </div>
  <div class="col-md-6">
  <figure class="figure">
    <img class="figure-img img-fluid rounded border" src="https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb-template/main/assets/img/screenshots/manual-home-chromium.png" alt="unaltremanual profile home page screenshot" loading="lazy">
    <figcaption class="figure-caption"><strong>unaltremanual.</strong> Course/manual home with chapters, teaching affordances and reader-oriented layout.</figcaption>
  </figure>
  </div>
  <div class="col-md-6">
  <figure class="figure">
    <img class="figure-img img-fluid rounded border" src="https://raw.githubusercontent.com/dosquartsdedocs/unaltraweb-template/main/assets/img/screenshots/unaltredocs-home-chromium.png" alt="unaltredocs profile home page screenshot" loading="lazy">
    <figcaption class="figure-caption"><strong>unaltredocs.</strong> Documentation profile with sectioned content and documentation navigation.</figcaption>
  </figure>
  </div>
</div>

## Choosing A Profile

| Profile | Use it for | Main content |
|---|---|---|
| `unaltreselfie` | A person, researcher, lab member or professional portfolio | `author` config, `_posts/`, `_news/`, `_projects/`, `_bibliography/`, CV PDF |
| `unaltreprojecte` | A research project, funded initiative or group output site | project pages, team data, outputs, repositories, readings, publications and news |
| `unaltremanual` | A manual, course, handbook or book-like learning resource | `_chapters/`, manual bibliography, callouts, figures, tables, Mermaid diagrams and search index |
| `unaltredocs` | Technical or operational documentation | `_documentation/` pages with `section`, `subsection` and `weight` front matter |

## Local Profile Review

Preview one profile without changing `_config.yml`:

```bash
make serve SITE_PROFILE=unaltreprojecte
```

Run all template profile demos together:

```bash
make serve-allprofiles
```

The local port convention is:

- `4001`: `unaltreselfie`.
- `4002`: `unaltreprojecte`.
- `4003`: `unaltremanual`.
- `4004`: `unaltredocs`.

## Filtering Content

Pages and documents can opt into profiles:

```yaml
profiles: [unaltreselfie, unaltreprojecte]
```

The core filters non-matching pages before writing the site. Alternate profiles should be tested by rebuilding with a config overlay, not by client-side preview switches.

## Feature Flags

Navigation pages can use a feature key:

```yaml
feature: projects
nav: true
```

If `unaltraweb.features.projects` is `false`, the page is hidden from navigation while the content can remain in the repository.

## Documentation Site Name

The public documentation site for this project is called `unaltraweb`. It may use documentation-oriented layouts and examples, but it should present the whole platform rather than brand itself as `unaltredocs`.
