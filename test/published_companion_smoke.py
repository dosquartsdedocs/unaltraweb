"""Explicit real-Docker acceptance of the installed published companion CLIs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from unaltraweb_mcp import site_tools


def invoke(cli: str, project: Path, *arguments: str) -> dict:
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "MCP_CONSUMER_WORKSPACE", "MCP_CLIENT_WORKSPACE"}}
    result = subprocess.run([cli, "--project", str(project), *arguments], env=environment,
                            cwd=project, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise AssertionError(f"{arguments}: {result.stdout}\n{result.stderr}")
    payload = json.loads(result.stdout)
    assert payload.get("ok"), payload
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diavisuals", required=True)
    parser.add_argument("--vegavisuals", required=True)
    args = parser.parse_args()
    factory = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="web-published-companions-") as temporary:
        project = Path(temporary) / "consumer with spaces"
        assert site_tools.new_web(project, site_profile_value="unaltredocs")["ok"]
        diagrams = project / "assets/diagrams"
        diagrams.mkdir(parents=True, exist_ok=True)
        for name, source in {
            "flow.mmd": "flowchart LR\n  A --> B\n",
            "sequence.puml": "@startuml\nAlice -> Bob: Published provider\n@enduml\n",
        }.items():
            (diagrams / name).write_text(source)
            invoke(args.diavisuals, project, "render-diagram", f"assets/diagrams/{name}",
                   f"assets/diagrams/{name}.svg")
        invoke(args.diavisuals, project, "project-check")

        invoke(args.vegavisuals, project, "init")
        charts = project / "assets/charts"
        charts.mkdir(parents=True)
        data = charts / "data.csv"
        data.write_text("label,value\nA,2\nB,4\n")
        (charts / "bars.vl.json").write_text(json.dumps({
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "data": {"url": "assets/charts/data.csv"}, "mark": "bar",
            "encoding": {"x": {"field": "label", "type": "nominal"},
                         "y": {"field": "value", "type": "quantitative"}},
        }))
        (charts / "point.vg.json").write_text(json.dumps({
            "$schema": "https://vega.github.io/schema/vega/v6.json", "width": 100, "height": 100,
            "marks": [{"type": "symbol", "encode": {"enter": {"x": {"value": 50}, "y": {"value": 50}}}}],
        }))
        (project / ".vegavisuals.yml").write_text(
            "version: 1\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations:\n"
            "  - name: bars\n    source: assets/charts/bars.vl.json\n    output: assets/charts/bars.svg\n"
            "    engine: vega-lite\n    format: svg\n    inputs: [assets/charts/data.csv]\n"
            "  - name: point\n    source: assets/charts/point.vg.json\n    output: assets/charts/point.svg\n"
            "    engine: vega\n    format: svg\n"
        )
        invoke(args.vegavisuals, project, "render-all")
        invoke(args.vegavisuals, project, "check")
        checked = site_tools.site_check(project, factory)
        assert checked["ok"], checked
        for provider in ("diavisuals", "vegavisuals"):
            receipt = json.loads((project / f".unaltraweb/receipts/{provider}.json").read_text())
            assert receipt["provider_version"] == "0.4.0", receipt
            assert len(receipt["artifacts"]) == 2, receipt
        original_data = data.read_bytes()
        data.write_text("label,value\nA,999\n")
        assert not site_tools.visualization_status(project, factory)["ok"]
        data.write_bytes(original_data)
        output = diagrams / "flow.mmd.svg"
        original_output = output.read_bytes()
        output.write_text("<svg/>")
        assert not site_tools.site_check(project, factory)["ok"]
        output.write_bytes(original_output)
        relocated = project.rename(Path(temporary) / "relocated")
        assert site_tools.site_check(relocated, factory)["ok"]
        print(json.dumps({"ok": True, "providers": ["diavisuals 0.4.0", "vegavisuals 0.4.0"],
                          "rendered": 4, "native_receipts": "accepted", "tampering": "rejected",
                          "relocation": "passed"}, indent=2))


if __name__ == "__main__":
    main()
