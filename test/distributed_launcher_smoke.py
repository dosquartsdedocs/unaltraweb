"""Opt-in real Docker acceptance of an installed launcher; retains synthetic evidence.

No core checkout is mounted. Run sequentially with explicit immutable image selections.
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


class Client:
    def __init__(self, launcher: Path, project: Path, image: str, log: Path):
        self.log = log.open("w", encoding="utf-8")
        env = {key: value for key, value in os.environ.items() if key not in {
            "UNALTRAWEB_FACTORY_DIR", "PYTHONPATH", "UNALTRAWEB_MCP_IMAGE", "MCP_CONSUMER_WORKSPACE",
        }}
        self.process = subprocess.Popen(
            [str(launcher), "serve", "--project", str(project), "--image", image],
            cwd=project, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True,
        )
        self.messages: queue.Queue = queue.Queue()
        self.sequence = 0
        self.reader = threading.Thread(target=self.read_messages, daemon=True)
        self.reader.start()
        self.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "installed-launcher-acceptance", "version": "1"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def read_messages(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                self.messages.put({"error": f"Non-protocol stdout: {line}"})
        self.messages.put({"error": "Server closed stdout; inspect retained stderr"})

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        self.send({"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params})
        while True:
            result = self.messages.get(timeout=900)
            if "error" in result:
                raise AssertionError(result)
            if result.get("id") == self.sequence:
                return result["result"]

    def tool(self, name, **arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        assert not result.get("isError"), result
        payload = result.get("structuredContent")
        if payload is None:
            payload = json.loads(next(item["text"] for item in result["content"] if item.get("type") == "text"))
        assert payload.get("ok", True), payload
        return payload

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=30)
        self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", default=["unaltreselfie", "unaltreprojecte", "unaltredocs", "unaltremanual"])
    parser.add_argument("--scaffold-image", help="Separate historical scaffold/build selection for a mixed-tuple test.")
    parser.add_argument("--host-build", action="store_true", help="Run the scaffold image's host build first, retaining its generated Bundler cache.")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    evidence = {"image": args.image, "scaffold_image": args.scaffold_image or args.image, "profiles": []}
    for profile in args.profiles:
        project = output / profile
        project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(project)], check=True)
        client = Client(args.launcher, project, args.scaffold_image or args.image, output / f"{profile}-create.log")
        try:
            assert not client.tool("detect_site")["is_unaltraweb_site"]
            created = client.tool("new_web", site_profile=profile, title=f"Installed launcher {profile}", baseurl=f"/{profile}")
            available_tools = {tool["name"] for tool in client.request("tools/list", {})["tools"]}
            for name in ("editorial_policy", "editorial_status"):
                if name in available_tools:
                    client.tool(name)
            if profile == "unaltremanual":
                client.tool("manual_authoring_capabilities")
                config = client.tool("site_source_read", path="_config.yml")
                text = config["content"].replace("      enabled: false\n", "      enabled: true\n", 1)
                assert text != config["content"]
                client.tool("site_source_write", path="_config.yml", content=text, expected_sha256=config["sha256"], dry_run=False)
                client.tool("site_source_write", path="_chapters/en/first.md", create_only=True, dry_run=False,
                            content="---\nlayout: manual-chapter\ntitle: Coordinates\nlang: en\nref: coordinates\nweight: 1\npermalink: /en/chapters/coordinates/\n---\n\nA coordinate system locates a point relative to a defined origin.\n")
                client.tool("manual_computation_status")
                client.tool("prose_check" if "prose_check" in available_tools else "manual_editorial_quality_check")
            # Keep synthetic source records indexed; no commit or identity configuration is needed.
            subprocess.run(["git", "-C", str(project), "add", "--", "."], check=True)
        finally:
            client.close()
        if args.host_build:
            # This is the generated host build path, independent of the globally selected MCP.
            with (output / f"{profile}-host-build.log").open("w") as log:
                subprocess.run(["make", "--silent", "--no-print-directory", "build", f"MCP_IMAGE={args.scaffold_image or args.image}"],
                               cwd=project, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
        client = Client(args.launcher, project, args.image, output / f"{profile}-runtime.log")
        record = {"profile": profile, "project": str(project), "created": created["ok"]}
        try:
            context = client.tool("site_context")
            record["update_state"] = context.get("update_status", {}).get("state", "not_available")
            # An advisory is recorded, never automatically applied.
            if profile == "unaltremanual":
                prepared = client.tool("manual_pdf_preview_prepare")
                assert prepared["publishes"] is False
                record["pdf_built_languages"] = prepared["built_languages"]
                record["pdf"] = [
                    {"path": str(path.relative_to(project)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for path in sorted((project / "tmp/manual-pdf").rglob("*.pdf"))
                ]
                assert record["pdf"]
            record["site_check"] = client.tool("site_check")["ok"]
            record["build"] = client.tool("build_site")["ok"]
            started = client.tool("preview_start", timeout_seconds=180)
            assert started["ready"] and started["requested_port"] == 0
            record["port"] = started["port"]
            status = client.tool("preview_status")
            inspected = json.loads(subprocess.check_output(["docker", "inspect", status["container"]], text=True))[0]
            assert all(mount["Destination"] != "/var/run/docker.sock" for mount in inspected["Mounts"])
            assert all(mount["Source"] == str(project) for mount in inspected["Mounts"])
            record["preview_image_id"] = inspected["Image"]
            record["mounts"] = inspected["Mounts"]
            record["http"] = client.tool("http_check", paths=[started["ready_path"]])["ok"]
            record["html_audit"] = client.tool("html_audit")["ok"]
            runtime_tools = {tool["name"] for tool in client.request("tools/list", {})["tools"]}
            record["image_backgrounds"] = client.tool("image_background_check") if "image_background_check" in runtime_tools else {"available": False}
        except Exception as exc:
            record["error"] = str(exc)
            evidence["profiles"].append(record)
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            raise
        finally:
            try:
                client.tool("preview_stop")
                if profile == "unaltremanual":
                    cleanup = client.tool("manual_pdf_preview_clean")
                    client.tool("manual_pdf_preview_clean", dry_run=False, confirm_clean=True, expected_receipt_sha256=cleanup["receipt_sha256"])
            finally:
                client.close()
        evidence["profiles"].append(record)
        (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
