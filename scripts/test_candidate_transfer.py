#!/usr/bin/env python3
"""Synthetic native candidate for the real Actions-v4 transfer regression.

No consumer content, publication, secrets, network acquisition or S3 account.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "test")]
from unaltraweb_mcp import candidate_storage as storage
import test_release_assets as native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "verify"])
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--sha256", default="")
    args = parser.parse_args()
    fixture = native.ReleaseAssetVerificationTests()
    fixture.setUp()
    try:
        fixture.repository = os.environ.get("GITHUB_REPOSITORY", fixture.repository)
        fixture.reviewed_sha = os.environ.get("GITHUB_SHA", fixture.reviewed_sha)
        fixture.write_assets()
        binding = storage.identity(fixture.repository, fixture.selector, fixture.reviewed_sha,
                                   os.environ.get("GITHUB_RUN_ID", "123"), os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
        if args.operation == "prepare":
            sha = storage.seal(fixture.assets, args.path, storage.DEFAULT_POLICY, binding)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
                    handle.write(f"sha256={sha}\n")
            print(json.dumps({"sha256": sha, "synthetic": True, "publishes": False}))
        else:
            storage.verify(args.path, storage.DEFAULT_POLICY, binding, args.sha256)
            arguments = fixture.arguments()
            arguments.assets = args.path / "release-assets"
            result = native.verify_release_assets.verify(arguments)
            print(json.dumps({**result, "synthetic": True, "publishes": False}))
    finally:
        fixture.tearDown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
