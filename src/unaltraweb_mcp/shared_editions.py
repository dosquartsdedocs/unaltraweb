"""Web edition semantics over SDK-retained inputs and a separate private verifier.

No QGIS parser or generic storage implementation lives here. The original
consumer admits files; native checks and composition run as separate SDK actors.
"""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path

from . import artifact_handoff_v1 as h, practice_editions as editions, practice_pdf
from .editorial_sources import canonical, digest
from .runtime_identity import code_bytes
from .shared_jobs import BoundJob, require, selected, runtime_contract
from .shared_practices import run_worker

CONTRACT = Path(__file__).with_name("shared-practice-verifier.json")

# Executed only in the pinned private image. Its CLI owns every GIS operation;
# the SDK owns marker validation, paths, leases, supervision and retention.
VERIFY_CODE = r'''
import hashlib, json, os, pathlib, subprocess, sys, yaml
from gacontext_runtime.api import code_identity
from gacontext_runtime.worker import WorkerBinding
config, expected, fingerprint, sdk_code = sys.argv[1:]
assert code_identity() == sdk_code
with WorkerBinding() as binding:
    with binding.open("inputs/consumer/" + config) as stream:
        raw = stream.read(1024 * 1024 + 1)
    assert len(raw) <= 1024 * 1024 and hashlib.sha256(raw).hexdigest() == expected
    spec = yaml.safe_load(raw)
    lease = binding.binding["lease_id"]
    prefix = "results/edition-check/" + fingerprint + "/" + lease
    temporary = "scratch/tmp/edition-check/" + lease
    with binding.open(temporary + "/intent.json", write=True) as stream:
        stream.write(json.dumps({"config": config, "sha256": expected}).encode())
    directory = "/work/" + temporary
    os.environ.update(HOME=directory, TMPDIR=directory)
    request = {"config": config, "config_sha256": expected, "fingerprint": fingerprint, "lease_id": lease}
    with binding.open(prefix + "/request.json", write=True) as stream:
        stream.write(json.dumps(request).encode())
    def call(name, arguments):
        with binding.open(prefix + "/" + name + ".json", write=True) as output, binding.open(prefix + "/" + name + ".log", write=True) as log:
            result = subprocess.run([sys.executable, "-I", "-B", "-m", "veure_qgis_mcp.cli", *arguments],
                                    stdout=output, stderr=log, cwd=directory, timeout=120)
        assert result.returncode == 0, name
        with binding.open(prefix + "/" + name + ".json") as stream:
            response = stream.read(2 * 1024 * 1024 + 1)
        assert len(response) <= 2 * 1024 * 1024
        value = json.loads(response)
        assert value.get("ok") is True, name
        return value
    schema = call("schema", ["practice-schema", "--profile", spec["gis"]["profile"]])
    reports = {}
    for who in ("alumnat", "docent"):
        args = ["practice-check", "--workspace", "/work/inputs/consumer", "--path", spec["gis"]["bundle"], "--sha256", spec["gis"]["sha256"]]
        for identifier in spec["selection"][who]:
            args += ["--select", identifier]
        reports[who] = call(who, args)
    with binding.open(prefix + "/report.json", write=True) as stream:
        stream.write(json.dumps({"request": request, "schema": schema, "reports": reports}, sort_keys=True).encode())
'''.strip()


def verifier_contract():
    value = h.parse_json(code_bytes(CONTRACT))
    require(value["kind"] == "unaltraweb-shared-practice-verifier" and value["schema_version"] == 1
            and value["profile"] == "qgis-practice-v3" and value["implicit_prepare"] is False
            and value["public_web_contains_provider_package"] is False
            and value["sdk_code_sha256"] == runtime_contract()["code_sha256"], "Invalid shared verifier contract")
    return value


def verifier_pin(contract):
    provider = contract["provider"]
    return {"origin": "prepared-image", "package": provider["name"], "version": provider["version"],
            "revision": provider["installed_revision"], "image_id": contract["image_id"], "schema_sha256": contract["schema_sha256"]}


def module_hashes():
    root = Path(__file__).parent
    return {name: digest(code_bytes(root / name)) for name in (
        "shared_editions.py", "shared_edition_worker.py", "shared_practice_worker.py",
        "practice_editions.py", "practice-edition-v1.schema.json", "shared-practice-verifier.json")}


def check_inputs(project, inputs):
    """Stream opaque GIS bytes; do not impose the reading-image RAM budget on GIS."""
    with closing(h.Workspace(str(project))) as workspace:
        for path, expected in inputs.items():
            try:
                actual, size, _ = workspace.read(path, h.MAX_FILE_BYTES)
            except FileNotFoundError:
                require(expected is None, "A selected edition input disappeared: " + path)
                continue
            require(expected is not None and type(expected["bytes"]) is int and (actual, size) == (expected["sha256"], expected["bytes"]),
                    "Edition input changed: " + path, "shared-input-changed")
        workspace.recheck()


def plan(project, factory, config, pdf_image, *, snapshot=False):
    project, factory = Path(project), Path(factory)
    spec, config_sha, site = editions.load_config(project, config)
    editions.privacy_preflight(project, config, spec, site, snapshot=snapshot)
    contract = verifier_contract()
    require(spec["gis"].get("profile") == contract["profile"] and spec["gis"]["verifier"] == verifier_pin(contract),
            "Edition requires the exact selected shared QGIS v3 verifier")
    with closing(h.Workspace(str(project))) as workspace:
        manifest, _, inventory = h.Verifier(workspace).bundle(spec["gis"]["bundle"], spec["gis"]["sha256"])
        require(manifest["producer"]["name"] == contract["provider"]["name"] and not manifest["dependencies"],
                "Shared edition currently requires one complete leaf QGIS bundle")
        base = Path(spec["gis"]["bundle"]).parent
        auxiliary = editions.author_resources(workspace, spec.get("resources", []))
        inputs = {(base / row["path"]).as_posix(): {"sha256": row["sha256"], "bytes": row["bytes"]} for row in manifest["files"]}
        def include(path, expected=None):
            if path in inputs and inputs[path] is not None:
                require(expected is None or inputs[path]["sha256"] == expected, "Edition input hash differs: " + path)
                return
            actual, size, _ = workspace.read(path, h.MAX_FILE_BYTES)
            require(expected is None or actual == expected, "Edition input hash differs: " + path)
            inputs[path] = {"sha256": actual, "bytes": size}
        include(spec["gis"]["bundle"], spec["gis"]["sha256"])
        include(config, config_sha)
        require(inputs[config]["bytes"] <= 1024 * 1024, "Edition configuration exceeds its metadata budget")
        include("_config.yml")
        # Broad preparation discovers only declared author reading resources.
        # Actual recipient closure/restrictions are checked by the edition worker
        # against fresh private CLI reports before any PDF or ZIP is constructed.
        all_products = {row["id"]: (base / row["path"]).as_posix() for row in manifest["files"]}
        all_targets = {all_products[row["id"]]: {"destination": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]}
                       for row in manifest["files"] if row["kind"] == "output"}
        factory_inputs = {}
        for who in editions.RECIPIENTS:
            reading = spec["readings"][who]
            include(reading["source"], reading["approved_sha256"])
            targets = {**all_targets, **{row["source"]: {key: row[key] for key in ("destination", "sha256", "bytes")} for row in auxiliary[who]}}
            prepared = practice_pdf.prepare(project, factory, reading["source"], spec["version"], pdf_image,
                portable_targets=targets, bindings=reading.get("bindings", []), products=all_products)
            for name, expected in prepared["original_inputs"].items():
                if expected is None:
                    inputs.setdefault(name, None)
                else:
                    include(name, expected)
            for row in auxiliary[who]:
                include(row["source"], row["sha256"])
            factory_inputs.update(prepared["factory_inputs"])
        workspace.recheck()
    require(len(inputs) <= 9000 and sum(row["bytes"] for row in inputs.values() if row) <= h.MAX_TOTAL_BYTES,
            "Edition input inventory exceeds the shared profile budget")
    value = {"schema_version": 1, "kind": "unaltraweb-shared-edition-request", "config": config, "config_sha256": config_sha,
             "spec": spec, "inputs": inputs, "factory_inputs": factory_inputs, "modules": module_hashes(),
             "pdf_image": pdf_image, "verifier": contract}
    require(len(canonical(value)) <= 2 * 1024 * 1024, "Edition request metadata exceeds its budget")
    return {**value, "fingerprint": digest(canonical(value))}


def validated_selection(project, request, verification):
    """Reuse Web approval/recipient/closure rules without parsing GIS formats."""
    spec, contract = request["spec"], request["verifier"]
    observed = verification["schema"]
    package = observed.get("installed_package", {})
    require(observed.get("ok") is True and observed.get("profile") == contract["profile"]
            and observed.get("schema_sha256") == contract["schema_sha256"]
            and package.get("name") == contract["provider"]["name"]
            and package.get("version") == contract["provider"]["version"]
            and package.get("revision") == contract["provider"]["installed_revision"], "Private native verifier identity differs")
    require(verification["request"]["config_sha256"] == request["config_sha256"]
            and verification["request"]["fingerprint"] == request["fingerprint"], "Verifier checked another edition request")
    with closing(h.Workspace(str(project))) as workspace:
        manifest, _, _ = h.Verifier(workspace).bundle(spec["gis"]["bundle"], spec["gis"]["sha256"])
        auxiliary = editions.author_resources(workspace, spec.get("resources", []))
        base = Path(spec["gis"]["bundle"]).parent
        known = {(base / row["path"]).as_posix() for row in manifest["files"]}
        known.update(row["source"] for rows in auxiliary.values() for row in rows)
        result = {}
        for who in editions.RECIPIENTS:
            report = verification["reports"][who]
            require(report.get("ok") is True and report.get("bundle", {}).get("sha256") == spec["gis"]["sha256"]
                    and report.get("bundle", {}).get("path") == spec["gis"]["bundle"]
                    and report.get("producer") == manifest["producer"], "Native verifier checked another GIS bundle/producer")
            rows = editions.validate_closure(report, manifest, spec["selection"][who], who,
                spec["gis"].get("teacher_only", []), profile=contract["profile"])
            if who == "alumnat":
                selected_ids = {row["id"] for row in rows}
                for container in report.get("native", {}).get("containers", []):
                    if container.get("file") in selected_ids:
                        require(all(member.get("role") not in editions.TEACHER_ROLES for member in container.get("members", [])),
                                "Student selection reaches a producer-declared resolved container member")
            targets = [{"source": (base / row["path"]).as_posix(), "destination": row["path"],
                        "sha256": row["sha256"], "bytes": row["bytes"], "id": row["id"], "role": row["role"]} for row in rows] + auxiliary[who]
            portable = {row["source"]: {key: row[key] for key in ("destination", "sha256", "bytes")} for row in targets}
            require(len(portable) == len(targets), "Portable source mapping is ambiguous")
            result[who] = {"closure": rows, "files": targets, "preparation": {
                "portable_targets": portable, "bindings": spec["readings"][who].get("bindings", []),
                "products": {row["id"]: (base / row["path"]).as_posix() for row in rows}, "restricted": sorted(known - portable.keys())}}
        workspace.recheck()
    return result


def compose(project, factory, config, *, dry_run=False):
    context = selected(project)
    contract = verifier_contract()
    require(context is not None and context.get("edition_verifier_image") == contract["image_id"],
            "Select the prepared shared edition verifier explicitly; no legacy fallback", "shared-edition-unconfigured")
    job = BoundJob(context)
    job.verify_service()
    request = plan(project, factory, config, context["pdf_image"])
    status = job.status()
    require(status.get("ok") and status["state"]["daemon_id"] == context["daemon_id"], "Shared edition job/daemon is unavailable")
    path = "exports/edition-" + request["fingerprint"] + "/bundle.json"
    response = {"ok": True, "publishes": False, "storage_runtime": "gacontext-runtime", "dry_run": dry_run,
                "fingerprint": request["fingerprint"], "job_id": context["job_id"], "config_sha256": request["config_sha256"],
                "input_files": len(request["inputs"]), "input_bytes": sum(row["bytes"] for row in request["inputs"].values() if row),
                "verifier": contract, "delivery": "pending explicit whole-snapshot receiver delivery"}
    seals = [row for row in status["seals"] if row["path"] == path]
    if seals:
        require(len(seals) == 1, "Ambiguous edition product")
        check_inputs(project, request["inputs"])
        return {**response, "state": "current", "product": seals[0], "reused": True}
    if dry_run:
        return {**response, "state": "planned", "native_selection_verified": False, "retained_bundle": path}
    require(status["state"]["phase"] == "open", "Selected edition job is not open")
    for name, record in request["inputs"].items():
        if record is None:
            continue
        state = job.status()
        require(state.get("ok"), "Cannot obtain edition input CAS")
        result = job.client.input_file(job.workspace, context["job_id"], context["owner_id"], name, "inputs/consumer/" + name,
            expected_sha256=record["sha256"], expected_bytes=record["bytes"],
            expected_revision=state["state"]["revision"], expected_epoch=state["state"]["epoch"])
        if not result.get("ok"):
            return {**response, "ok": False, "input_admission": result}
    check_inputs(project, request["inputs"])
    checked = run_worker(job, context, contract["image_id"], ["python3", "-I", "-B", "-c", VERIFY_CODE,
        config, request["config_sha256"], request["fingerprint"], contract["sdk_code_sha256"]])
    if not checked["ok"]:
        return {**response, **checked, "stage": "private-native-verification"}
    report = "results/edition-check/" + request["fingerprint"] + "/" + checked["worker"]["lease_id"] + "/report.json"
    built = run_worker(job, context, context["pdf_image"], ["python3", "-I", "-B", "-m", "unaltraweb_mcp.shared_edition_worker",
        "--config", config, "--fingerprint", request["fingerprint"], "--image", context["pdf_image"], "--verification", report,
        "--verifier-worker", canonical(checked["worker"]).decode()])
    if not built["ok"]:
        return {**response, **built, "stage": "web-composition", "verifier_worker": checked["worker"]}
    check_inputs(project, request["inputs"])
    practice_pdf._unchanged(Path(factory), request["factory_inputs"])
    require(module_hashes() == request["modules"], "Edition adapter code changed during composition")
    sealed = job.transition("seal")
    if not sealed.get("ok"):
        return {**response, "ok": False, "seal": sealed}
    product, = [row for row in sealed["seals"] if row["path"] == path]
    return {**response, "state": "sealed", "reused": False, "product": product,
            "verifier_worker": checked["worker"], "worker": built["worker"], "storage": sealed}


def checked_request(project, request):
    """Bind retained request projections to the actual approved consumer sources."""
    require(request["kind"] == "unaltraweb-shared-edition-request" and type(request["schema_version"]) is int
            and request["schema_version"] == 1, "Invalid retained edition request")
    require(digest(canonical({key: item for key, item in request.items() if key != "fingerprint"})) == request["fingerprint"],
            "Retained request fingerprint differs")
    spec, config_sha, site = editions.load_config(project, request["config"])
    require(spec == request["spec"] and config_sha == request["config_sha256"], "Retained edition spec differs from its original configuration")
    editions.privacy_preflight(project, request["config"], spec, site, snapshot=True)
    check_inputs(project, request["inputs"])
    for who in editions.RECIPIENTS:
        reading = spec["readings"][who]
        record = request["inputs"].get(reading["source"])
        require(isinstance(record, dict) and record.get("sha256") == reading["approved_sha256"], "Retained reading is not the approved source")


def verify_product(root, path, sha256):
    """Verify the native edition and each exact ZIP/PDF against retained inputs."""
    import zipfile
    from pypdf import PdfReader
    root = Path(root)
    base = Path(path).parent
    with closing(h.Workspace(str(root))) as workspace:
        native_bundle, _, _ = h.Verifier(workspace).bundle(path, sha256)
        def document(relative, limit=4 * 1024 * 1024):
            _, _, raw = workspace.read(relative, limit, collect=True)
            return h.parse_json(raw)
        request = document((base / "payload/request.json").as_posix())
        value = document((base / "payload/edition.json").as_posix())
        verification = document((base / "payload/verification.json").as_posix())
        fingerprint = request["fingerprint"]
        require(value["kind"] == "unaltraweb-shared-practice-edition" and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["fingerprint"] == fingerprint,
                "Edition request/receipt fingerprint differs")
        checked_request(root / "inputs/consumer", request)
        require(native_bundle["producer"]["name"] == "unaltraweb"
                and native_bundle["producer"]["revision"] == "sha256:" + digest(canonical(request["modules"])), "Edition producer controls differ")
        for name, expected in request["modules"].items():
            actual, _, _ = workspace.read((base / "payload/controls" / h.safe_path(name)).as_posix(), 2 * 1024 * 1024)
            require(actual == expected, "Retained edition control code differs from the request")
        require(set(value["packages"]) == set(value["readings"]) == set(editions.RECIPIENTS), "Edition recipients differ")
        selection = validated_selection(root / "inputs/consumer", request, verification)
        verified = {}
        for who in editions.RECIPIENTS:
            package, reading = value["packages"][who], value["readings"][who]
            manifest, _, _ = h.Verifier(workspace).bundle(reading["bundle"], reading["bundle_sha256"])
            reading_base = Path(reading["bundle"]).parent
            document_row, = [row for row in manifest["files"] if row["kind"] == "output" and row["role"] == "document"]
            require(reading["pdf"] == (reading_base / document_row["path"]).as_posix()
                    and (reading["pdf_sha256"], reading["pdf_bytes"]) == (document_row["sha256"], document_row["bytes"]),
                    "Reading PDF does not match its native bundle document")
            original = document((reading_base / "payload/request.json").as_posix())
            links = document((reading_base / "payload/controls/portable-links.json").as_posix())
            require(reading["portable_links"] == links, "Reading resource mapping differs from its sealed controls")
            require(original["fingerprint"] == reading["fingerprint"] and original["source"] == request["spec"]["readings"][who]["source"]
                    and original["version"] == request["spec"]["version"] and original["image_id"] == request["pdf_image"]
                    and original.get("preparation") == selection[who]["preparation"], "Reading seal does not match its recipient inputs")
            for source, expected in original["original_inputs"].items():
                selected_input = request["inputs"].get(source)
                require(source in request["inputs"] and (selected_input["sha256"] if selected_input else None) == expected,
                        "Reading has an unretained or changed original")
            receipt_path = (base / "payload/delivery" / h.safe_path(package["receipt"]["path"])).as_posix()
            observed, _, raw = workspace.read(receipt_path, 4 * 1024 * 1024, collect=True)
            require(observed == package["receipt"]["sha256"], "Recipient receipt differs")
            receipt = h.parse_json(raw)
            require(receipt["recipient"] == who and receipt["fingerprint"] == fingerprint and receipt["reading"] == reading
                    and receipt["closure"] == selection[who]["closure"]
                    and receipt["pdf"] == package["pdf"] and receipt["zip"] == package["zip"], "Recipient receipt selection differs")
            rows = receipt["files"]
            documents = [row for row in rows if row["role"] == "reading"]
            require(len(documents) == 1 and documents[0]["source"] == reading["pdf"]
                    and documents[0]["sha256"] == reading["pdf_sha256"] and documents[0]["bytes"] == reading["pdf_bytes"]
                    and documents[0]["destination"] == practice_pdf.BASENAMES[request["spec"]["language"]] + ".pdf",
                    "ZIP reading differs from the native PDF seal")
            expected_gis = {(row["source"], row["destination"], row["sha256"], row["bytes"]) for row in selection[who]["files"]}
            received_gis = {(row["source"].removeprefix("inputs/consumer/"), row["destination"], row["sha256"], row["bytes"])
                            for row in rows if row["role"] not in {"reading", "reading-resource"}}
            require(expected_gis == received_gis and len(rows) <= 10000
                    and sum(row["bytes"] for row in rows) <= h.MAX_TOTAL_BYTES, "ZIP selection differs or exceeds its budget")
            h.unique_paths([row["destination"] for row in rows])
            for row in rows:
                observed, size, _ = workspace.read(row["source"], h.MAX_FILE_BYTES)
                require((observed, size) == (row["sha256"], row["bytes"]), "ZIP source differs from retained bytes")
                if row["role"] == "reading-resource":
                    expected = reading["portable_links"]["targets"].get(row["source"].removeprefix("inputs/consumer/"))
                    require(expected is not None and all(row[key] == expected[key] for key in ("destination", "sha256", "bytes")),
                            "Unexpected reading resource in the ZIP")
            pdf_path = (base / "payload/delivery" / h.safe_path(package["pdf"]["path"])).as_posix()
            zip_path = (base / "payload/delivery" / h.safe_path(package["zip"]["path"])).as_posix()
            for relative, record in ((pdf_path, package["pdf"]), (zip_path, package["zip"])):
                actual, size, _ = workspace.read(relative, h.MAX_FILE_BYTES)
                require((actual, size) == (record["sha256"], record["bytes"]), "PDF/ZIP delivery differs")
            require(package["pdf"]["sha256"] == reading["pdf_sha256"], "Independent PDF differs from the reading seal")
            pages = PdfReader(root / pdf_path).pages
            require(pages and all(float(page.mediabox.width) > float(page.mediabox.height) for page in pages), "Edition reading is not landscape")
            with zipfile.ZipFile(root / zip_path) as archive:
                require(len(archive.namelist()) == len(rows) and set(archive.namelist()) == {row["destination"] for row in rows}, "ZIP inventory differs")
                for row in rows:
                    require(archive.getinfo(row["destination"]).file_size == row["bytes"], "ZIP member size differs")
                    import hashlib
                    hashed, length = hashlib.sha256(), 0
                    with archive.open(row["destination"]) as stream:
                        while chunk := stream.read(65536):
                            length += len(chunk)
                            require(length <= row["bytes"], "ZIP member exceeds its declared bound")
                            hashed.update(chunk)
                    require(hashed.hexdigest() == row["sha256"], "ZIP member differs from selected bytes")
            verified[who] = {"pdf": str(root / pdf_path), "zip": str(root / zip_path), "pages": len(pages),
                             "pdf_sha256": package["pdf"]["sha256"], "zip_sha256": package["zip"]["sha256"], "files": len(rows)}
        workspace.recheck()
    return {"ok": True, "fingerprint": fingerprint, "packages": verified, "native_integration_verified": True,
            "teaching_approval": False, "publishes": False}


def verify_delivered_edition(receiver, retention, product):
    relative = h.safe_path(retention["destination"]["path"])
    return verify_product(Path(receiver) / relative / "payload/files", product["path"], product["bundle_sha256"])
