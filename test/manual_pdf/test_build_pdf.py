from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "manual" / "build_pdf.py"
SPEC = importlib.util.spec_from_file_location("unaltraweb_manual_pdf", MODULE_PATH)
assert SPEC and SPEC.loader
manual_pdf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manual_pdf)


def write_markdown(path: Path, front: dict[str, object], body: str = "Body") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n\n{body}\n", encoding="utf-8")


class ManualPdfBuilderTests(unittest.TestCase):
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

    def test_sources_follow_weight_then_place_references_last(self) -> None:
        write_markdown(self.project / "_chapters/en/second.md", {"title": "Second", "lang": "en", "weight": 20})
        write_markdown(self.project / "_chapters/en/first.md", {"title": "First", "lang": "en", "weight": 10})
        write_markdown(self.project / "_chapters/en/reference.md", {"title": "Reference", "lang": "en", "weight": 5, "manual_numbered": False})
        write_markdown(self.project / "_chapters/en/web-only.md", {"title": "Web only", "lang": "en", "weight": 1, "pdf": False})

        _, chapters, source_lang = manual_pdf.manual_sources(self.project, self.config, "en")

        self.assertEqual(source_lang, "en")
        self.assertEqual([item[1]["title"] for item in chapters], ["First", "Second", "Reference"])

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
        self.assertIn("Table: A useful table", result)
        self.assertIn("![Detailed flow](assets/diagrams/flow.mmd.edited.svg)", result)

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

    def test_missing_translation_does_not_fall_back(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "English", "lang": "en", "weight": 10})
        self.config["unaltraweb"]["manual"]["pdf"]["languages"] = ["en", "es"]
        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "No manual chapters"):
            manual_pdf.manual_sources(self.project, self.config, "es")

    def test_cover_metadata_supports_multiple_localized_teaching_guides(self) -> None:
        self.config["unaltraweb"]["manual"]["metadata"] = {
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
        self.assertEqual(metadata["metadata-page-title"], "Manual details")

    def test_stale_manifest_cannot_be_published(self) -> None:
        write_markdown(self.project / "_chapters/en/chapter.md", {"title": "Chapter", "lang": "en", "weight": 10, "content_status": "approved"})
        paths = manual_pdf.artifact_paths(self.project, self.config, "en")
        paths["build_dir"].mkdir(parents=True)
        paths["pdf"].write_bytes(b"old pdf")
        paths["cover"].write_bytes(b"old cover")
        paths["manifest"].write_text('{"language":"en","fingerprint":"stale"}', encoding="utf-8")

        with self.assertRaisesRegex(manual_pdf.ManualPdfError, "latest source"):
            manual_pdf.publish_language(self.project, self.config, "en", True)

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
