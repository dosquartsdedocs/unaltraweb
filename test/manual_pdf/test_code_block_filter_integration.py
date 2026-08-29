from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTER = ROOT / "scripts" / "manual" / "filters" / "code-blocks.lua"
TEMPLATE = ROOT / "scripts" / "manual" / "templates" / "manual.tex"


@unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for Lua filter integration tests")
class CodeBlockFilterIntegrationTests(unittest.TestCase):
    def render(self, source: str) -> str:
        completed = subprocess.run(
            [
                "pandoc",
                "--from=markdown",
                "--to=latex",
                f"--lua-filter={FILTER}",
            ],
            input=source,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return completed.stdout

    def test_adds_language_header_and_line_numbers(self) -> None:
        output = self.render("```python\nprint('hello')\n```\n")

        self.assertIn(r"\begin{manualcode}[language=Python]{Python}", output)
        self.assertIn("print('hello')", output)
        self.assertIn(r"\end{manualcode}", output)

    def test_uses_localized_standard_label_for_unlabelled_code(self) -> None:
        output = self.render("---\nlang: ca\n---\n\n```\nplain\n```\n")

        self.assertIn(r"\begin{manualcode}{Codi}", output)
        self.assertIn(r"plain", output)

    def test_uses_configured_generic_label(self) -> None:
        output = self.render("---\ncode-block-label: Terminal output\n---\n\n```text\nplain\n```\n")

        self.assertIn(r"\begin{manualcode}{Terminal output}", output)

    def test_keeps_unknown_language_label_with_plain_listings_fallback(self) -> None:
        output = self.render("```javascript\nconst answer = 42;\n```\n")

        self.assertIn(r"\begin{manualcode}{JavaScript}", output)
        self.assertNotIn("language=JavaScript", output)

    def test_maps_supported_teaching_languages_to_listings(self) -> None:
        cases = {
            "bash": r"\begin{manualcode}[language=bash]{Bash}",
            "sql": r"\begin{manualcode}[language=SQL]{SQL}",
            "python": r"\begin{manualcode}[language=Python]{Python}",
            "r": r"\begin{manualcode}[language=R]{R}",
        }

        for language, expected in cases.items():
            with self.subTest(language=language):
                self.assertIn(expected, self.render(f"```{language}\nvalue <- 1\n```\n"))

    def test_preserves_explicit_start_number(self) -> None:
        output = self.render("```{.python startFrom=7}\nprint('hello')\n```\n")

        self.assertIn(r"\begin{manualcode}[language=Python,firstnumber=7]{Python}", output)

    @unittest.skipUnless(shutil.which("xelatex"), "XeLaTeX is required for PDF integration tests")
    def test_compiles_supported_languages_and_unicode_with_the_manual_template(self) -> None:
        source = """---
title: Code panels
author: Test author
short-title: Code panels
trailer-id: "00000000000000000000000000000000"
babel-lang: catalan
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
---

# Language support

```bash
curl -fsSL "https://example.test/api?comarca=Tarragonès&format=json"
```

```sql
SELECT municipi FROM indicadors WHERE poblacio > 10000;
```

```python
# Comprova la població.
print(dades["poblacio"])
```

```r
# Resumeix la població.
summary(municipis$poblacio)
```
"""
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "code-panels.pdf"
            completed = subprocess.run(
                [
                    "pandoc",
                    "--from=markdown",
                    "--standalone",
                    "--top-level-division=chapter",
                    "--number-sections",
                    f"--template={TEMPLATE}",
                    "--pdf-engine=xelatex",
                    f"--lua-filter={FILTER}",
                    f"--output={output}",
                ],
                input=source,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertGreater(output.stat().st_size, 0)
