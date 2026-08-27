from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from unaltraweb_mcp import site_tools
from unaltraweb_mcp import cli


FACTORY_ROOT = Path(__file__).resolve().parents[1]


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

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_render_stale_only_sets_compute_stale_only(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.manual_computation_render(Path("/tmp/site"), Path("/tmp/factory"), stale_only=True, confirm_overwrite=True)

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "manual-compute-render",
            env={"COMPUTE_STALE_ONLY": "1", "COMPUTE_CONFIRM_OVERWRITE": "1"},
        )

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_render_figures_target_uses_recipe_command(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}

        site_tools.manual_computation_render_figures(Path("/tmp/site"), Path("/tmp/factory"))

        run_factory_make.assert_called_once_with(
            Path("/tmp/factory"),
            Path("/tmp/site"),
            "manual-compute-render-figures",
            env={},
        )

    def test_render_figures_core_target_exists_and_skips_stale_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            source = project / "_chapters/en/chapter.qmd"
            source.parent.mkdir(parents=True)
            source.write_text(
                """---
title: Stale chapter
lang: en
ref: stale-chapter
unaltraweb_compute:
  engine: python
---

Chapter source.
""",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    "make",
                    "--silent",
                    "--no-print-directory",
                    "-C",
                    str(FACTORY_ROOT),
                    "manual-compute-render-figures",
                    f"PROJECT={project}",
                    "COMPUTE_MODE=chapter",
                    "COMPUTE_STALE_ONLY=0",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["rendered_count"], 0)
            self.assertFalse(source.with_suffix(".md").exists())
            lock = json.loads((project / ".unaltraweb/computations.lock.json").read_text(encoding="utf-8"))
            self.assertEqual(lock["records"], {})

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

    @patch("unaltraweb_mcp.site_tools.run_process")
    def test_factory_delegation_accepts_spaces_in_project_path(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, '{"ok": true}', "")
        with patch("unaltraweb_mcp.site_tools.project_path", side_effect=[Path("/tmp/factory"), Path("/tmp/My Site")]):
            result = site_tools.run_factory_make(Path("/tmp/factory"), Path("/tmp/site"), "manual-compute-status")

        self.assertTrue(result["ok"])
        self.assertIn("PROJECT=/tmp/My Site", run.call_args.args[0])

    @patch("unaltraweb_mcp.site_tools.run_process")
    def test_factory_delegation_fails_closed_on_invalid_or_truncated_json(self, run) -> None:
        run.return_value = site_tools.ProcessResult(
            args=["make"],
            returncode=0,
            stdout='{"ok": true',
            stderr="",
            timed_out=False,
            stdout_truncated=False,
            stderr_truncated=False,
        )
        invalid = site_tools.run_factory_make(Path("/tmp/factory"), Path("/tmp/site"), "manual-compute-status")
        self.assertFalse(invalid["ok"])
        self.assertIn("invalid JSON", invalid["output_error"])

        run.return_value = site_tools.ProcessResult(
            args=["make"],
            returncode=0,
            stdout='{"ok": true}',
            stderr="",
            timed_out=False,
            stdout_truncated=True,
            stderr_truncated=False,
        )
        truncated = site_tools.run_factory_make(Path("/tmp/factory"), Path("/tmp/site"), "manual-compute-status")
        self.assertFalse(truncated["ok"])
        self.assertIn("truncated", truncated["output_error"])

    def test_factory_make_preserves_project_path_with_spaces(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "My Site"
            project.mkdir()

            completed = subprocess.run(
                ["make", "--silent", "--no-print-directory", "-C", str(root), "manual-compute-status", f"PROJECT={project}"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["project"], str(project))

    @patch("unaltraweb_mcp.cli.tools.manual_computation_check", return_value={"ok": False})
    def test_cli_check_returns_nonzero_when_make_check_fails(self, _check) -> None:
        args = argparse.Namespace(project="/tmp/site", mcp_command="manual-computation-check", source="")

        self.assertEqual(cli.cmd_mcp(args), 1)


if __name__ == "__main__":
    unittest.main()
