from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import site_tools


class ManualPdfMcpTests(unittest.TestCase):
    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_build_uses_fixed_factory_target(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        site_tools.manual_pdf_build(project, factory, language="ca")

        run_factory_make.assert_called_once_with(factory, project, "manual-pdf-build", extra_args=["MANUAL_PDF_LANG=ca"])

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_publish_defaults_to_dry_run(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        result = site_tools.manual_pdf_publish(project, factory)

        self.assertTrue(result["dry_run"])
        run_factory_make.assert_called_once_with(factory, project, "manual-pdf-publish", extra_args=["MANUAL_PDF_PUBLISH_DRY_RUN=1"])

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_real_publish_requires_confirmation(self, run_factory_make) -> None:
        with self.assertRaisesRegex(RuntimeError, "confirm_publish=True"):
            site_tools.manual_pdf_publish(Path("/tmp/manual-site"), Path("/tmp/factory"), dry_run=False)
        run_factory_make.assert_not_called()


if __name__ == "__main__":
    unittest.main()
