from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "manual" / "build_pdf.py"
TEMPLATE_PATH = MODULE_PATH.parent / "templates" / "manual.tex"
SPEC = importlib.util.spec_from_file_location("unaltraweb_manual_pdf", MODULE_PATH)
assert SPEC and SPEC.loader
manual_pdf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manual_pdf)


def write_markdown(path: Path, front: dict[str, object], body: str = "Body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n\n{body}\n", encoding="utf-8")


def write_computation_figure_source(path: Path, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = {
        "title": "Computed figure",
        "lang": "en",
        "ref": path.stem.lower(),
        "unaltraweb_compute": {"engine": "r" if path.suffix.lower() in {".r", ".rmd"} else "python", "mode": "figure", "outputs": [output]},
    }
    front_text = yaml.safe_dump(front, sort_keys=False).rstrip()
    suffix = path.suffix.lower()
    if suffix in {".qmd", ".rmd"}:
        text = f"---\n{front_text}\n---\n\nFigure source.\n"
    elif suffix == ".r":
        text = "#' ---\n" + "\n".join(f"#' {line}" for line in front_text.splitlines()) + "\n#' ---\n"
    elif suffix == ".py":
        text = "# ---\n" + "\n".join(f"# {line}" for line in front_text.splitlines()) + "\n# ---\n"
    else:
        text = json.dumps({"metadata": {"unaltraweb_front_matter": front}, "cells": [], "nbformat": 4, "nbformat_minor": 5})
    path.write_text(text, encoding="utf-8")


def write_vega_manifest(project: Path, visualizations: list[dict[str, object]]) -> None:
    manifest = {
        "version": 1,
        "profile": "vl-convert-1.9.0",
        "family": "benizar",
        "visualizations": visualizations,
    }
    (project / ".vegavisuals.yml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


class ManualPdfBuilderTests(unittest.TestCase):
    def test_template_distinguishes_captions_from_body_text(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\DeclareCaptionFont{manualcaption}{\sffamily\fontsize{9.4}{11.2}\selectfont}", template)
        self.assertIn(r"\DeclareCaptionFont{manualsubcaption}{\sffamily\fontsize{8.8}{10.5}\selectfont}", template)
        self.assertIn(r"\DeclareCaptionLabelFormat{manual}{\textcolor{ManualSecondary}{#1\nobreakspace #2}}", template)
        self.assertIn("font={manualcaption,color=ManualMuted}", template)
        self.assertIn("labelformat=manual", template)
        self.assertIn("format=hang", template)
        self.assertIn("justification=RaggedRight", template)
        self.assertIn(r"\captionsetup[figure]{position=top,margin=1em,aboveskip=0pt,belowskip=7pt}", template)
        self.assertIn("font={manualsubcaption,color=ManualMuted}", template)
        self.assertIn("labelfont={bf,sf,color=ManualSecondary}", template)

    def test_template_colors_complete_headings_and_keeps_chapter_number_with_title(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\titleformat{\chapter}[hang]", template)
        self.assertIn(r"{\thechapter.}{0.55em}{}", template)
        self.assertIn(r"\normalfont\sffamily\LARGE\bfseries\color{ManualSecondary}", template)
        self.assertIn(r"\titleformat{\section}", template)
        self.assertIn(r"\normalfont\Large\bfseries\color{ManualSecondary}", template)
        self.assertNotIn(r"\@chapapp", template)

    def test_template_distinguishes_link_categories_and_code(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"linkcolor=ManualInternalLink", template)
        self.assertIn(r"urlcolor=ManualExternalLink", template)
        self.assertIn(r"citecolor=ManualCitationLink", template)
        self.assertIn(r"\NewDocumentCommand\citeproctext{}{}", template)
        self.assertIn(r"\NewDocumentCommand\citeproc{mm}", template)
        self.assertNotIn("$highlighting-macros$", template)
        self.assertIn(r"\renewcommand{\texttt}[1]", template)

    def test_template_renders_breakable_code_and_plain_verbatim_panels(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\usepackage{listings}", template)
        self.assertIn(r"\usepackage{lstlinebgrd}", template)
        self.assertIn(r"\lstdefinestyle{manualbase}", template)
        self.assertIn(r"\lstdefinelanguage{ManualURL}", template)
        self.assertIn(r"\lstdefinelanguage{ManualSpreadsheet}", template)
        self.assertIn(r"\lstdefinelanguage{ManualFileTree}", template)
        self.assertIn(r"\lstdefinestyle{manualcode}", template)
        self.assertIn(r"\lstdefinestyle{manualverbatim}", template)
        self.assertIn("breaklines=true", template)
        self.assertIn("breakatwhitespace=false", template)
        self.assertIn("columns=fullflexible", template)
        self.assertIn(r"linebackgroundcolor=\ManualCodeLineBackground", template)
        self.assertIn("framexleftmargin=0pt", template)
        self.assertIn(r"\newtcblisting{manualcode}[2][]", template)
        self.assertIn(r"\newtcblisting{manualverbatim}", template)
        self.assertIn("colbacktitle=ManualSecondary", template)
        self.assertIn("listing engine=listings", template)
        self.assertIn("breakable,", template)
        self.assertNotIn(r"\hookrightarrow", template)

    def test_template_keeps_callouts_together_without_floating_figures_through_them(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        callout = template.split(r"\newenvironment{manualcallout}", 1)[1].split(r"\hypersetup", 1)[0]

        self.assertNotIn("breakable,", callout)
        self.assertIn(r"\newenvironment{manualcallout}[3][enhanced]", template)
        self.assertIn("colback=#2!6!white", template)
        self.assertIn(r"\color{#2}#3", template)
        self.assertIn(r"\floatplacement{figure}{H}", template)

    def test_template_avoids_stretched_pages_and_orphaned_headings(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\raggedbottom", template)
        self.assertIn(r"\clubpenalty=10000", template)
        self.assertIn(r"\widowpenalty=10000", template)
        self.assertIn(r"\pretocmd{\section}{\Needspace{6\baselineskip}}{}{}", template)
        self.assertIn(r"\setlength{\LTpre}{0.6em}", template)

    def test_template_keeps_figures_in_source_order(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\usepackage{float}", template)
        self.assertIn(r"\floatplacement{figure}{H}", template)

    def test_template_wraps_long_urls(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\usepackage{xurl}", template)
        self.assertLess(template.index(r"\usepackage{xurl}"), template.index(r"\usepackage{hyperref}"))

    def test_template_starts_home_chapter_at_zero_conditionally(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        conditional_offset = "$if(include-home)$\n\\setcounter{chapter}{-1}\n$endif$"
        self.assertIn(conditional_offset, template)
        self.assertLess(template.index(r"\mainmatter"), template.index(conditional_offset))

    def test_template_uses_recto_book_pagination(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\documentclass[11pt,a4paper,twoside,openright]{book}", template)
        self.assertIn(r"\usepackage{emptypage}", template)
        self.assertIn(r"\geometry{inner=25mm,outer=22mm,top=24mm,bottom=26mm}", template)
        self.assertIn(r"\fancyfoot[LE,RO]{\small\sffamily\thepage}", template)
        self.assertNotIn(r"\fancyfoot[C]", template)
        self.assertIn(r"\fancypagestyle{plain}", template)
        self.assertIn(r"\label{manual:toc-end}", template)
        self.assertIn(r"\renewcommand{\@schapter}", template)

    def test_template_renders_compact_editorial_credits(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn("$metadata-page-title$", template)
        self.assertIn("$metadata-publisher-label$", template)
        self.assertIn("$metadata-publication-date-label$", template)
        self.assertIn("$metadata-license-label$", template)
        self.assertIn("$metadata-rights-label$", template)
        self.assertNotIn(r"{\Huge\bfseries\sffamily\color{ManualSecondary}$metadata-page-title$}", template)

    def test_template_adds_localized_content_indexes_when_present(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(r"\renewcommand{\lstlistingname}{$listing-label$}", template)
        self.assertIn(r"\renewcommand{\listfigurename}{$list-of-figures-title$}", template)
        self.assertIn("$if(has-figures)$\n\\listoffigures", template)
        self.assertIn("$if(has-tables)$\n\\listoftables", template)
        self.assertIn("$if(has-listings)$\n\\lstlistoflistings", template)
        self.assertNotIn("--listings", template)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name).resolve()
        self.config = {
            "title": "Test Manual",
            "lang": "en",
            "default_lang": "en",
            "unaltraweb": {
                "site_profile": "unaltremanual",
                "manual": {
                    "collection": "chapters",
                    "bibliography": False,
                    "pdf": {
                        "enabled": True,
                        "languages": ["en"],
                        "output": "assets/pdf/manual-{lang}.pdf",
                        "cover_output": "assets/img/manual-{lang}.png",
                    },
                },
            },
        }
        (self.project / "_config.yml").write_text(yaml.safe_dump(self.config), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_empty_front_matter_is_removed_from_bibliography(self) -> None:
        source = self.project / "_bibliography/manual.bib"
        source.parent.mkdir(parents=True)
        source.write_text("---\n---\n\n@book{example, title={Example}}\n", encoding="utf-8")
        destination = self.project / "tmp/bibliography.bib"
        destination.parent.mkdir(parents=True)

        manual_pdf.clean_bibliography(source, destination)

        self.assertEqual("\n@book{example, title={Example}}\n", destination.read_text(encoding="utf-8"))

    def test_bibliography_source_rejects_a_path_in_the_filename_setting(self) -> None:
        self.config["unaltraweb"]["manual"].update({"bibliography": True, "bibliography_file": "../outside.bib"})

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "must be a .bib filename"):
            manual_pdf.bibliography_source(self.project, self.config)

    def test_bibliography_filter_metadata_uses_contributors_and_custom_urls(self) -> None:
        records = [
            {
                "id": "zulu",
                "author": [{"family": "Zulu", "given": "Ada"}],
                "issued": {"date-parts": [[2026]]},
                "title": "Last",
                "DOI": "10.1234/zulu",
            },
            {
                "id": "agency",
                "author": [{"literal": "Àrea Example"}],
                "issued": {"date-parts": [[2025]]},
                "title": "First",
                "URL": "https://example.test/standard",
            },
        ]

        metadata = manual_pdf.bibliography_filter_metadata(records, {"agency": ["https://example.test/agency"]})

        self.assertTrue(metadata["bibliography-sort-keys"]["agency"].startswith("area example | 2025"))
        self.assertTrue(metadata["bibliography-sort-keys"]["zulu"].startswith("zulu, ada | 2026"))
        self.assertEqual(metadata["bibliography-access"]["zulu"]["doi"], "10.1234/zulu")
        self.assertEqual(
            metadata["bibliography-access"]["agency"]["urls"],
            ["https://example.test/standard", "https://example.test/agency"],
        )

    def test_bibliography_custom_urls_reads_website_and_manual_url_fields(self) -> None:
        text = (
            "@book{first,\n  website = {https://example.test/first},\n  manual_url = {https://example.test/manual-first}\n}\n\n"
            "@book{second,\n  manual_url = \"https://example.test/second\"\n}\n"
        )

        self.assertEqual(
            manual_pdf.bibliography_custom_urls(text),
            {
                "first": ["https://example.test/first", "https://example.test/manual-first"],
                "second": ["https://example.test/second"],
            },
        )

    def test_bibliography_filter_metadata_deduplicates_doi_urls(self) -> None:
        records = [{"id": "article", "title": "Article", "DOI": "http://dx.doi.org/10.1234/article", "URL": "https://doi.org/10.1234/article"}]

        metadata = manual_pdf.bibliography_filter_metadata(records, {"article": ["http://dx.doi.org/10.1234/article"]})

        self.assertEqual(metadata["bibliography-access"]["article"], {"doi": "10.1234/article", "urls": []})
        self.assertEqual(manual_pdf.normalize_doi("https://doi.org/10.1234/article"), "10.1234/article")

    def write_fresh_artifacts(self) -> dict[str, Path]:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"})
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        paths["build_dir"].mkdir(parents=True)
        paths["pdf"].write_bytes(b"generated pdf")
        paths["cover"].write_bytes(b"generated cover")
        _, _, _, _, _, _, _, fingerprint = manual_pdf.prepare_build(self.project, self.config, "en")
        manifest = {
            "language": "en",
            "fingerprint": fingerprint,
            "release_selector": "latest",
            "release_channel": "latest",
            "pdf": str(paths["pdf"].relative_to(self.project)),
            "cover": str(paths["cover"].relative_to(self.project)),
            "public_pdf": str(paths["public_pdf"].relative_to(self.project)),
            "public_cover": str(paths["public_cover"].relative_to(self.project)),
            "artifacts": {
                "pdf": manual_pdf.file_signature(paths["pdf"]),
                "cover": manual_pdf.file_signature(paths["cover"]),
            },
        }
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        return paths

    def test_sources_follow_weight_then_place_references_last(self) -> None:
        write_markdown(self.project / "_chapters/en/second.md", {"title": "Second", "lang": "en", "weight": 20})
        write_markdown(self.project / "_chapters/en/first.md", {"title": "First", "lang": "en", "weight": 10})
        write_markdown(self.project / "_chapters/en/reference.md", {"title": "Reference", "lang": "en", "weight": 5, "manual_numbered": False})
        write_markdown(self.project / "_chapters/en/web-only.md", {"title": "Web only", "lang": "en", "weight": 1, "pdf": False})

        _, chapters, source_lang = manual_pdf.manual_sources(self.project, self.config, "en")

        self.assertEqual(source_lang, "en")
        self.assertEqual([item[1]["title"] for item in chapters], ["First", "Second", "Reference"])

    def test_assemble_offsets_chapters_only_when_home_is_included(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10})

        metadata, _, markdown = manual_pdf.assemble(
            self.project,
            self.config,
            "en",
            manual_pdf.artifact_paths(self.project, self.config, "en"),
        )

        self.assertFalse(metadata["include-home"])
        self.assertTrue(markdown.startswith("# Chapter"))

        write_markdown(
            self.project / "_pages/en/manual.md",
            {"title": "Manual", "lang": "en", "layout": "manual-home"},
            "Introduction body",
        )
        metadata, _, markdown = manual_pdf.assemble(
            self.project,
            self.config,
            "en",
            manual_pdf.artifact_paths(self.project, self.config, "en"),
        )

        self.assertTrue(metadata["include-home"])
        self.assertTrue(markdown.startswith("# Course introduction"))

        self.config["unaltraweb"]["manual"]["pdf"]["include_home"] = False
        metadata, _, markdown = manual_pdf.assemble(
            self.project,
            self.config,
            "en",
            manual_pdf.artifact_paths(self.project, self.config, "en"),
        )

        self.assertFalse(metadata["include-home"])
        self.assertTrue(markdown.startswith("# Chapter"))

    def test_transform_converts_tables_citations_and_diagrams(self) -> None:
        diagram = self.project / "assets/diagrams/flow.mmd"
        diagram.parent.mkdir(parents=True)
        diagram.write_text("flowchart LR", encoding="utf-8")
        Path(str(diagram) + ".edited.svg").write_text("<svg/>", encoding="utf-8")
        source = self.project / "_chapters/en/chapter.md"
        text = """{% cite one two %}

::: table "A useful table"
| A | B |
|---|---|
| 1 | 2 |
:::

![Flow]({{ site.baseurl }}/assets/diagrams/flow.mmd "Detailed flow")
"""

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertIn("[@one; @two]", result)
        self.assertIn(r"\Needspace{10\baselineskip}", result)
        self.assertIn("Table: A useful table", result)
        self.assertIn("![Detailed flow](assets/diagrams/flow.mmd.edited.svg)", result)

    def test_transform_converts_captioned_listing_to_a_pandoc_attribute(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = '''::: listing "Read a project's roads"
```python
print("roads")
```
:::'''

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertEqual(
            '```{.python data-listing-caption="Read a project\'s roads"}\nprint("roads")\n```',
            result,
        )

    def test_transform_rejects_listing_with_more_than_one_fence(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = '''::: listing "Two blocks"
```python
print(1)
```
```python
print(2)
```
:::'''

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "exactly one fenced code block"):
            manual_pdf.transform_markdown(self.project, text, source)

    def test_transform_preserves_listing_syntax_inside_a_code_example(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = '''````markdown
::: listing "Example"
```python
print(1)
```
:::
````'''

        self.assertEqual(text, manual_pdf.transform_markdown(self.project, text, source))

    def test_assemble_marks_available_content_indexes_and_localizes_titles(self) -> None:
        image = self.project / "assets/figure.svg"
        image.parent.mkdir(parents=True)
        image.write_text("<svg/>", encoding="utf-8")
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "weight": 10},
            '''![Figure](assets/figure.svg "Figure caption")

::: table "Table caption"
| A | B |
| --- | --- |
| 1 | 2 |
:::

::: listing "Listing caption"
```python
print(1)
```
:::''',
        )

        metadata, _, _ = manual_pdf.assemble(
            self.project,
            self.config,
            "en",
            manual_pdf.artifact_paths(self.project, self.config, "en"),
        )

        self.assertTrue(metadata["has-figures"])
        self.assertTrue(metadata["has-tables"])
        self.assertTrue(metadata["has-listings"])
        self.assertEqual("Code example", metadata["listing-label"])
        self.assertEqual("List of code examples", metadata["list-of-listings-title"])

        catalan = manual_pdf.build_metadata(self.project, self.config, "ca", "ca", {}, [])
        self.assertEqual("Codi", catalan["listing-label"])
        self.assertEqual("Índex de figures", catalan["list-of-figures-title"])
        self.assertEqual("Índex de taules", catalan["list-of-tables-title"])
        self.assertEqual("Índex de codis", catalan["list-of-listings-title"])

    def test_transform_starts_oversized_tables_on_a_fresh_page(self) -> None:
        rows = "\n".join(f"| Row {index} | " + ("Long cell text. " * 12) + "|" for index in range(18))
        text = f'''::: table "Large table"
| Item | Description |
| --- | --- |
{rows}
:::'''

        result = manual_pdf.transform_markdown(
            self.project,
            text,
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn("```{=latex}\n\\clearpage\n```", result)
        self.assertIn("Table: Large table", result)

    def test_transform_moves_table_page_guard_before_an_immediate_heading(self) -> None:
        text = '''## Review table

::: table "Compact table"
| Item | Description |
| --- | --- |
| One | Short description |
:::'''

        result = manual_pdf.transform_markdown(
            self.project,
            text,
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn("```{=latex}\n\\Needspace{16\\baselineskip}\n```\n\n## Review table", result)
        self.assertLess(result.index(r"\Needspace"), result.index("## Review table"))

    def test_transform_collects_unique_citation_keys_outside_code(self) -> None:
        citation_keys: list[str] = []
        source = self.project / "_chapters/en/chapter.md"
        text = """{% cite zeta alpha %}

```liquid
{% cite ignored %}
```

{% cite alpha beta %}
"""

        result = manual_pdf.transform_markdown(self.project, text, source, citation_keys=citation_keys)

        self.assertIn("[@zeta; @alpha]", result)
        self.assertEqual(["zeta", "alpha", "beta"], citation_keys)

    def test_transform_allows_apostrophes_in_double_quoted_image_titles(self) -> None:
        source = self.project / "_chapters/en/chapter.md"

        result = manual_pdf.transform_markdown(
            self.project,
            "![Knowledge cycle]({{ site.baseurl }}/assets/cycle.svg \"A project's knowledge cycle\")",
            source,
        )

        self.assertEqual("![A project's knowledge cycle](assets/cycle.svg)", result)

    def test_transform_converts_html_code_without_parsing_excel_references_as_math(self) -> None:
        result = manual_pdf.transform_markdown(
            self.project,
            "<code>=COUNTIF($A$2:$A$100,A2)&gt;1</code>",
            self.project / "_chapters/en/chapter.md",
        )

        self.assertEqual("`=COUNTIF($A$2:$A$100,A2)>1`", result)

    def test_transform_numbers_display_math_but_preserves_explicit_starred_equations(self) -> None:
        text = r"""$$
D_i = \frac{P_i}{A_i}
\label{eq:density}
$$

\begin{equation\*}
x + y = z
\end{equation\*}

```markdown
$$
This example stays literal.
$$
```"""

        result = manual_pdf.transform_markdown(
            self.project,
            text,
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn(r"\begin{equation}" + "\n" + r"D_i = \frac{P_i}{A_i}", result)
        self.assertIn(r"\label{eq:density}" + "\n" + r"\end{equation}", result)
        self.assertIn(r"\begin{equation*}" + "\n" + r"x + y = z" + "\n" + r"\end{equation*}", result)
        self.assertNotIn(r"equation\*", result)
        self.assertIn("```markdown\n$$\nThis example stays literal.\n$$\n```", result)

    def test_transform_converts_localized_callouts_for_latex(self) -> None:
        source = self.project / "_chapters/ca/chapter.md"
        text = """>>>> **Reviseu les dades.** No confongueu absència i zero.

>>>>> En acabar, cal poder validar el resultat.
>>>>>
>>>>> - Comproveu les unitats.
>>>>> - Documenteu la font.
"""

        result = manual_pdf.transform_markdown(self.project, text, source, "ca")

        self.assertIn(r"\begin{manualcallout}{ManualCalloutWarning}{ADVERTÈNCIA}", result)
        self.assertIn(r"\begin{manualcallout}{ManualCalloutObjectives}{OBJECTIUS D'APRENENTATGE}", result)
        self.assertIn("- Comproveu les unitats.", result)
        self.assertEqual(result.count(r"\end{manualcallout}"), 2)
        self.assertNotIn(">>>>", result)

    def test_transform_allows_oversized_callouts_to_continue(self) -> None:
        body = "\n".join(f">> This is long callout line {index}. " + ("More text. " * 8) for index in range(24))

        result = manual_pdf.transform_markdown(
            self.project,
            body,
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn(r"\begin{manualcallout}[enhanced,breakable]{ManualCalloutInfo}{NOTE}", result)

    def test_transform_uses_web_callout_i18n_customization(self) -> None:
        i18n = self.project / "_data/i18n/ca.yml"
        i18n.parent.mkdir(parents=True)
        i18n.write_text("callouts:\n  warning: AVÍS PERSONALITZAT\n", encoding="utf-8")
        source = self.project / "_chapters/ca/chapter.md"

        result = manual_pdf.transform_markdown(
            self.project,
            ">>>> Reviseu les dades.\n\n>>>>> Valideu el resultat.",
            source,
            "ca",
            self.config,
        )

        self.assertIn(r"\begin{manualcallout}{ManualCalloutWarning}{AVÍS PERSONALITZAT}", result)
        self.assertIn(r"\begin{manualcallout}{ManualCalloutObjectives}{OBJECTIUS D'APRENENTATGE}", result)

    def test_transform_falls_back_to_default_language_callout_customization(self) -> None:
        i18n = self.project / "_data/i18n/en.yml"
        i18n.parent.mkdir(parents=True)
        i18n.write_text("callouts:\n  warning: CUSTOM DEFAULT WARNING\n", encoding="utf-8")

        result = manual_pdf.transform_markdown(
            self.project,
            ">>>> Check the data.",
            self.project / "_chapters/fr/chapter.md",
            "fr-FR",
            self.config,
        )

        self.assertIn(r"\begin{manualcallout}{ManualCalloutWarning}{CUSTOM DEFAULT WARNING}", result)

    def test_callout_i18n_customization_is_a_build_dependency(self) -> None:
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "content_status": "approved"},
            ">>>> Check the data.",
        )
        i18n = self.project / "_data/i18n/en.yml"
        i18n.parent.mkdir(parents=True)
        i18n.write_text("callouts:\n  warning: FIRST WARNING\n", encoding="utf-8")

        _, _, markdown, _, _, _, dependencies, fingerprint = manual_pdf.prepare_build(
            self.project,
            self.config,
            "en",
        )

        self.assertIn(r"\begin{manualcallout}{ManualCalloutWarning}{FIRST WARNING}", markdown)
        self.assertIn(("source:_data/i18n/en.yml", i18n), dependencies)

        i18n.write_text("callouts:\n  warning: SECOND WARNING\n", encoding="utf-8")
        _, _, _, _, _, _, _, updated_fingerprint = manual_pdf.prepare_build(self.project, self.config, "en")
        self.assertNotEqual(fingerprint, updated_fingerprint)

    def test_transform_preserves_ordinary_blockquotes(self) -> None:
        source = self.project / "_chapters/en/chapter.md"

        result = manual_pdf.transform_markdown(self.project, "> Quoted source", source)

        self.assertEqual(result, "> Quoted source")

    def test_transform_preserves_vega_examples_inside_code(self) -> None:
        reference = "![Bars]({{site.baseurl}}/assets/charts/missing.vl.json)"
        text = f"```markdown\n{reference}\n```\n\nUse `{reference}` or <code>{reference}</code>."

        result = manual_pdf.transform_markdown(
            self.project,
            text,
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn(f"```markdown\n{reference}\n```", result)
        self.assertIn(f"`{reference}`", result)
        self.assertIn(f"or `{reference}`.", result)

    def test_resolves_computation_figure_references_for_every_supported_source(self) -> None:
        references: list[str] = []
        expected: list[str] = []
        for index, suffix in enumerate([".qmd", ".Rmd", ".R", ".py", ".ipynb"]):
            source_path = f"assets/quarto/figure-{index}{suffix}"
            output_path = f"assets/img/generated/figure-{index}.svg"
            write_computation_figure_source(self.project / source_path, output_path)
            output = self.project / output_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("<svg/>\n", encoding="utf-8")
            references.append(f'![Figure {index}]({source_path} "Caption {index}")')
            expected.append(f"![Caption {index}]({output_path})")

        result = manual_pdf.transform_markdown(
            self.project,
            "\n\n".join(references),
            self.project / "_chapters/en/chapter.md",
        )

        for reference in expected:
            self.assertIn(reference, result)

    def test_computation_figure_prefers_edited_svg_override(self) -> None:
        source = self.project / "assets/quarto/chart.qmd"
        output_path = "assets/img/generated/chart.png"
        write_computation_figure_source(source, output_path)
        output = self.project / output_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"generated png")
        edited = output.with_suffix(".edited.svg")
        edited.write_text("<svg/>\n", encoding="utf-8")

        result = manual_pdf.transform_markdown(
            self.project,
            '![Chart](assets/quarto/chart.qmd "Computed chart")',
            self.project / "_chapters/en/chapter.md",
        )

        self.assertIn("![Computed chart](assets/img/generated/chart.edited.svg)", result)

    def test_computation_figure_reports_missing_declared_output(self) -> None:
        source = self.project / "assets/quarto/chart.qmd"
        write_computation_figure_source(source, "assets/img/generated/missing.svg")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "Missing rendered figure .*manual-compute-render-figures"):
            manual_pdf.resolve_visual_source(self.project, "assets/quarto/chart.qmd")

    def test_computation_figure_output_cannot_escape_project(self) -> None:
        source = self.project / "assets/quarto/chart.qmd"
        write_computation_figure_source(source, "../outside.svg")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "project-relative"):
            manual_pdf.resolve_visual_source(self.project, "assets/quarto/chart.qmd")

    def test_resolves_vega_sources_and_drops_web_decoration_for_pdf(self) -> None:
        for name, source_suffix, output_suffix in [("bars", ".vl.json", ".svg"), ("network", ".vg.json", ".png")]:
            source = self.project / f"assets/charts/{name}{source_suffix}"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("{}\n", encoding="utf-8")
            output = self.project / f"assets/img/{name}{output_suffix}"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"generated")
        write_vega_manifest(
            self.project,
            [
                {"name": "bars", "source": "assets/charts/bars.vl.json", "output": "assets/img/bars.svg"},
                {"name": "network", "source": "assets/charts/network.vg.json", "output": "assets/img/network.png"},
            ],
        )
        source = self.project / "_chapters/en/chapter.md"
        text = '![Bars]({{ site.baseurl }}/assets/charts/bars.vl.json?v=4#view "Quarterly bars"){: #bars data-figure-width="42rem"}'

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertEqual('![Quarterly bars](assets/img/bars.svg){#bars width=70%}', result)
        self.assertEqual("assets/img/network.png", manual_pdf.resolve_visual_source(self.project, "assets/charts/network.vg.json"))

        template = self.project / "manual.tex"
        template.write_text("template", encoding="utf-8")
        dependencies = manual_pdf.build_dependencies(self.project, {}, [], result, template, None)
        self.assertIn(("asset:assets/img/bars.svg", self.project / "assets/img/bars.svg"), dependencies)
        self.assertIn(("toolchain:Dockerfile", manual_pdf.DEFAULT_DOCKERFILE), dependencies)

    def test_resolves_localized_visual_sources_with_default_fallback(self) -> None:
        for path in [
            "assets/img/map.svg",
            "assets/img/map.ca.svg",
            "assets/diagrams/flow.puml",
            "assets/diagrams/flow.puml.svg",
            "assets/diagrams/flow.ca.puml",
            "assets/diagrams/flow.ca.puml.svg",
        ]:
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("<svg/>" if path.endswith(".svg") else "@startuml\n@enduml\n", encoding="utf-8")

        self.assertEqual(
            "assets/img/map.ca.svg",
            manual_pdf.resolve_visual_source(
                self.project,
                "assets/img/map.svg",
                language="ca",
                default_language="en",
                languages=["en", "ca"],
            ),
        )
        self.assertEqual(
            "assets/diagrams/flow.ca.puml.svg",
            manual_pdf.resolve_visual_source(
                self.project,
                "assets/diagrams/flow.puml",
                language="ca",
                default_language="en",
                languages=["en", "ca"],
            ),
        )
        self.assertEqual(
            "assets/img/map.svg",
            manual_pdf.resolve_visual_source(
                self.project,
                "assets/img/map.svg",
                language="es",
                default_language="en",
                languages=["en", "es", "ca"],
            ),
        )
        self.assertEqual(
            "assets/img/map.ca.svg",
            manual_pdf.resolve_visual_source(
                self.project,
                "assets/img/map.ca.svg",
                language="ca",
                default_language="en",
                languages=["en", "ca"],
            ),
        )

    def test_transform_localizes_every_visual_source_family(self) -> None:
        static_default = self.project / "assets/img/map.svg"
        static_localized = self.project / "assets/img/map.ca.svg"
        static_default.parent.mkdir(parents=True, exist_ok=True)
        static_default.write_text("<svg/>", encoding="utf-8")
        static_localized.write_text("<svg/>", encoding="utf-8")

        write_computation_figure_source(self.project / "assets/quarto/plot.qmd", "assets/img/plot.svg")
        write_computation_figure_source(self.project / "assets/quarto/plot.ca.qmd", "assets/img/plot.ca.svg")
        (self.project / "assets/img/plot.svg").write_text("<svg/>", encoding="utf-8")
        (self.project / "assets/img/plot.ca.svg").write_text("<svg/>", encoding="utf-8")

        for source_name, output_name in [("bars.vl.json", "bars.svg"), ("bars.ca.vl.json", "bars.ca.svg")]:
            source = self.project / f"assets/charts/{source_name}"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("{}\n", encoding="utf-8")
            (self.project / f"assets/img/{output_name}").write_text("<svg/>", encoding="utf-8")
        write_vega_manifest(
            self.project,
            [
                {"name": "bars", "source": "assets/charts/bars.vl.json", "output": "assets/img/bars.svg"},
                {"name": "bars-ca", "source": "assets/charts/bars.ca.vl.json", "output": "assets/img/bars.ca.svg"},
            ],
        )

        for source_name in ("flow.puml", "flow.ca.puml"):
            source = self.project / f"assets/diagrams/{source_name}"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("@startuml\n@enduml\n", encoding="utf-8")
            Path(str(source) + ".svg").write_text("<svg/>", encoding="utf-8")

        for source_name in ("sidebar.capture.yml", "sidebar.ca.capture.yml"):
            source = self.project / f"assets/captures/{source_name}"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("path: /\n", encoding="utf-8")
            Path(str(source).rsplit(".", 1)[0] + ".svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>Capture</text></svg>',
                encoding="utf-8",
            )

        text = """![Static](assets/img/map.svg "Static")
![Computed](assets/quarto/plot.qmd "Computed")
![Vega](assets/charts/bars.vl.json "Vega")
![Diagram](assets/diagrams/flow.puml "Diagram")
![Capture](assets/captures/sidebar.capture.yml "Capture")
"""
        result = manual_pdf.transform_markdown(
            self.project,
            text,
            self.project / "_chapters/ca/chapter.md",
            language="ca",
            config={"lang": "en", "default_lang": "en", "languages": ["en", "ca"]},
        )

        self.assertIn("(assets/img/map.ca.svg)", result)
        self.assertIn("(assets/img/plot.ca.svg)", result)
        self.assertIn("(assets/img/bars.ca.svg)", result)
        self.assertIn("(assets/diagrams/flow.ca.puml.svg)", result)
        self.assertIn("(assets/captures/sidebar.ca.capture.svg)", result)

    def test_build_dependencies_ignores_image_syntax_in_code(self) -> None:
        image = self.project / "assets/img/real.svg"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_text("<svg/>", encoding="utf-8")
        template = self.project / "manual.tex"
        template.write_text("template", encoding="utf-8")
        markdown = """![Real](assets/img/real.svg)

```markdown
![Example](/assets/img/example.svg)
```

`![Inline example](/assets/img/inline.svg)`
"""

        dependencies = manual_pdf.build_dependencies(self.project, {}, [], markdown, template, None)

        self.assertIn(("asset:assets/img/real.svg", image), dependencies)
        self.assertFalse(any("example.svg" in label or "inline.svg" in label for label, _ in dependencies))

    def test_transform_converts_subfigures_and_print_widths(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = """::: subfigures a+b/c "Bars & `points` at 50%"
![Bars](assets/img/bars.svg "Ordered bars"){: data-figure-width=“54rem”}
![Points](assets/img/points.svg "Points on lines"){: data-figure-width="54rem"}
![Lines](assets/img/lines.svg "Trend lines")
:::

![Matrix](assets/img/matrix.svg "Visual matrix"){: #matrix data-figure-width="54rem"}
"""

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertNotIn("::: subfigures", result)
        self.assertNotIn("data-figure-width", result)
        self.assertNotIn("UNALTRAWEBMANUALPROTECTED", result)
        self.assertIn(r"\caption{Bars \& \texttt{points} at 50\%}", result)
        self.assertIn(r"{\color{ManualMuted!45}\rule{\linewidth}{0.35pt}}", result)
        self.assertLess(result.index(r"\caption{Bars"), result.index(r"\rule{\linewidth}{0.35pt}"))
        self.assertLess(result.index(r"\caption{Bars"), result.index(r"\begin{subfigure}"))
        self.assertIn(r"\begin{figure}[H]", result)
        self.assertEqual(result.count(r"\begin{subfigure}[t]{0.48\linewidth}"), 2)
        self.assertEqual(result.count(r"\begin{subfigure}[t]{0.92\linewidth}"), 1)
        self.assertEqual(result.count(r"\def\maxheight{0.26\textheight}"), 3)
        self.assertIn("![](assets/img/bars.svg)", result)
        first_row = next(line for line in result.splitlines() if "assets/img/bars.svg" in line)
        self.assertIn("assets/img/points.svg", first_row)
        self.assertNotIn("assets/img/lines.svg", first_row)
        self.assertIn(r"\caption{Ordered bars}", result)
        self.assertIn("![Visual matrix](assets/img/matrix.svg){#matrix width=90%}", result)

    def test_transform_uses_pdf_dimensions_and_discards_web_dimensions(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = (
            '![Map](assets/img/map.svg "Map")'
            '{: #map data-figure-width-web="44rem" data-figure-height-web="30rem" '
            'data-figure-width-pdf="82%" data-figure-height-pdf="420pt"}'
        )

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertEqual("![Map](assets/img/map.svg){#map width=82% height=420pt}", result)

    def test_transform_applies_pdf_dimensions_inside_subfigures(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        text = """::: subfigures a+b "Comparison"
![A](assets/img/a.svg "Panel A"){: data-figure-width-web="44rem" data-figure-width-pdf="84%"}
![B](assets/img/b.svg "Panel B"){: data-figure-height-pdf="300pt"}
:::
"""

        result = manual_pdf.transform_markdown(self.project, text, source)

        self.assertIn("![](assets/img/a.svg){width=84%}", result)
        self.assertIn("![](assets/img/b.svg){height=300pt}", result)
        self.assertNotIn("data-figure-width-web", result)

    def test_transform_rejects_malformed_subfigures(self) -> None:
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "contains no images"):
            manual_pdf.transform_markdown(
                self.project,
                '::: subfigures a+b "Missing panels"\nNo images.\n:::',
                self.project / "_chapters/en/chapter.md",
            )

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "declares 2 panels but contains 1 image"):
            manual_pdf.transform_markdown(
                self.project,
                '::: subfigures a+b "Missing panel"\n![Only](assets/img/only.svg "Only panel")\n:::',
                self.project / "_chapters/en/chapter.md",
            )

    def test_vega_source_requires_manifest_declaration_and_rendered_output(self) -> None:
        source = self.project / "assets/charts/bars.vl.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "Missing required Vega visualization manifest"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        write_vega_manifest(self.project, [])
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "not declared"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        write_vega_manifest(
            self.project,
            [{"name": "bars", "source": "assets/charts/bars.vl.json", "output": "assets/img/missing.svg"}],
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "Missing rendered Vega visualization output"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

    def test_vega_manifest_rejects_duplicate_sources_and_unsafe_paths(self) -> None:
        source = self.project / "assets/charts/bars.vl.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}\n", encoding="utf-8")
        write_vega_manifest(
            self.project,
            [
                {"name": "bars-svg", "source": "assets/charts/bars.vl.json", "output": "assets/img/bars.svg"},
                {"name": "bars-png", "source": "assets/charts/bars.vl.json", "output": "assets/img/bars.png"},
            ],
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "Duplicate Vega visualization source"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        write_vega_manifest(
            self.project,
            [{"name": "bars", "source": "assets/charts/bars.vl.json", "output": "../outside.svg"}],
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "project-relative"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "project-relative"):
            manual_pdf.resolve_visual_source(self.project, "../outside.vl.json")

    def test_vega_manifest_rejects_duplicate_yaml_keys_aliases_and_wrong_version(self) -> None:
        source = self.project / "assets/charts/bars.vl.json"
        source.parent.mkdir(parents=True)
        source.write_text("{}\n", encoding="utf-8")
        manifest = self.project / ".vegavisuals.yml"
        manifest.write_text(
            "version: 1\nversion: 1\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations: []\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "duplicate key"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        manifest.write_text(
            "version: 1\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations: &items []\nother: *items\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "YAML aliases are not allowed"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        manifest.write_text(
            "version: 2\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations: []\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "version must be 1"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

        manifest.write_text(
            "version: true\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations: []\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "version must be 1"):
            manual_pdf.resolve_visual_source(self.project, "assets/charts/bars.vl.json")

    def test_resolves_every_jekyll_diagram_extension(self) -> None:
        for suffix in [".mmd", ".mermaid", ".puml", ".plantuml", ".uml"]:
            with self.subTest(suffix=suffix):
                source = self.project / f"assets/diagrams/flow{suffix}"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("diagram source\n", encoding="utf-8")
                Path(str(source) + ".svg").write_text("<svg/>\n", encoding="utf-8")

                resolved = manual_pdf.resolve_visual_source(self.project, str(source.relative_to(self.project)))

                self.assertEqual(resolved, f"assets/diagrams/flow{suffix}.svg")

    def test_transform_prefers_edited_web_capture_svg(self) -> None:
        capture = self.project / "assets/captures/sidebar.capture.yml"
        capture.parent.mkdir(parents=True)
        capture.write_text("version: 1\npath: /en/\n", encoding="utf-8")
        Path(str(capture).removesuffix(".yml") + ".svg").write_text("<svg/>", encoding="utf-8")
        Path(str(capture).removesuffix(".yml") + ".edited.svg").write_text("<svg/>", encoding="utf-8")
        source = self.project / "_chapters/en/chapter.md"

        result = manual_pdf.transform_markdown(
            self.project,
            '![Sidebar]({{ site.baseurl }}/assets/captures/sidebar.capture.yml "Annotated sidebar")',
            source,
        )

        self.assertIn("![Annotated sidebar](assets/captures/sidebar.capture.edited.svg)", result)

    def test_transform_rejects_unsafe_edited_web_capture_svg(self) -> None:
        capture = self.project / "assets/captures/sidebar.capture.yml"
        capture.parent.mkdir(parents=True)
        capture.write_text("version: 1\npath: /en/\n", encoding="utf-8")
        Path(str(capture).removesuffix(".yml") + ".edited.svg").write_text(
            '<svg><style>@import url("https://example.com/x.css");</style></svg>',
            encoding="utf-8",
        )

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "(?:Unsafe|Unsupported) web capture SVG"):
            manual_pdf.transform_markdown(
                self.project,
                '![Sidebar](assets/captures/sidebar.capture.yml "Annotated sidebar")',
                self.project / "_chapters/en/chapter.md",
            )

    def test_unknown_liquid_fails_instead_of_dropping_content(self) -> None:
        source = self.project / "_chapters/en/chapter.md"
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "Unsupported Liquid"):
            manual_pdf.transform_markdown(self.project, "{% include unknown.liquid %}", source)

    def test_published_paths_cannot_escape_project(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"]["output"] = "../../manual.pdf"
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "project-relative"):
            manual_pdf.artifact_paths(self.project, self.config, "en")

    def test_pdf_and_cover_destinations_cannot_collide(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"]["cover_output"] = "assets/pdf/manual-{lang}.pdf"
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "cover path must use"):
            manual_pdf.artifact_paths(self.project, self.config, "en")

    def test_multilingual_pdf_and_cover_destinations_must_be_unique(self) -> None:
        pdf = self.config["unaltraweb"]["manual"]["pdf"]
        pdf["languages"] = ["en", "ca"]
        for key, path in [
            ("output", "assets/pdf/manual.pdf"),
            ("cover_output", "assets/img/manual-cover.png"),
        ]:
            with self.subTest(key=key):
                pdf[key] = path
                with self.assertRaisesRegex(
                    manual_pdf.ManualPdfError,
                    rf"destination collision: .*'en'.*'ca'.*{Path(path).name}",
                ):
                    manual_pdf.artifact_plan(self.project, self.config, manual_pdf.language_list(self.config, pdf))
                pdf[key] = "assets/pdf/manual-{lang}.pdf" if key == "output" else "assets/img/manual-{lang}.png"

    def test_duplicate_pdf_languages_are_rejected_as_destination_collisions(self) -> None:
        pdf = self.config["unaltraweb"]["manual"]["pdf"]
        pdf["languages"] = ["en", "en"]

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "destination collision"):
            manual_pdf.artifact_plan(self.project, self.config, manual_pdf.language_list(self.config, pdf))

    def test_single_language_paths_may_omit_language_placeholder(self) -> None:
        pdf = self.config["unaltraweb"]["manual"]["pdf"]
        pdf["output"] = "assets/pdf/manual.pdf"
        pdf["cover_output"] = "assets/img/manual-cover.png"

        plan = manual_pdf.artifact_plan(self.project, self.config, manual_pdf.language_list(self.config, pdf))

        self.assertEqual(plan[0][1]["public_pdf"], self.project / "assets/pdf/manual.pdf")
        self.assertEqual(plan[0][1]["public_cover"], self.project / "assets/img/manual-cover.png")

    def test_destination_collisions_fail_before_mutating_commands(self) -> None:
        pdf = self.config["unaltraweb"]["manual"]["pdf"]
        pdf["languages"] = ["en", "ca"]
        pdf["output"] = "assets/pdf/manual.pdf"
        (self.project / "_config.yml").write_text(yaml.safe_dump(self.config), encoding="utf-8")

        for command, operation_name in [
            ("build", "build_language"),
            ("publish", "publish_language"),
            ("sync", "sync_language"),
        ]:
            with self.subTest(command=command), patch.object(manual_pdf, operation_name) as operation:
                with redirect_stderr(io.StringIO()):
                    status = manual_pdf.main([command, "--project", str(self.project), "--language", "en"])
                self.assertEqual(status, 2)
                operation.assert_not_called()

        with redirect_stderr(io.StringIO()):
            status = manual_pdf.main(["public-paths", "--project", str(self.project), "--language", "en"])
        self.assertEqual(status, 2)

    def test_artifact_extensions_are_fixed(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"]["output"] = "assets/pdf/manifest.json"
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "PDF path must use"):
            manual_pdf.artifact_paths(self.project, self.config, "en")

    def test_language_cannot_escape_build_directory(self) -> None:
        for language in ["../outside", "/tmp/outside", "ca/es"]:
            with self.subTest(language=language), self.assertRaisesRegex(manual_pdf.ManualPdfError, "Invalid PDF language"):
                manual_pdf.artifact_paths(self.project, self.config, language)

    def test_requested_language_must_be_configured(self) -> None:
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "not enabled"):
            manual_pdf.language_list(self.config, self.config["unaltraweb"]["manual"]["pdf"], "es")

    @patch.object(manual_pdf.subprocess, "run")
    def test_commands_use_a_reproducible_build_environment(self, run: object) -> None:
        run.return_value.returncode = 0

        manual_pdf.run_command(["pandoc", "manual.md"], self.project)

        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["SOURCE_DATE_EPOCH"], "0")
        self.assertEqual(environment["FORCE_SOURCE_DATE"], "1")
        self.assertEqual(environment["TZ"], "UTC")

    def test_build_fingerprint_sets_xetex_trailer_id(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en"})

        metadata, _, _, template, _, _, _, fingerprint = manual_pdf.prepare_build(self.project, self.config, "en")

        self.assertRegex(metadata["trailer-id"], r"\A[0-9a-f]{32}\Z")
        self.assertEqual(metadata["trailer-id"], fingerprint[:32])
        self.assertIn(r"\special{pdf:trailerid [<$trailer-id$><$trailer-id$>]}", template.read_text(encoding="utf-8"))

    @patch.object(manual_pdf, "run_command")
    def test_build_canonicalizes_pdf_before_rendering_cover(self, run_command) -> None:
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "content_status": "approved"},
        )

        def create_outputs(command: list[str], _project: Path) -> None:
            if command[0] == "pandoc":
                output = next(Path(argument.split("=", 1)[1]) for argument in command if argument.startswith("--output="))
                output.write_bytes(b"raw pdf")
            elif command[0] == "qpdf":
                Path(command[-1]).write_bytes(b"normalized pdf")
            elif command[0] == "pdftoppm":
                Path(f"{command[-1]}.png").write_bytes(b"cover")

        run_command.side_effect = create_outputs

        manual_pdf.build_language(self.project, self.config, "en")

        commands = [call.args[0] for call in run_command.call_args_list]
        self.assertEqual([command[0] for command in commands], ["pandoc", "qpdf", "pdftoppm"])
        self.assertNotIn("--listings", commands[0])
        self.assertIn(f"--lua-filter={manual_pdf.DEFAULT_CODE_BLOCK_FILTER}", commands[0])
        self.assertIn(f"--lua-filter={manual_pdf.DEFAULT_FIGURE_FILTER}", commands[0])
        self.assertNotIn("--highlight-style=pygments", commands[0])
        self.assertIn("--deterministic-id", commands[1])
        self.assertIn("--object-streams=generate", commands[1])
        self.assertIn("--recompress-flate", commands[1])
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        self.assertEqual(paths["pdf"].read_bytes(), b"normalized pdf")

    def test_missing_translation_does_not_fall_back(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "English", "lang": "en", "weight": 10})
        self.config["unaltraweb"]["manual"]["pdf"]["languages"] = ["en", "es"]
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "No manual chapters"):
            manual_pdf.manual_sources(self.project, self.config, "es")

    def test_cover_metadata_supports_multiple_localized_teaching_guides(self) -> None:
        self.config["unaltraweb"]["manual"]["metadata"] = {
            "publisher": {"en": "Example Press", "ca": "Editorial Exemple"},
            "edition": {"en": "First digital edition", "ca": "Primera edició digital"},
            "publication_date": {"en": "August 22, 2026", "ca": "22 d'agost de 2026"},
            "identifier": "urn:isbn:9780000000000",
            "license": "CC BY 4.0",
            "source": "https://example.test/manual",
            "revision_date": {"en": "August 11, 2026", "ca": "11 d'agost de 2026"},
            "teaching_guides": [
                {"degree": {"en": "Geography", "ca": "Geografia"}, "subject_code": "GEO-01"},
                {"degree": {"en": "Tourism", "ca": "Turisme"}, "subject_code": "TOU-01"},
            ]
        }
        self.config["unaltraweb"]["manual"]["pdf"]["cover"] = {
            "primary_color": "112233",
            "band_color": "990000",
        }

        metadata = manual_pdf.build_metadata(self.project, self.config, "en", "en", {}, [])

        self.assertEqual(
            metadata["teaching-guides"],
            [
                {"degree": "Geography", "subject-code": "GEO-01"},
                {"degree": "Tourism", "subject-code": "TOU-01"},
            ],
        )
        self.assertEqual(metadata["band-color"], "990000")
        self.assertEqual(metadata["revision-date"], "August 11, 2026")
        self.assertEqual(metadata["publisher"], "Example Press")
        self.assertEqual(metadata["edition"], "First digital edition")
        self.assertEqual(metadata["publication-date"], "August 22, 2026")
        self.assertEqual(metadata["identifier"], "urn:isbn:9780000000000")
        self.assertEqual(metadata["license"], "CC BY 4.0")
        self.assertEqual(metadata["source"], "https://example.test/manual")
        self.assertEqual(metadata["metadata-page-title"], "Editorial credits")
        self.assertEqual(metadata["metadata-instructors-label"], "Authors")
        self.assertEqual(metadata["release-selector"], "latest")
        self.assertEqual(metadata["release-channel"], "latest")

    def test_release_selector_is_visible_and_changes_the_pdf_fingerprint(self) -> None:
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"},
        )
        _, _, _, _, _, _, _, latest = manual_pdf.prepare_build(self.project, self.config, "en")
        with patch.dict(manual_pdf.os.environ, {"UNALTRAWEB_MANUAL_RELEASE_SELECTOR": "v2026.09"}):
            metadata, _, _, _, _, _, _, stable = manual_pdf.prepare_build(self.project, self.config, "en")

        self.assertEqual(metadata["release-selector"], "v2026.09")
        self.assertEqual(metadata["release-channel"], "stable")
        self.assertNotEqual(latest, stable)
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("$metadata-release-channel-label$", template)
        self.assertIn("$metadata-release-version-label$", template)

    def test_pdf_metadata_separates_link_and_inline_code_colors(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"].update(
            {
                "internal_link_color": "1122AA",
                "external_link_color": "AA3300",
                "citation_link_color": "CC2277",
                "inline_code_color": "552266",
            }
        )

        metadata = manual_pdf.build_metadata(self.project, self.config, "en", "en", {}, [])

        self.assertTrue(metadata["link-citations"])
        self.assertEqual(metadata["internal-link-color"], "1122AA")
        self.assertEqual(metadata["external-link-color"], "AA3300")
        self.assertEqual(metadata["citation-link-color"], "CC2277")
        self.assertEqual(metadata["inline-code-color"], "552266")
        self.assertEqual(metadata["chapter-references-title"], "References")

    def test_assemble_marks_requested_chapter_references_for_pdf(self) -> None:
        self.config["unaltraweb"]["manual"]["bibliography"] = True
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "weight": 10, "manual_references": True},
            body="First {% cite zeta alpha %}, then {% cite alpha beta %}.",
        )

        _, _, markdown = manual_pdf.assemble(
            self.project,
            self.config,
            "en",
            manual_pdf.artifact_paths(self.project, self.config, "en"),
        )

        self.assertIn('::: {.manual-chapter-citations data-citations="zeta,alpha,beta"}', markdown)

    @patch.object(manual_pdf, "run_command")
    def test_pdf_passes_structured_sort_and_access_metadata_to_post_citeproc_filter(self, run_command) -> None:
        self.config["unaltraweb"]["manual"]["bibliography"] = True
        bibliography = self.project / "_bibliography/manual.bib"
        bibliography.parent.mkdir(parents=True)
        bibliography.write_text("@book{example, author={Example, A.}, title={Example}, year={2026}}\n", encoding="utf-8")
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "content_status": "approved"},
        )

        rendered_metadata: dict[str, object] = {}
        rendered_bibliography: list[dict[str, object]] = []

        def create_outputs(command: list[str], _project: Path) -> None:
            if command[0] == "pandoc" and "--to=csljson" in command:
                output = next(Path(argument.split("=", 1)[1]) for argument in command if argument.startswith("--output="))
                output.write_text(
                    json.dumps(
                        [
                            {
                                "id": "example",
                                "author": [{"family": "Example", "given": "A."}],
                                "issued": {"date-parts": [[2026]]},
                                "title": "Example",
                                "DOI": "http://dx.doi.org/10.1234/example",
                            }
                        ]
                    ),
                    encoding="utf-8",
                )
            elif command[0] == "pandoc":
                output = next(Path(argument.split("=", 1)[1]) for argument in command if argument.startswith("--output="))
                output.write_bytes(b"raw pdf")
                metadata_path = next(Path(argument.split("=", 1)[1]) for argument in command if argument.startswith("--metadata-file="))
                rendered_metadata.update(yaml.safe_load(metadata_path.read_text(encoding="utf-8")))
                bibliography_path = next(Path(argument.split("=", 1)[1]) for argument in command if argument.startswith("--bibliography="))
                rendered_bibliography.extend(json.loads(bibliography_path.read_text(encoding="utf-8")))
            elif command[0] == "qpdf":
                Path(command[-1]).write_bytes(b"normalized pdf")
            elif command[0] == "pdftoppm":
                Path(f"{command[-1]}.png").write_bytes(b"cover")

        run_command.side_effect = create_outputs

        manual_pdf.build_language(self.project, self.config, "en")

        pandoc_command = run_command.call_args_list[1].args[0]
        citeproc_index = pandoc_command.index("--citeproc")
        filter_argument = f"--lua-filter={manual_pdf.DEFAULT_BIBLIOGRAPHY_FILTER}"
        self.assertGreater(pandoc_command.index(filter_argument), citeproc_index)
        self.assertTrue(any(argument.endswith("bibliography.json") for argument in pandoc_command))
        self.assertIn("example", rendered_metadata["bibliography-sort-keys"])
        self.assertEqual(rendered_metadata["bibliography-access"]["example"]["doi"], "10.1234/example")
        self.assertEqual(rendered_metadata["bibliography-access"]["example"]["urls"], [])
        self.assertEqual(rendered_bibliography[0]["DOI"], "10.1234/example")

    def test_editorial_metadata_does_not_infer_optional_publication_fields(self) -> None:
        self.config["unaltraweb"]["manual"]["metadata"] = {
            "institution": "Example University",
            "revision_date": "August 11, 2026",
        }

        metadata = manual_pdf.build_metadata(self.project, self.config, "en", "en", {}, [])

        self.assertEqual(metadata["publisher"], "")
        self.assertEqual(metadata["publication-date"], "")
        self.assertEqual(metadata["identifier"], "")
        self.assertEqual(metadata["license"], "")
        self.assertEqual(metadata["source"], "")
        self.assertEqual(metadata["rights"], "")

    def test_stale_manifest_cannot_be_published(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"})
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        paths["build_dir"].mkdir(parents=True)
        paths["pdf"].write_bytes(b"old pdf")
        paths["cover"].write_bytes(b"old cover")
        paths["manifest"].write_text('{"language":"en","fingerprint":"stale"}', encoding="utf-8")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "latest source"):
            manual_pdf.publish_language(self.project, self.config, "en", True)

    def test_check_requires_published_artifacts_to_match_fresh_build(self) -> None:
        paths = self.write_fresh_artifacts()
        paths["public_pdf"].parent.mkdir(parents=True)
        paths["public_cover"].parent.mkdir(parents=True, exist_ok=True)
        paths["public_pdf"].write_bytes(b"old pdf")
        paths["public_cover"].write_bytes(b"old cover")

        status_output = io.StringIO()
        with redirect_stdout(status_output):
            status_code = manual_pdf.main(["status", "--project", str(self.project)])
        status = json.loads(status_output.getvalue())
        with redirect_stdout(io.StringIO()):
            check_code = manual_pdf.main(["check", "--project", str(self.project)])

        self.assertEqual(status_code, 0)
        self.assertTrue(status["ready_to_publish"])
        self.assertFalse(status["published_current"])
        self.assertEqual(check_code, 1)

        paths["public_pdf"].write_bytes(paths["pdf"].read_bytes())
        paths["public_cover"].write_bytes(paths["cover"].read_bytes())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(manual_pdf.main(["check", "--project", str(self.project)]), 0)

    def test_check_rejects_published_copy_of_stale_build(self) -> None:
        paths = self.write_fresh_artifacts()
        paths["public_pdf"].parent.mkdir(parents=True)
        paths["public_cover"].parent.mkdir(parents=True, exist_ok=True)
        paths["public_pdf"].write_bytes(paths["pdf"].read_bytes())
        paths["public_cover"].write_bytes(paths["cover"].read_bytes())
        write_markdown(
            self.project / "_chapters/en/chapter.md",
            {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"},
            body="Updated body",
        )

        with redirect_stdout(io.StringIO()):
            self.assertEqual(manual_pdf.main(["check", "--project", str(self.project)]), 1)

    @patch.object(manual_pdf, "build_language")
    def test_sync_publishes_fresh_artifacts_without_rebuilding(self, build_language) -> None:
        paths = self.write_fresh_artifacts()

        result = manual_pdf.sync_language(self.project, self.config, "en")

        build_language.assert_not_called()
        self.assertEqual(result["state"], "updated")
        self.assertFalse(result["built"])
        self.assertTrue(result["published"])
        self.assertEqual(paths["public_pdf"].read_bytes(), paths["pdf"].read_bytes())
        self.assertEqual(paths["public_cover"].read_bytes(), paths["cover"].read_bytes())

    @patch.object(manual_pdf, "build_language")
    @patch.object(manual_pdf, "publish_language")
    def test_sync_leaves_current_public_artifacts_unchanged(self, publish_language, build_language) -> None:
        paths = self.write_fresh_artifacts()
        paths["public_pdf"].parent.mkdir(parents=True)
        paths["public_cover"].parent.mkdir(parents=True, exist_ok=True)
        paths["public_pdf"].write_bytes(paths["pdf"].read_bytes())
        paths["public_cover"].write_bytes(paths["cover"].read_bytes())

        result = manual_pdf.sync_language(self.project, self.config, "en")

        build_language.assert_not_called()
        publish_language.assert_not_called()
        self.assertEqual(result["state"], "current")
        self.assertFalse(result["built"])
        self.assertFalse(result["published"])

    def test_sync_skips_projects_with_manual_pdf_disabled(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"]["enabled"] = False
        (self.project / "_config.yml").write_text(yaml.safe_dump(self.config), encoding="utf-8")
        output = io.StringIO()

        with redirect_stdout(output):
            status_code = manual_pdf.main(["sync", "--project", str(self.project)])

        self.assertEqual(status_code, 0)
        self.assertEqual(json.loads(output.getvalue())["skipped"], True)

    def test_public_paths_are_empty_when_manual_pdf_is_disabled(self) -> None:
        self.config["unaltraweb"]["manual"]["pdf"]["enabled"] = False
        (self.project / "_config.yml").write_text(yaml.safe_dump(self.config), encoding="utf-8")
        output = io.StringIO()

        with redirect_stdout(output):
            status_code = manual_pdf.main(["public-paths", "--project", str(self.project)])

        self.assertEqual(status_code, 0)
        self.assertEqual(json.loads(output.getvalue())["paths"], [])

    def test_tampered_artifact_cannot_be_published(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"})
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        paths["build_dir"].mkdir(parents=True)
        paths["pdf"].write_bytes(b"generated pdf")
        paths["cover"].write_bytes(b"generated cover")
        _, _, _, _, _, _, _, fingerprint = manual_pdf.prepare_build(self.project, self.config, "en")
        manifest = {
            "language": "en",
            "fingerprint": fingerprint,
            "release_selector": "latest",
            "release_channel": "latest",
            "pdf": str(paths["pdf"].relative_to(self.project)),
            "cover": str(paths["cover"].relative_to(self.project)),
            "public_pdf": str(paths["public_pdf"].relative_to(self.project)),
            "public_cover": str(paths["public_cover"].relative_to(self.project)),
            "artifacts": {
                "pdf": manual_pdf.file_signature(paths["pdf"]),
                "cover": manual_pdf.file_signature(paths["cover"]),
            },
        }
        paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
        paths["pdf"].write_bytes(b"tampered pdf")

        status = manual_pdf.status_language(self.project, self.config, "en")

        self.assertFalse(status["artifacts_valid"])
        self.assertFalse(status["ready_to_publish"])
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "latest source"):
            manual_pdf.publish_language(self.project, self.config, "en", True)

    @patch.object(manual_pdf, "run_command", side_effect=manual_pdf.ManualPdfError("render failed"))
    def test_failed_build_invalidates_previous_manifest(self, _run_command) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10})
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        paths["build_dir"].mkdir(parents=True)
        paths["pdf"].write_bytes(b"old pdf")
        paths["cover"].write_bytes(b"old cover")
        paths["manifest"].write_text('{"language":"en"}', encoding="utf-8")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "render failed"):
            manual_pdf.build_language(self.project, self.config, "en")

        self.assertFalse(paths["manifest"].exists())


if __name__ == "__main__":
    unittest.main()
