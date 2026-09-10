from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "scripts" / "manual" / "templates" / "manual.tex"


@unittest.skipUnless(
    all(shutil.which(command) for command in ("pandoc", "xelatex", "pdftotext")),
    "Pandoc, XeLaTeX, and pdftotext are required for PDF integration tests",
)
class ManualTemplateIntegrationTests(unittest.TestCase):
    def test_toc_separates_long_numbers_from_titles(self) -> None:
        source = r"""---
title: TOC number widths
author: Test author
short-title: TOC number widths
trailer-id: "00000000000000000000000000000000"
babel-lang: english
primary-color: "990000"
band-color: "990000"
secondary-color: "003366"
muted-color: "666666"
internal-link-color: "003366"
external-link-color: "990000"
citation-link-color: "C2185B"
inline-code-color: "6F2B70"
series: Test series
rights: Test rights
metadata-page-title: Metadata
toc-title: Contents
listing-label: Code example
list-of-figures-title: List of figures
list-of-tables-title: List of tables
list-of-listings-title: List of code examples
toc: true
---

# Short

## Brief

### Small

```{=latex}
\setcounter{chapter}{6}
```

# Seven

```{=latex}
\setcounter{section}{9}
```

## Surfaces

```{=latex}
\setcounter{chapter}{7}
```

# Eight

## Section

```{=latex}
\setcounter{subsection}{9}
```

### Save
"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "toc-number-widths.pdf"
            completed = subprocess.run(
                [
                    "pandoc",
                    "--from=markdown",
                    "--standalone",
                    "--toc",
                    "--top-level-division=chapter",
                    "--number-sections",
                    f"--template={TEMPLATE}",
                    "--pdf-engine=xelatex",
                    f"--output={output}",
                ],
                input=source,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertNotIn("Overfull \\hbox", completed.stderr)
            bbox = subprocess.run(
                ["pdftotext", "-bbox-layout", str(output), "-"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout

        root = ET.fromstring(bbox)
        namespace = {"x": "http://www.w3.org/1999/xhtml"}
        pages = root.findall(".//x:page", namespace)
        toc_page = next(
            page
            for page in pages
            if {"Brief", "Surfaces", "Save"}.issubset(
                {word.text for word in page.findall(".//x:word", namespace)}
            )
        )

        def toc_entry(number: str, title: str) -> tuple[ET.Element, ET.Element]:
            words = toc_page.findall(".//x:word", namespace)
            number_word = next((word for word in words if word.text == number), None)
            title_word = next((word for word in words if word.text == title), None)
            self.assertIsNotNone(number_word, f"TOC number {number} was not a separate word")
            self.assertIsNotNone(title_word, f"TOC title {title} was not a separate word")
            assert number_word is not None and title_word is not None
            self.assertAlmostEqual(
                float(number_word.attrib["yMin"]),
                float(title_word.attrib["yMin"]),
                delta=1.0,
            )
            return number_word, title_word

        chapter_number, chapter_title = toc_entry("8", "Eight")
        short_section_number, short_section_title = toc_entry("1.1", "Brief")
        section_number, section_title = toc_entry("7.10", "Surfaces")
        short_subsection_number, short_subsection_title = toc_entry("1.1.1", "Small")
        subsection_number, subsection_title = toc_entry("8.1.10", "Save")

        for number, title in (
            (chapter_number, chapter_title),
            (section_number, section_title),
            (subsection_number, subsection_title),
        ):
            gap = float(title.attrib["xMin"]) - float(number.attrib["xMax"])
            self.assertGreaterEqual(gap, 5.0)

        self.assertAlmostEqual(
            float(short_section_title.attrib["xMin"]),
            float(section_title.attrib["xMin"]),
            delta=1.0,
        )
        self.assertAlmostEqual(
            float(short_subsection_title.attrib["xMin"]),
            float(subsection_title.attrib["xMin"]),
            delta=1.0,
        )
