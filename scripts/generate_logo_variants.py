#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


MONOCHROME_COLOR_RE = re.compile(r"(?i)(?P<prefix>\b(?:fill|stroke)\s*[:=]\s*[\"']?)#(?:000000|000)\b")
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def variant(value: str) -> tuple[Path, str]:
    try:
        output, color = value.rsplit("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("variants must use OUTPUT=#RRGGBB") from exc
    if not output or not HEX_COLOR_RE.fullmatch(color):
        raise argparse.ArgumentTypeError("variants must use OUTPUT=#RRGGBB")
    return Path(output), color.lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create color variants from a black monochrome SVG logo.")
    parser.add_argument("source", type=Path)
    parser.add_argument("variants", nargs="+", type=variant, metavar="OUTPUT=#RRGGBB")
    args = parser.parse_args()

    source = args.source.resolve()
    text = source.read_text(encoding="utf-8")

    for output, color in args.variants:
        rendered, replacements = MONOCHROME_COLOR_RE.subn(lambda match: match.group("prefix") + color, text)
        if replacements == 0:
            parser.error(f"{source} has no black fill or stroke declarations to replace")
        destination = output.resolve()
        if destination == source:
            parser.error("output must not overwrite the source SVG")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
        print(f"{destination}: {color} ({replacements} replacements)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
