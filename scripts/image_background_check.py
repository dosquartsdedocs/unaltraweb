#!/usr/bin/env python3
"""Run the packaged image background advisory without an MCP factory runtime."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from unaltraweb_mcp.image_backgrounds import main


if __name__ == "__main__":
    raise SystemExit(main())
