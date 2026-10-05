"""Real installed D0 stdio identity/lifecycle acceptance on owned consumers.

Use exact prepared image IDs/digests. The legacy point remains explicitly partial
when its public MCP surface predates live identity; never relabel that process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid


class Client:
    def __init__(self, launcher, project, image, image_id, output, *, legacy=False, offline=False, nested=False, worker_images=None):
        self.log = output.open("x")
        self.project = project
        self.sequence = 0
        self.responses = {}
        self.messages = queue.Queue()
        self.session = uuid.uuid4().hex
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "UNALTRAWEB_FACTORY_DIR", "MCP_CONSUMER_WORKSPACE",
            "UNALTRAWEB_MCP_IMAGE", "UNALTRAWEB_EXPECTED_IMAGE_ID", "UNALTRAWEB_MANAGED_RUNTIME", "UNALTRAWEB_WORKER_IMAGES", "UNALTRAWEB_DOCKER_ROOT"}}
        env["OPENCODE_CONFIG"] = str(output.parent / "foreign-registration.json")
        args = [str(launcher), "serve", "--project", str(project), "--image", image]
        if not legacy:
            args += ["--expected-image-id", image_id, "--session-id", self.session, "--managed"]
            if offline:
                args.append("--offline")
            if worker_images:
                args += ["--worker-images", json.dumps(worker_images)]
        if nested:
            socket = Path("/var/run/docker.sock")
            args = ["docker", "run", "--rm", "--pull", "never", "-i", "--network", "none", "--cpus", "1", "--memory", "512m",
                "--name", "d0-85-launcher-" + self.session, "--user", f"{os.getuid()}:{os.getgid()}",
                "--group-add", str(socket.stat().st_gid), "-e", "HOME=/tmp",
                "--mount", f"type=bind,source={project},target=/controller-project",
                "--mount", "type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock",
                "--entrypoint", "unaltraweb-mcp-docker", image, "serve", "--project", "/controller-project",
                "--host-project", str(project), "--image", image_id, "--expected-image-id", image_id,
                "--session-id", self.session, "--managed"]
        self.process = subprocess.Popen(args, cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True)
        def receive():
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
            self.messages.put({"closed": True})
        self.reader = threading.Thread(target=receive, daemon=True)
        self.reader.start()
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "d0-owner-acceptance", "version": "1"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def begin(self, method, params):
        self.sequence += 1
        self.send({"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params})
        return self.sequence

    def wait(self, identifier):
        while identifier not in self.responses:
            value = self.messages.get(timeout=900)
            assert not value.get("closed"), "Backend closed; inspect retained log"
            if "id" in value:
                self.responses[value["id"]] = value
        value = self.responses.pop(identifier)
        assert "error" not in value, value
        return value["result"]

    def request(self, method, params):
        return self.wait(self.begin(method, params))

    def tool(self, name, **arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        assert not result.get("isError"), result
        value = result.get("structuredContent")
        if value is None:
            value = json.loads(next(c["text"] for c in result["content"] if c.get("type") == "text"))
        assert value.get("ok", True), value
        return value

    def close(self):
        if not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.wait(timeout=1000)
        self.reader.join(timeout=5)
        self.log.close()


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def source_hashes(project):
    paths = subprocess.check_output(["git", "-C", str(project), "ls-files", "-z"], text=True).split("\0")
    return {path: hashlib.sha256((project / path).read_bytes()).hexdigest() for path in paths if path}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--launcher", type=Path, required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--legacy-launcher", type=Path)
    p.add_argument("--legacy-image")
    a = p.parse_args()
    out = a.output.absolute()
    out.mkdir(parents=True, exist_ok=False)
    foreign_registration = out / "foreign-registration.json"
    foreign_registration.write_text('{"mcp":{"unrelated-provider":{"command":["keep-existing"],"enabled":true}}}\n')
    foreign_hash = hashlib.sha256(foreign_registration.read_bytes()).hexdigest()
    image_id = docker("image", "inspect", "--format", "{{.Id}}", a.image)
    image_before = docker("image", "inspect", "--format", "{{json .RepoTags}}|{{json .RepoDigests}}", image_id)
    evidence = {"requirements_revision": "5634ea2e3e42122bb365992dfca9f248feb89dec", "image_id": image_id,
                "image_reference": a.image, "stages": [], "legacy_live_identity": None}
    clients = []
    def connect(project, stage, legacy=False, offline=False, nested=False, worker_images=None):
        launcher = a.legacy_launcher if legacy else a.launcher
        image = a.legacy_image if legacy else a.image
        client = Client(launcher, project, image, image_id, out / (stage + ".log"), legacy=legacy, offline=offline, nested=nested, worker_images=worker_images)
        clients.append(client)
        return client
    def close(client):
        client.close()
        clients.remove(client)
    def inspect(client):
        value = client.tool("runtime_identity")
        resource = json.loads(client.request("resources/read", {"uri": "web://runtime-identity"})["contents"][0]["text"])
        assert resource["instance_id"] == value["instance_id"]
        assert value["runtime"]["container"]["state"] == "matched", value
        assert value["runtime"]["container"]["image_id"] == image_id
        assert value["process"]["pid"] > 0 and value["process"]["start_ticks"]
        assert value["binding"]["effective_project"] == str(client.project)
        assert value["package"]["drift"] is False
        return value
    def lifecycle(project, value, action="session-status"):
        run = subprocess.run([str(a.launcher), action, "--project", str(project), "--session-id", value["session_id"],
            "--container-id", value["runtime"]["container"]["id"]], cwd=out, capture_output=True, text=True, check=True)
        result = json.loads(run.stdout)
        assert result["ok"], result
        return result

    try:
        primary = out / "consumer A"
        other = out / "consumer B"
        for project in (primary, other):
            project.mkdir()
            subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        if a.legacy_launcher and a.legacy_image:
            old = connect(primary, "legacy-A", True)
            old.tool("new_web", site_profile="unaltremanual", title="D0 preserved state")
            old.tool("build_site")
            available = {item["name"] for item in old.request("tools/list", {})["tools"]}
            evidence["legacy_live_identity"] = "runtime_identity" in available
            close(old)
        first = connect(primary, "first")
        second = connect(other, "second")
        if not (a.legacy_launcher and a.legacy_image):
            first.tool("new_web", site_profile="unaltremanual", title="D0 preserved state")
        second.tool("new_web", site_profile="unaltredocs", title="Independent consumer")
        first.tool("site_source_write", path="_chapters/en/d0.md", create_only=True, dry_run=False,
                   content="---\nlayout: manual-chapter\ntitle: Coordinates\nlang: en\nref: coordinates\nweight: 1\npermalink: /en/chapters/coordinates/\n---\n\nA coordinate locates a position relative to a defined origin.\n")
        config = first.tool("site_source_read", path="_config.yml")
        enabled = config["content"].replace("      enabled: false\n", "      enabled: true\n", 1)
        if enabled != config["content"]:
            first.tool("site_source_write", path="_config.yml", content=enabled, expected_sha256=config["sha256"], dry_run=False)
        old_cache = {str(path.relative_to(primary)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (primary / "tmp/unaltraweb-bundle").glob("*/*") if path.name in {"receipt.json", "Gemfile", "Gemfile.lock"}}
        for project in (primary, other):
            (project / "author-note.txt").write_text("Keep this authored edit intact.\n")
            subprocess.run(["git", "-C", str(project), "add", "--", "."], check=True)
        first_identity, second_identity = inspect(first), inspect(second)
        assert first_identity["instance_id"] != second_identity["instance_id"]
        original = source_hashes(primary)
        other_original = source_hashes(other)
        first.tool("manual_pdf_preview_prepare")
        first.tool("build_site")
        preview = first.tool("preview_start", timeout_seconds=180)
        first.tool("http_check", paths=[preview["path"]])
        preview_id = docker("container", "inspect", "--format", "{{.Id}}", preview["container"])
        assert first.tool("runtime_drain", confirm=True)["state"] == "draining"
        close(first)
        assert lifecycle(primary, first_identity)["resources_released"]
        assert subprocess.run(["docker", "container", "inspect", preview_id], capture_output=True).returncode != 0
        assert inspect(second)["instance_id"] == second_identity["instance_id"]
        first = connect(primary, "reconnected")
        reconnected = inspect(first)
        assert reconnected["instance_id"] != first_identity["instance_id"]
        evidence["stages"].append({"name": "reconnect-and-scope", "first": first_identity, "other": second_identity, "reconnected": reconnected})

        # Mutate only the running container's disposable overlay. Prepared image
        # bytes and the host engine checkout are never edited for this test.
        cid = reconnected["runtime"]["container"]["id"]
        contract = reconnected["package"]["root"] + "/component-contract.json"
        original_contract = subprocess.check_output(["docker", "exec", "--user", "0", cid, "python3", "-c",
            "import sys; from pathlib import Path; sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())", contract])
        changed = json.loads(original_contract)
        changed["release"]["version"] = "99.0.0"
        subprocess.run(["docker", "exec", "-i", "--user", "0", cid, "python3", "-c",
            "import sys; from pathlib import Path; Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())", contract], input=json.dumps(changed).encode(), check=True)
        try:
            drift = first.tool("runtime_identity")
            assert drift["instance_id"] == reconnected["instance_id"]
            assert drift["package"]["loaded_version"] == reconnected["package"]["loaded_version"]
            assert drift["package"]["current_version"] == "99.0.0" and drift["package"]["drift"]
            evidence["stages"].append({"name": "loaded-versus-disk", "identity": drift})
        finally:
            subprocess.run(["docker", "exec", "-i", "--user", "0", cid, "python3", "-c",
                "import sys; from pathlib import Path; Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())", contract], input=original_contract, check=True)
        assert source_hashes(primary) == original and source_hashes(other) == other_original

        # A real bounded build runs while the identity/control endpoint remains
        # responsive. EOF waits for that work and releases only this session.
        makefile = other / "Makefile"
        makefile.write_text(makefile.read_text() + "\n.PHONY: d0-delay\nbuild-native: d0-delay\nd0-delay:\n\tsleep 4\n")
        second.begin("tools/call", {"name": "build_site", "arguments": {}})
        deadline = time.monotonic() + 10
        while True:
            busy = second.tool("runtime_identity")
            if busy["lifecycle"]["state"] == "busy":
                break
            assert time.monotonic() < deadline
            time.sleep(0.05)
        assert second.tool("runtime_drain", confirm=True)["active_operations"] == 1
        close(second)
        assert lifecycle(other, second_identity)["resources_released"]
        assert inspect(first)["instance_id"] == reconnected["instance_id"]
        evidence["stages"].append({"name": "busy-drain", "identity": busy})

        # Backend crash recovery is separate from graceful client detachment.
        # Use a real PDF worker, preserving it until it completes, and reap only
        # this crashed session's idle preview. The other same-workspace backend
        # remains connected throughout.
        crash = connect(primary, "backend-crash")
        crash_identity = inspect(crash)
        crash.tool("preview_start", timeout_seconds=180)
        crash.begin("tools/call", {"name": "manual_pdf_build", "arguments": {"language": "en"}})
        deadline = time.monotonic() + 30
        while True:
            workers = docker("ps", "-q", "--no-trunc", "--filter", "label=io.context.mcp-role=manual-pdf", "--filter", "label=io.context.mcp-session=" + crash_identity["session_id"]).split()
            if workers:
                break
            assert time.monotonic() < deadline, "The real PDF worker did not start"
            time.sleep(0.05)
        docker("kill", "--signal", "KILL", crash_identity["runtime"]["container"]["id"])
        close(crash)
        orphan = lifecycle(primary, crash_identity, "reap-session")
        initial_orphan_state = orphan["state"]
        if orphan["state"] == "busy":
            assert not orphan["resources_released"]
        deadline = time.monotonic() + 120
        while not orphan["resources_released"]:
            assert time.monotonic() < deadline, "Owned orphan resources did not become recoverable"
            time.sleep(0.2)
            orphan = lifecycle(primary, crash_identity, "reap-session")
        assert inspect(first)["instance_id"] == reconnected["instance_id"]
        evidence["stages"].append({"name": "backend-crash-recovery", "identity": crash_identity, "observed_pdf_workers": workers,
                                   "initial_orphan_state": initial_orphan_state, "final": orphan})
        close(first)
        assert lifecycle(primary, reconnected)["resources_released"]
        offline = connect(primary, "offline", offline=True)
        offline_identity = inspect(offline)
        assert offline_identity["runtime"]["container"]["network_mode"] == "none"
        assert offline.tool("detect_site")["is_unaltraweb_site"]
        close(offline)
        assert lifecycle(primary, offline_identity)["resources_released"]
        evidence["stages"].append({"name": "offline-launch", "identity": offline_identity})
        nested = connect(primary, "explicit-daemon-mapping", nested=True)
        mapped = inspect(nested)
        assert mapped["binding"]["launcher_project"] == "/controller-project"
        assert mapped["binding"]["daemon_host_project"] == str(primary)
        nested.tool("manual_pdf_preview_prepare")
        nested.tool("build_site")
        close(nested)
        assert lifecycle(primary, mapped)["resources_released"]
        assert subprocess.run(["docker", "container", "inspect", "d0-85-launcher-" + nested.session], capture_output=True).returncode != 0
        evidence["stages"].append({"name": "explicit-daemon-mapping", "identity": mapped})
        pdf_ref = reconnected["runtime"]["workers"]["manual_pdf"]["reference"]
        for name, reference, expected in (("wrong-worker", pdf_ref, "sha256:" + "0" * 64),
                                           ("missing-worker", "sha256:" + "1" * 64, "sha256:" + "1" * 64)):
            guarded = connect(primary, name, worker_images={"manual_pdf": {"reference": reference, "expected_image_id": expected}})
            identity = guarded.tool("runtime_identity")
            assert identity["runtime"]["workers"]["manual_pdf"]["state"] in {"missing", "mismatch"}
            refused = guarded.request("tools/call", {"name": "manual_pdf_build", "arguments": {"language": "en"}})
            assert refused.get("isError"), refused
            assert source_hashes(primary) == original
            close(guarded)
            assert lifecycle(primary, identity)["resources_released"]
            evidence["stages"].append({"name": name, "identity": identity})
        for reference, expected in ((a.image, "sha256:" + "0" * 64), ("sha256:" + "1" * 64, "sha256:" + "1" * 64)):
            refused = subprocess.run([str(a.launcher), "serve", "--project", str(primary), "--image", reference,
                "--expected-image-id", expected, "--managed"], cwd=out, capture_output=True, text=True, timeout=20)
            assert refused.returncode and ("not match" in refused.stderr or "not prepared" in refused.stderr), refused
        evidence["wrong_and_missing_images"] = "refused"
        if a.legacy_launcher and a.legacy_image:
            old = connect(primary, "legacy-A-return", True)
            old.tool("manual_pdf_preview_prepare")
            old.tool("build_site")
            assert source_hashes(primary) == original
            close(old)
            evidence["legacy_rollback"] = "passed; legacy live identity remains partial when absent"
        assert all(hashlib.sha256((primary / name).read_bytes()).hexdigest() == sha for name, sha in old_cache.items())
        evidence["preserved_legacy_cache"] = old_cache
        assert docker("image", "inspect", "--format", "{{json .RepoTags}}|{{json .RepoDigests}}", image_id) == image_before
        evidence["prepared_image_unchanged"] = True
        assert hashlib.sha256(foreign_registration.read_bytes()).hexdigest() == foreign_hash
        evidence["foreign_registration_preserved"] = foreign_hash
        evidence["ok"] = True
        (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({"ok": True, "evidence": str(out / "evidence.json"), "stages": [s["name"] for s in evidence["stages"]]}))
    finally:
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()
