"""Compose retained GIS products and approved readings; never execute GIS code."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import traceback

from . import __version__, artifact_handoff_v1 as h, practice_editions as editions, practice_pdf
from .editorial_sources import canonical, digest
from .manual_release import _install_new_directory
from .shared_jobs import require, sdk
from .shared_practice_worker import put, run as render_reading
from .shared_editions import plan, check_inputs, validated_selection


def run(config, fingerprint, image, verification_path, verifier_worker):
    sdk()
    from gacontext_runtime.worker import WorkerBinding
    project, factory = Path("/work/inputs/consumer"), Path("/opt/unaltraweb")
    with WorkerBinding() as binding:
        request = plan(project, factory, config, image, snapshot=True)
        require(request["fingerprint"] == fingerprint, "Frozen edition inputs or code differ from the admitted plan")
        expected_report = "results/edition-check/" + fingerprint + "/" + verifier_worker["lease_id"] + "/report.json"
        require(verification_path == expected_report and verifier_worker["image_id"] == request["verifier"]["image_id"]
                and verifier_worker["exit_code"] == "0" and verifier_worker["finish"].get("worker_absent") is True,
                "Edition requires an absent, successful actor from its pinned private verifier")
        with binding.open(verification_path) as stream:
            raw_verification = stream.read(4 * 1024 * 1024 + 1)
        require(len(raw_verification) <= 4 * 1024 * 1024, "Native verification report exceeds its budget")
        verification = h.parse_json(raw_verification)
        require(verification["request"]["lease_id"] == verifier_worker["lease_id"], "Verifier report belongs to another lease")
        attempt = "recovery/" + binding.binding["lease_id"]
        put(binding, attempt + "/edition-request.json", canonical(request))
        selection = validated_selection(project, request, verification)
        prefix = "exports/edition-" + fingerprint
        final = Path("/work") / prefix / "bundle.json"
        if final.exists():
            from .shared_editions import verify_product
            verified = verify_product(Path("/work"), prefix + "/bundle.json", digest(final.read_bytes()))
            require(verified["fingerprint"] == fingerprint, "Retained edition differs from this request")
            return {"ok": True, "reused": True, "path": prefix + "/bundle.json", "sha256": digest(final.read_bytes())}
        readings = {}
        spec = request["spec"]
        # Validate both recipients before rendering either one.
        prepared = {who: practice_pdf.prepare(project, factory, spec["readings"][who]["source"], spec["version"], image,
                     **selection[who]["preparation"]) for who in editions.RECIPIENTS}
        for who in editions.RECIPIENTS:
            reading = prepared[who]
            require(reading["audience"] == who and reading["language"] == spec["language"], "Reading recipient/language differs")
            result = render_reading(reading["source"], spec["version"], "", image, reading["fingerprint"],
                                    preparation=selection[who]["preparation"])
            with closing(h.Workspace("/work")) as workspace:
                manifest, _, _ = h.Verifier(workspace).bundle(result["path"], result["sha256"])
            document, = [row for row in manifest["files"] if row["kind"] == "output" and row["role"] == "document"]
            readings[who] = {"bundle": result["path"], "bundle_sha256": result["sha256"],
                "fingerprint": reading["fingerprint"], "pdf": (Path(result["path"]).parent / document["path"]).as_posix(),
                "pdf_sha256": document["sha256"], "pdf_bytes": document["bytes"], "portable_links": reading["portable_links"]}
        stage = "results/edition-candidates/" + fingerprint + "/" + binding.binding["lease_id"]
        put(binding, stage + "/payload/request.json", canonical(request))
        put(binding, stage + "/payload/verification.json", raw_verification)
        for name, expected in request["modules"].items():
            raw = Path(__file__).with_name(name).read_bytes()
            require(digest(raw) == expected, "Edition control code changed")
            put(binding, stage + "/payload/controls/" + name, raw)
        # This marker is a declared native receipt, not scratch or a final file.
        put(binding, stage + "/payload/delivery/selection.json", canonical({"selection": spec["selection"], "config_sha256": request["config_sha256"]}))
        delivery = os.open(Path("/work") / stage / "payload/delivery", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        packages = {}
        try:
            for who in editions.RECIPIENTS:
                selected = selection[who]
                rows = [{**row, "source": "inputs/consumer/" + row["source"]} for row in selected["files"]]
                for name, target in prepared[who]["portable_links"]["targets"].items():
                    if name not in selected["preparation"]["portable_targets"]:
                        rows.append({"id": "reading-resource:" + name, "source": "inputs/consumer/" + name,
                                     "role": "reading-resource", **target})
                reading = readings[who]
                pdf_row = {"id": "reading-" + who, "source": reading["pdf"], "destination": practice_pdf.BASENAMES[spec["language"]] + ".pdf",
                           "sha256": reading["pdf_sha256"], "bytes": reading["pdf_bytes"], "role": "reading"}
                rows.append(pdf_row)
                name = spec["slug"] + ("-docent" if who == "docent" else "") + "-" + spec["version"] + "-" + spec["language"]
                zipped = editions.zip_files(Path("/work"), delivery, name + ".zip", rows)
                pdf = editions.copy_pdf(Path("/work"), delivery, name + ".pdf", pdf_row)
                receipt = {"kind": "unaltraweb-shared-edition-recipient", "schema_version": 1,
                           "recipient": who, "fingerprint": fingerprint, "files": rows, "reading": reading,
                           "pdf": pdf, "zip": zipped, "closure": selected["closure"], "verifier_worker": verifier_worker}
                raw = canonical(receipt)
                editions.write_new(delivery, name + ".receipt.json", raw)
                packages[who] = {"pdf": pdf, "zip": zipped, "receipt": {"path": name + ".receipt.json", "sha256": digest(raw)}}
            os.fsync(delivery)
        finally:
            os.close(delivery)
        value = {"kind": "unaltraweb-shared-practice-edition", "schema_version": 1, "fingerprint": fingerprint,
                 "packages": packages, "readings": readings, "verifier_worker": verifier_worker,
                 "publishes": False, "teaching_approval": False}
        put(binding, stage + "/payload/edition.json", canonical(value))
        check_inputs(project, request["inputs"])
        practice_pdf._unchanged(factory, request["factory_inputs"])
        # Inventory only the new, private candidate; all selected source copying
        # above used the existing guarded PDF/ZIP routines.
        with closing(h.Workspace("/work")) as workspace:
            files, _ = workspace.inventory(stage)
            records = []
            for number, name in enumerate(sorted(files)):
                sha, size, _ = workspace.read(stage + "/" + name, h.MAX_FILE_BYTES)
                is_request = name == "payload/request.json"
                records.append({"id": "request" if is_request else "file-" + str(number), "path": name,
                    "sha256": sha, "bytes": size, "ownership": "producer",
                    "kind": "output" if name.startswith("payload/delivery/") else "input",
                    "role": "request" if is_request else "document" if name.endswith(".pdf") else "edition-zip" if name.endswith(".zip") else "control"})
            workspace.recheck()
        bundle = {"kind": "mcp-artifact-bundle", "schema_version": 1, "request": "request", "files": records, "dependencies": [],
            "producer": {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + digest(canonical(request["modules"])),
                         "runtimes": [{"name": "manual-pdf", "revision": image}, {"name": "qgis-verifier", "revision": request["verifier"]["image_id"]}]}}
        raw = canonical(bundle)
        put(binding, stage + "/bundle.json", raw)
        h.check("/work", "bundle", stage + "/bundle.json", digest(raw))
        _install_new_directory(binding.root, stage, prefix)
        with closing(h.Workspace("/work")) as workspace:
            for parent in (str(Path(stage).parent), "exports"):
                with workspace.directory(parent) as directory:
                    os.fsync(directory)
        return {"ok": True, "path": prefix + "/bundle.json", "sha256": digest(raw), "publishes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "fingerprint", "image", "verification", "verifier-worker"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    h.safe_path(args.config)
    require(h.HASH_RE.fullmatch(args.fingerprint), "Invalid edition fingerprint")
    try:
        print(json.dumps(run(args.config, args.fingerprint, args.image, args.verification, h.parse_json(args.verifier_worker.encode()))))
    except Exception:
        from gacontext_runtime.worker import WorkerBinding
        with WorkerBinding() as binding:
            put(binding, "recovery/" + binding.binding["lease_id"] + "/edition-error.txt", traceback.format_exc().encode()[-65536:])
        raise


if __name__ == "__main__":
    main()
