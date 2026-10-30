from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from unaltraweb_mcp import manual_context as context
from unaltraweb_mcp import manual_context_sources as sources
from unaltraweb_mcp import site_tools, cli

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


SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="white"/><text x="10" y="40">Fixture</text></svg>'


def companion_receipt(root, owner):
    inputs = site_tools._companion_input_paths(root, owner)
    metadata = site_tools.component(owner)
    files = lambda paths: [{"path": path.relative_to(root).as_posix(), "sha256": context.digest(path.read_bytes())} for path in paths]
    receipt = {"schema_version": 1, "provider": owner, "provider_version": metadata["version"], "release": metadata["release"],
               "request_sha256": site_tools._companion_request_sha256(root, owner, inputs), "ok": True,
               "inputs": files(site_tools._companion_expected_inputs(root, owner, inputs)),
               "artifacts": files(site_tools._companion_expected_outputs(root, owner, inputs))}
    write(root, f".unaltraweb/receipts/{owner}.json", json.dumps(receipt))


def computation_fixture(root, *, chapter=False):
    native = sources.module(FACTORY, "scripts/computations/render.py")
    config = {"version": 1, "source_roots": ["_chapters", "assets/compute"]}
    write(root, ".unaltraweb/computations.yml", yaml.safe_dump(config))
    source = "_chapters/ca/first.qmd" if chapter else "assets/compute/figure.qmd"
    metadata = {"engine": "python"} if chapter else {"engine": "python", "mode": "figure", "outputs": ["assets/img/figure.svg"]}
    write(root, source, "---\n" + yaml.safe_dump({"title": "Fixture", "ref": "first" if chapter else "figure", "lang": "ca", "unaltraweb_compute": metadata}) + "---\nFixture executable source; no execution claimed.\n")
    if not chapter:
        write(root, "assets/img/figure.svg", SVG)
    config, path = native.load_config(root)
    record, = native.discover_sources(root, config)
    fingerprint, deps, image = native.fingerprint(root, config, path, record)
    saved = {"fingerprint": fingerprint, "dependencies": deps, "image": image, "image_identity": native.inspect_image(image["image"])}
    if chapter:
        saved.update(output={"path": record["output_path"], **native.file_signature(record["output"])}, assets=[])
    else:
        saved["outputs"] = [{"path": path, **native.file_signature(root / path)} for path in record["output_paths"]]
    write(root, ".unaltraweb/computations.lock.json", json.dumps({"version": 1, "records": {source: saved}}))
    return source


class ManualContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)

    def export(self, name="first", **kwargs):
        return context.export(self.root, FACTORY, name, **kwargs)

    def reference(self, source):
        path = self.root / "_chapters/ca/first.md"
        write(self.root, "_chapters/ca/first.md", path.read_text().replace("assets/img/map.png", source))

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
        with self.assertRaisesRegex(ValueError, "Unsafe|unreadable|Symlink"):
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

    def test_language_variants_and_default_fallback(self):
        write(self.root, "_chapters/en/first.md", '---\ntitle: First\nref: first\nlang: en\n---\nText.\n\n![Alt](assets/img/map.png "Caption")\n')
        original = (self.root / "assets/img/map.png").read_bytes()
        write(self.root, "assets/img/map.en.png", original)
        manifest, _ = unpack(self.export(language="en"), self.root)
        self.assertEqual(manifest["figures"][0]["language"], "en")
        self.assertEqual(manifest["figures"][0]["source"]["path"], "assets/img/map.en.png")
        (self.root / "assets/img/map.en.png").unlink()
        fallback, _ = unpack(self.export("fallback", language="en"), self.root)
        self.assertEqual(fallback["figures"][0]["language"], "ca")
        with self.assertRaisesRegex(ValueError, "configured"):
            self.export("bad", language="fr")

    def test_components_includes_citations_and_literal_code(self):
        write(self.root, "_bibliography/manual.bib", '@book{fixture, title={A verified title}, author={Writer, A}, year={2026}, url={https://example.org/reference}}')
        write(self.root, "_data/i18n/ca.yml", 'callouts:\n  warning: AVÍS\n')
        write(self.root, "_includes/context.md", 'Definició\n: Explicació exacta.\n\n>>>> Una advertència.\n\n{% cite fixture %}\n\n::: table "Taula"\n| A | B |\n| --- | --- |\n| 1 | 2 |\n:::\n\n::: subfigures a "Grup"\n![El `codi`](assets/img/map.png "Peu `literal`")\n:::\n\n::: listing "Exemple"\n```python\nprint("{% include absent.md %}")\n```\n:::\n')
        write(self.root, "_chapters/ca/first.md", '---\ntitle: Primer\nref: first\nlang: ca\n---\n{% include context.md %}\n')
        manifest, files = unpack(self.export(), self.root)
        text = "".join(files[part["path"]].decode() for part in manifest["chapters"][0]["sections"])
        self.assertIn("Definició\n: Explicació exacta.", text)
        self.assertIn("**AVÍS**", text)
        self.assertIn("A verified title", text)
        self.assertIn('print("{% include absent.md %}")', text)
        self.assertNotIn("::: table", text)
        self.assertEqual(manifest["figures"][0]["caption"], "Peu `literal`")

    def test_edited_diagram_receipt_and_source_staleness(self):
        write(self.root, "assets/diagrams/a.mmd", "flowchart LR\n A-->B\n")
        write(self.root, "assets/diagrams/a.mmd.svg", SVG)
        write(self.root, "assets/diagrams/a.mmd.edited.svg", SVG.replace("Fixture", "Edited"))
        companion_receipt(self.root, "diavisuals")
        self.reference("assets/diagrams/a.mmd")
        manifest, files = unpack(self.export(), self.root)
        figure = manifest["figures"][0]
        self.assertEqual(figure["resolution"]["kind"], "diagram")
        self.assertTrue(figure["resolution"]["edited"])
        self.assertIn(b"Edited", files[figure["path"]])
        receipt = json.loads((self.root / "tmp/manual-context/first/receipt.json").read_text())
        evidence = receipt["resolution_evidence"][figure["resolution"]["receipt_sha256"]]
        self.assertEqual(evidence["effective_sha256"], context.digest(files[figure["path"]]))
        write(self.root, "assets/diagrams/a.mmd.edited.svg", SVG.replace("Fixture", "Changed"))
        with self.assertRaisesRegex(ValueError, "Diagram receipt"):
            self.export("changed")

    def test_computation_outputs_edits_and_stale_sources(self):
        source = computation_fixture(self.root)
        write(self.root, "assets/img/figure.edited.svg", SVG.replace("Fixture", "Edited"))
        self.reference(source)
        manifest, files = unpack(self.export(), self.root)
        self.assertTrue(manifest["figures"][0]["resolution"]["edited"])
        self.assertEqual(manifest["figures"][0]["resolution"]["kind"], "computation")
        self.assertFalse(any(path.endswith(".qmd") for path in files))
        write(self.root, source, (self.root / source).read_text() + "Changed source\n")
        with self.assertRaisesRegex(ValueError, "source_or_environment_changed"):
            self.export("stale")

    def test_computation_modified_unmanaged_and_old_edited_refusals(self):
        source = computation_fixture(self.root)
        self.reference(source)
        write(self.root, "assets/img/figure.edited.svg", SVG)
        base_time = (self.root / "assets/img/figure.svg").stat().st_mtime_ns
        os.utime(self.root / "assets/img/figure.edited.svg", ns=(base_time-100000, base_time-100000))
        with self.assertRaisesRegex(ValueError, "predates"):
            self.export()
        (self.root / "assets/img/figure.edited.svg").unlink()
        write(self.root, "assets/img/figure.svg", SVG.replace("Fixture", "Modified"))
        with self.assertRaisesRegex(ValueError, "output_modified"):
            self.export()
        (self.root / ".unaltraweb/computations.lock.json").unlink()
        with self.assertRaisesRegex(ValueError, "present_unmanaged"):
            self.export()

    def test_generated_chapter_is_checked_and_exports_only_effective_markdown(self):
        source = computation_fixture(self.root, chapter=True)
        manifest, files = unpack(self.export(), self.root)
        self.assertTrue(any(b"Descendent exacte" in data for data in files.values()))
        write(self.root, source, (self.root / source).read_text() + "Changed\n")
        with self.assertRaisesRegex(ValueError, "source_or_environment_changed"):
            self.export("stale")

    def test_vega_uses_exact_manifest_output_and_checks_local_data(self):
        write(self.root, "assets/charts/bars.vl.json", json.dumps({"data": {"url": "assets/charts/data.csv"}, "mark": "bar"}))
        write(self.root, "assets/charts/data.csv", "x,y\n1,2\n")
        write(self.root, "assets/charts/bars.edited.svg", SVG)
        write(self.root, ".vegavisuals.yml", yaml.safe_dump({"version": 1, "profile": "default", "family": "default", "visualizations": [
            {"name": "bars", "source": "assets/charts/bars.vl.json", "output": "assets/charts/bars.edited.svg"}]}))
        companion_receipt(self.root, "vegavisuals")
        self.reference("assets/charts/bars.vl.json")
        manifest, _ = unpack(self.export(), self.root)
        self.assertEqual(manifest["figures"][0]["resolution"]["kind"], "vega")
        self.assertTrue(manifest["figures"][0]["resolution"]["edited"])
        write(self.root, "assets/charts/data.csv", "x,y\n1,3\n")
        with self.assertRaisesRegex(ValueError, "Vega receipt"):
            self.export("changed")

    def test_missing_capture_receipt_and_qgis_provenance_fail_explicitly(self):
        write(self.root, "assets/captures/site.capture.yml", "version: 1\npath: /ca/\n")
        self.reference("assets/captures/site.capture.yml")
        with self.assertRaisesRegex(ValueError, "Web captures are not current"):
            self.export()
        (self.root / "assets/captures/site.capture.yml").unlink()
        write(self.root, "assets/img/qgis.svg", SVG.replace("<rect", '<metadata>unaltracaptura-qgis</metadata><rect'))
        path = self.root / "_chapters/ca/first.md"
        write(self.root, "_chapters/ca/first.md", path.read_text().replace("assets/captures/site.capture.yml", "assets/img/qgis.svg"))
        with self.assertRaisesRegex(ValueError, "QGIS capture handoff is not supported"):
            self.export()

    def test_html_image_and_active_html_refusal(self):
        write(self.root, "_chapters/ca/first.md", '---\ntitle: Primer\nref: first\nlang: ca\n---\nText\n<img src="assets/img/map.png" alt="Alt" title="Peu">\n')
        manifest, files = unpack(self.export(), self.root)
        self.assertEqual(manifest["figures"][0]["caption"], "Peu")
        self.assertIn(b'<img src="/figures/', next(data for path, data in files.items() if path.endswith(".md")))
        write(self.root, "_chapters/ca/first.md", (self.root / "_chapters/ca/first.md").read_text() + "<iframe src='https://example.org/'></iframe>")
        with self.assertRaisesRegex(ValueError, "Unsupported active"):
            self.export("active")

    def test_no_binding_override_private_paths_and_invalid_selection(self):
        write(self.root, "practiques/private.png", (self.root / "assets/img/map.png").read_bytes())
        self.reference("practiques/private.png")
        result = site_tools.manual_context_export(self.root, FACTORY, "private")
        self.assertFalse(result["ok"])
        self.assertIn("public manual", result["error"])
        with patch.object(context, "active_runtime") as active:
            active.return_value.project = Path("/another-workspace")
            with self.assertRaisesRegex(ValueError, "bound"):
                self.export()
        with self.assertRaisesRegex(ValueError, "bounded list"):
            self.export(chapters="first")
        args = cli.build_parser().parse_args(["--project", str(self.root), "mcp", "manual-context-export", "--name", "cli", "--chapter", "first"])
        self.assertEqual(args.chapter, ["first"])

    def test_schema_contract_and_exact_blocks_ignore_code_headings(self):
        schema = json.loads((FACTORY / "src/unaltraweb_mcp/manual-context-v1.schema.json").read_text())
        manifest, _ = unpack(self.export(), self.root)
        import jsonschema
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
        text = "Introduction.\n\n```md\n## Literal heading\n```\n\n## Heading {#stable}\nText.\n\n### Child {#child}\nChild.\n"
        parts = context.split_sections(text, "chapter", "Title")
        self.assertEqual([row[0]["id"] for row in parts], ["chapter#intro", "chapter#stable", "chapter#child"])
        self.assertEqual("".join(block for _, block in parts), text)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            context.split_sections("## A {#same}\nA.\n## B {#same}\nB.\n", "chapter", "Title")

    def test_complete_capture_check_and_current_edited_byte_evidence(self):
        native = sources.module(FACTORY, "scripts/web_captures/render.py")
        native.factory_root = lambda: FACTORY
        source = "assets/captures/site.capture.yml"
        write(self.root, source, "version: 1\npath: /ca/\n")
        record, = native.discover(self.root)
        write(self.root, "assets/captures/site.capture.png", (self.root / "assets/img/map.png").read_bytes())
        write(self.root, "assets/captures/site.capture.svg", SVG)
        fingerprint, dependencies, image = native.fingerprint(self.root, record)
        saved = {"fingerprint": fingerprint, "image_identity": {key: value for key, value in image.items() if key != "image"},
                 "dependencies": dependencies, "png": native.file_signature(record["png"]), "svg": native.file_signature(record["svg"])}
        write(self.root, ".unaltraweb/web-captures.lock.json", json.dumps({"version": 1, "records": {source: saved}}))
        self.reference(source)
        manifest, _ = unpack(self.export(), self.root)
        self.assertEqual(manifest["figures"][0]["resolution"]["kind"], "web-capture")
        # A native edited capture keeps the producer's PNG/fingerprint metadata.
        metadata = {"png_sha256": saved["png"]["sha256"], "fingerprint": fingerprint}
        import html
        edited = SVG.replace("<rect", '<metadata id="unaltraweb-capture">' + html.escape(json.dumps(metadata)) + '</metadata><rect')
        self.assertIsNotNone(native.SVG_METADATA_RE.search(edited))
        write(self.root, "assets/captures/site.capture.edited.svg", edited)
        newer, _ = unpack(self.export("edited"), self.root)
        self.assertTrue(newer["figures"][0]["resolution"]["edited"])
        write(self.root, source, "version: 1\npath: /changed/\n")
        with self.assertRaisesRegex(ValueError, "Web captures are not current"):
            self.export("stale")

    def test_translated_diagram_uses_complete_suffix_and_fallback(self):
        write(self.root, "_chapters/en/first.md", '---\ntitle: First\nref: first\nlang: en\n---\n![A](assets/diagrams/a.mmd "Caption")\n')
        for language in ("", ".en"):
            write(self.root, f"assets/diagrams/a{language}.mmd", "flowchart LR\n A-->B\n")
            write(self.root, f"assets/diagrams/a{language}.mmd.svg", SVG)
        companion_receipt(self.root, "diavisuals")
        manifest, _ = unpack(self.export(language="en"), self.root)
        self.assertEqual(manifest["figures"][0]["source"]["path"], "assets/diagrams/a.en.mmd")
        self.assertEqual(manifest["figures"][0]["language"], "en")

    def test_svg_external_style_data_and_entities_rejected(self):
        self.reference("assets/img/a.svg")
        for value in ('<svg xmlns="http://www.w3.org/2000/svg"><style>@import "https://bad/";</style></svg>',
                      '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://bad/)"/></svg>',
                      '<!DOCTYPE svg [<!ENTITY x "data">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
                      '<svg xmlns="http://www.w3.org/2000/svg"><use href="/etc/passwd"/></svg>'):
            write(self.root, "assets/img/a.svg", value)
            with self.assertRaises(ValueError):
                self.export()

    def test_literal_unclosed_and_indented_code_are_not_executed_or_resolved(self):
        body = 'Introduction.\n\n    {% include missing.md %}\n\n```md\n![Example](https://example.org/no.png)\n{% include absent.md %}\n'
        write(self.root, "_chapters/ca/first.md", '---\ntitle: First\nref: first\nlang: ca\n---\n' + body)
        manifest, files = unpack(self.export(), self.root)
        self.assertEqual(files[manifest["chapters"][0]["sections"][0]["path"]].decode(), body)
        self.assertEqual(manifest["figures"], [])

    def test_unexpected_retained_file_prevents_seal(self):
        original = context._write
        injected = False
        def write_extra(fd, path, content):
            nonlocal injected
            original(fd, path, content)
            if not injected:
                injected = True
                original(fd, "unexpected.txt", b"Concurrent unknown file")
        with patch.object(context, "_write", side_effect=write_extra):
            with self.assertRaisesRegex(ValueError, "unexpected files"):
                self.export()
        self.assertFalse((self.root / "tmp/manual-context/first/receipt.json").exists())
        self.assertTrue((self.root / "tmp/manual-context/first/unexpected.txt").is_file())


if __name__ == "__main__":
    unittest.main()
