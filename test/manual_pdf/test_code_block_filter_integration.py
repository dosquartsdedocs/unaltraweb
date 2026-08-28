from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTER = ROOT / "scripts" / "manual" / "filters" / "code-blocks.lua"


@unittest.skipUnless(shutil.which("pandoc"), "pandoc is required for Lua filter integration tests")
class CodeBlockFilterIntegrationTests(unittest.TestCase):
    def render(self, source: str) -> str:
        completed = subprocess.run(
            [
                "pandoc",
                "--from=markdown",
                "--to=latex",
                "--highlight-style=pygments",
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

        self.assertIn(r"\begin{manualcode}{Python}", output)
        self.assertIn(r"\begin{Highlighting}[numbers=left", output)
        self.assertIn(r"\BuiltInTok{print}", output)
        self.assertIn(r"\end{manualcode}", output)

    def test_uses_localized_standard_label_for_unlabelled_code(self) -> None:
        output = self.render("---\nlang: ca\n---\n\n```\nplain\n```\n")

        self.assertIn(r"\begin{manualcode}{Codi}", output)
        self.assertIn(r"\begin{Highlighting}[numbers=left", output)
        self.assertIn(r"plain", output)

    def test_uses_configured_generic_label(self) -> None:
        output = self.render("---\ncode-block-label: Terminal output\n---\n\n```text\nplain\n```\n")

        self.assertIn(r"\begin{manualcode}{Terminal output}", output)

    def test_preserves_explicit_line_numbering(self) -> None:
        output = self.render("```{.python .numberLines}\nprint('hello')\n```\n")

        self.assertIn(r"\begin{Highlighting}[numbers=left", output)
