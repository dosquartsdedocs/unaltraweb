from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from unaltraweb_mcp import manual_context as context

FACTORY = Path(__file__).resolve().parents[1]


def write(root, path, data):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data, bytes) else data.encode())


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(root, paths, message="Fixture revision"):
    git(root, "add", "--", *paths)
    git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", message)


def fixture(root):
    config = {"theme": "unaltraweb", "title": "Manual de prova", "default_lang": "ca", "languages": ["ca", "en"],
              "exclude": ["tmp/"], "unaltraweb": {"site_profile": "unaltremanual", "manual": {"id": "fixture-manual-121", "collection": "chapters"}}}
    write(root, "_config.yml", yaml.safe_dump(config, allow_unicode=True))
    write(root, ".gitignore", "/tmp/\n")
    write(root, "_chapters/ca/first.md", '---\ntitle: Primer\nref: first\nlang: ca\nweight: 10\n---\nIntroducció exacta.\n\n## Mètode {#method}\n\nUn bloc de text.\n\n![Alt](assets/img/map.png "Mapa de prova"){: data-caption-source="Autoria sintètica"}\n\n### Detall {#detail}\n\nDescendent exacte.\n')
    image = io.BytesIO()
    Image.new("RGB", (12, 8), "navy").save(image, format="PNG")
    write(root, "assets/img/map.png", image.getvalue())
    git(root, "init", "-b", "fixture")
    commit(root, ["_config.yml", ".gitignore", "_chapters/ca/first.md", "assets/img/map.png"])


def unpack(result, root):
    package = root / result["path"]
    assert hashlib.sha256(package.read_bytes()).hexdigest() == result["sha256"]
    with tarfile.open(package) as archive:
        files = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
    manifest = json.loads(files.pop("manual-context.json"))
    return manifest, files


class ManualContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)

    def export(self, name="first", **kwargs):
        return context.export(self.root, FACTORY, name, **kwargs)

    def test_actual_one_chapter_static_export_and_exact_closure(self):
        result = self.export()
        manifest, files = unpack(result, self.root)
        self.assertEqual(manifest["manual"]["id"], "fixture-manual-121")
        self.assertFalse(manifest["manual"]["dirty"])
        self.assertEqual([s["id"] for s in manifest["chapters"][0]["sections"]], ["first#intro", "first#method", "first#detail"])
        self.assertEqual(set(manifest["files"]), set(files))
        for name, data in files.items():
            self.assertEqual(manifest["files"][name], {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
        self.assertEqual(manifest["figures"][0]["credits"], "Autoria sintètica")
        texts = [files[s["path"]].decode() for s in manifest["chapters"][0]["sections"]]
        self.assertEqual(texts[0], "Introducció exacta.\n\n")
        self.assertNotIn("Descendent exacte", texts[1])
        self.assertEqual(texts[2].count("Descendent exacte"), 1)
        self.assertIn("(/figures/", texts[1])
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.export()

    def test_rejects_absent_external_and_symlink_figures(self):
        original = (self.root / "_chapters/ca/first.md").read_text()
        for value in ("https://example.org/p.png", "../secret.png", "assets/img/missing.png", "assets/img/map.png?x=1"):
            with self.subTest(value=value):
                write(self.root, "_chapters/ca/first.md", original.replace("assets/img/map.png", value))
                with self.assertRaises((ValueError, RuntimeError)):
                    self.export()
        write(self.root, "_chapters/ca/first.md", original)
        (self.root / "assets/img/map.png").rename(self.root / "assets/img/real.png")
        (self.root / "assets/img/map.png").symlink_to("real.png")
        with self.assertRaisesRegex(ValueError, "Unsafe|unreadable"):
            self.export()

    def test_selection_and_dirty_revision(self):
        result = self.export(sections=["first#detail"])
        manifest, files = unpack(result, self.root)
        self.assertEqual(manifest["figures"], [])
        self.assertEqual(len(files), 1)
        write(self.root, "_chapters/ca/second.md", "---\ntitle: Segon\nref: second\nlang: ca\nweight: 1\npdf: false\n---\nUn altre text.\n")
        result2 = self.export("second", chapters=["first", "second"])
        next_manifest, _ = unpack(result2, self.root)
        self.assertEqual([c["ref"] for c in next_manifest["chapters"]], ["second", "first"])
        self.assertEqual(next_manifest["manual"]["id"], manifest["manual"]["id"])
        self.assertTrue(next_manifest["manual"]["dirty"])
        self.assertNotEqual(next_manifest["manual"]["source_sha256"], manifest["manual"]["source_sha256"])

    def test_receiver_incompatible_capture_svg_is_not_silently_replaced(self):
        text = (self.root / "_chapters/ca/first.md").read_text().replace("map.png", "capture.svg")
        write(self.root, "_chapters/ca/first.md", text)
        write(self.root, "assets/img/capture.svg", '<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AAAA"/></svg>')
        with self.assertRaisesRegex(ValueError, "Itemarium v1 cannot receive"):
            self.export()

    def test_new_source_during_export_refuses_seal(self):
        original = context.unchanged
        def concurrent(project, cache, walks):
            write(project, "_chapters/ca/added.md", "---\ntitle: Added\nref: added\nlang: ca\n---\nText.\n")
            return original(project, cache, walks)
        with patch.object(context, "unchanged", side_effect=concurrent):
            with self.assertRaisesRegex(ValueError, "inventory changed"):
                self.export()


if __name__ == "__main__":
    unittest.main()
