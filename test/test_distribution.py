from __future__ import annotations

import io
import json
import os
import copy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unaltraweb_mcp import __version__, cli, site_tools
from unaltraweb_mcp.distribution import (
    component_contract_semantic_errors,
    component_reference,
    distribution_contract,
    distribution_doctor,
    is_mutable_reference,
    validate_component_contract,
)
from scripts.validate_distribution import publish_ref_errors


class DistributionTests(unittest.TestCase):
    def test_component_contract_covers_the_modular_release(self) -> None:
        contract = distribution_contract()

        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["release"]["version"], __version__)
        self.assertEqual(
            set(contract["components"]),
            {"gem", "wheel", "runtime", "mcp", "compute_python", "compute_r", "web_capture", "manual_pdf", "diavisuals", "vegavisuals"},
        )
        self.assertEqual(
            {name for name, value in contract["components"].items() if value["included_in_wheel"]},
            {"wheel"},
        )
        self.assertTrue(all(value["repository"].startswith("https://") for value in contract["components"].values()))
        self.assertEqual(contract["receipt_contract"]["input_inventory"], "exact")
        self.assertEqual(
            contract["receipt_contract"]["vegavisuals_dependencies"],
            ["manifest.inputs", "visualizations[].inputs", "spec.data.url"],
        )
        self.assertEqual(contract["receipt_contract"]["diavisuals_dependencies"], [])
        self.assertEqual(
            {contract["components"][name]["release_status"] for name in ["diavisuals", "vegavisuals"]},
            {"released"},
        )

    def test_doctor_reports_healthy_limited_wheel_mode(self) -> None:
        result = distribution_doctor()

        self.assertTrue(result["ok"])
        self.assertTrue(result["offline"])
        self.assertTrue(result["limited"])
        self.assertTrue(result["release_ready"])
        self.assertEqual(result["pending_releases"], [])
        self.assertEqual(result["unavailable_releases"], [])
        self.assertEqual(result["receipt_contract"]["input_inventory"], "exact")
        self.assertEqual(result["mode"], "wheel")
        self.assertIn("UW-DIST-WHEEL-MODE", {item["code"] for item in result["findings"]})
        for finding in result["findings"]:
            self.assertEqual(
                {"code", "severity", "expected", "actual", "remediation"},
                {key for key in finding if key != "component"},
            )

    def test_doctor_treats_unavailable_external_releases_as_not_release_ready(self) -> None:
        contract = distribution_contract()
        contract["components"]["vegavisuals"]["release_status"] = "unavailable"

        with patch("unaltraweb_mcp.distribution.distribution_contract", return_value=contract):
            result = distribution_doctor()

        self.assertTrue(result["ok"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["pending_releases"], [])
        self.assertEqual(result["unavailable_releases"], ["vegavisuals"])
        self.assertIn("UW-DIST-COMPANION-RELEASE-UNAVAILABLE", {item["code"] for item in result["findings"]})

    def test_doctor_inspects_only_features_selected_by_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            (project / "_config.yml").write_text(
                "theme: unaltraweb\nunaltraweb:\n  site_profile: unaltremanual\n  manual:\n    pdf:\n      enabled: true\n",
                encoding="utf-8",
            )
            (project / "Gemfile").write_text('gem "unaltraweb", "= 0.3.0"\n', encoding="utf-8")
            (project / "Gemfile.lock").write_text("DEPENDENCIES\n  unaltraweb (= 0.3.0)\n", encoding="utf-8")
            (project / "Makefile").write_text(f"MCP_IMAGE ?= {component_reference('mcp')}\n", encoding="utf-8")
            (project / ".unaltraweb").mkdir()
            (project / ".unaltraweb/computations.yml").write_text(
                "version: 1\nengines:\n  python:\n    image: registry.example/manual:main\n",
                encoding="utf-8",
            )
            (project / ".vegavisuals.yml").write_text("visualizations: []\n", encoding="utf-8")
            (project / "assets").mkdir()
            (project / "assets/home.capture.yml").write_text("id: home\n", encoding="utf-8")

            result = distribution_doctor(project=project)

        self.assertTrue(result["ok"])
        self.assertEqual(result["project"]["profile"], "unaltremanual")
        self.assertTrue(result["project"]["features"]["manual_computations"])
        self.assertTrue(result["project"]["features"]["web_captures"])
        self.assertTrue(result["project"]["features"]["manual_pdf"])
        self.assertTrue(result["project"]["features"]["vegavisuals"])
        self.assertIn("manual_pdf", result["selected_components"])
        self.assertIn("UW-DIST-PROJECT-MUTABLE-PIN", {item["code"] for item in result["findings"]})

    def test_new_manual_selects_factory_owned_python_and_r_workers(self) -> None:
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project) / "manual"
            site_tools.new_web(project, site_profile_value="unaltremanual")

            result = distribution_doctor(project=project)

        self.assertTrue(result["ok"], result["findings"])
        self.assertTrue(result["project"]["features"]["manual_computations"])
        self.assertIn("compute_python", result["selected_components"])
        self.assertIn("compute_r", result["selected_components"])
        self.assertEqual(result["docker"]["images"]["compute_python"], component_reference("compute_python"))
        self.assertEqual(result["docker"]["images"]["compute_r"], component_reference("compute_r"))

    def test_factory_doctor_enforces_companion_lifecycle_and_capabilities(self) -> None:
        root = Path(__file__).resolve().parents[1]

        result = distribution_doctor(factory=root)
        companion_findings = [item for item in result["findings"] if item.get("component") in {"diavisuals", "vegavisuals"}]

        self.assertTrue(result["ok"], companion_findings)
        codes = {item["code"] for item in companion_findings}
        self.assertIn("UW-DIST-COMPANION-LIFECYCLE", codes)
        self.assertIn("UW-DIST-COMPANION-INSTALL-SPEC", codes)
        self.assertIn("UW-DIST-COMPANION-CAPABILITIES", codes)
        self.assertTrue(all(item["severity"] == "info" for item in companion_findings))

    def test_docker_doctor_only_inspects_local_images(self) -> None:
        root = Path(__file__).resolve().parents[1]
        commands: list[list[str]] = []

        def completed(command, **_kwargs):
            commands.append(command)
            if command[1] == "version":
                return subprocess.CompletedProcess(command, 0, "27.0.0\n", "")
            return subprocess.CompletedProcess(command, 1, "", "No such image")

        with patch("unaltraweb_mcp.distribution.shutil.which", return_value="/usr/bin/docker"), patch(
            "unaltraweb_mcp.distribution.run_process", side_effect=completed
        ):
            result = distribution_doctor(factory=root, check_docker=True)

        self.assertTrue(result["ok"], result["findings"])
        self.assertTrue(result["docker"]["checked"])
        self.assertTrue(any(command[1:3] == ["image", "inspect"] for command in commands))
        self.assertTrue(all("pull" not in command and "build" not in command for command in commands))

    def test_cli_package_inspection_does_not_require_factory(self) -> None:
        with tempfile.TemporaryDirectory(), patch.dict(os.environ, {}, clear=True), patch(
            "unaltraweb_mcp.cli.find_factory_dir", return_value=None
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                returncode = cli.main(["mcp", "list-tools"])
            inventory = json.loads(output.getvalue())
            self.assertEqual(returncode, 0)
            self.assertIn("distribution_doctor", inventory["tools"])

            with self.assertRaisesRegex(SystemExit, "requires the unaltraweb factory checkout"):
                cli.main(["mcp", "prompts"])

    def test_factory_discovery_rejects_an_unrelated_factory_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unrelated = root / "diavisuals"
            empty = root / "installed-wheel"
            unrelated.mkdir()
            empty.mkdir()
            manifest = unrelated / "mcp-factory.yml"
            manifest.write_text("name: diavisuals\n", encoding="utf-8")

            with patch.dict(os.environ, {"UNALTRAWEB_FACTORY_DIR": str(unrelated)}, clear=True), patch(
                "unaltraweb_mcp.cli.Path.cwd", return_value=unrelated
            ), patch("unaltraweb_mcp.cli.source_root", return_value=empty):
                self.assertIsNone(cli.find_factory_dir())
                manifest.write_text("name: unaltraweb\n", encoding="utf-8")
                self.assertEqual(cli.find_factory_dir(), unrelated.resolve())

    def test_cli_build_site_propagates_failed_ok_status(self) -> None:
        output = io.StringIO()
        with patch("unaltraweb_mcp.cli.factory_dir", return_value=Path("/tmp/factory")), patch(
            "unaltraweb_mcp.cli.tools.build_site",
            return_value={"ok": False, "returncode": 0, "error": "HTML audit failed"},
        ), redirect_stdout(output):
            returncode = cli.main(["--project", "/tmp/site", "mcp", "build-site"])

        self.assertEqual(returncode, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_wheel_contract_inventory_matches_every_cli_mcp_command(self) -> None:
        parser = cli.build_parser()
        top_subparsers = next(action for action in parser._actions if hasattr(action, "choices") and action.choices)
        mcp_parser = top_subparsers.choices["mcp"]
        mcp_subparsers = next(action for action in mcp_parser._actions if hasattr(action, "choices") and action.choices)
        actual = set(mcp_subparsers.choices)
        contract = distribution_contract()["wheel_contract"]

        self.assertEqual(set(top_subparsers.choices), cli.PACKAGE_ONLY_COMMANDS | cli.FACTORY_REQUIRED_COMMANDS | {"mcp"})
        self.assertEqual(set(contract["package_only_commands"]), cli.PACKAGE_ONLY_COMMANDS)
        self.assertEqual(set(contract["factory_required_commands"]), cli.FACTORY_REQUIRED_COMMANDS)
        self.assertEqual(actual, cli.ALL_MCP_COMMANDS)
        self.assertEqual(set(contract["package_only_mcp"]), cli.PACKAGE_ONLY_MCP_COMMANDS)
        self.assertEqual(set(contract["factory_required_mcp"]), cli.FACTORY_REQUIRED_MCP_COMMANDS)
        self.assertEqual(set(contract["package_only_mcp"]) | set(contract["factory_required_mcp"]), actual)

    def test_component_contract_schema_and_semantics_are_enforced(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "src/unaltraweb_mcp/component-contract.schema.json").read_text(encoding="utf-8"))
        contract = distribution_contract()
        validate_component_contract(contract, schema)
        self.assertEqual(component_contract_semantic_errors(contract), [])

        extra = copy.deepcopy(contract)
        extra["components"]["wheel"]["unexpected"] = True
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            validate_component_contract(extra, schema)

        inconsistent = copy.deepcopy(contract)
        inconsistent["components"]["wheel"]["reference"] = "unaltraweb-mcp==9.9.9"
        self.assertIn("wheel wheel reference does not match its version", component_contract_semantic_errors(inconsistent))

    def test_release_pin_classifier_rejects_mutable_channels(self) -> None:
        self.assertTrue(is_mutable_reference("ghcr.io/example/worker:main"))
        self.assertTrue(is_mutable_reference("https://github.com/example/tool.git@refs/heads/main"))
        self.assertTrue(is_mutable_reference("ghcr.io/example/worker"))
        self.assertTrue(is_mutable_reference("registry.example:5000/team/worker"))
        self.assertTrue(is_mutable_reference("registry.example:5000/team/worker:latest"))
        self.assertFalse(is_mutable_reference("ghcr.io/example/worker:0.3.0"))
        self.assertFalse(is_mutable_reference("registry.example:5000/team/worker:0.3.0"))
        self.assertFalse(is_mutable_reference("ghcr.io/example/worker@sha256:" + "a" * 64))
        self.assertTrue(is_mutable_reference("ghcr.io/example/worker@sha256:invalid"))
        self.assertTrue(is_mutable_reference("ghcr.io/example/worker:"))

    def test_distribution_validator_passes_repository_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / "scripts/validate_distribution.py")],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["release_ready"])
        self.assertEqual(result["pending_releases"], [])

        release = subprocess.run(
            [sys.executable, str(root / "scripts/validate_distribution.py"), "--require-release-ready"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(release.returncode, 0, release.stderr or release.stdout)
        self.assertTrue(json.loads(release.stdout)["release_ready"])

    def test_publish_ref_must_match_the_distribution_release(self) -> None:
        contract = distribution_contract()

        self.assertEqual(publish_ref_errors(
            contract,
            ref_type="tag",
            ref_name="v0.3.0",
            default_branch="main",
            component_ids=["runtime", "mcp"],
        ), [])
        self.assertEqual(publish_ref_errors(
            contract,
            ref_type="branch",
            ref_name="main",
            default_branch="main",
            component_ids=["runtime"],
        ), [])
        self.assertIn("publish ref must be", publish_ref_errors(
            contract,
            ref_type="tag",
            ref_name="v9.9.9",
            default_branch="main",
            component_ids=["runtime"],
        )[-1])

    def test_gemspec_packages_contract_schema_and_requires_bundler_four_ruby(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gemspec = (root / "unaltraweb.gemspec").read_text(encoding="utf-8")
        self.assertIn('spec.required_ruby_version = ">= 3.2"', gemspec)
        self.assertGreaterEqual(gemspec.count('"src/unaltraweb_mcp/component-contract.schema.json"'), 2)


if __name__ == "__main__":
    unittest.main()
