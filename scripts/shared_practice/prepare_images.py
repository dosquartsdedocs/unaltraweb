"""Explicit SDK image preparation; no operation/CLI call invokes this implicitly."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from unaltraweb_mcp.shared_jobs import runtime_contract, sdk


def execute(command, timeout=600, *, env=None):
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:] or result.stdout[-6000:])
    return result.stdout.strip()


def prepare(output, endpoint, daemon_id, sdk_wheel, web_wheel, *, pull_bases=False):
    expected = runtime_contract()
    sdk()
    assert hashlib.sha256(sdk_wheel.read_bytes()).hexdigest() == expected["wheel"]["sha256"]
    assert output.is_absolute() and output.resolve() == output and output.parent.is_dir()
    assert endpoint.startswith("unix:///") and len(daemon_id) > 0
    docker = ["docker", "--host", endpoint]
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("DOCKER_", "BUILDX_"))}
    environment["DOCKER_CONFIG"] = str(output / "docker-client")
    def run(command, timeout=600):
        return execute(command, timeout, env=environment)
    assert run([*docker, "info", "--format", "{{.ID}}"], 30) == daemon_id
    with zipfile.ZipFile(web_wheel) as wheel:
        for name in wheel.namelist():
            if Path(name).parent.as_posix() == "unaltraweb_mcp" and Path(name).suffix in {".py", ".json"}:
                assert wheel.read(name) == (ROOT / "src" / name).read_bytes()
    output.mkdir(mode=0o700)
    (output / "docker-client").mkdir(mode=0o700)
    import gacontext_runtime
    helper_source = Path(gacontext_runtime.__file__).parent / "controller_helper"
    helper = output / "helper"
    helper.mkdir()
    shutil.copyfile(sdk_wheel, helper / sdk_wheel.name)
    shutil.copyfile(helper_source / "Dockerfile", helper / "Dockerfile")
    domain = output / "domain"
    domain.mkdir()
    (domain / "packages").mkdir()
    for path in (sdk_wheel, web_wheel):
        shutil.copyfile(path, domain / "packages" / path.name)
    controls = domain / "controls"
    controls.mkdir()
    names = ["mcp-factory.yml", "scripts/manual/build_pdf.py", "scripts/manual/render_practice.py",
             "src/unaltraweb_mcp/practice_pdf.py"]
    for folder in ("scripts/manual/templates", "scripts/manual/filters"):
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*") if p.is_file())
    hashes = {}
    for name in sorted(names):
        target = controls / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        target.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    hashes["web-wheel"] = hashlib.sha256(web_wheel.read_bytes()).hexdigest()
    domain_sha = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    bases = {
        "helper": "python:3.12-slim-bookworm@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d",
        "controller": "ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:8183e7117f5902fc0ad4d930b757d874b2da1f93d5ef4db102ae4c1b03e357a3",
        "pdf": "ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf@sha256:1bb3f2dafd741e96c28639ec1cc8ccaeb81cbaa73e649f787c0b4ef59997bd4b"}
    images, base_ids = {}, {}
    for role, reference in bases.items():
        if pull_bases:
            run([*docker, "pull", reference])
        base_ids[role] = run([*docker, "image", "inspect", "--format", "{{.Id}}", reference], 30)
        context = helper if role == "helper" else domain
        dockerfile = helper / "Dockerfile" if role == "helper" else ROOT / ("scripts/manual/Dockerfile.shared" if role == "pdf" else "scripts/shared_practice/Dockerfile.controller")
        tag = "unaltraweb/shared-" + role + ":" + domain_sha[:32]
        # The preparation output is create-only; existing tags must be absent.
        observed = subprocess.run([*docker, "image", "inspect", tag], capture_output=True, text=True, env=environment)
        if not observed.returncode or "No such image" not in observed.stderr:
            raise RuntimeError("Cannot prove this preparation tag is unused: " + tag)
        command = [*docker, "build", "--network=none", "--pull=false", "--build-arg", "BASE_IMAGE=" + reference,
            "--build-arg", "SDK_CODE_SHA256=" + expected["code_sha256"], "--build-arg", "PACKAGE_CODE_SHA256=" + expected["code_sha256"],
            "--build-arg", "DOMAIN_SHA256=" + domain_sha, "--build-arg", "HELPER_SHA256=" + hashlib.sha256((helper_source / "volume_io.py").read_bytes()).hexdigest(),
            "--tag", tag, "--file", str(dockerfile), str(context)]
        built = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=600)
        with (output / (role + ".log")).open("x") as stream:
            stream.write(built.stdout + built.stderr)
        if built.returncode:
            raise RuntimeError("Image preparation failed; inspect " + str(output / (role + ".log")))
        row, = json.loads(run([*docker, "image", "inspect", tag], 30))
        assert row["Config"]["Labels"]["io.context.gacontext.runtime-code-sha256"] == expected["code_sha256"]
        identity = json.loads(run([*docker, "run", "--rm", "--pull=never", "--network=none", "--entrypoint", "python3",
            row["Id"], "-I", "-B", "-m", "gacontext_runtime", "package"], 60))
        assert identity["code_sha256"] == expected["code_sha256"] and identity["version"] == expected["version"]
        images[role] = {"image_id": row["Id"], "tag": tag, "sdk": identity}
    result = {"ok": True, "published": False, "endpoint": endpoint, "daemon_id": daemon_id, "sdk": expected,
              "images": images, "base_images": base_ids, "source_hashes": hashes, "domain_sha256": domain_sha}
    with (output / "prepared.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--daemon-id", required=True)
    parser.add_argument("--sdk-wheel", type=Path, required=True)
    parser.add_argument("--web-wheel", type=Path, required=True)
    parser.add_argument("--pull-bases", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.endpoint, args.daemon_id, args.sdk_wheel, args.web_wheel, pull_bases=args.pull_bases), indent=2))
