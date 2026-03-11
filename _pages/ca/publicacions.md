---
layout: page
title: Publicacions
permalink: /ca/publicacions/
description: Resultats científics i informes tècnics.
lang: ca
ref: publications
nav: true
nav_order: 5
---

{% include bib_search.liquid %}
{% include publications-summary.liquid %}

<div class="publications">
  {% bibliography %}
</div>
