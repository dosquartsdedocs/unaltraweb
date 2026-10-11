"""Installed recipient-edition acceptance against the owner-delivered GIS fixture."""
from __future__ import annotations

import argparse
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import shutil
import sys
import time
import uuid
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TRANSFER = Path("/tmp/opencode/practice32-qgis-0.6.0rc1-round32-r2")
GIS_IMAGE = "sha256:388d8d441c89232e08f413740e2f7d6c7906304bca64a619f574fb1db5bf1e3f"
BUNDLE_SHA = "abd44b02101243a3ddfd492357c2882e6a3f62248dde192616159944c41056a4"
EXPECTED = {
    "unaltracaptura_qgis-0.6.0rc1-py3-none-any.whl": "82f2c6772fa8bb9aaae08237494af72df7e103038643fd6dfcdcd6f1ac45ed5f",
    "portable-buffer-1.0.0.fixture.zip": "ea6fbae78c93e8e0fc516a513cab246d0af7d36886585beff70cab79a65f762c",
    "receipt.json": "b787deca6c32df65abe82416089663bcd947b57ee68a4164fc457d38c8ce7b3b",
    "candidate.json": "19bc94d24e997571f85866e4f823d43cbfed0f7a2f6088f24324809b997a4e3c",
    "qgis-practice-v1.schema.json": "9bc7f15ede9d67b3e1209c329da13d9fcb08004090d05b27662a43de6edf3445",
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while piece := stream.read(1024*1024):
            h.update(piece)
    return h.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n")


def run(arguments, *, timeout=180, env=None):
    result = subprocess.run(arguments, text=True, capture_output=True, timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError(f"Failed {arguments}: {result.stdout[-6000:]}\n{result.stderr[-6000:]}")
    return result.stdout


def extract(archive_path, target):
    target.mkdir(parents=True, exist_ok=False)
    names, total = set(), 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            name = member.filename
            assert name and not name.startswith("/") and "\\" not in name
            assert all(part not in {"", ".", "..", ".git"} for part in name.rstrip("/").split("/"))
            assert name.casefold() not in names
            names.add(name.casefold())
            assert len(names) <= 10000 and stat.S_IFMT(member.external_attr >> 16) in {0, stat.S_IFREG, stat.S_IFDIR}
            total += member.file_size
            assert member.file_size <= 512*1024**2 and total <= 2*1024**3
            path = target / name
            if member.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, path.open("xb") as dest:
                    while chunk := source.read(65536):
                        dest.write(chunk)


def intake(output):
    ready = json.loads((TRANSFER / "ready.json").read_bytes())
    assert ready["ready"] is True
    for row in ready["files"]:
        path = TRANSFER / row["path"]
        assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], row["path"]
    for name, expected in EXPECTED.items():
        assert sha(TRANSFER / name) == expected, name
    output.mkdir(parents=True, exist_ok=False)
    extract(TRANSFER / "portable-buffer-1.0.0.fixture.zip", output / "delivery")
    assert sha(output / "delivery/bundle.json") == BUNDLE_SHA
    result = json.loads(run(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only",
        "--mount", f"type=bind,source={output},target={output},readonly", "--entrypoint", "unaltracaptura-qgis", GIS_IMAGE,
        "practice-check", "--workspace", str(output), "--path", "delivery/bundle.json", "--sha256", BUNDLE_SHA, "--select", "initial-project"]))
    save(output / "initial-check.json", result)
    save(output / "ready-observation.json", ready)
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def compose_mcp(project, config, candidate, launcher, output, readings):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from practice_candidate_smoke import clean_environment, payload
    image = candidate["controller"]["image_id"]
    params = StdioServerParameters(command=str(launcher), args=["serve", "--project", str(project), "--image", image,
        "--expected-image-id", image, "--managed", "--offline"], env=clean_environment())
    with (output / "mcp.log").open("x") as log:
        async with stdio_client(params, errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as session:
                await session.initialize()
                tools = {tool.name for tool in (await session.list_tools()).tools}
                assert "manual_practice_compose" in tools
                identity = payload(await session.call_tool("runtime_identity", {}))
                assert identity["runtime"]["selected_image_id"] == image and identity["package"]["mode"] == "installed"
                reviews = {}
                for who, source in readings.items():
                    prose = payload(await session.call_tool("prose_check", {"target": source}))
                    assert prose["ok"] and prose["files_checked"] == 1, prose
                    review = payload(await session.call_tool("editorial_review_prepare", {"target": source, "kind": "line"}))
                    assert review["ok"] and review["fragments"] and review["sources"][0]["path"] == source, review
                    recorded = payload(await session.call_tool("editorial_review_record", {"report": {
                        "id": "practice-"+who, "target": source, "kind": "line", "source_digest": review["source_digest"],
                        "reviewer": "Synthetic installed acceptance", "reviewer_kind": "agent", "findings": []}, "expected_revision": review["revision"]}))
                    assert recorded["ok"], recorded
                    reviews[who] = {"prose": prose, "review": review, "recorded": recorded}
                preview = payload(await session.call_tool("manual_practice_compose", {"config": config, "dry_run": True}))
                assert preview["ok"] and not (project / "dist").exists(), preview
                result = payload(await session.call_tool("manual_practice_compose", {"config": config}))
                save(output / "compose-result.json", result)
                assert result["ok"], result
                repeated = payload(await session.call_tool("manual_practice_compose", {"config": config}))
                assert repeated["ok"] is False and "already exists" in repeated["error"], repeated
                await session.call_tool("runtime_drain", {"confirm": True})
    terminated = json.loads(run([str(launcher), "session-status", "--project", str(project), "--session-id", identity["session_id"],
                                 "--container-id", identity["runtime"]["container"]["id"]]))
    assert terminated["resources_released"], terminated
    return {"result": result, "identity": identity, "reviews": reviews, "repeat": repeated, "terminated": terminated}


def edition_fixture(project, candidate, *, legacy, version):
    from practice_candidate_smoke import fixture
    sources, _ = fixture(project, "Mètodes territorials de prova" if legacy else "Cartografia de prova", ["990031" if legacy else "990011"])
    site = json.loads((project / "_config.yml").read_bytes())
    slug = "tigit-projecte-territorial" if legacy else "candidate"
    if legacy:
        changed = {}
        for who, old in sources.items():
            target = f"_practices/tigit-projecte-territorial/ca/{who}/LLEGIU-ME.md"
            (project / target).parent.mkdir(parents=True, exist_ok=True)
            (project / old).rename(project / target)  # Fixture construction, before the authored baseline.
            changed[who] = target
        sources = changed
        site["exclude"].append("_practices/")
        site["unaltraweb"]["practices"] = {"readings": [{"source": source, "slug": slug, "lang": "ca", "recipient": who}
                                                       for who, source in sources.items()]}
    (project / "_config.yml").write_text(json.dumps(site, ensure_ascii=False, indent=2)+"\n")
    extract(TRANSFER / "portable-buffer-1.0.0.fixture.zip", project / "sandbox/gis/delivery")
    teacher = project / sources["docent"]
    teacher.write_text(teacher.read_text() + '\n![Captura real del resultat](sandbox/gis/delivery/payload/captures/resolved-project/overview.png "Captura del productor QGIS.")\n')
    verifier = candidate["gis_verifier"]
    spec = {"kind": "unaltraweb-practice-edition", "schema_version": 1, "slug": slug, "version": version, "language": "ca",
            "gis": {"profile": "qgis-practice-v1", "bundle": "sandbox/gis/delivery/bundle.json", "sha256": BUNDLE_SHA,
                    "verifier": {"package": "unaltracaptura-qgis", "version": verifier["package"]["version"], "revision": verifier["package"]["revision"],
                                 "schema_sha256": verifier["schema_sha256"], "wheel_sha256": candidate["gis_wheel"]["sha256"]},
                    "teacher_only": ["resolved-project", "resolved-data", "resolved-project-svg", "resolved-project-original", "resolved-project-png"]},
            "selection": {"alumnat": ["initial-project"], "docent": ["resolved-project", "resolved-project-svg", "resolved-project-png"]},
            "readings": {who: {"source": source, "approved_sha256": sha(project / source)} for who, source in sources.items()}}
    if legacy:
        poster = project / "_practices/tigit-projecte-territorial/infografia.svg"
        poster.write_text('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="800" height="500">'
                          '<rect width="800" height="500" fill="white"/><g inkscape:label="Text editable"><text x="40" y="60">Síntesi territorial</text>'
                          '<image href="map.png" x="40" y="100" width="640" height="320"/></g></svg>')
        image = poster.with_name("map.png")
        shutil.copyfile(project / "assets/teaching/map.png", image)
        poster.with_name("private-control.py").write_text("# Must not be included merely because it neighbours the SVG\n")
        spec["resources"] = [{"path": poster.relative_to(project).as_posix(), "role": "editable-infographic", "sha256": sha(poster),
            "destination": "resources/infografia.svg", "recipients": ["alumnat", "docent"], "dependencies": [
                {"path": image.relative_to(project).as_posix(), "sha256": sha(image), "destination": "resources/map.png"}]}]
    config = f"practiques/{slug}/edition-{version}.json"
    (project / config).parent.mkdir(parents=True, exist_ok=True)
    save(project / config, spec)
    authored = ["_config.yml", ".gitignore", config, *sources.values(), *(path.relative_to(project).as_posix() for path in (project / "assets").rglob("*.png"))]
    if legacy:
        authored.extend(path.relative_to(project).as_posix() for path in poster.parent.iterdir() if path.is_file())
    run(["git", "-C", str(project), "add", "--", *authored])
    return spec, config, sources, {name: sha(project / name) for name in authored}


def verify_final_members(extracted, result, who):
    rows = [{"path": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in result["closure"][who]]
    rows.extend({"path": row["destination"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in result.get("author_resources", {}).get(who, []))
    rows.extend({"path": row["destination"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in result.get("reading_resources", {}).get(who, []))
    expected = {row["path"]: row for row in rows}
    actual = {path.relative_to(extracted).as_posix() for path in extracted.rglob("*") if path.is_file()}
    assert actual == {*expected, "LLEGIU-ME.pdf"}, "Final ZIP lacks or adds a declared dependency/resource"
    for name, row in expected.items():
        assert sha(extracted / name) == row["sha256"] and (extracted / name).stat().st_size == row["bytes"], "Final ZIP dependency/resource bytes differ: " + name
    return expected


def observed_reopen(arguments, receiver, expected, engine):
    """Observe the REAL engine mounts and hash its selected input packet."""
    from practice_candidate_smoke import command
    observations = []
    project_id = hashlib.sha256(str(receiver).encode()).hexdigest()[:16]
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run, arguments, timeout=180)
        while not future.done():
            ids = command(["docker", "ps", "-q", "--no-trunc", "--filter", "ancestor="+engine,
                           "--filter", "label=io.context.mcp-project="+project_id]).stdout.split()
            for identifier in ids:
                if identifier in {item["id"] for item in observations}:
                    continue
                checked = command(["docker", "container", "inspect", identifier], expected=None)
                if checked.returncode:
                    continue
                info = json.loads(checked.stdout)[0]
                mounts = info["Mounts"]
                packets = []
                for mount in mounts:
                    source = Path(mount["Source"])
                    assert str(source) != str(receiver) and not source.is_relative_to(receiver / "bundle"), "Engine mounted the full private/original bundle"
                    if source.is_relative_to(receiver) and source.is_dir():
                        files = {p.relative_to(source).as_posix(): p for p in source.rglob("*") if p.is_file()}
                        if any(name.endswith(".qgz") for name in files):
                            assert mount["RW"] is False and set(files) == set(expected), (mount, list(files), expected)
                            for name, row in expected.items():
                                assert sha(files[name]) == row["sha256"] and files[name].stat().st_size == row["bytes"], name
                            packets.append({"mount": mount, "files": expected})
                assert packets and info["HostConfig"]["NetworkMode"] == "none", mounts
                observations.append({"id": identifier, "image": info["Image"], "mounts": mounts, "packets_from_final_zip": packets})
            time.sleep(.1)
        result = json.loads(future.result())
    assert observations, "No real QGIS engine packet/mount observation was captured"
    for observed in observations:
        absent = command(["docker", "container", "inspect", observed["id"]], expected=None)
        assert absent.returncode and ("No such container" in absent.stderr or "No such object" in absent.stderr)
    return result, observations


def reopen_final_zip(project, spec, result, who, candidate, proof):
    from practice_candidate_smoke import runtime_args
    zipped = project / result["path"] / result["packages"][who]["path"]
    assert sha(zipped) == result["packages"][who]["sha256"]
    extracted = proof / who / "extracted"
    extract(zipped, extracted)
    verify_final_members(extracted, result, who)
    # Preserve legacy ZIP-only checkpoints; a declared independent PDF must be
    # the same sealed reading, with its own verifiable paired receipt.
    package = result["packages"][who]
    if "pdf" in package:
        delivered = package["pdf"]
        pdf = zipped.parent / delivered["path"]
        assert sha(pdf) == delivered["sha256"] and pdf.stat().st_size == delivered["bytes"]
        assert pdf.read_bytes() == (extracted / "LLEGIU-ME.pdf").read_bytes()
        receipt = zipped.parent / delivered["receipt"]
        assert sha(receipt) == delivered["receipt_sha256"]
        value = json.loads(receipt.read_bytes())
        assert value["recipient"] == who and value["zip"]["sha256"] == package["sha256"]
        assert value["sealed_source"]["sha256"] == delivered["sha256"]
        assert sha(zipped.parent / value["edition_receipt"]["path"]) == value["edition_receipt"]["sha256"]
    expected = {row["path"]: row["sha256"] for row in result["closure"][who]}
    for path, digest in expected.items():
        assert sha(extracted / path) == digest, path
    if who == "alumnat":
        assert not any(row["role"] in {"resolved-project", "resolved-data", "source", "control"} for row in result["closure"][who])
    # The public reopen API consumes a complete seal. Retain its unchanged control
    # evidence privately, but replace *every selected GIS file* from the FINAL ZIP.
    # No pre-ZIP selected file is used in the actual reopen workspace.
    receiver = proof / who / "reopen-workspace"
    shutil.copytree(project / Path(spec["gis"]["bundle"]).parent, receiver / "bundle")
    for name in expected:
        target = receiver / "bundle" / name
        target.unlink()
        shutil.copyfile(extracted / name, target)
    args = runtime_args(receiver, candidate, uuid.uuid4().hex, entrypoint="unaltracaptura-qgis")
    selected_id = "initial-project" if who == "alumnat" else "resolved-project"
    selected = json.loads(run(args+["practice-check", "--workspace", str(receiver), "--path", "bundle/bundle.json", "--sha256", spec["gis"]["sha256"],
                                    "--select", selected_id]))
    # Check the subset the producer will actually hand to QGIS against bytes from
    # the final ZIP before allowing any copied private control evidence nearby.
    packet = {row["path"]: {"sha256": row["sha256"], "bytes": row["bytes"]} for row in selected["closure"]}
    assert set(packet) <= set(expected)
    for name, row in packet.items():
        assert sha(extracted / name) == row["sha256"] and (extracted / name).stat().st_size == row["bytes"]
    args = runtime_args(receiver, candidate, uuid.uuid4().hex, entrypoint="unaltracaptura-qgis")
    request = ["practice-reopen", "--workspace", str(receiver), "--path", "bundle/bundle.json", "--sha256", spec["gis"]["sha256"],
               "--select", selected_id, "--output", "sandbox/final-zip-reopen.json"]
    engine = next(row["revision"] for row in result["gis"]["producer"]["runtimes"] if row["name"] == "qgis")
    reopened, mounts = observed_reopen(args+request, receiver, packet, engine)
    assert reopened["ok"], reopened
    return {"final_zip": str(zipped), "zip_sha256": sha(zipped), "extracted": str(extracted), "selected_hashes_from_zip": expected,
            "reopen": reopened, "engine_observations": mounts,
            "control_evidence": "unchanged complete producer seal; all selected files replaced from final ZIP"}


def bad_final_zips(project, result, proof, dependency_path="payload/data/relief.tif"):
    original = project / result["path"] / result["packages"]["alumnat"]["path"]
    cases = {}
    for mutation in ("removed", "altered"):
        changed = proof / ("final-dependency-"+mutation+".zip")
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(changed, "x", compression=zipfile.ZIP_DEFLATED) as dest:
            for info in source.infolist():
                raw = source.read(info)
                if info.filename == dependency_path:
                    if mutation == "removed":
                        continue
                    raw = bytes([raw[0] ^ 1]) + raw[1:]
                dest.writestr(info.filename, raw)
        recalculated_archive_identity = sha(changed)
        extracted = proof / ("final-dependency-"+mutation)
        extract(changed, extracted)
        assert sha(changed) == recalculated_archive_identity
        try:
            verify_final_members(extracted, result, "alumnat")
        except AssertionError as error:
            cases[mutation] = {"ok": False, "refused": str(error), "zip": str(changed), "recalculated_zip_sha256": recalculated_archive_identity,
                               "original_closure_still_required": result["closure"]["alumnat"], "private_fallback_used": False}
        else:
            raise AssertionError("A newly hashed ZIP bypassed the original required closure")
    save(proof / "final-zip-negatives.json", cases)
    return cases


def negative_compositions(project, spec, candidate, proof):
    from practice_candidate_smoke import runtime_args, command, tree_hashes
    before = tree_hashes(project / "dist")
    pdfs = tree_hashes(project / "sandbox/practiques")
    cases = {}
    def invoke(value, name):
        value = copy.deepcopy(value)
        value["version"] = "negative-"+name
        relative = f"practiques/{spec['slug']}/negative-{name}.json"
        save(project / relative, value)
        run(["git", "-C", str(project), "add", "--", relative])
        called = command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-compose",
                           "--config", relative], expected=None)
        result = json.loads(called.stdout)
        assert called.returncode and result["ok"] is False, result
        assert tree_hashes(project / "dist") == before and tree_hashes(project / "sandbox/practiques") == pdfs, name
        cases[name] = result
        return result

    damaged = project / "sandbox/gis/delivery/payload/sources/activity.py"
    raw = damaged.read_bytes()
    damaged.write_bytes(raw+b"\n# altered unselected source\n")
    invoke(spec, "tampered-bundle")
    assert damaged.read_bytes() == raw+b"\n# altered unselected source\n"
    damaged.write_bytes(raw)
    dependency = project / "sandbox/gis/delivery/payload/data/relief.tif"
    data = dependency.read_bytes()
    dependency.unlink()
    invoke(spec, "missing-closure")
    dependency.write_bytes(data)
    wrong = copy.deepcopy(spec)
    wrong["selection"]["alumnat"] = ["resolved-project"]
    assert "teacher-only" in invoke(wrong, "resolved-student")["error"]
    wrong["selection"]["alumnat"] = ["resolved-project-svg"]
    assert "teacher-only" in invoke(wrong, "teacher-visual")["error"]
    wrong = copy.deepcopy(spec)
    wrong["selection"]["docent"] = ["rebuild"]
    assert "reconstruction" in invoke(wrong, "control-selection")["error"]
    wrong = copy.deepcopy(spec)
    wrong["readings"]["alumnat"], wrong["readings"]["docent"] = wrong["readings"]["docent"], wrong["readings"]["alumnat"]
    assert "mapped" in invoke(wrong, "swapped-readings")["error"]
    wrong = copy.deepcopy(spec)
    wrong["gis"]["verifier"]["wheel_sha256"] = "0"*64
    assert "wheel hash" in invoke(wrong, "wrong-verifier")["error"]
    wrong = copy.deepcopy(spec)
    wrong["readings"]["alumnat"]["approved_sha256"] = "0"*64
    assert "approved source hash" in invoke(wrong, "stale-approval")["error"]
    link = project / "sandbox/gis/linked"
    link.symlink_to(project / "sandbox/gis/delivery", target_is_directory=True)
    wrong = copy.deepcopy(spec)
    wrong["gis"]["bundle"] = "sandbox/gis/linked/bundle.json"
    invoke(wrong, "symlink-bundle")
    save(proof / "negatives.json", cases)
    return cases


def acceptance(candidate_path, expected_sha, output):
    from practice_candidate_smoke import clean_environment, runtime_args, inspect_pdf, check_jekyll_exclusion, OWNED_CONTAINERS, command
    assert sha(candidate_path) == expected_sha
    candidate = json.loads(candidate_path.read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    wheel = candidate_path.parent / candidate["web_wheel"]["path"]
    assert sha(wheel) == candidate["web_wheel"]["sha256"]
    environment = output / "installed"
    venv.EnvBuilder(with_pip=True).create(environment)
    requirements = output / "requirements.txt"
    requirements.write_text(f"{wheel.as_uri()} --hash=sha256:{sha(wheel)}\n")
    run([str(environment / "bin/python"), "-m", "pip", "install", "--no-index", "--no-deps", "--require-hashes", "-r", str(requirements)])
    launcher = environment / "bin/unaltraweb-mcp-docker"
    records = []
    for index in (1, 2):
        project, proof = output / f"consumer-{index}", output / f"proof-{index}"
        proof.mkdir()
        spec, config, sources, authored = edition_fixture(project, candidate, legacy=index == 2, version=f"2026-10-r{index}")
        actual = asyncio.run(compose_mcp(project, config, candidate, launcher, proof, sources))
        result = actual["result"]
        pdfs = {who: inspect_pdf(project, result["readings"][who], "Mètodes territorials de prova" if index == 2 else "Cartografia de prova",
                                 ["990031" if index == 2 else "990011"], who) for who in sources}
        reopened = {who: reopen_final_zip(project, spec, result, who, candidate, proof) for who in sources}
        zip_negatives = bad_final_zips(project, result, proof)
        negatives = negative_compositions(project, spec, candidate, proof) if index == 1 else None
        # A second edition of the SAME GIS job through the public CLI. No
        # consumer wrapper and no GIS computation command is involved.
        alternate = copy.deepcopy(spec)
        alternate["version"] += "-cli"
        alternate_config = f"practiques/{spec['slug']}/edition-cli.json"
        save(project / alternate_config, alternate)
        run(["git", "-C", str(project), "add", "--", alternate_config])
        cli_result = json.loads(run(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-compose",
                                     "--config", alternate_config], timeout=180))
        assert cli_result["ok"] and cli_result["gis"]["job"] == result["gis"]["job"], cli_result
        cli_reopen = {who: reopen_final_zip(project, alternate, cli_result, who, candidate, proof / "cli-edition") for who in sources}
        planned = copy.deepcopy(spec)
        planned["version"] += "-make"
        make_config = f"practiques/{spec['slug']}/edition-make.json"
        save(project / make_config, planned)
        run(["git", "-C", str(project), "add", "--", make_config])
        make = runtime_args(project, candidate, uuid.uuid4().hex, entrypoint="make")
        idx = make.index(candidate["controller"]["image_id"])
        make[idx:idx] = ["--env", "PRACTICE_EDITION_CONFIG="+make_config, "--env", "PRACTICE_DRY_RUN=1"]
        make_result = json.loads(run(make+["--silent", "--no-print-directory", "-C", "/opt/unaltraweb", "manual-practice-compose"]))
        assert make_result["ok"] and make_result["dry_run"] and not (project / make_result["path"]).exists(), make_result
        # Remove only the intentionally created fixture symlink before the
        # read-only Jekyll-copy audit. Producer data and final editions are intact.
        if (project / "sandbox/gis/linked").is_symlink():
            (project / "sandbox/gis/linked").unlink()
        web = check_jekyll_exclusion(project, candidate)
        assert authored == {name: sha(project / name) for name in authored}
        assert not (project / "_site").exists()
        record = {"source_preserved": authored, "api": actual, "pdfs": pdfs, "final_zip_reopen": reopened,
                  "negatives": negatives, "final_zip_negatives": zip_negatives,
                  "cli_edition": cli_result, "cli_zip_reopen": cli_reopen, "make_plan": make_result, "jekyll": web}
        save(proof / "evidence.json", record)
        records.append(record)
        print(json.dumps({"consumer": index, "ok": True, "packages": result["packages"]}), flush=True)
    for identifier in sorted(OWNED_CONTAINERS):
        absent = command(["docker", "container", "inspect", identifier], expected=None)
        assert absent.returncode and ("No such container" in absent.stderr or "No such object" in absent.stderr), absent.stderr
    save(output / "evidence.json", {"ok": True, "candidate_sha256": expected_sha, "consumers": records,
         "cleanup": {"web_test_containers_observed_absent": sorted(OWNED_CONTAINERS), "job_volumes_created": 0,
                     "qgis": "each public producer reopen receipt verifies its exact engine termination"}})
    print(json.dumps({"ok": True, "evidence": str(output / "evidence.json"), "sha256": sha(output / "evidence.json")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.intake:
        intake(args.intake.resolve())
    else:
        acceptance(args.candidate.resolve(), args.sha256, args.output.resolve())
