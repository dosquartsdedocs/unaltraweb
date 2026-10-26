"""Opt-in native Web/shared-SDK acceptance on one fresh bounded rootless daemon.

Uses the pinned common harness for observation and evidence-before-cache-retirement,
the actual installed SDK service/FixtureTask and the native Web MCP tool. Never
selects a production endpoint or a real manual.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.shared_practice.prepare_images import prepare
from unaltraweb_mcp.shared_practices import verify_delivered_pdf
from unaltraweb_mcp.shared_jobs import runtime_contract


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def payload(result):
    if isinstance(getattr(result, "structuredContent", None), dict):
        return result.structuredContent
    return json.loads("\n".join(row.text for row in result.content if hasattr(row, "text")))


async def native_mcp(command, environment, root, fixture, context, images, *, expect_timeout=False):
    source = "practiques/demo/ca/alumnat/LLEGIU-ME.md"
    session = uuid.uuid4().hex
    workspace = str(fixture.workspace)
    selected = root / "web-context.json"
    save(selected, context)
    selected.chmod(0o600)
    docker = ["docker", "--host", context["docker_endpoint"]]
    args = [*docker[1:], "run", "--rm", "--pull=never", "--interactive", "--network=none", "--read-only",
            "--cpus=2", "--memory=4g", "--pids-limit=512", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=536870912", "--user=0:0", "--name=unaltraweb-stdio-" + session,
            "--label=io.context.mcp-factory=unaltraweb", "--label=io.context.mcp-role=stdio",
            "--label=io.context.mcp-session=" + session,
            "--label=io.context.mcp-project=" + hashlib.sha256(workspace.encode()).hexdigest()[:16]]
    socket = context["docker_endpoint"].removeprefix("unix://")
    for path, readonly in ((workspace, True), (context["service_root"], True), (str(selected), True), (socket, False)):
        args += ["--mount", "type=bind,source=" + path + ",target=" + path + (",readonly" if readonly else "")]
    for key, value in {"HOME": "/tmp", "DOCKER_HOST": context["docker_endpoint"], "UNALTRAWEB_SHARED_JOB_CONTEXT": str(selected),
        "MCP_CONSUMER_WORKSPACE": workspace, "UNALTRAWEB_DOCKER_ROOT": workspace, "UNALTRAWEB_RUNTIME_SESSION": session,
        "UNALTRAWEB_MCP_IMAGE": images["controller"]["image_id"], "UNALTRAWEB_EXPECTED_IMAGE_ID": images["controller"]["image_id"],
        "UNALTRAWEB_MANAGED_RUNTIME": "1", "UNALTRAWEB_RUNTIME_NETWORK": "none", "MANUAL_PDF_IMAGE": images["pdf"]["image_id"]}.items():
        args += ["--env", key + "=" + value]
    args += [images["controller"]["image_id"], "--project", workspace, "mcp", "serve"]
    with (root / "web-mcp.log").open("x") as errors:
        async with stdio_client(StdioServerParameters(command="docker", args=args, env=environment), errlog=errors) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing, read_timeout_seconds=__import__("datetime").timedelta(seconds=960)) as client:
                await client.initialize()
                resources = {}
                for uri in ("web://job-storage-provider", "web://shared-runtime"):
                    response = await client.read_resource(uri)
                    resources[uri] = json.loads(response.contents[0].text)
                assert resources["web://shared-runtime"]["code_sha256"] == runtime_contract()["code_sha256"]
                status_request = {"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "status",
                                  "registry_id": context["registry_id"], "job_id": context["job_id"]}
                before = payload(await client.call_tool("job_storage", {"request": status_request}))
                assert before["ok"] and before["read_only"] and not before["changed"]
                plan = payload(await client.call_tool("manual_practice_pdf_build", {"source": source, "version": "synthetic-a7", "dry_run": True}))
                assert plan["ok"] and plan["storage_runtime"] == "gacontext-runtime", plan
                result = payload(await client.call_tool("manual_practice_pdf_build", {"source": source, "version": "synthetic-a7"}))
                save(root / "web-build.json", result)
                observed = {"resources": resources, "before": before, "plan": plan, "build": result}
                if expect_timeout:
                    assert not result["ok"] and result.get("code") in {"shared-worker-failed", "shared-worker-observation-failed"}, result
                    current = payload(await client.call_tool("job_storage", {"request": status_request}))
                    assert current["ok"] and current["state"]["phase"] == "open" and not current["seals"], current
                    observed["pending_after_failure"] = current
                else:
                    assert result["ok"] and result["state"] == "sealed", result
                    repeated = payload(await client.call_tool("manual_practice_pdf_build", {"source": source, "version": "synthetic-a7"}))
                    assert repeated["ok"] and repeated["reused"] and repeated["product"] == result["product"]
                    stale = payload(await client.call_tool("job_storage", {"request": {**status_request, "operation": "seal",
                        "expected_revision": before["state"]["revision"], "expected_epoch": before["state"]["epoch"]}}))
                    assert not stale["ok"] and stale["error"]["code"] == "storage-revision-conflict", stale
                    current = payload(await client.call_tool("job_storage", {"request": status_request}))
                    state = current["state"]
                    closed = payload(await client.call_tool("job_storage", {"request": {**status_request, "operation": "quiesce",
                        "expected_revision": state["revision"], "expected_epoch": state["epoch"]}}))
                    assert closed["ok"] and closed["state"]["phase"] == "closed", closed
                    observed.update(replay=repeated, stale_cas=stale, quiesce=closed)
                identity = payload(await client.call_tool("runtime_identity", {}))
                assert identity["package"]["mode"] == "installed" and not identity["package"]["drift"]
                await client.call_tool("runtime_drain", {"confirm": True})
                after_drain = payload(await client.call_tool("job_storage", {"request": status_request}))
                assert after_drain["ok"] and after_drain["read_only"]
    absent = command([*docker, "container", "inspect", "unaltraweb-stdio-" + session], check=False)
    assert absent.returncode and "No such" in absent.stderr
    return {"ok": True, **observed, "readonly_after_drain": after_drain, "identity": identity,
            "exact_controller_absent": identity["runtime"]["container"]["id"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--common-harness", type=Path, required=True)
    parser.add_argument("--sdk-wheel", type=Path, required=True)
    parser.add_argument("--web-wheel", type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.common_harness.read_bytes()).hexdigest() == "83429ab874d79e72ec558ff63e84c99ac73bdf766a48a483e139506fc3dc91d3"
    spec = importlib.util.spec_from_file_location("qualified_common_harness", args.common_harness)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    from gacontext_runtime.client import Client
    from gacontext_runtime.testing import FixtureTask
    from gacontext_runtime.worker import create_args
    from gacontext_runtime.api import code_identity
    assert code_identity() == runtime_contract()["code_sha256"]
    root, retained = args.output, args.evidence_dir
    assert root.is_absolute() and root.resolve() == root and root.parent == Path("/tmp/opencode") and len(str(root / "docker.sock")) < 104
    assert retained.resolve() == retained and retained.is_relative_to(ROOT / "tmp") and retained.parent.is_dir()
    root.mkdir(mode=0o700)
    retained.mkdir(mode=0o700)
    for folder in ("home", "runtime", "docker-client", "dist"):
        (root / folder).mkdir(mode=0o700)
    for path in (args.sdk_wheel, args.web_wheel):
        shutil.copyfile(path, root / "dist" / path.name)
    endpoint = "unix://" + str(root / "docker.sock")
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("DOCKER_", "BUILDX_", "MCP_", "UNALTRAWEB_")) and key not in {"PYTHONPATH", "PYTHONHOME"}}
    environment.update(HOME=str(root / "home"), DOCKER_CONFIG=str(root / "docker-client"), PYTHONDONTWRITEBYTECODE="1")
    unit = "unaltraweb-shared-" + uuid.uuid4().hex + ".service"
    proof = {"ok": False, "synthetic_only": True, "unit": unit, "endpoint": endpoint, "sdk_code": code_identity()}
    save(root / "owner.json", proof)
    save(retained / "run-intent.json", proof)
    config = {"data-root": str(root / "data"), "exec-root": str(root / "exec"), "hosts": [endpoint], "pidfile": str(root / "dockerd.pid"),
              "storage-driver": "overlay2", "bridge": "none", "iptables": False, "ip6tables": False, "ip-forward": False, "ip-masq": False,
              "userland-proxy": False, "log-level": "error"}
    save(root / "daemon.json", config)
    def command(argv, *, timeout=180, check=True, input=None):
        return common.execute(argv, env=environment, cwd=root, timeout=timeout, check=check, input=input)
    docker = ["/usr/bin/docker", "--host", endpoint]
    services, daemon_started = [], False
    try:
        command(["systemd-run", "--user", "--unit=" + unit, "--collect", "--property=Delegate=yes", "--property=MemoryMax=6G",
            "--property=CPUQuota=400%", "--property=TasksMax=2048", "--property=KillMode=control-group", "--property=TimeoutStopSec=30",
            "--property=RuntimeMaxSec=2400", "--setenv=HOME=" + str(root / "home"), "--setenv=XDG_RUNTIME_DIR=" + str(root / "runtime"),
            "--setenv=DBUS_SESSION_BUS_ADDRESS=" + os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus"),
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR=" + str(root / "rootlesskit"), "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_NET=slirp4netns",
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=none", "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=true",
            "--setenv=DOCKERD_ROOTLESS_ROOTLESSKIT_FLAGS=", "--setenv=_DOCKERD_ROOTLESS_CHILD=", "/usr/bin/dockerd-rootless.sh", "--config-file", str(root / "daemon.json")])
        daemon_started = True
        deadline, info = time.monotonic() + 45, None
        while time.monotonic() < deadline:
            response = command([*docker, "info", "--format", "{{json .}}"], timeout=5, check=False)
            if response.returncode == 0:
                value = json.loads(response.stdout)
                if common.daemon_ready(value):
                    info = value
                    break
            time.sleep(.25)
        assert info and "name=rootless" in info["SecurityOptions"] and info["Driver"] == "overlay2" and info["CgroupVersion"] == "2"
        assert not info["Containers"] and not info["Images"] and info["MemoryLimit"] and info["CpuCfsQuota"]
        prepared = prepare(root / "prepared", endpoint, info["ID"], args.sdk_wheel, args.web_wheel, pull_bases=True)
        proof["prepared"] = prepared
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
        provider_raw = (ROOT / "mcp-job-storage.json").read_bytes()
        (root / "provider.json").write_bytes(provider_raw)
        checked("jobs.provider-register", descriptor=str(root / "provider.json"), expected_sha=hashlib.sha256(provider_raw).hexdigest(),
                images=[prepared["images"]["pdf"]["image_id"]])
        fixture = FixtureTask(client, root / "fixture-a", "unaltraweb", synthetic=True)
        job = fixture.allocate()
        second = fixture.join("independent-web-client")
        assert fixture.allocate(second)["id"] == job["id"]
        source = fixture.workspace / "practiques/demo/ca/alumnat/LLEGIU-ME.md"
        source.parent.mkdir(parents=True)
        source.write_text("---\ntitle: Shared SDK synthetic handout\nlang: ca\ncontent_status: draft\n---\n\n# Synthetic map\n\n![Synthetic pixels](assets/picture.png)\n\n" + "\n\n".join("Observe the synthetic pattern and record an observation." for _ in range(45)))
        (fixture.workspace / "assets").mkdir()
        picture = Image.frombytes("RGB", (1536, 1024), random.Random(116).randbytes(1536 * 1024 * 3))
        picture.save(fixture.workspace / "assets/picture.png")
        assert (fixture.workspace / "assets/picture.png").stat().st_size > 4 * 1024**2
        save(fixture.workspace / "_config.yml", {"title": "Synthetic SDK course", "lang": "ca", "languages": ["ca"],
            "exclude": ["practiques", "sandbox", "dist"], "unaltraweb": {"site_profile": "unaltremanual", "manual": {
                "metadata": {"subject": "Synthetic SDK course", "short_title": "SDK", "series": "Test", "instructors": [{"name": "Synthetic author"}],
                             "teaching_guides": [{"degree": "Synthetic", "subject_code": "999116"}]}, "pdf": {"mark_drafts": True}}}})
        shutil.copytree(root / "prepared/domain/controls", fixture.workspace / "acceptance-controls")
        context = {"kind": "unaltraweb.shared-job-context", "schema_version": 1, "workspace": str(fixture.workspace), "service_root": str(service),
            "docker_endpoint": endpoint, "daemon_id": info["ID"], "registry_id": job["state"]["registry_id"], "job_id": job["id"],
            "task_id": fixture.record["task_id"], "owner_id": fixture.record["owners"][0], "pdf_image": prepared["images"]["pdf"]["image_id"],
            "worker_user": f"{os.getuid()}:{os.getgid()}"}
        original = {p.relative_to(fixture.workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.workspace.rglob("*") if p.is_file()}
        # Force actual PDF deadlines through the operator-selected policy. No
        # synthetic sleep, direct worker kill, test-only renderer or SDK fork.
        # The common harness retains this receiver subtree, including failed-call
        # results and logs, before it retires any of this daemon's test caches.
        proof["timeouts"] = []
        for seconds in (2, 5):
            attempt_root = fixture.registry.root / "receiver" / ("probe-timeout-" + str(seconds))
            attempt_root.mkdir()
            started = datetime.now(timezone.utc)
            attempt = asyncio.run(native_mcp(command, environment, attempt_root, fixture,
                {**context, "worker_timeout_seconds": seconds}, prepared["images"], expect_timeout=True))
            observed = fixture.call("jobs.inspect", job_id=job["id"])["job"]
            worker = attempt["build"]["worker"]
            actor = observed["actors"][worker["lease_id"]]
            deadline = datetime.fromisoformat(actor["deadline"].replace("Z", "+00:00"))
            assert actor["state"] == "released" and actor["container_id"] == worker["container_id"]
            assert datetime.now(timezone.utc) >= deadline and worker["timeout_seconds"] == seconds
            assert observed["docker_ownership"] == actor["docker_ownership"] == {
                "factory": "unaltraweb", "project": hashlib.sha256(str(fixture.workspace).encode()).hexdigest()[:16]}
            events = [json.loads(line) for line in command([*docker, "events", "--since", started.isoformat(),
                "--until", datetime.now(timezone.utc).isoformat(), "--filter", "container=" + worker["container_id"],
                "--format", "{{json .}}"], timeout=10).stdout.splitlines()]
            assert not any(row["Action"] == "oom" for row in events), events
            assert any(row["Action"] == "kill" and row.get("Actor", {}).get("Attributes", {}).get("signal") in {"15", "9"}
                       and row["timeNano"] / 10**9 >= deadline.timestamp() for row in events), events
            assert any(row["Action"] == "destroy" for row in events), events
            assert fixture.allocate()["id"] == job["id"]
            proof["timeouts"].append({"seconds": seconds, "native": attempt, "actor": actor,
                                       "events": events, "same_job_after_timeout": job["id"]})
        success_root = fixture.registry.root / "receiver" / "probe-success"
        success_root.mkdir()
        proof["native"] = asyncio.run(native_mcp(command, environment, success_root, fixture, context, prepared["images"]))
        assert all(row["native"]["build"]["fingerprint"] == proof["native"]["build"]["fingerprint"] for row in proof["timeouts"])
        assert not any((fixture.workspace / name).exists() for name in ("sandbox", "tmp", "dist", "_site"))
        assert original == {p.relative_to(fixture.workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.workspace.rglob("*") if p.is_file()}
        first_close = fixture.close_owner(fixture.record["owners"][0])
        assert first_close["other_users_preserved"]
        fixture.close_owner(second)
        pending = fixture.call("jobs.inspect", job_id=job["id"])["job"]["state"]
        assert pending["phase"] == "closed" and pending["holds"] and pending["products"]
        assert sorted(row["state"] for row in pending["volumes"]) == ["absent", "verified"]
        child.kill()
        child.wait(timeout=20)
        replacement, restarted = start_service(2)
        assert restarted["instance_id"] != identity["instance_id"]
        result = fixture.finish()
        assert result["zero_job_volumes"]
        retention, = result["retentions"]
        proof["delivered_pdf"] = verify_delivered_pdf(fixture.registry.root / "receiver", retention, proof["native"]["build"]["product"])
        relocation = root / "fixture-b/receiver"
        relocation.parent.mkdir()
        shutil.copytree(fixture.registry.root / "receiver", relocation)
        proof["relocated_pdf"] = verify_delivered_pdf(relocation, retention, proof["native"]["build"]["product"])
        assert proof["relocated_pdf"]["sha256"] == proof["delivered_pdf"]["sha256"]
        for row in proof["timeouts"]:
            lease = row["actor"]["id"]
            retained_root = fixture.registry.root / "receiver" / retention["destination"]["path"] / "payload/files"
            request = json.loads((retained_root / "recovery" / lease / "request.json").read_bytes())
            log = (retained_root / "recovery" / lease / "render.log").read_bytes()
            assert request["fingerprint"] == proof["native"]["build"]["fingerprint"] and request["lease_id"] == lease
            assert b'"command": ["pandoc"' in log, log
            assert (retained_root / "results/prepared" / request["fingerprint"] / lease / "payload/request.json").is_file()
            relocated_log = relocation / retention["destination"]["path"] / "payload/files/recovery" / lease / "render.log"
            assert relocated_log.read_bytes() == log
            row.update(diagnostics_retained=True, log_bytes=len(log), log_sha256=hashlib.sha256(log).hexdigest())
        assert not command([*docker, "container", "ls", "--all", "--quiet"]).stdout.strip()
        assert not command([*docker, "volume", "ls", "--quiet"]).stdout.strip()
        proof.update(ok=True, task=result, source_inputs_unchanged=True, same_slot_reused=True, other_client_preserved=True,
                      pending_products_protected=True, common_service_restarted=True, zero_job_volumes=True, zero_workers=True,
                      forced_pdf_deadlines_qualified=True, retry_after_timeout_same_job=True)
        save(root / "w1-proof.json", proof)
        expected_images = {*prepared["base_images"].values(), *(row["image_id"] for row in prepared["images"].values())}
        proof["test_cache_retirement"] = common.retire_test_cache(root, retained, command, docker, info["ID"], expected_images)
        command(["systemctl", "--user", "stop", unit], timeout=60)
        state = command(["systemctl", "--user", "show", unit, "--property=ActiveState", "--property=MainPID"]).stdout
        assert "ActiveState=active" not in state and "MainPID=0" in state
        ledger = service / "w1"
        snapshot = lambda: {p.relative_to(ledger).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in ledger.rglob("*") if p.is_file()}
        before = snapshot()
        params = {"kind": "gacontext.job-storage-request", "schema_version": 1, "operation": "status", "registry_id": context["registry_id"], "job_id": context["job_id"]}
        readonly = client.job_storage(str(fixture.workspace), "unaltraweb", params)
        assert readonly["ok"] and readonly["read_only"] and not readonly["changed"] and before == snapshot()
        proof["readonly_without_daemon"] = readonly
        checked("service.stop", expected_instance_id=restarted["instance_id"])
        assert replacement.wait(timeout=20) == 0
        proof["daemon_stopped"] = True
    except Exception as error:
        proof.update(ok=False, error=str(error))
        raise
    finally:
        for process in services:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
        if daemon_started:
            command(["systemctl", "--user", "stop", unit], timeout=60, check=False)
            (root / "daemon.log").write_text(command(["journalctl", "--user", "--unit", unit, "--no-pager", "-n", "100"], check=False).stdout)
        save(root / "rootless-proof.json", proof)
        saved = common.retain_evidence(root, retained)
        print(json.dumps({"ok": proof["ok"], "proof": str(root / "rootless-proof.json"), "retained": saved}, indent=2))


if __name__ == "__main__":
    main()
