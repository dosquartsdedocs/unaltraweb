from __future__ import annotations

import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from unaltraweb_mcp import cli, site_tools
from unaltraweb_mcp.distribution import distribution_contract


class ManualReleaseMcpTests(unittest.TestCase):
    @patch("unaltraweb_mcp.site_tools.run_factory_make", return_value={"ok": True})
    def test_wrappers_use_fixed_targets_and_environment_selector(self, run_factory_make) -> None:
        project = Path("/tmp/manual-site")
        factory = Path("/tmp/factory")

        site_tools.manual_release_status(project, factory, selector="v2026.09.2")
        site_tools.manual_release_check(project, factory, selector="latest")
        prepared = site_tools.manual_release_prepare(project, factory)

        self.assertEqual(
            run_factory_make.call_args_list[0].args,
            (factory, project, "manual-release-status"),
        )
        self.assertEqual(run_factory_make.call_args_list[0].kwargs, {"env": {"MANUAL_RELEASE_SELECTOR": "v2026.09.2"}})
        self.assertEqual(run_factory_make.call_args_list[1].args, (factory, project, "manual-release-check"))
        self.assertEqual(
            run_factory_make.call_args_list[2].kwargs,
            {
                "env": {
                    "MANUAL_RELEASE_SELECTOR": "latest",
                    "MANUAL_RELEASE_DRY_RUN": "1",
                    "MANUAL_RELEASE_CONFIRM_PREPARE": "0",
                }
            },
        )
        self.assertTrue(prepared["ok"])

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_selector_injection_and_unconfirmed_prepare_never_reach_factory(self, run_factory_make) -> None:
        with self.assertRaises(ValueError):
            site_tools.manual_release_status(Path("/tmp/site"), Path("/tmp/factory"), selector="latest; id")
        with self.assertRaisesRegex(RuntimeError, "confirm_prepare=True"):
            site_tools.manual_release_prepare(Path("/tmp/site"), Path("/tmp/factory"), dry_run=False)
        run_factory_make.assert_not_called()

    def test_cli_check_and_prepare_propagate_failed_status(self) -> None:
        for command, tool in [
            ("manual-release-check", "manual_release_check"),
            ("manual-release-prepare", "manual_release_prepare"),
        ]:
            with self.subTest(command=command), patch("unaltraweb_mcp.cli.factory_dir", return_value=Path("/tmp/factory")), patch.object(
                cli.tools,
                tool,
                return_value={"ok": False, "error": "not current"},
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    returncode = cli.main(["--project", "/tmp/site", "mcp", command])
                self.assertEqual(returncode, 1)
                self.assertFalse(json.loads(output.getvalue())["ok"])

    @patch("unaltraweb_mcp.cli.factory_dir", return_value=Path("/tmp/factory"))
    @patch("unaltraweb_mcp.cli.tools.manual_release_prepare", return_value={"ok": True})
    def test_cli_prepare_defaults_to_dry_run_and_passes_confirmation(self, prepare, _factory_dir) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--project", "/tmp/site", "mcp", "manual-release-prepare"]), 0)
            self.assertEqual(
                cli.main(
                    [
                        "--project",
                        "/tmp/site",
                        "mcp",
                        "manual-release-prepare",
                        "--selector",
                        "v2026.09",
                        "--apply",
                        "--confirm-prepare",
                    ]
                ),
                0,
            )

        self.assertTrue(prepare.call_args_list[0].kwargs["dry_run"])
        self.assertFalse(prepare.call_args_list[0].kwargs["confirm_prepare"])
        self.assertFalse(prepare.call_args_list[1].kwargs["dry_run"])
        self.assertTrue(prepare.call_args_list[1].kwargs["confirm_prepare"])
        self.assertEqual(prepare.call_args_list[1].kwargs["selector"], "v2026.09")

    def test_tool_and_distribution_inventories_match(self) -> None:
        root = Path(__file__).resolve().parents[1]
        names = {"manual_release_status", "manual_release_check", "manual_release_prepare"}
        inventory = site_tools.list_tools()
        manifest = yaml.safe_load((root / "mcp-factory.yml").read_text(encoding="utf-8"))
        contract = distribution_contract()["wheel_contract"]

        self.assertTrue(names.issubset(inventory["tools"]))
        self.assertTrue(names.issubset(manifest["mcp"]["required_tools"]))
        self.assertTrue({name.replace("_", "-") for name in names}.issubset(contract["factory_required_mcp"]))
        self.assertEqual(set(manifest["mcp"]["required_tools"]), set(inventory["tools"]))
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        for target in ["manual-release-status", "manual-release-check", "manual-release-prepare", "mcp-manual-release-status", "mcp-manual-release-check", "mcp-manual-release-prepare"]:
            self.assertIn(f"{target}:", makefile)
        self.assertNotIn('git ', (root / "src/unaltraweb_mcp/manual_release.py").read_text(encoding="utf-8"))
        self.assertIn("manual-pdf-status: ## Inspect manual PDF configuration", makefile)
        self.assertIn("manual-pdf-check: ## Reject stale or unpublished", makefile)
        self.assertNotIn("manual-pdf-status: manual-pdf-preflight", makefile)
        self.assertNotIn("manual-pdf-check: manual-pdf-preflight", makefile)

    def test_make_selector_is_exported_without_recipe_interpolation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        makefile = (root / "Makefile").read_text(encoding="utf-8")

        self.assertIn("export MANUAL_RELEASE_SELECTOR", makefile)
        self.assertIn("override MANUAL_RELEASE_SELECTOR := $(value MANUAL_RELEASE_SELECTOR)", makefile)
        release_recipes = makefile[makefile.index("define run_manual_release_worker"):]
        self.assertNotIn("$(MANUAL_RELEASE_SELECTOR)", release_recipes)
        completed = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-n",
                "manual-release-status",
                "MCP_CONSUMER_WORKSPACE=/tmp/example",
                "MANUAL_RELEASE_SELECTOR=$(shell printf SELECTOR_EXPANDED >&2)",
            ],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("SELECTOR_EXPANDED", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
