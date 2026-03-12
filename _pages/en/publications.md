---
layout: page
title: Publications
permalink: /en/publications/
description: Scientific outputs and technical reports.
lang: en
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
