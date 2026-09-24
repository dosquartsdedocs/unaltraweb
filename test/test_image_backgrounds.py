from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import image_backgrounds as images
from unaltraweb_mcp.image_probe import inspect_raster
from unaltraweb_mcp.processes import run_process

HAS_PIL = importlib.util.find_spec("PIL") is not None
HAS_CAIRO = importlib.util.find_spec("cairosvg") is not None


class ImageBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        self.write("_config.yml", "title: Example\nbaseurl: /site\ndefault_lang: en\nlanguages: [en, ca]\nunaltraweb:\n  site_profile: unaltremanual\n")

    def write(self, path, content):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
        return target

    def raster(self, mode="RGBA", colour=(12, 45, 70, 255), format="PNG", **options):
        from PIL import Image
        value = Image.new(mode, (4, 3), colour)
        stream = io.BytesIO()
        value.save(stream, format=format, **options)
        return stream.getvalue()

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_png_alpha_pixels_and_palette_transparency_not_channel_presence(self):
        from PIL import Image
        cases = [(self.raster(), "opaque"), (self.raster(colour=(90, 30, 20, 128)), "transparent"),
                 (self.raster("RGB", (0, 0, 0)), "opaque")]
        palette = Image.new("P", (3, 3), 0)
        palette.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        palette.putpixel((1, 1), 1)
        stream = io.BytesIO()
        palette.save(stream, format="PNG", transparency=1)
        cases.append((stream.getvalue(), "transparent"))
        cases.append((self.raster("RGB", (12, 45, 70), transparency=(12, 45, 70)), "transparent"))
        for index, (data, expected) in enumerate(cases):
            self.write(f"assets/{index}.png", data)
            result = images.image_background_check(self.project, f"assets/{index}.png")
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["images"][0]["state"], expected, result)
            self.assertEqual(bool(result["warnings"]), expected == "transparent")

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_other_raster_formats_and_animation_are_checked(self):
        from PIL import Image
        for format, suffix in (("JPEG", "jpg"), ("BMP", "bmp"), ("TIFF", "tif"), ("WEBP", "webp")):
            with self.subTest(format=format):
                self.write(f"assets/photo.{suffix}", self.raster("RGB", (35, 60, 120), format=format))
                self.assertEqual(images.image_background_check(self.project, f"assets/photo.{suffix}")["images"][0]["state"], "opaque")
        stream = io.BytesIO()
        Image.new("RGBA", (4, 3), (20, 30, 40, 255)).save(stream, format="PNG", save_all=True,
            append_images=[Image.new("RGBA", (4, 3), (20, 30, 40, 0))], duration=100, blend=0, disposal=0)
        self.write("assets/animated.png", stream.getvalue())
        result = images.image_background_check(self.project, "assets/animated.png")["images"][0]
        self.assertEqual(result["state"], "transparent")
        self.assertEqual(result["transparent_frame"], 1)
        self.write("assets/transparent.gif", self.raster("P", 0, format="GIF", transparency=0))
        self.assertEqual(images.image_background_check(self.project, "assets/transparent.gif")["images"][0]["state"], "transparent")

    @unittest.skipUnless(HAS_CAIRO and HAS_PIL, "CairoSVG and Pillow are package dependencies")
    def test_svg_any_background_colour_and_actual_partial_transparency(self):
        for index, (body, expected) in enumerate([
            ('<circle cx="20" cy="20" r="8" fill="red"/>', "transparent"),
            ('<rect width="100%" height="100%" fill="#182738"/>', "opaque"),
            ('<rect width="100%" height="100%" fill="#ffe0ae"/><text x="2" y="20">Label</text>', "opaque"),
            ('<rect width="100%" height="100%" fill="#fff" fill-opacity="0.5"/>', "transparent"),
            ('<rect width="25" height="40" fill="blue"/>', "transparent"),
        ]):
            self.write(f"assets/{index}.svg", f'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">{body}</svg>')
            result = images.image_background_check(self.project, f"assets/{index}.svg")["images"][0]
            self.assertEqual(result["state"], expected, result)
            self.assertEqual(result["method"], "svg-raster-sample")

    @unittest.skipUnless(HAS_CAIRO and HAS_PIL, "CairoSVG and Pillow are package dependencies")
    def test_svg_embedded_capture_is_allowed_but_external_resources_are_not(self):
        encoded = base64.b64encode(self.raster("RGB", (120, 30, 60))).decode()
        for reference, expected in (("data:image/png;base64," + encoded, "opaque"),
                                    ("file:///etc/passwd", "unverifiable"),
                                    ("https://example.invalid/private.png", "unverifiable")):
            self.write("assets/capture.svg", f'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3"><image width="4" height="3" href="{reference}"/></svg>')
            result = images.image_background_check(self.project, "assets/capture.svg")["images"][0]
            self.assertEqual(result["state"], expected, result)

    def test_escaped_image_labels_remain_bounded_and_preserve_references(self):
        result = run_process(
            [sys.executable, "-c", "from unaltraweb_mcp.image_backgrounds import _source_references; "
             "assert _source_references('![' + chr(92) * 10000) == []"],
            timeout_seconds=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        text = '\n'.join([
            r'![Escaped \] label](assets/a.png)',
            r'![Escaped \\ slash](assets/b.svg)',
            r'![Escaped \[ opening](<assets/with space.png>)',
        ])
        self.assertEqual(images._source_references(text), [
            (1, "assets/a.png"), (2, "assets/b.svg"), (3, "assets/with space.png"),
        ])

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_sources_ignore_code_examples_and_resolve_localised_edited_outputs(self):
        self.write("assets/flow.mmd", "flowchart LR\n a-->b\n")
        self.write("assets/flow.ca.mmd", "flowchart LR\n a-->b\n")
        self.write("assets/flow.ca.mmd.edited.svg", b"not an SVG")
        self.write("assets/photo.png", self.raster())
        self.write("_chapters/ca/example.md", '''---
title: Example
lang: ca
---
![Flow](assets/flow.mmd "Caption")
![Photo]({{ site.baseurl }}/assets/photo.png "Photo")
```markdown
![Example](assets/absent.png)
```
`![Inline example](assets/also-absent.png)`
''')
        result = images.image_background_check(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["image_count"], 2, result)
        self.assertEqual(result["images"][0]["path"], "assets/flow.ca.mmd.edited.svg")
        self.assertIn("author-owned", result["warnings"][0]["remediation"])

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_rendered_paths_srcsets_and_metadata_are_inspected_once(self):
        self.write("_site/assets/photo.png", self.raster(colour=(50, 60, 70, 0)))
        self.write("_site/en/index.html", '<img src="/site/assets/photo.png" srcset="../assets/photo.png 1x, /site/assets/photo.png 2x" alt="Photo">')
        result = images.image_background_check(self.project, output_folder="_site")
        self.assertEqual(result["image_count"], 1, result)
        self.assertEqual(result["images"][0]["reference_count"], 3)
        self.assertEqual(len(result["warnings"]), 1)

    def test_unsafe_missing_remote_and_unverifiable_inputs_never_claim_opacity(self):
        self.write("assets/bad.png", b"broken")
        self.write("assets/link.png", b"placeholder").unlink()
        (self.project / "assets/link.png").symlink_to("/etc/passwd")
        self.write("_pages/en/test.md", '![One](assets/link.png)\n![Remote](https://example.invalid/photo.png)\n![Broken](assets/bad.png)\n![Missing](assets/missing.svg)\n')
        result = images.image_background_check(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["warnings"]), 4, result)
        self.assertTrue(all(item["state"] == "unverifiable" for item in result["images"]))
        self.assertFalse(images.image_background_check(self.project, "../outside.png")["ok"])

    def test_check_is_read_only_and_reports_budgets_and_worker_failure(self):
        self.write("assets/test.svg", '<svg width="10" height="10"/>')
        before = {str(path): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        with patch.object(images, "CHECK_SECONDS", 0):
            result = images.image_background_check(self.project, "assets/test.svg")
        self.assertEqual(result["images"][0]["state"], "unverifiable")
        self.assertIn("budget", result["warnings"][0]["message"])
        self.assertEqual({str(path): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}, before)

    @unittest.skipUnless(HAS_PIL and HAS_CAIRO, "CairoSVG and Pillow are package dependencies")
    def test_generated_outputs_and_public_image_metadata(self):
        self.write("assets/chart.vl.json", "{}")
        self.write(".vegavisuals.yml", "version: 1\nvisualizations:\n  - source: assets/chart.vl.json\n    output: assets/chart.png\n")
        self.write("assets/chart.png", self.raster())
        self.write("assets/plot.py", '# ---\n# unaltraweb_compute:\n#   mode: figure\n#   outputs: [assets/plot.png]\n# ---\nraise RuntimeError("Never execute inspected source")\n')
        self.write("assets/plot.png", self.raster(colour=(50, 60, 70, 0)))
        self.write("assets/page.capture.yml", "version: 1\npath: /\n")
        self.write("assets/page.capture.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#354267"/></svg>')
        self.write("_data/team.yml", "- name: Example\n  image: assets/chart.png\n")
        self.write("_chapters/en/images.md", '![Chart](assets/chart.vl.json "Chart")\n![Plot](assets/plot.py "Plot")\n![Capture](assets/page.capture.yml "Capture")\n')
        result = images.image_background_check(self.project)
        self.assertTrue(result["ok"], result)
        indexed = {item["path"]: item for item in result["images"]}
        self.assertEqual(indexed["assets/chart.png"]["state"], "opaque")
        self.assertEqual(indexed["assets/plot.png"]["owner"], "assets/plot.py")
        self.assertEqual(indexed["assets/plot.png"]["state"], "transparent")
        self.assertEqual(indexed["assets/page.capture.svg"]["state"], "opaque")

    @unittest.skipUnless(HAS_PIL and HAS_CAIRO, "CairoSVG and Pillow are package dependencies")
    def test_svg_unsupported_features_and_entities_are_unverifiable(self):
        for data in ('<!DOCTYPE svg [<!ENTITY secret SYSTEM "file:///etc/passwd">]><svg>&secret;</svg>',
                     '<svg width="10" height="10"><mask id="m"/></svg>'):
            self.write("assets/unverified.svg", data)
            report = images.image_background_check(self.project, "assets/unverified.svg")
            self.assertTrue(report["ok"])
            self.assertEqual(report["images"][0]["state"], "unverifiable")

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_normal_checks_warn_without_rejecting_a_transparent_image(self):
        from unaltraweb_mcp import site_tools
        self.write("assets/transparent.png", self.raster(colour=(20, 30, 40, 0)))
        self.write("_pages/en/home.md", '![A](assets/transparent.png "Caption")\n')
        self.write("_site/index.html", '<html lang="en"><title>Example</title><img alt="A" src="/site/assets/transparent.png"></html>')
        self.write("_site/assets/transparent.png", (self.project / "assets/transparent.png").read_bytes())
        result = site_tools.html_audit(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["warnings"][0]["code"], "UW-IMAGE-TRANSPARENT")
        self.assertEqual(result["finding_count"], 0)

    @unittest.skipUnless(HAS_PIL, "Pillow is a package dependency")
    def test_large_dimensions_are_rejected_before_pixel_loading(self):
        from PIL import Image
        with patch.object(Image, "open") as opened:
            opened.return_value.__enter__.return_value.size = (100_000, 100_000)
            opened.return_value.__enter__.return_value.format = "PNG"
            with self.assertRaisesRegex(ValueError, "megapixel"):
                inspect_raster(b"input")


if __name__ == "__main__":
    unittest.main()
