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

Web rendering is fully styled. PDF output currently preserves these as blockquotes without equivalent labels or styling, so review both formats.

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

## Figure layouts

Use `subfigures` when panels form one comparison or explanation:

```markdown
::: subfigures a+b/c "Comparison of source, intermediate result, and final map"
![Source](assets/img/source.png "Source table")
![Intermediate](assets/img/intermediate.png "Joined layer")
![Result](assets/img/result.png "Final thematic map")
:::
```

`+` places panels in one row and `/` starts a new row. Web layout is supported. PDF layout is not yet equivalent, so inspect the PDF and use separate captioned figures when print composition matters.

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

## Citations, code, and math

Use verified bibliography keys:

```liquid
{% cite sourceKey %}
{% cite firstKey secondKey %}
```

Use ordinary fenced code with an explicit language. For mathematics in Markdown sources, use single dollar delimiters for inline expressions and double dollar delimiters on separate lines for display expressions. These forms survive the Jekyll Markdown pipeline and have the clearest web and PDF path:

```markdown
The density is $D_i=P_i/A_i$ for territory $i$.

$$
D_i = \frac{P_i}{A_i}
$$
```

Do not mark mathematical variables as inline code: `` `P_i` `` renders literally instead of typesetting the subscript. Do not use `\(...\)` directly in Markdown sources because Kramdown consumes those backslashes before MathJax runs.

## Web-only components

Tabs, details, interactive charts and maps, galleries, audio, video, and arbitrary Liquid figure includes can work in the browser but do not have general PDF parity. An assistant must not introduce them into a PDF-enabled manual without stating the limitation and reviewing both outputs.

## Required checks

Run these checks after drafting or structural revision:

```text
manual_source_quality_check
manual_editorial_quality_check
build_site
manual_pdf_build when PDF output is enabled
```

All body content must remain publishable. Keep author instructions, uncertainty, review notes, workflow status, and unresolved editorial decisions outside pages and chapters.
