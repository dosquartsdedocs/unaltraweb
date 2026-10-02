"""Security/transaction fixtures; published producer acceptance is a separate gate."""
from __future__ import annotations

from contextlib import closing
import hashlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from unaltraweb_mcp import artifact_handoff_v1 as wire
from unaltraweb_mcp import artifact_imports as imports
from unaltraweb_mcp import letter_bundle as letter


def fixture(root):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf = io.BytesIO()
    writer.write(pdf)
    template = b"Unit-test template; not a published producer proof.\n"
    template_hash = imports.digest(template)
    source = b"---\ntitle: Test letter\nlang: english\ndraft: false\ndate: '2026-10-01'\nrecipient:\n  name: Reader\nsignature: false\n---\n\nA retained test letter.\n"
    producer = imports.json_bytes({"identity": "unaltracarta-code-inventory-v1", "version": "0.3.0rc1", "files": {"assets/templates/default-letter.latex": template_hash}})
    payload = {
        "payload/source/original.letter.md": source, "payload/render/letter.md": source,
        "payload/render/template.latex": template,
        "payload/render/metadata-0.yml": b"author:\n  name: Sender\n",
        "payload/render/metadata-1.yml": b"strings: {}\n",
        "payload/render/metadata-paths.yml": b"paths: {sources: /work, data: /work, templates: /work, logos: '', signatures: '', selfies: ''}\n",
        "payload/evidence/producer.json": producer,
        "payload/evidence/runtime.json": imports.json_bytes({"revision": letter.RENDERER, "os": "linux", "architecture": "amd64"}),
        "payload/evidence/pandoc.json": b'{"pandoc-api-version":[1],"meta":{},"blocks":[]}',
        "payload/output/letter.pdf": pdf.getvalue(),
        "payload/request.json": imports.json_bytes({"profile": letter.PROFILE, "source": "drafts/test.letter.md", "template": "default-letter.latex",
            "arguments": letter.PDF_ARGS, "validation_arguments": letter.AST_ARGS, "render_root": "payload/render", "container_root": "/work",
            "draft": False, "attachments": "text-labels-only", "author_origin": "project", "recipient_key": None, "language": "english",
            "environment": {"HOME": "/tmp", "TEXMFCACHE": "/tmp/texmf-cache"}}),
    }
    files = []
    for index, (path, data) in enumerate(payload.items()):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        kind = "output" if path == letter.PDF_PATH else "evidence" if "/evidence/" in path else "input"
        role = "request" if path.endswith("request.json") else "letter-pdf" if kind == "output" else "render-input"
        files.append({"id": "request" if role == "request" else f"f{index}", "path": path, "kind": kind, "role": role,
                      "ownership": "author" if "/source/" in path else "producer", "sha256": imports.digest(data), "bytes": len(data)})
    manifest = {"schema_version": 1, "kind": "mcp-artifact-bundle", "request": "request", "files": files, "dependencies": [],
                "producer": {"name": "unaltracarta", "version": "0.3.0rc1", "revision": "sha256:" + imports.digest(producer), "runtimes": [{"name": "pandoc-latex", "revision": letter.RENDERER}]}}
    data = imports.json_bytes(manifest)
    (root / "bundle.json").write_bytes(data)
    return imports.digest(data), template_hash


class ArtifactImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "receiver"
        self.project.mkdir()
        (self.project / "_config.yml").write_text("theme: unaltraweb\nlang: en\nunaltraweb:\n  site_profile: unaltremanual\n")
        (self.project / ".gitignore").write_text("tmp/\n_site/\n# author rule\nprivate-notes/\n")
        subprocess.run(["git", "init", "--quiet", str(self.project)], check=True)
        self.source = self.project / "incoming/letter"
        self.sha, template_hash = fixture(self.source)
        patcher = patch.dict(letter.TEMPLATES, {"default-letter.latex": template_hash})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, **kwargs):
        return imports.import_bundle(self.project, "incoming/letter/bundle.json", self.sha, "letter", "_chapters/en/letter.md", **kwargs)

    def apply(self):
        result = self.call(dry_run=False, confirm_import=True)
        self.assertTrue(result["ok"], result)
        return result

    def reseal(self):
        path = self.source / "bundle.json"
        manifest = json.loads(path.read_text())
        for item in manifest["files"]:
            data = (self.source / item["path"]).read_bytes()
            item.update(sha256=imports.digest(data), bytes=len(data))
        path.write_bytes(imports.json_bytes(manifest))
        self.sha = imports.digest(path.read_bytes())

    def test_pinned_reference_verifier_and_schema_bytes(self):
        base = Path(wire.__file__).parent
        self.assertEqual(imports.digest(Path(wire.__file__).read_bytes()), "48368035f242f4d4446cbbe1363f8a01a7c17fa164ffef21abadd878b288d82d")
        self.assertEqual(imports.digest((base / "artifact-handoff-v1.schema.json").read_bytes()), "b52a32b3bcfeed28cf34a9ec1557665a94466b51c451ccad47d2e87f6e23f9aa")

    def test_plan_does_not_write_and_confirmation_is_required(self):
        result = self.call()
        self.assertTrue(result["ok"], result)
        self.assertFalse((self.project / ".unaltraweb").exists())
        self.assertFalse(self.call(dry_run=False)["ok"])
        self.assertFalse((self.project / ".unaltraweb").exists())

    def test_native_integration_survives_retirement_and_relocation(self):
        result = self.apply()
        wire.check(str(self.project), "integration", result["integration"], result["integration_sha256"])
        shutil.rmtree(self.project / "incoming")
        shutil.rmtree(self.project / "tmp")
        moved = self.project.with_name("moved receiver")
        self.project.rename(moved)
        checked = imports.check_imports(moved)
        self.assertTrue(checked["ok"], checked)
        self.assertTrue((moved / ".unaltraweb/artifacts/letter/bundle/payload/source/original.letter.md").is_file())

    def test_author_prose_is_preserved_on_identical_reimport(self):
        self.apply()
        content = self.project / "_chapters/en/letter.md"
        content.write_text(content.read_text() + "\nAuthor explanation.\n")
        before = content.read_bytes()
        repeated = self.call(dry_run=False, confirm_import=True)
        self.assertTrue(repeated["ok"], repeated)
        self.assertTrue(repeated["reused"])
        self.assertEqual(content.read_bytes(), before)

    def test_modified_public_pdf_is_never_overwritten(self):
        self.apply()
        target = self.project / "assets/documents/letter.pdf"
        target.write_bytes(b"author replacement")
        self.assertFalse(imports.check_imports(self.project)["ok"])
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        self.assertEqual(target.read_bytes(), b"author replacement")

    def test_missing_reference_blocks_check(self):
        self.apply()
        (self.project / "_chapters/en/letter.md").write_text("Author removed the inclusion.\n")
        self.assertEqual(imports.check_imports(self.project)["error"]["code"], "reference")

    def test_conflicting_content_preflights_before_any_publication(self):
        target = self.project / "_chapters/en/letter.md"
        target.parent.mkdir(parents=True)
        target.write_text("Author content\n")
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        self.assertFalse((self.project / ".unaltraweb/artifacts").exists())
        self.assertEqual(target.read_text(), "Author content\n")

    def test_tampered_and_incomplete_bundles_fail_before_writes(self):
        target = self.source / "payload/render/metadata-0.yml"
        target.write_bytes(target.read_bytes() + b"# changed\n")
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        target.unlink()
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        self.assertFalse((self.project / ".unaltraweb").exists())

    def test_resealed_incomplete_resource_is_a_domain_failure(self):
        (self.source / "payload/render/metadata-0.yml").write_text("author:\n  name: Sender\n  images:\n    signature: missing.png\n")
        (self.source / "payload/render/metadata-paths.yml").write_text("paths: {sources: /work, data: /work, templates: /work, logos: '', signatures: /work/resources/signatures, selfies: ''}\n")
        self.reseal()
        wire.check(str(self.project), "bundle", "incoming/letter/bundle.json", self.sha)
        self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1")

    def test_stale_ast_cannot_hide_new_local_reference(self):
        path = self.source / "payload/render/letter.md"
        path.write_text(path.read_text() + "\n[Local](missing.csv)\n")
        self.reseal()
        self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1")

    def test_stale_ast_cannot_hide_metadata_references_or_render_overrides(self):
        target = self.source / "payload/render/metadata-0.yml"
        for extra in ("  affiliation: '[Local](missing.csv)'\n", "  name: '![](missing.png)'\n",
                      "header-includes: ignored\n"):
            target.write_text("author:\n  familyname: Sender\n" + extra)
            self.reseal()
            wire.check(str(self.project), "bundle", "incoming/letter/bundle.json", self.sha)
            self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1")

    def test_malformed_pandoc_link_is_a_structured_domain_failure(self):
        target = self.source / "payload/evidence/pandoc.json"
        target.write_bytes(imports.json_bytes({"pandoc-api-version": [1], "meta": {}, "blocks": [{"t": "Link", "c": []}]}))
        self.reseal()
        self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1")

    def test_symlink_and_hardlink_inputs_are_rejected(self):
        target = self.source / "payload/render/letter.md"
        outside = self.project / "outside"
        target.rename(outside)
        target.symlink_to(outside)
        self.assertFalse(self.call()["ok"])
        target.unlink()
        os.link(outside, target)
        self.assertFalse(self.call()["ok"])

    def test_failure_retains_recovery_and_does_not_claim_completion(self):
        create = imports._create
        def interrupted(workspace, path, data):
            if path == "assets/documents/letter.pdf":
                raise OSError("injected publication failure")
            return create(workspace, path, data)
        with patch.object(imports, "_create", side_effect=interrupted):
            result = self.call(dry_run=False, confirm_import=True)
        self.assertFalse(result["ok"])
        self.assertTrue((self.project / result["recovery"]).is_file())
        self.assertFalse((self.project / ".unaltraweb/artifacts/letter/binding.json").exists())
        self.assertFalse(imports.check_imports(self.project)["ok"])
        self.apply()  # Explicit retry can adopt unchanged partial bytes.

    def test_ignored_retention_is_not_durable_import(self):
        (self.project / ".gitignore").write_text("tmp/\n.unaltraweb/\n")
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        self.assertFalse((self.project / ".unaltraweb").exists())

    def test_pdf_actions_are_rejected_after_valid_reseal(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_js("app.alert('unexpected');")
        with (self.source / letter.PDF_PATH).open("wb") as stream:
            writer.write(stream)
        self.reseal()
        wire.check(str(self.project), "bundle", "incoming/letter/bundle.json", self.sha)
        self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1")

    def test_reader_coexists_with_parent_pdf_controller_project_lock(self):
        self.apply()
        fd = os.open(self.project, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(imports.check_imports(self.project)["ok"])
        finally:
            os.close(fd)

    def test_destination_symlink_preserves_external_content(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "sentinel").write_text("preserve")
        (self.project / "assets").symlink_to(outside)
        self.assertFalse(self.call(dry_run=False, confirm_import=True)["ok"])
        self.assertEqual(list(outside.iterdir()), [outside / "sentinel"])

    def test_hidden_reference_is_not_native_integration(self):
        self.apply()
        target = self.project / "_chapters/en/letter.md"
        for body in ("```liquid\n{% retained_document letter %}\n```\n", "{% comment %}{% retained_document letter %}{% endcomment %}"):
            target.write_text(body)
            self.assertFalse(imports.check_imports(self.project)["ok"])

    def test_executable_source_owns_its_markdown_destination(self):
        source = self.project / "_chapters/en/letter.qmd"
        source.parent.mkdir(parents=True)
        source.write_text("Author executable source\n")
        result = self.call(dry_run=False, confirm_import=True)
        self.assertFalse(result["ok"])
        self.assertEqual(source.read_text(), "Author executable source\n")
        self.assertFalse(source.with_suffix(".md").exists())

    def test_render_check_is_bound_to_the_native_page_and_pdf(self):
        self.apply()
        config = self.project / "_config.yml"
        config.write_text(config.read_text() + "baseurl: /base\n")
        output = self.project / "_site"
        page = output / "en/retained/letter/index.html"
        page.parent.mkdir(parents=True)
        page.write_text('<object data-retained-document="letter" data="/base/assets/documents/letter.pdf"></object>')
        pdf = output / "assets/documents/letter.pdf"
        pdf.parent.mkdir(parents=True)
        shutil.copyfile(self.project / "assets/documents/letter.pdf", pdf)
        vendor = output / "assets/vendor.html"
        vendor.write_bytes(b"x" * (2 * 1024 * 1024))
        checked = imports.check_imports(self.project, output_folder="_site")
        self.assertTrue(checked["ok"], checked)
        for url in ("/wrong.pdf", "/assets/documents/letter.pdf", "https://elsewhere.test/base/assets/documents/letter.pdf"):
            page.write_text(f'<object data-retained-document="letter" data="{url}"></object>')
            self.assertFalse(imports.check_imports(self.project, output_folder="_site")["ok"])

    def test_front_matter_delimiters_are_complete_lines(self):
        result = self.call(title="Letter --- original", dry_run=False, confirm_import=True)
        self.assertTrue(result["ok"], result)
        content = self.project / "_chapters/en/letter.md"
        content.write_bytes(content.read_bytes().replace(b"\n", b"\r\n"))
        self.assertTrue(imports.check_imports(self.project)["ok"])

    def test_pdf_action_aliases_and_chains_cannot_hide_external_actions(self):
        from pypdf import PdfWriter
        from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
        for mode in ("alias", "chain"):
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            launch = writer._add_object(DictionaryObject({NameObject("/S"): NameObject("/Launch"), NameObject("/F"): TextStringObject("outside")}))
            if mode == "alias":
                writer.root_object.update({NameObject("/OpenAction"): launch, NameObject("/Alias"): launch})
            else:
                writer.root_object[NameObject("/OpenAction")] = DictionaryObject({NameObject("/S"): NameObject("/URI"),
                    NameObject("/URI"): TextStringObject("https://example.org"), NameObject("/Next"): ArrayObject([launch])})
            with (self.source / letter.PDF_PATH).open("wb") as stream:
                writer.write(stream)
            self.reseal()
            self.assertEqual(self.call()["error"]["code"], "letter-pdf-v1", mode)

    def test_pdf_internal_open_destination_is_supported(self):
        from pypdf import PdfWriter
        from pypdf.generic import ArrayObject, NameObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        writer.root_object[NameObject("/OpenAction")] = ArrayObject([page.indirect_reference, NameObject("/Fit")])
        with (self.source / letter.PDF_PATH).open("wb") as stream:
            writer.write(stream)
        self.reseal()
        self.assertTrue(self.call()["ok"])

    def test_manual_pdf_inclusion_and_dependency_inventory_are_verified(self):
        self.apply()
        path = Path(__file__).resolve().parents[1] / "scripts/manual/build_pdf.py"
        spec = importlib.util.spec_from_file_location("retained_manual_pdf", path)
        pdf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdf)
        source = self.project / "_chapters/en/letter.md"
        text = "{% retained_document letter %}"
        rendered = pdf.transform_markdown(self.project, text, source)
        self.assertIn(r"\includepdf[pages=-,pagecommand={}]{assets/documents/letter.pdf}", rendered)
        checked = imports.check_imports(self.project)["imports"][0]
        deps = dict(pdf.build_dependencies(self.project, {}, [source], rendered, pdf.DEFAULT_TEMPLATE, None))
        self.assertTrue({"retained:" + name for name in checked["inputs"]} <= deps.keys())
        self.assertIn("import-check:pdf_probe.py", deps)
        self.assertIn("import-check:distribution.py", deps)
        self.assertNotIn("import-check:component-contract.json", deps)  # No worker self-digest cycle.
        code = "```liquid\n" + text + "\n```"
        self.assertNotIn(r"\includepdf", pdf.transform_markdown(self.project, code, source))
        (self.project / checked["pdf"]).write_bytes(b"changed by author")
        with self.assertRaisesRegex(pdf.ManualPdfError, "Retained document verification failed"):
            pdf.transform_markdown(self.project, text, source)
