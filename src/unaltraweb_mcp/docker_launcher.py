"""Installed host adapter to the full GHCR runtime, separate from the native CLI."""

from __future__ import annotations

import argparse
from importlib.metadata import distribution
import os
from pathlib import Path

from .distribution import component_reference


def launcher_root() -> Path:
    """Resolve wheel data via RECORD, including venv and user installations."""
    installed = distribution("unaltraweb-mcp")
    for entry in installed.files or ():
        if entry.as_posix().endswith("share/unaltraweb-launcher/mcp-factory.yml"):
            root = Path(installed.locate_file(entry)).resolve().parent
            required = ["Makefile", "mcp-factory.yml"] + [
                f"scripts/{name}.sh" for name in (
                    "unaltraweb-mcp-bootstrap", "unaltraweb-mcp-project-id",
                    "unaltraweb-mcp-cleanup", "unaltraweb-docker-mount",
                )
            ]
            if all((root / name).is_file() for name in required):
                return root
    raise RuntimeError("Installed Docker launcher assets are missing; install a containing wheel (non-editable).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="serve", choices=("serve", "prepare", "check", "smoke", "down", "path", "manifest", "session-status", "reap-session"))
    parser.add_argument("--project", help="Explicit consumer directory (or MCP_CONSUMER_WORKSPACE).")
    parser.add_argument("--image", help="Full MCP image selection; defaults to this package's release image.")
    parser.add_argument("--project-id", help="Retained project identity for down only.")
    parser.add_argument("--expected-image-id", help="Exact prepared Docker configuration ID; managed mode refuses a mismatch.")
    parser.add_argument("--managed", action="store_true", help="Require an immutable image reference or explicit expected image ID.")
    parser.add_argument("--offline", action="store_true", help="Start the controller with Docker networking disabled (daemon socket remains explicit).")
    parser.add_argument("--host-project", help="Explicit Docker-daemon source when the launcher sees a different project path.")
    parser.add_argument("--session-id", help="32-hex connection identity, distinct from the serving backend instance.")
    parser.add_argument("--container-id", help="Exact retained backend container ID for session inspection/recovery.")
    parser.add_argument("--worker-images", help="Startup-fixed JSON mapping of worker references and expected image IDs.")
    args = parser.parse_args(argv)
    if args.container_id and args.action not in {"session-status", "reap-session"}:
        parser.error("--container-id is only supported by session lifecycle commands")
    if (args.host_project or args.worker_images or args.offline) and args.action != "serve":
        parser.error("Host mapping, worker selections and offline networking apply to serve only")
    if args.project_id and args.action != "down":
        parser.error("--project-id is only supported by down")
    if args.image and args.action in {"down", "path", "manifest"}:
        parser.error("--image requires serve, prepare, check or smoke")
    try:
        root = launcher_root()
    except RuntimeError as exc:
        parser.error(str(exc))
    if args.action == "path":
        print(root)
        return 0
    if args.action == "manifest":
        print((root / "mcp-factory.yml").read_text(encoding="utf-8"), end="")
        return 0
    if args.action in {"session-status", "reap-session"}:
        from .runtime_lifecycle import session_status
        import json
        if not (args.project and args.session_id and args.container_id):
            parser.error("Session lifecycle needs --project, --session-id and --container-id")
        result = session_status(args.project, args.session_id, args.container_id, reap=args.action == "reap-session")
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.action == "serve" and not (args.project or os.environ.get("MCP_CONSUMER_WORKSPACE")):
        parser.error("serve requires --project or MCP_CONSUMER_WORKSPACE")
    script = "unaltraweb-mcp-cleanup.sh" if args.action == "down" else "unaltraweb-mcp-bootstrap.sh"
    command = ["/bin/sh", str(root / "scripts" / script)]
    if args.project:
        command.extend(["--project", args.project])
    if args.action != "down":
        image = args.image or os.environ.get("UNALTRAWEB_MCP_IMAGE") or component_reference("mcp")
        command.extend(["--image", image])
        for name in ("expected_image_id", "host_project", "session_id", "worker_images"):
            if getattr(args, name):
                command.extend(["--" + name.replace("_", "-"), getattr(args, name)])
        if args.managed:
            command.append("--managed")
        if args.offline:
            command.append("--offline")
    if args.project_id:
        command.extend(["--project-id", args.project_id])
    if args.action in {"prepare", "check", "smoke"}:
        command.append(f"--{args.action}")
    os.execv(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
