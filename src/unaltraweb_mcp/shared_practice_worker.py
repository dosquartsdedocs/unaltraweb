"""Private PDF domain worker. Storage authority is exclusively the common SDK."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import traceback

from . import __version__, artifact_handoff_v1 as handoff, practice_pdf
from .editorial_sources import canonical, digest
from .shared_jobs import require, sdk


def put(binding, path, raw):
    """Only immutable exact reuse; never replace retained source or output."""
    try:
        with binding.open(path) as stream:
            existing = stream.read(len(raw) + 1)
        require(existing == raw, "Existing retained domain file has different bytes", "shared-output-collision")
    except FileNotFoundError:
        with binding.open(path, write=True) as stream:
            stream.write(raw)


def file_record(number, name, raw):
    request = name == "payload/request.json"
    return {"id": "request" if request else "file-" + str(number),
            "kind": "output" if name.startswith("payload/results/") else "input",
            "role": "request" if request else "document" if name.endswith(".pdf") else "control",
            "path": name, "bytes": len(raw), "sha256": digest(raw), "ownership": "producer"}


def run(source, version, run_name, image, fingerprint, *, preparation=None):
    sdk()  # Exact installed SDK payload; no source-checkout fallback.
    from gacontext_runtime.worker import WorkerBinding
    factory = Path("/opt/unaltraweb")
    project = Path("/work/inputs/consumer")
    options = preparation or {}
    require(not options.keys() - {"portable_targets", "bindings", "products", "restricted"}, "Unexpected shared reading preparation fields")
    with WorkerBinding() as binding:
        request = {"kind": "unaltraweb.shared-practice-request", "schema_version": 1, "source": source,
                   "version": version, "run": run_name, "image_id": image, "fingerprint": fingerprint,
                    "publication": "unpublished shared-runtime owner candidate"}
        if preparation is not None:
            request["preparation"] = preparation
        prefix = "exports/practice-" + fingerprint
        # The effective request is fsynced in protected storage before rendering.
        put(binding, "results/requests/" + fingerprint + ".json", canonical(request))
        attempt = "recovery/" + binding.binding["lease_id"]
        if preparation is not None:
            attempt += "/" + fingerprint
        put(binding, attempt + "/request.json", canonical({**request, "lease_id": binding.binding["lease_id"]}))
        manifest_path = Path("/work") / prefix / "bundle.json"
        if manifest_path.exists():
            raw = manifest_path.read_bytes()
            handoff.check("/work", "bundle", prefix + "/bundle.json", digest(raw))
            require(json.loads((manifest_path.parent / "payload/request.json").read_bytes())["fingerprint"] == fingerprint,
                    "Retained request differs from this operation")
            return {"ok": True, "reused": True, "path": prefix + "/bundle.json", "sha256": digest(raw)}
        plan = practice_pdf.prepare(project, factory, source, version, image, run_name, **options)
        require(plan["fingerprint"] == fingerprint, "Worker sources/controls differ from the prepared domain request", "shared-input-changed")
        temporary = "scratch/tmp/practice-" + fingerprint + "/" + binding.binding["lease_id"]
        source_root = "/work/" + temporary + "/source"
        effective = practice_pdf.prepare(project, factory, source, version, image, run_name, source_root=source_root, **options)
        for name, raw in effective["files"].items():
            put(binding, temporary + "/source/" + name, raw)
        put(binding, temporary + "/output/intent.json", canonical(request))
        # Preserve factory sources, normalized controls and effective Markdown;
        # bulk image copies, TeX, preview and extraction work remain in scratch.
        retained = {"payload/request.json": canonical({**request, "original_inputs": plan["original_inputs"],
            "factory_inputs": plan["factory_inputs"], "effective_fingerprint": effective["fingerprint"]})}
        worker_source = Path(__file__).read_bytes()
        retained["payload/factory/shared_practice_worker.py"] = worker_source
        for name, raw in effective["files"].items():
            if not name.startswith("assets/"):
                retained["payload/controls/" + name] = raw
        for name, expected in plan["factory_inputs"].items():
            raw = (factory / name).read_bytes()
            require(digest(raw) == expected, "Factory control changed inside the selected worker")
            retained["payload/factory/" + name] = raw
        for name, raw in retained.items():
            # Effective controls contain this attempt's scratch resource root.
            # Keep interrupted attempts immutable so a same-job retry can retain
            # its own controls without replacing the earlier evidence.
            put(binding, "results/prepared/" + fingerprint + "/" + binding.binding["lease_id"] + "/" + name, raw)
        output = Path("/work") / temporary / "output"
        spec = importlib.util.spec_from_file_location("unaltraweb_shared_pdf_render", factory / "scripts/manual/render_practice.py")
        render = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(render)
        os.environ.update(HOME=str(output), SOURCE_DATE_EPOCH="0", FORCE_SOURCE_DATE="1", TZ="UTC", TMPDIR=str(output))
        try:
            # Write subprocess diagnostics directly to protected storage. A hard
            # deadline/kill need not execute Python cleanup for this log to survive.
            with binding.open(attempt + "/render.log", write=True) as log:
                render.main(source=source_root, output=output, log_stream=log)
            practice_pdf._unchanged(project, plan["original_inputs"])
            practice_pdf._unchanged(factory, plan["factory_inputs"])
        except Exception:
            put(binding, attempt + "/error.txt", traceback.format_exc().encode()[-65536:])
            raise
        with binding.open(attempt + "/render.log") as log:
            raw_log = log.read(16 * 1024 * 1024 + 1)
        require(len(raw_log) <= 16 * 1024 * 1024, "Render log exceeds the native retention budget")
        retained["payload/results/render.log"] = raw_log
        for name in (plan["basename"] + ".pdf", "render-report.json", "source.effective.md", "source.effective.json"):
            retained["payload/results/" + name] = (output / name).read_bytes()
        records = []
        for number, (name, raw) in enumerate(sorted(retained.items())):
            put(binding, prefix + "/" + name, raw)
            records.append(file_record(number, name, raw))
        bundle = {"kind": "mcp-artifact-bundle", "schema_version": 1, "request": "request", "files": records, "dependencies": [],
                  "producer": {"name": "unaltraweb", "version": __version__,
                               "revision": "sha256:" + digest(canonical({**plan["factory_inputs"], "shared_practice_worker.py": digest(worker_source)})),
                               "runtimes": [{"name": "manual-pdf", "revision": image}]}}
        raw = canonical(bundle)
        put(binding, prefix + "/bundle.json", raw)
        handoff.check("/work", "bundle", prefix + "/bundle.json", digest(raw))
        return {"ok": True, "path": prefix + "/bundle.json", "sha256": digest(raw), "publishes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--run", default="")
    parser.add_argument("--image", required=True)
    parser.add_argument("--fingerprint", required=True)
    args = parser.parse_args()
    if not __import__("re").fullmatch(r"[0-9a-f]{64}", args.fingerprint):
        raise ValueError("Invalid domain fingerprint")
    try:
        print(json.dumps(run(args.source, args.version, args.run, args.image, args.fingerprint)))
    except Exception:
        from gacontext_runtime.worker import WorkerBinding
        with WorkerBinding() as binding:
            put(binding, "recovery/" + binding.binding["lease_id"] + "/fatal.txt", traceback.format_exc().encode()[-65536:])
        raise


if __name__ == "__main__":
    main()
