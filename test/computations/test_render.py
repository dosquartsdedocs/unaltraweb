from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "computations" / "render.py"
SPEC = importlib.util.spec_from_file_location("unaltraweb_computations", MODULE_PATH)
assert SPEC and SPEC.loader
computations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(computations)


def write_qmd(path: Path, *, engine: str = "python", inputs: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = {
        "layout": "manual-chapter",
        "title": "Computed chapter",
        "lang": "en",
        "ref": "computed-chapter",
        "weight": 50,
        "unaltraweb_compute": {"engine": engine, "inputs": inputs or []},
    }
    path.write_text(
        "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n\n## Result\n",
        encoding="utf-8",
    )


def write_figure_qmd(path: Path, output: str = "assets/img/generated/en/figure.svg") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = {
        "title": "Computed figure",
        "lang": "en",
        "ref": "computed-figure",
        "format": "gfm",
        "unaltraweb_compute": {"engine": "python", "mode": "figure", "outputs": [output]},
    }
    path.write_text(
        "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n\nFigure source.\n",
        encoding="utf-8",
    )


class ComputationRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name).resolve()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self, engines: dict[str, object] | None = None) -> None:
        path = self.project / ".unaltraweb/computations.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "source_roots": ["_chapters"],
                    "generated_assets_root": "assets/img/generated",
                    "engines": engines or {},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_discovers_same_stem_output_and_explicit_qmd_engine(self) -> None:
        write_qmd(self.project / "_chapters/en/05-computed.qmd")
        config, _ = computations.load_config(self.project)

        records = computations.discover_sources(self.project, config)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["engine"], "python")
        self.assertEqual(records[0]["output_path"], "_chapters/en/05-computed.md")
        self.assertEqual(records[0]["figures_path"], "assets/img/generated/en/computed-chapter")

    def test_discovers_figure_mode_outputs(self) -> None:
        write_figure_qmd(self.project / "_chapters/en/figure.qmd")
        config, _ = computations.load_config(self.project)

        records = computations.discover_sources(self.project, config)

        self.assertEqual(records[0]["mode"], "figure")
        self.assertEqual(records[0]["output_paths"], ["assets/img/generated/en/figure.svg"])

    def test_figure_mode_status_uses_declared_output_signature(self) -> None:
        source = self.project / "_chapters/en/figure.qmd"
        write_figure_qmd(source)
        output = self.project / "assets/img/generated/en/figure.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<svg></svg>\n", encoding="utf-8")
        self.write_config({"python": {"image": "project:python"}})
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
        computations.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        "mode": "figure",
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "image": image,
                        "outputs": [{"path": record["output_paths"][0], **computations.file_signature(output)}],
                    }
                }
            },
        )

        self.assertTrue(computations.status(self.project)["ok"])
        output.write_text("<svg><text>changed</text></svg>\n", encoding="utf-8")

        self.assertEqual(computations.status(self.project)["sources"][0]["reason"], "output_modified")

    def test_figure_mode_publishes_staged_declared_output(self) -> None:
        source = self.project / "_chapters/en/figure.qmd"
        write_figure_qmd(source)
        config, _ = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        stage = self.project / "tmp/stage"
        staged = stage / "figure.svg"
        staged.parent.mkdir(parents=True)
        staged.write_text("<svg><text>new</text></svg>\n", encoding="utf-8")

        computations.publish_figure_outputs(record, stage, confirm_overwrite=False, owned=False)

        self.assertEqual((self.project / record["output_paths"][0]).read_text(encoding="utf-8"), "<svg><text>new</text></svg>\n")

    def test_figure_mode_refuses_unmanaged_staged_replacement(self) -> None:
        source = self.project / "_chapters/en/figure.qmd"
        write_figure_qmd(source)
        config, _ = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        output = self.project / record["output_paths"][0]
        output.parent.mkdir(parents=True)
        output.write_text("<svg><text>author</text></svg>\n", encoding="utf-8")
        stage = self.project / "tmp/stage"
        staged = stage / "figure.svg"
        staged.parent.mkdir(parents=True)
        staged.write_text("<svg><text>new</text></svg>\n", encoding="utf-8")

        with self.assertRaisesRegex(computations.ComputationError, "unmanaged generated figure"):
            computations.publish_figure_outputs(record, stage, confirm_overwrite=False, owned=False)

        self.assertEqual(output.read_text(encoding="utf-8"), "<svg><text>author</text></svg>\n")

    def test_rejects_generated_paths_outside_managed_roots(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        front = yaml.safe_load(source.read_text(encoding="utf-8").split("---", 2)[1])
        front["unaltraweb_compute"]["output"] = "README.md"
        source.write_text("---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n", encoding="utf-8")
        config, _ = computations.load_config(self.project)

        with self.assertRaisesRegex(computations.ComputationError, "configured source root"):
            computations.discover_sources(self.project, config)

    def test_rejects_overlapping_figure_directories(self) -> None:
        first = self.project / "_chapters/en/first.qmd"
        second = self.project / "_chapters/en/second.qmd"
        write_qmd(first)
        write_qmd(second)
        for path, figures in [(first, "assets/img/generated/en/shared"), (second, "assets/img/generated/en/shared/nested")]:
            text = path.read_text(encoding="utf-8")
            front = yaml.safe_load(text.split("---", 2)[1])
            front["ref"] = path.stem
            front["unaltraweb_compute"]["figures"] = figures
            path.write_text("---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n", encoding="utf-8")
        config, _ = computations.load_config(self.project)

        with self.assertRaisesRegex(computations.ComputationError, "overlap on generated figures"):
            computations.discover_sources(self.project, config)

    def test_qmd_requires_explicit_engine(self) -> None:
        path = self.project / "_chapters/en/chapter.qmd"
        path.parent.mkdir(parents=True)
        path.write_text("---\ntitle: Chapter\nlang: en\nref: chapter\n---\n", encoding="utf-8")
        config, _ = computations.load_config(self.project)

        with self.assertRaisesRegex(computations.ComputationError, "must declare"):
            computations.discover_sources(self.project, config)

    def test_script_front_matter_preserves_nested_yaml(self) -> None:
        sources = {
            "chapter.R": "#' ---\n#' title: Chapter\n#' execute:\n#'   echo: false\n#' unaltraweb_compute:\n#'   engine: r\n#' ---\n",
            "chapter.py": "# ---\n# title: Chapter\n# execute:\n#   echo: false\n# unaltraweb_compute:\n#   engine: python\n# ---\n",
        }

        for name, text in sources.items():
            with self.subTest(name=name):
                path = self.project / name
                path.write_text(text, encoding="utf-8")
                front = computations.read_front_matter(path)

                self.assertEqual(front["execute"], {"echo": False})
                self.assertIn(front["unaltraweb_compute"]["engine"], {"r", "python"})

    def test_status_yaml_fallback_supports_compute_config_without_pyyaml(self) -> None:
        source = self.project / "assets/quarto/color/figure.qmd"
        write_figure_qmd(source, output="assets/img/color/figure.svg")
        path = self.project / ".unaltraweb/computations.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """version: 1
source_roots:
  - _chapters
  - assets/quarto
engines:
  python:
    local_image: tigit-compute-python:local
    lockfiles:
      - requirements-compute.txt
""",
            encoding="utf-8",
        )
        (self.project / "requirements-compute.txt").write_text("matplotlib\n", encoding="utf-8")

        with patch.object(computations, "yaml", None):
            config, _ = computations.load_config(self.project)
            records = computations.discover_sources(self.project, config)

        self.assertEqual(config["source_roots"], ["_chapters", "assets/quarto"])
        self.assertEqual(records[0]["output_paths"], ["assets/img/color/figure.svg"])

    def test_environment_image_override_wins_over_project_configuration(self) -> None:
        self.write_config({"python": {"image": "registry/project:main"}})
        config, _ = computations.load_config(self.project)

        with patch.dict("os.environ", {"COMPUTE_PYTHON_IMAGE": "project:temporary"}):
            result = computations.resolve_image(config, "python")

        self.assertEqual(result["image"], "project:temporary")
        self.assertEqual(result["source"], "environment:COMPUTE_PYTHON_IMAGE")

    @patch.object(computations, "run_command")
    @patch.object(computations, "inspect_image", return_value={"available": "false", "id": "", "digest": ""})
    def test_image_override_is_pulled_instead_of_building_project_dockerfile(self, _inspect_image, run_command) -> None:
        dockerfile = self.project / "Dockerfile.compute"
        dockerfile.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n", encoding="utf-8")
        self.write_config(
            {
                "python": {
                    "image": "registry/project:main",
                    "local_image": "project:local",
                    "dockerfile": "Dockerfile.compute",
                }
            }
        )
        config, _ = computations.load_config(self.project)

        with patch.dict("os.environ", {"COMPUTE_PYTHON_IMAGE": "registry/override:ci"}):
            result = computations.build_engine_image(self.project, config, "python")

        self.assertEqual(result["action"], "pull")
        run_command.assert_called_once_with(["docker", "pull", "registry/override:ci"])

    @patch.object(computations, "run_command")
    def test_local_environment_builds_configured_project_image(self, run_command) -> None:
        dockerfile = self.project / "Dockerfile.compute"
        dockerfile.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n", encoding="utf-8")
        self.write_config(
            {
                "python": {
                    "local_image": "project:local",
                    "base_image": "registry/base:main",
                    "dockerfile": "Dockerfile.compute",
                    "context": ".",
                }
            }
        )
        config, _ = computations.load_config(self.project)

        with patch.dict("os.environ", {"COMPUTE_ENV": "local", "COMPUTE_DOCKER_BUILD_NETWORK": "host"}, clear=False):
            result = computations.build_engine_image(self.project, config, "python")

        self.assertEqual(result["action"], "build")
        command = run_command.call_args.args[0]
        self.assertEqual(command[:4], ["docker", "build", "--network", "host"])
        self.assertIn("BASE_IMAGE=registry/base:main", command)
        self.assertIn("project:local", command)

    @patch.object(computations, "run_command")
    def test_local_image_name_defaults_when_project_dockerfile_is_configured(self, run_command) -> None:
        dockerfile = self.project / "Dockerfile.compute"
        dockerfile.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n", encoding="utf-8")
        self.write_config({"python": {"dockerfile": "Dockerfile.compute"}})
        config, _ = computations.load_config(self.project)

        with patch.dict("os.environ", {"COMPUTE_ENV": "local", "COMPUTE_PYTHON_IMAGE": ""}, clear=False):
            selected = computations.resolve_image(config, "python")
            result = computations.build_engine_image(self.project, config, "python")

        expected = f"{self.project.name}-compute-python:local"
        self.assertEqual(selected["image"], expected)
        self.assertEqual(result["action"], "build")
        self.assertIn(expected, run_command.call_args.args[0])

    def test_default_local_image_name_is_docker_safe(self) -> None:
        config = {"project_name": "My Manual Project!"}

        self.assertEqual(computations.default_local_image(config, "python"), "my-manual-project-compute-python:local")

    @patch.object(computations, "run_command")
    def test_make_override_still_builds_matching_local_project_image(self, run_command) -> None:
        dockerfile = self.project / "Dockerfile.compute"
        dockerfile.write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n", encoding="utf-8")
        self.write_config(
            {
                "python": {
                    "local_image": "project:local",
                    "dockerfile": "Dockerfile.compute",
                }
            }
        )
        config, _ = computations.load_config(self.project)

        with patch.dict("os.environ", {"COMPUTE_ENV": "local", "COMPUTE_PYTHON_IMAGE": "project:local"}, clear=False):
            result = computations.build_engine_image(self.project, config, "python")

        self.assertEqual(result["action"], "build")
        self.assertIn("project:local", run_command.call_args.args[0])

    def test_input_and_lockfile_changes_make_output_stale(self) -> None:
        data = self.project / "data/input.csv"
        data.parent.mkdir(parents=True)
        data.write_text("value\n1\n", encoding="utf-8")
        lockfile = self.project / "requirements-compute.txt"
        lockfile.write_text("matplotlib==3.10.5\n", encoding="utf-8")
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source, inputs=["data/input.csv"])
        self.write_config({"python": {"image": "project:python", "lockfiles": ["requirements-compute.txt"]}})
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
        record["output"].parent.mkdir(parents=True, exist_ok=True)
        record["output"].write_text("generated\n", encoding="utf-8")
        record["figures"].mkdir(parents=True)
        computations.write_lock(
            self.project,
            {
                "version": 1,
                "records": {
                    record["source_path"]: {
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "image": image,
                        "output": {"path": record["output_path"], **computations.file_signature(record["output"])},
                        "figures": record["figures_path"],
                        "assets": [],
                    }
                },
            },
        )

        self.assertTrue(computations.status(self.project)["ok"])
        data.write_text("value\n2\n", encoding="utf-8")
        stale = computations.status(self.project)

        self.assertFalse(stale["ok"])
        self.assertEqual(stale["sources"][0]["reason"], "source_or_environment_changed")

    def test_stale_only_skips_current_figure_output(self) -> None:
        source = self.project / "_chapters/en/05-figure.qmd"
        write_figure_qmd(source)
        output = self.project / "assets/img/generated/en/figure.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<svg />", encoding="utf-8")
        self.write_config({"python": {"image": "project:python", "lockfiles": ["requirements-compute.txt"]}})
        lockfile = self.project / "requirements-compute.txt"
        lockfile.write_text("matplotlib==3.10.5\n", encoding="utf-8")
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
        computations.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        "mode": "figure",
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "image": image,
                        "image_identity": {"id": "", "digest": ""},
                        "outputs": [{"path": record["output_paths"][0], **computations.file_signature(output)}],
                    }
                },
            },
        )

        with patch.object(computations, "render_figure_outputs", return_value={"available": "true", "id": "", "digest": ""}) as render_call:
            result = computations.render(self.project, stale_only=True)

        render_call.assert_not_called()
        self.assertEqual(result["rendered_count"], 0)

    def test_stale_only_renders_source_changed_figure(self) -> None:
        source = self.project / "_chapters/en/05-figure.qmd"
        write_figure_qmd(source)
        output = self.project / "assets/img/generated/en/figure.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<svg />", encoding="utf-8")
        self.write_config({"python": {"image": "project:python", "lockfiles": ["requirements-compute.txt"]}})
        lockfile = self.project / "requirements-compute.txt"
        lockfile.write_text("matplotlib==3.10.5\n", encoding="utf-8")
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
        computations.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        "mode": "figure",
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "image": image,
                        "image_identity": {"id": "", "digest": ""},
                        "outputs": [{"path": record["output_paths"][0], **computations.file_signature(output)}],
                    }
                },
            },
        )
        source.write_text(source.read_text(encoding="utf-8").replace("Computed figure", "Computed figure v2"), encoding="utf-8")

        with patch.object(computations, "render_figure_outputs", return_value={"available": "true", "id": "", "digest": ""}) as render_call:
            result = computations.render(self.project, stale_only=True)

        render_call.assert_called_once()
        self.assertEqual(result["rendered_count"], 1)

    def test_stale_only_never_replaces_unmanaged_existing_figure(self) -> None:
        source = self.project / "_chapters/en/05-figure.qmd"
        write_figure_qmd(source)
        output = self.project / "assets/img/generated/en/figure.svg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<svg />", encoding="utf-8")
        self.write_config({"python": {"image": "project:python"}})

        with patch.object(computations, "render_figure_outputs", return_value={"available": "true", "id": "", "digest": ""}) as render_call:
            result = computations.render(self.project, stale_only=True)

        render_call.assert_not_called()
        self.assertEqual(result["rendered_count"], 0)

    def test_stale_only_skips_current_and_renders_stale_chapter(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source, inputs=["data/input.csv"])
        data = self.project / "data/input.csv"
        data.parent.mkdir(parents=True)
        data.write_text("value\n1\n", encoding="utf-8")
        self.write_config({"python": {"image": "project:python"}})
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        output = self.project / record["output_path"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("generated\n", encoding="utf-8")
        record["figures"].mkdir(parents=True)
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
        computations.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "image": image,
                        "output": {"path": record["output_path"], **computations.file_signature(record["output"])},
                        "figures": record["figures_path"],
                        "assets": [],
                    }
                },
            },
        )

        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})) as render_call:
            computations.render(self.project, stale_only=True)
        render_call.assert_not_called()

        data.write_text("value\n2\n", encoding="utf-8")
        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})) as render_call:
            computations.render(self.project, stale_only=True)
        render_call.assert_called_once()

    def test_source_scoped_status_does_not_report_other_sources_as_orphans(self) -> None:
        first = self.project / "_chapters/en/first.qmd"
        second = self.project / "_chapters/en/second.qmd"
        write_qmd(first)
        write_qmd(second)
        second.write_text(second.read_text(encoding="utf-8").replace("computed-chapter", "computed-second"), encoding="utf-8")
        config, config_path = computations.load_config(self.project)
        lock = {"records": {}}
        for record in computations.discover_sources(self.project, config):
            digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record)
            record["output"].write_text("generated\n", encoding="utf-8")
            record["figures"].mkdir(parents=True)
            lock["records"][record["source_path"]] = {
                "fingerprint": digest,
                "dependencies": dependencies,
                "image": image,
                "output": {"path": record["output_path"], **computations.file_signature(record["output"])},
                "assets": [],
            }
        computations.write_lock(self.project, lock)

        result = computations.status(self.project, source="_chapters/en/first.qmd")

        self.assertTrue(result["ok"])
        self.assertEqual(result["orphaned_records"], [])

    def test_orphan_record_remains_a_freshness_failure_after_partial_render(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        computations.write_lock(self.project, {"records": {"_chapters/en/deleted.qmd": {}}})

        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})):
            computations.render(self.project, source="_chapters/en/05-computed.qmd")

        result = computations.status(self.project)
        self.assertIn("_chapters/en/deleted.qmd", result["orphaned_records"])
        self.assertFalse(result["ok"])

    def test_full_render_prunes_orphan_record_only_after_artifacts_are_absent(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        computations.write_lock(
            self.project,
            {
                "records": {
                    "_chapters/en/deleted.qmd": {
                        "output": {"path": "_chapters/en/deleted.md"},
                        "figures": "assets/img/generated/en/deleted",
                    }
                }
            },
        )

        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})):
            computations.render(self.project, confirm_overwrite=True)

        self.assertNotIn("_chapters/en/deleted.qmd", computations.load_lock(self.project)["records"])

    def test_full_render_prunes_orphan_record_when_new_source_owns_paths(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        output = self.project / "_chapters/en/05-computed.md"
        figures = self.project / "assets/img/generated/en/computed-chapter"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("previous generated\n", encoding="utf-8")
        figures.mkdir(parents=True, exist_ok=True)
        computations.write_lock(
            self.project,
            {
                "records": {
                    "_chapters/en/05-computed.R": {
                        "output": {"path": "_chapters/en/05-computed.md", **computations.file_signature(output)},
                        "figures": "assets/img/generated/en/computed-chapter",
                        "assets": [],
                    }
                }
            },
        )

        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})):
            computations.render(self.project, confirm_overwrite=True)

        records = computations.load_lock(self.project)["records"]
        self.assertIn("_chapters/en/05-computed.qmd", records)
        self.assertNotIn("_chapters/en/05-computed.R", records)

    def test_explicit_prune_removes_absent_orphan_after_engine_renders(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        computations.write_lock(
            self.project,
            {"records": {"_chapters/en/deleted.qmd": {"output": {"path": "_chapters/en/deleted.md"}, "figures": "assets/img/generated/en/deleted"}}},
        )

        with patch.object(computations, "render_stage", return_value=("generated\n", [], {"available": "true", "id": "image", "digest": ""})):
            computations.render(self.project, engine="python")
        result = computations.prune(self.project)

        self.assertEqual(result["removed_records"], ["_chapters/en/deleted.qmd"])

    @patch.object(computations, "inspect_image", return_value={"available": "false", "id": "", "digest": ""})
    def test_status_reuses_recorded_identity_when_image_is_unavailable(self, _inspect_image) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        self.write_config({"python": {"image": "registry/project@sha256:1234"}})
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        saved = {
            "image": computations.resolve_image(config, "python"),
            "image_identity": {"available": "true", "id": "sha256:local", "digest": "registry/project@sha256:1234"},
        }
        digest, dependencies, image = computations.fingerprint(self.project, config, config_path, record, saved)
        record["output"].parent.mkdir(parents=True, exist_ok=True)
        record["output"].write_text("generated\n", encoding="utf-8")
        record["figures"].mkdir(parents=True)
        computations.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        **saved,
                        "fingerprint": digest,
                        "dependencies": dependencies,
                        "output": {"path": record["output_path"], **computations.file_signature(record["output"])},
                        "figures": record["figures_path"],
                        "assets": [],
                    }
                }
            },
        )

        self.assertTrue(computations.status(self.project)["ok"])

    @patch.object(computations, "inspect_image", return_value={"available": "true", "id": "sha256:new", "digest": ""})
    def test_available_image_identity_overrides_recorded_identity(self, _inspect_image) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        self.write_config({"python": {"image": "project:python"}})
        config, config_path = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        saved = {
            "image": computations.resolve_image(config, "python"),
            "image_identity": {"available": "true", "id": "sha256:old", "digest": ""},
        }

        current, _, _ = computations.fingerprint(self.project, config, config_path, record, saved)
        with patch.object(computations, "inspect_image", return_value={"available": "true", "id": "sha256:old", "digest": ""}):
            recorded, _, _ = computations.fingerprint(self.project, config, config_path, record, saved)

        self.assertNotEqual(current, recorded)

    def test_first_render_refuses_to_replace_unmanaged_output(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        config, _ = computations.load_config(self.project)
        record = computations.discover_sources(self.project, config)[0]
        record["output"].write_text("author content\n", encoding="utf-8")

        with self.assertRaisesRegex(computations.ComputationError, "unmanaged"):
            computations.publish_render(self.project, record, "generated\n", [], False, False)

    def test_generated_markdown_preserves_public_front_matter_only(self) -> None:
        source = self.project / "_chapters/en/05-computed.qmd"
        write_qmd(source)
        front = computations.read_front_matter(source)

        output = computations.yaml_front(front)

        self.assertIn("layout: manual-chapter", output)
        self.assertNotIn("unaltraweb_compute", output)

    def test_quarto_html_figure_becomes_captioned_markdown_and_versioned_asset(self) -> None:
        stage = self.project / "tmp/stage"
        markdown = stage / "chapter.md"
        media = stage / "chapter_files/figure-commonmark/plot.png"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"png")
        markdown.write_text("", encoding="utf-8")
        body = '''<div id="fig-plot">
<img src="chapter_files/figure-commonmark/plot.png"
data-fig-alt="A useful plot" alt="A useful plot" />
Figure&nbsp;1: Computed result
</div>'''

        rendered, copies = computations.generated_media(stage, markdown, body, "assets/img/generated/en/chapter")

        self.assertIn('![A useful plot]({{ site.baseurl }}/assets/img/generated/en/chapter/chapter_files/figure-commonmark/plot.png "Computed result")', rendered)
        self.assertEqual(len(copies), 1)

    def test_lock_file_is_deterministic_json(self) -> None:
        computations.write_lock(self.project, {"records": {"b": {"value": 2}, "a": {"value": 1}}})

        data = json.loads((self.project / computations.LOCK_PATH).read_text(encoding="utf-8"))

        self.assertEqual(data["version"], 1)
        self.assertEqual(list(data["records"]), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
