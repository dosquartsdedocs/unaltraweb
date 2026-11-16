"""Private-only local admission of explicitly pinned retained paired outputs.

No renderer, scientific/native provider, credential, transport or catalogue call.
Original bytes and unresolved/inherited claims remain distinct from fresh checks.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid
import zipfile

from . import __version__, artifact_handoff_v1 as h, manual_pdf_preview as fs
from .artifact_publication import canonical, consumer_repository, digest, require, shape
from .editorial_sources import yaml_mapping
from .manual_release import _install_new_directory

SCHEMA = Path(__file__).with_name("retained-private-intake-v1.schema.json")
ROOT = "sandbox/retained-handoffs"
KIND = "unaltraweb-retained-private-artifact-receipt"
MAX_METADATA = 1024**2
PRIVATE_INPUTS = ("dist/practiques/", "sandbox/", "context/", "tmp/")
VALIDATION = {"raw_bytes_and_references": "checked", "zip_member_content_hashes": "freshly-checked-without-extraction",
              "pdf_structure": "not-revalidated; original worker-bound bytes/header checked", "native_scientific": "not-performed", "author_approval": "not-granted"}
LOCAL_REFS = {"reading_source", "reading_sha256", "pdf_receipt", "pdf_receipt_sha256"}
ERRORS = {
    "retained-manifest-format": "Unsupported or incomplete original retained-manifest family",
    "retained-archive-reference": "Original archive/file names or archive hashes conflict with the exact selection",
    "retained-reading-ambiguous": "The selected original reading reference is missing or ambiguous",
    "retained-reading-reference": "Original reading PDF/job references differ from the selected worker output",
    "retained-recipient-mismatch": "Original reading role/audience differs from the selected recipient",
    "retained-language-mismatch": "Original reading language differs from the selected handoff language",
    "retained-worker-reference": "Original worker receipt path/hash or provenance metadata differs",
    "retained-source-reference": "Original worker/source hash references differ from the selected reading",
    "retained-output-reference": "Selected PDF differs from original worker output seal or ZIP reading reference",
    "retained-input-changed": "Retained input differs from its exact reviewed SHA-256/size pin",
    "retained-admission-lineage": "Retained original reference/declaration lineage differs from its original evidence",
    "retained-reading-hash-reference": "Original reading hash matches neither or ambiguously matches the independently bound PDF/source bytes",
}


class RetainedIntakeError(ValueError):
    """Fixed safe diagnostics; original opaque data never enters the message."""
    def __init__(self, code):
        self.code = code
        super().__init__(ERRORS[code])


def guard(condition, code):
    if not condition:
        raise RetainedIntakeError(code)


@contextmanager
def opened(workspace, path):
    with workspace.directory(str(Path(path).parent) if Path(path).parent != Path(".") else "") as parent:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and h.signature(before) == workspace.snapshots[path],
                    "Retained input differs from its pinned descriptor identity")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                yield stream
            require(h.signature(before) == h.signature(os.fstat(fd))
                    == h.signature(os.stat(Path(path).name, dir_fd=parent, follow_symlinks=False)), "Retained input changed during inspection")
        finally:
            os.close(fd)


def pin(workspace, row, *, collect=False, limit=h.MAX_FILE_BYTES):
    h.safe_path(row["path"])
    actual, size, raw = workspace.read(row["path"], limit, collect=collect)
    guard(type(row["bytes"]) is int and (actual, size) == (row["sha256"], row["bytes"]), "retained-input-changed")
    return raw


def claims(manifest, evidence):
    flags = {key: manifest.get(key) for key in ("human_approved", "exact_historical_bundle", "local_candidate")}
    if "publishes" in manifest:
        flags["publishes"] = manifest["publishes"]
    require(all(type(value) is bool or value is None for value in flags.values()), "Invalid inherited editorial/provenance status")
    refs = {}
    for field in ("proof", "moodle_statement"):
        path, sha = manifest.get(field), manifest.get(field + "_sha256")
        require(sha is None or isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "Invalid inherited evidence hash")
        refs[field] = {"path": path, "sha256": sha,
                       "state": "selected-matching-bytes" if path is not None and any(row["file"]["path"] == path and row["file"]["sha256"] == sha for row in evidence)
                       else "inherited-unresolved" if path is not None or sha is not None else "not-declared"}
    return {**flags, "approval_origin": "original-manifest", "approved_by_intake": False,
            "native_scientific_validation": "not-performed", "inherited_claims_recertified": False, "references": refs}


def handoff_identity(request, manifest):
    # An explicit new snapshot run is never invented historical provenance.
    return {**request["handoff"], "version": manifest["version"], **({"run": manifest["run"]} if "run" in manifest else {})}


def declarations(manifest):
    return {key: {"present": key in manifest, "value": manifest.get(key)}
            for key in ("run", "human_approved", "local_candidate", "exact_historical_bundle", "publishes")}


def reference_family(original, manifest):
    if "reading_receipt" in original:
        guard("archive" in original and any(key in original for key in ("reading_receipt_sha256", "receipt_sha256", "pdf_receipt_sha256")), "retained-manifest-format")
        return "package-reading-receipt-v1"
    if LOCAL_REFS.intersection(original):
        guard(LOCAL_REFS <= original.keys() and "archive" in original, "retained-manifest-format")
        return "package-local-reading-v1"
    guard("file" in original and isinstance(manifest.get("reading_receipts"), list)
          and 1 <= len(manifest["reading_receipts"]) <= 256, "retained-manifest-format")
    return "file-root-reading-receipts-v1"


def recipient(original):
    fields = [key for key in ("recipient", "role") if key in original]
    guard(bool(fields) and isinstance(original[fields[0]], str) and original[fields[0]] in {"alumnat", "docent"}
          and all(original[key] == original[fields[0]] for key in fields), "retained-recipient-mismatch")
    return original[fields[0]]


def worker_fields(original, item):
    fields = {}
    for label, names, expected in (("path", ("pdf_receipt", "reading_receipt"), item["pdf_receipt"]["path"]),
                                  ("sha256", ("pdf_receipt_sha256", "reading_receipt_sha256", "receipt_sha256"), item["pdf_receipt"]["sha256"])):
        present = [key for key in names if key in original]
        guard(bool(present) and all(original[key] == expected for key in present), "retained-worker-reference")
        fields[label] = present
    return fields


def specification(request, manifest):
    guard(isinstance(manifest, dict) and {"activity", "version", "packages"} <= manifest.keys(), "retained-manifest-format")
    require(manifest["activity"] == request["handoff"]["activity"], "Declared activity differs; handoff/activity aliases must be explicit")
    guard(all(isinstance(manifest[key], str) and 0 < len(manifest[key]) <= 200 for key in ("activity", "version"))
          and ("run" not in manifest or manifest["run"] is None or isinstance(manifest["run"], str) and 0 < len(manifest["run"]) <= 200),
          "retained-manifest-format")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", manifest["version"]), "Original version is not an exportable identity label; never normalise it silently")
    packages = manifest["packages"]
    require(isinstance(packages, list) and 1 <= len(packages) <= 2 and all(isinstance(row, dict) for row in packages), "Invalid original recipient package list")
    by_who = {recipient(row): row for row in packages}
    require(len(by_who) == len(packages) and set(by_who) <= {"alumnat", "docent"}, "Conflicting original recipient assignments")
    require(len({row["recipient"] for row in request["packages"]}) == len(request["packages"]), "Duplicate requested recipient")
    base = Path(request["handoff"]["manifest"]["path"]).parent
    require(base == Path("dist/practiques") / request["handoff"]["slug"] / request["handoff"]["language"], "Select the explicit flat handoff slug/language path")
    outputs, dependencies = [], []
    for item in request["packages"]:
        original = by_who.get(item["recipient"])
        guard(original is not None and {"sha256", "members"} <= original.keys(), "retained-manifest-format")
        family = reference_family(original, manifest)
        aliases = [original[key] for key in ("archive", "file") if key in original]
        guard(aliases and all(name == Path(item["archive"]["path"]).name for name in aliases)
              and item["archive"]["sha256"] == original["sha256"], "retained-archive-reference")
        for key, suffix in (("archive", ".zip"), ("pdf", ".pdf")):
            row = item[key]
            h.safe_path(row["path"])
            require(Path(row["path"]).parent == base and row["path"].endswith(suffix), "Selected output is outside the retained handoff or has the wrong format")
            dependencies.append(row["path"])
        if family in {"package-local-reading-v1", "package-reading-receipt-v1"}:
            worker_fields(original, item)
        h.safe_path(item["pdf_artifact"])
        h.safe_path(item["reading_member"])
        guard(item["pdf_artifact"].startswith("outputs/") and item["pdf_artifact"].endswith(".pdf")
              and isinstance(original["members"], dict) and original["members"].get(item["reading_member"]) == item["pdf"]["sha256"], "retained-output-reference")
        require(len({row["format"] for row in item["selected"]}) == len(item["selected"]), "Duplicate selected output format")
        for selected in item["selected"]:
            row = item["pdf" if selected["format"] == "pdf" else "archive"]
            outputs.append({"id": selected["id"], "recipient": item["recipient"], "format": selected["format"], **row})
    h.unique_paths(dependencies)
    require(len({row["id"] for row in outputs}) == len(outputs), "Duplicate selected output ID")
    h.unique_paths([Path(row["path"]).name for row in outputs])
    return outputs, by_who


def worker_receipt(raw, item, original, *, manifest, language):
    value = h.parse_json(raw)
    guard(type(value.get("schema_version")) is int and value["schema_version"] == 1 and value.get("kind") == "private-practice-pdf"
          and all(isinstance(value.get(key), dict) for key in ("renderer", "effective_source", "factory_inputs", "original_inputs")), "retained-worker-reference")
    family = reference_family(original, manifest)
    package_pointer = "/packages/" + str(next(index for index, row in enumerate(manifest["packages"]) if row is original))
    additions = {}
    if family in {"package-local-reading-v1", "package-reading-receipt-v1"}:
        fields = worker_fields(original, item)
        reading_pointer, source = package_pointer, original.get("reading_source", value.get("source"))
        source_sha = value["original_inputs"].get(source) if isinstance(source, str) else None
        source_origin = {"document": "original-worker-receipt", "sha256": item["pdf_receipt"]["sha256"],
                         "pointer": "/original_inputs/" + source.replace("~", "~0").replace("/", "~1") if isinstance(source, str) else None}
        worker_origin = package_pointer + "/" + fields["path"][0]
        declared_hash = original.get("reading_sha256")
        meaning = "not-declared"
        if "reading_sha256" in original:
            is_source = isinstance(source_sha, str) and declared_hash == source_sha
            is_pdf = declared_hash == item["pdf"]["sha256"]
            guard(is_source != is_pdf, "retained-reading-hash-reference")
            meaning = "markdown-source" if is_source else "delivered-pdf"
            if is_source and family == "package-local-reading-v1":
                # Preserve the original supported projection exactly, including
                # its manifest source-hash origin, for old receipts/stages.
                source_origin = {"document": "original-manifest", "pointer": package_pointer + "/reading_sha256"}
            elif is_pdf and family == "package-local-reading-v1":
                family = "package-local-pdf-reading-v1"
        if family == "package-local-reading-v1" and "recipient" not in original:
            family = "package-local-role-v1"
        if family != "package-local-reading-v1":
            additions = {"original_field_origins": {
                "recipient": [package_pointer + "/" + key for key in ("recipient", "role") if key in original],
                "worker_path": [package_pointer + "/" + key for key in fields["path"]],
                "worker_sha256": [package_pointer + "/" + key for key in fields["sha256"]],
                "source": {"document": "original-manifest", "pointer": package_pointer + "/reading_source"} if "reading_source" in original
                          else {"document": "original-worker-receipt", "sha256": item["pdf_receipt"]["sha256"], "pointer": "/source"},
                "reading_hash": {"present": "reading_sha256" in original, "value": declared_hash,
                                 "pointer": package_pointer + "/reading_sha256" if "reading_sha256" in original else None, "semantics": meaning}},
                "delivered_pdf_sha256": item["pdf"]["sha256"], "delivered_pdf_origin": {"document": "original-worker-receipt", "sha256": item["pdf_receipt"]["sha256"], "pointer": "/artifacts/" + item["pdf_artifact"].replace("~", "~0").replace("/", "~1")}}
    else:
        pdf_path = (Path(item["pdf_receipt"]["path"]).parent / item["pdf_artifact"]).as_posix()
        # Only selected exact path anchors are authority. Other/case rows remain
        # opaque original data, never audiences or file/command instructions.
        matches = [(index, row) for index, row in enumerate(manifest["reading_receipts"]) if isinstance(row, dict)
                   and (row.get("receipt") == item["pdf_receipt"]["path"] or row.get("pdf") == pdf_path)]
        guard(len(matches) == 1, "retained-reading-ambiguous")
        index, reading = matches[0]
        guard(reading.get("role") == reading.get("audience") == item["recipient"], "retained-recipient-mismatch")
        guard(reading.get("language") == language, "retained-language-mismatch")
        guard(reading.get("receipt") == item["pdf_receipt"]["path"] and reading.get("receipt_sha256") == item["pdf_receipt"]["sha256"], "retained-worker-reference")
        guard(reading.get("pdf") == pdf_path and reading.get("pdf_sha256") == item["pdf"]["sha256"]
              and ("job" not in reading or reading["job"] == str(Path(item["pdf_receipt"]["path"]).parent)), "retained-reading-reference")
        reading_pointer, source = "/reading_receipts/" + str(index), reading.get("source")
        source_sha = value["original_inputs"].get(source) if isinstance(source, str) else None
        source_origin = {"document": "original-worker-receipt", "sha256": item["pdf_receipt"]["sha256"],
                         "pointer": "/original_inputs/" + source.replace("~", "~0").replace("/", "~1") if isinstance(source, str) else None}
        worker_origin = reading_pointer + "/receipt"
    guard(isinstance(source, str) and source and isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{64}", source_sha)
          and value.get("source") == source and value["original_inputs"].get(source) == source_sha, "retained-source-reference")
    guard(isinstance(value.get("artifacts"), dict) and value["artifacts"].get(item["pdf_artifact"]) == item["pdf"]["sha256"], "retained-output-reference")
    references = {"family": family, "package_pointer": package_pointer, "archive_fields": [key for key in ("archive", "file") if key in original],
                  "reading_pointer": reading_pointer, "source": source, "source_sha256": source_sha, "source_sha256_origin": source_origin,
                  "worker_reference_origin": worker_origin, "worker_receipt": item["pdf_receipt"], "pdf_artifact": item["pdf_artifact"],
                  "reading_member": item["reading_member"], "recipient": item["recipient"], "language": language, **additions}
    return {"receipt_bytes": "checked", "selected_pdf_and_source_references": "checked", "renderer_effective_source_factory_claims": "inherited-not-reexecuted"}, references


def copies_for(request, request_pin, outputs):
    rows = [{"source": request_pin["path"], "path": "local/request/" + Path(request_pin["path"]).name,
             "sha256": request_pin["sha256"], "bytes": request_pin["bytes"]},
            {"source": request["handoff"]["manifest"]["path"], "path": "local/manifest/" + Path(request["handoff"]["manifest"]["path"]).name,
             "sha256": request["handoff"]["manifest"]["sha256"], "bytes": request["handoff"]["manifest"]["bytes"]}]
    for item in request["packages"]:
        row = item["pdf_receipt"]
        rows.append({"source": row["path"], "path": "local/worker-" + item["recipient"] + "/" + Path(row["path"]).name,
                     "sha256": row["sha256"], "bytes": row["bytes"]})
    for index, item in enumerate(request["evidence"]):
        row = item["file"]
        rows.append({"source": row["path"], "path": f"local/evidence-{index}/" + Path(row["path"]).name,
                     "sha256": row["sha256"], "bytes": row["bytes"]})
    require(sum(row["bytes"] for row in rows) <= 16 * MAX_METADATA, "Local evidence exceeds its snapshot budget")
    rows.extend({"source": row["path"], "path": "files/" + Path(row["path"]).name, "sha256": row["sha256"], "bytes": row["bytes"]} for row in outputs)
    h.unique_paths([row["path"] for row in rows])
    return rows


def plan(project: Path, request_path: str, sha256: str):
    fs._require_git_root(project)
    tracked, ignored = fs._git_state(project, Path(h.safe_path(request_path)))
    require(tracked and not ignored, "Intake request must be versioned and non-ignored")
    with closing(h.Workspace(str(project))) as workspace:
        actual, size, raw = workspace.read(request_path, MAX_METADATA, collect=True)
        require(actual == sha256, "Intake request differs from its reviewed SHA-256")
        request = h.parse_json(raw)
        shape(request, SCHEMA.name)
        repository = consumer_repository(project, request["consumer_repository"])
        destination = Path(h.safe_path(request["snapshot"]))
        require(destination.as_posix().startswith(ROOT + "/") and len(destination.parts) >= 4, "Snapshot requires a confined retained-handoff run")
        fs._require_generated_path(project, destination, label="Private retained handoff")
        try:
            parent = fs._open_directory(workspace.fd, destination.parent)
        except FileNotFoundError:
            parent = None
        if parent is not None:
            try:
                try:
                    os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("Retained handoff destination exists; admission is create-only")
            finally:
                os.close(parent)
        config_sha, _, config_raw = workspace.read("_config.yml", MAX_METADATA, collect=True)
        site = yaml_mapping(config_raw.decode())
        from .practice_pdf import private_path_issues
        from .practice_editions import check_zip_directory, verify_zip_inventory
        require(site.get("unaltraweb", {}).get("site_profile") == "unaltremanual" and not private_path_issues(site), "Intake requires a private/excluded manual workspace")
        require(request["handoff"]["language"] in (site.get("languages") or [site.get("default_lang") or site.get("lang") or "en"]), "Intake language is not enabled")
        manifest = h.parse_json(pin(workspace, request["handoff"]["manifest"], collect=True, limit=MAX_METADATA))
        outputs, original_packages = specification(request, manifest)
        request_pin = {"path": request_path, "sha256": sha256, "bytes": size}
        copies = copies_for(request, request_pin, outputs)
        reports, references = {}, {}
        for item in request["packages"]:
            pin(workspace, item["archive"])
            pin(workspace, item["pdf"])
            with opened(workspace, item["pdf"]["path"]) as source:
                require(source.read(5) == b"%PDF-", "Original worker-bound PDF has no PDF header")
            require(item["pdf_receipt"]["path"].startswith(PRIVATE_INPUTS) and item["pdf_receipt"]["path"].endswith(".json"), "Select confined local PDF receipt evidence")
            worker = pin(workspace, item["pdf_receipt"], collect=True, limit=MAX_METADATA)
            report, reading = worker_receipt(worker, item, original_packages[item["recipient"]], manifest=manifest, language=request["handoff"]["language"])
            references[item["recipient"]] = reading
            reports[item["recipient"]] = {"worker": report}
            report["reading_source_bytes"] = "fresh-exact-path" if any(row["path"] == reading["source"] and row["sha256"] == reading["source_sha256"] for row in request["sources"]) else "inherited-reference-only"
            with opened(workspace, item["archive"]["path"]) as source:
                check_zip_directory(source)
                with zipfile.ZipFile(source) as archive:
                    reports[item["recipient"]]["zip"] = verify_zip_inventory(archive, original_packages[item["recipient"]]["members"])
        for index, entry in enumerate(request["evidence"]):
            row = entry["file"]
            require(row["path"].startswith(PRIVATE_INPUTS), "Select bounded private handoff evidence, not arbitrary sources")
            require(row["path"].endswith(".json") if entry["role"] != "checksums" else Path(row["path"]).parent == Path(request["handoff"]["manifest"]["path"]).parent,
                    "Evidence must be metadata JSON or the selected handoff checksums")
            content = pin(workspace, row, collect=True, limit=MAX_METADATA)
            if entry["role"] != "checksums":
                h.parse_json(content)
            else:
                sums = {}
                for line in content.decode().splitlines():
                    match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
                    require(match is not None, "Invalid original checksum declaration")
                    name = h.safe_path(match[2])
                    require(name not in sums, "Duplicate checksum declaration")
                    sums[name] = match[1]
                require(all(sums.get(Path(out["path"]).name) == out["sha256"] for out in outputs), "Selected output differs from original checksums")
        readings = {row["source"]: row["source_sha256"] for row in references.values()}
        for row in request["sources"]:
            require(row["path"].startswith(("practiques/", "_practices/", "sandbox/", "tmp/")) and row["path"].endswith((".md", ".markdown")), "Only explicit bounded reading source pins are inspected; sources are not exported")
            pin(workspace, row, limit=2 * MAX_METADATA)
            guard(row["sha256"] in readings.values() and (row["path"] not in readings or row["sha256"] == readings[row["path"]]), "retained-source-reference")
        require(len({row["path"] for row in request["sources"]}) == len(request["sources"]), "Duplicate source pins")
        workspace.recheck()
    from .runtime_identity import fingerprint
    code = fingerprint(Path(__file__).parent)
    require(code["available"], "Intake producer code is not safely observable")
    payload = {"kind": "unaltraweb-retained-private-intake-plan", "schema_version": 1, "purpose": "private-archive",
               "request": request_pin, "specification": request,
               "consumer_repository": repository, "site_config_sha256": config_sha,
               "handoff": handoff_identity(request, manifest),
               "outputs": outputs, "copies": copies, "package_checks": reports, "source_pins": request["sources"],
               "original_references": references, "original_declarations": declarations(manifest),
               "claims": claims(manifest, request["evidence"]), "producer": {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + code["sha256"]},
               "validation": VALIDATION}
    return {"ok": True, "read_only": True, "network": False, "credentials_resolved": False, "publishes": False,
            "plan_sha256": digest(canonical(payload)), "plan": payload}


def output_receipt(snapshot, admission_sha, identifier):
    return {"kind": KIND, "schema_version": 1, "purpose": "private-archive", "output_id": identifier,
            "admission": {"path": snapshot + "/admission.json", "sha256": admission_sha}}


def snapshot(project, request_path, sha256, expected_plan_sha256):
    from .practice_editions import _copy_selected, write_new
    reviewed = plan(project, request_path, sha256)
    require(reviewed["plan_sha256"] == expected_plan_sha256, "Intake plan differs from the reviewed digest")
    payload = reviewed["plan"]
    relative = Path(payload["specification"]["snapshot"])
    admission = {"kind": "unaltraweb-retained-private-handoff-admission", "schema_version": 1,
                 "purpose": "private-archive", "snapshot": relative.as_posix(), "plan_sha256": expected_plan_sha256, "plan": payload}
    content = canonical(admission)
    admission_sha = digest(content)
    receipts = {}
    with closing(h.Workspace(str(project))) as workspace:
        parent = fs._open_directory(workspace.fd, relative.parent, create=True)
        name = ".intake-" + uuid.uuid4().hex
        os.mkdir(name, 0o700, dir_fd=parent)
        directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            for row in payload["copies"]:
                path = Path(row["path"])
                folder = fs._open_directory(directory, path.parent, create=True)
                try:
                    fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=folder)
                    with os.fdopen(fd, "wb") as target:
                        _copy_selected(workspace, row, target)
                        target.flush()
                        os.fsync(target.fileno())
                    os.fsync(folder)
                finally:
                    os.close(folder)
            write_new(directory, "admission.json", content)
            folder = fs._open_directory(directory, Path("receipts"), create=True)
            try:
                for row in payload["outputs"]:
                    raw = canonical(output_receipt(relative.as_posix(), admission_sha, row["id"]))
                    write_new(folder, row["id"] + ".json", raw)
                    receipts[row["id"]] = {"path": relative.as_posix() + "/receipts/" + row["id"] + ".json", "sha256": digest(raw),
                                          "recipient": row["recipient"], "format": row["format"]}
                os.fsync(folder)
            finally:
                os.close(folder)
            require(plan(project, request_path, sha256) == reviewed, "Selected intake inputs changed during snapshot")
            fs._require_generated_path(project, relative, label="Private retained handoff")
            check = fs._open_directory(workspace.fd, relative.parent)
            try:
                require(fs._identity(os.fstat(check)) == fs._identity(os.fstat(parent)), "Intake destination parent changed")
            finally:
                os.close(check)
            os.fsync(directory)
            _install_new_directory(parent, name, relative.name)
            os.fsync(parent)
        finally:
            os.close(directory)
            os.close(parent)
    for row in receipts.values():
        with closing(h.Workspace(str(project))) as workspace:
            artifact(workspace, project, row["path"], row["sha256"])
    return {"ok": True, "publishes": False, "purpose": "private-archive", "snapshot": relative.as_posix(),
            "plan_sha256": expected_plan_sha256, "admission_sha256": admission_sha, "receipts": receipts, "claims": payload["claims"]}


def artifact(workspace, project, path, expected):
    actual, _, raw = workspace.read(path, MAX_METADATA, collect=True)
    require(actual == expected, "Retained artifact receipt differs from its exact pin")
    receipt = h.parse_json(raw)
    require(set(receipt) == {"kind", "schema_version", "purpose", "output_id", "admission"} and receipt["kind"] == KIND
            and type(receipt["schema_version"]) is int and receipt["schema_version"] == 1 and receipt["purpose"] == "private-archive", "Invalid retained private artifact receipt")
    base = Path(path).parent.parent.as_posix()
    require(base.startswith(ROOT + "/") and path == base + "/receipts/" + receipt["output_id"] + ".json"
            and receipt["admission"]["path"] == base + "/admission.json", "Retained artifact receipt escaped its snapshot")
    fs._require_generated_path(project, Path(base), label="Retained private admission")
    group_sha, _, group_raw = workspace.read(base + "/admission.json", 16 * MAX_METADATA, collect=True)
    require(group_sha == receipt["admission"]["sha256"], "Retained admission seal differs")
    group = h.parse_json(group_raw)
    require(group.get("kind") == "unaltraweb-retained-private-handoff-admission" and type(group.get("schema_version")) is int
            and group["schema_version"] == 1 and group.get("purpose") == "private-archive" and group.get("snapshot") == base,
            "Invalid private admission scope")
    payload = group["plan"]
    require(digest(canonical(payload)) == group["plan_sha256"] and payload["purpose"] == "private-archive"
            and payload["specification"]["snapshot"] == base and payload["validation"] == VALIDATION, "Retained admission plan changed")
    shape(payload["specification"], SCHEMA.name)
    inventory = payload["copies"]
    for row in inventory:
        actual, size, _ = workspace.read(base + "/" + h.safe_path(row["path"]), h.MAX_FILE_BYTES)
        require((actual, size) == (row["sha256"], row["bytes"]), "Retained snapshot bytes/evidence changed")
    source_copy = next(row for row in inventory if row["path"].startswith("local/request/"))
    _, _, request_raw = workspace.read(base + "/" + source_copy["path"], MAX_METADATA, collect=True)
    require(h.parse_json(request_raw) == payload["specification"] and digest(request_raw) == payload["request"]["sha256"], "Retained request binding differs")
    manifest_copy = next(row for row in inventory if row["path"].startswith("local/manifest/"))
    _, _, manifest_raw = workspace.read(base + "/" + manifest_copy["path"], MAX_METADATA, collect=True)
    manifest = h.parse_json(manifest_raw)
    outputs, originals = specification(payload["specification"], manifest)
    legacy = "original_references" not in payload and "original_declarations" not in payload
    original_claims = claims(manifest, payload["specification"]["evidence"])
    if legacy:
        # PR134 did not project an original publishes declaration. Keep its
        # immutable receipt/sidecar exactly, even when the raw manifest had one.
        original_claims.pop("publishes", None)
    require(outputs == payload["outputs"] and original_claims == payload["claims"], "Admission role/approval lineage differs from original evidence")
    require(payload["handoff"] == handoff_identity(payload["specification"], manifest), "Admission handoff/activity identity differs from original inputs")
    require(all(payload["consumer_repository"].get(key) == value for key, value in payload["specification"]["consumer_repository"].items()), "Admission repository declaration differs from its request")
    require(inventory == copies_for(payload["specification"], payload["request"], outputs), "Admission copy inventory differs from its exact selected request")
    references = {}
    for item in payload["specification"]["packages"]:
        copied = next(row for row in inventory if row["source"] == item["pdf_receipt"]["path"])
        _, _, raw = workspace.read(base + "/" + copied["path"], MAX_METADATA, collect=True)
        _, references[item["recipient"]] = worker_receipt(raw, item, originals[item["recipient"]], manifest=manifest,
                                                       language=payload["specification"]["handoff"]["language"])
    if not legacy:
        guard(payload.get("original_references") == references and payload.get("original_declarations") == declarations(manifest), "retained-admission-lineage")
    else:
        # Original PR134 admissions have the package-local family and historical
        # run. Their receipt/stage/sidecar identity is not rewritten on upgrade.
        guard(isinstance(manifest.get("run"), str) and all(row["family"] == "package-local-reading-v1" for row in references.values()), "retained-admission-lineage")
    expected_files = {row["path"] for row in inventory} | {"admission.json"}
    for out in outputs:
        filename = "receipts/" + out["id"] + ".json"
        expected_files.add(filename)
        _, _, item_raw = workspace.read(base + "/" + filename, MAX_METADATA, collect=True)
        require(item_raw == canonical(output_receipt(base, group_sha, out["id"])), "Retained output receipt was replaced or relabelled")
    files, _ = workspace.inventory(base)
    require(files == expected_files, "Retained snapshot has neighbouring or unselected files")
    selected = next((row for row in outputs if row["id"] == receipt["output_id"]), None)
    require(selected is not None, "Unknown retained output selection")
    source = base + "/files/" + Path(selected["path"]).name
    require(any(row["path"] == source.removeprefix(base + "/") and row["sha256"] == selected["sha256"] and row["bytes"] == selected["bytes"] for row in inventory), "Selected retained output mapping differs")
    workspace.recheck()
    return {"source": source, "row": {"path": Path(source).name, "sha256": selected["sha256"], "bytes": selected["bytes"]},
            "recipient": selected["recipient"], "format": selected["format"], "handoff": payload["handoff"],
            "consumer_repository": payload["consumer_repository"], "claims": payload["claims"], "validation": payload["validation"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "snapshot"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.operation == "plan":
            require(not args.expected_plan_sha256, "Planning does not apply an admission")
            result = plan(args.project, args.request, args.sha256)
        else:
            require(args.expected_plan_sha256, "Snapshot requires the reviewed expected plan SHA-256")
            result = snapshot(args.project, args.request, args.sha256, args.expected_plan_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except RetainedIntakeError as exc:
        print(json.dumps({"ok": False, "publishes": False, "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError, StopIteration, RuntimeError, h.HandoffError, zipfile.BadZipFile):
        print(json.dumps({"ok": False, "publishes": False, "error": {"code": "retained-intake-refused", "message": "Retained private intake refused; inspect the exact request, pinned bytes and native references"}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
