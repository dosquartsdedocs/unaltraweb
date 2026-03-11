---
layout: page
title: "Indicador de resiliencia territorial (dimensión social: comunidades)"
description: "Ficha demo con metodología, cálculos de ejemplo y umbrales de interpretación."
img: assets/img/10.jpg
importance: 5
category: indicator
lang: es
permalink: /es/outputs/indicador-resiliencia-territorial-social/
---

## Resumen demo

Este output simula un indicador de resiliencia territorial centrado en la dimensión social (comunidades). Sirve como plantilla para publicar ficha metodológica, cálculos y rangos de interpretación.

{% include figure.liquid loading="eager" path="assets/img/10.jpg" title="Imagen de ejemplo para resiliencia comunitaria" class="img-fluid rounded z-depth-1" %}

## Ficha del indicador (demo)

| Campo | Valor de ejemplo |
| --- | --- |
| Código | `TR-SOC-01` |
| Nombre | Fortaleza de redes de apoyo comunitario |
| Dimensión | Social |
| Unidad | Índice (0-100) |
| Escala espacial | Municipio / distrito |
| Frecuencia | Anual |
| Fuentes | Encuesta muestral, registro local, censo abierto |

## Lógica de cálculo

El índice de ejemplo combina tres componentes normalizados:

- tasa de participación comunitaria,
- acceso a servicios de apoyo cercanos,
- confianza vecinal percibida.

`TR_SOC_01 = 0.4 * participacion_norm + 0.3 * servicios_norm + 0.3 * confianza_norm`

## Tabla de datos de muestra

| Territorio | Participación (0-100) | Acceso a servicios (0-100) | Confianza (0-100) | TR-SOC-01 |
| --- | ---: | ---: | ---: | ---: |
| Distrito A | 68 | 55 | 62 | 62.3 |
| Distrito B | 44 | 72 | 51 | 54.1 |
| Distrito C | 80 | 64 | 77 | 74.3 |

## Umbrales de interpretación

| Rango | Interpretación |
| --- | --- |
| 0-39 | Resiliencia social baja |
| 40-59 | Resiliencia social medio-baja |
| 60-79 | Resiliencia social medio-alta |
| 80-100 | Resiliencia social alta |

Usa esta página como base para publicar fichas reales de indicadores con metadatos, fórmulas, control de calidad y tablas descargables.
