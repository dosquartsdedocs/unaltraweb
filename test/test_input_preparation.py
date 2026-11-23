from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp import input_preparation as inputs, site_tools
from unaltraweb_mcp.editorial_sources import digest


class InputPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("sandbox/\ndist/\n")
        self.site = {"unaltraweb": {"site_profile": "unaltremanual"}, "exclude": ["practiques/", "sandbox/", "dist/"]}
        self.raw = b"municipality,value\nSynthetic,10\n"
        self.manifest = {
            "schema_version": 1, "kind": "tigit-teaching-resources", "version": "2026-10-14",
            "source_commit": "1" * 40, "source_prefix": "_practices/demo/",
            "source_url": "https://raw.githubusercontent.com/example/manual/" + "1" * 40 + "/_practices/demo/",
            "snapshot": "sandbox/practiques/demo/recursos/2026-10-14",
            "files": [{"path": "data/table.csv", "sha256": digest(self.raw), "bytes": len(self.raw)}],
        }
        self.manifest_path = "practiques/demo/recursos.yml"
        self.config_path = ".unaltraweb/input-preparation.json"
        self.write_sources()

    def write_sources(self):
        (self.root / "_config.yml").write_text(json.dumps(self.site))
        manifest = self.root / self.manifest_path
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(self.manifest))
        config = self.root / self.config_path
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({"schema_version": 1, "resources": [{"profile": "immutable-github-files-v1", "manifest": self.manifest_path, "sha256": digest(manifest.read_bytes())}]}))
        self.sha = digest(config.read_bytes())
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore", "_config.yml", self.config_path, self.manifest_path], check=True)

    def prepare(self, **kwargs):
        return inputs.prepare(self.root, self.config_path, self.sha, **kwargs)

    def stream(self, url):
        self.assertEqual(url, self.manifest["source_url"] + "data/table.csv")
        return io.BytesIO(self.raw)

    def test_pinned_native_preparation_readback_and_readonly_reuse(self):
        result = self.prepare(allow_fetch=True, opener=self.stream)
        self.assertFalse(result["publishes"])
        self.assertFalse(result["renders"])
        self.assertEqual(result["snapshots"][0]["state"], "prepared")
        target = self.root / self.manifest["snapshot"]
        self.assertEqual((target / "data/table.csv").read_bytes(), self.raw)
        before = {path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        with patch.object(inputs, "fetch", side_effect=AssertionError("check cannot fetch")):
            checked = self.prepare(check_only=True, opener=lambda _: self.fail("must not fetch"))
        self.assertEqual(checked["snapshots"][0]["state"], "current")
        self.assertEqual(before, {path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()})
        (target / "data/table.csv").write_bytes(b"author modification")
        with self.assertRaisesRegex(ValueError, "changed"), patch.object(inputs, "fetch") as fetch:
            self.prepare(allow_fetch=True)
        fetch.assert_not_called()
        self.assertEqual((target / "data/table.csv").read_bytes(), b"author modification")

    def test_missing_data_needs_explicit_fetch_and_source_only_checks_do_not_hydrate(self):
        with self.assertRaisesRegex(ValueError, "explicit --fetch"):
            self.prepare()
        self.assertFalse((self.root / "sandbox").exists())
        workflow = (Path(__file__).resolve().parents[1] / "src/unaltraweb_mcp/scaffolds/common/.github/workflows/source-checks.yml.tmpl").read_text()
        self.assertNotIn("input_preparation", workflow)
        self.assertNotIn("--fetch", workflow)
        self.assertNotIn("manual-inputs-prepare", workflow)

    def test_corrupt_absent_and_auth_failure_retain_attempt_but_never_install_snapshot(self):
        for name in ("corrupt", "size", "absent", "auth"):
            with self.subTest(name=name):
                def failed(url):
                    if name in {"absent", "auth"}:
                        raise OSError(name)
                    return io.BytesIO(b"corrupt" if name == "corrupt" else self.raw + b"more")
                with self.assertRaises((ValueError, OSError)):
                    self.prepare(allow_fetch=True, opener=failed)
                self.assertFalse((self.root / self.manifest["snapshot"]).exists())
        attempts = list((self.root / Path(self.manifest["snapshot"]).parent).glob(".inputs-*"))
        self.assertEqual(len(attempts), 4)

    def test_manifest_and_top_config_hashes_are_required_before_network(self):
        with self.assertRaisesRegex(ValueError, "reviewed SHA"), patch.object(inputs, "fetch") as fetch:
            inputs.prepare(self.root, self.config_path, "0" * 64, allow_fetch=True)
        fetch.assert_not_called()
        manifest = self.root / self.manifest_path
        manifest.write_bytes(manifest.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "reviewed SHA"):
            self.prepare(allow_fetch=True)
        self.assertFalse((self.root / "sandbox").exists())

    def test_paths_git_policy_exclusions_and_symlinks_are_boundaries(self):
        original = copy.deepcopy(self.manifest)
        for snapshot in ("_site/data", "../escape", "sandbox/other/data", "assets/private", "sandbox/practiques/demo/../escape"):
            self.manifest = {**original, "snapshot": snapshot}
            self.write_sources()
            with self.subTest(snapshot=snapshot), self.assertRaises(Exception):
                self.prepare(allow_fetch=True, opener=self.stream)
        self.manifest = original
        self.write_sources()
        (self.root / "outside").mkdir()
        (self.root / "sandbox").symlink_to(self.root / "outside", target_is_directory=True)
        with self.assertRaises((ValueError, OSError, RuntimeError)):
            self.prepare(allow_fetch=True, opener=self.stream)
        self.assertEqual(list((self.root / "outside").iterdir()), [])
        (self.root / "sandbox").unlink()
        for include in ("sandbox", "sandbox/**", "**/*.csv", "."):
            self.site["include"] = [include]
            self.write_sources()
            with self.subTest(include=include), self.assertRaisesRegex(ValueError, "Jekyll include"):
                self.prepare(allow_fetch=True, opener=self.stream)
        self.site.pop("include")
        self.site["exclude"].remove("sandbox/")
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "exclusions"):
            self.prepare(allow_fetch=True, opener=self.stream)

    def test_no_moving_source_url_live_query_executable_or_duplicate_config(self):
        for field, value in (("source_commit", "main"), ("source_url", "https://example.org/latest.csv"), ("source_url", self.manifest["source_url"] + "?token=x")):
            changed = {**self.manifest, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                inputs.inventory(changed)
        config = self.root / self.config_path
        for body in ('{"schema_version":1,"schema_version":1,"resources":[]}', '{"schema_version":1,"resources":[],"command":"python preparer.py"}'):
            config.write_text(body)
            with self.assertRaises((ValueError, inputs.h.HandoffError)):
                inputs.prepare(self.root, self.config_path, digest(config.read_bytes()), allow_fetch=True)

    def test_control_change_during_fetch_prevents_installation(self):
        def mutate(url):
            path = self.root / self.manifest_path
            path.write_bytes(path.read_bytes() + b" ")
            return io.BytesIO(self.raw)
        with self.assertRaises(ValueError):
            self.prepare(allow_fetch=True, opener=mutate)
        self.assertFalse((self.root / self.manifest["snapshot"]).exists())

    def test_hydration_restores_native_freshness_without_rendering_or_editing_lock(self):
        from computations.test_render import computations, write_figure_qmd
        import yaml

        self.prepare(allow_fetch=True, opener=self.stream)
        source = self.root / "assets/quarto/fixture.qmd"
        output_path = "assets/img/generated/fixture.svg"
        write_figure_qmd(source, output=output_path)
        front = yaml.safe_load(source.read_text().split("---", 2)[1])
        input_path = self.manifest["snapshot"] + "/data/table.csv"
        front["unaltraweb_compute"]["inputs"] = [input_path]
        source.write_text("---\n" + yaml.safe_dump(front) + "---\n\nSynthetic figure source.\n")
        compute_config = self.root / ".unaltraweb/computations.yml"
        compute_config.write_text(yaml.safe_dump({"version": 1, "source_roots": ["assets/quarto"],
            "generated_assets_root": "assets/img/generated", "engines": {"python": {"image": "synthetic/python:fixture"}}}))
        output = self.root / output_path
        output.parent.mkdir(parents=True)
        output.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Synthetic pre-existing producer output</text></svg>')
        config, config_path = computations.load_config(self.root)
        record = computations.discover_sources(self.root, config)[0]
        fingerprint, dependencies, image = computations.fingerprint(self.root, config, config_path, record)
        computations.write_lock(self.root, {"records": {record["source_path"]: {"mode": "figure", "fingerprint": fingerprint,
            "dependencies": dependencies, "image": image, "outputs": [{"path": output_path, **computations.file_signature(output)}]}}})
        lock_path = self.root / ".unaltraweb/computations.lock.json"
        lock = lock_path.read_bytes()
        self.assertTrue(computations.status(self.root)["ok"])
        (self.root / self.manifest["snapshot"]).rename(self.root / "retained-original-fixture")
        with patch.object(computations, "run_command", side_effect=AssertionError("Freshness/hydration must not render")):
            with self.assertRaisesRegex(computations.ComputationError, "Missing computation input"):
                computations.status(self.root)
            self.prepare(allow_fetch=True, opener=self.stream)
            self.assertTrue(computations.status(self.root)["ok"])
            (self.root / input_path).write_bytes(b"changed after hydration")
            self.assertFalse(computations.status(self.root)["ok"])
        self.assertEqual(lock_path.read_bytes(), lock)
        self.assertFalse((self.root / "_site").exists())

    def test_scaffolds_have_explicit_noop_configuration_and_no_automatic_fetch(self):
        project = self.root / "new-site"
        site_tools.new_web(project, site_profile_value="unaltremanual")
        self.assertEqual(json.loads((project / self.config_path).read_bytes()), {"schema_version": 1, "resources": []})
        makefile = (project / "Makefile").read_text()
        self.assertIn("manual-inputs-prepare: runtime-image", makefile)
        self.assertNotIn("build: manual-inputs-prepare", makefile)
        self.assertIn("INPUT_PREPARATION_FETCH ?= 0", makefile)


if __name__ == "__main__":
    unittest.main()
