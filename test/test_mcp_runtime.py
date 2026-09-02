from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from unaltraweb_mcp import cli
from unaltraweb_mcp import site_tools
from unaltraweb_mcp.docker_mount import docker_bind_mount


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
                self.assertTrue((project / ".unaltraweb/docker-mount.sh").is_file())
                makefile = (project / "Makefile").read_text(encoding="utf-8")
                self.assertIn("docker run", makefile)
                self.assertIn(".unaltraweb/docker-mount.sh", makefile)
                self.assertIn("serve-native: site-check-native serve-capture-native", makefile)
                self.assertIn("unaltraweb (= 0.3.0)", (project / "Gemfile.lock").read_text(encoding="utf-8"))
                self.assertEqual((project / "context/writing-profile.md").is_file(), profile == "unaltremanual")
                for path in site_tools.PROFILE_CONTRACTS[profile]["recommended_paths"]:
                    self.assertTrue((project / path).exists(), path)

    def test_generated_native_targets_do_not_reparse_the_checkout_path(self) -> None:
        project = self.project / "site,source=tmp \"$(path-pwn)\" `path-pwn` 'quoted'"
        site_tools.new_web(project, site_profile_value="unaltredocs", title="Hostile path")
        fake_bin = self.project / "native-bin"
        fake_bin.mkdir()
        marker = self.project / "path-was-evaluated"
        pwn = fake_bin / "path-pwn"
        pwn.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
        pwn.chmod(0o755)
        capture = self.project / "native-args"
        command = fake_bin / "unaltraweb-mcp"
        command.write_text("#!/bin/sh\nprintf '%s\\0' \"$@\" > \"$CAPTURE\"\n", encoding="utf-8")
        command.chmod(0o755)

        completed = subprocess.run(
            ["make", "--silent", "--no-print-directory", "-C", str(project), "site-check-native"],
            env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "CAPTURE": str(capture)},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(capture.read_bytes().split(b"\0")[:-1], [b"--project", os.fsencode(project.resolve()), b"mcp", b"site-check"])

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
    @patch("unaltraweb_mcp.site_tools._http_probe")
    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    def test_existing_preview_waits_until_ready(self, inspect, http_probe, _sleep) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "0",
                site_tools.PREVIEW_CONTAINER_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {
                "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
                "Ports": {"4000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]},
            },
        }
        inspect.return_value = info
        http_probe.side_effect = [{"ok": False}, {"ok": True}]

        result = site_tools.preview_start(self.project, timeout_seconds=10)

        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        self.assertEqual(http_probe.call_count, 2)

    def test_preview_route_uses_home_permalink_and_generated_root_fallback(self) -> None:
        pages = self.project / "_pages" / "en"
        pages.mkdir(parents=True)
        (pages / "index.md").write_text(
            "---\npermalink: /welcome/\n---\nHome.\n",
            encoding="utf-8",
        )
        config = {"baseurl": "/docs", "default_lang": "en"}
        self.assertEqual(site_tools._preview_configured_route(self.project, config), "/docs/welcome/")

        (self.project / "_site").mkdir()
        (self.project / "_site/index.html").write_text("ready\n", encoding="utf-8")
        _, project_id, name = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "0",
                site_tools.PREVIEW_CONTAINER_PORT_LABEL: "4000",
                site_tools.PREVIEW_BASEURL_LABEL: "/docs",
                site_tools.PREVIEW_PATH_LABEL: "/docs/en/",
            }},
            "State": {"Running": True},
            "NetworkSettings": {
                "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
                "Ports": {"4000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]},
            },
        }
        with patch("unaltraweb_mcp.site_tools._preview_inspect", return_value=info), patch(
            "unaltraweb_mcp.site_tools._http_probe", return_value={"ok": True}
        ) as probe, patch("unaltraweb_mcp.site_tools.time.sleep", return_value=None):
            ready, result = site_tools._wait_for_preview(self.project, name, 1)

        self.assertTrue(ready)
        self.assertEqual([call.args[1] for call in probe.call_args_list], [["/docs/"]])
        self.assertEqual(result["configured_path"], "/docs/en/")
        self.assertEqual(result["ready_path"], "/docs/")
        self.assertEqual(result["url"], "http://127.0.0.1:49152/docs/")

    @patch("unaltraweb_mcp.site_tools._http_probe", return_value={"ok": True})
    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    def test_legacy_default_preview_is_idempotent_with_dynamic_default(self, inspect, _http_probe) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        inspect.return_value = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {
                "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
                "Ports": {"4000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "4000"}]},
            },
        }

        result = site_tools.preview_start(self.project)

        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        self.assertTrue(result["legacy_default_port"])
        self.assertEqual(result["port"], 4000)

    @patch("unaltraweb_mcp.site_tools._http_probe", return_value={"ok": True})
    @patch("unaltraweb_mcp.site_tools._preview_inspect")
    @patch("unaltraweb_mcp.site_tools._docker")
    def test_preview_uses_controller_image_id(self, docker, inspect, _http_check) -> None:
        _, project_id, _ = site_tools._preview_identity(self.project)
        info = {
            "Config": {"Labels": {
                site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                site_tools.PREVIEW_ROLE_LABEL: "preview",
                site_tools.PREVIEW_PROJECT_LABEL: project_id,
                site_tools.PREVIEW_PORT_LABEL: "0",
                site_tools.PREVIEW_CONTAINER_PORT_LABEL: "4000",
                site_tools.PREVIEW_PROFILE_LABEL: "",
                site_tools.PREVIEW_PATH_LABEL: "/",
            }},
            "State": {"Running": True, "Status": "running", "ExitCode": 0},
            "NetworkSettings": {
                "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
                "Ports": {"4000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49153"}]},
            },
        }
        inspect.side_effect = [None, info, info]
        docker.return_value = subprocess.CompletedProcess(["docker", "run"], 0, "container-id\n", "")

        with patch.dict(os.environ, {"UNALTRAWEB_MCP_IMAGE": "sha256:controller"}):
            result = site_tools.preview_start(self.project, timeout_seconds=0)

        self.assertTrue(result["ok"])
        run_args = docker.call_args.args[0]
        self.assertIn("sha256:controller", run_args)
        self.assertEqual(run_args[run_args.index("--entrypoint") + 2], "sha256:controller")
        self.assertEqual(run_args[run_args.index("-p") + 1], "127.0.0.1::4000")
        mounts = [next(csv.reader([run_args[index + 1]])) for index, value in enumerate(run_args[:-1]) if value == "--mount"]
        self.assertIn(["type=bind", f"source={self.project.resolve()}", "target=/workspace"], mounts)
        self.assertNotIn("-v", run_args)

    def test_two_projects_get_distinct_preview_names_labels_and_dynamic_ports(self) -> None:
        projects = [self.project / "first" / "site", self.project / "second" / "site"]
        for project in projects:
            project.mkdir(parents=True)

        completed = subprocess.CompletedProcess(["docker", "run"], 0, "container-id\n", "")
        with patch("unaltraweb_mcp.site_tools._require_site_runtime", side_effect=lambda project, _target: (Path(project).resolve(), {})), patch(
            "unaltraweb_mcp.site_tools._preview_inspect", return_value=None
        ), patch("unaltraweb_mcp.site_tools.site_config", return_value={}), patch(
            "unaltraweb_mcp.site_tools.default_language", return_value=""
        ), patch("unaltraweb_mcp.site_tools._docker", return_value=completed) as docker, patch(
            "unaltraweb_mcp.site_tools._wait_for_preview", return_value=(True, {"running": True})
        ):
            for project in projects:
                site_tools.preview_start(project)

        commands = [call.args[0] for call in docker.call_args_list]
        project_ids = [site_tools._preview_identity(project)[1] for project in projects]
        self.assertNotEqual(project_ids[0], project_ids[1])
        self.assertEqual({command[command.index("-p") + 1] for command in commands}, {"127.0.0.1::4000"})
        self.assertEqual(
            {command[command.index("--name") + 1] for command in commands},
            {f"unaltraweb-preview-{project_id}" for project_id in project_ids},
        )
        for command, project_id in zip(commands, project_ids):
            self.assertIn(f"{site_tools.PREVIEW_PROJECT_LABEL}={project_id}", command)
            self.assertIn(f"{site_tools.PREVIEW_PORT_LABEL}=0", command)
            self.assertIn(f"{site_tools.PREVIEW_CONTAINER_PORT_LABEL}=4000", command)

        payloads = []
        for project, project_id, host_port in zip(projects, project_ids, [49154, 49155]):
            payloads.append(site_tools._preview_payload(project, {
                "Config": {"Labels": {
                    site_tools.PREVIEW_FACTORY_LABEL: "unaltraweb",
                    site_tools.PREVIEW_ROLE_LABEL: "preview",
                    site_tools.PREVIEW_PROJECT_LABEL: project_id,
                    site_tools.PREVIEW_PORT_LABEL: "0",
                    site_tools.PREVIEW_CONTAINER_PORT_LABEL: "4000",
                    site_tools.PREVIEW_PATH_LABEL: "/",
                }},
                "State": {"Running": True},
                "NetworkSettings": {
                    "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
                    "Ports": {"4000/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(host_port)}]},
                },
            }))
        self.assertEqual([payload["port"] for payload in payloads], [49154, 49155])
        self.assertEqual({payload["internal_url"] for payload in payloads}, {"http://172.17.0.2:4000/"})

    def test_project_id_matches_preview_identity(self) -> None:
        root = Path(__file__).resolve().parents[1]

        completed = subprocess.run(
            ["/bin/sh", str(root / "scripts/unaltraweb-mcp-project-id.sh"), str(self.project)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        expected = hashlib.sha256(str(self.project.resolve()).encode("utf-8")).hexdigest()[:16]
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), expected)
        self.assertEqual(site_tools._preview_identity(self.project)[1], expected)

    def test_preview_and_worker_identity_preserve_trailing_workspace_whitespace(self) -> None:
        host_project = f"{self.project}/trailing-space "
        expected = hashlib.sha256(host_project.encode("utf-8")).hexdigest()[:16]
        with patch.dict(os.environ, {"UNALTRAWEB_DOCKER_ROOT": host_project}):
            self.assertEqual(site_tools._preview_identity(self.project)[0], host_project)
            self.assertEqual(site_tools._preview_identity(self.project)[1], expected)

        merged_env = {**os.environ, "UNALTRAWEB_DOCKER_ROOT": host_project}
        self.assertEqual(site_tools._docker_host_project(self.project, merged_env), host_project)

    def test_mount_encoders_reject_multiline_fields_before_docker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(ValueError, "carriage returns or newlines"):
            docker_bind_mount("/tmp/source\n--privileged", "/workspace")
        for helper in [
            root / "scripts/unaltraweb-docker-mount.sh",
            root / "src/unaltraweb_mcp/scaffolds/common/.unaltraweb/docker-mount.sh",
        ]:
            completed = subprocess.run(
                ["/bin/sh", str(helper), "/tmp/source\n--privileged", "/workspace"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("carriage returns or newlines", completed.stderr)

    def test_manifest_stdio_launches_preserve_two_adversarial_workspaces(self) -> None:
        root = Path(__file__).resolve().parents[1]
        projects = [
            self.project / "launch,source=" / "tmp" / "one: $dollar `printf BAD` 'single' \"double\" $(shell printf INJECTED)",
            self.project / "other,source=" / "var" / "two: $other `printf WORSE` 'quote' \"quoted\" $(shell printf ALTERED)",
        ]
        for project in projects:
            project.mkdir(parents=True)
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        docker = fake_bin / "docker"
        docker.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = image ]; then printf '%s\\n' 'sha256:controller'; exit 0; fi\n"
            "printf '%s\\n' \"$@\" > \"$CAPTURE\"\n"
            "if [ -n \"${READY_CAPTURE:-}\" ]; then\n"
            "  : > \"$READY_CAPTURE\"\n"
            "  while [ ! -e \"$RELEASE_FILE\" ]; do sleep 0.01; done\n"
            "fi\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        manifest = next(yaml.safe_load_all((root / "mcp-factory.yml").read_text(encoding="utf-8")))
        transport = manifest["transport"]
        release = self.project / "release-launches"
        ready_files: list[Path] = []
        processes: list[subprocess.Popen[str]] = []
        launches: list[list[str]] = []
        for index, project in enumerate(projects):
            capture = self.project / f"docker-args-{index}"
            ready = self.project / f"docker-ready-{index}"
            ready_files.append(ready)
            env = os.environ.copy()
            env.update({
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CAPTURE": str(capture),
                "READY_CAPTURE": str(ready),
                "RELEASE_FILE": str(release),
                **{
                    key: value.replace("${workspaceFolder}", str(project.resolve()))
                    for key, value in transport["env"].items()
                },
            })
            command = [part.replace("${factoryRoot}", str(root)) for part in transport["command"]]
            processes.append(subprocess.Popen(
                command,
                cwd=project,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            ))

        deadline = time.monotonic() + 5
        while not all(path.exists() for path in ready_files) and time.monotonic() < deadline:
            time.sleep(0.01)
        all_ready = all(path.exists() for path in ready_files)
        all_running = all(process.poll() is None for process in processes)
        release.touch()
        for index, process in enumerate(processes):
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertEqual(stdout, "", "stdio launcher must reserve stdout for MCP protocol messages")
            launches.append((self.project / f"docker-args-{index}").read_text(encoding="utf-8").splitlines())
        self.assertTrue(all_ready, "both manifest launches must overlap")
        self.assertTrue(all_running)

        project_ids = [hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:16] for project in projects]
        self.assertNotEqual(project_ids[0], project_ids[1])
        for args, project, project_id in zip(launches, projects, project_ids):
            self.assertNotIn("--name", args)
            self.assertIn("io.context.mcp-role=stdio", args)
            self.assertIn(f"io.context.mcp-project={project_id}", args)
            self.assertIn("sha256:controller", args)
            self.assertNotIn(str(root), args)
            mounts = [next(csv.reader([args[index + 1]])) for index, value in enumerate(args[:-1]) if value == "--mount"]
            self.assertIn(["type=bind", f"source={project.resolve()}", "target=/workspace"], mounts)
            self.assertIn(["type=bind", f"source={project.resolve()}", f"target={project.resolve()}"], mounts)
            self.assertNotIn("-v", args)
            self.assertEqual(args[args.index("-w") + 1], str(project.resolve()))
            self.assertEqual(args[args.index("--project") + 1], str(project.resolve()))

    def test_mount_csv_encoders_block_duplicate_fields_in_real_docker(self) -> None:
        docker = shutil.which("docker")
        image = os.environ.get("UNALTRAWEB_MCP_IMAGE", site_tools.component_reference("mcp"))
        if docker is None or subprocess.run(
            [docker, "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode != 0:
            self.skipTest("real Docker parser test requires the local unaltraweb MCP image")

        attacker = self.project / "attacker-workspace"
        attacker.mkdir()
        intended = Path(f'{self.project}/intended,source={attacker},"quoted"')
        intended.mkdir(parents=True)
        helpers = [
            Path(__file__).resolve().parents[1] / "scripts/unaltraweb-docker-mount.sh",
            Path(__file__).resolve().parents[1] / "src/unaltraweb_mcp/scaffolds/common/.unaltraweb/docker-mount.sh",
        ]
        targets = ["/workspace", '/workspace,target=/cross-workspace,"quoted"']
        mounts = [docker_bind_mount(intended, target, readonly=True) for target in targets]
        mounts.extend(
            subprocess.run(
                ["/bin/sh", str(helper), str(intended), target, "readonly"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout.strip()
            for helper in helpers
            for target in targets
        )
        for mount in mounts:
            fields = next(csv.reader([mount]))
            source = next(field.removeprefix("source=") for field in fields if field.startswith("source="))
            target = next(field.removeprefix("target=") for field in fields if field.startswith("target="))
            self.assertEqual(len([field for field in fields if field.startswith("source=")]), 1)
            self.assertEqual(len([field for field in fields if field.startswith("target=")]), 1)
            self.assertEqual(source, str(intended))
            created = subprocess.run(
                [docker, "create", "--mount", mount, image, "true"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            container = created.stdout.strip()
            try:
                inspected = subprocess.run(
                    [docker, "inspect", container],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                parsed = json.loads(inspected.stdout)[0]["Mounts"]
                self.assertEqual(len(parsed), 1)
                self.assertEqual(parsed[0]["Source"], str(intended))
                self.assertEqual(parsed[0]["Destination"], target)
                self.assertFalse(parsed[0]["RW"])
            finally:
                subprocess.run([docker, "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def test_outer_preview_and_worker_mount_call_sites_use_csv_encoders(self) -> None:
        root = Path(__file__).resolve().parents[1]
        call_sites = [
            root / "Makefile",
            root / "scripts/unaltraweb-mcp-bootstrap.sh",
            root / "scripts/test_gem_build.py",
            root / "scripts/web_captures/render.py",
            root / "src/unaltraweb_mcp/site_tools.py",
            root / "src/unaltraweb_mcp/scaffolds/common/Makefile.tmpl",
        ]
        for path in call_sites:
            with self.subTest(path=path.relative_to(root)):
                self.assertNotIn("type=bind,source=", path.read_text(encoding="utf-8"))
        self.assertIn("unaltraweb-docker-mount.sh", (root / "Makefile").read_text(encoding="utf-8"))
        self.assertIn("unaltraweb-docker-mount.sh", (root / "scripts/unaltraweb-mcp-bootstrap.sh").read_text(encoding="utf-8"))
        self.assertIn("docker_bind_mount", (root / "src/unaltraweb_mcp/site_tools.py").read_text(encoding="utf-8"))

    def test_make_cleanup_scopes_project_and_maintainer_targets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        capture = self.project / "docker-calls"
        docker = fake_bin / "docker"
        docker.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' CALL \"$@\" >> \"$CAPTURE\"\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        env = os.environ.copy()
        env.pop("MCP_CONSUMER_WORKSPACE", None)
        env.pop("MCP_PROJECT_ID", None)
        env.update({"PATH": f"{fake_bin}:{env['PATH']}", "CAPTURE": str(capture)})

        def run_target(target: str, project: Path | None = None, project_id: str = "") -> list[list[str]]:
            capture.unlink(missing_ok=True)
            target_env = env.copy()
            target_env.pop("MCP_CONSUMER_WORKSPACE", None)
            target_env.pop("MCP_PROJECT_ID", None)
            if project is not None:
                target_env["MCP_CONSUMER_WORKSPACE"] = str(project)
            if project_id:
                target_env["MCP_PROJECT_ID"] = project_id
            completed = subprocess.run(
                ["make", "--silent", "--no-print-directory", "-C", str(root), target],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=target_env,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            calls: list[list[str]] = []
            for line in capture.read_text(encoding="utf-8").splitlines():
                if line == "CALL":
                    calls.append([])
                else:
                    calls[-1].append(line)
            return calls

        project_id = hashlib.sha256(str(self.project.resolve()).encode("utf-8")).hexdigest()[:16]
        self.assertEqual(
            run_target("mcp-down", self.project),
            [
                [
                    "ps", "-aq", "--filter", "label=io.context.mcp-factory=unaltraweb",
                    "--filter", f"label=io.context.mcp-project={project_id}",
                ],
                [
                    "network", "ls", "-q", "--filter", "label=io.context.mcp-factory=unaltraweb",
                    "--filter", f"label=io.context.mcp-project={project_id}",
                ],
            ],
        )
        other_project = self.project / "other-project"
        other_project.mkdir()
        other_id = hashlib.sha256(str(other_project.resolve()).encode("utf-8")).hexdigest()[:16]
        other_calls = run_target("mcp-down", other_project)
        self.assertNotEqual(project_id, other_id)
        self.assertTrue(all(f"label=io.context.mcp-project={other_id}" in call for call in other_calls))
        self.assertTrue(all(f"label=io.context.mcp-project={project_id}" not in call for call in other_calls))

        deleted_project = self.project / "deleted-project"
        deleted_project.mkdir()
        deleted_id = hashlib.sha256(str(deleted_project.resolve()).encode("utf-8")).hexdigest()[:16]
        deleted_project.rmdir()
        deleted_calls = run_target("mcp-down", deleted_project, project_id=deleted_id)
        self.assertTrue(all(f"label=io.context.mcp-project={deleted_id}" in call for call in deleted_calls))

        retained_calls = run_target("mcp-down", project_id=deleted_id)
        self.assertTrue(all(f"label=io.context.mcp-project={deleted_id}" in call for call in retained_calls))

        alias = self.project.parent / f"{self.project.name}-canonical-project-alias"
        alias.symlink_to(self.project, target_is_directory=True)
        alias_calls = run_target("mcp-down", alias, project_id=project_id)
        self.assertTrue(all(f"label=io.context.mcp-project={project_id}" in call for call in alias_calls))

        capture.unlink(missing_ok=True)
        mismatch_env = env.copy()
        mismatch_env["MCP_CONSUMER_WORKSPACE"] = str(self.project)
        mismatch_env["MCP_PROJECT_ID"] = other_id
        mismatch = subprocess.run(
            ["make", "--silent", "--no-print-directory", "-C", str(root), "mcp-down"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=mismatch_env,
            check=False,
        )
        self.assertEqual(mismatch.returncode, 2)
        self.assertIn("canonical live workspace", mismatch.stderr)
        self.assertFalse(capture.exists())

        absent_env = env.copy()
        absent_env["MCP_CONSUMER_WORKSPACE"] = str(self.project / "absent")
        absent = subprocess.run(
            ["make", "--silent", "--no-print-directory", "-C", str(root), "mcp-down"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=absent_env,
            check=False,
        )
        self.assertEqual(absent.returncode, 2)
        self.assertIn("Set MCP_PROJECT_ID", absent.stderr)
        self.assertFalse(capture.exists())

        self.assertEqual(
            run_target("mcp-down-all"),
            [
                ["ps", "-aq", "--filter", "label=io.context.mcp-factory=unaltraweb"],
                ["network", "ls", "-q", "--filter", "label=io.context.mcp-factory=unaltraweb"],
            ],
        )

    def test_repository_targets_default_safely_but_stdio_requires_workspace(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("MCP_CONSUMER_WORKSPACE", None)
        marker = self.project / "make-expanded"
        completed = subprocess.run(
            [
                "make", "--silent", "--no-print-directory", "-C", str(root),
                "distribution-doctor", f"PROJECT=$(shell touch {marker})",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["project"]["path"], str(root))
        self.assertFalse(marker.exists())

        stdio = subprocess.run(
            ["make", "--silent", "--no-print-directory", "-C", str(root), "mcp-stdio"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(stdio.returncode, 2)
        self.assertIn("MCP_CONSUMER_WORKSPACE", stdio.stderr)

        command_line = subprocess.run(
            [
                "make", "--silent", "--no-print-directory", "-C", str(root), "mcp-stdio",
                f"MCP_CONSUMER_WORKSPACE=$(shell touch {marker})",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(command_line.returncode, 2)
        self.assertIn("must be inherited", command_line.stderr)
        self.assertFalse(marker.exists())

    def test_visualization_status_requires_provider_receipt_for_configured_project(self) -> None:
        (self.project / ".vegavisuals.yml").write_text("visualizations: []\n", encoding="utf-8")

        status = site_tools.visualization_status(self.project, Path("/opt/unaltraweb"))

        self.assertFalse(status["ok"])
        self.assertFalse(status["delegated"])
        self.assertEqual(status["owner"], "vegavisuals")
        self.assertEqual(status["required_tool"], "visualization_check")
        self.assertEqual(status["receipt"]["state"], "missing")

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
        self.assertEqual(manifest["workspace_rule"]["binding"], "consumer")
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            manifest["transport"]["command"],
            ["make", "--no-print-directory", "-C", "${factoryRoot}", "mcp-stdio"],
        )
        self.assertEqual(manifest["transport"]["env"], {"MCP_CONSUMER_WORKSPACE": "${workspaceFolder}"})
        self.assertNotIn("init", manifest["commands"])
        self.assertEqual(
            manifest["commands"]["down"],
            ["make", "mcp-down"],
        )
        self.assertNotIn("down_all", manifest["commands"])
        self.assertTrue(all(not dependency["init"] for dependency in manifest["mcp_dependencies"]))
        self.assertNotIn("mcp-init:", (root / "Makefile").read_text(encoding="utf-8"))

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
