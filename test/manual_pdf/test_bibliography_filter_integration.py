from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bibliography-filter"
FILTER = ROOT / "scripts" / "manual" / "filters" / "bibliography.lua"
BUILDER = ROOT / "scripts" / "manual" / "build_pdf.py"


@unittest.skipUnless(shutil.which("pandoc"), "Pandoc is supplied by the manual PDF image")
class BibliographyFilterIntegrationTests(unittest.TestCase):
    def test_numeric_csl_is_reordered_and_access_links_are_restored(self) -> None:
        spec = importlib.util.spec_from_file_location("unaltraweb_manual_pdf_integration", BUILDER)
        assert spec and spec.loader
        manual_pdf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manual_pdf)
        with tempfile.TemporaryDirectory() as directory:
            bibliography = Path(directory) / "bibliography.bib"
            manual_pdf.clean_bibliography(FIXTURE / "references.bib", bibliography)
            metadata = manual_pdf.extract_bibliography_metadata(FIXTURE / "references.bib", bibliography, ROOT)
            metadata.update({"nocite": "@*", "chapter-references-title": "References"})
            metadata_path = Path(directory) / "metadata.yml"
            metadata_path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")

            completed = subprocess.run(
                [
                    "pandoc",
                    str(FIXTURE / "source.md"),
                    "--from=markdown+fenced_divs",
                    f"--metadata-file={metadata_path}",
                    f"--bibliography={bibliography.with_suffix('.json')}",
                    f"--csl={FIXTURE / 'numeric.csl'}",
                    "--citeproc",
                    f"--lua-filter={FILTER}",
                    "--to=plain",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        output = completed.stdout
        agency_positions = [index for index in range(len(output)) if output.startswith("2. Agency title", index)]
        zulu_positions = [index for index in range(len(output)) if output.startswith("1. Zulu title", index)]
        self.assertEqual(2, len(agency_positions), output)
        self.assertEqual(2, len(zulu_positions), output)
        self.assertTrue(all(agency < zulu for agency, zulu in zip(agency_positions, zulu_positions)), output)
        self.assertEqual(2, output.count("https://example.test/agency"), output)
        self.assertEqual(2, output.count("https://doi.org/10.1234/zulu"), output)


if __name__ == "__main__":
    unittest.main()
