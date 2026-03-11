---
layout: page
title: "Indicador de resiliència territorial (dimensió social: comunitats)"
description: "Fitxa demo amb metodologia, càlculs de mostra i llindars d'interpretació."
img: assets/img/10.jpg
importance: 5
category: indicator
lang: ca
permalink: /ca/outputs/indicador-resiliencia-territorial-social/
---

## Resum demo

Aquest output simula un indicador de resiliència territorial centrat en la dimensió social (comunitats). Serveix com a plantilla per publicar fitxa metodològica, càlculs i rangs d'interpretació.

{% include figure.liquid loading="eager" path="assets/img/10.jpg" title="Imatge de mostra per a resiliència comunitària" class="img-fluid rounded z-depth-1" %}

## Fitxa de l'indicador (demo)

| Camp | Valor de mostra |
| --- | --- |
| Codi | `TR-SOC-01` |
| Nom | Fortalesa de xarxes de suport comunitari |
| Dimensió | Social |
| Unitat | Índex (0-100) |
| Escala espacial | Municipi / districte |
| Freqüència | Anual |
| Fonts | Enquesta mostral, registre local, cens obert |

## Lògica de càlcul

L'índex de mostra combina tres components normalitzats:

- taxa de participació comunitària,
- accés a serveis de suport pròxims,
- confiança veïnal percebuda.

`TR_SOC_01 = 0.4 * participacio_norm + 0.3 * serveis_norm + 0.3 * confianca_norm`

## Taula de dades de mostra

| Territori | Participació (0-100) | Accés a serveis (0-100) | Confiança (0-100) | TR-SOC-01 |
| --- | ---: | ---: | ---: | ---: |
| Districte A | 68 | 55 | 62 | 62.3 |
| Districte B | 44 | 72 | 51 | 54.1 |
| Districte C | 80 | 64 | 77 | 74.3 |

## Llindars d'interpretació

| Rang | Interpretació |
| --- | --- |
| 0-39 | Resiliència social baixa |
| 40-59 | Resiliència social mitjana-baixa |
| 60-79 | Resiliència social mitjana-alta |
| 80-100 | Resiliència social alta |

Fes servir aquesta pàgina com a base per publicar fitxes reals d'indicadors amb metadades, fórmules, control de qualitat i taules descarregables.
