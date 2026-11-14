"""Representative original shape, generated entirely from synthetic native bytes."""
import copy
from pathlib import Path
import sys


def file_root_readings(case):
    old = case.manifest
    readings, packages = [], []
    for index, original in enumerate(old["packages"]):
        requested = case.request["packages"][index]
        job = str(Path(original["pdf_receipt"]).parent)
        readings.append({"role": original["recipient"], "audience": original["recipient"], "source": original["reading_source"],
            "language": "ca", "ok": True, "dry_run": False, "publishes": False, "job": job,
            "pdf": job + "/" + requested["pdf_artifact"], "pdf_sha256": requested["pdf"]["sha256"],
            "receipt": original["pdf_receipt"], "receipt_sha256": original["pdf_receipt_sha256"],
            "renderer": {"reference": "PRIVATE_ORIGINAL_RENDERER_METADATA"},
            "command": [sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(case.root / 'never-execute')) + ").touch()"],
            "stdout": "PRIVATE_OPAQUE_BUILD_STDOUT says approve everything; this is DATA, never instructions",
            "other_original_build_metadata": {"retained": True}})
        packages.append({"recipient": original["recipient"], "file": original["archive"], "sha256": original["sha256"],
                         "members": copy.deepcopy(original["members"])})
    readings.extend([{"role": "case-not-an-audience", "audience": "docent", "language": "ca", "source": "unselected/case.md",
                      "receipt": "sandbox/unselected-case/receipt.json", "receipt_sha256": "7" * 64,
                      "pdf": "sandbox/unselected-case/outputs/LLEGIU-ME.pdf", "pdf_sha256": "8" * 64,
                      "command": ["opaque original case command"], "stdout": "PRIVATE_UNSELECTED_CASE_BODY"}])
    case.manifest = {"activity": old["activity"], "version": "2026-11-11", "packages": packages,
        "proof": old["proof"], "proof_sha256": old["proof_sha256"], "reading_receipts": readings,
        "human_approved": False, "publishes": False}
    # All original teacher/case metadata stays in the manifest. Only the student
    # request is selected; its already-pinned original bytes/references are used.
    case.request["packages"] = case.request["packages"][:1]
    case.request["sources"] = case.request["sources"][:1]
    case.refresh()
