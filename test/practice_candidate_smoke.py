#!/usr/bin/env python3
"""Verify a hash-bound installed practice candidate against synthetic consumers.

No unaltraweb checkout imports: the wheel is installed in a fresh venv and the
actual MCP/CLI/Make calls execute the selected immutable image. No images are
built or pulled by this acceptance. Test evidence and failed outputs are retained.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import venv
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, ImageDraw
from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parents[1]
APPROVED_SOURCE = "d37ef4c64eb7d2f2e7ef83cf037640ff42a964e0"
OWNED_CONTAINERS = set()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(1024*1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def save(path, value):
    with path.open("x") as output:
        output.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def command(args, *, env=None, expected=0, timeout=180):
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=timeout)
    if expected is not None and result.returncode != expected:
        raise AssertionError(f"Command failed ({result.returncode}, expected {expected}): {args}\n{result.stdout[-12000:]}\n{result.stderr[-12000:]}")
    return result


def docker_json(kind, value):
    return json.loads(command(["docker", kind, "inspect", value]).stdout)[0]


def bind(source, destination, readonly=False):
    # Docker --mount values are CSV records, not shell/Make assignments.
    import csv
    output = io.StringIO()
    csv.writer(output, lineterminator="").writerow(["type=bind", "source="+str(source), "target="+str(destination)] + (["readonly"] if readonly else []))
    return output.getvalue()


def clean_environment():
    return {key: value for key, value in os.environ.items() if not (
        key.startswith(("UNALTRAWEB_", "PRACTICE_", "MCP_", "MANUAL_PDF_")) or key in {"PYTHONPATH", "PYTHONHOME"})}


def payload(result):
    value = getattr(result, "structuredContent", None)
    if isinstance(value, dict):
        return value
    text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
    try:
        return json.loads(text)
    except ValueError:
        return {"ok": False, "error": text, "isError": bool(result.isError)}


def tree_hashes(root):
    return {path.relative_to(root).as_posix(): file_hash(path) for path in sorted(root.rglob("*")) if path.is_file()}


def fixture(project, course, codes):
    project.mkdir()
    command(["git", "init", "--quiet", str(project)])
    (project / ".gitignore").write_text("sandbox/\ndist/\n")
    (project / "assets/teaching").mkdir(parents=True)
    for name, size, colour in [("series.png", (123, 61), "#980000"), ("institution.png", (117, 59), "#12465c")]:
        picture = Image.new("RGB", size, "white")
        ImageDraw.Draw(picture).rectangle((3, 3, size[0]-4, size[1]-4), fill=colour)
        picture.save(project / "assets/teaching" / name)
    picture = Image.new("RGB", (640, 320), "#e7eff2")
    drawing = ImageDraw.Draw(picture)
    drawing.line([(30, 280), (160, 170), (300, 240), (420, 80), (600, 30)], fill="#205b75", width=12)
    picture.save(project / "assets/teaching/map.png")
    config = {
        "title": course, "lang": "ca", "default_lang": "ca", "languages": ["ca"],
        "exclude": ["practiques/", "sandbox/", "dist/"],
        "unaltraweb": {"site_profile": "unaltremanual", "manual": {
            "metadata": {"subject": course, "short_title": "PROVA", "series": "dosquartsdedocs",
                         "academic_year": "2099/2100", "institution": "Institució de prova", "instructors": [{"name": "Autoria sintètica"}],
                         "teaching_guides": [{"degree": "Grau de prova", "subject_code": code} for code in codes]},
            "pdf": {"mark_drafts": True, "cover": {"series_logo": "assets/teaching/series.png", "institution_logo": "assets/teaching/institution.png"}},
        }},
    }
    # JSON is also YAML and avoids importing factory configuration code.
    (project / "_config.yml").write_text(json.dumps(config, ensure_ascii=False, indent=2)+"\n")
    sources = {}
    for audience in ("alumnat", "docent"):
        relative = f"practiques/candidate/ca/{audience}/LLEGIU-ME.md"
        path = project / relative
        path.parent.mkdir(parents=True)
        content = "---\ntitle: Lectura de prova instal·lada\nlang: ca\ncontent_status: draft\n---\n\n"
        content += "# Lectura del mapa\n\nObserveu la forma de la línia i descriviu-ne els canvis de direcció.\n\n"
        content += '![Esquema sintètic de treball](assets/teaching/map.png "Recurs propi del consumidor de prova.")\n\n'
        content += "# Registre d'observacions\n\n| Pas | Observació |\n| --- | --- |\n"
        content += "".join(f"| {number} | Compareu el tram {number} i anoteu-ne la interpretació. |\n" for number in range(1, 43))
        content += "\nTable: Registre de la lectura.\n\n"
        if audience == "docent":
            content += "# Solució docent\n\nMARCADOR-SOLUCIO-DOCENT: la línia alterna direccions i representa un exemple sintètic.\n"
        else:
            content += "# Comprovació\n\nJustifiqueu les observacions amb les dades de la figura.\n"
        path.write_text(content)
        sources[audience] = relative
    authored = {"_config.yml", ".gitignore", *sources.values(), *(path.relative_to(project).as_posix() for path in (project / "assets").rglob("*.png"))}
    return sources, {name: file_hash(project / name) for name in authored}


def executed_images(page, reader):
    found = []
    def visit(contents, resources, depth=0):
        assert depth < 12
        resources = resources.get_object() if hasattr(resources, "get_object") else resources
        xobjects = resources.get("/XObject", {})
        xobjects = xobjects.get_object() if hasattr(xobjects, "get_object") else xobjects
        for operands, operator in ContentStream(contents, reader).operations:
            if operator != b"Do":
                continue
            target = xobjects[operands[0]].get_object()
            if target.get("/Subtype") == "/Image":
                found.append((int(target["/Width"]), int(target["/Height"])))
            elif target.get("/Subtype") == "/Form":
                visit(target, target.get("/Resources", resources), depth+1)
    visit(page.get_contents(), page["/Resources"])
    return found


def inspect_pdf(project, result, course, codes, audience):
    path = project / result["pdf"]
    reader = PdfReader(path)
    assert len(reader.pages) >= 2, "The first-page-only logo test needs multiple pages"
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for value in (course, *codes, "Autoria sintètica", "Lectura de prova instal·lada", result["version"]):
        assert value in text, (value, text)
    assert "2099/2100" not in text
    assert ("MARCADOR-SOLUCIO-DOCENT" in text) == (audience == "docent")
    assert ("Guia docent" if audience == "docent" else "Guia de pràctica") in text
    sizes, logos = [], []
    for index, page in enumerate(reader.pages):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        assert abs(width-841.89) < 1 and abs(height-595.276) < 1, (width, height)
        sizes.append([width, height])
        images = executed_images(page, reader)
        present = [list(size) for size in ((123, 61), (117, 59)) if size in images]
        assert len(present) == (2 if index == 0 else 0), (index, images)
        logos.append(present)
    fonts = command(["pdffonts", str(path)]).stdout
    assert "DejaVu" in fonts, fonts
    receipt = json.loads((project / result["receipt"]).read_bytes())
    job = project / result["job"]
    for relative, expected in receipt["artifacts"].items():
        assert file_hash(job / relative) == expected, relative
    assert set(tree_hashes(job)) == {*receipt["artifacts"], "receipt.json"}
    for relative, expected in receipt["original_inputs"].items():
        assert (file_hash(project / relative) if (project / relative).exists() else None) == expected, relative
    return {"pdf": str(path), "pdf_sha256": file_hash(path), "receipt": str(project / result["receipt"]),
            "receipt_sha256": file_hash(project / result["receipt"]), "pages": len(reader.pages), "sizes_pt": sizes,
            "logos_by_page": logos, "fonts": fonts, "result": result}


def runtime_args(project, candidate, token, *, entrypoint="unaltraweb-mcp"):
    socket = Path("/var/run/docker.sock").resolve(strict=True)
    OWNED_CONTAINERS.add("practice98-" + token)
    return ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
            "--name", "practice98-" + token, "--label", "io.context.practice-test=" + token,
            "--user", f"{os.getuid()}:{os.getgid()}", "--group-add", str(socket.stat().st_gid),
            "--mount", bind(project, project), "--mount", bind(socket, "/var/run/docker.sock"),
            "--env", "HOME=/tmp", "--env", "MCP_CONSUMER_WORKSPACE="+str(project),
            "--env", "UNALTRAWEB_DOCKER_ROOT="+str(project), "--env", "MANUAL_PDF_IMAGE="+candidate["pdf_worker"]["reference"],
            "--workdir", str(project), "--entrypoint", entrypoint, candidate["controller"]["image_id"]]


async def live_candidate(project, sources, candidate, launcher, output, *, wrong_worker=False):
    session_id = uuid.uuid4().hex
    selected = candidate["controller"]["image_id"]
    worker = {"reference": candidate["pdf_worker"]["reference"],
              "expected_image_id": "sha256:" + "0"*64 if wrong_worker else candidate["pdf_worker"]["image_id"]}
    arguments = ["serve", "--project", str(project), "--image", selected, "--expected-image-id", selected, "--managed", "--offline",
                 "--session-id", session_id, "--worker-images", json.dumps({"manual_pdf": worker})]
    params = StdioServerParameters(command=str(launcher), args=arguments, env=clean_environment())
    records = {"session_id": session_id, "reads": {}, "workers": []}
    with (output / ("wrong-worker-stderr.log" if wrong_worker else "mcp-stderr.log")).open("x") as log:
        async with stdio_client(params, errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as client:
                await client.initialize()
                inventory = {item.name for item in (await client.list_tools()).tools}
                assert "manual_practice_pdf_build" in inventory and "job_storage" not in inventory, inventory
                records["tools"] = sorted(inventory)
                identity = payload(await client.call_tool("runtime_identity", {}))
                records["identity"] = identity
                assert identity["package"]["mode"] == "installed" and identity["package"]["drift"] is False, identity
                assert identity["runtime"]["selected_image_id"] == selected and identity["runtime"]["container"]["state"] == "matched", identity
                assert identity["runtime"]["container"]["source_revision"] == candidate["source_revision"], identity
                assert identity["binding"]["consumer"] == identity["binding"]["daemon_host_project"] == str(project)
                for audience, source in sources.items():
                    request = {"source": source, "version": "2026-10-candidate", "run": "wrong-image" if wrong_worker else "installed-01"}
                    running = asyncio.create_task(client.call_tool("manual_practice_pdf_build", request))
                    while not running.done():
                        project_id = hashlib.sha256(str(project).encode()).hexdigest()[:16]
                        ids = await asyncio.to_thread(command, ["docker", "ps", "-q", "--no-trunc", "--filter", "label=io.context.mcp-role=manual-pdf",
                                                               "--filter", "label=io.context.mcp-project="+project_id])
                        for identifier in ids.stdout.split():
                            inspected = await asyncio.to_thread(command, ["docker", "container", "inspect", identifier], expected=None)
                            if inspected.returncode:
                                continue
                            observed = json.loads(inspected.stdout)[0]
                            mounts = observed["Mounts"]
                            assert observed["Image"] == candidate["pdf_worker"]["image_id"], observed
                            assert len(mounts) == 2 and {m["Destination"] for m in mounts} == {"/source", "/out"}, mounts
                            assert next(m for m in mounts if m["Destination"] == "/source")["RW"] is False
                            if identifier not in {item["id"] for item in records["workers"]}:
                                OWNED_CONTAINERS.add(identifier)
                                records["workers"].append({"id": identifier, "image_id": observed["Image"], "mounts": mounts,
                                                          "network": observed["HostConfig"]["NetworkMode"]})
                        await asyncio.sleep(.1)
                    result = payload(await running)
                    if wrong_worker:
                        assert result.get("ok") is False and "mismatch" in result.get("error", ""), result
                        records["refusal"] = result
                        break
                    assert result["ok"] and result["state"] == "built" and result["publishes"] is False, result
                    before = tree_hashes(project / result["job"])
                    reused = payload(await client.call_tool("manual_practice_pdf_build", request))
                    assert reused["ok"] and reused["state"] == "current" and before == tree_hashes(project / result["job"]), reused
                    records["reads"][audience] = result
                if not wrong_worker:
                    assert records["workers"], "No actual PDF worker mount observation was captured"
                await client.call_tool("runtime_drain", {"confirm": True})
    identifier = records["identity"]["runtime"]["container"]["id"]
    OWNED_CONTAINERS.add(identifier)
    checked = command([str(launcher), "session-status", "--project", str(project), "--session-id", session_id, "--container-id", identifier], env=clean_environment())
    records["terminated"] = json.loads(checked.stdout)
    assert records["terminated"]["resources_released"], records["terminated"]
    return records


def tuple_check(candidate):
    image_id = candidate["controller"]["image_id"]
    code = ("import json,hashlib,unaltraweb_mcp; from pathlib import Path; from unaltraweb_mcp.artifact_imports import CHECKER_FILES; "
            "root=Path(unaltraweb_mcp.__file__).parent; print(json.dumps({'path':str(root),'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in CHECKER_FILES}}))")
    actual = json.loads(command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
                                "--entrypoint", "python3", image_id, "-I", "-c", code]).stdout)
    assert "site-packages" in actual["path"] or "dist-packages" in actual["path"], actual
    assert actual["files"] == candidate["checker_files"], actual
    core = candidate["consumer_integration"]["core_sha"]
    for name, expected in actual["files"].items():
        content = subprocess.check_output(["git", "-C", str(ROOT), "show", core + ":src/unaltraweb_mcp/" + name])
        assert digest(content) == expected, (core, name)
    code = "import hashlib,json,sys; from pathlib import Path; r=Path('/opt/unaltraweb/src/unaltraweb_mcp'); print(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in json.loads(sys.argv[1])}))"
    worker = json.loads(command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
                                "--entrypoint", "python3", candidate["pdf_worker"]["image_id"], "-I", "-c", code, json.dumps(list(actual["files"]))]).stdout)
    assert worker == actual["files"], "Selected core/controller/PDF checkers differ"
    font_code = """import hashlib,json,subprocess
from pathlib import Path
result={}
for family in ('DejaVu Serif','DejaVu Sans','DejaVu Sans Mono'):
    actual,path=subprocess.check_output(['fc-match','-f','%{family}|%{file}',family],text=True).split('|')
    assert actual == family, (family,actual)
    result[family]={'family':actual,'path':path,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
print(json.dumps(result))
"""
    fonts = json.loads(command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
                               "--entrypoint", "python3", candidate["pdf_worker"]["image_id"], "-I", "-c", font_code]).stdout)
    return {"ok": True, "controller_package": actual["path"], "checker_files": actual["files"], "consumer_core_sha": core,
            "workflow_sha": candidate["consumer_integration"]["site_deploy_workflow_sha"],
            "pdf_producer_sha": candidate["pdf_worker"]["source_revision"], "fonts": fonts}


def negative_cases(project, sources, candidate, results, launcher, output):
    before = tree_hashes(project / "sandbox")
    env = clean_environment()
    missing_consumer = command([str(launcher), "serve", "--image", candidate["controller"]["image_id"]], env=env, expected=2)
    assert "requires --project" in missing_consumer.stderr
    wrong_controller = command([str(launcher), "serve", "--project", str(project), "--image", candidate["controller"]["image_id"],
                                "--expected-image-id", "sha256:"+"0"*64], env=env, expected=None)
    assert wrong_controller.returncode and "does not match" in wrong_controller.stderr
    missing_image = command([str(launcher), "serve", "--project", str(project), "--image", "sha256:"+"0"*64], env=env, expected=None)
    assert missing_image.returncode and "not prepared" in missing_image.stderr
    def cli(source, run="installed-01"):
        return json.loads(command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-pdf-build",
            "--source", source, "--version", "2026-10-candidate", "--run", run], expected=None).stdout)
    source = project / sources["alumnat"]
    original = source.read_bytes()
    source.write_bytes(original + b"\nChanged author request.\n")
    changed = cli(sources["alumnat"])
    assert changed["ok"] is False and "different inputs" in changed["error"], changed
    assert source.read_bytes() == original + b"\nChanged author request.\n" and tree_hashes(project / "sandbox") == before
    source.write_bytes(original)  # Restore only this explicitly created test source.
    font_path = project / results["alumnat"]["job"] / "inputs/practice.tex"
    original_font = font_path.read_bytes()
    altered = original_font.replace(b"DejaVu Serif", b"Definitely Missing Candidate Font")
    assert altered != original_font
    font_path.write_bytes(altered)
    font_mismatch = cli(sources["alumnat"])
    assert font_mismatch["ok"] is False and "modified" in font_mismatch["error"], font_mismatch
    assert font_path.read_bytes() == altered
    font_path.write_bytes(original_font)
    source.write_bytes(original + b"\n![Absent](assets/teaching/missing.png)\n")
    missing_input = cli(sources["alumnat"], "missing-input")
    assert missing_input["ok"] is False and tree_hashes(project / "sandbox") == before, missing_input
    source.write_bytes(original)
    assert tree_hashes(project / "sandbox") == before
    wrong_worker = asyncio.run(live_candidate(project, sources, candidate, launcher, output, wrong_worker=True))
    assert tree_hashes(project / "sandbox") == before

    # A real font-availability failure using the same prepared PDF toolchain.
    # Only the isolated test worker sees this empty fontconfig; the approved
    # template and successful jobs remain byte-identical.
    font_case = output / "missing-font"
    shutil.copytree(project / results["alumnat"]["job"] / "inputs", font_case / "inputs")
    (font_case / "outputs").mkdir()
    (font_case / "inputs/fontconfig.xml").write_text('<?xml version="1.0"?><fontconfig><reset-dirs/><dir>/source/no-fonts</dir><cachedir>/tmp/font-cache</cachedir></fontconfig>')
    name = "practice98-font-" + uuid.uuid4().hex
    OWNED_CONTAINERS.add(name)
    args = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--name", name,
            "--user", f"{os.getuid()}:{os.getgid()}", "--cpus", "2", "--memory", "2g", "--pids-limit", "256", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912,mode=1777",
            "--env", "HOME=/tmp", "--env", "FONTCONFIG_FILE=/source/fontconfig.xml", "--env", "FONTCONFIG_PATH=/source",
            "--mount", bind(font_case / "inputs", "/source", True), "--mount", bind(font_case / "outputs", "/out"),
            "--entrypoint", "python3", candidate["pdf_worker"]["image_id"], "/source/render_practice.py"]
    failed_font = command(args, expected=None)
    assert failed_font.returncode != 0 and not (font_case / "outputs/LLEGIU-ME.pdf").exists(), failed_font.stdout
    log = (font_case / "outputs/render.log").read_text(errors="replace")
    assert "fontspec" in log and "cannot be found" in log, log[-6000:]
    assert command(["docker", "container", "inspect", name], expected=None).returncode != 0
    return {"consumer_required": missing_consumer.stderr, "controller_image_mismatch": wrong_controller.stderr, "missing_image": missing_image.stderr,
            "changed_source": changed, "snapshot_font_mismatch": font_mismatch, "missing_input": missing_input,
            "worker_image_mismatch": wrong_worker, "missing_font": {"returncode": failed_font.returncode,
                "log": str(font_case / "outputs/render.log"), "log_sha256": file_hash(font_case / "outputs/render.log")}}


def rebuild_snapshot(project, result, candidate, output):
    # Reconstruct outside the consumer, with only the complete retained effective
    # snapshot and the pinned PDF image. No original site/factory is mounted.
    target = output / ("relocated-" + result["audience"])
    shutil.copytree(project / result["job"] / "inputs", target / "inputs")
    (target / "outputs").mkdir()
    name = "practice98-rebuild-" + uuid.uuid4().hex
    OWNED_CONTAINERS.add(name)
    command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--name", name,
             "--user", f"{os.getuid()}:{os.getgid()}", "--cpus", "2", "--memory", "2g", "--pids-limit", "256", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912,mode=1777",
             "--env", "HOME=/tmp", "--env", "SOURCE_DATE_EPOCH=0", "--env", "FORCE_SOURCE_DATE=1", "--env", "TZ=UTC",
             "--mount", bind(target / "inputs", "/source", True), "--mount", bind(target / "outputs", "/out"),
             "--entrypoint", "python3", candidate["pdf_worker"]["image_id"], "/source/render_practice.py"])
    rebuilt = target / "outputs/LLEGIU-ME.pdf"
    assert file_hash(rebuilt) == file_hash(project / result["pdf"]), "Relocated offline reconstruction changed the PDF bytes"
    return {"ok": True, "pdf": str(rebuilt), "sha256": file_hash(rebuilt), "input_hashes": tree_hashes(target / "inputs")}


def check_jekyll_exclusion(project, candidate):
    name = "practice98-web-" + uuid.uuid4().hex
    OWNED_CONTAINERS.add(name)
    code = """import json,os,shutil,subprocess
from pathlib import Path
source=Path('/tmp/site-source'); destination=Path('/tmp/site-output')
shutil.copytree('/consumer',source,ignore=shutil.ignore_patterns('.git'))
environment={**os.environ,'HOME':'/tmp','JEKYLL_ENV':'production','UNALTRAWEB_RENDER_DIAGRAMS':'0'}
result=subprocess.run(['python3','-m','unaltraweb_mcp.bundler_runtime','--project',str(source),'--core','/opt/unaltraweb','--',
    'bundle','exec','jekyll','build','--config','/opt/unaltraweb/_config.yml,_config.yml','--disable-disk-cache','--destination',str(destination)],
    cwd=source,env=environment,capture_output=True,text=True,timeout=120)
assert result.returncode == 0, result.stdout+'\\n'+result.stderr
files=[path.relative_to(destination).as_posix() for path in destination.rglob('*') if path.is_file()]
assert files
assert not any(path.split('/')[0] in {'practiques','sandbox','dist'} or path.endswith('LLEGIU-ME.pdf') for path in files), files
for path in destination.rglob('*.html'):
    assert 'MARCADOR-SOLUCIO-DOCENT' not in path.read_text(errors='replace')
print(json.dumps({'ok':True,'files':len(files),'private_roots_absent':True,'teacher_marker_absent':True}))
"""
    result = command(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--name", name,
                      "--user", f"{os.getuid()}:{os.getgid()}", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
                      "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,nosuid,nodev,size=536870912,mode=1777",
                      "--mount", bind(project, "/consumer", True), "--entrypoint", "python3", candidate["controller"]["image_id"], "-I", "-c", code])
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert file_hash(args.candidate) == args.sha256, "Candidate manifest sender hash differs"
    candidate = json.loads(args.candidate.read_bytes())
    assert candidate["source_revision"] == APPROVED_SOURCE and candidate["published"] is False
    base, output = args.candidate.resolve().parent, args.output.resolve()
    assert output.is_relative_to(ROOT / "tmp")
    output.mkdir(parents=True, exist_ok=False)
    wheel = base / candidate["wheel"]["path"]
    assert file_hash(wheel) == candidate["wheel"]["sha256"]
    assert file_hash(base / candidate["source_archive"]["path"]) == candidate["source_archive"]["sha256"]
    assert file_hash(base / candidate["controller_archive"]["path"]) == candidate["controller_archive"]["sha256"]
    loaded = command(["docker", "image", "load", "--input", str(base / candidate["controller_archive"]["path"])], timeout=300)
    assert candidate["controller"]["image_id"] in loaded.stdout, loaded.stdout
    for key in ("controller", "pdf_worker"):
        selected = candidate[key]
        observed = docker_json("image", selected["image_id"])
        assert observed["Id"] == selected["image_id"]
        assert observed["Config"]["Labels"]["org.opencontainers.image.revision"] == selected["source_revision"]
    environment = output / "installed"
    venv.EnvBuilder(with_pip=True).create(environment)
    python, launcher = environment / "bin/python", environment / "bin/unaltraweb-mcp-docker"
    requirements = output / "requirements.txt"
    requirements.write_text(f"{wheel.as_uri()} --hash=sha256:{candidate['wheel']['sha256']}\n")
    command([str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--require-hashes", "-r", str(requirements)], env=clean_environment())
    location = command([str(python), "-I", "-c", "import unaltraweb_mcp; print(unaltraweb_mcp.__file__)"], env=clean_environment()).stdout.strip()
    assert str(environment) in location and "site-packages" in location
    installed_manifest = command([str(launcher), "manifest"], env=clean_environment()).stdout
    assert "manual_practice_pdf_build" in installed_manifest and "job_storage" not in installed_manifest
    evidence = {"candidate_sha256": args.sha256, "installed_package": location, "archive_load": loaded.stdout,
                "tuple": tuple_check(candidate), "consumers": []}
    for index, (course, codes) in enumerate([("Cartografia de prova", ["990011", "990012"]), ("Anàlisi territorial de prova", ["990021"])]):
        project = output / f"consumer-{index+1}"
        sources, authored = fixture(project, course, codes)
        review = output / f"review-{index+1}"
        review.mkdir()
        observed = asyncio.run(live_candidate(project, sources, candidate, launcher, review))
        pdfs = {audience: inspect_pdf(project, result, course, codes, audience) for audience, result in observed["reads"].items()}
        relocated = {audience: rebuild_snapshot(project, result, candidate, review) for audience, result in observed["reads"].items()}
        negative = negative_cases(project, sources, candidate, observed["reads"], launcher, review) if index == 0 else None
        student = observed["reads"]["alumnat"]
        cli = command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-pdf-build",
            "--source", sources["alumnat"], "--version", student["version"], "--run", "installed-01"])
        assert json.loads(cli.stdout)["state"] == "current", cli.stdout
        make = runtime_args(project, candidate, uuid.uuid4().hex, entrypoint="make")
        image_index = make.index(candidate["controller"]["image_id"])
        make[image_index:image_index] = ["--env", "PRACTICE_SOURCE=" + sources["docent"], "--env", "PRACTICE_VERSION=" + student["version"],
                                        "--env", "PRACTICE_RUN=installed-01"]
        rendered = command(make + ["--silent", "--no-print-directory", "-C", "/opt/unaltraweb", "manual-practice-pdf-build"])
        assert json.loads(rendered.stdout)["state"] == "current", rendered.stdout
        web = check_jekyll_exclusion(project, candidate)
        assert authored == {name: file_hash(project / name) for name in authored}
        assert not any((project / name).exists() for name in ("_site", "dist", "assets/pdf"))
        record = {"project": str(project), "authored_hashes": authored, "runtime": observed, "pdfs": pdfs,
                  "negative": negative, "relocated": relocated, "jekyll_private_exclusion": web,
                  "cli": json.loads(cli.stdout), "make": json.loads(rendered.stdout)}
        save(review / "evidence.json", record)
        evidence["consumers"].append(record)
        print(json.dumps({"consumer": index+1, "ok": True, "pdfs": {key: value["pdf_sha256"] for key, value in pdfs.items()}}), flush=True)
    evidence["ok"] = True
    for identifier in sorted(OWNED_CONTAINERS):
        absence = command(["docker", "container", "inspect", identifier], expected=None)
        assert absence.returncode and ("No such object" in absence.stderr or "No such container" in absence.stderr), absence.stderr
    evidence["cleanup"] = {"observed_absent": sorted(OWNED_CONTAINERS), "job_volumes_created": 0,
                           "retained": "PDFs, input snapshots, receipts, negative logs, candidate image/archive and installed test environment"}
    save(output / "evidence.json", evidence)
    print(json.dumps({"ok": True, "evidence": str(output / "evidence.json"), "sha256": file_hash(output / "evidence.json")}, indent=2))


if __name__ == "__main__":
    main()
