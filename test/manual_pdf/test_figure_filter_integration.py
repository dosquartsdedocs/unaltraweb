from __future__ import annotations

import shutil
import importlib.util
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTER = ROOT / "scripts" / "manual" / "filters" / "figure-captions.lua"


@unittest.skipUnless(shutil.which("pandoc"), "Pandoc is supplied by the manual PDF image")
class FigureFilterIntegrationTests(unittest.TestCase):
    def test_subfigure_titles_keep_escaped_code_in_short_and_full_captions(self) -> None:
        spec = importlib.util.spec_from_file_location("caption_credits_demo", Path(__file__).with_name("caption_credits_demo.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        title = "Coverage 50% & result `value_name`"
        source = (f'::: subfigures a "{title}" {{: data-caption-source="Source: shared."}}\n'
                  f'![Panel](a.png "{title}"){{: data-caption-source="Source: panel."}}\n:::\n')
        transformed = demo.builder().transform_markdown(ROOT, source, ROOT / "chapter.md")
        latex = subprocess.run(
            ["pandoc", "--from=markdown+fenced_divs+pipe_tables+link_attributes", "--to=latex", f"--lua-filter={FILTER}"],
            input=transformed, text=True, capture_output=True, check=True,
        ).stdout
        short = re.findall(r"\\caption\[(.*?)\]", latex, re.S)
        self.assertEqual(len(short), 2, latex)
        for caption in short:
            self.assertIn(r"\texttt{value\_name}", caption)
            self.assertIn(r"50\% \&", caption)
            self.assertNotIn("Source:", caption)
        self.assertEqual(latex.count(r"\texttt{value\_name}"), 4, latex)
        self.assertNotIn("``", latex)

    def test_credit_citations_and_links_are_resolved_before_styling(self) -> None:
        source = '''---
references:
  - id: credit-ref
    type: book
    title: Fixture Reference
    author:
      - literal: Fixture Author
    issued:
      date-parts: [[2020]]
---
![Description [Source: [@credit-ref], [licence](https://example.org/credit).]{.uw-caption-source}](a.png)
'''
        result = subprocess.run(
            ["pandoc", "--from=markdown+link_attributes", "--to=latex", "--citeproc", f"--lua-filter={FILTER}"],
            input=source, text=True, capture_output=True, check=True,
        ).stdout
        self.assertNotIn("@credit-ref", result)
        self.assertIn("Fixture Author", result)
        self.assertIn(r"\href{https://example.org/credit}{licence}", result)
        short = re.search(r"\\caption\[(.*?)\]", result, re.S).group(1)
        self.assertEqual(short, "{Description}")

    def test_figure_and_table_credits_stay_out_of_short_captions(self) -> None:
        source = '''![Description [Source: figure-credit.]{.uw-caption-source}](a.png)

Table: Values [Source: table-credit.]{.uw-caption-source}

| A | B |
| --- | --- |
| 1 | 2 |
'''
        result = subprocess.run(
            ["pandoc", "--from=markdown+link_attributes", "--to=latex", f"--lua-filter={FILTER}"],
            input=source, text=True, capture_output=True, check=True,
        ).stdout
        short = re.findall(r"\\caption\[(.*?)\]", result, re.S)
        self.assertEqual(len(short), 2, result)
        self.assertTrue(any("Description" in value for value in short))
        self.assertTrue(any("Values" in value for value in short))
        self.assertFalse(any("credit" in value for value in short), result)
        self.assertIn(r"\itshape Source: figure-credit.", result)
        self.assertIn(r"\itshape Source: table-credit.", result)

    @unittest.skipUnless(all(shutil.which(name) for name in ("xelatex", "qpdf", "pdftotext", "pdftoppm", "rsvg-convert")), "Full manual PDF worker is required")
    def test_rendered_pdf_lists_exclude_credits_that_remain_in_body(self) -> None:
        spec = importlib.util.spec_from_file_location("caption_credits_demo", Path(__file__).with_name("caption_credits_demo.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        with tempfile.TemporaryDirectory() as directory:
            project = demo.prepare_demo(Path(directory) / "manual")
            chapter = project / "_chapters/ca/captions.md"
            chapter.write_text(chapter.read_text(encoding="utf-8") + '''
## Composició

::: subfigures a/b "Composició de dues vistes" {: data-caption-source="Font: crèdit compartit de la composició."}
![A](assets/img/caption-credits-demo.svg "Vista A"){: data-caption-source="Font: crèdit del panell."}
![B](assets/img/caption-credits-demo.svg "Vista B")
:::

::: table "A deliberately long caption used to exercise multiple lines before the header" {: data-caption-source="Source: a synthetic attribution long enough to continue onto another line so that the gap is measured from the final credit line rather than the first caption line."}
| MultilineKey | Value |
| --- | --- |
| A | 1 |
:::
''', encoding="utf-8")
            builder = demo.builder()
            manifest = builder.build_language(project, builder.read_yaml(project / "_config.yml"), "ca")
            self.assertIn("asset:assets/img/caption-credits-demo.svg", manifest["dependencies"])
            image = project / "assets/img/caption-credits-demo.svg"
            image.write_text(image.read_text(encoding="utf-8").replace("#315a75", "#315a76"), encoding="utf-8")
            self.assertNotEqual(builder.prepare_build(project, builder.read_yaml(project / "_config.yml"), "ca")[-1], manifest["fingerprint"])
            text = subprocess.run(["pdftotext", "-layout", str(project / manifest["pdf"]), "-"],
                                  text=True, capture_output=True, check=True).stdout
            bbox = subprocess.run(["pdftotext", "-bbox-layout", str(project / manifest["pdf"]), "-"],
                                  text=True, capture_output=True, check=True).stdout
        pages = [re.sub(r"\s+", " ", page) for page in text.split("\f")]
        for caption in ("Tres etapes connectades", "Valors de l'exemple", "Composició de dues vistes"):
            with self.subTest(caption=caption):
                matching = [page for page in pages if caption in page.replace("’", "'")]
                self.assertGreaterEqual(len(matching), 2, text)
                self.assertNotIn("Font:", matching[0], text)
                self.assertTrue(any("Font:" in page for page in matching[1:]), text)
        self.assertIn("crèdit del panell", " ".join(pages))
        namespace = {"x": "http://www.w3.org/1999/xhtml"}
        rendered_pages = ET.fromstring(bbox).findall(".//x:page", namespace)
        for header in ("Element", "Codi", "MultilineKey"):
            with self.subTest(table_header=header):
                page = next(page for page in rendered_pages if any(word.text == header for word in page.findall(".//x:word", namespace)))
                header_top = next(float(word.attrib["yMin"]) for word in page.findall(".//x:word", namespace) if word.text == header)
                lines = page.findall(".//x:line", namespace)
                caption_start = max(float(line.attrib["yMin"]) for line in lines
                                    if float(line.attrib["yMax"]) < header_top and any(word.text == "Taula" for word in line.findall("x:word", namespace)))
                caption_bottom = max(float(line.attrib["yMax"]) for line in lines
                                     if caption_start <= float(line.attrib["yMin"]) and float(line.attrib["yMax"]) < header_top)
                gap = header_top - caption_bottom
                self.assertGreaterEqual(gap, 12, f"Caption-to-header gap is cramped: {gap:.2f} pt")
                self.assertLessEqual(gap, 18, f"Caption-to-header gap wastes space: {gap:.2f} pt")

    def test_latex_figure_caption_precedes_image_and_preserves_label(self) -> None:
        completed = subprocess.run(
            [
                "pandoc",
                "--from=markdown+link_attributes",
                "--to=latex",
                f"--lua-filter={FILTER}",
            ],
            cwd=ROOT,
            input="![A readable caption](assets/img/example.png){#fig-example width=80%}\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn(r"\caption{A readable caption}\label{fig-example}", completed.stdout)
        self.assertLess(completed.stdout.index(r"\caption{"), completed.stdout.index(r"\includegraphics"))


if __name__ == "__main__":
    unittest.main()
