"""Opt-in installed Web/private-QGIS acceptance using a tiny synthetic example.

Inputs are already acquired, hash-verified provider release assets and its pinned
portable-practice example. This driver neither acquires images nor edits clients.
Public CI never runs it. All products, failed attempts and evidence are retained.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import uuid
import venv
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from practice_candidate_smoke import OWNED_CONTAINERS, clean_environment, command, fixture, inspect_pdf, payload, tree_hashes
from practice_editions_smoke import extract, observed_reopen, save, sha, verify_final_members
from private_practice_bridge_smoke import PDF, PDF_ID, bridge_args, public_args
from test_mcp_practice_resources import assert_practice_resources

ROOT = Path(__file__).resolve().parents[1]


def release_assets(assets, contract):
    release = contract["release"]
    receipt_path = assets / release["receipt"]["file"]
    assert receipt_path.stat().st_size == release["receipt"]["bytes"]
    assert sha(receipt_path) == release["receipt"]["sha256"]
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["name"] == contract["provider"]["name"]
    assert receipt["version"] == contract["provider"]["version"]
    assert release["tag"] == "v" + receipt["version"]
    assert receipt["source"] == {"repository": release["repository"], "revision": "git:" + release["source_commit"]}
    assert release["receipt"]["url"] == release["repository"] + "/releases/download/" + release["tag"] + "/release.json"
    assert receipt["producer_revision"] == release["practice_producer_revision"]
    assert {key: receipt["wheel"][key] for key in ("bytes", "sha256")} == release["wheel"]
    assert receipt["mcp_image"]["id"] == contract["controller"]["image_id"]
    assert receipt["qgis_image"] == contract["engine"]["image_id"]
    for row in (receipt["wheel"], receipt["mcp_image"]["archive"]):
        assert Path(row["file"]).name == row["file"]
        path = assets / row["file"]
        assert not path.is_symlink() and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
    for profile, expected in contract["profiles"].items():
        assert sha(assets / (profile + ".schema.json")) == expected
    with zipfile.ZipFile(assets / receipt["wheel"]["file"]) as wheel:
        metadata = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
        assert len(metadata) == 1
        text = wheel.read(metadata[0]).decode()
        assert "\nName: unaltracaptura-qgis\n" in text and "\nVersion: " + receipt["version"] + "\n" in text
    # Read Docker-save metadata only. Never extract/load/retag the private archive.
    with tarfile.open(assets / receipt["mcp_image"]["archive"]["file"], "r:gz") as archive:
        members = archive.getmembers()
        entries = {member.name: member for member in members}
        assert len(members) == len(entries) < 10000
        def small_json(name):
            entry = entries[name]
            assert entry.isfile() and entry.size < 2 * 1024**2
            raw = archive.extractfile(entry).read()
            return json.loads(raw), raw
        manifest, _ = small_json("manifest.json")
        assert len(manifest) == 2
        images = {}
        for row in manifest:
            config, raw = small_json(row["Config"])
            image = "sha256:" + hashlib.sha256(raw).hexdigest()
            assert image not in images
            assert (config["os"], config["architecture"]) == ("linux", "amd64")
            assert row["Layers"] and all(entries[name].isfile() for name in row["Layers"])
            images[image] = {"layers": len(row["Layers"]), "source": config.get("config", {}).get("Labels", {}).get("org.opencontainers.image.revision")}
        assert set(images) == {contract["controller"]["image_id"], contract["engine"]["image_id"]}
        assert images[contract["controller"]["image_id"]]["source"] == contract["controller"]["observed_oci_source_revision"]
    return {"receipt": receipt, "receipt_sha256": sha(receipt_path), "archive_images": images}


async def compose(project, config, candidate, launcher, contract, output):
    session = uuid.uuid4().hex
    workers = {"manual_pdf": {"reference": PDF, "expected_image_id": PDF_ID},
               "practice_verifier": {"reference": contract["controller"]["image_id"], "expected_image_id": contract["controller"]["image_id"]}}
    image = candidate["controller"]["image_id"]
    parameters = StdioServerParameters(command=str(launcher), args=["serve", "--project", str(project),
        "--image", image, "--expected-image-id", image, "--session-id", session, "--managed", "--offline",
        "--worker-images", json.dumps(workers)], env=clean_environment(), cwd=str(output))
    with (output / "mcp.log").open("x") as log:
        async with stdio_client(parameters, errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as client:
                await client.initialize()
                await assert_practice_resources(client)
                identity = payload(await client.call_tool("runtime_identity", {}))
                save(output / "live-identity.json", identity)
                assert identity["runtime"]["workers"]["practice_verifier"]["observed_image_id"] == contract["controller"]["image_id"]
                assert "qgis" not in identity["runtime"]["workers"]
                preview = payload(await client.call_tool("manual_practice_compose", {"config": config, "dry_run": True}))
                assert preview["ok"], preview
                result = payload(await client.call_tool("manual_practice_compose", {"config": config}))
                save(output / "compose.json", result)
                assert result["ok"], result
                repeated = payload(await client.call_tool("manual_practice_compose", {"config": config}))
                assert not repeated["ok"] and "already exists" in repeated["error"], repeated
                drained = payload(await client.call_tool("runtime_drain", {"confirm": True}))
    ended = json.loads(command([str(launcher), "session-status", "--project", str(project), "--session-id", session,
                               "--container-id", identity["runtime"]["container"]["id"]], env=clean_environment()).stdout)
    assert ended["resources_released"], ended
    return result, {"identity": identity, "plan": preview, "repeat": repeated, "drain": drained, "detach": ended}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--qgis-fixture", type=Path, required=True)
    parser.add_argument("--qgis-python", type=Path, required=True)
    parser.add_argument("--web-wheel", type=Path, required=True)
    parser.add_argument("--web-image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.absolute()
    assert out.resolve() == out and out.is_relative_to(ROOT / "tmp")
    out.mkdir()
    raw = (ROOT / "src/unaltraweb_mcp/practice-verifier-runtime.json").read_bytes()
    contract = json.loads(raw)
    provenance = release_assets(args.assets, contract)
    save(out / "provenance.json", provenance)
    with zipfile.ZipFile(args.web_wheel) as wheel:
        assert wheel.read("unaltraweb_mcp/practice-verifier-runtime.json") == raw
        assert not any(name.startswith(("veure_qgis_mcp/", "unaltracaptura_annotations/")) for name in wheel.namelist())
    candidate = {"controller": {"image_id": args.web_image}, "pdf_worker": {"reference": PDF, "image_id": PDF_ID}}
    project = out / "consumer"
    readings, _ = fixture(project, "Compatibilitat QGIS sintètica", ["999109"])
    source = json.loads((args.qgis_fixture / "source.json").read_bytes())
    assert source["source"] == contract["release"]["source_commit"] and source["synthetic"] is True
    inputs = project / "practiques/synthetic-gis"
    inputs.mkdir()
    for row in source["files"]:
        assert Path(row["file"]).name == row["file"]
        path = args.qgis_fixture / row["file"]
        assert path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
        shutil.copyfile(path, inputs / row["file"])
    schemas = {}
    for profile in contract["profiles"]:
        request = {"operation": "schema", "profile": profile}
        schemas[profile] = json.loads(command(bridge_args(project, candidate, request)).stdout)
        assert schemas[profile]["origin"]["execution"]["cleanup"]["resources_released"]
    code = "import hashlib,importlib.util,json; from unaltraweb_mcp.practice_verifier import CONTRACT; assert importlib.util.find_spec('veure_qgis_mcp') is None; print(json.dumps({'descriptor_sha256':hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),'private_package_present':False}))"
    packaged = json.loads(command(public_args(project, candidate, "python3") + ["-I", "-B", "-c", code]).stdout)
    assert packaged["descriptor_sha256"] == hashlib.sha256(raw).hexdigest()
    generated = command([str(args.qgis_python), "-I", "-B", "-m", "veure_qgis_mcp.cli", "practice-run", "--workspace", str(project),
                         "--request", "practiques/synthetic-gis/activity.json", "--output", "sandbox/gis/run01"], env=clean_environment(), timeout=900)
    native = json.loads(generated.stdout)
    save(out / "native-run.json", native)
    assert native["ok"], native
    assert native["source_inputs_unchanged"] and len(native["checks"]) == 8
    assert native["producer"]["version"] == contract["provider"]["version"]
    assert native["producer"]["revision"] == contract["provider"]["installed_revision"]
    bundle = project / "sandbox/gis/run01/bundle.json"
    manifest = json.loads(bundle.read_bytes())
    spec = {"schema_version": 1, "kind": "unaltraweb-practice-edition", "slug": "candidate", "language": "ca", "version": "2099-synthetic-109",
        "gis": {"profile": "qgis-practice-v1", "bundle": bundle.relative_to(project).as_posix(), "sha256": sha(bundle),
                "verifier": {"origin": "prepared-image", "package": contract["provider"]["name"], "version": contract["provider"]["version"],
                    "revision": contract["provider"]["installed_revision"], "image_id": contract["controller"]["image_id"],
                    "schema_sha256": contract["profiles"]["qgis-practice-v1"]},
                "teacher_only": [row["id"] for row in manifest["files"] if row["role"] in {"resolved-data", "resolved-project", "capture", "capture-original", "annotation"}]},
        "selection": {"alumnat": ["initial-project"], "docent": ["resolved-project"]},
        "readings": {who: {"source": path, "approved_sha256": sha(project / path)} for who, path in readings.items()}}
    config = "practiques/candidate/edition.json"
    save(project / config, spec)
    authored = ["_config.yml", ".gitignore", config, *readings.values(), *(p.relative_to(project).as_posix() for p in (project / "assets").rglob("*.png"))]
    command(["git", "-C", str(project), "add", "--", *authored])
    originals = tree_hashes(project / "practiques")
    installed = out / "web-client"
    venv.EnvBuilder(with_pip=False).create(installed)
    command(["python3", "-m", "pip", "--python", str(installed / "bin/python"), "install", "--no-index", "--no-deps", "--no-compile", str(args.web_wheel)], env=clean_environment())
    assert (installed / "bin/unaltraweb-mcp-docker").is_file()
    result, live = asyncio.run(compose(project, config, candidate, installed / "bin/unaltraweb-mcp-docker", contract, out))
    products = {}
    for who, selected in (("alumnat", "initial-project"), ("docent", "resolved-project")):
        package = result["packages"][who]
        archive = project / result["path"] / package["path"]
        assert sha(archive) == package["sha256"]
        extracted = out / (who + "-packet")
        extract(archive, extracted)
        verify_final_members(extracted, result, who)
        pdf = inspect_pdf(project, result["readings"][who], "Compatibilitat QGIS sintètica", ["999109"], who)
        assert sha(extracted / "LLEGIU-ME.pdf") == package["pdf"]["sha256"] == pdf["pdf_sha256"]
        receiver = out / (who + "-receiver")
        shutil.copytree(bundle.parent, receiver / "bundle")
        for row in result["closure"][who]:
            shutil.copyfile(extracted / row["path"], receiver / "bundle" / row["path"])
        request = {"operation": "check", "bundle": "bundle/bundle.json", "sha256": sha(bundle), "selected": [selected]}
        checked = json.loads(command(bridge_args(receiver, candidate, request)).stdout)
        packet = {row["path"]: {"sha256": row["sha256"], "bytes": row["bytes"]} for row in checked["result"]["closure"]}
        for name, row in packet.items():
            assert sha(extracted / name) == row["sha256"]
        request.update(operation="reopen", output="proof/reopen.json")
        reopened, engines = observed_reopen(bridge_args(receiver, candidate, request), receiver, packet, contract["engine"]["image_id"])
        assert reopened["result"]["ok"] and reopened["origin"]["execution"]["cleanup"]["resources_released"]
        products[who] = {"pdf": pdf, "zip_sha256": sha(archive), "checked": checked, "reopened": reopened, "engines": engines}
    assert tree_hashes(project / "practiques") == originals
    for name in sorted(OWNED_CONTAINERS):
        absent = command(["docker", "container", "inspect", name], expected=None)
        assert absent.returncode and ("No such container" in absent.stderr or "No such object" in absent.stderr), name
    evidence = {"ok": True, "scope": "synthetic technical acceptance, not real-consumer adoption or teaching approval",
        "web_image": args.web_image, "web_wheel_sha256": sha(args.web_wheel), "descriptor_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": provenance, "provider_fixture": source, "schemas": schemas, "packaged": packaged,
        "native_run": native, "composition": result, "live": live, "products": products, "authored_inputs_preserved": True,
        "outer_cli_containers_absent": sorted(OWNED_CONTAINERS)}
    save(out / "evidence.json", evidence)
    print(json.dumps({"ok": True, "evidence": str(out / "evidence.json"), "sha256": sha(out / "evidence.json")}, indent=2))


if __name__ == "__main__":
    main()
