"""Installed Carta -> unaltraweb acceptance; authenticated final packet only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from distributed_launcher_smoke import Client

ACCEPTANCE_SHA = "1bc7c467f3e35abf9fa5c27583dd8cc3ad4d4372f930c4be60ed142122158504"
ARCHIVE_SHA = "8764a717bda33e15b48b3a06fe6fbe5dc075abedf4fd52bd37fdf4ed70896179"
RECEIPT_SHA = "9d94b918db086b445e4d8a3ece2435622e0f9f9893bcd50708b4d13f5ca0ad44"


def extract_evidence(packet: Path, destination: Path) -> dict:
    from unaltraweb_mcp.artifact_handoff_v1 import safe_path

    for name, expected in (("distribution.json", RECEIPT_SHA), ("acceptance-0.3.0rc1.json", ACCEPTANCE_SHA), ("acceptance-0.3.0rc1.tar.gz", ARCHIVE_SHA)):
        assert hashlib.sha256((packet / name).read_bytes()).hexdigest() == expected
    accepted = json.loads((packet / "acceptance-0.3.0rc1.json").read_text())
    with tarfile.open(packet / "acceptance-0.3.0rc1.tar.gz") as archive:
        members = archive.getmembers()
        assert len(members) == len(accepted["evidence_files"])
        assert {item.name for item in members} == {"acceptance/" + name for name in accepted["evidence_files"]}
        destination.mkdir(parents=True, exist_ok=False)
        for member in members:
            safe_path(member.name)
            relative = member.name.removeprefix("acceptance/")
            assert member.isfile() and member.size <= 1024 * 1024
            data = archive.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == accepted["evidence_files"][relative]
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(data)
    return accepted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--image")
    parser.add_argument("--pdf-image")
    args = parser.parse_args()
    if args.extract:
        print(json.dumps(extract_evidence(args.packet, args.extract)["bundle_verification"], indent=2))
        return
    if not all((args.output, args.cli, args.launcher, args.image, args.pdf_image)):
        parser.error("Installed acceptance needs --output, --cli, --launcher, --image and --pdf-image")
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    selected_pdf = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", args.pdf_image], text=True).strip()
    controller = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image], text=True))[0]
    configured_pdf = next((value.split("=", 1)[1] for value in controller["Config"]["Env"] if value.startswith("MANUAL_PDF_IMAGE=")), "")
    if not configured_pdf:
        # Published candidates are exercised directly, without deriving a new
        # controller image or changing the release's selected PDF worker.
        configured_pdf = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--entrypoint", "python3", args.image,
            "-c", "from unaltraweb_mcp.distribution import component_reference; print(component_reference('manual_pdf'))"], text=True).strip()
        assert "@sha256:" in configured_pdf, "Published acceptance requires an immutable native PDF selection"
    actual_pdf = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", configured_pdf], text=True).strip()
    assert actual_pdf == selected_pdf, "The runtime does not select the requested PDF worker"
    producer = output / "producer"
    accepted = extract_evidence(args.packet, producer)
    original_bundle = producer / "wheel" / accepted["bundle_verification"]["wheel"]["native"]["path"]
    expected = accepted["bundle_verification"]["wheel"]["native"]["sha256"]
    receiver = output / "receiver"
    receiver.mkdir()
    subprocess.run(["git", "init", "--quiet", str(receiver)], check=True)
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "UNALTRAWEB_FACTORY_DIR", "MCP_CONSUMER_WORKSPACE"}}

    def cli(project, *arguments):
        result = subprocess.run([str(args.cli), "--project", str(project), *arguments], cwd=output, env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, (result.stdout, result.stderr)
        value = json.loads(result.stdout)
        assert value.get("ok", True), value
        return value

    cli(receiver, "new-web", "--site-profile", "unaltremanual", "--title", "Retained letter integration", "--baseurl", "/letter-proof")
    incoming = receiver / "tmp/incoming/letter"
    shutil.copytree(original_bundle.parent, incoming)
    common = ("mcp", "import-artifact-bundle", "--path", "tmp/incoming/letter/bundle.json", "--sha256", expected,
              "--import-id", "carta", "--content-path", "_chapters/en/carta.md", "--title", "Retained published letter")
    plan = cli(receiver, *common)
    assert plan["dry_run"] and not (receiver / ".unaltraweb/artifacts").exists()
    imported = cli(receiver, *common, "--apply", "--confirm-import")
    record_path = imported["integration"]
    cli(receiver, "mcp", "artifact-import-check")
    original_pdf_hash = hashlib.sha256((incoming / "payload/output/letter.pdf").read_bytes()).hexdigest()
    from pypdf import PdfReader
    original_pages = [" ".join((page.extract_text() or "").split()) for page in PdfReader(incoming / "payload/output/letter.pdf").pages]
    assert original_pages and all(original_pages)
    chapter = receiver / "_chapters/en/carta.md"
    chapter.write_text(chapter.read_text() + "\nThe retained original remains available with its source evidence.\n")
    author_hash = hashlib.sha256(chapter.read_bytes()).hexdigest()
    reused = cli(receiver, *common, "--apply", "--confirm-import")
    assert reused["reused"] and hashlib.sha256(chapter.read_bytes()).hexdigest() == author_hash
    shutil.rmtree(producer)
    shutil.rmtree(receiver / "tmp/incoming")
    assert not producer.exists()
    cli(receiver, "mcp", "artifact-import-check")
    evidence = {"profile": "letter-pdf-v1", "packet_sha256": RECEIPT_SHA, "bundle_sha256": expected,
                "import": imported, "producer_retired": True, "mapped_pdf_sha256": original_pdf_hash,
                 "runtimes": {"mcp_image_id": controller["Id"], "pdf_image_id": selected_pdf, "mcp_reference": args.image,
                              "pdf_reference": args.pdf_image, "configured_pdf": configured_pdf,
                              "source_commit": controller["Config"].get("Labels", {}).get("org.opencontainers.image.revision", "")},
                 "original_pages": len(original_pages), "stages": []}

    def render(project, name):
        client = Client(args.launcher, project, args.image, output / f"{name}.log")
        try:
            client.tool("manual_authoring_capabilities")
            client.tool("editorial_policy")
            client.tool("editorial_status")
            config = client.tool("site_source_read", path="_config.yml")
            enabled = config["content"].replace("      enabled: false\n", "      enabled: true\n", 1)
            if enabled != config["content"]:
                client.tool("site_source_write", path="_config.yml", content=enabled, expected_sha256=config["sha256"], dry_run=False)
            client.tool("prose_check")
            subprocess.run(["git", "-C", str(project), "add", "--", "."], check=True)
            client.tool("site_check")
            if name == "relocated":
                client.tool("manual_pdf_build", language="en")
            prepared = client.tool("manual_pdf_preview_prepare")
            assert not prepared["publishes"]
            client.tool("build_site")
            client.tool("artifact_import_check", output_folder="_site")
            started = client.tool("preview_start", timeout_seconds=180)
            client.tool("http_check", paths=["/letter-proof/en/retained/carta/", "/letter-proof/assets/documents/carta.pdf"])
            assert not (project / "_site/.unaltraweb/artifacts").exists()
            pdf = project / "tmp/manual-pdf/en/manual-en.pdf"
            rendered = PdfReader(pdf)
            # Compare with the actual original font encoding, including retained
            # ligatures. Require every source page in order, not just its title.
            pages = iter(enumerate(" ".join((page.extract_text() or "").split()) for page in rendered.pages))
            matched_pages = []
            for original in original_pages:
                match = next((index for index, text in pages if original in text), None)
                assert match is not None, "An original letter page is absent from the composed PDF"
                matched_pages.append(match + 1)
            assert hashlib.sha256((project / "assets/documents/carta.pdf").read_bytes()).hexdigest() == original_pdf_hash
            assert hashlib.sha256(chapter.read_bytes() if chapter.exists() else (project / "_chapters/en/carta.md").read_bytes()).hexdigest() == author_hash
            saved = output / f"{name}.pdf"
            shutil.copyfile(pdf, saved)
            evidence["stages"].append({"stage": name, "port": started["port"], "pdf_sha256": hashlib.sha256(saved.read_bytes()).hexdigest(), "pages": len(rendered.pages),
                                       "retained_pages": matched_pages, "forced_pdf_rebuild": name == "relocated"})
        finally:
            try:
                client.tool("preview_stop")
                cleanup = client.tool("manual_pdf_preview_clean")
                if cleanup.get("receipt_sha256"):
                    client.tool("manual_pdf_preview_clean", dry_run=False, confirm_clean=True, expected_receipt_sha256=cleanup["receipt_sha256"])
            finally:
                client.close()

    render(receiver, "integrated")
    moved = output / "relocated-receiver"
    receiver.rename(moved)
    cli(moved, "mcp", "artifact-import-check", "--output-folder", "_site")
    generic = subprocess.run([str(args.cli.parent / "python"), "-m", "unaltraweb_mcp.artifact_handoff_v1", "integration", "--workspace", str(moved), "--path", record_path, "--sha256", imported["integration_sha256"], "--json"], cwd=output, env=env, capture_output=True, text=True, check=True)
    evidence["generic_after_move"] = json.loads(generic.stdout)
    render(moved, "relocated")
    evidence["receiver"] = str(moved)
    (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
