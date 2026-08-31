from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ThemeRuntimeTests(unittest.TestCase):
    def test_manual_styles_own_link_emphasis_and_mobile_code_wrapping(self) -> None:
        manual = (ROOT / "_sass/_manual.scss").read_text(encoding="utf-8")

        self.assertIn(".manual-content a", manual)
        self.assertIn("color: inherit", manual)
        self.assertIn('.container[role="main"] .manual-content code', manual)
        self.assertIn("overflow-wrap: anywhere", manual)
        self.assertIn(".manual-content .md-table code", manual)
        self.assertIn("white-space: normal", manual)

    def test_mathjax_defaults_include_manual_web_pdf_parity_macros(self) -> None:
        setup = (ROOT / "assets/js/mathjax-setup.js").read_text(encoding="utf-8")
        pseudocode_setup = (ROOT / "assets/js/pseudocode-setup.js").read_text(encoding="utf-8")
        scripts = (ROOT / "_includes/scripts.liquid").read_text(encoding="utf-8")
        config = (ROOT / "_config.yml").read_text(encoding="utf-8")

        self.assertIn('load: ["[tex]/cancel"]', setup)
        self.assertIn('cancel: "input/tex/extensions/cancel.js"', config)
        self.assertIn('tags: window.unaltrawebMathJaxTags || "all"', setup)
        for macro in ["cm", "mm", "m", "km", "cms", "squarekilometre", "hectare", "ha"]:
            self.assertIn(f"{macro}:", setup)
        self.assertIn("site.unaltraweb.mathjax.tags", scripts)
        self.assertNotIn("window.MathJax =", pseudocode_setup)
        self.assertLess(scripts.index("mathjax-setup.js"), scripts.index("page.pseudocode"))

    def test_redirect_pages_use_the_destination_as_canonical(self) -> None:
        head = (ROOT / "_includes/head.liquid").read_text(encoding="utf-8")

        self.assertIn("page.redirect == true", head)
        self.assertIn("unaltraweb_canonical_url = page.redirect", head)
        self.assertIn("unaltraweb_canonical_url | absolute_url", head)
        self.assertIn("unaltraweb_canonical_url | escape", head)

    def test_reading_metadata_is_escaped_before_rendering(self) -> None:
        layout = (ROOT / "_layouts/book-review.liquid").read_text(encoding="utf-8")
        card = (ROOT / "_includes/reading-cover-card.liquid").read_text(encoding="utf-8")
        controls = (ROOT / "_includes/reading-biblio-controls.liquid").read_text(encoding="utf-8")

        self.assertIn("localized_title | escape", layout)
        self.assertIn("localized_author | escape", layout)
        self.assertIn("doi_url | escape", layout)
        self.assertIn("item_title | escape", card)
        self.assertIn("item_author | escape", card)
        self.assertIn("biblio_doi_url | escape", controls)
        self.assertIn("biblio_url_https_prefix == 'https://'", controls)
        self.assertIn("| downcase", controls)

    def test_shared_page_metadata_escapes_html_and_serializes_json(self) -> None:
        metadata = (ROOT / "_includes/metadata.liquid").read_text(encoding="utf-8")
        default_layout = (ROOT / "_layouts/default.liquid").read_text(encoding="utf-8")

        self.assertIn("social_title | escape", metadata)
        self.assertIn("schema_headline | jsonify", metadata)
        self.assertIn("author_name | jsonify", metadata)
        self.assertIn("redirect_http_scheme == 'http://'", default_layout)
        self.assertIn("redirect_https_scheme == 'https://'", default_layout)


if __name__ == "__main__":
    unittest.main()
