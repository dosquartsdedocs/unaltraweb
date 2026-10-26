"""Private-practice domain orchestration through one selected common job.

No registry, allocation, marker, sampler, retention or cleanup implementation is
owned here. Preparation and product semantics reuse the existing Web renderer.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from . import artifact_handoff_v1 as handoff, practice_pdf
from .processes import run_process
from .shared_jobs import BoundJob, SharedError, require, selected


def _docker(context, arguments, *, timeout=30):
    value = run_process(["docker", "--host", context["docker_endpoint"], *arguments], timeout_seconds=timeout, output_limit=65536)
    require(not value.timed_out and not value.stdout_truncated and not value.stderr_truncated and value.returncode == 0,
            "Selected Docker operation failed; retain the exact job/grant for common recovery", "shared-worker-unknown")
    return value.stdout.strip()


def run_worker(job, context, image, command):
    """Execute one domain actor using the SDK's grant/admission/absence authority."""
    timeout = context.get("worker_timeout_seconds", 900)
    require(_docker(context, ["info", "--format", "{{.ID}}"]) == context["daemon_id"], "Selected Docker daemon changed", "shared-daemon-mismatch")
    grant = job.call("jobs.grant", job_id=context["job_id"], owner_id=context["owner_id"])
    lease = grant["binding"]["lease_id"]
    worker = {"container_id": None, "lease_id": lease, "image_id": image,
              "timeout_seconds": timeout, "recovery_path": "recovery/" + lease}
    try:
        arguments = job.create_args(grant, image, command(grant) if callable(command) else command)
        for flag, value in (("--memory", "1g"), ("--memory-swap", "1g"), ("--pids-limit", "128"), ("--user", context["worker_user"])):
            arguments[arguments.index(flag) + 1] = value
        container = _docker(context, arguments)
        require(__import__("re").fullmatch(r"[0-9a-f]{64}", container), "Create did not return an exact worker ID", "shared-worker-unknown")
        worker["container_id"] = container
        job.call("jobs.actor-start", job_id=context["job_id"], lease_id=lease, container_id=container, timeout_seconds=timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        cancelled = job.client.call("jobs.actor-cancel", workspace=job.workspace, job_id=context["job_id"], lease_id=lease)
        return {"ok": False, "code": "shared-worker-admission-failed", "error": str(exc)[:2048], "worker": worker, "cancellation": cancelled}
    try:
        exit_code = _docker(context, ["container", "wait", container], timeout=timeout + 20)
    except SharedError:
        cancelled = job.client.call("jobs.actor-cancel", workspace=job.workspace, job_id=context["job_id"], lease_id=lease)
        return {"ok": False, "code": "shared-worker-observation-failed",
                "error": "Worker observation failed; common cancellation/recovery remains authoritative",
                "worker": worker, "cancellation": cancelled, "storage": job.status()}
    finished = job.call("jobs.actor-finish", job_id=context["job_id"], lease_id=lease)
    require(finished.get("worker_absent"), "Common manager did not confirm worker absence", "shared-worker-unknown")
    worker.update(exit_code=exit_code, finish=finished)
    if exit_code != "0":
        return {"ok": False, "code": "shared-worker-failed",
                "error": "Domain worker failed; original inputs and recovery diagnostics remain retained",
                "worker": worker, "storage": job.status()}
    return {"ok": True, "worker": worker}


def build(project, factory, source, version, *, run="", dry_run=False):
    context = selected(project)
    require(context is not None, "Select a shared task/job before shared execution", "shared-runtime-unconfigured")
    timeout = context.get("worker_timeout_seconds", 900)
    job = BoundJob(context)
    identity = job.verify_service()
    plan = practice_pdf.prepare(Path(project), Path(factory), source, version, context["pdf_image"], run)
    response = {"ok": True, "publishes": False, "storage_runtime": "gacontext-runtime", "dry_run": dry_run,
        "job_id": context["job_id"], "task_id": context["task_id"], "sdk": {key: identity[key] for key in ("version", "code_sha256")},
        **{key: plan[key] for key in ("source", "version", "language", "audience", "fingerprint")},
        "selected_inputs": plan["original_inputs"], "factory_inputs": plan["factory_inputs"], "pdf": None,
        "delivery": "pending explicit common receiver delivery; no sandbox or dist staging", "worker_timeout_seconds": timeout}
    status = job.status()
    require(status.get("ok"), "Selected job is unavailable", "shared-status-unavailable")
    require(status["state"]["daemon_id"] == context["daemon_id"], "Selected job belongs to a different daemon", "shared-daemon-mismatch")
    path = "exports/practice-" + plan["fingerprint"] + "/bundle.json"
    seals = [row for row in status["seals"] if row["path"] == path]
    if seals:
        require(len(seals) == 1, "Ambiguous native product mapping")
        return {**response, "state": "current", "product": seals[0], "storage": status, "reused": True}
    if dry_run:
        return {**response, "state": "planned", "retained_bundle": path, "storage": status}
    require(status["state"]["phase"] == "open", "Shared job is not open; do not allocate another slot implicitly", "shared-admission-closed")
    admitted = []
    for name, expected in plan["original_inputs"].items():
        if expected is None:
            continue
        state = job.status()
        require(state.get("ok"), "Cannot obtain input admission CAS", "shared-status-unavailable")
        result = job.client.input_file(context["workspace"], context["job_id"], context["owner_id"], name, "inputs/consumer/" + name,
            expected_sha256=expected, expected_bytes=(Path(project) / name).stat().st_size,
            expected_revision=state["state"]["revision"], expected_epoch=state["state"]["epoch"])
        if not result.get("ok"):
            return {**response, "ok": False, "input_admission": result, "storage": job.status()}
        admitted.append(result)
    practice_pdf._unchanged(Path(project), plan["original_inputs"])
    practice_pdf._unchanged(Path(factory), plan["factory_inputs"])
    executed = run_worker(job, context, context["pdf_image"], ["python3", "-I", "-B", "-m", "unaltraweb_mcp.shared_practice_worker",
        "--source", source, "--version", version, "--image", context["pdf_image"], "--fingerprint", plan["fingerprint"],
        *(["--run", run] if run else [])])
    if not executed["ok"]:
        return {**response, **executed}
    practice_pdf._unchanged(Path(project), plan["original_inputs"])
    practice_pdf._unchanged(Path(factory), plan["factory_inputs"])
    sealed = job.transition("seal")
    if not sealed.get("ok"):
        return {**response, "ok": False, "seal": sealed, "worker": executed["worker"]}
    product, = [row for row in sealed["seals"] if row["path"] == path]
    return {**response, "state": "sealed", "product": product, "storage": sealed, "input_admissions": admitted,
            "worker": executed["worker"], "reused": False}


def verify_delivered_pdf(receiver, retention, product):
    """Domain check of durable bytes; generic witness/retirement stay in the SDK."""
    destination = retention["destination"]["path"]
    root = Path(receiver) / destination / "payload/files"
    verified = handoff.check(str(root), "bundle", product["path"], product["bundle_sha256"])
    require(verified.get("ok"), "Delivered native PDF bundle does not verify")
    manifest = json.loads((root / product["path"]).read_bytes())
    parent = (root / product["path"]).parent
    request = json.loads((parent / "payload/request.json").read_bytes())
    from pypdf import PdfReader
    document, = [row for row in manifest["files"] if row["role"] == "document"]
    pdf = parent / document["path"]
    parsed = PdfReader(pdf)
    require(parsed.pages and all(float(page.mediabox.width) > float(page.mediabox.height) for page in parsed.pages),
            "Delivered practice PDF must be landscape")
    for name, expected in request["original_inputs"].items():
        if expected is not None:
            require(practice_pdf.digest((root / "inputs/consumer" / name).read_bytes()) == expected, "Delivered original differs from its domain request")
    return {"ok": True, "pdf": str(pdf), "sha256": document["sha256"], "pages": len(parsed.pages),
            "source": request["source"], "version": request["version"], "native_integration_verified": True,
            "teaching_approval": False, "publishes": False}
