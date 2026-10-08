"""Opt-in native W1 acceptance; all fixtures and failed jobs remain inspectable.

Run from the source checkout with PYTHONPATH=src. Images must already be prepared.
The output is a new synthetic Git site, never an existing consumer directory.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from unaltraweb_mcp.job_storage import contract, reception
from unaltraweb_mcp.job_storage.manager import Manager


DEMO = '''import json, os
from pathlib import Path
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="white"/><text x="20" y="100">W1 retained result</text></svg>'
Path("figure.svg").write_text(svg)
Path("figure.edited.svg").write_text(svg.replace("retained result", "authored variant"))
Path("execution.json").write_text(json.dumps({"uid": os.getuid(), "consumer": os.environ["MCP_CONSUMER_WORKSPACE"], "execution": os.getcwd()}))
'''


async def check_control_api(project, registry, registry_id, job_id, controller_image=None, seal_on_connection=False):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    environment = {key: value for key, value in os.environ.items()
                   if key not in {"UNALTRAWEB_RUNTIME_SESSION", "UNALTRAWEB_DOCKER_ROOT", "UNALTRAWEB_MANAGED_RUNTIME"}}
    environment["UNALTRAWEB_JOB_STORAGE_STATE"] = str(registry)
    parameters = StdioServerParameters(command=sys.executable,
        args=["-B", "-m", "unaltraweb_mcp.cli", "--project", str(project), "mcp", "serve"], env=environment)
    if controller_image:
        parameters = StdioServerParameters(command="/bin/sh", args=[str(Path(__file__).resolve().parents[1] / "scripts/unaltraweb-mcp-bootstrap.sh"),
            "--project", str(project), "--host-project", str(project), "--storage-state", str(registry),
            "--host-storage-state", str(registry), "--image", controller_image, "--managed", "--offline"], env=environment)
    async with stdio_client(parameters) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as client:
            await client.initialize()
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert "job_storage" in tools
            resource = await client.read_resource("web://job-storage-provider")
            descriptor = json.loads(resource.contents[0].text)
            assert contract.validate(descriptor)["contract"] == contract.CONTRACT
            request = {"kind": "gacontext.job-storage-request", "schema_version": 1,
                       "operation": "status", "registry_id": registry_id, "job_id": job_id}
            result = await client.call_tool("job_storage", {"request": request})
            assert not result.isError, result
            state = result.structuredContent
            assert contract.validate(state)["phase"] == ("open" if seal_on_connection else "released"), state
            if seal_on_connection:
                sealed = await client.call_tool("job_storage", {"request": {**request, "operation": "seal",
                    "expected_revision": state["revision"], "expected_epoch": state["epoch"]}})
                assert not sealed.isError and len(sealed.structuredContent["products"]) == 1, sealed
            identity = await client.call_tool("runtime_identity", {})
            assert identity.structuredContent["package"]["drift"] is False
            await client.call_tool("runtime_drain", {"confirm": True})
            after_drain = await client.call_tool("job_storage", {"request": request})
            assert not after_drain.isError and after_drain.structuredContent["phase"] == ("open" if seal_on_connection else "released"), after_drain
            observed = identity.structuredContent
            evidence = {"instance_id": observed["instance_id"], "job_id": job_id, "status_after_drain": after_drain.structuredContent["phase"],
                        "session_id": observed["session_id"], "container": observed["runtime"]["container"]}
    if controller_image:
        from unaltraweb_mcp.runtime_lifecycle import session_status
        # MCP clients may enforce a short EOF grace period. Complete cleanup
        # using the persistent native manager after observing exact backend death.
        manager = Manager(project, state_root=registry, utility_image=controller_image)
        deadline = time.monotonic() + 30
        while True:
            recovered = manager.reap_session(evidence["session_id"], evidence["container"]["id"])
            if recovered["ok"] and all(item.get("state", {}).get("phase") in {"closed", "released"} for item in recovered["jobs"]):
                break
            assert time.monotonic() < deadline, recovered
            await asyncio.sleep(.1)
        evidence["storage_recovery"] = recovered
        closed = session_status(str(project), evidence["session_id"], evidence["container"]["id"])
        assert closed["ok"] and closed["resources_released"], closed
        evidence["closed"] = closed
    return evidence


def accept_pending_eof(root, registry, image, controller_image):
    project = root / "pending-eof"
    project.mkdir()
    (project / "_config.yml").write_text("title: Pending native EOF fixture\n")
    (project / "demo.py").write_text(DEMO)
    manager = Manager(project, state_root=registry, utility_image=image)
    state = manager.begin("compute-python", limits={"max_scratch_bytes": 32*1024**2, "max_retained_bytes": 32*1024**2})
    registry_id, job_id = state["registry_id"], state["job_id"]
    state = manager.stage(registry_id, job_id, state["revision"], state["epoch"], ["_config.yml", "demo.py"])["state"]
    state = manager.prepare_workspace(registry_id, job_id, state["revision"], state["epoch"])["state"]
    state = manager.run(registry_id, job_id, state["revision"], state["epoch"], ["python3", "demo.py"], timeout_seconds=10)["state"]
    manager.detach(registry_id, job_id, state["revision"], state["epoch"])
    native = asyncio.run(check_control_api(project, registry, registry_id, job_id, controller_image, seal_on_connection=True))
    state = manager.status(registry_id, job_id)
    assert state["phase"] == "closed" and not state["holds"] and state["products"][0]["disposition"] == "pending", state
    assert {volume["role"]: volume["state"] for volume in state["volumes"]} == {"scratch": "absent", "retained": "verified"}, state
    evidence = {"ok": True, "native": native, "after_eof": state}
    (project / "evidence.json").write_bytes(contract.canonical(evidence))
    print(json.dumps({"eof": "passed", "pending_job": job_id}), flush=True)
    return evidence


def accept(root, registry, image, format_name, controller_image=None):
    project = root / format_name
    project.mkdir()
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    (project / "_config.yml").write_text(
        "title: Synthetic W1 acceptance\nunaltraweb:\n  product_retention:\n"
        "    enabled: true\n    root: .unaltraweb/products\n"
        f"    format: {format_name}\n    profiles: [unaltraweb-job-v1]\n"
        "    assets:\n      root: assets/received\n      roles: [rendered-visual, edited-visual, document]\n"
    )
    (project / "demo.py").write_text(DEMO)
    manager = Manager(project, state_root=registry, utility_image=image)
    state = manager.begin("compute-python", limits={"max_scratch_bytes": 32*1024**2, "max_retained_bytes": 32*1024**2})
    registry_id, job_id = state["registry_id"], state["job_id"]
    evidence = {"registry_id": registry_id, "job_id": job_id, "format": format_name}
    (project / "admission.json").write_bytes(contract.canonical(evidence))

    def args():
        return registry_id, job_id, state["revision"], state["epoch"]

    def control(operation):
        return manager.control({"kind": "gacontext.job-storage-request", "schema_version": 1,
                                "operation": operation, "registry_id": registry_id, "job_id": job_id,
                                "expected_revision": state["revision"], "expected_epoch": state["epoch"]})

    state = manager.stage(*args(), ["_config.yml", "demo.py"], parameters={"fixture": "native-retention-acceptance"})["state"]
    state = manager.prepare_workspace(*args())["state"]
    executed = manager.run(*args(), ["python3", "demo.py"], timeout_seconds=10)
    assert executed["report"]["exit_code"] == 0 and executed["report"]["pressure_or_timeout"] is None, executed
    state = executed["state"]
    state = control("seal")
    assert len(state["products"]) == 1 and not state["holds"], state
    product_id = state["products"][0]["id"]
    state = manager.detach(*args())
    state = control("quiesce")
    pending = manager.plan_release(registry_id, job_id)
    assert {row["role"]: row["action"] for row in pending["plan"]["volumes"]} == {"scratch": "remove-volume", "retained": "blocked"}, pending
    scratch_release = manager.apply_release(pending["plan"], pending["plan_sha256"])
    received = manager.receive_product(registry_id, job_id, product_id)
    assert received["state"]["products"][0]["disposition"] == "acknowledged", received
    if format_name != "directory":
        assert received["verification_job_release"]["state"]["phase"] == "released", received
        assert received["retention"]["bundle_sha256"] != received["retention"]["destination"]["content_sha256"], received
    reused = manager.receive_product(registry_id, job_id, product_id)
    assert reused["reused"] and reused["retention"]["destination"] == received["retention"]["destination"], reused
    ready = manager.plan_release(registry_id, job_id)
    assert ready["plan"]["all_releasable"], ready
    released = manager.apply_release(ready["plan"], ready["plan_sha256"])
    assert released["state"]["phase"] == "released" and all(item["state"] == "absent" for item in released["state"]["volumes"]), released
    with manager.registry.locked() as ledger:
        witness = ledger.read("decisions/" + received["state"]["products"][0]["decision"]["id"] + ".json")["witness"]
    checked = reception.verify_record(manager, witness)
    relocated = root / (format_name + "-relocated")
    shutil.copytree(project, relocated)
    other = Manager(relocated, state_root=registry, utility_image=image)
    relocated_check = other.check_retained(received["retention"]["bundle_sha256"])
    assert relocated_check["ok"] and relocated_check["receiver_binding_id"] != received["retention"]["receiver_binding_id"], relocated_check
    try:
        other.status(registry_id, job_id)
    except contract.StorageError as error:
        assert error.code == "storage-binding-mismatch", error
    else:
        raise AssertionError("Relocation adopted the original producer's authority")
    # A changed author asset must survive a failed automatic revalidation.
    edited = next(relocated.glob("assets/received/**/figure.edited.svg"))
    authored = edited.read_bytes().replace(b"authored variant", b"local author change")
    edited.write_bytes(authored)
    try:
        other.check_retained(received["retention"]["bundle_sha256"])
    except contract.StorageError as error:
        assert error.code == "storage-retention-stale", error
    else:
        raise AssertionError("An edited author asset was silently accepted")
    assert edited.read_bytes() == authored
    native_api = asyncio.run(check_control_api(project, registry, registry_id, job_id, controller_image))
    evidence.update(scratch_release=scratch_release, received=received, reused=reused, released=released,
                    post_retirement_check=checked, relocation_check=relocated_check, authored_change_preserved=True, native_api=native_api)
    (project / "evidence.json").write_bytes(contract.canonical(evidence))
    return {"format": format_name, "job_id": job_id, "phase": released["state"]["phase"],
            "bundle_sha256": received["retention"]["bundle_sha256"], "verified_files": checked["verified_files"]}


def client_worker(project, registry, image, registry_id, job_id, ready, finish, outcome):
    manager = Manager(project, state_root=registry, utility_image=image)
    state = manager.status(registry_id, job_id)
    state = manager.attach(registry_id, job_id, state["revision"], state["epoch"])
    original_start = manager.docker.start_worker
    def started(*arguments, **keywords):
        ready.set()
        return original_start(*arguments, **keywords)
    manager.docker.start_worker = started
    manager.run(registry_id, job_id, state["revision"], state["epoch"], ["python3", "demo.py"], timeout_seconds=15)
    if not finish.wait(30):
        raise RuntimeError("Native acceptance parent did not release its client barrier")
    outcome.put(manager.toggle_off([(registry_id, job_id)]))


def accept_faults(root, registry, image):
    """Small bounded failures, never fill the host disk or remove pending sources."""
    project = root / "faults"
    project.mkdir()
    (project / "_config.yml").write_text("title: W1 failure fixture\n")
    (project / "demo.py").write_text(DEMO + "\nimport time\ntime.sleep(3)\n")
    manager = Manager(project, state_root=registry, utility_image=image)
    evidence = {"cases": []}

    def new_job(limits=None):
        state = manager.begin("compute-python", limits=limits)
        registry_id, job_id = state["registry_id"], state["job_id"]
        state = manager.stage(registry_id, job_id, state["revision"], state["epoch"], ["_config.yml", "demo.py"])["state"]
        return manager.prepare_workspace(registry_id, job_id, state["revision"], state["epoch"])["state"]

    def wait_busy(registry_id, job_id):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                state = manager.status(registry_id, job_id)
                attached = {identifier for volume in state["volumes"] for identifier in volume["attachments"]}
                if state["activity"] == "busy" and any((manager.docker.inspect("container", identifier) or {}).get("running") for identifier in attached):
                    return state
            except contract.StorageError as error:
                assert error.code == "storage-registry-busy", error
            time.sleep(.05)
        raise AssertionError("Native worker never became observably busy")

    context = multiprocessing.get_context("spawn")
    for crash in (False, True):
        state = new_job({"max_scratch_bytes": 32*1024**2, "max_retained_bytes": 32*1024**2})
        registry_id, job_id = state["registry_id"], state["job_id"]
        ready, finish, outcome = context.Event(), context.Event(), context.Queue()
        client = context.Process(target=client_worker, args=(project, registry, image, registry_id, job_id, ready, finish, outcome))
        client.start()
        try:
            assert ready.wait(15), "Second native client did not attach"
            busy = wait_busy(registry_id, job_id)
            if crash:
                client.kill()
                client.join(5)
            kept = manager.toggle_off([(registry_id, job_id)])
            assert kept["ok"], kept
            kept_state = kept["jobs"][0]["state"]
            assert all(volume["state"] != "absent" for volume in kept_state["volumes"]), kept
            if not crash:
                assert kept_state["phase"] == "open" and kept["jobs"][0]["kept"] == "other-or-unknown-client-interest", kept
                finish.set()
                closed = outcome.get(timeout=30)
                client.join(5)
                assert client.exitcode == 0, client.exitcode
            else:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    closed = manager.toggle_off([(registry_id, job_id)])
                    if closed["ok"] and closed["jobs"][0].get("state", {}).get("phase") == "closed":
                        break
                    time.sleep(.2)
            assert closed["ok"], closed
            result = closed["jobs"][0]["state"]
            assert result["phase"] == "closed" and result["holds"], result
            assert {volume["role"]: volume["state"] for volume in result["volumes"]} == {"scratch": "absent", "retained": "verified"}, result
            evidence["cases"].append({"case": "controller-crash" if crash else "two-clients", "busy": busy, "kept": kept, "closed": closed})
            (project / "progress.json").write_bytes(contract.canonical(evidence))
        finally:
            finish.set()
            if client.is_alive():
                client.terminate()
                client.join(5)
            outcome.close()

    state = new_job({"max_scratch_bytes": 32768, "max_retained_bytes": 32*1024**2, "monitor_interval_seconds": 1})
    registry_id, job_id = state["registry_id"], state["job_id"]
    command = ["python3", "-c", "import os,time; from pathlib import Path; Path('useful-result.txt').write_text('preserve'); Path(os.environ['TMPDIR'],'pressure.bin').write_bytes(b'x'*(2*1024*1024)); time.sleep(30)"]
    pressure = manager.run(registry_id, job_id, state["revision"], state["epoch"], command, timeout_seconds=15)
    assert pressure["report"]["pressure_or_timeout"] == "scratch byte ceiling exceeded", pressure
    assert pressure["state"]["phase"] == "draining", pressure
    closed = manager.toggle_off([(registry_id, job_id)])
    assert closed["ok"] and closed["jobs"][0]["state"]["phase"] == "closed", closed
    assert {volume["role"]: volume["state"] for volume in closed["jobs"][0]["state"]["volumes"]} == {"scratch": "absent", "retained": "verified"}, closed
    evidence["cases"].append({"case": "monitored-pressure", "pressure": pressure, "closed": closed})
    with manager.registry.locked() as ledger:
        before = list(ledger.record["jobs"])
    for limits, code in [({"min_free_bytes": 2**40}, "storage-budget-exceeded"), ({"quota_enforcement": "hard"}, "storage-quota-unsupported")]:
        try:
            manager.begin("compute-python", limits=limits)
        except contract.StorageError as error:
            assert error.code == code, error
        else:
            raise AssertionError("Unsupported budget was admitted")
    with manager.registry.locked() as ledger:
        assert before == ledger.record["jobs"]
    evidence["admission_refusals"] = ["insufficient-observed-daemon-capacity", "unsupported-hard-quota"]
    (project / "evidence.json").write_bytes(contract.canonical(evidence))
    print(json.dumps({"faults": "passed", "retained_pending_jobs": [case["closed"]["jobs"][0]["state"]["job_id"] for case in evidence["cases"]]}), flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--controller-image", help="Exact prepared W1 MCP image ID for native Docker stdio acceptance")
    parser.add_argument("--faults", action="store_true", help="Also exercise two clients, controller crash, monitored pressure and admission refusal")
    parser.add_argument("--formats", nargs="+", choices=("directory", "zip", "tar-gzip"), default=["directory", "zip", "tar-gzip"])
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False)
    results = []
    for format_name in args.formats:
        result = accept(output, output / "registry", args.image, format_name, args.controller_image)
        results.append(result)
        print(json.dumps(result), flush=True)
    faults = accept_faults(output, output / "registry", args.image) if args.faults else None
    eof = accept_pending_eof(output, output / "registry", args.image, args.controller_image) if args.controller_image else None
    (output / "evidence.json").write_bytes(contract.canonical({"ok": True, "results": results, "faults": faults, "eof": eof}))


if __name__ == "__main__":
    main()
