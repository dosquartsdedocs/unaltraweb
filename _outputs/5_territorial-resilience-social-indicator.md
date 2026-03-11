---
layout: page
title: "Territorial resilience indicator (social dimension: communities)"
description: "Demo indicator card with methodological sheet, sample calculations, and interpretation thresholds."
img: assets/img/10.jpg
importance: 5
category: indicator
lang: en
---

## Demo overview

This output simulates a territorial resilience indicator focused on the social dimension (communities). It is intended as a template card to present the indicator sheet, placeholder calculations, and interpretation ranges.

{% include figure.liquid loading="eager" path="assets/img/10.jpg" title="Community resilience placeholder image" class="img-fluid rounded z-depth-1" %}

## Indicator sheet (demo)

| Field | Demo value |
| --- | --- |
| Indicator code | `TR-SOC-01` |
| Name | Community support network strength |
| Dimension | Social |
| Unit | Index (0-100) |
| Spatial scale | Municipality / district |
| Update frequency | Annual |
| Data sources | Survey sample, local registry, open census |

## Calculation logic

The demo index combines three normalized components:

- community participation rate,
- access to nearby support services,
- perceived neighborhood trust.

`TR_SOC_01 = 0.4 * participation_norm + 0.3 * services_norm + 0.3 * trust_norm`

## Sample data table

| Territory | Participation (0-100) | Services access (0-100) | Trust (0-100) | TR-SOC-01 |
| --- | ---: | ---: | ---: | ---: |
| District A | 68 | 55 | 62 | 62.3 |
| District B | 44 | 72 | 51 | 54.1 |
| District C | 80 | 64 | 77 | 74.3 |

## Interpretation thresholds

| Range | Interpretation |
| --- | --- |
| 0-39 | Low social resilience |
| 40-59 | Medium-low social resilience |
| 60-79 | Medium-high social resilience |
| 80-100 | High social resilience |

Use this page as a base to publish real indicator cards, including metadata, formulas, QA notes, and downloadable tables.
