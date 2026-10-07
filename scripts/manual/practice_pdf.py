#!/usr/bin/env python3
"""Consumer-bound entry point used by the factory Make contract."""
import argparse
import json
import os
from pathlib import Path
import sys

FACTORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FACTORY / "src"))
from unaltraweb_mcp.distribution import consumer_integration
from unaltraweb_mcp.practice_pdf import build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    try:
        result = build(Path(args.project), FACTORY, os.environ.get("PRACTICE_SOURCE", ""),
                       os.environ.get("PRACTICE_VERSION", ""), run=os.environ.get("PRACTICE_RUN", ""),
                       image=os.environ.get("MANUAL_PDF_IMAGE") or consumer_integration()["manual_pdf_image"],
                       dry_run=os.environ.get("PRACTICE_DRY_RUN", "0") == "1")
    except (OSError, ValueError, RuntimeError) as exc:
        result = {"ok": False, "publishes": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
