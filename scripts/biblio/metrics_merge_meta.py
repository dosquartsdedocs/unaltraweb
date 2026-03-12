#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from metrics_common import SummaryContext, compute_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge metrics report JSON files into _data/metrics.yml")
    parser.add_argument(
        "--reports",
        nargs="*",
        default=[],
        help="Report JSON files. Defaults to tmp/metrics-report*.json",
    )
    parser.add_argument("--metrics-out", default="_data/metrics.yml", help="Output metrics YAML")
    parser.add_argument("--max-year-gap", type=int, default=2, help="Configured max year gap for Scimago")
    parser.add_argument("--updated-on", default="", help="Optional date override (YYYY-MM-DD)")
    return parser.parse_args()


def load_reports(paths: list[Path]) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    stale_total = 0
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries.extend(payload.get("entries", []))
        stale_total += int(payload.get("summary", {}).get("scimago_stale_rejected", 0) or 0)
    return entries, stale_total


def main() -> None:
    args = parse_args()
    report_paths = [Path(p) for p in args.reports] if args.reports else sorted(Path("tmp").glob("metrics-report*.json"))

    entries, stale_total = load_reports(report_paths)
    if not entries:
        raise SystemExit("No metrics report entries found to merge.")

    summary = compute_summary(entries, SummaryContext(max_year_gap=args.max_year_gap, stale_rejected=stale_total))
    updated_on = args.updated_on or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    metrics_payload = {
        "metrics": {
            "updated_on": updated_on,
            "sources": {
                "openalex": "merged-reports",
                "crossref": "merged-reports",
                "google_scholar": "merged-reports",
                "scimago": "merged-reports",
            },
            "summary": summary,
        }
    }

    out_path = Path(args.metrics_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(metrics_payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Merged {len(report_paths)} report(s) into {out_path}")


if __name__ == "__main__":
    main()
