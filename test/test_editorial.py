from __future__ import annotations

import json
import io
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import cli, editorial as ed, site_tools
from unaltraweb_mcp import editorial_sources as sources


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.configure()

    def write(self, path, text):
        target = self.project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def configure(self, profile="unaltremanual", extra=""):
        self.write("_config.yml", f"title: A publication\ndefault_lang: en\nlanguages: [en, ca, es]\nunaltraweb:\n  site_profile: {profile}\n" + extra)

    def policy(self, **values):
        self.write(ed.POLICY, json.dumps({"schema_version": 1, **values}))

    def prepare(self, *, target="", kind="line"):
        self.write("_pages/en/about.md", "---\ntitle: About\n---\nThe method describes the observation.\n")
        packet = ed.editorial_review_prepare(self.project, target, kind)
        anchor = next(unit for unit in packet["fragments"] if unit["text"].startswith("The method"))
        report = {"id": "review-1", "target": target, "kind": kind, "source_digest": packet["source_digest"],
                  "reviewer": "An editor", "reviewer_kind": "human", "findings": [
                      {"id": "clarity", "anchor": anchor["id"], "quote": "The method", "severity": "major",
                       "reason": "The method has no concrete referent.", "suggestion": "Name the verified method."}]}
        return packet, report

    def test_profile_and_language_voices_are_contextual(self):
        examples = {"ca": "Jo investigo cartografia.", "es": "Yo investigo cartografía.", "en": "I study cartography."}
        for lang, text in examples.items():
            self.write(f"_pages/{lang}/about.md", text + "\n")
        for profile in ed.PROFILES:
            with self.subTest(profile=profile):
                self.configure(profile)
                result = ed.prose_check(self.project)
                self.assertTrue(result["ok"], result)
                voices = [item for item in result["findings"] if item["rule"] == "personal_voice"]
                self.assertEqual(len(voices), 0 if profile == "unaltreselfie" else 3)
        self.configure()
        self.write("_pages/ca/about.md", "En aquest manual s'explica el mètode i la pràctica. Selecciona la capa.\n")
        self.write("_pages/es/about.md", "Todo el conjunto se puede analizar. Selecciona la capa.\n")
        self.write("_pages/en/about.md", "This manual describes the method. Select the layer.\n")
        self.assertEqual(ed.prose_check(self.project)["findings"], [])

    def test_personal_achievement_and_technical_reference_are_not_chat(self):
        self.configure("unaltreselfie")
        self.write("_pages/ca/about.md", "He publicat una eina i he afegit un conjunt de dades al repositori.\n")
        self.assertEqual(ed.prose_check(self.project)["findings"], [])
        self.configure("unaltredocs")
        self.write("_documentation/en/api.md", "The content_status field records editorial status.\nSet `content_status` to `approved`.\n")
        result = ed.prose_check(self.project)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["warnings"])

    def test_common_leaks_are_errors_in_all_profiles(self):
        for profile in ed.PROFILES:
            self.configure(profile)
            for lang, text in {"en": "As requested, I have added this paragraph.", "ca": "Tal com m'has demanat, he afegit això.", "es": "Como me has pedido, he añadido esto."}.items():
                self.write(f"_pages/{lang}/about.md", text)
            with self.subTest(profile=profile):
                result = ed.prose_check(self.project)
                self.assertFalse(result["ok"])
                self.assertEqual({item["path"] for item in result["findings"] if item["severity"] == "error"}, {f"_pages/{lang}/about.md" for lang in ("en", "ca", "es")})

    def test_comments_code_math_links_quotes_and_examples_are_not_instructions(self):
        self.write("_pages/en/about.md", """---
title: About
content_status: needs_review
---
<!-- As requested, TODO. -->
{% comment %}As requested.{% endcomment %}
```text
TODO As requested.
```
~~~python
TODO
~~~
    TODO indented code
`TODO` and $TODO$ and $$TODO$$.
[A link](https://example.invalid/TODO)
"As requested" and “As requested” and «As requested» are quoted.
> As requested, TODO.
<pre>As requested, TODO.</pre>
<script>TODO</script>
<style>TODO</style>
<blockquote>As requested, TODO.</blockquote>
<q>As requested</q>
Text <!-- ![TODO](path) --> remains.
""")
        self.write("_pages/en/example.md", "---\neditorial:\n  genre: example\n---\nAs requested, TODO.\n")
        result = ed.prose_check(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["findings"], [])
        packet = ed.editorial_review_prepare(self.project)
        self.assertTrue(any(unit["genre"] == "quote" for unit in packet["fragments"]))

    def test_public_metadata_and_image_captions_have_anchors(self):
        self.write("_data/team.yml", "- bio_ca: 'Tal com m’has demanat, aquesta és la biografia.'\n  content_status: TODO\n")
        self.write("_pages/en/about.md", '---\ntitle: "As requested, Title"\n---\n![TODO](image.svg "As requested, Caption")\n<img alt="As requested, Image" src="image.svg">\n')
        result = ed.prose_check(self.project)
        self.assertFalse(result["ok"])
        fields = {item["field"] for item in result["findings"]}
        self.assertTrue({"/0/bio_ca", "/title", "alt", "caption", "img.alt"} <= fields, fields)
        self.assertFalse(any(item["field"].endswith("content_status") for item in result["findings"]))

    def test_root_jekyll_pages_and_raw_html(self):
        self.write("index.html", "---\ntitle: Root\n---\n<p>As requested, Root.</p><code>TODO</code>\n")
        self.write("README.md", "TODO repository instructions\n")
        self.write("notes.md", "TODO no front matter\n")
        result = ed.prose_check(self.project)
        self.assertFalse(result["ok"])
        self.assertEqual({item["rule"] for item in result["findings"]}, {"author_instruction_reference"})
        self.assertEqual({item["path"] for item in result["findings"]}, {"index.html"})

    def test_profile_unpublished_excluded_sources_are_skipped(self):
        self.configure(extra="exclude: [_pages/en/private.md]\n")
        self.write("_pages/en/private.md", "TODO\n")
        self.write("_pages/en/draft.md", "---\npublished: false\n---\nTODO\n")
        self.write("_pages/en/selfie.md", "---\nprofiles: [unaltreselfie]\n---\nTODO\n")
        result = ed.prose_check(self.project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["coverage"]["skipped"]), 3)

    def test_genre_voice_and_local_terminology(self):
        self.policy(terms={"clearly": "Explain the evidence."}, genres={"procedure": {"voice": "personal"}})
        self.write("_pages/en/about.md", "---\neditorial:\n  genre: procedure\n---\nI clearly select the layer.\n")
        self.write("_pages/en/preface.md", "---\neditorial:\n  genre: preface\n---\nI thank the team.\n")
        result = ed.prose_check(self.project)
        self.assertTrue(result["ok"])
        self.assertEqual({item["rule"] for item in result["findings"]}, {"terminology"})

    def test_read_only_checks_create_no_context_or_state(self):
        self.write("_pages/en/about.md", "Readable prose.\n")
        before = sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*"))
        ed.prose_check(self.project)
        ed.editorial_review_prepare(self.project)
        ed.editorial_status(self.project)
        ed.editorial_publication_check(self.project)
        self.assertEqual(sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*")), before)

    def test_record_exact_anchors_cas_and_dispositions(self):
        packet, report = self.prepare()
        created = ed.editorial_review_record(self.project, report, packet["revision"])
        self.assertEqual(created["revision"], 1)
        self.assertFalse(created["approves_content"])
        with self.assertRaisesRegex(ValueError, "state changed"):
            ed.editorial_review_resolve(self.project, "review-1", "clarity", "accepted", "Agreed", 0)
        ed.editorial_review_resolve(self.project, "review-1", "clarity", "accepted", "Agreed", 1)
        ed.editorial_review_resolve(self.project, "review-1", "clarity", "rejected", "The referent is defined in the previous section.", 2)
        state = ed.editorial_status(self.project)
        finding = state["reviews"]["review-1"]["findings"][0]
        self.assertEqual([item["status"] for item in finding["history"]], ["pending", "accepted"])
        self.assertEqual(finding["status"], "rejected")
        self.assertEqual(state["revision"], 3)
        self.assertFalse(state["reviews"]["review-1"]["stale"])

    def test_quote_mismatch_duplicate_or_stale_report_never_writes(self):
        packet, report = self.prepare()
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            ed.editorial_review_record(self.project, {**report, "kind": "evidence"}, 0)
        report["findings"][0]["quote"] = "A fabricated quote"
        with self.assertRaisesRegex(ValueError, "quote/anchor"):
            ed.editorial_review_record(self.project, report, 0)
        self.assertFalse((self.project / ed.STATE).exists())
        report["findings"][0]["quote"] = "The method"
        report["findings"].append(dict(report["findings"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            ed.editorial_review_record(self.project, report, 0)
        report["findings"] = []
        self.write("_pages/en/about.md", "Changed source.\n")
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            ed.editorial_review_record(self.project, report, 0)
        self.assertFalse((self.project / ed.STATE).exists())

    def test_source_change_in_record_recheck_is_refused(self):
        _, report = self.prepare()
        original = ed._packet
        def mutate(*args):
            packet = original(*args)
            self.write("_pages/en/about.md", "Concurrent edit.\n")
            return packet
        with patch.object(ed, "_packet", side_effect=mutate), self.assertRaisesRegex(ValueError, "changed before"):
            ed.editorial_review_record(self.project, report, 0)
        self.assertFalse((self.project / ed.STATE).exists())

    def test_source_mutations_wait_until_review_state_is_published(self):
        cases = [("update", "_pages/en/about.md"), ("create", "_pages/en/new.md"),
                 ("delete", "_pages/en/about.md"), ("update", "_config.yml"),
                 ("update", ed.WRITING_PROFILE)]
        original_write = ed._write_state
        original_flock = ed.fcntl.flock
        root = self.project.stat()
        for operation, path in cases:
            with self.subTest(operation=operation, path=path):
                self.configure()
                self.write(ed.WRITING_PROFILE, "Use concrete subjects.\n")
                (self.project / ed.STATE).unlink(missing_ok=True)
                (self.project / "_pages/en/new.md").unlink(missing_ok=True)
                packet, report = self.prepare()
                current = site_tools.site_source_read(self.project, path) if operation != "create" else None
                root_attempted = threading.Event()
                mutation_finished = threading.Event()
                futures = []

                def observed_flock(fd, mode):
                    info = os.fstat(fd)
                    if (threading.current_thread().name.startswith("editorial-source") and mode == ed.fcntl.LOCK_EX
                            and (info.st_dev, info.st_ino) == (root.st_dev, root.st_ino)):
                        root_attempted.set()
                    return original_flock(fd, mode)

                def mutate_source():
                    if operation == "delete":
                        result = site_tools.site_source_delete(self.project, path, expected_sha256=current["sha256"],
                                                               dry_run=False, confirm_delete=True)
                    else:
                        content = current["content"] + "\n# A later edit\n" if current else "A newly created page.\n"
                        result = site_tools.site_source_write(self.project, path, content,
                                                              expected_sha256=current["sha256"] if current else "",
                                                              create_only=operation == "create", dry_run=False)
                    mutation_finished.set()
                    return result

                def publish_after_writer_attempt(reader, state, previous):
                    # This callback is exactly after record's final _packet
                    # recheck, the window identified in the review.
                    futures.append(executor.submit(mutate_source))
                    self.assertTrue(root_attempted.wait(5), "Source mutation did not join the project-root lock protocol.")
                    self.assertFalse(mutation_finished.is_set(), "Source changed between the recheck and state publication.")
                    with ed.Reader(self.project) as snapshot:
                        self.assertEqual(ed._packet(snapshot, "", "line")["source_digest"], packet["source_digest"])
                    original_write(reader, state, previous)

                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="editorial-source") as executor:
                    with patch.object(ed.fcntl, "flock", side_effect=observed_flock), patch.object(ed, "_write_state", side_effect=publish_after_writer_attempt):
                        recorded = ed.editorial_review_record(self.project, report, 0)
                        self.assertTrue(futures[0].result(timeout=5)["ok"])
                self.assertTrue(recorded["ok"])
                saved = json.loads((self.project / ed.STATE).read_text(encoding="utf-8"))
                self.assertEqual(saved["reviews"]["review-1"]["source_digest"], packet["source_digest"])
                # A later, serialized source mutation makes the valid record
                # stale; it did not alter the snapshot at publication time.
                self.assertTrue(ed.editorial_status(self.project)["reviews"]["review-1"]["stale"])

    def test_internal_source_writes_reuse_and_retain_the_verified_root_lock(self):
        self.prepare()
        with ed.Reader(self.project) as locked:
            ed.fcntl.flock(locked.fd, ed.fcntl.LOCK_EX)
            for path in ("_config.yml", "_pages/en/about.md"):
                source = site_tools.site_source_read(self.project, path)
                site_tools.site_source_write(self.project, path, source["content"] + "\n# Updated\n",
                                             expected_sha256=source["sha256"], dry_run=False, _locked_root_fd=locked.fd)
                with ed.Reader(self.project) as competing:
                    with self.assertRaises(BlockingIOError):
                        ed.fcntl.flock(competing.fd, ed.fcntl.LOCK_EX | ed.fcntl.LOCK_NB)
            source = site_tools.site_source_read(self.project, "_pages/en/about.md")
            site_tools.site_source_delete(self.project, source["path"], expected_sha256=source["sha256"],
                                          dry_run=False, confirm_delete=True, _locked_root_fd=locked.fd)
            with ed.Reader(self.project) as competing:
                with self.assertRaises(BlockingIOError):
                    ed.fcntl.flock(competing.fd, ed.fcntl.LOCK_EX | ed.fcntl.LOCK_NB)

        source = site_tools.site_source_read(self.project, "_config.yml")
        with tempfile.TemporaryDirectory() as outside, ed.Reader(Path(outside)) as wrong:
            with self.assertRaisesRegex(ValueError, "does not match"):
                site_tools.site_source_write(self.project, "_config.yml", source["content"],
                                             expected_sha256=source["sha256"], dry_run=False, _locked_root_fd=wrong.fd)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_simultaneous_records_do_not_clobber(self):
        _, report = self.prepare()
        def record(index):
            try:
                ed.editorial_review_record(self.project, {**report, "id": f"review-{index}"}, 0)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(record, [1, 2]))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(ed.editorial_status(self.project)["revision"], 1)

    def test_source_policy_config_and_writing_changes_make_reviews_stale(self):
        for changed, content in (("_pages/en/about.md", "Changed prose.\n"), (ed.WRITING_PROFILE, "Prefer concrete subjects.\n"),
                                 (ed.POLICY, '{"sentence_words":30}'), ("_config.yml", "unaltraweb:\n  site_profile: unaltremanual\nlanguages: [en]\n")):
            with self.subTest(changed=changed):
                self.configure()
                self.policy()
                self.write(ed.WRITING_PROFILE, "Initial preference.\n")
                state = self.project / ed.STATE
                state.unlink(missing_ok=True)
                _, report = self.prepare(target="_pages/en/about.md")
                ed.editorial_review_record(self.project, report, 0)
                self.write(changed, content)
                self.assertTrue(ed.editorial_status(self.project)["reviews"]["review-1"]["stale"])

    def test_generated_markdown_points_to_executable_owner(self):
        self.write("_chapters/en/example.md", "Generated prose.\n")
        self.write("_chapters/en/example.py", "# trusted execution is a separate workflow\n")
        self.write(".unaltraweb/computations.lock.json", json.dumps({"version": 1, "records": {
            "_chapters/en/example.py": {"output": {"path": "_chapters/en/example.md", "sha256": "a" * 64}}}}))
        packet = ed.editorial_review_prepare(self.project, "_chapters/en/example.md")
        self.assertEqual(packet["sources"][0]["editable_source"], "_chapters/en/example.py")
        self.assertIn("_chapters/en/example.py", packet["source_hashes"])
        self.write("_chapters/en/example.py", "# new executable source\n")
        self.assertNotEqual(ed.editorial_review_prepare(self.project, "_chapters/en/example.md")["source_digest"], packet["source_digest"])

    def test_opt_in_publication_requires_fresh_passes_and_explicit_dispositions(self):
        self.policy(require_reviews=True, required_kinds=["line"], human_review=True)
        _, report = self.prepare()
        self.assertFalse(ed.editorial_publication_check(self.project)["ok"])
        self.assertTrue(ed.prose_check(self.project)["ok"])
        ed.editorial_review_record(self.project, report, 0)
        self.assertFalse(ed.editorial_publication_check(self.project)["ok"])
        ed.editorial_review_record(self.project, {**report, "id": "review-2", "findings": []}, 1)
        # Superseding a report must not silently resolve its major findings.
        result = ed.editorial_publication_check(self.project)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing_reviews"], [])
        ed.editorial_review_resolve(self.project, "review-1", "clarity", "resolved", "Verified the section-level definition.", 2)
        self.assertTrue(ed.editorial_publication_check(self.project)["ok"])
        self.write("_pages/en/new.md", "A new page.\n")
        self.assertFalse(ed.editorial_publication_check(self.project)["ok"])

    def test_rendered_check_catches_template_leaks_and_private_context(self):
        self.write("_site/index.html", '<html lang="en"><body><p>As requested, from a template.</p><pre>TODO</pre></body></html>')
        result = ed.editorial_publication_check(self.project, "_site")
        self.assertFalse(result["ok"])
        self.assertEqual({item["rule"] for item in result["rendered_findings"]}, {"author_instruction_reference"})
        self.write("_site/index.html", "<p>Publishable.</p>")
        self.write("_site/context/editorial-policy.json", "{}")
        self.write("_site/.unaltraweb/scaffold.json", "{}")
        result = ed.editorial_publication_check(self.project, "_site")
        self.assertEqual(len([item for item in result["issues"] if item["rule"] == "internal_editorial_output"]), 2)

    def test_target_output_and_symlink_confinement(self):
        self.write("private.md", "Not a Jekyll page.\n")
        for target in ("../other.md", "/etc/passwd", "context/private.md", "_pages/../private.md", "_pages/*.md"):
            with self.subTest(target=target):
                self.assertFalse(ed.prose_check(self.project, target)["ok"])
        self.assertFalse(ed.editorial_publication_check(self.project, "../outside")["ok"])
        self.assertFalse(ed.editorial_publication_check(self.project, "_config.yml")["ok"])
        self.write("_pages/en/about.md", "Valid.\n")
        (self.project / "_pages/en/link.md").symlink_to(self.project / "private.md")
        self.assertFalse(ed.prose_check(self.project)["ok"])

    def test_state_context_symlink_is_not_followed(self):
        _, report = self.prepare()
        with tempfile.TemporaryDirectory() as external:
            (self.project / "context").symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                ed.editorial_review_record(self.project, report, 0)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_special_large_and_invalid_inputs_fail_closed(self):
        source = self.write("_pages/en/about.md", "Normal.\n")
        for content in (b"\xff", b"NUL\x00", b"x" * (sources.MAX_BYTES + 1)):
            source.write_bytes(content)
            self.assertFalse(ed.prose_check(self.project)["ok"])
        source.unlink()
        os.mkfifo(source)
        self.assertFalse(ed.prose_check(self.project)["ok"])

    def test_invalid_policy_yaml_and_state_are_not_silently_reset(self):
        for policy in ('', '{"schema_version":2}', '{"terms":[]}', '{"genres":{"novel":{}}}', '{"required_kinds":[{}]}', '{"sentence_words":true}', '{"require_reviews":false,"require_reviews":true}'):
            with self.subTest(policy=policy):
                self.write(ed.POLICY, policy)
                self.assertFalse(ed.prose_check(self.project)["ok"])
        self.policy()
        self.write("_data/bad.yml", "title: one\ntitle: two\n")
        self.assertFalse(ed.prose_check(self.project)["ok"])
        self.write(ed.STATE, '{"schema_version":1,"revision":3,"reviews":{"bad":{}}}')
        before = (self.project / ed.STATE).read_bytes()
        with self.assertRaises(ValueError):
            ed.editorial_status(self.project)
        self.assertFalse(ed.editorial_publication_check(self.project)["ok"])
        self.assertEqual((self.project / ed.STATE).read_bytes(), before)

    def test_cli_records_and_checks_use_the_same_engine_and_exit_status(self):
        packet, report = self.prepare()
        base = ["--project", str(self.project), "mcp"]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(base + ["editorial-review-prepare"]), 0)
        self.assertEqual(json.loads(output.getvalue()), json.loads(sources.canonical(packet)))
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(base + ["editorial-review-record", "--report-json", json.dumps(report), "--expected-revision", "0"]), 0)
        self.assertEqual(json.loads(output.getvalue())["revision"], 1)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(base + ["editorial-review-resolve", "--review-id", "review-1", "--finding-id", "clarity", "--status", "rejected", "--reason", "The method is defined.", "--expected-revision", "1"]), 0)
        self.write("_pages/en/about.md", "As requested, TODO.\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(base + ["prose-check"]), 1)
            self.assertEqual(cli.main(base + ["editorial-publication-check"]), 1)

    def test_generated_profiles_have_healthy_editorial_defaults(self):
        for profile in ed.PROFILES:
            with self.subTest(profile=profile):
                project = self.project / profile
                self.assertTrue(site_tools.new_web(project, site_profile_value=profile)["ok"])
                self.assertTrue(ed.prose_check(project)["ok"])
                self.assertFalse(ed.editorial_policy(project)["require_reviews"])
                self.assertFalse((project / ed.STATE).exists())

    def test_nested_language_precedence_matches_site_contract(self):
        self.configure(extra="  default_lang: ca\n")
        self.write("_pages/about.md", "El mètode i la pràctica formen un conjunt.\n")
        self.assertEqual(ed.prose_check(self.project)["findings"], [])
        self.assertEqual(ed.editorial_policy(self.project)["default_language"], site_tools.default_language(site_tools.site_config(self.project)))

    def test_manual_draft_language_remains_diagnostic(self):
        self.write("_chapters/en/about.md", "In this draft the chapter is still incomplete.\n")
        result = site_tools.manual_editorial_quality_check(self.project)
        self.assertFalse(result["ok"])
        self.assertIn("draft_process_language", {item["rule"] for item in result["findings"]})

    def test_site_check_runs_source_gate_without_requiring_review_records(self):
        project = self.project / "site"
        site_tools.new_web(project, site_profile_value="unaltreselfie")
        factory = Path(__file__).resolve().parents[1]
        result = site_tools.site_check(project, factory)
        self.assertTrue(result["ok"], result)
        (project / "_pages/en/index.md").write_text("As requested, I have added the page.\n", encoding="utf-8")
        result = site_tools.site_check(project, factory)
        self.assertFalse(result["ok"])
        self.assertFalse(result["prose"]["ok"])


if __name__ == "__main__":
    unittest.main()
