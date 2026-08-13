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
        self.assertIn("$x_i$", components["code_and_math"]["syntax"])
        self.assertIn("Do not use inline code", components["code_and_math"]["guidance"])

        inventory = site_tools.list_tools()
        self.assertIn("web://manual-authoring-components", inventory["resources"])
        self.assertIn("manual_structure_audit", inventory["prompts"])
        self.assertIn("manual_authoring_capabilities", inventory["tools"])
        self.assertIn("manual_computation_status", inventory["tools"])
        self.assertIn("executable_sources", components)

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


if __name__ == "__main__":
    unittest.main()
