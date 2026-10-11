"""Installed Web composition of the owner-delivered native QGIS rc2 fixture.

Reads only public JSON observations; it does not parse native GIS formats.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
from pathlib import Path
import uuid
import venv

from practice_editions_smoke import sha, save, run, extract, compose_mcp, reopen_final_zip, bad_final_zips
from practice_candidate_smoke import fixture, inspect_pdf, runtime_args, command, tree_hashes, check_jekyll_exclusion, OWNED_CONTAINERS
from practice_links_smoke import pdf_links

ROOT = Path(__file__).resolve().parents[1]
TRANSFER = Path("/tmp/opencode/practice32-qgis-0.6.0rc2-round32-n1")
READY_SHA = "49a8887587eb5942aae7aa76b678acd617cec799294c350fe5fc6d344d881a1a"
SEAL = "7f26db5a8cc05af081ea21a65d7d167e05f4b6b1a2a7a6e9b361c91066605507"
DESCRIPTOR_SHA = "3118638d53c63ef2c059d73f744b2ac399aa1f2e2c21f27f0026f3fbbb122df7"


def native_fixture(project, candidate):
    ready_path = TRANSFER / "ready.json"
    assert sha(ready_path) == READY_SHA
    ready = json.loads(ready_path.read_bytes())
    assert ready["ready"] is True
    for row in ready["files"]:
        path = TRANSFER / row["path"]
        assert not path.is_symlink() and path.stat().st_size == row["bytes"] and sha(path) == row["sha256"]
    readings, _ = fixture(project, "Pràctica nativa sintètica", ["99201", "99202"])
    extract(TRANSFER / "native-teaching-1.0.0.fixture.zip", project / "sandbox/gis/native")
    bundle = project / "sandbox/gis/native/bundle.json"
    assert sha(bundle) == SEAL and sha(bundle.parent / "payload/practice.json") == DESCRIPTOR_SHA
    manifest = json.loads(bundle.read_bytes())
    assert len(manifest["files"]) == 42
    files = {row["id"]: row for row in manifest["files"]}
    teacher = project / readings["docent"]
    teacher.write_text(teacher.read_text() + '\n![Resultat natiu](sandbox/gis/native/payload/captures/resolved-project/overview.png "Captura real QGIS.")\n\n'
                       '[Infografia editable](exports/infografia.svg) · [Mapa PDF](exports/infografia.pdf)\n')
    verifier = candidate["gis_profiles"]["qgis-practice-v2"]
    spec = {"schema_version": 1, "kind": "unaltraweb-practice-edition", "slug": "candidate", "language": "ca", "version": "2026-10-native-r1",
            "gis": {"profile": "qgis-practice-v2", "bundle": "sandbox/gis/native/bundle.json", "sha256": SEAL,
                    "verifier": {"package": verifier["package"]["name"], "version": verifier["package"]["version"],
                                 "revision": verifier["package"]["revision"], "schema_sha256": verifier["schema_sha256"],
                                 "wheel_sha256": candidate["gis_wheel"]["sha256"]},
                    "teacher_only": [row["id"] for row in manifest["files"] if row["role"] in {"resolved-data", "resolved-project", "map-svg", "map-pdf", "capture", "capture-original", "annotation"}]},
            "selection": {"alumnat": ["initial-project"], "docent": ["resolved-project", "infographic-svg", "infographic-pdf", "resolved-project-png"]},
            "readings": {who: {"source": source, "approved_sha256": sha(project / source)} for who, source in readings.items()}}
    spec["readings"]["docent"]["bindings"] = [{"reference": "exports/infografia."+suffix, "product": "infographic-"+suffix,
                                                "sha256": files["infographic-"+suffix]["sha256"]} for suffix in ("svg", "pdf")]
    config = "practiques/candidate/edition-native.json"
    save(project / config, spec)
    authored = ["_config.yml", ".gitignore", config, *readings.values(), *(p.relative_to(project).as_posix() for p in (project / "assets").rglob("*.png"))]
    run(["git", "-C", str(project), "add", "--", *authored])
    return spec, config, readings, {path: sha(project/path) for path in authored}


def check_public_native_observations(project, spec, result, reopens, candidate, proof):
    # Exact closures and domain observations originate in the public verifier.
    checks = {}
    for selected_id, expected_count in (("initial-project", 11), ("resolved-project", 9), ("infographic-svg", 2)):
        checked = json.loads(run(runtime_args(project, candidate, uuid.uuid4().hex, entrypoint="unaltracaptura-qgis") + [
            "practice-check", "--workspace", str(project), "--path", spec["gis"]["bundle"], "--sha256", SEAL, "--select", selected_id]))
        assert checked["ok"] and checked["profile"] == "qgis-practice-v2" and len(checked["closure"]) == expected_count, checked
        checks[selected_id] = checked
    native = checks["initial-project"]["native"]
    initial = next(row for row in native["containers"] if row["file"] == "initial-data")
    assert {("project", "inici"), ("raster", "mdt"), ("raster", "ortofoto"), ("style", "1")} <= {
        (member["kind"], member["name"]) for member in initial["members"]}, initial
    assert not any(member["role"] in {"resolved-data", "resolved-project"} for member in initial["members"])
    initial_ids = {row["id"] for row in checks["initial-project"]["closure"]}
    assert {"font-regular", "marker-symbol", "municipalities-shp", "municipalities-shx", "municipalities-dbf",
            "municipalities-prj", "municipalities-cpg", "id-table", "id-table-types"} <= initial_ids
    assert {row["id"] for row in checks["infographic-svg"]["closure"]} == {"font-regular", "infographic-svg"}
    student = reopens["alumnat"]["reopen"]["projects"]["initial-project"]
    embedded = next(row for row in reopens["alumnat"]["reopen"]["embedded_projects"]
                    if row["file"] == "initial-data" and row["project"] == "inici")
    assert embedded["state"]["crs"] == "EPSG:25831"
    assert {layer.get("subdataset") for layer in embedded["state"]["layers"]} >= {"mdt", "ortofoto"}
    rasters = {layer.get("subdataset"): layer for layer in student["layers"] if layer.get("subdataset")}
    for name, bands in (("mdt", 1), ("ortofoto", 3)):
        assert (rasters[name]["width"], rasters[name]["height"], rasters[name]["bands"], rasters[name]["crs"]) == (600, 640, bands, "EPSG:25831")
    assert any(row.get("feature_count") == 22 and row["source"].endswith(".shp") for row in student["layers"])
    resolved = reopens["docent"]["reopen"]["projects"]["resolved-project"]
    assert set(resolved["native"]["themes"]) == {"Principal", "Referència"}
    assert resolved["native"]["theme_layers"]["Principal"] and resolved["native"]["theme_layers"]["Referència"]
    layout = next(row for row in resolved["native"]["layouts"] if row["name"] == "Infografia base")
    maps = {row["id"]: row for row in layout["maps"]}
    assert set(maps) == {"principal", "localitzador"} and maps["principal"]["extent"] != maps["localitzador"]["extent"]
    for identifier, scale in (("principal", 15000), ("localitzador", 75000)):
        row = maps[identifier]
        assert abs(row["scale"]-scale) < .01 and row["crs"] == "EPSG:25831"
        extent = row["extent"]
        assert abs((extent[2]-extent[0])-row["width_mm"]*scale/1000) < .01
        assert abs((extent[3]-extent[1])-row["height_mm"]*scale/1000) < .01
    packet = Path(reopens["docent"]["extracted"])
    final_links = pdf_links(packet / "LLEGIU-ME.pdf")
    targets = {row["target"] for row in final_links if row["kind"] in {"/URI", "/GoToR", "/Launch"}}
    assert {"payload/figures/infografia.svg", "payload/figures/infografia.pdf"} <= targets, final_links
    for name in targets:
        if not name.startswith(("https:", "http:", "mailto:")):
            assert (packet / name).resolve().is_relative_to(packet.resolve()) and (packet / name).is_file(), name
    save(proof / "public-native-observations.json", checks)
    return {"checks": checks, "fresh_embedded_starter": embedded, "fresh_reopened_initial": student,
            "fresh_reopened_resolved": resolved, "final_reading_links": final_links}


def negatives(project, spec, result, candidate, proof):
    before_dist, before_pdf = tree_hashes(project / "dist"), tree_hashes(project / "sandbox/practiques")
    failures = {}
    def invoke(value, name):
        value = copy.deepcopy(value)
        value["version"] = "negative-native-"+name
        config = f"practiques/candidate/negative-{name}.json"
        save(project / config, value)
        run(["git", "-C", str(project), "add", "--", config])
        command_result = command(runtime_args(project, candidate, uuid.uuid4().hex) + ["--project", str(project), "mcp", "manual-practice-compose", "--config", config], expected=None)
        refused = json.loads(command_result.stdout)
        assert command_result.returncode and refused["ok"] is False, refused
        assert before_dist == tree_hashes(project / "dist") and before_pdf == tree_hashes(project / "sandbox/practiques")
        failures[name] = refused
        return refused
    wrong = copy.deepcopy(spec)
    wrong["gis"]["verifier"]["schema_sha256"] = candidate["gis_profiles"]["qgis-practice-v1"]["schema_sha256"]
    assert "identity/schema" in invoke(wrong, "v1-pin-for-v2")["error"]
    wrong = copy.deepcopy(spec)
    wrong["gis"]["profile"] = "qgis-practice-v1"
    assert "identity/schema" in invoke(wrong, "v1-profile-v2-pin")["error"]
    wrong["gis"]["verifier"]["schema_sha256"] = candidate["gis_profiles"]["qgis-practice-v1"]["schema_sha256"]
    assert "requested explicit selection" in invoke(wrong, "wrong-bundle-profile")["error"]
    wrong = copy.deepcopy(spec)
    wrong["gis"]["verifier"]["wheel_sha256"] = "0"*64
    assert "wheel hash" in invoke(wrong, "wrong-wheel")["error"]
    wrong = copy.deepcopy(spec)
    wrong["selection"]["alumnat"].append("infographic-svg")
    assert "teacher-only" in invoke(wrong, "teacher-export")["error"]
    font = project / "sandbox/gis/native/payload/data/fonts/DejaVuSans.ttf"
    font_bytes = font.read_bytes()
    font.unlink()
    invoke(spec, "missing-font")
    font.write_bytes(font_bytes)
    sidecar = project / "sandbox/gis/native/payload/data/municipalities.shx"
    raw = sidecar.read_bytes()
    sidecar.write_bytes(bytes([raw[0]^1])+raw[1:])
    invoke(spec, "altered-sidecar")
    assert sidecar.read_bytes() != raw
    sidecar.write_bytes(raw)
    archive_failures = bad_final_zips(project, result, proof, dependency_path="payload/data/municipalities.shx")
    save(proof / "native-negatives.json", failures)
    return {"composition": failures, "final_zip": archive_failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.candidate) == args.sha256
    candidate = json.loads(args.candidate.read_bytes())
    assert candidate["gis_profiles"]["qgis-practice-v2"]["package"]["version"] == "0.6.0rc2"
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / "tmp")
    output.mkdir(parents=True, exist_ok=False)
    environment = output / "installed"
    venv.EnvBuilder(with_pip=True).create(environment)
    wheel = args.candidate.resolve().parent / candidate["web_wheel"]["path"]
    assert sha(wheel) == candidate["web_wheel"]["sha256"]
    (output / "requirements.txt").write_text(f"{wheel.as_uri()} --hash=sha256:{sha(wheel)}\n")
    run([str(environment / "bin/python"), "-m", "pip", "install", "--no-index", "--no-deps", "--require-hashes", "-r", str(output / "requirements.txt")])
    project, proof = output / "consumer", output / "proof"
    proof.mkdir()
    spec, config, readings, originals = native_fixture(project, candidate)
    composed = asyncio.run(compose_mcp(project, config, candidate, environment / "bin/unaltraweb-mcp-docker", proof, readings))
    result = composed["result"]
    assert result["gis_verifier"]["profile"] == "qgis-practice-v2"
    assert len(result["closure"]["alumnat"]) == 11
    pdfs = {who: inspect_pdf(project, result["readings"][who], "Pràctica nativa sintètica", ["99201", "99202"], who) for who in readings}
    reopens = {who: reopen_final_zip(project, spec, result, who, candidate, proof) for who in readings}
    native = check_public_native_observations(project, spec, result, reopens, candidate, proof)
    negative = negatives(project, spec, result, candidate, proof)
    web = check_jekyll_exclusion(project, candidate)
    assert originals == {path: sha(project / path) for path in originals}
    for identifier in sorted(OWNED_CONTAINERS):
        absent = command(["docker", "container", "inspect", identifier], expected=None)
        assert absent.returncode and ("No such container" in absent.stderr or "No such object" in absent.stderr)
    evidence = {"ok": True, "candidate_sha256": args.sha256, "profile": "qgis-practice-v2", "ready_sha256": READY_SHA,
        "composition": composed, "pdfs": pdfs, "final_zip_reopen": reopens, "public_native": native,
        "negatives": negative, "jekyll": web, "original_hashes": originals,
        "cleanup": {"test_containers_absent": sorted(OWNED_CONTAINERS), "job_volumes_created": 0}}
    save(output / "evidence.json", evidence)
    print(json.dumps({"ok": True, "evidence": str(output / "evidence.json"), "sha256": sha(output / "evidence.json"), "packages": result["packages"]}, indent=2))


if __name__ == "__main__":
    main()
