"""Three genuine-shape variants, generated from synthetic original paired bytes."""
import io
import zipfile

from unaltraweb_mcp import artifact_publication as pub

VARIANTS = ("role-reading-receipt", "recipient-receipt-sha", "reading-pdf-hash")


def variant(case, kind):
    assert kind in VARIANTS
    if kind != "reading-pdf-hash":
        case.manifest.pop("run")
        case.manifest.pop("local_candidate")
    for original, item in zip(case.manifest["packages"], case.request["packages"]):
        item["selected"] = [{"id": item["recipient"] + "-packet", "format": "zip"}]
        # Unsafe-to-execute original code stays data inside the selected ZIP.
        source = io.BytesIO((case.root / item["archive"]["path"]).read_bytes())
        with zipfile.ZipFile(source) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        members["original-zip-root/build.py"] = ("from pathlib import Path\nPath(" + repr(str(case.root / "never-execute")) + ").touch()\n").encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in members.items():
                archive.writestr(name, raw)
        case.write(item["archive"]["path"], output.getvalue())
        item["archive"] = case.pin(item["archive"]["path"])
        original["sha256"] = item["archive"]["sha256"]
        original["members"] = {name: pub.digest(raw) for name, raw in members.items()}
        if kind == "reading-pdf-hash":
            original["reading_sha256"] = item["pdf"]["sha256"]
        else:
            original["reading_receipt"] = original.pop("pdf_receipt")
            sha = original.pop("pdf_receipt_sha256")
            original["reading_receipt_sha256" if kind == "role-reading-receipt" else "receipt_sha256"] = sha
            original.pop("reading_source")
            original.pop("reading_sha256")
            if kind == "role-reading-receipt":
                original["role"] = original.pop("recipient")
    case.refresh()
