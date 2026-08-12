from __future__ import annotations

import sys
import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import site_tools
from unaltraweb_mcp import cli


class ManualComputationsMcpTests(unittest.TestCase):
    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_status_uses_factory_make_with_consumer_project(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.manual_computation_status(Path("/tmp/site"), Path("/tmp/factory"), source="_chapters/en/chapter.qmd")

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "manual-compute-status",
            env={"COMPUTE_SOURCE": "_chapters/en/chapter.qmd"},
        )

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_render_requires_explicit_confirmation_for_first_overwrite(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.manual_computation_render(Path("/tmp/site"), Path("/tmp/factory"), confirm_overwrite=True)

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "manual-compute-render",
            env={"COMPUTE_CONFIRM_OVERWRITE": "1"},
        )

    def test_source_cannot_escape_project(self) -> None:
        with self.assertRaisesRegex(ValueError, "project-relative"):
            site_tools.manual_computation_status(Path("/tmp/site"), Path("/tmp/factory"), source="../outside.qmd")

    def test_source_rejects_make_expansion(self) -> None:
        with self.assertRaisesRegex(ValueError, "safe project-relative"):
            site_tools.manual_computation_status(Path("/tmp/site"), Path("/tmp/factory"), source="$(shell touch /tmp/pwned)")

    def test_factory_delegation_rejects_shell_substitution_in_project_path(self) -> None:
        with patch("unaltraweb_mcp.site_tools.project_path", side_effect=[Path("/tmp/factory"), Path("/tmp/`touch pwned`")]):
            with self.assertRaisesRegex(ValueError, "unsafe for Make delegation"):
                site_tools.run_factory_make(Path("/tmp/factory"), Path("/tmp/site"), "manual-compute-status")

    def test_factory_delegation_rejects_whitespace_in_project_path(self) -> None:
        with patch("unaltraweb_mcp.site_tools.project_path", side_effect=[Path("/tmp/factory"), Path("/tmp/My Site")]):
            with self.assertRaisesRegex(ValueError, "unsafe for Make delegation"):
                site_tools.run_factory_make(Path("/tmp/factory"), Path("/tmp/site"), "manual-compute-status")

    @patch("unaltraweb_mcp.cli.tools.manual_computation_check", return_value={"ok": False})
    def test_cli_check_returns_nonzero_when_make_check_fails(self, _check) -> None:
        args = argparse.Namespace(project="/tmp/site", mcp_command="manual-computation-check", source="")

        self.assertEqual(cli.cmd_mcp(args), 1)


if __name__ == "__main__":
    unittest.main()
