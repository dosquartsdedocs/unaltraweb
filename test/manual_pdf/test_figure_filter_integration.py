from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILTER = ROOT / "scripts" / "manual" / "filters" / "figure-captions.lua"


@unittest.skipUnless(shutil.which("pandoc"), "Pandoc is supplied by the manual PDF image")
class FigureFilterIntegrationTests(unittest.TestCase):
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
