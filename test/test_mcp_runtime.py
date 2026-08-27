from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from unaltraweb_mcp import cli
from unaltraweb_mcp import site_tools


class McpRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project / "_config.yml").write_text(
            "theme: unaltraweb\nunaltraweb:\n  site_profile: unaltreselfie\n",
            encoding="utf-8",
        )
        (self.project / "Gemfile").write_text('gem "unaltraweb"\n', encoding="utf-8")
        (self.project / "Makefile").write_text(
            "build-native build-local:\n\t@true\n\nserve-native serve-local:\n\t@true\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_detects_consumer_and_native_runtime_targets(self) -> None:
        status = site_tools.detect_site(self.project)

        self.assertTrue(status["is_unaltraweb_site"])
        self.assertTrue(status["markers"]["theme"])
        self.assertTrue(status["markers"]["gem"])
        self.assertEqual(status["runtime_targets"], {"build_native": True, "serve_native": True})

    def test_make_target_detection_does_not_execute_makefile(self) -> None:
        marker = self.project / "executed"
        (self.project / "Makefile").write_text(
            f"SIDE_EFFECT := $(shell touch {marker})\n"
            "serve-capture-native := disabled\n"
            "build-native build-local:\n\t@true\n",
            encoding="utf-8",
        )

        self.assertFalse(site_tools._make_target_available(self.project, "serve-capture-native"))
        self.assertTrue(site_tools._make_target_available(self.project, "build-native"))
        self.assertFalse(marker.exists())

    def test_rejects_directory_without_unaltraweb_markers(self) -> None:
        (self.project / "_config.yml").write_text("title: Plain Jekyll\n", encoding="utf-8")
        (self.project / "Gemfile").write_text('gem "jekyll"\n', encoding="utf-8")

        self.assertFalse(site_tools.detect_site(self.project)["is_unaltraweb_site"])

    def test_scaffold_inventory_ignores_external_template_environment(self) -> None:
        template = self.project / "template"
        template.mkdir()
        (template / "_config.yml").write_text("theme: unaltraweb\n", encoding="utf-8")
        (template / "Makefile").write_text("build:\n\t@true\n", encoding="utf-8")
        (template / "Gemfile").write_text('gem "unaltraweb"\n', encoding="utf-8")

        with patch.dict(os.environ, {"UNALTRAWEB_TEMPLATE_PATH": str(template)}):
            status = site_tools.starter_templates(Path("/opt/unaltraweb"))

        self.assertEqual(status["default"], "unaltreselfie")
        self.assertEqual(status["source"], "unaltraweb_mcp package")
        self.assertNotIn(str(template.resolve()), str(status))

    def test_package_scaffolds_are_available_for_every_profile(self) -> None:
        status = site_tools.scaffold_inventory()

        available = {item["profile"]: item["available"] for item in status["profiles"]}

        self.assertEqual(set(available), set(site_tools.PROFILE_CONTRACTS))
        self.assertTrue(all(available.values()))
        self.assertTrue(status["common_available"])

    def test_new_web_creates_each_profile_and_passes_its_contract(self) -> None:
        expected_layouts = {
            "unaltreselfie": "profile",
            "unaltreprojecte": "page",
            "unaltremanual": "manual-home",
            "unaltredocs": "documentation-home",
        }
        for profile, layout in expected_layouts.items():
            with self.subTest(profile=profile):
                project = self.project / profile
                result = site_tools.new_web(project, site_profile_value=profile, title=f"Test {profile}")

                self.assertTrue(result["ok"], result)
                self.assertEqual(site_tools.site_profile(site_tools.site_config(project)), profile)
                self.assertIn(f"layout: {layout}", (project / "_pages/en/index.md").read_text(encoding="utf-8"))
                self.assertTrue((project / ".github/workflows/deploy.yml").is_file())
                makefile = (project / "Makefile").read_text(encoding="utf-8")
                self.assertIn("docker run", makefile)
                self.assertIn("serve-native: site-check-native serve-capture-native", makefile)
                self.assertIn("unaltraweb (= 0.3.0)", (project / "Gemfile.lock").read_text(encoding="utf-8"))
                self.assertEqual((project / "context/writing-profile.md").is_file(), profile == "unaltremanual")
                for path in site_tools.PROFILE_CONTRACTS[profile]["recommended_paths"]:
                    self.assertTrue((project / path).exists(), path)

    def test_new_web_is_idempotent_for_the_same_inputs(self) -> None:
        project = self.project / "new-site"

        first = site_tools.new_web(project, site_profile_value="unaltredocs", title="Test docs")
        second = site_tools.new_web(project, site_profile_value="unaltredocs", title="Test docs")

        self.assertGreater(first["created_count"], 0)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["unchanged_count"], first["created_count"])

    def test_new_web_preflights_all_collisions_before_writing(self) -> None:
        project = self.project / "collision"
        project.mkdir()
        (project / "_config.yml").write_text("title: Existing\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "no website files were written"):
            site_tools.new_web(project, site_profile_value="unaltreprojecte")

        self.assertFalse((project / "Makefile").exists())
        self.assertFalse((project / "_pages").exists())
        self.assertEqual((project / "_config.yml").read_text(encoding="utf-8"), "title: Existing\n")

    def test_new_web_preflights_file_ancestors_before_writing(self) -> None:
        project = self.project / "ancestor-collision"
        project.mkdir()
        (project / "_pages").write_text("not a directory\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "expected a directory but found a file: _pages"):
            site_tools.new_web(project, site_profile_value="unaltredocs")

        self.assertEqual(list(project.iterdir()), [project / "_pages"])
        self.assertFalse((project / "_documentation").exists())

    def test_new_web_rejects_symlinks_without_writing_through_them(self) -> None:
        project = self.project / "symlink-site"
        outside = self.project / "outside"
        project.mkdir()
        outside.mkdir()
        (project / "_pages").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "symlink is not allowed"):
            site_tools.new_web(project)

        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((project / "_config.yml").exists())

    def test_new_web_rejects_symlink_in_destination_ancestors(self) -> None:
        outside = self.project / "destination-outside"
        alias = self.project / "destination-alias"
        outside.mkdir()
        alias.symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "Symlinks are not allowed in the new website destination"):
            site_tools.new_web(alias / "site")

        self.assertEqual(list(outside.iterdir()), [])

        with self.assertRaisesRegex(RuntimeError, "Symlinks are not allowed in the new website destination"):
            cli.main(["--project", str(alias / "cli-site"), "new-web"])

        self.assertEqual(list(outside.iterdir()), [])

    def test_new_web_does_not_follow_symlink_created_after_preflight(self) -> None:
        project = self.project / "raced-symlink-site"
        outside = self.project / "raced-outside"
        project.mkdir()
        outside.mkdir()
        original_preflight = site_tools._scaffold_preflight

        def add_symlink_after_preflight(project_path, payloads, required_directories):
            result = original_preflight(project_path, payloads, required_directories)
            (project_path / "_pages").symlink_to(outside, target_is_directory=True)
            return result

        with patch("unaltraweb_mcp.site_tools._scaffold_preflight", side_effect=add_symlink_after_preflight):
            with self.assertRaisesRegex(RuntimeError, "could not apply the preflighted scaffold safely"):
                site_tools.new_web(project)

        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((project / "_config.yml").exists())

    def test_new_web_does_not_overwrite_file_created_after_preflight(self) -> None:
        project = self.project / "raced-file-site"
        project.mkdir()
        original_preflight = site_tools._scaffold_preflight

        def add_file_after_preflight(project_path, payloads, required_directories):
            result = original_preflight(project_path, payloads, required_directories)
            (project_path / "_config.yml").write_text("title: Raced\n", encoding="utf-8")
            return result

        with patch("unaltraweb_mcp.site_tools._scaffold_preflight", side_effect=add_file_after_preflight):
            with self.assertRaisesRegex(RuntimeError, "could not apply the preflighted scaffold safely"):
                site_tools.new_web(project)

        self.assertEqual((project / "_config.yml").read_text(encoding="utf-8"), "title: Raced\n")

    def test_new_web_revalidates_unchanged_files_after_preflight(self) -> None:
        project = self.project / "raced-unchanged-site"
        outside = self.project / "raced-unchanged-outside"
        site_tools.new_web(project)
        outside.write_text("title: Outside\n", encoding="utf-8")
        original_preflight = site_tools._scaffold_preflight

        def replace_unchanged_file(project_path, payloads, required_directories):
            result = original_preflight(project_path, payloads, required_directories)
            (project_path / "_config.yml").unlink()
            (project_path / "_config.yml").symlink_to(outside)
            return result

        with patch("unaltraweb_mcp.site_tools._scaffold_preflight", side_effect=replace_unchanged_file):
            with self.assertRaisesRegex(RuntimeError, "could not apply the preflighted scaffold safely"):
                site_tools.new_web(project)

        self.assertEqual(outside.read_text(encoding="utf-8"), "title: Outside\n")

    def test_new_web_rejects_language_paths(self) -> None:
        project = self.project / "unsafe-language"

        with self.assertRaisesRegex(ValueError, "Invalid language identifier"):
            site_tools.new_web(project, languages="en,../outside")

        self.assertFalse(project.exists())

    def test_initialize_site_rejects_external_templates(self) -> None:
        with self.assertRaisesRegex(ValueError, "External template paths are not supported"):
            site_tools.initialize_site(self.project / "legacy", Path("/opt/unaltraweb"), template_path="/tmp/template")

    def test_profile_check_cli_exits_nonzero_for_invalid_site(self) -> None:
        (self.project / "_config.yml").write_text("title: Invalid\n", encoding="utf-8")

        with patch("builtins.print"):
            returncode = cli.main(["--project", str(self.project), "mcp", "profile-check"])

        self.assertEqual(returncode, 1)

    @patch("unaltraweb_mcp.cli.tools.site_check", return_value={"ok": False})
    def test_site_check_cli_exits_nonzero_for_failed_preflight(self, _site_check) -> None:
        with patch("builtins.print"):
            returncode = cli.main(["--project", str(self.project), "mcp", "site-check"])

        self.assertEqual(returncode, 1)

    @patch("unaltraweb_mcp.site_tools.run_make", return_value={"ok": True, "returncode": 0})
    def test_build_uses_current_mcp_runtime_without_nested_container(self, run_make) -> None:
        factory = Path("/opt/unaltraweb")

        result = site_tools.build_site(self.project, factory, site_profile="unaltredocs")

        run_make.assert_called_once_with(
            self.project.resolve(),
            "build-native",
            extra_args=["LOCAL_CORE=/opt/unaltraweb", "SITE_PROFILE=unaltredocs"],
            env={"UNALTRAWEB_MCP_RUNTIME": "1"},
        )
        self.assertEqual(result["runtime"], "mcp-container")
        self.assertFalse(result["nested_container"])

    @patch("unaltraweb_mcp.site_tools._preview_inspect", return_value=None)
    def test_preview_status_is_scoped_to_host_project(self, _inspect) -> None:
        with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_ROOT": "/home/test/site"}):
            status = site_tools.preview_status(self.project)

        self.assertEqual(status["status"], "absent")
        self.assertEqual(status["host_project"], "/home/test/site")
        self.assertTrue(status["container"].startswith("unaltraweb-preview-"))

    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    def test_preview_stop_refuses_unowned_container(self, inspect) -> None:
        inspect.return_value = {"Config": {"Labels": {}}, "State": {"Running": True}}

        with self.assertRaisesRegex(RuntimeError, "unowned Docker container"):
            site_tools.preview_stop(self.project)

    @patch("unaltraweb_mcp.site_tools._docker")
    def test_preview_inspect_does_not_hide_docker_errors(self, docker) -> None:
        docker.return_value = subprocess.CompletedProcess(
            ["docker", "inspect"],
            returncode=1,
            stdout="",
            stderr="permission denied while trying to connect to the Docker daemon",
        )

        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            site_tools.preview_status(self.project)

    @patch("unaltraweb_mcp.site_tools.time.sleep", return_value=None)
    @patch("unaltraweb_mcp.site_tools.http_check")
    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    def test_existing_preview_waits_until_ready(self, inspect, http_check, _sleep) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.2"}}},
        }
        inspect.return_value = info
        http_check.side_effect = [{"ok": False}, {"ok": True}]

        result = site_tools.preview_start(self.project, timeout_seconds=10)

        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        self.assertEqual(http_check.call_count, 2)

    @patch("unaltraweb_mcp.site_tools.http_check", return_value={"ok": True})
    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    @patch("unaltraweb_mcp.site_tools._docker")
    def test_preview_uses_controller_image_id(self, docker, inspect, _http_check) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {"Networks": {"bridge": {"IPAddress": "172.17.0.2"}}},
        }
        inspect.side_effect = [None, info, info]
        docker.return_value = subprocess.CompletedProcess(["docker", "run"], 0, "container-id\n", "")

        with patch.dict(os.environ, {"UNALTRAWEB_MCP_IMAGE": "sha256:controller"}):
            result = site_tools.preview_start(self.project, timeout_seconds=0)

        self.assertTrue(result["ok"])
        run_args = docker.call_args.args[0]
        self.assertIn("sha256:controller", run_args)
        self.assertEqual(run_args[run_args.index("--entrypoint") + 2], "sha256:controller")

    def test_bootstrap_names_and_labels_stdio_container_by_project(self) -> None:
        root = Path(__file__).resolve().parents[1]
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        capture = self.project / "docker-args"
        docker = fake_bin / "docker"
        docker.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = image ]; then printf '%s\\n' 'sha256:controller'; exit 0; fi\n"
            "printf '%s\\n' \"$@\" > \"$CAPTURE\"\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        env = os.environ.copy()
        env.update({"PATH": f"{fake_bin}:{env['PATH']}", "CAPTURE": str(capture)})

        completed = subprocess.run(
            [str(root / "scripts/unaltraweb-mcp-bootstrap.sh"), "--project", str(self.project)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        args = capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("--name", args)
        self.assertTrue(args[args.index("--name") + 1].startswith("unaltraweb-mcp-"))
        self.assertIn("io.context.mcp-role=stdio", args)
        self.assertIn("sha256:controller", args)
        self.assertNotIn(str(root), args)
        canonical_mount = f"{self.project.resolve()}:{self.project.resolve()}"
        self.assertIn(canonical_mount, args)
        self.assertEqual(args[args.index("-w") + 1], str(self.project.resolve()))
        self.assertEqual(args[args.index("--project") + 1], str(self.project.resolve()))

    def test_visualization_status_delegates_configured_project_to_companion_mcp(self) -> None:
        (self.project / ".vegavisuals.yml").write_text("visualizations: []\n", encoding="utf-8")

        status = site_tools.visualization_status(self.project, Path("/opt/unaltraweb"))

        self.assertTrue(status["ok"])
        self.assertTrue(status["delegated"])
        self.assertEqual(status["owner"], "vegavisuals")
        self.assertEqual(status["required_tool"], "visualization_check")

    def test_inventory_exposes_runtime_tools(self) -> None:
        tools = site_tools.list_tools()["tools"]

        for name in ["new_web", "detect_site", "build_site", "preview_start", "preview_status", "preview_stop"]:
            self.assertIn(name, tools)

    def test_prompt_inventory_is_structured_and_complete(self) -> None:
        root = Path(__file__).resolve().parents[1]

        inventory = site_tools.prompt_inventory(root)

        self.assertTrue(inventory["all_available"])
        self.assertEqual(inventory["prompt_count"], len(site_tools.PROMPT_SPECS))
        self.assertEqual([prompt["name"] for prompt in inventory["prompts"]], list(site_tools.PROMPT_SPECS))
        structure = next(prompt for prompt in inventory["prompts"] if prompt["name"] == "manual_structure_audit")
        self.assertEqual([argument["name"] for argument in structure["arguments"]], ["target", "revision_mode"])
        self.assertEqual(site_tools.list_tools()["prompts"], list(site_tools.PROMPT_SPECS))

    def test_factory_manifest_matches_runtime_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = next(yaml.safe_load_all((root / "mcp-factory.yml").read_text(encoding="utf-8")))
        inventory = site_tools.list_tools()

        self.assertEqual(set(manifest["mcp"]["resources"]), set(inventory["resources"]))
        self.assertEqual(set(manifest["mcp"]["required_tools"]), set(inventory["tools"]))
        self.assertIn("context", manifest["workspace_rule"]["init_creates"])
        self.assertIn("context", manifest["workspace_rule"]["source_paths"])

    def test_writing_profile_is_excluded_from_published_site(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = yaml.safe_load((root / "_config.yml").read_text(encoding="utf-8"))

        self.assertIn("context/", config["exclude"])

    @patch("unaltraweb_mcp.site_tools.run_factory_make")
    def test_bibliometrics_update_delegates_to_factory(self, run_factory_make) -> None:
        run_factory_make.return_value = {"ok": True}
        factory = Path("/tmp/factory")

        site_tools.bibliometrics_update(self.project, factory, offline=True, dry_run=True)

        run_factory_make.assert_called_once_with(
            factory,
            self.project,
            "metrics-update",
            extra_args=["METRICS_ARGS=--offline --dry-run"],
        )

    def test_scimago_input_rejects_make_expansion(self) -> None:
        with self.assertRaisesRegex(ValueError, "safe project-relative"):
            site_tools.bibliometrics_fetch_scimago(
                self.project,
                Path("/tmp/factory"),
                scimago_input="$(shell touch /tmp/pwned).csv",
            )


if __name__ == "__main__":
    unittest.main()
