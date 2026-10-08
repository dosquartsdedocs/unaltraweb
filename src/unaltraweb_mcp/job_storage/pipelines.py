"""Factory-owned domain orchestration on native W1 jobs.

The originating consumer is never repointed at the execution volume. Only an
explicit receiver policy writes final project material; unsuccessful operations
keep their source/result/recovery obligations in retained storage.
"""
from __future__ import annotations

import os
import fnmatch
from pathlib import Path
import tarfile

from .. import artifact_handoff_v1 as handoff, practice_pdf, runtime_identity
from ..distribution import component_reference
from ..editorial_sources import Reader, yaml_mapping
from ..runtime_lifecycle import inspect_image
from . import contract as c, reception
from .manager import Manager


def selected():
    active = runtime_identity.active_runtime()
    return bool((active.env if active else os.environ).get("UNALTRAWEB_JOB_STORAGE_STATE"))


def worker_image(key, variable):
    active = runtime_identity.active_runtime()
    if active is not None:
        return active.worker(key)
    observed = inspect_image(os.environ.get(variable) or component_reference(key))
    c.require(observed["state"] == "matched", "Prepare the exact selected domain image before work", "storage-image-unavailable")
    return observed["observed_image_id"]


class ProductSummary:
    """Read bounded metadata from a verified read-only export; discard bulk bytes."""
    def __init__(self, manifest_sha, report_path):
        self.manifest_sha, self.report_path = manifest_sha, report_path
        self.manifest = self.report = None

    def __call__(self, incoming):
        report_raw = None
        with tarfile.open(fileobj=incoming, mode="r|") as archive:
            for member in archive:
                if member.name not in {"bundle.json", self.report_path}:
                    continue
                c.require(member.isfile() and 0 <= member.size <= c.MAX_DOCUMENT, "Product metadata is outside its bound")
                source = archive.extractfile(member)
                c.require(source is not None, "Product metadata is unreadable")
                raw = source.read(c.MAX_DOCUMENT + 1)
                c.require(len(raw) == member.size, "Product metadata is truncated")
                if member.name == "bundle.json":
                    c.require(c.sha256(raw) == self.manifest_sha, "Product manifest differs from the selected seal")
                    self.manifest = c.parse(raw)
                else:
                    report_raw, self.report = raw, c.parse(raw)
        c.require(self.manifest is not None and report_raw is not None, "Product metadata is incomplete")
        entry = next((item for item in self.manifest["files"] if item["path"] == self.report_path), None)
        c.require(entry is not None and entry["sha256"] == c.sha256(report_raw), "Product report is outside its verified inventory")


def receive_by_policy(manager, registry_id, job_id, product_id, *, private=False):
    with Reader(manager.origin.project) as reader:
        config = yaml_mapping(reader.text("_config.yml"))
    policy = (config.get("unaltraweb") or {}).get("product_retention")
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return {"state": "pending", "mappings": [], "reason": "No enabled explicit durable retention policy"}
    policy, _ = reception.policy(manager.origin.project)
    if private:
        def excluded(path):
            parts = Path(path).parts
            ancestors = ["/".join(parts[:count]) for count in range(1, len(parts)+1)]
            included = config.get("include") or []
            if any(isinstance(pattern, str) and (pattern == "." or any(fnmatch.fnmatchcase(parent, pattern.rstrip("/"))
                   or parent.startswith(pattern.rstrip("/")+"/") for parent in ancestors)) for pattern in included):
                return False
            return parts[0].startswith(".") or any(isinstance(entry, str) and entry.rstrip("/") in ancestors
                                                   for entry in config.get("exclude", []))
        destinations = [policy.get("root", "")]
        assets = policy.get("assets") or {}
        if assets.get("roles"):
            destinations.append(assets.get("root", ""))
        if not all(isinstance(path, str) and path and excluded(path) for path in destinations):
            return {"state": "pending", "mappings": [], "reason": "Private practice delivery needs Jekyll-excluded destinations"}
    received = manager.receive_product(registry_id, job_id, product_id)
    base = Path(received["retention"]["destination"]["path"]).parent
    with Reader(manager.origin.project) as reader:
        binding = c.parse(reader.read((base / "binding.json").as_posix()))
    released = manager.toggle_off([(registry_id, job_id)])
    return {"state": "acknowledged", "mappings": binding["mappings"], "receipt": received["retention"],
            "receipt_sha256": received["retention_sha256"], "storage_release": released}


def build_practice(project, factory, source, version, *, run="", dry_run=False):
    project, factory = Path(project).resolve(strict=True), Path(factory).resolve(strict=True)
    image = worker_image("manual_pdf", "MANUAL_PDF_IMAGE")
    plan = practice_pdf.prepare(project, factory, source, version, image, run, source_root="/work/inputs/prepared")
    prepared = dict(plan["files"])
    # Retain original factory inputs as well as the effective normalized request,
    # derived template and renderer. A factory hash alone is not a source copy.
    with Reader(factory) as reader:
        for name, expected in plan["factory_inputs"].items():
            raw = reader.read(name)
            c.require(c.sha256(raw) == expected, "Factory input changed during preparation", "storage-input-changed")
            prepared["factory/" + name] = raw
    paths = sorted(name for name, digest in plan["original_inputs"].items() if digest is not None)
    pdf_path = "payload/results/practice/" + plan["basename"] + ".pdf"
    preview_path = "payload/results/practice/preview.png"
    result = {"ok": True, "publishes": False, "dry_run": dry_run, "runtime": c.CONTRACT,
              **{key: plan[key] for key in ("source", "version", "language", "audience", "fingerprint")},
              "renderer_image_id": image, "selected_inputs": paths}
    if dry_run:
        return {**result, "retained_pdf_path": pdf_path, "retained_preview_path": preview_path}
    manager = Manager(project)
    state = manager.begin("practice-pdf")
    registry_id, job_id = state["registry_id"], state["job_id"]
    result.update(registry_id=registry_id, job_id=job_id)
    try:
        parameters = {"kind": "practice-pdf", **{key: result[key] for key in ("source", "version", "language", "audience", "fingerprint")},
                      "output_roles": {"results/practice/" + plan["basename"] + ".pdf": "document",
                                       "results/practice/preview.png": "rendered-visual"}}
        state = manager.stage(registry_id, job_id, state["revision"], state["epoch"], paths,
                              parameters=parameters, prepared_files=prepared)["state"]
        executed = manager.run(registry_id, job_id, state["revision"], state["epoch"],
                               ["python3", "/work/inputs/prepared/render_practice.py"], image=image, cwd="results")
        state = executed["state"]
        if executed["report"]["exit_code"] != 0 or executed["report"]["pressure_or_timeout"] is not None:
            result["diagnostics"] = manager.read_diagnostics(registry_id, job_id,
                ["recovery/.manager/" + executed["report"]["operation_id"] + ".log", "results/practice/render.log"])
        c.require(executed["report"]["exit_code"] == 0 and executed["report"]["pressure_or_timeout"] is None,
                  "Practice renderer failed; its source, results and log remain retained", "storage-operation-incomplete")
        practice_pdf._unchanged(project, plan["original_inputs"])
        practice_pdf._unchanged(factory, plan["factory_inputs"])
        state = manager.control({"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "seal",
                                 "registry_id": registry_id, "job_id": job_id,
                                 "expected_revision": state["revision"], "expected_epoch": state["epoch"]})
        product = state["products"][0]
        closed = manager.toggle_off([(registry_id, job_id)])
        c.require(closed["ok"], "Practice storage drain is incomplete", "storage-busy")
        summary = ProductSummary(product["bundle_sha256"], "payload/results/practice/render-report.json")
        manager.export_product(registry_id, job_id, product["id"], "directory", summary)
        by_path = {entry["path"]: entry for entry in summary.manifest["files"]}
        c.require(pdf_path in by_path and preview_path in by_path, "Practice product is missing its PDF or preview")
        received = receive_by_policy(manager, registry_id, job_id, product["id"], private=True)
        mappings = {item["source"]: item["destination"] for item in received["mappings"]}
        destination = received.get("receipt", {}).get("destination", {})
        if destination.get("format") == "directory":
            for path in (pdf_path, preview_path):
                mappings.setdefault(path, destination["path"] + "/" + path)
        return {**result, "product": product, "report": summary.report,
                "pdf": mappings.get(pdf_path), "preview": mappings.get(preview_path),
                "retained_pdf": {"path": pdf_path, "sha256": by_path[pdf_path]["sha256"]},
                "retained_preview": {"path": preview_path, "sha256": by_path[preview_path]["sha256"]},
                "retention": received, "storage": manager.status(registry_id, job_id)}
    except (OSError, ValueError, RuntimeError, handoff.HandoffError) as exc:
        return {**result, "ok": False, "error": str(exc)[:4096], "code": getattr(exc, "code", "storage-operation-incomplete"),
                "storage_release": manager.toggle_off([(registry_id, job_id)])}
