from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContentSearchJavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for content search tests")
    def test_occurrence_matcher(self) -> None:
        completed = subprocess.run(
            ["node", "--test", "test/js/content_search_test.js"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_search_markup_keeps_result_labels_distinct_from_panels(self) -> None:
        header = (ROOT / "_includes/header.liquid").read_text(encoding="utf-8")

        self.assertEqual(3, header.count("data-content-search-results-label="))
        self.assertEqual(3, header.count("data-content-search-results data-content-search-empty="))
        self.assertNotIn('data-content-search-results="{{', header)


if __name__ == "__main__":
    unittest.main()
