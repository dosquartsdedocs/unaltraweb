---
layout: page
published: false
permalink: /publications/
title: Publications
description: Publications by categories in reversed chronological order.
nav: true
nav_order: 4
---

<!-- _pages/publications.md -->

<!-- Bibsearch Feature -->

{% include bib_search.liquid %}

<div class="publications">

{% capture n_total_raw %}{% bibliography_count -f papers %}{% endcapture %}
{% assign n_total = n_total_raw | strip | plus: 0 %}

{% capture n_article_raw %}{% bibliography_count -f papers --query @article %}{% endcapture %}
{% assign n_article = n_article_raw | strip | plus: 0 %}

{% capture n_inproceedings_raw %}{% bibliography_count -f papers --query @inproceedings %}{% endcapture %}
{% assign n_inproceedings = n_inproceedings_raw | strip | plus: 0 %}

{% capture n_incollection_raw %}{% bibliography_count -f papers --query @incollection %}{% endcapture %}
{% assign n_incollection = n_incollection_raw | strip | plus: 0 %}

{% capture n_book_raw %}{% bibliography_count -f papers --query @book %}{% endcapture %}
{% assign n_book = n_book_raw | strip | plus: 0 %}

{% capture n_inbook_raw %}{% bibliography_count -f papers --query @inbook %}{% endcapture %}
{% assign n_inbook = n_inbook_raw | strip | plus: 0 %}

{% capture n_techreport_raw %}{% bibliography_count -f papers --query @techreport %}{% endcapture %}
{% assign n_techreport = n_techreport_raw | strip | plus: 0 %}

{% capture n_phdthesis_raw %}{% bibliography_count -f papers --query @phdthesis %}{% endcapture %}
{% assign n_phdthesis = n_phdthesis_raw | strip | plus: 0 %}

{% capture n_mastersthesis_raw %}{% bibliography_count -f papers --query @mastersthesis %}{% endcapture %}
{% assign n_mastersthesis = n_mastersthesis_raw | strip | plus: 0 %}

{% capture n_misc_raw %}{% bibliography_count -f papers --query @misc %}{% endcapture %}
{% assign n_misc = n_misc_raw | strip | plus: 0 %}

{% if n_total > 0 %}
  {% assign parts = "" | split: "|" %}

  {% if n_article > 0 %}
    {% capture s %}<strong>{{ n_article }}</strong> journal article{% if n_article != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% if n_inproceedings > 0 %}
    {% capture s %}<strong>{{ n_inproceedings }}</strong> conference paper{% if n_inproceedings != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% if n_incollection > 0 %}
    {% capture s %}<strong>{{ n_incollection }}</strong> book chapter{% if n_incollection != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% assign n_books_total = n_book | plus: n_inbook %}
  {% if n_books_total > 0 %}
    {% capture s %}<strong>{{ n_books_total }}</strong> book{% if n_books_total != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% if n_techreport > 0 %}
    {% capture s %}<strong>{{ n_techreport }}</strong> technical report{% if n_techreport != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% assign n_thesis_total = n_phdthesis | plus: n_mastersthesis %}
  {% if n_thesis_total > 0 %}
    {% capture s %}<strong>{{ n_thesis_total }}</strong> thes{% if n_thesis_total == 1 %}is{% else %}es{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  {% if n_misc > 0 %}
    {% capture s %}<strong>{{ n_misc }}</strong> other item{% if n_misc != 1 %}s{% endif %}{% endcapture %}
    {% assign parts = parts | push: s %}
  {% endif %}

  <p class="pub-counts">
    This page currently lists <strong>{{ n_total }}</strong> publications: {{ parts | join: ", " }}.
  </p>
{% endif %}

{% include publications-metrics-summary.liquid %}


{% bibliography %}

</div>
