---
layout: page
title: Productos
permalink: /es/productos/
description: Datos, herramientas, mapas, fichas de indicadores, cálculos y otros productos del proyecto.
lang: es
ref: outputs
nav: true
nav_order: 3
---

{% assign current_lang = page.lang | default: site.default_lang %}
{% assign localized_outputs = site.outputs | where: 'lang', current_lang %}
{% if localized_outputs.size == 0 and current_lang != site.default_lang %}
  {% assign localized_outputs = site.outputs | where: 'lang', site.default_lang %}
{% endif %}
{% if current_lang == site.default_lang %}
  {% assign fallback_outputs = site.outputs | where_exp: 'output', 'output.lang == nil' %}
  {% assign localized_outputs = localized_outputs | concat: fallback_outputs %}
{% endif %}
{% assign sorted_outputs = localized_outputs | sort: 'importance' %}

<div class="projects">
  {% if sorted_outputs.size > 0 %}
    <div class="row row-cols-1 row-cols-md-3">
      {% for project in sorted_outputs %}
        {% include projects.liquid %}
      {% endfor %}
    </div>
  {% else %}
    <p>Añade tarjetas en la colección `_outputs` para poblar esta sección.</p>
  {% endif %}
</div>
