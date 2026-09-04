from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import tempfile
import tarfile
import unittest
from pathlib import Path

from scripts.manual import verify_release_assets
from unaltraweb_mcp import manual_release


class ReleaseAssetVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.site = self.root / "site"
        self.assets = self.root / "release-assets"
        (self.site / "assets/pdf").mkdir(parents=True)
        (self.site / "assets/img").mkdir(parents=True)
        (self.site / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
        (self.site / "assets/pdf/manual-en.pdf").write_bytes(b"pdf\n")
        (self.site / "assets/img/manual-cover-en.png").write_bytes(b"cover\n")
        self.assets.mkdir()
        self.selector = "v2026.09"
        self.reviewed_sha = "1" * 40
        self.core_sha = "2" * 40
        self.image = "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:" + "3" * 64
        self.site_build_image = "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:" + "5" * 64
        self.repository = "example/manual"
        self.write_assets()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_archive(self, *, root_mode: int = 0o755, archive_format: int = tarfile.PAX_FORMAT) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"

        def canonical(member: tarfile.TarInfo) -> tarfile.TarInfo:
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.mtime = 0
            member.mode = root_mode if member.name in {"", "."} else (0o755 if member.isdir() else 0o644)
            return member

        with tarfile.open(archive, "w:gz", format=archive_format) as handle:
            handle.add(self.site, arcname=".", filter=canonical)

    def write_sums(self) -> None:
        records = []
        for path in sorted(self.assets.iterdir(), key=lambda item: item.name):
            if path.name == "SHA256SUMS":
                continue
            records.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
        (self.assets / "SHA256SUMS").write_text("".join(records), encoding="utf-8")

    def write_assets(self) -> None:
        snapshot = manual_release._snapshot(self.site, canonical_modes=True)
        pdf = self.site / "assets/pdf/manual-en.pdf"
        cover = self.site / "assets/img/manual-cover-en.png"
        manifest = {
            "channel": "stable",
            "fingerprint_schema": "unaltraweb-tree-v1",
            "pdfs": [
                {
                    "language": "en",
                    "path": "pdf/manual-en.pdf",
                    "published_path": "assets/pdf/manual-en.pdf",
                    "site_path": "site/assets/pdf/manual-en.pdf",
                    "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                    "size": pdf.stat().st_size,
                    "cover_path": "assets/img/manual-cover-en.png",
                    "cover_site_path": "site/assets/img/manual-cover-en.png",
                    "cover_sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
                    "cover_size": cover.stat().st_size,
                    "draft": False,
                }
            ],
            "schema_version": 2,
            "selector": self.selector,
            "site": {
                "bytes": snapshot["bytes"],
                "file_count": snapshot["file_count"],
                "path": "site",
                "sha256": snapshot["sha256"],
            },
            "source": {
                "bytes": 1,
                "commit": self.reviewed_sha,
                "file_count": 1,
                "sha256": "4" * 64,
                "site_build_image": self.site_build_image,
                "source_date_epoch": "1788393600",
            },
        }
        manifest_content = verify_release_assets.canonical_json(manifest)
        manifest_sha256 = hashlib.sha256(manifest_content).hexdigest()
        (self.assets / "release-manifest.json").write_bytes(manifest_content)
        publication = {
            "candidate_manifest_sha256": manifest_sha256,
            "channel": "stable",
            "core_sha": self.core_sha,
            "manual_pdf_image": self.image,
            "python_version": "3.13.3",
            "repository": self.repository,
            "ruby_version": "3.3.5",
            "schema_version": 2,
            "selector": self.selector,
            "site_build_image": self.site_build_image,
            "site_build_python_version": "3.13.5",
            "source_date_epoch": "1788393600",
            "source_sha": self.reviewed_sha,
            "vegavisuals_sha": "",
        }
        (self.assets / "publication.json").write_bytes(verify_release_assets.canonical_json(publication))
        (self.assets / "manual-en.pdf").write_bytes(pdf.read_bytes())
        self.write_archive()
        self.write_sums()

    def arguments(self) -> argparse.Namespace:
        manifest_sha256 = hashlib.sha256((self.assets / "release-manifest.json").read_bytes()).hexdigest()
        return argparse.Namespace(
            assets=self.assets,
            selector=self.selector,
            reviewed_sha=self.reviewed_sha,
            core_sha=self.core_sha,
            manual_pdf_image=self.image,
            python_version="3.13.3",
            ruby_version="3.3.5",
            site_build_image=self.site_build_image,
            vegavisuals_sha="",
            repository=self.repository,
            candidate_manifest_sha256=manifest_sha256,
        )

    def test_accepts_assets_that_exactly_match_reviewed_manifest(self) -> None:
        result = verify_release_assets.verify(self.arguments())

        self.assertTrue(result["ok"])
        self.assertEqual(result["selector"], self.selector)

    def test_exact_transfer_comparison_accepts_independent_copy(self) -> None:
        received = self.root / "received-assets"
        shutil.copytree(self.assets, received)

        verify_release_assets.compare_asset_directories(self.assets, received)

        with self.assertRaisesRegex(verify_release_assets.VerificationError, "independent directories"):
            verify_release_assets.compare_asset_directories(self.assets, self.assets)

    def test_direct_verification_rejects_trailing_bytes_even_with_updated_sums(self) -> None:
        received = self.root / "received-assets"
        shutil.copytree(self.assets, received)
        archive = received / f"manual-site-{self.selector}.tar.gz"
        archive.write_bytes(archive.read_bytes() + b"trailing transfer bytes")
        records = []
        for path in sorted(received.iterdir(), key=lambda item: item.name):
            if path.name != "SHA256SUMS":
                records.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
        (received / "SHA256SUMS").write_text("".join(records), encoding="utf-8")
        arguments = self.arguments()
        arguments.assets = received

        with self.assertRaisesRegex(
            verify_release_assets.VerificationError,
            "trailing bytes or a concatenated gzip member",
        ):
            verify_release_assets.verify(arguments)
        with self.assertRaisesRegex(verify_release_assets.VerificationError, "differs from the locally verified"):
            verify_release_assets.compare_asset_directories(self.assets, received)

    def test_direct_verification_rejects_a_concatenated_gzip_member(self) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"
        member = archive.read_bytes()
        archive.write_bytes(member + member)
        self.write_sums()

        with self.assertRaisesRegex(
            verify_release_assets.VerificationError,
            "trailing bytes or a concatenated gzip member",
        ):
            verify_release_assets.verify(self.arguments())

    def test_rejects_nonzero_data_after_tar_end_inside_one_gzip_member(self) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"
        with tarfile.open(archive, "r:gz") as handle:
            for _ in handle:
                pass
            logical_tar_end = handle.offset
        payload = gzip.decompress(archive.read_bytes())
        insertion = logical_tar_end + 2 * tarfile.BLOCKSIZE
        self.assertGreaterEqual(len(payload), insertion)
        payload = payload[:insertion] + b"unauthorized".ljust(tarfile.BLOCKSIZE, b"\0") + payload[insertion:]
        archive.write_bytes(gzip.compress(payload, mtime=0))
        self.write_sums()

        with self.assertRaisesRegex(
            verify_release_assets.VerificationError,
            "nonzero data after its logical tar end",
        ):
            verify_release_assets.verify(self.arguments())

    def test_rejects_a_single_zero_tar_end_block(self) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"
        with tarfile.open(archive, "r:gz") as handle:
            for _ in handle:
                pass
            logical_tar_end = handle.offset
        payload = gzip.decompress(archive.read_bytes())
        archive.write_bytes(gzip.compress(payload[: logical_tar_end + tarfile.BLOCKSIZE], mtime=0))
        self.write_sums()

        with self.assertRaisesRegex(
            verify_release_assets.VerificationError,
            "canonical two-block tar end marker",
        ):
            verify_release_assets.verify(self.arguments())

    def test_rejects_unaligned_zero_tar_padding(self) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"
        payload = gzip.decompress(archive.read_bytes()) + b"\0"
        archive.write_bytes(gzip.compress(payload, mtime=0))
        self.write_sums()

        with self.assertRaisesRegex(
            verify_release_assets.VerificationError,
            "decompressed stream is not block aligned",
        ):
            verify_release_assets.verify(self.arguments())

    def test_accepts_valid_gnu_tar_record_padding(self) -> None:
        self.write_archive(archive_format=tarfile.GNU_FORMAT)
        self.write_sums()

        self.assertTrue(verify_release_assets.verify(self.arguments())["ok"])

    def test_rejects_tampered_site_even_when_outer_sums_are_regenerated(self) -> None:
        (self.site / "index.html").write_text("tampered\n", encoding="utf-8")
        self.write_archive()
        self.write_sums()

        with self.assertRaisesRegex(verify_release_assets.VerificationError, "Site archive fingerprint"):
            verify_release_assets.verify(self.arguments())

    def test_rejects_tampered_pdf_and_unlisted_asset(self) -> None:
        (self.assets / "manual-en.pdf").write_bytes(b"tampered pdf\n")
        self.write_sums()
        with self.assertRaisesRegex(verify_release_assets.VerificationError, "Standalone PDF"):
            verify_release_assets.verify(self.arguments())

        (self.assets / "manual-en.pdf").write_bytes(b"pdf\n")
        (self.assets / "unlisted.txt").write_text("unexpected\n", encoding="utf-8")
        self.write_sums()
        with self.assertRaisesRegex(verify_release_assets.VerificationError, "unauthorized"):
            verify_release_assets.verify(self.arguments())

    def test_rejects_invalid_site_build_python_provenance(self) -> None:
        publication_path = self.assets / "publication.json"
        publication = json.loads(publication_path.read_text(encoding="utf-8"))
        publication["site_build_python_version"] = "rolling"
        publication_path.write_bytes(verify_release_assets.canonical_json(publication))
        self.write_sums()

        with self.assertRaisesRegex(verify_release_assets.VerificationError, "site-build Python version"):
            verify_release_assets.verify(self.arguments())

    def test_rejects_links_in_site_archive(self) -> None:
        archive = self.assets / f"manual-site-{self.selector}.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            root = tarfile.TarInfo(".")
            root.type = tarfile.DIRTYPE
            root.mode = 0o755
            handle.addfile(root)
            link = tarfile.TarInfo("./escape")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../outside"
            handle.addfile(link)
        self.write_sums()

        with self.assertRaisesRegex(verify_release_assets.VerificationError, "link or special"):
            verify_release_assets.verify(self.arguments())

    def test_rejects_noncanonical_archive_root_mode(self) -> None:
        self.write_archive(root_mode=0o777)
        self.write_sums()

        with self.assertRaisesRegex(verify_release_assets.VerificationError, "canonical mode-0755"):
            verify_release_assets.verify(self.arguments())


if __name__ == "__main__":
    unittest.main()
