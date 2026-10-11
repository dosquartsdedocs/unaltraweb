"""Compose two private teaching editions from an opaque, verified GIS producer.

GIS execution, project parsing and closure discovery belong to the installed
producer. This editor consumes its public check result and never filters a
required dependency out of an otherwise accepted selection.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
import posixpath
from pathlib import Path
import stat
import sys
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import uuid
import zipfile

from . import __version__, artifact_handoff_v1 as handoff, manual_pdf_preview as fs, practice_pdf
from .editorial_sources import Reader, canonical, digest, private_practice_identity, yaml_mapping
from .manual_release import _install_new_directory
from .processes import run_process
from .runtime_identity import active_runtime
from .distribution import consumer_integration

SCHEMA = Path(__file__).with_name("practice-edition-v1.schema.json")
RECIPIENTS = ("alumnat", "docent")
CLASSROOM_ROLES = {"initial-data", "initial-project", "resolved-data", "resolved-project", "capture", "capture-original", "annotation"}
PROFILE_ROLES = {"qgis-practice-v1": CLASSROOM_ROLES,
                 "qgis-practice-v2": CLASSROOM_ROLES | {"map-svg", "map-pdf"}}
TEACHER_ROLES = {"resolved-data", "resolved-project"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def schema():
    return handoff.parse_json(SCHEMA.read_bytes())


def load_config(project, config_path):
    handoff.safe_path(config_path)
    with Reader(project) as reader:
        raw = reader.read(config_path)
        document = yaml_mapping(raw.decode("utf-8"))
        site = yaml_mapping(reader.text("_config.yml"))
    rules = schema()
    handoff.check_shape(document, rules, rules["$defs"])
    for value in (document["slug"], document["version"], document["gis"]["bundle"]):
        handoff.safe_path(value)
    for who in RECIPIENTS:
        handoff.safe_path(document["readings"][who]["source"])
        ids = document["selection"][who]
        require(len(ids) == len(set(ids)), "Edition selection has duplicate IDs")
    require(document["readings"]["alumnat"]["source"] != document["readings"]["docent"]["source"], "Each recipient needs its own reading")
    return document, digest(raw), site


def privacy_preflight(project, config_path, spec, site):
    fs._require_git_root(project)
    tracked, ignored = fs._git_state(project, Path(config_path))
    require(tracked and not ignored, "Edition configuration must be a versioned, non-ignored consumer source")
    problems = practice_pdf.private_path_issues(site)
    require(not problems, "; ".join(problems))
    required_roots = {"practiques", "sandbox", "dist"}
    for who in RECIPIENTS:
        source = spec["readings"][who]["source"]
        mapped = private_practice_identity(site, source)
        require(mapped is not None and (mapped["slug"], mapped["lang"], mapped["recipient"]) == (spec["slug"], spec["language"], who),
                "Reading source is not mapped to this exact slug/language/recipient")
        required_roots.add(Path(source).parts[0])
    excluded = {value.rstrip("/") for value in site.get("exclude", []) if isinstance(value, str)}
    require(required_roots <= excluded, "All private practice reading/work/delivery roots must be explicitly excluded from Jekyll")
    included = site.get("include") or []
    import fnmatch
    for value in included:
        if isinstance(value, str):
            require(value != "." and not any(fnmatch.fnmatchcase(root, value.strip("/")) or root.startswith(value.rstrip("/")+"/")
                    or fnmatch.fnmatchcase(root+"/LLEGIU-ME.md", value) or fnmatch.fnmatchcase(root+"/delivery.zip", value)
                    for root in required_roots), "Jekyll include exposes a private practice root")
    fs._require_generated_path(project, Path("sandbox/practiques") / spec["slug"], label="Practice snapshots")
    fs._require_generated_path(project, Path("dist/practiques") / spec["slug"], label="Retained edition delivery")


def provider_command(project, arguments):
    # An operator can select another prepared interpreter; a consumer document
    # cannot supply arbitrary executables, Python imports or command arguments.
    python = os.environ.get("UNALTRAWEB_PRACTICE_QGIS_PYTHON") or sys.executable
    require(Path(python).is_absolute(), "Producer verifier interpreter must be explicitly absolute")
    result = run_process([python, "-I", "-m", "veure_qgis_mcp.cli", *arguments], cwd=project,
                         timeout_seconds=120, output_limit=1024*1024)
    require(not result.returncode and not result.timed_out and not result.stdout_truncated and not result.stderr_truncated,
            "Installed QGIS verifier refused the bundle/selection: " + (result.stderr or result.stdout)[-3000:])
    value = handoff.parse_json(result.stdout.encode())
    require(value.get("ok") is True, "Installed QGIS verifier did not certify this operation")
    return value


def verifier_identity(project, expected, profile="qgis-practice-v1"):
    require(profile in PROFILE_ROLES, "Unsupported selected GIS profile")
    # Legacy rc1's public default is v1 and has no --profile option. V2 always
    # requests its explicit schema; it must never be validated with a v1 pin.
    arguments = ["practice-schema"] + (["--profile", profile] if profile != "qgis-practice-v1" else [])
    observed = provider_command(project, arguments)
    package = observed.get("installed_package") or {}
    require(observed.get("profile") == profile and observed.get("schema_sha256") == expected["schema_sha256"]
            and all(package.get(key) == expected[key if key != "name" else "package"] for key in ("name", "version", "revision")),
            "Installed QGIS verifier identity/schema differs from the edition pin")
    python = os.environ.get("UNALTRAWEB_PRACTICE_QGIS_PYTHON") or sys.executable
    code = "import json; from importlib.metadata import distribution; d=distribution('unaltracaptura-qgis'); print(d.read_text('direct_url.json') or '{}')"
    installed = run_process([python, "-I", "-c", code], cwd=project, timeout_seconds=20)
    require(not installed.returncode and not installed.stdout_truncated, "Cannot inspect the installed producer wheel identity")
    metadata = handoff.parse_json(installed.stdout.encode())
    require(metadata.get("archive_info", {}).get("hashes", {}).get("sha256") == expected["wheel_sha256"],
            "Installed producer wheel hash differs from the selected candidate")
    return {"profile": profile, "package": package, "schema_sha256": observed["schema_sha256"], "wheel_sha256": expected["wheel_sha256"]}


def validate_closure(report, manifest, roots, recipient, teacher_only=(), *, profile="qgis-practice-v1"):
    require(profile in PROFILE_ROLES and report.get("profile") == profile and isinstance(report.get("selected"), list)
            and len(report["selected"]) == len(roots) and set(report["selected"]) == set(roots), "Producer did not return the requested explicit selection")
    rows = report.get("closure")
    require(isinstance(rows, list) and 0 < len(rows) <= 512, "Invalid bounded producer closure")
    by_id = {entry["id"]: entry for entry in manifest["files"]}
    selected = {row["id"] for row in rows}
    require(len(selected) == len(rows) and set(roots) <= selected, "Incomplete or duplicate producer closure")
    for row in rows:
        declared = by_id.get(row["id"])
        require(declared is not None and all(row.get(key) == declared.get(key) for key in ("path", "sha256", "bytes", "kind", "role", "ownership")),
                "Selected producer file differs from the independently verified common inventory")
        require(set(row["depends_on"]) <= selected, "A required producer dependency is missing; closure cannot be filtered")
        require(row["kind"] == "output" and row["role"] in PROFILE_ROLES[profile],
                "Control/source/reconstruction/private products are not classroom delivery files")
        if recipient == "alumnat":
            require(row["role"] not in TEACHER_ROLES and row["id"] not in teacher_only,
                    "Student selection reaches a teacher-only/resolved product")
    handoff.unique_paths([row["path"] for row in rows])
    return rows


def write_new(directory, name, content):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def author_resources(workspace, declarations):
    """Bounded editable SVG resources, independent of opaque GIS products.

    Every local reference must be explicitly declared, hashed and mapped without
    changing its relative relationship. No directory scan or neighbour inference.
    """
    from .image_probe import svg_resource, MAX_SVG_BYTES
    import tinycss2

    result = {who: [] for who in RECIPIENTS}
    for item in declarations:
        require(len(item["recipients"]) == len(set(item["recipients"])), "Duplicate resource recipient")
        require(Path(item["path"]).suffix.lower() == ".svg", "Editable infographic must be SVG")
        members = [item, *item["dependencies"]]
        handoff.unique_paths([row["path"] for row in members])
        handoff.unique_paths([row["destination"] for row in members])
        by_source = {row["path"]: row for row in members}
        rows, references = [], []
        for row in members:
            source, destination = row["path"], row["destination"]
            handoff.safe_path(source)
            handoff.safe_path(destination)
            require(Path(source).parts[0] in {"practiques", "_practices", "assets"}, "Author resources must be selected from authored practice/assets roots")
            require(Path(destination).parts[0] == "resources", "Author resource destinations must be beneath resources/")
            require(Path(destination).suffix.lower() == Path(source).suffix.lower(), "Resource mapping must preserve its format suffix")
            require(Path(source).suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".woff", ".woff2", ".ttf", ".otf"},
                    "Scripts/controls are not infographic resources")
            is_svg = Path(source).suffix.lower() == ".svg"
            observed, size, raw = workspace.read(source, MAX_SVG_BYTES if is_svg else 64*1024*1024, collect=is_svg)
            require(observed == row["sha256"], "Author resource hash differs from the declared bytes")
            rows.append({"id": "author:"+source, "source": source, "destination": destination, "sha256": observed, "bytes": size,
                         "role": item["role"] if row is item else "infographic-resource"})
            if not is_svg:
                continue
            text = raw.decode("utf-8")
            require(not re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?xml-stylesheet", text, re.I), "SVG declarations/external stylesheets are unsupported")
            root = ET.fromstring(text)
            require(root.tag.rsplit("}", 1)[-1] == "svg", "Expected SVG resource")

            def reference(value, navigation=False):
                if not value or value.startswith("#"):
                    return
                parsed = urlsplit(value)
                if navigation and parsed.scheme in {"https", "http", "mailto"}:
                    return
                if parsed.scheme == "data":
                    svg_resource(value, "image")
                    return
                require(not parsed.scheme and not parsed.netloc and not parsed.query, "Remote/dynamic SVG resources are not retained")
                local = unquote(parsed.path)
                target = posixpath.normpath(posixpath.join(str(Path(source).parent), local))
                handoff.safe_path(target)
                require(target in by_source, "SVG dependency is absent from the explicit author-resource declaration")
                mapped = posixpath.normpath(posixpath.join(str(Path(destination).parent), local))
                require(mapped == by_source[target]["destination"], "Author resource mapping breaks a relative SVG reference")
                references.append({"source": source, "target": target})

            def css(text):
                require(not re.search(r"@import\b", text, re.I), "Imported SVG stylesheets need a supported explicit resource profile")
                def walk(tokens):
                    for token in tokens:
                        require(token.type != "error", "Invalid SVG CSS resource expression")
                        if token.type == "url":
                            reference(token.value)
                        elif token.type == "function":
                            if token.lower_name == "url":
                                values = [part for part in token.arguments if part.type not in {"whitespace", "comment"}]
                                require(len(values) == 1 and values[0].type in {"string", "url", "ident"}, "Dynamic SVG URL is unsupported")
                                reference(values[0].value)
                            else:
                                walk(token.arguments)
                        elif hasattr(token, "content"):
                            walk(token.content)
                walk(tinycss2.parse_component_value_list(text))

            for count, node in enumerate(root.iter(), 1):
                require(count <= 20000, "SVG node limit exceeded")
                tag = node.tag.rsplit("}", 1)[-1]
                require(tag not in {"script", "foreignObject", "animate", "animateMotion", "animateTransform", "set"}, "Executable/dynamic author SVG is unsupported")
                for key, value in node.attrib.items():
                    name = key.rsplit("}", 1)[-1]
                    require(not name.lower().startswith("on"), "Executable SVG attributes are unsupported")
                    if name in {"href", "src"}:
                        reference(value, navigation=tag == "a")
                    if name == "style" or "url(" in value.lower():
                        css(value)
                if tag == "style":
                    css(node.text or "")
        reachable = {item["path"]}
        while True:
            following = reachable | {edge["target"] for edge in references if edge["source"] in reachable}
            if following == reachable:
                break
            reachable = following
        require(reachable == set(by_source), "Unreferenced neighbouring files are not infographic dependencies")
        for who in item["recipients"]:
            result[who].extend(rows)
    for rows in result.values():
        handoff.unique_paths([row["destination"] for row in rows])
    return result


def _copy_selected(workspace, row, target):
    """Copy one verified regular source, retaining the same guards for PDF/ZIP."""
    handoff.safe_path(row["source"])
    parent, _, name = row["source"].rpartition("/")
    with workspace.directory(parent) as source_dir:
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_dir)
        try:
            before = os.fstat(source)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == row["bytes"], "Edition source is not the selected regular file")
            count, hasher = 0, hashlib.sha256()
            while piece := os.read(source, 65536):
                count += len(piece)
                require(count <= row["bytes"], "Edition source grew while copying")
                hasher.update(piece)
                target.write(piece)
            require(count == row["bytes"] and hasher.hexdigest() == row["sha256"]
                    and handoff.signature(before) == handoff.signature(os.fstat(source))
                    == handoff.signature(os.stat(name, dir_fd=source_dir, follow_symlinks=False)), "Edition source changed during copying")
        finally:
            os.close(source)


def _output_record(output, filename):
    output.seek(0)
    hasher = hashlib.sha256()
    while piece := output.read(1024*1024):
        hasher.update(piece)
    return {"path": filename, "sha256": hasher.hexdigest(), "bytes": os.fstat(output.fileno()).st_size}


def copy_pdf(project, directory, filename, row):
    """Deliver the already sealed reading bytes; never invoke a renderer."""
    handoff.safe_path(filename)
    require(Path(filename).name == filename and filename.endswith(".pdf"), "Expected a delivery PDF basename")
    require(0 < row["bytes"] <= handoff.MAX_FILE_BYTES, "Delivery PDF exceeds its budget")
    fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, "w+b") as output, closing(handoff.Workspace(str(project))) as workspace:
        _copy_selected(workspace, row, output)
        output.flush()
        os.fsync(output.fileno())
        result = _output_record(output, filename)
        require((result["sha256"], result["bytes"]) == (row["sha256"], row["bytes"]), "Delivered PDF differs from its sealed source")
        return result


def zip_files(project, directory, filename, entries):
    """Stream only the exact selected inventory; preserve relative GIS paths."""
    handoff.unique_paths([row["destination"] for row in entries])
    require(len(entries) <= 10000 and sum(row["bytes"] for row in entries) <= handoff.MAX_TOTAL_BYTES, "Edition ZIP exceeds its budget")
    fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with os.fdopen(fd, "w+b") as output, closing(handoff.Workspace(str(project))) as workspace:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for row in sorted(entries, key=lambda item: item["destination"]):
                info = zipfile.ZipInfo(row["destination"], date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with archive.open(info, "w", force_zip64=True) as target:
                    _copy_selected(workspace, row, target)
        output.flush()
        os.fsync(output.fileno())
        output.seek(0)
        with zipfile.ZipFile(output) as archive:
            require(set(archive.namelist()) == {row["destination"] for row in entries}, "Final ZIP inventory differs")
            for row in entries:
                with archive.open(row["destination"]) as member:
                    hasher = hashlib.sha256()
                    while piece := member.read(65536):
                        hasher.update(piece)
                    require(hasher.hexdigest() == row["sha256"], "Final ZIP member differs from selected bytes")
        return _output_record(output, filename)


def compose(project: Path, factory: Path, config_path: str, *, dry_run=False):
    require(Path(project).is_absolute(), "Composition requires an explicit absolute consumer")
    project = Path(project)
    spec, config_sha, site = load_config(project, config_path)
    privacy_preflight(project, config_path, spec, site)
    relative = Path("dist/practiques") / spec["slug"] / spec["version"] / spec["language"]
    # Opening every ancestor rejects symlinks even in the early collision check.
    root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            parent = fs._open_directory(root, relative.parent)
        except FileNotFoundError:
            parent = None
        if parent is not None:
            try:
                try:
                    os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError("Edition destination already exists; versions are create-only")
            finally:
                os.close(parent)
        profile = spec["gis"].get("profile", "qgis-practice-v1")
        verifier = verifier_identity(project, spec["gis"]["verifier"], profile)
        closures, reports, readings = {}, {}, {}
        with closing(handoff.Workspace(str(project))) as workspace:
            common = handoff.Verifier(workspace)
            manifest, _, _ = common.bundle(spec["gis"]["bundle"], spec["gis"]["sha256"])
            require(manifest["producer"]["name"] == "unaltracaptura-qgis", "Unsupported GIS producer")
            base = Path(spec["gis"]["bundle"]).parent
            for who in RECIPIENTS:
                args = ["practice-check", "--workspace", str(project), "--path", spec["gis"]["bundle"], "--sha256", spec["gis"]["sha256"]]
                for identifier in spec["selection"][who]:
                    args.extend(["--select", identifier])
                reports[who] = provider_command(project, args)
                require(reports[who].get("bundle", {}).get("sha256") == spec["gis"]["sha256"], "Producer checked a different bundle")
                closures[who] = validate_closure(reports[who], manifest, spec["selection"][who], who, spec["gis"].get("teacher_only", []), profile=profile)
                source = spec["readings"][who]["source"]
                actual, _, _ = workspace.read(source, 2*1024*1024)
                require(actual == spec["readings"][who]["approved_sha256"], "Reading differs from its explicitly approved source hash")
            auxiliary = author_resources(workspace, spec.get("resources", []))
            portable, products, restricted = {}, {}, {}
            known_sources = {(base / row["path"]).as_posix() for row in manifest["files"]}
            known_sources.update(row["source"] for rows in auxiliary.values() for row in rows)
            for who in RECIPIENTS:
                targets = [{"source": (base / row["path"]).as_posix(), "destination": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]}
                           for row in closures[who]] + auxiliary[who]
                portable[who] = {row["source"]: {key: row[key] for key in ("destination", "sha256", "bytes")} for row in targets}
                require(len(portable[who]) == len(targets), "Portable reading source mapping is ambiguous")
                products[who] = {row["id"]: (base / row["path"]).as_posix() for row in closures[who]}
                restricted[who] = known_sources - portable[who].keys()
            runtime = active_runtime()
            image = runtime.worker("manual_pdf") if runtime else (os.environ.get("MANUAL_PDF_IMAGE") or consumer_integration()["manual_pdf_image"])
            run_id = "edition-" + config_sha[:16]
            planned_readings = {who: practice_pdf.build(project, factory, spec["readings"][who]["source"], spec["version"], image=image,
                               run=run_id, dry_run=True, portable_targets=portable[who], bindings=spec["readings"][who].get("bindings", []),
                               products=products[who], restricted=restricted[who]) for who in RECIPIENTS}
            reading_resources = {who: [{"id": "reading-resource:"+path, "source": path, "role": "reading-resource", **row}
                                for path, row in planned_readings[who]["portable_links"]["targets"].items() if path not in portable[who]] for who in RECIPIENTS}
            workspace.recheck()
            result = {"ok": True, "dry_run": dry_run, "publishes": False, "path": relative.as_posix(),
                      "operation": "Web composition of existing GIS products; no GIS calculation invoked", "gis_verifier": verifier,
                      "gis": {"bundle": spec["gis"], "producer": manifest["producer"], "activity": reports["alumnat"]["activity"], "job": reports["alumnat"]["job"]},
                      "selection": spec["selection"], "closure": closures, "author_resources": auxiliary,
                      "reading_resources": reading_resources,
                      "reading_links": {who: planned_readings[who]["portable_links"] for who in RECIPIENTS}}
            if dry_run:
                return result
            for who in RECIPIENTS:
                readings[who] = practice_pdf.build(project, factory, spec["readings"][who]["source"], spec["version"], image=image, run=run_id,
                                                   portable_targets=portable[who], bindings=spec["readings"][who].get("bindings", []),
                                                   products=products[who], restricted=restricted[who])
                require(readings[who]["ok"], "Reading PDF did not complete")
                require(readings[who]["portable_links"] == planned_readings[who]["portable_links"], "Reading resource mapping changed during rendering")
            workspace.recheck()
            with Reader(project) as reader:
                require(digest(reader.read(config_path)) == config_sha, "Edition configuration changed during rendering")
            parent = fs._open_directory(root, relative.parent, create=True)
            stage_name = ".candidate-" + spec["language"] + "-" + uuid.uuid4().hex
            os.mkdir(stage_name, 0o700, dir_fd=parent)
            stage = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            packages = {}
            try:
                for who in RECIPIENTS:
                    rows = [{"id": item["id"], "source": (base / item["path"]).as_posix(), "destination": item["path"],
                                 "sha256": item["sha256"], "bytes": item["bytes"], "role": item["role"]} for item in closures[who]]
                    rows.extend(auxiliary[who])
                    rows.extend(reading_resources[who])
                    pdf = readings[who]
                    hashed, length, _ = workspace.read(pdf["pdf"], handoff.MAX_FILE_BYTES)
                    reading_row = {"id": "reading-"+who, "source": pdf["pdf"], "destination": practice_pdf.BASENAMES[spec["language"]]+".pdf",
                                   "sha256": hashed, "bytes": length, "role": "reading"}
                    rows.append(reading_row)
                    receipt_sha, _, receipt_raw = workspace.read(pdf["receipt"], 1024*1024, collect=True)
                    pdf_receipt = handoff.parse_json(receipt_raw)
                    name = spec["slug"] + ("-docent" if who == "docent" else "") + "-" + spec["version"] + "-" + spec["language"] + ".zip"
                    zipped = zip_files(project, stage, name, rows)
                    delivered_pdf = copy_pdf(project, stage, name.removesuffix(".zip") + ".pdf", reading_row)
                    receipt = {"schema_version": 1, "kind": "unaltraweb-practice-edition-receipt", "recipient": who,
                        "slug": spec["slug"], "version": spec["version"], "language": spec["language"], "zip": zipped,
                        "config": {"path": config_path, "sha256": config_sha}, "producer_verification": reports[who], "verifier": verifier,
                        "reading": {"source": spec["readings"][who], "pdf": pdf["pdf"], "pdf_sha256": hashed,
                                    "receipt": pdf["receipt"], "receipt_sha256": receipt_sha, "renderer": pdf_receipt["renderer"],
                                    "portable_links": pdf_receipt["portable_links"], "effective_source": pdf_receipt["effective_source"],
                                    "inputs": pdf_receipt["original_inputs"], "factory_inputs": pdf_receipt["factory_inputs"],
                                    "delivery": delivered_pdf},
                        "files": rows, "author_resources": auxiliary[who], "composer": {"name": "unaltraweb", "version": __version__},
                        "retention": "dist delivery is durable; this receipt grants no cleanup permission"}
                    receipt_bytes = canonical(receipt)
                    write_new(stage, name + ".receipt.json", receipt_bytes)
                    pdf_receipt_name = delivered_pdf["path"] + ".receipt.json"
                    pdf_delivery_receipt = canonical({
                        "schema_version": 1, "kind": "unaltraweb-practice-pdf-delivery-receipt", "recipient": who,
                        "slug": spec["slug"], "version": spec["version"], "language": spec["language"],
                        "pdf": delivered_pdf, "zip": zipped, "config": receipt["config"],
                        "sealed_source": {"path": pdf["pdf"], "sha256": hashed, "receipt": pdf["receipt"], "receipt_sha256": receipt_sha},
                        "edition_receipt": {"path": name + ".receipt.json", "sha256": digest(receipt_bytes)},
                        "retention": receipt["retention"],
                    })
                    write_new(stage, pdf_receipt_name, pdf_delivery_receipt)
                    packages[who] = {**zipped, "receipt": name + ".receipt.json", "receipt_sha256": digest(receipt_bytes),
                                     "pdf": {**delivered_pdf, "receipt": pdf_receipt_name, "receipt_sha256": digest(pdf_delivery_receipt)}}
                workspace.recheck()
                # Re-run complete common and domain verification before commit;
                # neither filtered results nor stale acknowledgements are authority.
                handoff.check(str(project), "bundle", spec["gis"]["bundle"], spec["gis"]["sha256"])
                verifier_identity(project, spec["gis"]["verifier"], profile)
                with Reader(project) as reader:
                    require(digest(reader.read(config_path)) == config_sha, "Edition selection changed before publication")
                    for who in RECIPIENTS:
                        practice_pdf._unchanged(project, json.loads(reader.read(readings[who]["receipt"]))["original_inputs"])
                write_new(stage, "edition.json", canonical({**result, "packages": packages, "readings": readings}))
                os.fsync(stage)
                current = fs._open_directory(root, relative.parent)
                try:
                    require(fs._identity(os.fstat(current)) == fs._identity(os.fstat(parent)), "Delivery parent changed")
                finally:
                    os.close(current)
                fs._require_generated_path(project, relative, label="Retained edition delivery")
                _install_new_directory(parent, stage_name, relative.name)
                os.fsync(parent)
                return {**result, "packages": packages, "readings": readings}
            finally:
                os.close(stage)
                os.close(parent)
    finally:
        os.close(root)
