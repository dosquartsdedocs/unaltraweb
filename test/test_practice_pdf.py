from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

from unaltraweb_mcp import cli, practice_pdf, site_tools

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "practiques/demo/ca/alumnat/LLEGIU-ME.md"
IMAGE_ID = "sha256:" + "a" * 64
IMAGE = "example/pdf@sha256:" + "b" * 64
CONFIG = {
    "title": "Test course", "lang": "ca", "languages": ["ca", "es", "en"],
    "exclude": ["practiques/", "sandbox/", "dist/"],
    "unaltraweb": {"site_profile": "unaltremanual", "manual": {
        "metadata": {"subject": "Test subject", "short_title": "TEST", "series": "Dos quarts de docs",
                     "academic_year": "2026/2027", "instructors": [{"name": "Test author"}],
                     "teaching_guides": [{"degree": "First degree", "subject_code": "12345"},
                                         {"degree": "Second degree", "subject_code": "67890"}]},
        "pdf": {"mark_drafts": True},
    }},
}


class PracticePdfFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet", str(self.project)], check=True)
        (self.project / ".gitignore").write_text("sandbox/\n")
        self.config = copy.deepcopy(CONFIG)
        self.write_config()
        self.source = self.project / SOURCE
        self.source.parent.mkdir(parents=True)
        self.source.write_text("---\ntitle: Test activity\nlang: ca\ncontent_status: draft\n---\n# Begin\n\nFirst step.\n")
        self.image = patch.object(practice_pdf, "inspect_image", return_value={"state": "matched", "observed_image_id": IMAGE_ID})
        self.image.start()
        self.addCleanup(self.image.stop)

    def write_config(self):
        (self.project / "_config.yml").write_text(yaml.safe_dump(self.config))

    def plan(self, **changes):
        arguments = {"source": SOURCE, "version": "v1", "image_id": IMAGE_ID}
        arguments.update(changes)
        return practice_pdf.prepare(self.project, ROOT, **arguments)

    def build(self, **changes):
        arguments = {"source": SOURCE, "version": "v1", "image": IMAGE}
        arguments.update(changes)
        return practice_pdf.build(self.project, ROOT, **arguments)

    def fake_render(self, command, **kwargs):
        # The unit test only exercises controller ownership, reuse and receipts;
        # the real Docker test below verifies the actual PDF bytes and layout.
        job = self.project / self.plan()["job"]
        (job / "outputs/LLEGIU-ME.pdf").write_bytes(b"%PDF-1.7\nunit-test-output")
        (job / "outputs/preview.png").write_bytes(b"unit-test-preview")
        (job / "outputs/render-report.json").write_text('{"pages": 1, "publishes": false}')
        return SimpleNamespace(returncode=0, timed_out=False, stdout="", stderr="")


class PracticePdfTests(PracticePdfFixture):
    def test_metadata_and_layout_use_course_codes_and_practice_version(self):
        plan = self.plan()
        metadata = plan["metadata"]
        self.assertEqual("12345, 67890", metadata["subject-codes"])
        self.assertEqual("dosquartsdedocs", metadata["series"])
        self.assertEqual("v1", metadata["practice-version"])
        self.assertEqual("Test activity", metadata["title"])
        self.assertTrue(metadata["draft"])
        template = plan["files"]["practice.tex"].decode()
        self.assertNotIn("$academic-year$", template)
        self.assertNotIn(r"\frontmatter", template)
        self.assertNotIn(r"\begin{titlepage}", template)
        self.assertIn("($subject-codes$)", template)
        self.assertIn("width=58mm,height=26mm", template)

    def test_language_and_audience_names_are_explicit(self):
        for language, basename in practice_pdf.BASENAMES.items():
            for audience in ("alumnat", "docent"):
                with self.subTest(language=language, audience=audience):
                    source = f"practiques/demo/{language}/{audience}/{basename}.md"
                    self.assertEqual(("demo", language, audience, basename), practice_pdf.validate_request(source, "2026-10-r2"))
        with self.assertRaises(ValueError):
            practice_pdf.validate_request("practiques/demo/es/alumnat/README.md", "v1")

    def test_rejects_unsafe_selectors_before_dispatch(self):
        for value in ("../escape", "x/../../escape", "$(shell touch marker)", "x\nnew", ""):
            with self.subTest(version=value), self.assertRaises(ValueError):
                practice_pdf.validate_request(SOURCE, value)
        with patch.object(site_tools, "run_factory_make") as dispatch:
            with self.assertRaises(ValueError):
                site_tools.manual_practice_pdf_build(self.project, ROOT, "../../secret.md", "v1")
            dispatch.assert_not_called()

    def test_requires_private_jekyll_exclusions(self):
        self.config["exclude"].remove("practiques/")
        self.write_config()
        with self.assertRaisesRegex(ValueError, "Add practiques/"):
            self.plan()
        result = site_tools.profile_check(self.project)
        self.assertFalse(result["ok"])
        self.assertTrue(any(issue.get("code") == "private-practice-exclusion" for issue in result["issues"]))

    def test_jekyll_include_cannot_override_private_exclusions(self):
        for pattern in ("practiques/demo", "**/*.md", "**/*.pdf"):
            self.config["include"] = [pattern]
            self.write_config()
            with self.subTest(pattern=pattern), self.assertRaisesRegex(ValueError, "must not expose"):
                self.plan()

    def test_only_declared_images_are_snapshotted(self):
        (self.project / "assets").mkdir()
        (self.project / "assets/figure.png").write_bytes(b"selected-image")
        (self.project / "assets/private.png").write_bytes(b"unselected-image")
        self.source.write_text(self.source.read_text() + "\n![Caption](assets/figure.png)\n")
        plan = self.plan()
        self.assertIn("assets/figure.png", plan["original_inputs"])
        self.assertNotIn("assets/private.png", plan["original_inputs"])
        self.assertNotIn(b"unselected-image", plan["files"].values())
        self.assertEqual(1, len(plan["metadata"]["practice-assets"]))

    def test_reference_images_and_source_relative_images_are_captured(self):
        (self.source.parent / "figure.png").write_bytes(b"image")
        self.source.write_text(self.source.read_text() + "\n![Caption][picture]\n\n[picture]: figure.png\n")
        plan = self.plan()
        self.assertIn("figure.png", plan["metadata"]["practice-assets"])
        self.assertIn("practiques/demo/ca/alumnat/figure.png", plan["original_inputs"])

    def test_remote_traversing_and_symlinked_images_fail(self):
        original = self.source.read_text()
        for raw in ("https://example.org/image.png", "../../outside.png", "/etc/secret.png", "assets/source.qmd"):
            with self.subTest(image=raw):
                self.source.write_text(original + f"\n![Caption]({raw})\n")
                with self.assertRaises(ValueError):
                    self.plan()
        (self.source.parent / "link.png").symlink_to(self.source)
        self.source.write_text(original + "\n![Caption](link.png)\n")
        with self.assertRaises(ValueError):
            self.plan()

    def test_unresolved_liquid_is_not_rendered_as_reader_text(self):
        original = self.source.read_text()
        self.source.write_text(original + "\n{% include arbitrary.html %}\n")
        with self.assertRaisesRegex(ValueError, "unresolved Liquid"):
            self.plan()
        self.source.write_text(original + "\n`{% include example.html %}`\n")
        self.assertIn(b"`{% include example.html %}`", self.plan()["files"]["source.md"])

    def test_dry_run_does_not_create_jobs(self):
        with patch.object(practice_pdf, "run_process") as renderer:
            result = self.build(dry_run=True)
        self.assertEqual("planned", result["state"])
        self.assertFalse(result["publishes"])
        self.assertFalse((self.project / "sandbox").exists())
        renderer.assert_not_called()

    def test_missing_image_never_pulls(self):
        with patch.object(practice_pdf, "inspect_image", return_value={"state": "missing"}), patch.object(practice_pdf, "run_process") as renderer:
            with self.assertRaisesRegex(ValueError, "Prepare"):
                self.build()
            renderer.assert_not_called()

    def test_job_requires_ignore_and_refuses_symlinked_ancestors(self):
        (self.project / ".gitignore").write_text("")
        with self.assertRaisesRegex(RuntimeError, "ignored"):
            self.build()
        (self.project / ".gitignore").write_text("sandbox/\n")
        target = self.project / "not-sandbox"
        target.mkdir()
        (self.project / "sandbox").symlink_to(target, target_is_directory=True)
        with self.assertRaises((OSError, ValueError, RuntimeError)):
            self.build()
        self.assertEqual([], list(target.iterdir()))

    def test_sealed_job_is_reused_and_modified_output_is_preserved(self):
        with patch.object(practice_pdf, "run_process", side_effect=self.fake_render) as renderer:
            result = self.build()
            reused = self.build()
            self.assertEqual("built", result["state"])
            self.assertEqual("current", reused["state"])
            self.assertEqual(1, renderer.call_count)
            pdf = self.project / result["pdf"]
            pdf.write_bytes(b"author-edited")
            with self.assertRaisesRegex(ValueError, "modified"):
                self.build()
            self.assertEqual(b"author-edited", pdf.read_bytes())

    def test_invalid_receipt_cannot_bypass_verification(self):
        with patch.object(practice_pdf, "run_process", side_effect=self.fake_render):
            result = self.build()
        path = self.project / result["receipt"]
        receipt = json.loads(path.read_text())
        for case in ("missing-artifact", "boolean-schema"):
            changed = copy.deepcopy(receipt)
            if case == "missing-artifact":
                changed["artifacts"].pop("outputs/LLEGIU-ME.pdf")
            else:
                changed["schema_version"] = True
            path.write_text(json.dumps(changed))
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, "inventory"):
                self.build()

    def test_unrecorded_files_change_the_retained_job(self):
        with patch.object(practice_pdf, "run_process", side_effect=self.fake_render):
            result = self.build()
        (self.project / result["job"] / "outputs/.unexpected").write_text("Retain this edit")
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.build()

    def test_ignore_change_during_render_cannot_seal_job(self):
        def mutate(command, **kwargs):
            result = self.fake_render(command, **kwargs)
            (self.project / ".gitignore").write_text("")
            return result
        job = self.project / self.plan()["job"]
        with patch.object(practice_pdf, "run_process", side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, "ignored"):
                self.build()
        self.assertFalse((job / "receipt.json").exists())

    def test_source_drift_during_render_cannot_seal_job(self):
        def mutate(command, **kwargs):
            result = self.fake_render(command, **kwargs)
            self.source.write_text(self.source.read_text() + "\nChanged\n")
            return result
        job = self.project / self.plan()["job"]
        with patch.object(practice_pdf, "run_process", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.build()
        self.assertFalse((job / "receipt.json").exists())
        self.assertTrue((job / "outputs/LLEGIU-ME.pdf").exists())

    def test_dependency_change_gets_another_retained_job(self):
        first = self.plan()
        self.source.write_text(self.source.read_text() + "\nMore explanation\n")
        second = self.plan()
        self.assertNotEqual(first["job"], second["job"])
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_unsealed_job_is_a_collision_even_in_dry_run(self):
        job = self.project / self.plan()["job"]
        job.mkdir(parents=True)
        (job / "keep.txt").write_text("Retain failed build evidence")
        with self.assertRaisesRegex(ValueError, "unsealed"):
            self.build(dry_run=True)
        self.assertEqual("Retain failed build evidence", (job / "keep.txt").read_text())

    def test_factory_make_does_not_expand_untrusted_selectors(self):
        marker = self.project / "executed"
        environment = os.environ.copy()
        environment["MCP_CONSUMER_WORKSPACE"] = str(self.project)
        completed = subprocess.run(["make", "--silent", "--no-print-directory", "-C", str(ROOT),
                                    "manual-practice-pdf-build", f"PRACTICE_SOURCE=$(shell touch {marker})",
                                    "PRACTICE_VERSION=v1"], env=environment, text=True, capture_output=True)
        self.assertNotEqual(0, completed.returncode)
        self.assertFalse(marker.exists())
        self.assertFalse(json.loads(completed.stdout)["ok"])

    def test_worker_only_mounts_snapshot_and_outputs(self):
        command = practice_pdf.docker_command("/tmp/site, with spaces", self.plan(), "c" * 16, "d" * 16)
        mounts = [command[index+1] for index, value in enumerate(command) if value == "--mount"]
        self.assertEqual(2, len(mounts))
        self.assertTrue(mounts[0].endswith(",readonly"))
        self.assertIn('"target=/source"', mounts[0])
        self.assertIn('"target=/out"', mounts[1])
        self.assertIn("--read-only", command)
        self.assertIn("none", command)
        self.assertEqual(IMAGE_ID, command[-2])
        self.assertNotIn(str(ROOT), " ".join(mounts))

    def test_mcp_and_cli_dispatch_factory_target(self):
        with patch.object(site_tools, "run_factory_make", return_value={"ok": True}) as dispatch:
            site_tools.manual_practice_pdf_build(self.project, ROOT, SOURCE, "v1", run="review-2", dry_run=True)
        dispatch.assert_called_once_with(ROOT, self.project, "manual-practice-pdf-build", env={
            "PRACTICE_SOURCE": SOURCE, "PRACTICE_VERSION": "v1", "PRACTICE_RUN": "review-2", "PRACTICE_DRY_RUN": "1"})
        self.assertIn("manual-practice-pdf-build", cli.FACTORY_REQUIRED_MCP_COMMANDS)
        self.assertIn("manual_practice_pdf_build", site_tools.list_tools()["tools"])


@unittest.skipUnless(os.environ.get("UNALTRAWEB_PRACTICE_TEST_IMAGE") and shutil.which("docker"), "Explicitly prepared PDF Docker image required")
class PracticePdfIntegrationTests(PracticePdfFixture):
    def test_real_worker_renders_and_reuses_private_handout(self):
        self.image.stop()
        from PIL import Image
        from pypdf import PdfReader
        asset = self.source.parent / "figure.png"
        Image.new("RGB", (640, 400), "#eeeeee").save(asset)
        self.source.write_text(self.source.read_text() + '\n![Accessible image description](figure.png "A bounded figure.")\n\n| Field | Value |\n| --- | --- |\n| A | B |\n\nTable: A compact table.\n')
        image = os.environ["UNALTRAWEB_PRACTICE_TEST_IMAGE"]
        result = self.build(image=image)
        pdf = self.project / result["pdf"]
        reader = PdfReader(pdf)
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        self.assertIn("12345, 67890", text)
        self.assertIn("A bounded figure.", text)
        self.assertNotIn("2026/2027", text)
        self.assertTrue(all(float(page.mediabox.width) > float(page.mediabox.height) for page in reader.pages))
        before = pdf.read_bytes()
        self.assertEqual("current", self.build(image=image)["state"])
        self.assertEqual(before, pdf.read_bytes())
