"""Opt-in installed GIS -> shared PDF/ZIP acceptance using one owned daemon.

Common policy remains in the pinned SDK and its evidence-retention harness.
Only the qualified synthetic QGIS bundle is consumed; no GIS calculation runs.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from scripts.shared_practice.prepare_images import prepare
from unaltraweb_mcp import artifact_handoff_v1 as h, shared_editions
from unaltraweb_mcp.practice_editions import _copy_selected
from unaltraweb_mcp.editorial_sources import canonical, digest
from shared_practice_smoke import save, payload
from test_practice_pdf import CONFIG


def prepare_consumer(project, source, sha):
    h.check(str(source), "bundle", "bundle.json", sha)
    manifest = h.parse_json((source / "bundle.json").read_bytes())
    with closing(h.Workspace(str(source))) as workspace:
        records = [{"path": "bundle.json", "sha256": sha, "bytes": (source / "bundle.json").stat().st_size}, *manifest["files"]]
        for row in records:
            target = project / "incoming/gis" / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                _copy_selected(workspace, {**row, "source": row["path"]}, output)
        workspace.recheck()
    (project / "_config.yml").write_bytes(canonical(CONFIG))
    (project / ".gitignore").write_text("incoming/\nsandbox/\ndist/\n")
    (project / "assets").mkdir()
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="#f8f7f2"/>'
           b'<image width="1" height="1" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="/>'
           b'<text x="5" y="25">Editable synthetic template</text></svg>')
    (project / "assets/template.svg").write_bytes(svg)
    by_id = {row["id"]: row for row in manifest["files"]}
    spec = {"kind": "unaltraweb-practice-edition", "schema_version": 1, "slug": "demo", "version": "shared-v3", "language": "ca",
        "gis": {"profile": "qgis-practice-v3", "bundle": "incoming/gis/bundle.json", "sha256": sha,
                "verifier": shared_editions.verifier_pin(shared_editions.verifier_contract())},
        "selection": {"alumnat": ["initial-project"], "docent": ["resolved-project"]}, "readings": {},
        "resources": [{"path": "assets/template.svg", "destination": "resources/template.svg", "sha256": digest(svg),
                       "role": "editable-infographic", "recipients": ["alumnat", "docent"], "dependencies": []}]}
    for who, identifier in (("alumnat", "initial-project"), ("docent", "resolved-project")):
        source_path = f"practiques/demo/ca/{who}/LLEGIU-ME.md"
        path = project / source_path
        path.parent.mkdir(parents=True)
        raw = (f"---\ntitle: Synthetic {who} reading\nlang: ca\ncontent_status: draft\n---\n\n# Project\n\n"
               "[Open the selected project](project.qgz).\n\n[Editable template](template.svg).\n\n"
               "Observe the synthetic coverage and describe the relationship between its layers.\n").encode()
        path.write_bytes(raw)
        spec["readings"][who] = {"source": source_path, "approved_sha256": digest(raw), "bindings": [
            {"reference": "project.qgz", "product": identifier, "sha256": by_id[identifier]["sha256"]},
            {"reference": "template.svg", "path": "assets/template.svg", "sha256": digest(svg), "destination": "resources/template.svg"}]}
    (project / "edition.json").write_bytes(canonical(spec))
    refused = copy.deepcopy(spec)
    refused["selection"]["docent"] = ["resolved-project", "atlas-pdf"]
    (project / "edition-atlas.json").write_bytes(canonical(refused))
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    subprocess.run(["git", "add", "--", ".gitignore", "_config.yml", "edition.json", "edition-atlas.json", "practiques", "assets"], cwd=project, check=True)
    return spec


async def native_mcp(root, fixture, context, prepared, environment, command):
    session = uuid.uuid4().hex
    probe = fixture.registry.root / "receiver/probe"
    probe.mkdir()
    selected = probe / "context.json"
    save(selected, context)
    selected.chmod(0o600)
    workspace, socket = str(fixture.workspace), context["docker_endpoint"].removeprefix("unix://")
    name = "unaltraweb-stdio-" + session
    args = ["--host", context["docker_endpoint"], "run", "--rm", "--pull=never", "--interactive", "--network=none", "--read-only",
            "--cpus=2", "--memory=4g", "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=536870912", "--user=0:0", "--name=" + name,
            "--label=io.context.mcp-factory=unaltraweb", "--label=io.context.mcp-role=stdio",
            "--label=io.context.mcp-session=" + session, "--label=io.context.mcp-project=" + digest(workspace.encode())[:16]]
    for path, readonly in ((workspace, True), (context["service_root"], True), (str(selected), True), (socket, False)):
        args += ["--mount", "type=bind,source=" + path + ",target=" + path + (",readonly" if readonly else "")]
    for key, value in {"HOME": "/tmp", "DOCKER_HOST": context["docker_endpoint"], "UNALTRAWEB_SHARED_JOB_CONTEXT": str(selected),
        "MCP_CONSUMER_WORKSPACE": workspace, "UNALTRAWEB_DOCKER_ROOT": workspace, "UNALTRAWEB_RUNTIME_SESSION": session,
        "UNALTRAWEB_MCP_IMAGE": prepared["images"]["controller"]["image_id"], "UNALTRAWEB_EXPECTED_IMAGE_ID": prepared["images"]["controller"]["image_id"],
        "UNALTRAWEB_MANAGED_RUNTIME": "1", "UNALTRAWEB_RUNTIME_NETWORK": "none", "MANUAL_PDF_IMAGE": context["pdf_image"]}.items():
        args += ["--env", key + "=" + value]
    args += [prepared["images"]["controller"]["image_id"], "--project", workspace, "mcp", "serve"]
    with (probe / "mcp.log").open("x") as log:
        async with stdio_client(StdioServerParameters(command="docker", args=args, env=environment), errlog=log) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=__import__("datetime").timedelta(seconds=1200)) as client:
                await client.initialize()
                plan = payload(await client.call_tool("manual_practice_compose", {"config": "edition.json", "dry_run": True}))
                assert plan["ok"] and plan["state"] == "planned" and not plan["native_selection_verified"], plan
                rejected = payload(await client.call_tool("manual_practice_compose", {"config": "edition-atlas.json"}))
                save(probe / "rejected.json", rejected)
                assert not rejected["ok"] and rejected.get("stage") == "web-composition", rejected
                result = payload(await client.call_tool("manual_practice_compose", {"config": "edition.json"}))
                save(probe / "built.json", result)
                assert result["ok"] and result["state"] == "sealed", result
                repeated = payload(await client.call_tool("manual_practice_compose", {"config": "edition.json"}))
                assert repeated["ok"] and repeated["reused"] and repeated["product"] == result["product"], repeated
                original = (fixture.workspace / "assets/template.svg").read_bytes()
                (fixture.workspace / "assets/template.svg").write_bytes(original + b"<!-- changed during retry -->")
                changed = payload(await client.call_tool("manual_practice_compose", {"config": "edition.json"}))
                (fixture.workspace / "assets/template.svg").write_bytes(original)
                assert not changed["ok"], changed
                request = {"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "status",
                           "job_id": context["job_id"], "registry_id": context["registry_id"]}
                current = payload(await client.call_tool("job_storage", {"request": request}))
                state = current["state"]
                closed = payload(await client.call_tool("job_storage", {"request": {**request, "operation": "quiesce",
                    "expected_revision": state["revision"], "expected_epoch": state["epoch"]}}))
                assert closed["ok"] and closed["state"]["phase"] == "closed", closed
                identity = payload(await client.call_tool("runtime_identity", {}))
                assert identity["package"]["mode"] == "installed" and not identity["package"]["drift"]
                await client.call_tool("runtime_drain", {"confirm": True})
                readonly = payload(await client.call_tool("job_storage", {"request": request}))
                assert readonly["ok"] and readonly["read_only"]
    absent = command(["docker", "--host", context["docker_endpoint"], "container", "inspect", name], check=False)
    assert absent.returncode and "No such" in absent.stderr
    return {"ok": True, "plan": plan, "rejected": rejected, "build": result, "replay": repeated,
            "changed_source_refused": changed, "quiesce": closed, "identity": identity, "readonly_after_drain": readonly}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "evidence-dir", "common-harness", "sdk-wheel", "web-wheel", "qgis-bundle", "verifier-archive"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    assert digest(args.common_harness.read_bytes()) == "83429ab874d79e72ec558ff63e84c99ac73bdf766a48a483e139506fc3dc91d3"
    spec = importlib.util.spec_from_file_location("qualified_common_harness", args.common_harness)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    from gacontext_runtime.client import Client
    from gacontext_runtime.testing import FixtureTask
    root, retained = args.output, args.evidence_dir
    assert root.is_absolute() and root.resolve() == root and root.parent == Path("/tmp/opencode") and len(str(root / "docker.sock")) < 104
    assert retained.resolve() == retained and retained.is_relative_to(ROOT / "tmp") and retained.parent.is_dir()
    assert args.qgis_bundle.resolve() == args.qgis_bundle and args.qgis_bundle.is_relative_to(ROOT / "tmp")
    root.mkdir(mode=0o700)
    retained.mkdir(mode=0o700)
    for folder in ("home", "runtime", "docker-client", "dist"):
        (root / folder).mkdir(mode=0o700)
    for path in (args.sdk_wheel, args.web_wheel):
        shutil.copyfile(path, root / "dist" / path.name)
    endpoint = "unix://" + str(root / "docker.sock")
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("DOCKER_", "BUILDX_", "MCP_", "UNALTRAWEB_")) and key not in {"PYTHONPATH", "PYTHONHOME"}}
    environment.update(HOME=str(root / "home"), DOCKER_CONFIG=str(root / "docker-client"), PYTHONDONTWRITEBYTECODE="1")
    unit = "unaltraweb-edition-" + uuid.uuid4().hex + ".service"
    proof = {"ok": False, "synthetic_only": True, "unit": unit, "endpoint": endpoint}
    save(root / "owner.json", proof)
    save(retained / "run-intent.json", proof)
    save(root / "daemon.json", {"data-root": str(root / "data"), "exec-root": str(root / "exec"), "hosts": [endpoint], "pidfile": str(root / "dockerd.pid"),
        "storage-driver": "overlay2", "bridge": "none", "iptables": False, "ip6tables": False, "ip-forward": False, "ip-masq": False,
        "userland-proxy": False, "log-level": "error"})
    def command(argv, *, timeout=180, check=True, input=None):
        return common.execute(argv, env=environment, cwd=root, timeout=timeout, check=check, input=input)
    docker = ["/usr/bin/docker", "--host", endpoint]
    services, started = [], False
    try:
        command(["systemd-run", "--user", "--unit=" + unit, "--collect", "--property=Delegate=yes", "--property=MemoryMax=6G",
            "--property=CPUQuota=400%", "--property=TasksMax=2048", "--property=KillMode=control-group", "--property=TimeoutStopSec=30",
            "--property=RuntimeMaxSec=2400", "--setenv=HOME=" + str(root / "home"), "--setenv=XDG_RUNTIME_DIR=" + str(root / "runtime"),
            "--setenv=DBUS_SESSION_BUS_ADDRESS=" + os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus"),
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR=" + str(root / "rootlesskit"), "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns",
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=none", "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=true",
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_FLAGS=", "--setenv=_DOCKERD_ROOTLESS_CHILD=", "/usr/bin/dockerd-rootless.sh", "--config-file", str(root / "daemon.json")])
        started = True
        deadline, info = time.monotonic() + 45, None
        while time.monotonic() < deadline:
            response = command([*docker, "info", "--format", "{{json .}}"], timeout=5, check=False)
            if response.returncode == 0 and common.daemon_ready(json.loads(response.stdout)):
                info = json.loads(response.stdout)
                break
            time.sleep(.25)
        assert info and "name=rootless" in info["SecurityOptions"] and not info["Containers"] and not info["Images"]
        prepared = prepare(root / "prepared", endpoint, info["ID"], args.sdk_wheel, args.web_wheel, pull_bases=True)
        contract = shared_editions.verifier_contract()
        command([*docker, "image", "load", "--input", str(args.verifier_archive)], timeout=180)
        observed, = json.loads(command([*docker, "image", "inspect", contract["image_id"]]).stdout)
        assert observed["Config"]["Labels"]["io.context.gacontext.runtime-code-sha256"] == contract["sdk_code_sha256"]
        proof.update(prepared=prepared, private_verifier=contract)
        prefix = [sys.executable, "-I", "-B", "-m", "gacontext_runtime"]
        registry, service = root / "registry", root / "service"
        command([*prefix, "controls", "init", "--registry", str(registry)])
        command([*prefix, "init", "--root", str(service), "--runtime-registry", str(registry)])
        client = Client(service)
        def start_service(number):
            with (root / f"service-{number}.log").open("xb") as log:
                child = subprocess.Popen([*prefix, "serve", "--root", str(service)], env=environment, cwd=root, stdout=log, stderr=subprocess.STDOUT)
            services.append(child)
            end = time.monotonic() + 20
            while time.monotonic() < end:
                try:
                    identity = client.identity()
                    if identity.get("ok"):
                        return child, identity
                except (FileNotFoundError, ConnectionRefusedError):
                    pass
                time.sleep(.1)
            raise RuntimeError("Owned shared service failed to start")
        child, identity = start_service(1)
        def checked(method, **params):
            result = client.call(method, **params)
            assert result.get("ok"), result
            return result
        checked("jobs.configure", helper_image=prepared["images"]["helper"]["image_id"], docker_endpoint=endpoint, expected_daemon_id=info["ID"])
        raw = (ROOT / "mcp-job-storage.json").read_bytes()
        (root / "provider.json").write_bytes(raw)
        checked("jobs.provider-register", descriptor=str(root / "provider.json"), expected_sha=digest(raw),
                images=[prepared["images"]["pdf"]["image_id"], contract["image_id"]])
        fixture = FixtureTask(client, root / "fixture-a", "unaltraweb", synthetic=True)
        job = fixture.allocate()
        second = fixture.join("second-edition-client")
        assert fixture.allocate(second)["id"] == job["id"]
        prepare_consumer(fixture.workspace, args.qgis_bundle, "c3fcba723808303ba0aaaddd72af3cdb87a0cc2eab151859813208a58c48d295")
        context = {"kind": "unaltraweb.shared-job-context", "schema_version": 1, "workspace": str(fixture.workspace), "service_root": str(service),
            "docker_endpoint": endpoint, "daemon_id": info["ID"], "registry_id": job["state"]["registry_id"], "job_id": job["id"],
            "task_id": fixture.record["task_id"], "owner_id": fixture.record["owners"][0], "pdf_image": prepared["images"]["pdf"]["image_id"],
            "edition_verifier_image": contract["image_id"], "worker_user": f"{os.getuid()}:{os.getgid()}"}
        original = {p.relative_to(fixture.workspace).as_posix(): digest(p.read_bytes()) for p in fixture.workspace.rglob("*") if p.is_file() and ".git" not in p.parts}
        proof["native"] = asyncio.run(native_mcp(root, fixture, context, prepared, environment, command))
        assert original == {p.relative_to(fixture.workspace).as_posix(): digest(p.read_bytes()) for p in fixture.workspace.rglob("*") if p.is_file() and ".git" not in p.parts}
        assert not any((fixture.workspace / name).exists() for name in ("sandbox", "tmp", "dist", "_site"))
        assert fixture.close_owner(fixture.record["owners"][0])["other_users_preserved"]
        fixture.close_owner(second)
        pending = fixture.call("jobs.inspect", job_id=job["id"])["job"]["state"]
        assert pending["holds"] and pending["products"] and sorted(row["state"] for row in pending["volumes"]) == ["absent", "verified"]
        child.kill()
        child.wait(timeout=20)
        replacement, restarted = start_service(2)
        assert restarted["instance_id"] != identity["instance_id"]
        result = fixture.finish()
        retention, = result["retentions"]
        proof["delivered"] = shared_editions.verify_delivered_edition(fixture.registry.root / "receiver", retention, proof["native"]["build"]["product"])
        relocation = root / "fixture-b/receiver"
        relocation.parent.mkdir()
        shutil.copytree(fixture.registry.root / "receiver", relocation)
        proof["relocated"] = shared_editions.verify_delivered_edition(relocation, retention, proof["native"]["build"]["product"])
        failed = proof["native"]["rejected"]["worker"]["recovery_path"] + "/edition-error.txt"
        failed_path = fixture.registry.root / "receiver" / retention["destination"]["path"] / "payload/files" / failed
        assert b"not classroom delivery files" in failed_path.read_bytes()
        proof["required_control_refusal"] = {"retained_path": failed, "sha256": digest(failed_path.read_bytes())}
        assert not command([*docker, "container", "ls", "--all", "--quiet"]).stdout.strip()
        assert not command([*docker, "volume", "ls", "--quiet"]).stdout.strip()
        proof.update(ok=True, task=result, originals_unchanged=True, same_slot_reused=True, pending_products_protected=True,
                     common_service_restarted=True, zero_workers=True, zero_job_volumes=True)
        save(root / "w1-proof.json", proof)
        expected = {*prepared["base_images"].values(), *(row["image_id"] for row in prepared["images"].values()), contract["image_id"]}
        proof["test_cache_retirement"] = common.retire_test_cache(root, retained, command, docker, info["ID"], expected)
        command(["systemctl", "--user", "stop", unit], timeout=60)
        ledger = service / "w1"
        snapshot = lambda: {p.relative_to(ledger).as_posix(): digest(p.read_bytes()) for p in ledger.rglob("*") if p.is_file()}
        before = snapshot()
        status = client.job_storage(str(fixture.workspace), "unaltraweb", {"kind": "gacontext.job-storage-request", "schema_version": 1,
            "operation": "status", "registry_id": context["registry_id"], "job_id": context["job_id"]})
        assert status["ok"] and status["read_only"] and not status["changed"] and before == snapshot()
        proof["readonly_without_daemon"] = status
        checked("service.stop", expected_instance_id=restarted["instance_id"])
        assert replacement.wait(timeout=20) == 0
        proof["daemon_stopped"] = True
    except Exception as error:
        proof.update(ok=False, error=str(error))
        raise
    finally:
        for child in services:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=20)
        if started:
            command(["systemctl", "--user", "stop", unit], timeout=60, check=False)
            (root / "daemon.log").write_text(command(["journalctl", "--user", "--unit", unit, "--no-pager", "-n", "100"], check=False).stdout)
        save(root / "rootless-proof.json", proof)
        saved = common.retain_evidence(root, retained)
        print(json.dumps({"ok": proof["ok"], "proof": str(root / "rootless-proof.json"), "retained": saved}, indent=2))


if __name__ == "__main__":
    main()
