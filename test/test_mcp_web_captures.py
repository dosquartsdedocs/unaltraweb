from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import cli, site_tools


class WebCapturesMcpTests(unittest.TestCase):
    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_status_delegates_to_fixed_factory_target(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.web_capture_status(Path("/tmp/site"), Path("/tmp/factory"), source="assets/captures/home.capture.yml")

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "web-capture-status",
            env={"WEB_CAPTURE_SOURCE": "assets/captures/home.capture.yml"},
        )

    @patch("unaltraweb_mcp.site_tools.run_make")
    def test_render_delegates_to_project_isolated_workflow(self, run_make) -> None:
        run_make.return_value = {"ok": True}

        site_tools.web_capture_render(
            Path("/tmp/site"),
            Path("/tmp/factory"),
            source="assets/captures/home.capture.yml",
            confirm_overwrite=True,
        )

        run_make.assert_called_once_with(
            Path("/tmp/site").resolve(),
            "web-capture-render",
            env={
                "WEB_CAPTURE_SOURCE": "assets/captures/home.capture.yml",
                "WEB_CAPTURE_CONFIRM_OVERWRITE": "1",
            },
        )

    def test_rejects_unsafe_source(self) -> None:
        for source in ["../outside.capture.yml", "$(shell touch /tmp/pwned).capture.yml", "assets/home.yml"]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                site_tools.web_capture_status(Path("/tmp/site"), Path("/tmp/factory"), source=source)

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_accepts_yaml_source_suffix(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.web_capture_status(Path("/tmp/site"), Path("/tmp/factory"), source="assets/captures/home.capture.yaml")

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "web-capture-status",
            env={"WEB_CAPTURE_SOURCE": "assets/captures/home.capture.yaml"},
        )

    @patch("unaltraweb_mcp.cli.tools.web_capture_check", return_value={"ok": False})
    def test_cli_check_returns_nonzero_when_stale(self, _check) -> None:
        args = argparse.Namespace(project="/tmp/site", mcp_command="web-capture-check", source="")

        self.assertEqual(cli.cmd_mcp(args), 1)

    def test_inventory_exposes_capture_tools(self) -> None:
        inventory = site_tools.list_tools()

        self.assertIn("web://web-captures", inventory["resources"])
        self.assertIn("web_capture_status", inventory["tools"])
        self.assertIn("web_capture_render", inventory["tools"])


if __name__ == "__main__":
    unittest.main()
