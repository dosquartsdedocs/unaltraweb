---
title: Check Image Backgrounds
description: Read-only transparency warnings for raster images and self-contained SVG figures.
lang: en
ref: image_backgrounds
profiles: [unaltredocs]
documentation_profiles: [local-authors, site-designers, contributors, core-developers]
section: Design And Customize
weight: 318
permalink: "/image-backgrounds/"
nav_title: Image Backgrounds
---

Publication images should have an opaque background chosen for their content.
Any opaque colour is valid. A transparent PNG can be just as difficult to read
as a transparent SVG when enlarged over the website, so the check examines image
content rather than assuming that one filename extension is safe.

`image_background_check` is an **advisory**. It reports transparent and
unverifiable images, without modifying files, painting them white, changing
their dimensions or turning a style warning into a publication failure.

## What Is Checked

- PNG, including palette and RGB `tRNS` transparency, and supported JPEG, GIF,
  WebP, BMP, TIFF and AVIF images are decoded with Pillow. A PNG with an alpha
  channel whose values are all fully opaque passes the check.
- Animated raster images are inspected frame by frame within a fixed budget.
  A transparent frame is reported even if the first frame is opaque.
- Self-contained SVG and SVGZ images are rasterised with CairoSVG into a bounded
  viewport, with no supplied background colour. This samples the asset's own
  background; a CSS background behind the image in the page does not count.
- SVG embedded PNG/JPEG captures are supported. External resource loading is
  disabled. Dynamic SVG, masks, filters and unsupported resources are reported
  as unverifiable rather than assumed opaque.

SVG inspection is a raster sample at a maximum side of 1536 pixels, not proof of
opacity at every possible scale or under every SVG renderer. Raster inspection
allows up to 16 megapixels per frame, 32 frames and 64 million frame-pixels in
total. Files are limited to 32 MiB (8 MiB of SVG text), with a bounded project
batch, decoder CPU/memory limits and timeouts. Oversized, malformed, missing or
unsupported images produce explicit diagnostics.

## Source And Rendered Views

The default check inspects image references in published Markdown/HTML source,
public image metadata and configured content collections. Code examples and
comments are skipped. The source resolver follows the declared output of
computation, capture, Mermaid/PlantUML and Vega references, prefers the supported
author-edited override, and selects maintained language variants using the
normal default-language fallback.

The rendered-output check inspects HTML image references, including `srcset`,
posters and icon links. It catches assets contributed by layouts or metadata
that a static source projection cannot resolve. Remote, data-URL and
fragment-selected references are not fetched or silently certified; inspect a
local, self-contained output or review the exact rendered view.

Findings identify the image path and referring document, include the inspected
file hash when available, and name the authoritative source for generated
figures. Repeated references to one asset are grouped.

## Commands And MCP

These consumer commands are available from the modular wheel:

```bash
unaltraweb-mcp --project /path/to/site mcp image-background-check
unaltraweb-mcp --project /path/to/site mcp image-background-check --source assets/img/map.svg
unaltraweb-mcp --project /path/to/site mcp image-background-check --source _chapters/en/maps.md
unaltraweb-mcp --project /path/to/site mcp image-background-check --output-folder _site
```

The MCP tool is `image_background_check`, and the source report is also available
at `web://image-backgrounds`. `site_check` includes the source check;
`html_audit` adds the rendered check; the MCP PDF build returns source-image
advisories. CLI checks print image warnings to stderr, so the package scaffold's
normal build still surfaces them when its JSON output is redirected.

The reusable deployment workflow runs the packaged native checker before build
and against the output folder before upload. A native gem installation can use:

```bash
python /path/to/unaltraweb/scripts/image_background_check.py --project /path/to/site --output-folder _site
```

The checker requires Pillow, CairoSVG and the system Cairo library. The MCP image
and native deployment workflow install them. A missing decoder is reported as
unverifiable. A completed check with transparency warnings exits successfully;
an invalid inspection request or source inventory returns a nonzero exit status.

## Fixing A Warning

Choose a background colour in the authoritative source or export settings. For
example, Matplotlib exports can set `facecolor` and `transparent=False`, and
`ggsave` can set `bg`. An SVG can use an opaque full-viewport background shape
behind its artwork. Check the chosen text/background contrast on web and PDF.

Keep the decision with the author: opaque white is one choice, not a forced
default. Regenerate renderer-owned assets through their factory. Review an
existing `.edited.svg` or unmanaged image before changing it, and preserve
original captures and source material. The background check does not establish
generation freshness, attribution or permission to replace an asset.
