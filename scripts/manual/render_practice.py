#!/usr/bin/env python3
"""Run only inside the bounded PDF toolchain with /source readonly and /out writable."""
import json
from pathlib import Path
import re
import subprocess

SOURCE = Path("/source")
OUTPUT = Path("/out")


def run(command, log):
    subprocess.run(command, cwd=OUTPUT, check=True, stdout=log, stderr=subprocess.STDOUT)


def main():
    request = json.loads((SOURCE / "request.json").read_text())
    basename = request["basename"]
    assert basename in {"LLEGIU-ME", "LEEME", "README"}
    filters = request["filters"]
    assert filters == ["practice-layout.lua", "code-blocks.lua", "figure-captions.lua", "practice-finish.lua"]
    with (OUTPUT / "render.log").open("x") as log:
        command = ["pandoc", "/source/source.md", "--standalone",
                   "--from=markdown+fenced_divs+pipe_tables+link_attributes-raw_tex-raw_html",
                   "--number-sections", "--top-level-division=section", "--metadata-file=/source/metadata.yml",
                   "--template=/source/practice.tex", "--resource-path=/source", "-t", "latex", "-o", "practice.tex"]
        for name in filters:
            command.append("--lua-filter=/source/" + name)
        run(command, log)
        for _ in range(3):
            run(["xelatex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "practice.tex"], log)
        run(["qpdf", "--deterministic-id", "--object-streams=generate", "--recompress-flate",
             "--compression-level=9", "practice.pdf", basename + ".pdf"], log)
        run(["pdftoppm", "-f", "1", "-singlefile", "-png", "-r", "110", basename + ".pdf", "preview"], log)
    latex_log = (OUTPUT / "practice.log").read_text(errors="replace")
    diagnostics = [line for line in latex_log.splitlines() if re.search(r"Overfull|Underfull|Warning:|Missing character", line)]
    from pypdf import PdfReader
    pdf = PdfReader(OUTPUT / (basename + ".pdf"))
    if not pdf.pages or any(float(page.mediabox.width) < float(page.mediabox.height) for page in pdf.pages):
        raise ValueError("Practice PDF must contain landscape pages")
    report = {"pages": len(pdf.pages), "diagnostics": diagnostics,
              "review_required": True, "publishes": False}
    (OUTPUT / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
