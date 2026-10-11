#!/usr/bin/env python3
"""Validate the private-runtime declaration; native checks require explicit opt-in.

There is deliberately no installation/download operation. Public build/CI checks
metadata and unit fixtures only; the hub prepares the authenticated private images.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from unaltraweb_mcp import practice_verifier
from unaltraweb_mcp.distribution import distribution_contract

COMPONENT = "qgis_practice_verifier"


def required(contract):
    return "manual-practice-compose" in contract.get("wheel_contract", {}).get("factory_required_mcp", [])


def publication_errors(contract):
    if not required(contract):
        return []
    try:
        runtime = practice_verifier.runtime_contract()
        item = contract["components"][COMPONENT]
        if (item["kind"] != "companion" or item["name"] != runtime["provider"]["name"]
                or item["version"] != runtime["provider"]["version"] or item["release_status"] != "released"
                or item["release"] != runtime["release"]["tag"] or item["included_in_wheel"] is not False
                or item["repository"] != runtime["release"]["repository"]
                or item["reference"] != item["repository"] + ".git@" + item["release"]
                or not set(runtime["profiles"]) <= set(item["features"])):
            return ["Private QGIS runtime metadata differs from the accepted release declaration"]
    except (KeyError, TypeError, OSError, ValueError) as exc:
        return ["Private QGIS runtime declaration is incomplete: " + str(exc)]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-runtime", action="store_true", help="Opt in to native checks on already hub-prepared private images")
    parser.add_argument("--project", type=Path, help="Explicit bound workspace for the private check")
    args = parser.parse_args(argv)
    errors = publication_errors(distribution_contract())
    result = {"ok": not errors, "errors": errors, "origin": "prepared-image",
              "private_checks": {"state": "not_run", "reason": "Public CI does not acquire or execute the private QGIS runtime"}}
    if args.check_runtime:
        try:
            if errors or args.project is None or not args.project.is_absolute():
                raise ValueError("Native checking requires valid metadata and an explicit absolute project")
            profiles = {}
            for profile in practice_verifier.runtime_contract()["profiles"]:
                observed = practice_verifier.call(args.project, "schema", profile=profile)
                value = observed["result"]
                profiles[profile] = {"package": value["installed_package"], "schema_sha256": value["schema_sha256"], "origin": observed["origin"]}
            result["private_checks"] = {"state": "passed", "scope": "image/package/schema identity only; bundle/reopen acceptance is separate", "profiles": profiles}
        except (OSError, ValueError, RuntimeError) as exc:
            result.update(ok=False, errors=[*errors, str(exc)], private_checks={"state": "blocked", "reason": str(exc)})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
