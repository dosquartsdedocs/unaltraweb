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
    consumer_integration,
    distribution_contract,
    distribution_doctor,
    is_mutable_reference,
    validate_component_contract,
)
from scripts.validate_distribution import (
    load_release_candidate_receipt_errors,
    publish_ref_errors,
    release_candidate_receipt_errors,
    release_tag_status_errors,
)


class DistributionTests(unittest.TestCase):
    def test_component_contract_covers_the_modular_release(self) -> None:
        contract = distribution_contract()

        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(contract["release"]["version"], __version__)
        self.assertEqual(contract["consumer_integration"], consumer_integration())
        self.assertRegex(contract["consumer_integration"]["core_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(contract["consumer_integration"]["vegavisuals_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(
            contract["consumer_integration"]["manual_pdf_image"],
            r"^ghcr\.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:[0-9a-f]{64}$",
        )
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
        self.assertTrue(all(
            component.get("image_repository", "").startswith("ghcr.io/dosquartsdedocs/")
            for component in contract["components"].values()
            if component["kind"] == "container"
        ))

    def test_doctor_reports_healthy_limited_wheel_mode(self) -> None:
        result = distribution_doctor()

        self.assertTrue(result["ok"])
        self.assertTrue(result["offline"])
        self.assertTrue(result["limited"])
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["pending_releases"], ["gem", "manual_pdf", "mcp", "runtime", "web_capture", "wheel"])
        self.assertEqual(result["unavailable_releases"], [])
        self.assertEqual(result["receipt_contract"]["input_inventory"], "exact")
        self.assertEqual(result["consumer_integration"], consumer_integration())
        self.assertEqual(result["mode"], "wheel")
        self.assertIn("UW-DIST-WHEEL-MODE", {item["code"] for item in result["findings"]})
        self.assertIn("UW-DIST-RELEASE-PENDING", {item["code"] for item in result["findings"]})
        self.assertNotIn("UW-DIST-COMPANION-RELEASE-PENDING", {item["code"] for item in result["findings"]})
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
        self.assertEqual(result["pending_releases"], ["gem", "manual_pdf", "mcp", "runtime", "web_capture", "wheel"])
        self.assertEqual(result["unavailable_releases"], ["vegavisuals"])
        self.assertIn("UW-DIST-COMPANION-RELEASE-UNAVAILABLE", {item["code"] for item in result["findings"]})

    def test_doctor_treats_reviewed_candidates_as_release_ready(self) -> None:
        contract = distribution_contract()
        for component in contract["components"].values():
            if component["release_status"] == "pending":
                component["release_status"] = "ready"

        with patch("unaltraweb_mcp.distribution.distribution_contract", return_value=contract):
            result = distribution_doctor()

        self.assertTrue(result["ok"])
        self.assertTrue(result["release_ready"])
        self.assertEqual(result["pending_releases"], [])
        self.assertNotIn("UW-DIST-RELEASE-PENDING", {item["code"] for item in result["findings"]})

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

    def test_project_doctor_associates_git_pins_with_unaltraweb(self) -> None:
        integration = consumer_integration()
        wrong_sha = "0" * 40
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            (project / "_config.yml").write_text(
                "theme: unaltraweb\nunaltraweb:\n  site_profile: unaltredocs\n",
                encoding="utf-8",
            )
            (project / "Gemfile").write_text(
                "source \"https://rubygems.org\"\n\n"
                "group :jekyll_plugins do\n"
                f"  gem \"decoy\", \"= 1.0.0\",\n      git: \"{integration['core_repository']}\",\n      ref: \"{integration['core_sha']}\"\n"
                f"  gem \"unaltraweb\", \"= 0.3.0\",\n      git: \"https://github.com/example/wrong.git\",\n      ref: \"{wrong_sha}\"\n"
                "end\n",
                encoding="utf-8",
            )
            (project / "Gemfile.lock").write_text(
                "GIT\n"
                f"  remote: {integration['core_repository']}\n  revision: {integration['core_sha']}\n  ref: {integration['core_sha']}\n"
                "  specs:\n    decoy (1.0.0)\n\n"
                "GIT\n"
                f"  remote: https://github.com/example/wrong.git\n  revision: {wrong_sha}\n  ref: {wrong_sha}\n"
                "  specs:\n    unaltraweb (0.3.0)\n\n"
                "DEPENDENCIES\n  unaltraweb (= 0.3.0)!\n",
                encoding="utf-8",
            )
            (project / "Makefile").write_text(f"MCP_IMAGE ?= {component_reference('mcp')}\n", encoding="utf-8")

            result = distribution_doctor(project=project)

        finding = next(item for item in result["findings"] if item["code"] == "UW-DIST-PROJECT-GEM-PIN")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["actual"]["repository"], "https://github.com/example/wrong.git")
        self.assertEqual(finding["actual"]["lock_repository"], "https://github.com/example/wrong.git")

    def test_project_doctor_accepts_an_exact_one_line_gem_declaration(self) -> None:
        integration = consumer_integration()
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            site_tools.new_web(project, site_profile_value="unaltredocs")
            (project / "Gemfile").write_text(
                f'gem "unaltraweb", "= 0.3.0", git: "{integration["core_repository"]}", ref: "{integration["core_sha"]}"\n',
                encoding="utf-8",
            )

            result = distribution_doctor(project=project)

        finding = next(item for item in result["findings"] if item["code"] == "UW-DIST-PROJECT-GEM-PIN")
        self.assertEqual(finding["severity"], "info", finding)

    def test_project_doctor_rejects_a_mismatched_bundler_git_ref(self) -> None:
        integration = consumer_integration()
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            site_tools.new_web(project, site_profile_value="unaltredocs")
            lock_path = project / "Gemfile.lock"
            lock_text = lock_path.read_text(encoding="utf-8")
            lock_path.write_text(
                lock_text.replace(f"  ref: {integration['core_sha']}", "  ref: main", 1),
                encoding="utf-8",
            )

            result = distribution_doctor(project=project)

        finding = next(item for item in result["findings"] if item["code"] == "UW-DIST-PROJECT-GEM-PIN")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["actual"]["lock_ref"], "main")

    def test_project_doctor_ignores_spoofed_gemfile_pins_in_comments(self) -> None:
        integration = consumer_integration()
        wrong_sha = "0" * 40
        with tempfile.TemporaryDirectory() as raw_project:
            project = Path(raw_project)
            site_tools.new_web(project, site_profile_value="unaltredocs")
            (project / "Gemfile").write_text(
                "source \"https://rubygems.org\"\n\n"
                "group :jekyll_plugins do\n"
                "  gem \"unaltraweb\", \"= 0.3.0\",\n"
                f"      # git: \"{integration['core_repository']}\", ref: \"{integration['core_sha']}\"\n"
                "      git: \"https://github.com/example/wrong.git\",\n"
                f"      ref: \"{wrong_sha}\"\n"
                "end\n",
                encoding="utf-8",
            )

            result = distribution_doctor(project=project)

        finding = next(item for item in result["findings"] if item["code"] == "UW-DIST-PROJECT-GEM-PIN")
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(finding["actual"]["repository"], "https://github.com/example/wrong.git")
        self.assertEqual(finding["actual"]["gemfile_revision"], wrong_sha)

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
        self.assertIn("release-candidates.json", (root / ".dockerignore").read_text(encoding="utf-8").splitlines())

        extra = copy.deepcopy(contract)
        extra["components"]["wheel"]["unexpected"] = True
        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            validate_component_contract(extra, schema)

        newline_pin = copy.deepcopy(contract)
        newline_pin["consumer_integration"]["core_sha"] += "\n"
        with self.assertRaisesRegex(RuntimeError, "at most 40 characters"):
            validate_component_contract(newline_pin, schema)

        ready = copy.deepcopy(contract)
        ready["components"]["runtime"]["release_status"] = "ready"
        validate_component_contract(ready, schema)

        inconsistent = copy.deepcopy(contract)
        inconsistent["components"]["wheel"]["reference"] = "unaltraweb-mcp==9.9.9"
        self.assertIn("wheel wheel reference does not match its version", component_contract_semantic_errors(inconsistent))

        released_container = copy.deepcopy(contract)
        released_container["components"]["runtime"]["release_status"] = "released"
        self.assertIn(
            "runtime released container reference must use an immutable digest",
            component_contract_semantic_errors(released_container),
        )
        released_container["components"]["runtime"]["reference"] = "ghcr.io/dosquartsdedocs/unaltraweb@sha256:" + "a" * 64
        self.assertNotIn(
            "runtime released container reference must use an immutable digest",
            component_contract_semantic_errors(released_container),
        )
        released_container["components"]["runtime"]["reference"] = "ghcr.io/dosquartsdedocs/unaltraweb@sha256:invalid"
        self.assertIn(
            "runtime container reference does not match its version",
            component_contract_semantic_errors(released_container),
        )
        released_container["components"]["runtime"]["reference"] = (
            "ghcr.io/dosquartsdedocs/unaltraweb@sha256:\nsource=ghcr.io/attacker/runtime@sha256:" + "a" * 64
        )
        self.assertIn(
            "runtime container reference does not match its version",
            component_contract_semantic_errors(released_container),
        )

        released_mcp = copy.deepcopy(contract)
        released_mcp["components"]["mcp"]["release_status"] = "released"
        self.assertIn(
            "mcp release status must remain ready because its publication digest is recorded externally",
            component_contract_semantic_errors(released_mcp),
        )

        ready_companion = copy.deepcopy(contract)
        ready_companion["components"]["diavisuals"]["release_status"] = "ready"
        self.assertIn(
            "diavisuals companion must be released before coordinated publication",
            component_contract_semantic_errors(ready_companion),
        )

        malformed_repository = copy.deepcopy(contract)
        malformed_repository["components"]["runtime"]["image_repository"] += "\n"
        self.assertIn(
            "runtime container must declare a valid image repository",
            component_contract_semantic_errors(malformed_repository),
        )

        inconsistent_consumer = copy.deepcopy(contract)
        inconsistent_consumer["consumer_integration"]["core_repository"] = "https://github.com/example/core.git"
        self.assertIn(
            "consumer integration core repository must match the gem provider",
            component_contract_semantic_errors(inconsistent_consumer),
        )

        inconsistent_pdf = copy.deepcopy(contract)
        inconsistent_pdf["components"]["manual_pdf"]["image_repository"] = "ghcr.io/dosquartsdedocs/other-pdf"
        self.assertIn(
            "consumer integration manual PDF image must match the manual PDF provider",
            component_contract_semantic_errors(inconsistent_pdf),
        )

        invalid_workflow = copy.deepcopy(contract)
        invalid_workflow["consumer_integration"]["site_deploy_workflow"] = "example/core/.github/workflows/site-deploy.yml"
        self.assertIn(
            "consumer integration deploy workflow must belong to the core provider",
            component_contract_semantic_errors(invalid_workflow),
        )

        malformed_values = [
            ("core_sha", "0" * 40, "consumer integration core SHA must be a nonzero full lowercase commit SHA"),
            ("core_sha", contract["consumer_integration"]["core_sha"] + "\n", "consumer integration core SHA must be a nonzero full lowercase commit SHA"),
            ("manual_pdf_image", contract["consumer_integration"]["manual_pdf_image"] + "\n", "consumer integration manual PDF image must match the manual PDF provider"),
            ("vegavisuals_sha", "0" * 40, "consumer integration Vega revision must be a nonzero full lowercase commit SHA"),
            ("vegavisuals_sha", contract["consumer_integration"]["vegavisuals_sha"] + "\n", "consumer integration Vega revision must be a nonzero full lowercase commit SHA"),
        ]
        for field, value, message in malformed_values:
            with self.subTest(field=field, value=value):
                malformed = copy.deepcopy(contract)
                malformed["consumer_integration"][field] = value
                self.assertIn(message, component_contract_semantic_errors(malformed))

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
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["pending_releases"], ["gem", "manual_pdf", "mcp", "runtime", "web_capture", "wheel"])

        release = subprocess.run(
            [sys.executable, str(root / "scripts/validate_distribution.py"), "--require-release-ready"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(release.returncode, 2, release.stderr or release.stdout)
        self.assertFalse(json.loads(release.stdout)["release_ready"])

    def test_publish_ref_must_match_the_distribution_release(self) -> None:
        contract = distribution_contract()

        pending_tag_errors = publish_ref_errors(
            contract,
            ref_type="tag",
            ref_name="v0.3.0",
            default_branch="main",
            component_ids=["runtime", "mcp"],
        )
        self.assertTrue(any("gem must be release-ready" in error for error in pending_tag_errors))
        self.assertTrue(any("runtime must be release-ready" in error for error in pending_tag_errors))
        self.assertEqual(
            pending_tag_errors[-6:],
            release_tag_status_errors(contract, ref_type="tag", ref_name="v0.3.0"),
        )
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

        released = copy.deepcopy(contract)
        for component_id, component in released["components"].items():
            component["release_status"] = "released"
            if component["kind"] == "container":
                component["reference"] = f"ghcr.io/dosquartsdedocs/{component_id}@sha256:" + "a" * 64
        self.assertEqual(publish_ref_errors(
            released,
            ref_type="tag",
            ref_name="v0.3.0",
            default_branch="main",
            component_ids=["runtime", "mcp"],
        ), [])

        released["components"]["runtime"]["release_status"] = "unavailable"
        self.assertIn("runtime must be release-ready", publish_ref_errors(
            released,
            ref_type="tag",
            ref_name="v0.3.0",
            default_branch="main",
            component_ids=["runtime"],
        )[-1])

        ready = copy.deepcopy(contract)
        for component in ready["components"].values():
            component["release_status"] = "ready"
        self.assertEqual(publish_ref_errors(
            ready,
            ref_type="tag",
            ref_name="v0.3.0",
            default_branch="main",
            component_ids=["runtime", "mcp"],
        ), [])

    def test_pending_release_tag_validation_uses_readiness_exit_status(self) -> None:
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.update({
            "GITHUB_REF_TYPE": "tag",
            "GITHUB_REF_NAME": "v0.3.0",
            "GITHUB_DEFAULT_BRANCH": "main",
        })

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/validate_distribution.py"),
                "--require-release-ready",
                "--validate-publish-ref",
                "--components",
                "runtime,mcp",
            ],
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(completed.returncode, 2, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertFalse(result["ok"])
        self.assertTrue(any("runtime must be release-ready" in error for error in result["errors"]))

    def test_release_candidate_receipt_binds_ready_components_to_parent_commit(self) -> None:
        contract = distribution_contract()
        for component in contract["components"].values():
            if component["release_status"] == "pending":
                component["release_status"] = "ready"
        source_commit = "a" * 40
        digest = "b" * 64
        receipt = {
            "schema_version": 1,
            "release": "v0.3.0",
            "source_commit": source_commit,
            "components": {
                "gem": {"artifact": "unaltraweb-0.3.0.gem", "sha256": digest},
                "wheel": {"artifact": "unaltraweb_mcp-0.3.0-py3-none-any.whl", "sha256": digest},
                "runtime": {"reference": f"ghcr.io/dosquartsdedocs/unaltraweb@sha256:{digest}"},
                "mcp": {"reference": f"ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:{digest}"},
                "web_capture": {"reference": f"ghcr.io/dosquartsdedocs/unaltraweb-web-capture@sha256:{digest}"},
                "manual_pdf": {"reference": f"ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:{digest}"},
            },
        }

        self.assertEqual(release_candidate_receipt_errors(
            contract,
            receipt,
            parent_commit=source_commit,
            changed_paths=["release-candidates.json"],
        ), [])

        mutable = copy.deepcopy(receipt)
        mutable["components"]["mcp"]["reference"] = "ghcr.io/dosquartsdedocs/unaltraweb-mcp:sha-candidate"
        self.assertIn(
            "mcp candidate reference must use an immutable digest from ghcr.io/dosquartsdedocs/unaltraweb-mcp",
            release_candidate_receipt_errors(contract, mutable),
        )
        wrong_repository = copy.deepcopy(receipt)
        wrong_repository["components"]["runtime"]["reference"] = f"ghcr.io/attacker/runtime@sha256:{digest}"
        self.assertIn(
            "runtime candidate reference must use an immutable digest from ghcr.io/dosquartsdedocs/unaltraweb",
            release_candidate_receipt_errors(contract, wrong_repository),
        )
        injected = copy.deepcopy(receipt)
        injected["components"]["runtime"]["reference"] = (
            f"ghcr.io/dosquartsdedocs/unaltraweb\nversion=9.9.9@sha256:{digest}"
        )
        self.assertIn(
            "runtime candidate reference must use an immutable digest from ghcr.io/dosquartsdedocs/unaltraweb",
            release_candidate_receipt_errors(contract, injected),
        )
        swapped_package = copy.deepcopy(receipt)
        swapped_package["components"]["gem"]["artifact"] = "unaltraweb_mcp-0.3.0-py3-none-any.whl"
        self.assertIn(
            "gem candidate artifact must be unaltraweb-0.3.0.gem",
            release_candidate_receipt_errors(contract, swapped_package),
        )
        self.assertIn(
            "release candidate receipt source_commit must be the parent of the release metadata commit",
            release_candidate_receipt_errors(contract, receipt, parent_commit="c" * 40),
        )
        self.assertIn(
            "release metadata commit may change only release-candidates.json",
            release_candidate_receipt_errors(contract, receipt, changed_paths=["README.md", "release-candidates.json"]),
        )
        self.assertIn(
            "release candidate source commit must belong to the default branch",
            release_candidate_receipt_errors(contract, receipt, default_branch_ancestor=False),
        )

    def test_release_candidate_receipt_fails_closed_without_default_branch(self) -> None:
        contract = distribution_contract()
        contract["components"]["runtime"]["release_status"] = "ready"
        digest = "b" * 64
        receipt = {
            "schema_version": 1,
            "release": "v0.3.0",
            "source_commit": "a" * 40,
            "components": {
                "runtime": {"reference": f"ghcr.io/dosquartsdedocs/unaltraweb@sha256:{digest}"},
            },
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "release-candidates.json").write_text(json.dumps(receipt), encoding="utf-8")
            commands = [
                subprocess.CompletedProcess([], 0, stdout="a" * 40 + "\n", stderr=""),
                subprocess.CompletedProcess([], 0, stdout="release-candidates.json\n", stderr=""),
                subprocess.CompletedProcess([], 1, stdout="", stderr="missing origin HEAD"),
            ]
            with patch.dict(os.environ, {"GITHUB_DEFAULT_BRANCH": ""}), patch(
                "scripts.validate_distribution.subprocess.run",
                side_effect=commands,
            ):
                errors = load_release_candidate_receipt_errors(root, contract)

        self.assertEqual(errors, ["could not determine the default branch for release candidate ancestry validation"])

    def test_gemspec_packages_contract_schema_and_requires_bundler_four_ruby(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gemspec = (root / "unaltraweb.gemspec").read_text(encoding="utf-8")
        self.assertIn('spec.required_ruby_version = ">= 3.2"', gemspec)
        self.assertIn('File.exist?(File.join(repo_root, ".git"))', gemspec)
        self.assertGreaterEqual(gemspec.count('"src/unaltraweb_mcp/component-contract.schema.json"'), 2)


if __name__ == "__main__":
    unittest.main()
