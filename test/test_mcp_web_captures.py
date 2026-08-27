from __future__ import annotations

import argparse
import os
import subprocess
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

    @patch("unaltraweb_mcp.site_tools._docker")
    @patch("unaltraweb_mcp.site_tools._capture_runtime_available", return_value=True)
    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_render_delegates_to_factory_isolated_workflow(self, run_factory_make, _runtime_available, docker) -> None:
        run_factory_make.return_value = {"ok": True}
        docker.return_value = subprocess.CompletedProcess([], 0, "", "")

        with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_ROOT": "/tmp/site", "UNALTRAWEB_MCP_IMAGE": "unaltraweb-mcp:test"}):
            site_tools.web_capture_render(
                Path("/tmp/site"),
                Path("/tmp/factory"),
                source="assets/captures/home.capture.yml",
                confirm_overwrite=True,
            )

        args, kwargs = run_factory_make.call_args
        self.assertEqual(args, (Path("/tmp/factory"), Path("/tmp/site").resolve(), "web-capture-render"))
        self.assertEqual(kwargs["env"]["WEB_CAPTURE_SOURCE"], "assets/captures/home.capture.yml")
        self.assertEqual(kwargs["env"]["WEB_CAPTURE_CONFIRM_OVERWRITE"], "1")
        self.assertTrue(kwargs["env"]["WEB_CAPTURE_BASE_URL"].startswith("http://unaltraweb-capture-site-"))
        self.assertTrue(kwargs["env"]["WEB_CAPTURE_DOCKER_NETWORK"].startswith("unaltraweb-capture-"))
        self.assertIn("WEB_CAPTURE_SERVICE_HOST", kwargs["env"])
        service_run = docker.call_args_list[1].args[0]
        self.assertIn("serve-capture-native", service_run)
        self.assertEqual(docker.call_args_list[-2].args[0][:2], ["rm", "-f"])
        self.assertEqual(docker.call_args_list[-1].args[0][:2], ["network", "rm"])

    @patch("unaltraweb_mcp.site_tools.run_make")
    @patch("unaltraweb_mcp.site_tools._capture_runtime_available", return_value=False)
    def test_render_uses_legacy_consumer_orchestration(self, _runtime_available, run_make) -> None:
        run_make.return_value = {"ok": True}

        site_tools.web_capture_render(Path("/tmp/site"), Path("/tmp/factory"))

        run_make.assert_called_once_with(Path("/tmp/site").resolve(), "web-capture-render", env={})

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
