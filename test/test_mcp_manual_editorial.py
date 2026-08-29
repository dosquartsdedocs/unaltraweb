from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unaltraweb_mcp import mcp_server, site_tools


class ManualEditorialQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project / "_chapters/ca").mkdir(parents=True)
        (self.project / "context").mkdir()
        (self.project / "context/writing-profile.md").write_text("# Style\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_flags_non_publishable_metatext_but_skips_metadata_comments_and_code(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
content_status: approved
---

# Estat editorial

Tal com m'has demanat, he afegit aquesta explicació.

El camp content_status encara apareix al text.

<!-- TODO editorial que no es publica. -->

```yaml
content_status: approved
TODO: example
```
""",
            encoding="utf-8",
        )

        result = site_tools.manual_editorial_quality_check(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["files_checked"], 1)
        self.assertEqual(result["writing_profile"], "context/writing-profile.md")
        rules = {item["rule"] for item in result["findings"]}
        self.assertEqual(rules, {"editorial_scaffolding", "author_instruction_reference", "assistant_conversation", "workflow_status"})
        self.assertTrue(all(item["line"] not in {3, 12, 15, 16} for item in result["findings"]))

    def test_accepts_reader_facing_manual_prose(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
content_status: approved
---

# Fonts territorials

Una font oficial ha d'identificar l'organisme responsable, la data de referència i la unitat territorial abans de comparar-ne els valors.
""",
            encoding="utf-8",
        )

        result = site_tools.manual_editorial_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["findings"], [])

    def test_manual_writing_guidance_exposes_structure_and_callout_conventions(self) -> None:
        factory = Path(__file__).resolve().parents[1]

        guidance = mcp_server._manual_writing_guidance(self.project, factory)

        self.assertIn("`####` for a cohesive numbered local subsection", guidance)
        self.assertIn("`>>>>` warning", guidance)
        self.assertIn("Project-specific writing profile:\n\n# Style", guidance)
        self.assertIn("## Definition lists", guidance)
        self.assertIn("topic or reader goal", guidance)

    def test_exposes_paragraph_model_and_supported_components(self) -> None:
        (self.project / "_config.yml").write_text(
            "unaltraweb:\n  manual:\n    pdf:\n      enabled: true\n",
            encoding="utf-8",
        )
        (self.project / "assets/charts").mkdir(parents=True)
        (self.project / "assets/charts/bars.vl.json").write_text("{}\n", encoding="utf-8")
        (self.project / "assets/charts/network.vg.json").write_text("{}\n", encoding="utf-8")
        (self.project / "assets/captures").mkdir(parents=True)
        (self.project / "assets/captures/home.capture.yml").write_text("path: /\n", encoding="utf-8")
        (self.project / "assets/captures/detail.capture.yaml").write_text("path: /detail/\n", encoding="utf-8")
        (self.project / ".vegavisuals.yml").write_text("version: 1\n", encoding="utf-8")

        result = site_tools.manual_authoring_capabilities(self.project)

        self.assertTrue(result["pdf_enabled"])
        self.assertEqual(
            result["paragraph_structure"]["diagnostic_sequence"],
            ["topic_or_reader_goal", "problem_or_question", "arguments_and_examples", "discussion_or_limits", "concrete_closure_or_transition"],
        )
        components = {item["id"]: item for item in result["components"]}
        self.assertIn("#### numbered fourth-level subsection", components["heading_levels"]["syntax"])
        self.assertIn("h4 does not", components["heading_levels"]["web"])
        self.assertIn(">>>> warning", components["callouts"]["syntax"])
        self.assertEqual(components["definition_lists"]["pdf"], "supported as indented description entries with term colons")
        self.assertIn('data-figure-width="22rem"', components["figures"]["syntax"][1])
        self.assertIn("a+b/c", components["subfigures"]["syntax"][0])
        self.assertIn("before/after", components["subfigures"]["guidance"])
        self.assertIn("use the component selectively", components["subfigures"]["guidance"])
        self.assertIn("@startfiles", components["diagrams"]["guidance"])
        self.assertIn("between 8 pt and the 11 pt body size", components["diagrams"]["guidance"])
        self.assertIn(".vl.json", components["vega_visualizations"]["syntax"][0])
        self.assertIn(".vg.json", components["vega_visualizations"]["syntax"][1])
        self.assertIn("source -> output", components["vega_visualizations"]["syntax"][2])
        self.assertIn("#stable-heading", components["links_and_cross_references"]["syntax"][2])
        self.assertIn("distinct", components["links_and_cross_references"]["pdf"])
        self.assertIn("$x_i$", components["code_and_math"]["syntax"])
        self.assertIn("$\\eqref{eq:model}$", components["code_and_math"]["syntax"])
        self.assertIn("Rouge", components["code_and_math"]["web"])
        self.assertIn("listings", components["code_and_math"]["pdf"])
        self.assertIn("Do not use inline code", components["code_and_math"]["guidance"])

        inventory = site_tools.list_tools()
        self.assertIn("web://manual-authoring-components", inventory["resources"])
        self.assertIn("manual_structure_audit", inventory["prompts"])
        self.assertIn("manual_authoring_capabilities", inventory["tools"])
        self.assertIn("manual_computation_status", inventory["tools"])
        self.assertIn("manual_computation_render_figures", inventory["tools"])
        self.assertIn("executable_sources", components)
        self.assertIn("web_captures", components)
        self.assertIn("web_capture_check", result["quality_tools"])
        self.assertIn("visualization_check", result["quality_tools"])

        content = site_tools.content_inventory(self.project)
        self.assertEqual(content["visualization_manifest"], ".vegavisuals.yml")
        self.assertEqual(
            content["visualization_sources"],
            ["assets/charts/bars.vl.json", "assets/charts/network.vg.json"],
        )
        self.assertEqual(
            content["web_capture_sources"],
            ["assets/captures/detail.capture.yaml", "assets/captures/home.capture.yml"],
        )

    def test_source_quality_warns_about_fake_fourth_level_headings(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

**FAOSTAT.**

Publishable explanation.

![Portal](assets/img/portal.png "Captura pròpia, 11 d'agost de 2026.")
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["standalone_bold_labels"]), 1)
        self.assertIn("#### heading", result["standalone_bold_labels"][0]["message"])
        self.assertEqual(result["figures_without_title"], [])

    def test_source_quality_estimates_effective_pdf_diagram_text_size(self) -> None:
        diagrams = self.project / "assets/diagrams"
        diagrams.mkdir(parents=True)
        (diagrams / "compact.mmd").write_text("flowchart TB\n  A --> B\n", encoding="utf-8")
        (diagrams / "compact.mmd.svg").write_text(
            '<svg viewBox="0 0 400 700"><style>svg{font-size:18px}</style><text>Compact</text></svg>\n',
            encoding="utf-8",
        )
        (diagrams / "wide.mmd").write_text("flowchart TB\n  A --> B\n", encoding="utf-8")
        (diagrams / "wide.mmd.svg").write_text(
            '<svg viewBox="0 0 2000 700"><style>svg{font-size:18px}</style><text>Wide</text></svg>\n',
            encoding="utf-8",
        )
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

![Compact](assets/diagrams/compact.mmd "Compact diagram")

![Wide](assets/diagrams/wide.mmd "Wide diagram")
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        typography = result["diagram_typography"]
        self.assertEqual(typography["body_font_points"], 11.0)
        self.assertEqual([item["state"] for item in typography["references"]], ["oversized", "undersized"])
        self.assertEqual(len(typography["findings"]), 2)
        self.assertIn("8-11 pt", result["warnings"][-1]["message"])

    def test_source_quality_flags_diagram_that_is_too_tall_for_pdf(self) -> None:
        diagrams = self.project / "assets/diagrams"
        diagrams.mkdir(parents=True)
        (diagrams / "tall.mmd").write_text("flowchart TB\n  a --> b\n", encoding="utf-8")
        (diagrams / "tall.mmd.svg").write_text(
            '<svg viewBox="0 0 400 1200"><style>.node{font-size:16px}</style><text>Tall</text></svg>\n',
            encoding="utf-8",
        )
        (self.project / "_chapters/ca/chapter.md").write_text(
            "![Tall](assets/diagrams/tall.mmd \"Caption\"){: data-figure-width=\"30rem\"}\n",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        typography = result["diagram_typography"]
        self.assertEqual(typography["maximum_height_points"], 600.0)
        self.assertEqual(len(typography["references"]), 1)
        self.assertEqual(typography["references"][0]["state"], "too_tall")
        self.assertGreater(typography["references"][0]["estimated_pdf_height_points"], 600.0)
        self.assertEqual(len(typography["findings"]), 1)

    def test_source_quality_compares_static_svg_text_with_web_and_pdf_body_text(self) -> None:
        figures = self.project / "assets/img"
        figures.mkdir(parents=True)
        (figures / "map.svg").write_text(
            '<svg viewBox="0 0 1000 500"><style>.label{font-size:24px}</style><text class="label">Map</text></svg>\n',
            encoding="utf-8",
        )
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

![Map](assets/img/map.svg "Map caption"){: data-figure-width-web="40rem" data-figure-width-pdf="80%"}
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        typography = result["figure_typography"]
        self.assertEqual(typography["web_body_font_pixels"], 16.32)
        self.assertEqual(len(typography["references"]), 1)
        reference = typography["references"][0]
        self.assertEqual(reference["visual_kind"], "svg")
        self.assertEqual(reference["data_figure_width_web"], "40rem")
        self.assertEqual(reference["data_figure_width_pdf"], "80%")
        self.assertEqual(reference["web"]["state"], "ok")
        self.assertEqual(reference["pdf"]["state"], "ok")
        self.assertAlmostEqual(reference["web"]["font_to_body_ratio"], 0.941, places=3)
        self.assertIn("width", reference["suggested_dimensions"]["web"])
        self.assertIn("width", reference["suggested_dimensions"]["pdf"])

    def test_source_quality_accounts_for_subfigure_panel_widths(self) -> None:
        figures = self.project / "assets/img"
        figures.mkdir(parents=True)
        for name in ("a", "b", "c"):
            (figures / f"{name}.svg").write_text(
                '<svg viewBox="0 0 800 400"><style>text{font-size:24px}</style><text>Panel</text></svg>\n',
                encoding="utf-8",
            )
        (self.project / "_chapters/ca/chapter.md").write_text(
            """::: subfigures a+b/c "Comparison"
![A](assets/img/a.svg "A")
![B](assets/img/b.svg "B")
![C](assets/img/c.svg "C")
:::
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        references = result["figure_typography"]["references"]
        self.assertEqual([item["web_panel_width_factor"] for item in references], [0.49, 0.49, 1.0])
        self.assertEqual([item["pdf_panel_width_factor"] for item in references], [0.48, 0.48, 0.92])
        self.assertLess(references[0]["pdf"]["display_width_points"], references[2]["pdf"]["display_width_points"])

    def test_source_quality_audits_the_selected_localized_visual(self) -> None:
        (self.project / "_config.yml").write_text(
            "lang: en\ndefault_lang: en\nlanguages: [en, ca]\n",
            encoding="utf-8",
        )
        figures = self.project / "assets/img"
        figures.mkdir(parents=True)
        (figures / "map.svg").write_text(
            '<svg viewBox="0 0 800 400"><style>text{font-size:20px}</style><text>Map</text></svg>\n',
            encoding="utf-8",
        )
        (figures / "map.ca.svg").write_text(
            '<svg viewBox="0 0 800 400"><style>text{font-size:24px}</style><text>Mapa</text></svg>\n',
            encoding="utf-8",
        )
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
lang: ca
---

![Map](assets/img/map.svg "Map caption")
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        reference = result["figure_typography"]["references"][0]
        self.assertEqual(reference["source"], "assets/img/map.svg")
        self.assertEqual(reference["localized_source"], "assets/img/map.ca.svg")
        self.assertEqual(reference["output"], "assets/img/map.ca.svg")
        self.assertEqual(reference["source_minimum_font_pixels"], 24.0)

    def test_source_quality_warns_about_repeated_learning_objective_callouts(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

Chapter introduction.

>>>>> Chapter learning objectives are allowed near the opening.

## Data Access

Introductory prose.

>>>>> First objective block.

More prose.

>>>>> Second objective block in the same section.
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["learning_objective_callouts"]), 3)
        self.assertEqual(len(result["dense_learning_objective_callouts"]), 1)
        messages = [warning["message"] for warning in result["warnings"]]
        self.assertIn("Some learning-objective callouts are repeated or placed away from section openings.", messages)

    def test_source_quality_warns_when_objectives_replace_introduction(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

>>>>> Chapter objectives without prose.

## Data Access

>>>>> Section objectives without prose.
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["dense_learning_objective_callouts"]), 2)
        self.assertTrue(all(item["opening_blocks_before"] == 0 for item in result["dense_learning_objective_callouts"]))

    def test_source_quality_accepts_objectives_after_brief_introduction(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

Chapter context.

>>>>> Chapter learning objectives after prose.

## Data Access

Opening paragraph.

Second opening paragraph.

>>>>> Section objectives after a short introduction.
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["learning_objective_callouts"]), 2)
        self.assertEqual(result["dense_learning_objective_callouts"], [])

    def test_source_quality_warns_when_objectives_follow_subheading(self) -> None:
        (self.project / "_chapters/ca/chapter.md").write_text(
            """---
title: Chapter
---

## Data Access

Opening paragraph.

### Downloading

Subsection prose.

>>>>> Late objective block.
""",
            encoding="utf-8",
        )

        result = site_tools.manual_source_quality_check(self.project)

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["dense_learning_objective_callouts"]), 1)
        self.assertTrue(result["dense_learning_objective_callouts"][0]["after_subheading"])


if __name__ == "__main__":
    unittest.main()
