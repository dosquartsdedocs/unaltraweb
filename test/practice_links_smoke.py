"""Installed reproduction/regression for local links in final recipient ZIP PDFs."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import posixpath
import sys
import shutil
from urllib.parse import unquote, urlsplit
import venv
import uuid
import hashlib

from pypdf import PdfReader

from practice_editions_smoke import edition_fixture, compose_mcp, extract, run, save, sha

SOURCE_ROOT = "_practices/tigit-projecte-territorial"
LOCAL_HREF = "../../templates/infografia-a3.svg"
THEORY_URL = "https://example.org/teoria?q=1#metode"


def linked_fixture(project, candidate, *, bound_captures=False):
    spec, config_path, readings, _ = edition_fixture(project, candidate, legacy=True, version="2026-10-links")
    site = json.loads((project / "_config.yml").read_bytes())
    for who, old in list(readings.items()):
        name = "LLEGIU-ME-estudiant.md" if who == "alumnat" else "LLEGIU-ME-docent.md"
        relative = SOURCE_ROOT + "/readings/ca/" + name
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        (project / old).rename(target)  # Construct the synthetic original tree before its baseline.
        lines = target.read_text().splitlines()
        assert len(lines) < 134
        lines.extend([""] * (134-len(lines)))
        lines.append("[plantilla editable A3](" + LOCAL_HREF + ")")
        lines.extend(["", "[Teoria]("+THEORY_URL+")", "", "[Comprovació](#comprovacio)", "", "# Comprovació {#comprovacio}", "", "Verifiqueu els elements seleccionats."])
        target.write_text("\n".join(lines)+"\n")
        assert target.read_text().splitlines()[134] == "[plantilla editable A3](" + LOCAL_HREF + ")"
        readings[who] = relative
        spec["readings"][who] = {"source": relative, "approved_sha256": sha(target)}
    site["unaltraweb"]["practices"]["readings"] = [{"source": path, "slug": spec["slug"], "lang": "ca", "recipient": who} for who, path in readings.items()]
    (project / "_config.yml").write_text(json.dumps(site, ensure_ascii=False, indent=2)+"\n")
    resource = spec["resources"][0]
    templates = project / SOURCE_ROOT / "templates"
    templates.mkdir()
    for row, name in [(resource, "infografia-a3.svg"), (resource["dependencies"][0], "map.png")]:
        target = templates / name
        (project / row["path"]).rename(target)
        row.update(path=target.relative_to(project).as_posix(), sha256=sha(target))
    resource["destination"] = "resources/figures/plantilla-editable.svg"
    resource["dependencies"][0]["destination"] = "resources/figures/map.png"
    bound_paths = []
    if bound_captures:
        capture = project / "sandbox/practiques/accessibilitat-vilaseca/2026-10-07-organitzacio/captures/inici.png"
        capture.parent.mkdir(parents=True)
        shutil.copyfile(project / "assets/teaching/map.png", capture)
        bound_paths.append(capture.relative_to(project).as_posix())
        for who, relative in readings.items():
            target = project / relative
            target.write_text(target.read_text() + '\n![Captura inicial declarada](captures/inici.png "Recurs del run conservat.")\n\n[Obriu la captura](captures/inici.png)\n')
            spec["readings"][who]["approved_sha256"] = sha(target)
        site["unaltraweb"]["practices"]["readings"][0]["bindings"] = [{"reference": "captures/inici.png",
            "path": bound_paths[0], "sha256": sha(capture), "destination": "resources/captures/inici.png"}]
        # The same binding format can address an explicitly selected GIS product.
        bundle = json.loads((project / "sandbox/gis/delivery/bundle.json").read_bytes())
        row = next(row for row in bundle["files"] if row["id"] == "resolved-project-original")
        spec["readings"]["docent"]["bindings"] = [{"reference": "captures/inici.png", "product": row["id"], "sha256": row["sha256"]}]
        (project / "_config.yml").write_text(json.dumps(site, ensure_ascii=False, indent=2)+"\n")
    (project / config_path).write_text(json.dumps(spec, ensure_ascii=False, indent=2)+"\n")
    authored = ["_config.yml", config_path, *readings.values(), resource["path"], resource["dependencies"][0]["path"]]
    run(["git", "-C", str(project), "add", "--", *authored])
    authored.extend(bound_paths)
    return spec, config_path, readings, {name: sha(project/name) for name in authored}


def pdf_links(path):
    reader = PdfReader(path)
    links = []
    for number, page in enumerate(reader.pages, 1):
        for entry in page.get("/Annots", []):
            annotation = entry.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            if action is not None:
                action = action.get_object()
                kind = str(action.get("/S"))
                target = action.get("/URI") if kind == "/URI" else action.get("/F") if kind in {"/Launch", "/GoToR"} else action.get("/D")
                if hasattr(target, "get_object"):
                    target = target.get_object()
                if isinstance(target, dict):
                    target = target.get("/UF") or target.get("/F")
                links.append({"page": number, "kind": kind, "target": str(target)})
            elif annotation.get("/Dest") is not None:
                links.append({"page": number, "kind": "/GoTo", "target": str(annotation["/Dest"])})
    return links


def inspect_final(project, result, who, output):
    archive = project / result["path"] / result["packages"][who]["path"]
    assert sha(archive) == result["packages"][who]["sha256"]
    destination = output / who
    extract(archive, destination)
    links = pdf_links(destination / "LLEGIU-ME.pdf")
    local, external, internal = [], [], []
    for link in links:
        if link["kind"] == "/GoTo":
            internal.append(link)
            continue
        uri = urlsplit(link["target"])
        if uri.scheme in {"https", "http", "mailto"}:
            external.append(link)
            continue
        relative = unquote(uri.path)
        target = (destination / relative).resolve()
        local.append({**link, "resolved": str(target), "confined": target.is_relative_to(destination.resolve()), "exists": target.is_file()})
    assert any(link["target"] == THEORY_URL for link in external), links
    reader = PdfReader(destination / "LLEGIU-ME.pdf")
    resolved_anchors = []
    for row in internal:
        named = reader.named_destinations.get(row["target"])
        assert named is not None, (row, list(reader.named_destinations))
        page = reader.get_destination_page_number(named)
        assert page is not None and 0 <= page < len(reader.pages)
        resolved_anchors.append({"target": row["target"], "page": page+1,
                                 "has_heading": "Comprovació" in (reader.pages[page].extract_text() or "")})
    assert any(row["has_heading"] for row in resolved_anchors), (links, resolved_anchors)
    return {"zip": str(archive), "zip_sha256": sha(archive), "pdf_sha256": sha(destination/"LLEGIU-ME.pdf"),
            "links": links, "local": local, "external": external, "internal": internal, "resolved_anchors": resolved_anchors,
            "selected_template_exists": (destination / "resources/figures/plantilla-editable.svg").is_file()}


def negative_links(project, original_spec, readings, candidate, output):
    from practice_candidate_smoke import runtime_args, command, tree_hashes
    before = tree_hashes(project / "dist")
    snapshots = tree_hashes(project / "sandbox/practiques")
    source = project / readings["alumnat"]
    original = source.read_bytes()
    results = {}
    def invoke(spec, name):
        spec = json.loads(json.dumps(spec))
        spec["version"] = "negative-links-"+name
        spec["readings"]["alumnat"]["approved_sha256"] = sha(source)
        config = f"practiques/{spec['slug']}/negative-links-{name}.json"
        save(project / config, spec)
        run(["git", "-C", str(project), "add", "--", config])
        called = command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-compose",
            "--config", config], expected=None)
        result = json.loads(called.stdout)
        assert called.returncode and result["ok"] is False, result
        assert tree_hashes(project / "dist") == before and tree_hashes(project / "sandbox/practiques") == snapshots, name
        results[name] = result
        return result
    for name, href in [("undeclared", "../../templates/not-selected.svg"), ("escape", "../../../../../../secret.svg")]:
        source.write_bytes(original.replace(LOCAL_HREF.encode(), href.encode()))
        invoke(original_spec, name)
        assert href.encode() in source.read_bytes()
        source.write_bytes(original)
    spec = json.loads(json.dumps(original_spec))
    spec["resources"][0]["recipients"] = ["docent"]
    assert "selection" in invoke(spec, "teacher-only")["error"]
    poster = project / original_spec["resources"][0]["path"]
    poster_bytes = poster.read_bytes()
    poster.unlink()
    invoke(original_spec, "missing-selected-target")
    poster.write_bytes(poster_bytes)
    spec = json.loads(json.dumps(original_spec))
    # Source declarations cannot use a hash to bypass the recipient's GIS IDs.
    student_extra = "[Unselected GIS](extra/teacher.qgz)\n"
    source.write_bytes(original + student_extra.encode())
    teacher_row = next(row for row in json.loads((project / spec["gis"]["bundle"]).read_bytes())["files"] if row["id"] == "resolved-project")
    spec["readings"]["alumnat"]["bindings"] = [{"reference": "extra/teacher.qgz", "product": "resolved-project", "sha256": teacher_row["sha256"]}]
    assert "not selected" in invoke(spec, "bound-other-selection")["error"]
    source.write_bytes(original)
    # Standalone compilation must not certify this otherwise legitimate local
    # prose href without its recipient/ZIP context.
    called = command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-pdf-build",
                     "--source", readings["alumnat"], "--version", "standalone-local-link", "--run", "refusal", "--dry-run"], expected=None)
    standalone = json.loads(called.stdout)
    assert standalone["ok"] is False and "Standalone" in standalone["error"], standalone
    results["standalone-local-link"] = standalone
    assert source.read_bytes() == original and tree_hashes(project / "dist") == before
    save(output / "negative-links.json", results)
    return results


async def capture_binding_acceptance(project, candidate, launcher, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from practice_candidate_smoke import fixture, payload, clean_environment, tree_hashes
    from PIL import Image
    sources, _ = fixture(project, "Accessibilitat sintètica", ["99110"])
    site = json.loads((project / "_config.yml").read_bytes())
    captured = project / "sandbox/practiques/accessibilitat-vilaseca/2026-10-07-organitzacio/captures/inici.png"
    captured.parent.mkdir(parents=True)
    Image.new("RGB", (320, 120), "#23617a").save(captured)
    mapped = {}
    bindings = []
    for who, old in sources.items():
        relative = f"practiques/accessibilitat-vilaseca/ca/{who}/LLEGIU-ME.md"
        target = project / relative
        target.parent.mkdir(parents=True)
        (project / old).rename(target)
        target.write_text("---\ntitle: Captura declarada\nlang: ca\ncontent_status: draft\n---\n# Observeu la captura\n\n"
                          '![Captura inicial](captures/inici.png "Imatge del run conservat.")\n')
        mapped[who] = relative
        bindings.append({"source": relative, "slug": "accessibilitat-vilaseca", "lang": "ca", "recipient": who,
                         "bindings": [{"reference": "captures/inici.png", "path": captured.relative_to(project).as_posix(), "sha256": sha(captured)}]})
    site["unaltraweb"]["practices"] = {"readings": bindings}
    (project / "_config.yml").write_text(json.dumps(site, ensure_ascii=False, indent=2)+"\n")
    authored = {path: sha(project/path) for path in ["_config.yml", *mapped.values(), captured.relative_to(project).as_posix()]}
    image = candidate["controller"]["image_id"]
    params = StdioServerParameters(command=str(launcher), args=["serve", "--project", str(project), "--image", image,
        "--expected-image-id", image, "--managed", "--offline"], env=clean_environment())
    results = {}
    with (output / "capture-mcp.log").open("x") as log:
        async with stdio_client(params, errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as session:
                await session.initialize()
                identity = payload(await session.call_tool("runtime_identity", {}))
                for who, relative in mapped.items():
                    request = {"source": relative, "version": "capture-bindings-v1", "run": "installed-01"}
                    planned = payload(await session.call_tool("manual_practice_pdf_build", {**request, "dry_run": True}))
                    assert planned["ok"] and planned["state"] == "planned", planned
                    result = payload(await session.call_tool("manual_practice_pdf_build", request))
                    assert result["ok"] and result["state"] == "built", result
                    receipt = json.loads((project / result["receipt"]).read_bytes())
                    assert receipt["portable_links"]["context"] == "standalone"
                    assert receipt["portable_links"]["resolved_bindings"][0]["sha256"] == sha(captured)
                    assert not (project / "captures").exists() and not (project / relative).parent.joinpath("captures").exists()
                    results[who] = result
                before = tree_hashes(project / "sandbox")
                raw = captured.read_bytes()
                captured.write_bytes(raw+b"changed")
                refused = payload(await session.call_tool("manual_practice_pdf_build", {"source": mapped["alumnat"], "version": "bad-hash", "dry_run": True}))
                assert refused["ok"] is False and "binding hash" in refused["error"], refused
                captured.write_bytes(raw)
                captured.unlink()
                absent = payload(await session.call_tool("manual_practice_pdf_build", {"source": mapped["alumnat"], "version": "absent-capture", "dry_run": True}))
                assert absent["ok"] is False and "Missing" in absent["error"], absent
                captured.write_bytes(raw)
                old_config = (project / "_config.yml").read_bytes()
                del site["unaltraweb"]["practices"]["readings"][0]["bindings"]
                (project / "_config.yml").write_text(json.dumps(site))
                undeclared = payload(await session.call_tool("manual_practice_pdf_build", {"source": mapped["alumnat"], "version": "no-discovery", "dry_run": True}))
                assert undeclared["ok"] is False and "Missing" in undeclared["error"], undeclared
                (project / "_config.yml").write_bytes(old_config)
                assert tree_hashes(project / "sandbox") == before
                await session.call_tool("runtime_drain", {"confirm": True})
    stopped = json.loads(run([str(launcher), "session-status", "--project", str(project), "--session-id", identity["session_id"],
                              "--container-id", identity["runtime"]["container"]["id"]]))
    assert stopped["resources_released"] and authored == {path: sha(project/path) for path in authored}
    return {"ok": True, "readings": results, "changed_hash_refused": refused, "absent_capture_refused": absent, "no_sandbox_discovery": undeclared,
            "authored_hashes": authored, "terminated": stopped}


def owned_cli_acceptance(project, spec, candidate, launcher, output):
    """Exercise the documented one-shot CLI with native limits/ownership/reap."""
    from practice_candidate_smoke import runtime_args, command
    planned = json.loads(json.dumps(spec))
    planned["version"] = "native-cli-links-plan"
    relative = f"practiques/{spec['slug']}/native-cli-links.json"
    save(project / relative, planned)
    run(["git", "-C", str(project), "add", "--", relative])
    session = uuid.uuid4().hex
    project_id = hashlib.sha256(str(project).encode()).hexdigest()[:16]
    args = runtime_args(project, candidate, session)
    args[1] = "create"
    args.remove("--rm")
    args.insert(2, "--init")
    args[args.index("--name")+1] = "unaltraweb-stdio-"+session
    args[args.index("--memory")+1] = "4g"
    args[args.index("--pids-limit")+1] = "512"
    offset = args.index(candidate["controller"]["image_id"])
    args[offset:offset] = ["--label", "io.context.mcp-factory=unaltraweb", "--label", "io.context.mcp-role=stdio",
        "--label", "io.context.mcp-project="+project_id, "--label", "io.context.mcp-session="+session,
        "--env", "UNALTRAWEB_RUNTIME_SESSION="+session]
    identifier = run(args+["--project", str(project), "mcp", "manual-practice-compose", "--config", relative, "--dry-run"]).strip()
    try:
        info = json.loads(run(["docker", "container", "inspect", identifier]))[0]
        assert info["HostConfig"]["Memory"] == 4*1024**3 and info["HostConfig"]["PidsLimit"] == 512
        assert info["HostConfig"]["NanoCpus"] == 2_000_000_000
        result = json.loads(run(["docker", "start", "--attach", identifier]))
        assert result["ok"] and result["dry_run"] and not (project / result["path"]).exists(), result
    finally:
        reaped = json.loads(run([str(launcher), "reap-session", "--project", str(project), "--session-id", session, "--container-id", identifier]))
        assert reaped["resources_released"], reaped
    evidence = {"ok": True, "container_id": identifier, "labels": info["Config"]["Labels"],
                "limits": {key: info["HostConfig"][key] for key in ("Memory", "PidsLimit", "NanoCpus")}, "result": result, "reaped": reaped}
    save(output / "native-cli.json", evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-broken", action="store_true")
    parser.add_argument("--bound-captures", action="store_true")
    args = parser.parse_args()
    assert sha(args.candidate) == args.sha256
    candidate = json.loads(args.candidate.read_bytes())
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    environment = root / "installed"
    venv.EnvBuilder(with_pip=True).create(environment)
    wheel = args.candidate.resolve().parent / candidate["web_wheel"]["path"]
    assert sha(wheel) == candidate["web_wheel"]["sha256"]
    requirements = root / "requirements.txt"
    requirements.write_text(f"{wheel.as_uri()} --hash=sha256:{sha(wheel)}\n")
    run([str(environment / "bin/python"), "-m", "pip", "install", "--no-index", "--no-deps", "--require-hashes", "-r", str(requirements)])
    project, review = root / "consumer", root / "review"
    review.mkdir()
    spec, config, sources, authored = linked_fixture(project, candidate, bound_captures=args.bound_captures)
    result = asyncio.run(compose_mcp(project, config, candidate, environment / "bin/unaltraweb-mcp-docker", review, sources))
    inspected = {who: inspect_final(project, result["result"], who, root / "extracted") for who in sources}
    if not args.expect_broken:
        for who, path in sources.items():
            reading = result["result"]["readings"][who]
            job = project / reading["job"]
            receipt = json.loads((project / reading["receipt"]).read_bytes())
            assert (job / "inputs/original.md").read_bytes() == (project / path).read_bytes()
            assert LOCAL_HREF in (project / path).read_text()
            assert LOCAL_HREF not in (job / receipt["effective_source"]["markdown"]).read_text()
            assert receipt["portable_links"] == reading["portable_links"]
            assert sha(job / receipt["effective_source"]["markdown"]) == receipt["effective_source"]["markdown_sha256"]
            assert sha(job / receipt["effective_source"]["ast"]) == receipt["effective_source"]["ast_sha256"]
    for who, report in inspected.items():
        assert report["selected_template_exists"] and report["local"], report
        if args.expect_broken:
            assert any(not row["confined"] or not row["exists"] for row in report["local"]), report
        else:
            assert all(row["confined"] and row["exists"] for row in report["local"]), report
            expected = {"resources/figures/plantilla-editable.svg"}
            if args.bound_captures:
                expected.add("resources/captures/inici.png" if who == "alumnat" else "payload/captures/resolved-project/overview.original.png")
            assert {row["target"] for row in report["local"]} == expected, report
    assert authored == {name: sha(project/name) for name in authored}
    negatives = negative_links(project, spec, sources, candidate, review) if not args.expect_broken else None
    captures = asyncio.run(capture_binding_acceptance(root / "capture-consumer", candidate, environment / "bin/unaltraweb-mcp-docker", review)) if args.bound_captures else None
    native_cli = owned_cli_acceptance(project, spec, candidate, environment / "bin/unaltraweb-mcp-docker", review) if not args.expect_broken else None
    evidence = {"ok": True, "reproduction_of_broken_candidate": args.expect_broken, "candidate_sha256": args.sha256,
                "source_preserved": authored, "api": result, "final_pdf_links": inspected, "negatives": negatives,
                "capture_bindings": captures, "native_cli": native_cli}
    save(root / "evidence.json", evidence)
    print(json.dumps({"ok": True, "broken_reproduced": args.expect_broken, "evidence": str(root/"evidence.json"), "sha256": sha(root/"evidence.json"),
                      "local_links": {who: value["local"] for who, value in inspected.items()}}, indent=2))


if __name__ == "__main__":
    main()
