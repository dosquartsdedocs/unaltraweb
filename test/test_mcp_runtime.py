from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_rejects_directory_without_unaltraweb_markers(self) -> None:
        (self.project / "_config.yml").write_text("title: Plain Jekyll\n", encoding="utf-8")
        (self.project / "Gemfile").write_text('gem "jekyll"\n', encoding="utf-8")

        self.assertFalse(site_tools.detect_site(self.project)["is_unaltraweb_site"])

    def test_starter_template_uses_container_mount(self) -> None:
        template = self.project / "template"
        template.mkdir()
        (template / "_config.yml").write_text("theme: unaltraweb\n", encoding="utf-8")
        (template / "Makefile").write_text("build:\n\t@true\n", encoding="utf-8")
        (template / "Gemfile").write_text('gem "unaltraweb"\n', encoding="utf-8")

        with patch.dict(os.environ, {"UNALTRAWEB_TEMPLATE_PATH": str(template)}):
            status = site_tools.starter_templates(Path("/opt/unaltraweb"))

        self.assertEqual(status["default"], str(template.resolve()))

    def test_embedded_starter_template_is_available(self) -> None:
        factory = Path(__file__).resolve().parents[1]

        status = site_tools.starter_templates(factory)

        self.assertEqual(status["default"], str((factory / "templates/site").resolve()))

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

        for name in ["detect_site", "build_site", "preview_start", "preview_status", "preview_stop"]:
            self.assertIn(name, tools)


if __name__ == "__main__":
    unittest.main()
