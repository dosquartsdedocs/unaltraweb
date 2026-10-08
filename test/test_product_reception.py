from __future__ import annotations

import copy
import io
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from unaltraweb_mcp import artifact_handoff_v1 as handoff
from unaltraweb_mcp.job_storage import bundles, contract as c, reception, worker


def bundle_fixture(root, *, resource=True):
    source = b"# Original input\n"
    request = {"kind": "unaltraweb.job-request", "schema_version": 1,
               "inputs": [{"path": "project/demo.py", "sha256": c.sha256(source), "bytes": len(source)}]}
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="logo.svg"/></svg>'
    contents = {"payload/inputs/request.json": c.canonical(request), "payload/inputs/project/demo.py": source,
                "payload/results/project/figure.svg": svg, "payload/results/project/figure.edited.svg": svg.replace(b"<image", b'<image x="2"')}
    if resource:
        contents["payload/results/project/logo.svg"] = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    entries = []
    for index, (name, raw) in enumerate(contents.items()):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        entries.append({"id": f"file-{index}", "path": name, "kind": "input" if "/inputs/" in name else "output",
                        "role": "request" if index == 0 else "edited-visual" if ".edited." in name else "source" if index == 1 else "rendered-visual",
                        "ownership": "author" if index < 2 or ".edited." in name else "producer",
                        "sha256": c.sha256(raw), "bytes": len(raw)})
    entries[3]["variant_of"] = entries[2]["id"]
    manifest = {"schema_version": 1, "kind": "mcp-artifact-bundle",
                "producer": {"name": "unaltraweb", "version": "0.7.1", "revision": "sha256:" + "a"*64, "runtimes": []},
                "request": "file-0", "files": entries, "dependencies": []}
    encoded = c.canonical(manifest)
    (root / "bundle.json").write_bytes(encoded)
    return c.sha256(encoded), manifest


class RetainedBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_resource_closure_includes_authored_variant_original_and_local_dependencies(self):
        digest, manifest = bundle_fixture(self.root)
        domain = bundles.check(self.root, "bundle.json", digest)
        mappings = reception.selected_mappings({"assets": {"root": "assets/retained", "roles": ["edited-visual"]}}, manifest, domain)
        self.assertEqual({item["source"] for item in mappings}, {
            "payload/results/project/figure.svg", "payload/results/project/figure.edited.svg", "payload/results/project/logo.svg"})

    def test_missing_rendering_dependency_fails_even_when_common_tree_hashes_match(self):
        digest, _ = bundle_fixture(self.root, resource=False)
        handoff.check(str(self.root), "bundle", "bundle.json", digest)
        with self.assertRaisesRegex(ValueError, "Missing retained resource"):
            bundles.check(self.root, "bundle.json", digest)

    def test_partial_source_copy_and_unlisted_files_are_rejected(self):
        digest, _ = bundle_fixture(self.root)
        source = self.root / "payload/inputs/project/demo.py"
        original = source.read_bytes()
        source.write_bytes(original[:-2])
        with self.assertRaises((ValueError, handoff.HandoffError)):
            bundles.check(self.root, "bundle.json", digest)
        source.write_bytes(original)
        (self.root / "undeclared.txt").write_text("unresolved source")
        with self.assertRaises((ValueError, handoff.HandoffError)):
            bundles.check(self.root, "bundle.json", digest)

    def test_input_inventory_cannot_be_reduced_by_resealing_the_manifest(self):
        _, manifest = bundle_fixture(self.root)
        path = self.root / "payload/inputs/request.json"
        request = c.parse(path.read_bytes())
        request["inputs"] = []
        raw = c.canonical(request)
        path.write_bytes(raw)
        manifest["files"][0].update(sha256=c.sha256(raw), bytes=len(raw))
        raw_manifest = c.canonical(manifest)
        (self.root / "bundle.json").write_bytes(raw_manifest)
        with self.assertRaisesRegex(ValueError, "Unresolved native source"):
            bundles.check(self.root, "bundle.json", c.sha256(raw_manifest))


class ArchiveVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.digest, _ = bundle_fixture(self.source)

    def archive(self, format_name, extra=None):
        output = io.BytesIO()
        if format_name == "zip":
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(self.source.rglob("*")):
                    if path.is_file():
                        archive.writestr(path.relative_to(self.source).as_posix(), path.read_bytes())
                if extra:
                    extra(archive)
        else:
            with tarfile.open(fileobj=output, mode="w:gz") as archive:
                for path in sorted(self.source.rglob("*")):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(self.source).as_posix())
                if extra:
                    extra(archive)
        return output.getvalue()

    def verify(self, raw, format_name):
        work = self.root / ("work-" + str(len(list(self.root.glob("work-*")))))
        for directory in ("inputs", "exports", "results", "recovery", "scratch/work"):
            (work / directory).mkdir(parents=True, exist_ok=True)
        request = {"format": format_name, "archive_bytes": len(raw), "archive_sha256": c.sha256(raw), "bundle_sha256": self.digest,
                   "operation_id": "1"*32, "product_id": "2"*32, "markers": {"retained": {}, "scratch": {}},
                   "limits": {"max_retained_bytes": 64*1024**2, "max_scratch_bytes": 64*1024**2, "max_entries": 10000, "min_free_bytes": 0}}
        with patch.object(worker, "ROOT", work), patch.object(worker, "domain_check", bundles.check, create=True), \
                patch.object(worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw))):
            return worker.verify_archive(request), work

    def test_both_archives_retain_exact_archive_bytes_and_complete_verified_tree(self):
        for format_name in ("zip", "tar-gzip"):
            with self.subTest(format=format_name):
                raw = self.archive(format_name)
                report, work = self.verify(raw, format_name)
                self.assertEqual((work / "inputs/source.archive").read_bytes(), raw)
                self.assertEqual(report["archive_sha256"], c.sha256(raw))
                self.assertEqual(report["bundle_sha256"], self.digest)
                bundles.check(work, report["bundle_path"], self.digest)

    def test_archive_traversal_links_case_aliases_and_duplicate_directories_are_refused(self):
        def zip_link(archive):
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"/etc/passwd")
        def tar_link(archive):
            info = tarfile.TarInfo("link")
            info.type, info.linkname = tarfile.LNKTYPE, "bundle.json"
            archive.addfile(info)
        def tar_directories(archive):
            for _ in range(2):
                info = tarfile.TarInfo("duplicate")
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
        cases = [("zip", lambda archive: archive.writestr("../outside", b"bad")), ("zip", zip_link),
                 ("zip", lambda archive: archive.writestr("Bundle.json", b"alias")), ("tar-gzip", tar_link),
                 ("tar-gzip", tar_directories)]
        for format_name, mutation in cases:
            with self.subTest(format=format_name, mutation=mutation), self.assertRaises(ValueError):
                self.verify(self.archive(format_name, mutation), format_name)
        self.assertFalse((self.root / "outside").exists())

    def test_truncated_archive_never_yields_a_product(self):
        for format_name in ("zip", "tar-gzip"):
            with self.subTest(format=format_name), self.assertRaises((ValueError, EOFError, tarfile.TarError, zipfile.BadZipFile, handoff.HandoffError)):
                self.verify(self.archive(format_name)[:80], format_name)
        for work in self.root.glob("work-*"):
            self.assertTrue((work / "inputs/source.archive").exists())
            self.assertEqual(list((work / "exports").iterdir()), [])


class DurableReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = ("unaltraweb:\n  product_retention:\n    enabled: true\n    root: .unaltraweb/products\n"
                       "    format: directory\n    profiles: [unaltraweb-job-v1]\n    assets:\n"
                       "      root: assets/received\n      roles: [edited-visual]\n")
        (self.root / "_config.yml").write_text(self.config)

    def retained(self):
        source = self.root / "source"
        source.mkdir()
        digest, manifest = bundle_fixture(source)
        chosen, policy_sha = reception.policy(self.root)
        base = ".unaltraweb/products/" + digest + "/directory"
        final = self.root / base / "bundle"
        final.parent.mkdir(parents=True)
        shutil.move(source, final)
        domain = bundles.check(self.root, base + "/bundle/bundle.json", digest)
        mappings = reception.selected_mappings(chosen, manifest, domain)
        for mapping in mappings:
            target = self.root / mapping["destination"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(final / mapping["source"], target)
        binding = {"kind": "unaltraweb.retained-product", "schema_version": 1, "bundle_sha256": digest,
                   "format": "directory", "path": base + "/bundle", "policy_sha256": policy_sha,
                   "domain_profile": domain["domain_profile"], "domain_check_sha256": domain["evidence_sha256"], "mappings": mappings}
        (self.root / base / "binding.json").write_bytes(c.canonical(binding))
        (self.root / base / "domain-check.json").write_bytes(c.canonical({key: value for key, value in domain.items() if key != "evidence_sha256"}))
        witness = {"receiver_host_root": str(self.root), "receiver_root_identity": {"device": self.root.stat().st_dev, "inode": self.root.stat().st_ino},
                   "binding_path": base + "/binding.json", "format": "directory", "path": base + "/bundle",
                   "content_sha256": digest, "bundle_sha256": digest, "policy_sha256": policy_sha}
        manager = SimpleNamespace(origin=SimpleNamespace(project=self.root, host_project=str(self.root)))
        return manager, witness, binding

    def test_missing_or_temporary_policy_is_not_automatic_consent(self):
        for config in ("title: no policy\n", self.config.replace(".unaltraweb/products", "tmp/products"),
                       self.config.replace("enabled: true", "enabled: false")):
            (self.root / "_config.yml").write_text(config)
            with self.assertRaises(c.StorageError):
                reception.policy(self.root)

    def test_reduced_mapping_cannot_hide_an_author_change(self):
        manager, witness, binding = self.retained()
        with patch.object(reception, "durable_binding"):
            reception.verify_record(manager, witness)
            changed = self.root / binding["mappings"][0]["destination"]
            changed.write_bytes(b"author-owned replacement")
            binding["mappings"] = []
            (self.root / witness["binding_path"]).write_bytes(c.canonical(binding))
            with self.assertRaisesRegex(c.StorageError, "Native mapping differs"):
                reception.verify_record(manager, witness)
            self.assertEqual(changed.read_bytes(), b"author-owned replacement")

    def test_stale_policy_and_copied_witness_require_independent_revalidation(self):
        manager, witness, _ = self.retained()
        with patch.object(reception, "durable_binding"):
            copied = copy.deepcopy(witness)
            copied["receiver_root_identity"]["inode"] += 1
            with self.assertRaisesRegex(c.StorageError, "Receiver binding changed"):
                reception.verify_record(manager, copied)
            (self.root / "_config.yml").write_text(self.config.replace("[edited-visual]", "[document]"))
            with self.assertRaisesRegex(c.StorageError, "Receiver policy is stale"):
                reception.verify_record(manager, witness)

    def test_receiver_lock_is_exclusive_and_symlink_destination_cannot_clobber(self):
        with reception.receiver_lock(self.root):
            with self.assertRaises(c.StorageError):
                with reception.receiver_lock(self.root):
                    self.fail("Receiver lock allowed a concurrent transaction")
        outside = self.root / "author.txt"
        outside.write_bytes(b"keep")
        (self.root / "target").symlink_to(outside)
        with reception.receiver_lock(self.root) as root:
            with self.assertRaises(FileExistsError):
                reception.write_new(root, "target", b"overwrite")
        self.assertEqual(outside.read_bytes(), b"keep")
