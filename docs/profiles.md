---
title: Site Profiles
description: Prepared website families supported by unaltraweb.
permalink: /profiles/
---

# Site profiles

<p class="lede">A site profile is a high-level prepared website family. It is not a Jekyll layout or include. Profiles select the real build shape before Jekyll writes the site.</p>

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

## Current Profiles

<div class="cards">
  <section class="card">
    <h3>personal</h3>
    <p>Academic or professional personal sites with profile home, optional blog, CV, projects, publications and social links.</p>
  </section>
  <section class="card">
    <h3>project</h3>
    <p>Research project sites with home pages, team, outputs, publications, resources, repositories and news.</p>
  </section>
  <section class="card">
    <h3>manual</h3>
    <p>Book-like manuals with localized chapters, sidebar navigation, right-hand table of contents, manual search and teaching blocks.</p>
  </section>
  <section class="card">
    <h3>software</h3>
    <p>Planned profile for software/project documentation, releases, repositories and usage pages.</p>
  </section>
  <section class="card">
    <h3>course</h3>
    <p>Planned teaching profile extending manual behaviour with course, slides and exercise affordances.</p>
  </section>
</div>

## Filtering Content

Pages and documents can opt into profiles:

```yaml
profiles: [personal, project]
```

The core filters non-matching pages before writing the site. Alternate profiles should be tested by rebuilding with a config overlay, not by client-side preview switches.

## Feature Flags

Navigation pages can use a feature key:

```yaml
feature: projects
nav: true
```

If `unaltraweb.features.projects` is `false`, the page is hidden from navigation while the content can remain in the repository.
