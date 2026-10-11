#!/usr/bin/env python3
"""Install the released, hash-bound QGIS verifier into the prepared MCP image.

The component BOM is the only pin authority. A missing final owner pin is a
publication/build blocker, never a request to use a local rc wheel or an index.
"""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, distribution
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from unaltraweb_mcp.processes import run_process

COMPONENT = "qgis_practice_verifier"
REPOSITORY = "https://github.com/dosquartsdedocs/unaltracaptura-qgis"
PROFILES = ("qgis-practice-v1", "qgis-practice-v2")


def required(contract):
    return "manual-practice-compose" in contract.get("wheel_contract", {}).get("factory_required_mcp", [])


def selection(contract):
    item = contract.get("components", {}).get(COMPONENT)
    if not isinstance(item, dict):
        raise ValueError("QGIS verifier final release pin is missing; wait for the owner URL+SHA-256")
    version = item.get("version", "")
    features = item.get("features", [])
    if (item.get("kind") != "companion" or item.get("release_status") != "released"
            or not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version)
            or item.get("release") != "v" + version or item.get("name") != "unaltracaptura_qgis"
            or item.get("repository") != REPOSITORY or item.get("included_in_wheel") is not False
            or not isinstance(features, list) or any(not isinstance(value, str) for value in features)
            or not set(PROFILES) <= set(features)):
        raise ValueError("QGIS verifier requires an explicitly released owner component with both practice profiles")
    reference = item.get("reference", "")
    prefix = f"{REPOSITORY}/releases/download/v{version}/unaltracaptura_qgis-{version}-py3-none-any.whl#sha256="
    if not isinstance(reference, str) or not reference.startswith(prefix):
        raise ValueError("QGIS verifier must use its exact public release wheel URL+SHA-256")
    digest = reference.removeprefix(prefix)
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or digest == "0" * 64:
        raise ValueError("QGIS verifier wheel SHA-256 is absent or invalid")
    return {"package": "unaltracaptura-qgis", "version": version, "reference": reference, "wheel_sha256": digest}


def publication_errors(contract):
    if not required(contract):
        return []
    try:
        selection(contract)
    except (ValueError, TypeError) as exc:
        return [str(exc)]
    return []


def checked_run(arguments, timeout=120):
    result = run_process(arguments, timeout_seconds=timeout, output_limit=1024*1024)
    if result.returncode or result.timed_out or result.stdout_truncated or result.stderr_truncated:
        raise RuntimeError("QGIS verifier installation/check failed: " + (result.stderr or result.stdout)[-3000:])
    return result.stdout


def verify_installed(selected):
    installed = distribution(selected["package"])
    direct = json.loads(installed.read_text("direct_url.json") or "{}")
    if (installed.version != selected["version"]
            or direct.get("archive_info", {}).get("hashes", {}).get("sha256") != selected["wheel_sha256"]):
        raise ValueError("Installed QGIS verifier differs from the selected release wheel")
    profiles = {}
    revisions = set()
    for profile in PROFILES:
        value = json.loads(checked_run([sys.executable, "-I", "-m", "veure_qgis_mcp.cli", "practice-schema", "--profile", profile]))
        package = value.get("installed_package", {})
        if (value.get("ok") is not True or value.get("profile") != profile
                or package.get("name") != selected["package"] or package.get("version") != selected["version"]
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(package.get("revision", "")))
                or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("schema_sha256", "")))):
            raise ValueError("Installed QGIS verifier did not certify the requested public profile")
        revisions.add(package["revision"])
        profiles[profile] = {"schema_sha256": value["schema_sha256"], "package": package}
    if len(revisions) != 1:
        raise ValueError("QGIS verifier profile identities disagree")
    return {"ok": True, "selection": selected, "profiles": profiles}


def install(contract):
    selected = selection(contract)  # Refuse before pip/network when the final pin is absent.
    checked_run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-cache-dir",
                 "--break-system-packages", selected["reference"]], timeout=600)
    return verify_installed(selected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=ROOT / "src/unaltraweb_mcp/component-contract.json")
    parser.add_argument("--install", action="store_true", help="Explicit image-build installation; otherwise only validate the pin")
    args = parser.parse_args(argv)
    from unaltraweb_mcp.distribution import _strict_json
    try:
        contract = _strict_json(args.contract)
        result = install(contract) if args.install else {"ok": True, "selection": selection(contract)}
    except (OSError, ValueError, RuntimeError, PackageNotFoundError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
