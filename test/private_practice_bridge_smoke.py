"""Explicit local-only acceptance: public Web image -> prepared private QGIS CLI.

No image acquisition, private wheel installation, model-algorithm execution or
consumer code is used. The input is the previously owned synthetic fixture.
Public CI does not invoke this driver and reports private checks as not_run.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import venv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from practice_candidate_smoke import clean_environment, payload, runtime_args, command, tree_hashes, OWNED_CONTAINERS
from practice_editions_smoke import extract, verify_final_members, observed_reopen, bad_final_zips

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tmp/practice-editions-98/native-acceptance-01/consumer"
SEAL = "7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507"
PDF = "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b"
PDF_ID = "sha256:618163d3f924439792b2306617bd9612f566c5881166102fa544b4e782d569fa"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n")


def public_args(project, candidate, entrypoint="unaltraweb-mcp"):
    arguments = runtime_args(project, candidate, uuid.uuid4().hex, entrypoint=entrypoint)
    arguments[arguments.index("--memory")+1] = "4g"
    arguments[arguments.index("--pids-limit")+1] = "512"
    return arguments


def bridge_args(project, candidate, request):
    code = "import json,os,sys; from pathlib import Path; from unaltraweb_mcp.practice_verifier import call; r=json.loads(sys.argv[1]); print(json.dumps(call(Path(os.environ['MCP_CONSUMER_WORKSPACE']),r.pop('operation'),**r)))"
    return public_args(project, candidate, "python3") + ["-I", "-B", "-c", code, json.dumps(request)]


async def compose(project, config, candidate, launcher, contract, out):
    session = uuid.uuid4().hex
    workers = {"manual_pdf": {"reference": PDF, "expected_image_id": PDF_ID},
               "practice_verifier": {"reference": contract["controller"]["image_id"], "expected_image_id": contract["controller"]["image_id"]}}
    parameters = StdioServerParameters(command=str(launcher), args=["serve", "--project", str(project),
        "--image", candidate["controller"]["image_id"], "--expected-image-id", candidate["controller"]["image_id"],
        "--session-id", session, "--managed", "--offline", "--worker-images", json.dumps(workers)], env=clean_environment(), cwd="/tmp/opencode")
    with (out/"mcp.log").open("x") as log:
        async with stdio_client(parameters, errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as client:
                await client.initialize()
                identity = payload(await client.call_tool("runtime_identity", {}))
                assert identity["runtime"]["workers"]["practice_verifier"]["observed_image_id"] == contract["controller"]["image_id"]
                plan = payload(await client.call_tool("manual_practice_compose", {"config": config, "dry_run": True}))
                assert plan["ok"] and plan["gis_verifier"]["origin"]["kind"] == "prepared-image", plan
                result = payload(await client.call_tool("manual_practice_compose", {"config": config}))
                assert result["ok"], result
                await client.call_tool("runtime_drain", {"confirm": True})
    cid = identity["runtime"]["container"]["id"]
    ended = json.loads(command([str(launcher), "session-status", "--project", str(project), "--session-id", session, "--container-id", cid]).stdout)
    assert ended["resources_released"]
    return result, {"identity": identity, "plan": plan, "ended": ended}


def reopen_zip(project, spec, result, who, candidate, contract, proof):
    package = result["packages"][who]
    archive = project / result["path"] / package["path"]
    extracted = proof / who / "extracted"
    extract(archive, extracted)
    verify_final_members(extracted, result, who)
    pdf = archive.parent / package["pdf"]["path"]
    assert pdf.read_bytes() == (extracted / "LLEGIU-ME.pdf").read_bytes()
    assert sha(pdf) == package["pdf"]["sha256"]
    assert sha(archive.parent/package["pdf"]["receipt"]) == package["pdf"]["receipt_sha256"]
    reading = result["readings"][who]
    original_receipt = project/reading["receipt"]
    assert sha(original_receipt) == reading["receipt_sha256"]
    original = json.loads(original_receipt.read_bytes())
    artifact = Path(reading["pdf"]).relative_to(Path(reading["receipt"]).parent).as_posix()
    assert sha(pdf) == reading["pdf_sha256"] == original["artifacts"][artifact]
    receiver = proof / who / "reopen-workspace"
    shutil.copytree(project / Path(spec["gis"]["bundle"]).parent, receiver / "bundle")
    for row in result["closure"][who]:
        target = receiver / "bundle" / row["path"]
        target.unlink()
        shutil.copyfile(extracted / row["path"], target)
    selected = "initial-project" if who == "alumnat" else "resolved-project"
    request = {"operation": "check", "bundle": "bundle/bundle.json", "sha256": spec["gis"]["sha256"], "selected": [selected]}
    checked = json.loads(command(bridge_args(receiver, candidate, request), timeout=180).stdout)
    packet = {row["path"]: {"sha256": row["sha256"], "bytes": row["bytes"]} for row in checked["result"]["closure"]}
    for name, row in packet.items():
        assert sha(extracted/name) == row["sha256"] and (extracted/name).stat().st_size == row["bytes"]
    request.update(operation="reopen", output="sandbox/final-zip-reopen.json")
    opened, mounts = observed_reopen(bridge_args(receiver, candidate, request), receiver, packet, contract["engine"]["image_id"])
    assert opened["result"]["ok"] and opened["origin"]["execution"]["cleanup"]["resources_released"], opened
    if who == "alumnat":
        embedded = next(row for row in opened["result"]["embedded_projects"] if row["project"] == "inici")
        assert embedded["state"]["crs"] == "EPSG:25831"
        rasters = {row["subdataset"]: row for row in embedded["state"]["layers"] if row.get("subdataset")}
        assert {(key, row["width"], row["height"], row["bands"]) for key, row in rasters.items()} == {("mdt", 600, 640, 1), ("ortofoto", 600, 640, 3)}
    else:
        native = opened["result"]["projects"]["resolved-project"]["native"]
        assert set(native["themes"]) == {"Principal", "Referència"}
        layout = next(row for row in native["layouts"] if row["name"] == "Infografia base")
        maps = {row["id"]: row for row in layout["maps"]}
        assert abs(maps["principal"]["scale"]-15000) < .01 and abs(maps["localitzador"]["scale"]-75000) < .01
        assert maps["principal"]["extent"] != maps["localitzador"]["extent"]
    return {"zip": str(archive), "pdf": str(pdf), "pdf_sha256": sha(pdf), "zip_sha256": sha(archive),
            "check": checked, "reopen": opened, "engine_observations": mounts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to(ROOT / "tmp")
    out.mkdir()
    probe = json.loads(args.public_probe.read_bytes())
    contract = json.loads((ROOT / "src/unaltraweb_mcp/practice-verifier-runtime.json").read_bytes())
    candidate = {"controller": {"image_id": probe["image_id"]}, "pdf_worker": {"reference": PDF, "image_id": PDF_ID}}
    original_hashes = tree_hashes(SOURCE)
    project = out/"consumer"
    project.mkdir()
    for name in (".git", "assets", "practiques"):
        shutil.copytree(SOURCE/name, project/name)
    for name in (".gitignore", "_config.yml"):
        shutil.copyfile(SOURCE/name, project/name)
    shutil.copytree(SOURCE/"sandbox/gis/native", project/"sandbox/gis/native")
    config = "practiques/candidate/edition-native.json"
    old_spec = json.loads((project/config).read_bytes())
    spec = copy.deepcopy(old_spec)
    spec["version"] = "2026-10-private-runtime-r1"
    spec["gis"]["verifier"] = {"origin": "prepared-image", "package": contract["provider"]["name"],
        "version": contract["provider"]["version"], "revision": contract["provider"]["installed_revision"],
        "image_id": contract["controller"]["image_id"], "schema_sha256": contract["profiles"]["qgis-practice-v2"]}
    (project/config).write_text(json.dumps(spec, sort_keys=True, indent=2)+"\n")
    before = {str(path.relative_to(project)): sha(path) for path in (project/"practiques").rglob("*") if path.is_file()}
    install = out/"public-client"
    venv.EnvBuilder(with_pip=False).create(install)
    command(["python3", "-m", "pip", "--python", str(install/"bin/python"), "install", "--no-index", "--no-deps", "--no-compile", probe["wheel"]["path"]])
    launcher = install/"bin/unaltraweb-mcp-docker"
    check_code = "import importlib.util,json; from importlib.metadata import distributions; p={d.metadata['Name'].lower().replace('_','-') for d in distributions()}; assert 'unaltracaptura-qgis' not in p; assert importlib.util.find_spec('veure_qgis_mcp') is None; print(json.dumps({'private_package_present':False}))"
    absence = json.loads(command(public_args(project, candidate, "python3") + ["-I", "-B", "-c", check_code]).stdout)
    result, live = asyncio.run(compose(project, config, candidate, launcher, contract, out))
    proof = out/"proof"
    proof.mkdir()
    reopens = {who: reopen_zip(project, spec, result, who, candidate, contract, proof) for who in ("alumnat", "docent")}
    negatives = bad_final_zips(project, result, proof, dependency_path="payload/data/municipalities.shx")
    dist_before = tree_hashes(project/"dist")
    failures = {}
    for name in ("legacy", "wrong-image", "wrong-profile", "producer-is-not-verifier", "missing-runtime"):
        changed = copy.deepcopy(spec)
        changed["version"] += "-" + name
        if name == "legacy":
            changed["gis"]["verifier"] = old_spec["gis"]["verifier"]
        elif name == "wrong-image":
            changed["gis"]["verifier"]["image_id"] = "sha256:" + "0"*64
        elif name == "wrong-profile":
            changed["gis"]["verifier"]["schema_sha256"] = contract["profiles"]["qgis-practice-v1"]
        elif name == "producer-is-not-verifier":
            changed["gis"]["verifier"]["revision"] = contract["release"]["practice_producer_revision"]
        (project/config).write_text(json.dumps(changed))
        arguments = public_args(project, candidate)
        if name == "missing-runtime":
            arguments[-1:-1] = ["-e", "PRACTICE_VERIFIER_IMAGE=sha256:"+"0"*64]
        checked = command(arguments + ["--project", str(project), "mcp", "manual-practice-compose", "--config", config, "--dry-run"], expected=None)
        value = json.loads(checked.stdout)
        assert checked.returncode and value["ok"] is False, value
        if name == "missing-runtime":
            assert "hub preparation" in value["error"] and "no pull/build" in value["error"]
        failures[name] = value
        assert tree_hashes(project/"dist") == dist_before
    (project/config).write_text(json.dumps(spec, sort_keys=True, indent=2)+"\n")
    v1_project = ROOT/"tmp/practice-editions-98/rc2-v1-acceptance-01/consumer-1"
    v1 = json.loads(command(bridge_args(v1_project, candidate, {"operation": "check", "bundle": "sandbox/gis/delivery/bundle.json",
        "sha256": "abd44b02101243a3ddfd492357c2882e6a3f62248dde192616159944c41056a4", "selected": ["initial-project"]})).stdout)
    assert v1["result"]["profile"] == "qgis-practice-v1"
    assert tree_hashes(SOURCE) == original_hashes
    assert {str(path.relative_to(project)): sha(path) for path in (project/"practiques").rglob("*") if path.is_file()} == before
    for name in OWNED_CONTAINERS:
        absent = command(["docker", "container", "inspect", "--format", "{{.Id}}", name], expected=None)
        assert absent.returncode and ("No such container" in absent.stderr or "No such object" in absent.stderr)
    evidence = {"ok": True, "public_probe": probe, "no_private_package_in_web": absence,
                "runtime_contract": contract, "composition": result, "live": live, "reopens": reopens,
                "legacy_v1_check": v1, "negative_final_zips": negatives, "refusals": failures,
                "original_rc2_sources_unchanged": True, "native_checks": "passed locally; not a public-CI claim"}
    save(out/"evidence.json", evidence)
    print(json.dumps({"ok": True, "evidence": str(out/"evidence.json"), "sha256": sha(out/"evidence.json")}, indent=2))


if __name__ == "__main__":
    main()
