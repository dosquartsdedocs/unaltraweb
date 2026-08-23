# Manual authoring components

This is the component contract for MCP agents drafting or reviewing `unaltremanual` content. Read it together with the consumer site's `context/writing-profile.md`.

## Paragraph development

Diagnose paragraph function before polishing sentences. A paragraph should normally have one primary job and, when the material warrants it, develop this sequence:

1. Name the topic, object, or reader goal.
2. Establish the problem, question, uncertainty, or decision.
3. Develop the explanation through arguments, verified evidence, concrete examples, or worked operations.
4. Discuss meaning, alternatives, conditions, consequences, or limitations.
5. Close with a concrete takeaway, quality criterion, verification step, or transition.

Do not force every paragraph to contain all five moves. Use the sequence to diagnose missing logic. Improve paragraph structure before sentence style, separate evidence from interpretation, and do not invent examples or specificity merely to make prose appear concrete.

## Heading levels

Use heading levels semantically:

```markdown
## Numbered section
### Numbered subsection
#### Numbered fourth-level subsection
```

All three levels receive hierarchical numbers in the manual body. The secondary page TOC contains only `h2` and `h3`; `h4` remains a numbered local subdivision so the rail stays concise. Use `####` when a minor unit develops a cohesive idea, source, case, example, or operation through its own paragraph or paragraphs. Do not imitate a heading with a standalone bold phrase such as `**Source.**`; keep bold run-ins in the same paragraph they introduce.

## Callouts

Nested blockquote depth selects the callout type. The browser inserts the localized label, so do not repeat it manually.

```markdown
> Ordinary quotation

>> Note or tip

>>> Worked example

>>>> Warning

>>>>> Learning objectives

>>>>>> Caution or danger
```

Web and PDF rendering use the same callout type and localized label. The PDF uses a compact, breakable framed box so multi-paragraph notes and objective lists can continue across pages; review both formats for fit and emphasis.

Use `>>>>>` learning objectives sparingly, normally once after a short chapter or major-section introduction. They should orient the section after the reader has enough context, not replace the opening explanation, and they should not recur as mid-section reminders.

## Definition lists

Use definition lists for compact terminology that benefits from a dictionary-like presentation:

```markdown
Spatial reference system
: Rules and parameters used to interpret coordinates in a defined spatial framework.
```

The web renders the term with a colon and the definition as an indented entry. The PDF renders the same relationship as an indented description list. Definitions should support explanatory prose, not replace it.

## Figures

Use an explicit Markdown title as the caption:

```markdown
![Accessible description](assets/img/map.png "Distribution of the indicator by municipality")
```

Every teaching figure needs meaningful alt text and a caption. The manual numbers figures automatically on the web; the same image and caption are available to the PDF builder.

When the same width works on both supports, narrow and centre the complete figure container without setting a fixed height:

```markdown
![Project folders](assets/diagrams/folders.puml "Recommended project structure"){: data-figure-width="22rem"}
```

`data-figure-width` is a compatible shared fallback. When the web and printed page need different visible sizes, declare them independently:

```markdown
![Text-bearing map](assets/img/map.svg "Distribution by municipality"){: data-figure-width-web="44rem" data-figure-width-pdf="82%"}
```

The web value accepts a CSS width and remains limited by the reading column. The PDF value accepts a Pandoc length or percentage. Optional `data-figure-height-web` and `data-figure-height-pdf` values act as maximum constraints; width and height are always combined with the intrinsic aspect ratio, so the image is not stretched. Keep height automatic unless the support imposes a real limit.

After inserting or regenerating a text-bearing SVG figure or diagram, run `manual_source_quality_check`. It estimates the smallest visible SVG text at the declared web and PDF sizes, compares it with the surrounding body text, and returns separate suggested widths. Raster images do not expose dependable text metrics; use SVG for charts and diagrams when possible, and still inspect both rendered supports at final size.

For multilingual manuals, reference the default-language visual with an unsuffixed logical name. Add `.<lang>` immediately before the complete suffix only when the visual itself needs translation:

```text
map.svg              # default-language source
map.ca.svg           # Catalan static variant
boxplot.ca.qmd       # Catalan computation source
quarterly.ca.vl.json # Catalan Vega-Lite source
flow.ca.mmd          # Catalan Mermaid source
folders.ca.puml      # Catalan PlantUML source
```

Web and PDF first try the requested language and fall back to the unsuffixed default source when that variant is absent. If a localized source exists but its declared output is absent, stale, or invalid, fix that source lifecycle rather than silently using the default output. Localized computation and Vega sources must declare distinct localized outputs.

## Figure layouts

Use `subfigures` when panels form one direct comparison or explanation, such as before/after states, controlled alternatives, a short sequence, or complementary views that the reader needs to inspect together:

```markdown
::: subfigures a+b/c "Comparison of source, intermediate result, and final map"
![Source](assets/img/source.png "Source table")
![Intermediate](assets/img/intermediate.png "Joined layer")
![Result](assets/img/result.png "Final thematic map")
:::
```

`+` places panels in one row and `/` starts a new row. Prefer compact layouts such as `a+b` or `a+b/c`, write one caption that states the shared comparison, and give each panel a specific caption. This is a high-value teaching device when juxtaposition carries the argument, but it should remain selective: do not group images only because they share a topic, and avoid consecutive multi-panel figures that reduce emphasis or make evidence too small. Web and PDF preserve the declared rows, panel labels and captions; always inspect dense layouts at the final page size.

## Tables

Every teaching table must use a captioned block:

```markdown
::: table "Checks before joining a table to a layer"
| Check | Criterion |
| --- | --- |
| Key | Unique and stored with the same type |
| Coverage | Expected territories are represented |
:::
```

Bare pipe tables fail `manual_source_quality_check`. Captioned tables are numbered on the web and converted to Pandoc tables in the PDF.

## Diagrams

Store reusable sources under `assets/diagrams/` and reference them as captioned images:

```markdown
![Processing flow](assets/diagrams/flow.mmd "Processing flow from source to result")
![Project folders](assets/diagrams/folders.puml "Recommended project structure")
```

Use Mermaid `.mmd` for flows and PlantUML `.puml` or `.plantuml` for structured diagrams. Prefer PlantUML `@startfiles` for file trees. `diavisuals` generates the SVG; preserve an existing `*.edited.svg` unless the author explicitly approves replacement. Do not use inline Mermaid or PlantUML fences in manuals.

## Static Vega visualizations

Store Vega-Lite specifications as `*.vl.json` and raw Vega specifications as `*.vg.json`. Declare each source exactly once in `.vegavisuals.yml`, including its generated output, then reference the source as a normal captioned image:

```markdown
![Quarterly totals](assets/charts/quarterly.vl.json "Quarterly totals"){: data-figure-width-web="42rem" data-figure-width-pdf="78%"}
```

The web and PDF builders resolve the source through the manifest and use the same declared output. A source used as a web image must produce SVG or PNG; prefer SVG for web/PDF parity. Render with `make visualization-render`, commit the specification, output, manifest, and `.vegavisuals.lock.json`, and do not publish while `make visualization-check` or the companion `visualization_check` MCP tool reports stale, missing, unmanaged, or modified output. Reference a generated output directly when one source intentionally has multiple render variants.

## Web captures

Use a versioned `.capture.yml` recipe when a teaching figure must show a rendered website. The recipe stores a local preview path, viewport, theme, waits, declared inputs, and CSS selectors for annotations. Rendering creates:

```text
page.capture.yml
page.capture.png
page.capture.svg
page.capture.edited.svg  # optional author-owned override
```

Reference `page.capture.yml` as the captioned image source. Jekyll and the PDF builder prefer `page.capture.edited.svg` when it exists, otherwise `page.capture.svg`. The PNG is the untouched browser capture; annotations remain editable vector layers in the self-contained SVG. Never overwrite an edited SVG without approval, and do not publish while `web_capture_check` reports it stale.

## Computed figures

Use a computation source in `mode: figure` when a chapter must show a figure produced by R or Python code. Store the source under a configured `source_roots` directory (for example `assets/quarto/`), declare its outputs, and reference the source the same way you reference a diagram:

```markdown
![Alt text](assets/quarto/data-visualization/boxplot.qmd "Caption"){: data-figure-width-web="48rem" data-figure-width-pdf="88%"}
```

The source declares `mode: figure` and its generated assets:

```yaml
---
unaltraweb_compute:
  engine: r
  mode: figure
  outputs:
    - assets/img/data-visualization/boxplot-housing.svg
---
```

`make build` and `make serve` first render only stale figures (`manual-compute-render-figures`), then Jekyll rewrites the reference to the declared output. An author-owned override named like the output with `.edited.svg` (for example `boxplot-housing.edited.svg`) wins over the regenerated figure and is never overwritten. Keep figure outputs deterministic: regenerate them from the source instead of editing the generated SVG, and ask before replacing an existing `.edited.svg`.

## Citations, code, and math

Use verified bibliography keys:

```liquid
{% cite sourceKey %}
{% cite firstKey secondKey %}
```

Bibliographic citations, external URLs, and internal links are separate semantic categories in both outputs: citations use pink, external links use the external-link color, and links to headings or numbered equations use the internal-link color. Give headings stable explicit identifiers when another passage links to them:

```markdown
## Normalization {#normalization}

See [the normalization criteria](#normalization) and the [OGC standards](https://www.ogc.org/).
```

Use ordinary fenced code with an explicit language. Rouge highlights web code and Pandoc Skylighting highlights PDF code; inline code remains monospaced and visually distinct in both. Common identifiers include `bash`, `powershell`, `sql`, `python`, `r`, `haskell`, `javascript`, `yaml`, and `json`.

For mathematics in Markdown sources, use single dollar delimiters for inline expressions and double dollar delimiters on separate lines for displayed equations. Displayed equations are numbered by default on the web and in the PDF:

```markdown
The density is $D_i=P_i/A_i$ for territory $i$.

$$
D_i = \frac{P_i}{A_i}
\label{eq:density}
$$

Equation $\eqref{eq:density}$ defines density.
```

Add a stable `eq:` label inside a display block when the text needs to refer to it, then place `\eqref` inside inline-math delimiters so MathJax and LaTeX follow the same source. When a displayed expression explicitly does not need a number, opt out with `equation*`:

```markdown
\begin{equation*}
\bar{x}_w = \frac{\sum_i w_i x_i}{\sum_i w_i}
\end{equation*}
```

Do not place a label inside `equation*`, because an unnumbered expression has no stable equation number to retrieve. Do not mark mathematical variables as inline code: `` `P_i` `` renders literally instead of typesetting the subscript. Do not use `\(...\)` directly in Markdown sources because Kramdown consumes those backslashes before MathJax runs.

## Web-only components

Tabs, details, interactive charts and maps, galleries, audio, video, and arbitrary Liquid figure includes can work in the browser but do not have general PDF parity. An assistant must not introduce them into a PDF-enabled manual without stating the limitation and reviewing both outputs.

## Executable sources

When a `.qmd`, `.Rmd`, `.R`, `.py`, or `.ipynb` source owns a chapter, edit that source rather than its generated `.md`. Keep one R or Python engine per source, declare non-code inputs, render explicitly, and review source, Markdown, figures, and `.unaltraweb/computations.lock.json` together. Never publish while `manual_computation_check` reports stale output. For single figures, prefer `mode: figure` sources referenced from Markdown (see "Computed figures" above) instead of chapter-mode sources, because figure sources are rendered on `make build` and keep each figure reproducible on its own.

## Required checks

Run these checks after drafting or structural revision:

```text
manual_source_quality_check
manual_editorial_quality_check
manual_computation_check when executable sources exist
visualization_check when .vegavisuals.yml exists
build_site
manual_pdf_build when PDF output is enabled
```

All body content must remain publishable. Keep author instructions, uncertainty, review notes, workflow status, and unresolved editorial decisions outside pages and chapters.
