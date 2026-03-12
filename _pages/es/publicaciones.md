---
layout: page
title: Publicaciones
permalink: /es/publicaciones/
description: Resultados científicos e informes técnicos.
lang: es
ref: publications
nav: true
nav_order: 5
---

{% include bib_search.liquid %}
{% include publications-summary.liquid %}
{% include publications-metrics-summary.liquid %}

<div class="publications">
  {% bibliography %}
</div>
