"""Prepare the versioned caption fixture for an explicit local PDF review."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "caption-credits"


def prepare_demo(project: Path) -> Path:
    # copytree refuses any existing destination; never reset review evidence.
    shutil.copytree(FIXTURE, project)
    images = project / "assets/img"
    images.mkdir(parents=True)
    shutil.copyfile(ROOT / "docs/assets/img/caption-credits-demo.svg", images / "caption-credits-demo.svg")
    return project


def builder():
    spec = importlib.util.spec_from_file_location("caption_demo_pdf", ROOT / "scripts/manual/build_pdf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="tmp/caption-credits-review")
    parser.add_argument("--build", action="store_true", help="Build with the available Pandoc/XeLaTeX worker tools")
    args = parser.parse_args()
    project = (ROOT / args.output).resolve()
    if not project.is_relative_to(ROOT / "tmp") or project == ROOT / "tmp":
        parser.error("Choose a new review directory below this checkout's tmp/.")
    prepare_demo(project)
    result = {"project": str(project)}
    if args.build:
        pdf = builder()
        result["manifest"] = pdf.build_language(project, pdf.read_yaml(project / "_config.yml"), "ca")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
