from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "web_captures" / "render.py"
SPEC = importlib.util.spec_from_file_location("unaltraweb_web_captures", MODULE_PATH)
assert SPEC and SPEC.loader
captures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(captures)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def write_recipe(destination: Path, **overrides: object) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    recipe: dict[str, object] = {
        "version": 1,
        "path": "/manual/chapter/",
        "viewport": {"width": 1280, "height": 720},
        "theme": {
            "setting": "cafe",
            "expect": {"selector": "html", "attribute": "data-theme", "equals": "cafe"},
        },
        "waits": {"selectors": [".manual-content"]},
        "annotations": [
            {
                "id": "chapter-nav",
                "selector": ".manual-sidebar",
                "kind": "arrow",
                "text": "Chapter navigation",
            }
        ],
    }
    recipe.update(overrides)
    destination.write_text(yaml.safe_dump(recipe, sort_keys=False), encoding="utf-8")


class WebCaptureRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name).resolve()
        self.source = self.project / "assets/captures/manual.capture.yml"
        write_recipe(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_discovers_source_and_preserves_capture_basename(self) -> None:
        records = captures.discover(self.project)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_path"], "assets/captures/manual.capture.yml")
        self.assertEqual(captures.relative(self.project, records[0]["png"]), "assets/captures/manual.capture.png")
        self.assertEqual(captures.relative(self.project, records[0]["svg"]), "assets/captures/manual.capture.svg")
        self.assertEqual(captures.relative(self.project, records[0]["edited"]), "assets/captures/manual.capture.edited.svg")

    def test_rejects_remote_recipe_url(self) -> None:
        write_recipe(self.source, path="https://example.com/manual/")

        with self.assertRaisesRegex(captures.WebCaptureError, "local absolute URL path"):
            captures.discover(self.project)

    def test_rejects_unknown_recipe_keys_and_script_like_selectors(self) -> None:
        write_recipe(self.source, script="alert(1)")
        with self.assertRaisesRegex(captures.WebCaptureError, "Unknown capture recipe keys"):
            captures.discover(self.project)

        write_recipe(self.source, annotations=[{"selector": "main\nscript", "kind": "outline"}])
        with self.assertRaisesRegex(captures.WebCaptureError, "CSS selector"):
            captures.discover(self.project)

    def test_rejects_mutually_exclusive_capture_modes(self) -> None:
        write_recipe(self.source, capture={"full_page": True, "selector": "main"})

        with self.assertRaisesRegex(captures.WebCaptureError, "mutually exclusive"):
            captures.discover(self.project)

    def test_clip_padding_is_preserved(self) -> None:
        write_recipe(self.source, capture={"clip": {"selector": "main", "padding": 24}})

        record = captures.discover(self.project)[0]

        self.assertEqual(record["recipe"]["capture"]["clip"], {"selector": "main", "padding": 24})

    def test_selected_source_cannot_escape_project(self) -> None:
        with self.assertRaisesRegex(captures.WebCaptureError, "safe project-relative"):
            captures.status(self.project, source="../outside.capture.yml")

    def test_svg_embeds_original_png_and_vector_layers(self) -> None:
        record = captures.discover(self.project)[0]
        png = self.project / "tmp.png"
        png.write_bytes(PNG_1X1)
        worker = {
            "browser_version": "123.0",
            "device_scale_factor": 1,
            "origin": {"x": 0, "y": 0},
            "annotations": [
                {
                    **record["recipe"]["annotations"][0],
                    "box": {"x": 0, "y": 0, "width": 1, "height": 1},
                }
            ],
        }

        rendered = captures.svg_for(self.project, record, png, worker, "fingerprint")

        self.assertIn(base64.b64encode(PNG_1X1).decode("ascii"), rendered)
        self.assertIn('inkscape:label="Background"', rendered)
        self.assertIn('inkscape:label="Highlights"', rendered)
        self.assertIn('inkscape:label="Arrows"', rendered)
        self.assertIn('inkscape:label="Labels"', rendered)
        self.assertIn('id="annotation-chapter-nav"', rendered)
        self.assertIn("Chapter navigation", rendered)
        metadata_match = captures.SVG_METADATA_RE.search(rendered)
        self.assertIsNotNone(metadata_match)

    @patch.object(captures, "inspect_image", return_value={"available": "false", "id": "", "digest": ""})
    def test_status_detects_current_outputs_and_stale_edited_override(self, _inspect_image) -> None:
        record = captures.discover(self.project)[0]
        record["png"].write_bytes(PNG_1X1)
        record["svg"].write_text("<svg/>", encoding="utf-8")
        fingerprint, dependencies, image = captures.fingerprint(self.project, record)
        captures.write_lock(
            self.project,
            {
                "records": {
                    record["source_path"]: {
                        "fingerprint": fingerprint,
                        "dependencies": dependencies,
                        "image": image["image"],
                        "png": {"path": captures.relative(self.project, record["png"]), **captures.file_signature(record["png"])},
                        "svg": {"path": captures.relative(self.project, record["svg"]), **captures.file_signature(record["svg"])},
                    }
                }
            },
        )

        self.assertTrue(captures.status(self.project)["ok"])
        stale_metadata = json.dumps({"png_sha256": "old", "fingerprint": fingerprint})
        record["edited"].write_text(f'<svg><metadata id="unaltraweb-capture">{stale_metadata}</metadata></svg>', encoding="utf-8")
        result = captures.status(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["captures"][0]["reason"], "edited_override_stale")

    @patch.object(captures, "inspect_image", return_value={"available": "false", "id": "", "digest": ""})
    def test_edited_override_must_match_current_fingerprint(self, _inspect_image) -> None:
        record = captures.discover(self.project)[0]
        record["png"].write_bytes(PNG_1X1)
        record["svg"].write_text("<svg/>", encoding="utf-8")
        fingerprint, dependencies, image = captures.fingerprint(self.project, record)
        metadata = json.dumps({"png_sha256": captures.file_signature(record["png"])["sha256"], "fingerprint": "old"})
        record["edited"].write_text(f'<svg><metadata id="unaltraweb-capture">{metadata}</metadata></svg>', encoding="utf-8")
        captures.write_lock(
            self.project,
            {"records": {record["source_path"]: {"fingerprint": fingerprint, "dependencies": dependencies, "image": image["image"], "png": captures.file_signature(record["png"]), "svg": captures.file_signature(record["svg"])}}},
        )

        result = captures.status(self.project)

        self.assertEqual(result["captures"][0]["reason"], "edited_override_stale")

    def test_status_rejects_orphaned_capture_artifacts(self) -> None:
        orphan = self.project / "assets/captures/old.capture.svg"
        orphan.write_text("<svg/>", encoding="utf-8")

        result = captures.status(self.project)

        self.assertFalse(result["ok"])
        self.assertEqual(result["orphaned_artifacts"], ["assets/captures/old.capture.svg"])

    def test_first_publish_refuses_unmanaged_output(self) -> None:
        record = captures.discover(self.project)[0]
        record["svg"].write_text("author content", encoding="utf-8")
        temporary = self.project / "capture.png"
        temporary.write_bytes(PNG_1X1)

        with self.assertRaisesRegex(captures.WebCaptureError, "unmanaged"):
            captures.publish(record, temporary, "<svg/>", confirm_overwrite=False, owned=False)

    def test_svg_safety_rejects_scripts_and_external_images(self) -> None:
        unsafe = self.project / "unsafe.svg"
        for text in [
            "<svg><script>alert(1)</script></svg>",
            '<svg><image href="https://example.com/x.png"/></svg>',
            '<svg><style>@import url("https://example.com/x.css");</style></svg>',
            '<svg><rect style="fill:url(https://example.com/x.svg)"/></svg>',
            '<svg xml:base="https://example.com/"><use href="#shape"/></svg>',
            '<svg><animate attributeName="href" to="https://example.com/x.svg"/></svg>',
        ]:
            with self.subTest(text=text):
                unsafe.write_text(text, encoding="utf-8")
                with self.assertRaises(captures.WebCaptureError):
                    captures.validate_svg_safety(unsafe)

    def test_base_url_is_an_origin_only(self) -> None:
        with patch.dict("os.environ", {"WEB_CAPTURE_DOCKER_NETWORK": "capture-net", "WEB_CAPTURE_SERVICE_HOST": "capture-site"}), patch.object(captures, "internal_network", return_value=True):
            self.assertEqual(captures.validate_base_url("http://capture-site:4000/"), "http://capture-site:4000")
        for value in ["file:///tmp/site", "http://user:pass@localhost:4000", "http://localhost:4000/path", "https://example.com"]:
            with self.subTest(value=value), self.assertRaises(captures.WebCaptureError):
                captures.validate_base_url(value)

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/docker")
    def test_internal_network_must_be_marked_internal(self, _which, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "false\n"
        self.assertFalse(captures.internal_network("ordinary-bridge"))

        run.return_value.stdout = "true\n"
        self.assertTrue(captures.internal_network("capture-net"))


if __name__ == "__main__":
    unittest.main()
