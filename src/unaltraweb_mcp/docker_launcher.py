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
    parser.add_argument("action", nargs="?", default="serve", choices=("serve", "prepare", "check", "smoke", "down", "path", "manifest"))
    parser.add_argument("--project", help="Explicit consumer directory (or MCP_CONSUMER_WORKSPACE).")
    parser.add_argument("--image", help="Full MCP image selection; defaults to this package's release image.")
    parser.add_argument("--project-id", help="Retained project identity for down only.")
    args = parser.parse_args(argv)
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
    if args.action == "serve" and not (args.project or os.environ.get("MCP_CONSUMER_WORKSPACE")):
        parser.error("serve requires --project or MCP_CONSUMER_WORKSPACE")
    script = "unaltraweb-mcp-cleanup.sh" if args.action == "down" else "unaltraweb-mcp-bootstrap.sh"
    command = ["/bin/sh", str(root / "scripts" / script)]
    if args.project:
        command.extend(["--project", args.project])
    if args.action != "down":
        image = args.image or os.environ.get("UNALTRAWEB_MCP_IMAGE") or component_reference("mcp")
        command.extend(["--image", image])
    if args.project_id:
        command.extend(["--project-id", args.project_id])
    if args.action in {"prepare", "check", "smoke"}:
        command.append(f"--{args.action}")
    os.execv(command[0], command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
