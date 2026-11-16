"""Synthetic municipal-style original ZIP; deliberately NO PDF/worker/edition."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from unaltraweb_mcp import artifact_publication as publication


class ArchiveFixture:
    def __init__(self, owner):
        temporary = tempfile.TemporaryDirectory(prefix="original-archive-")
        owner.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = "assets/projects/city/original-starter.zip"
        self.control = ".unaltraweb/original-archive.json"
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "remote", "add", "origin", "git@github.com:example/course.git"], check=True)
        self.write(".gitignore", b"sandbox/\ndist/\n")
        self.write("_config.yml", publication.canonical({"lang": "ca", "languages": ["ca"], "exclude": ["practiques/", "sandbox/", "dist/"],
            "unaltraweb": {"site_profile": "unaltremanual"}}))
        qgz = io.BytesIO()
        with zipfile.ZipFile(qgz, "w") as bundle:
            bundle.writestr("project.qgs", b'<synthetic-project><wms>https://wms.example.invalid/network-needed</wms></synthetic-project>')
        self.members = {"starter/README.md": b"PRIVATE_ORIGINAL_PROVENANCE: synthetic starter, no original approval/language/role seal.\n",
            "starter/LICENSE.txt": b"Synthetic CC-BY provenance declaration, DATA not an independently certified licence.\n",
            "starter/build.py": ("from pathlib import Path\nPath(" + repr(str(self.root / "must-not-execute")) + ").touch()\n").encode(),
            "starter/data/area.geojson": b'{"type":"FeatureCollection","features":[]}',
            "starter/data/area.gpkg": b"opaque synthetic GPKG bytes; no GIS validation is asserted",
            "starter/project.qgz": qgz.getvalue()}
        self.members["starter/SHA256SUMS"] = "".join(publication.digest(raw) + "  " + name.removeprefix("starter/") + "\n" for name, raw in self.members.items()).encode()
        self.write_archive()
        self.write("context/provenance.md", b"PRIVATE_LOCAL_NOTE: original starter retained; source/role/language/approval unknown; WMS needs network.\n")
        self.write("context/SHA256SUMS", (self.pin(self.path)["sha256"] + "  original-starter.zip\n").encode())
        self.request = {"kind": "unaltraweb.original-private-archive", "schema_version": 1, "purpose": "private-archive",
            "consumer_repository": {"remote": "origin", "host": "github.com", "repository": "example/course"},
            "archive_id": "city-starter", "archive": self.pin(self.path), "snapshot": "sandbox/original-archives/city-starter/trial",
            "classification": {"kind": "initial-project", "role": "unknown", "language": "unknown", "human_approval": "unknown",
                "native_reopen": "not-performed", "scientific_validation": "not-performed", "full_offline": "requires-network"},
            "evidence": [{"id": "provenance", "role": "provenance", "file": self.pin("context/provenance.md")},
                         {"id": "archive-sums", "role": "checksums", "file": self.pin("context/SHA256SUMS")}],
            "member_references": [{"role": "provenance", "path": "starter/README.md", "sha256": publication.digest(self.members["starter/README.md"])}],
            "checksums": [{"source": "member", "path": "starter/SHA256SUMS", "scope": "members", "base": "starter"},
                          {"source": "evidence", "path": "archive-sums", "scope": "archive", "base": "assets/projects/city"}]}
        self.save()
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore", "_config.yml", self.control, "assets", "context"], check=True)

    def write(self, path, raw):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    def pin(self, path):
        raw = (self.root / path).read_bytes()
        return {"path": path, "sha256": publication.digest(raw), "bytes": len(raw)}

    def write_archive(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, raw in self.members.items():
                archive.writestr(name, raw)
        self.write(self.path, data.getvalue())

    def save(self):
        self.write(self.control, publication.canonical(self.request))
        self.sha = self.pin(self.control)["sha256"]

    def route(self, admitted):
        config = {"kind": "unaltraweb.practice-artifact-storage", "schema_version": 3, "consumer_repository": self.request["consumer_repository"],
            "publication": {"kind": "gacontext.publication-policy", "schema_version": 1, "project_id": "private-course", "default_target": "s4",
                "targets": {"s4": {"driver": "s3", "endpoint": "https://s3.example.invalid", "region": "synthetic-1", "bucket": "course", "prefix": "originals",
                    "visibility": "private", "audiences": ["private", "student", "teacher"], "auth_ref": "exact-project"}}},
            "artifacts": {"starter": {"target": "s4", "audience": "private", "format": "zip", "storage_profile": "authenticated-private-v1",
                "delivery_layout": "files-v1", "receipt": admitted["receipt"], "receipt_sha256": admitted["receipt_sha256"]}}}
        self.write(publication.CONFIG, publication.canonical(config))
        subprocess.run(["git", "-C", str(self.root), "add", publication.CONFIG], check=True)
        return config, self.pin(publication.CONFIG)["sha256"]
