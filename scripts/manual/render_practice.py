#!/usr/bin/env python3
"""Run only inside the bounded PDF toolchain with /source readonly and /out writable."""
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

SOURCE = Path("/source")
OUTPUT = Path("/out")
MARKDOWN = "markdown+fenced_divs+pipe_tables+link_attributes-raw_tex-raw_html"


def run(command, log):
    subprocess.run(command, cwd=OUTPUT, check=True, stdout=log, stderr=subprocess.STDOUT)


def effective_source(request, log):
    """Apply the controller's authorised links to the actual Pandoc AST.

    This is a lookup/fail-closed rendering pass, not another filesystem resolver.
    The exact effective AST/Markdown are retained with the render artifacts.
    """
    assert request.get("portable_links") == "portable-links.json"
    raw = (SOURCE / "portable-links.json").read_bytes()
    if len(raw) > 1024*1024:
        raise ValueError("Portable link context exceeds its bound")
    links = json.loads(raw)
    assert links["kind"] == "unaltraweb-practice-reading-links" and links["schema_version"] == 1
    mapping = {entry["href"]: entry["target"] for entry in links["links"]}
    run(["pandoc", str(SOURCE / "source.md"), "--from="+MARKDOWN, "--to=json", "--output=source.parsed.json"], log)
    parsed = OUTPUT / "source.parsed.json"
    if parsed.stat().st_size > 16*1024*1024:
        raise ValueError("Practice AST exceeds its bound")
    document = json.loads(parsed.read_bytes())
    pending, count, applied = [(document, 0)], 0, []
    while pending:
        value, depth = pending.pop()
        count += 1
        if count > 200000 or depth > 128:
            raise ValueError("Practice AST exceeds its structural bound")
        if isinstance(value, dict):
            if value.get("t") == "Link":
                target = value["c"][-1]
                href = target[0]
                uri = urlsplit(href)
                if href in mapping:
                    target[0] = mapping[href]
                    applied.append({"source_href": href, "target_href": target[0]})
                elif not href.startswith("#") and uri.scheme.lower() not in {"https", "http", "mailto"}:
                    raise ValueError("Pandoc found a local/unsupported reading link without an authorised portable mapping: " + href)
            pending.extend((child, depth+1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth+1) for child in value)
    effective = OUTPUT / "source.effective.json"
    effective.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True)+"\n")
    run(["pandoc", str(effective), "--from=json", "--to=markdown", "--wrap=none", "--output=source.effective.md"], log)
    return links, applied


def check_pdf_links(pdf, context):
    allowed = {row["destination"] for row in context["targets"].values()}
    observed = []
    for page_number, page in enumerate(pdf.pages, 1):
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link" or annotation.get("/A") is None:
                continue
            action = annotation["/A"].get_object()
            kind = str(action.get("/S"))
            if kind == "/GoTo":
                continue
            if kind not in {"/URI", "/GoToR", "/Launch"}:
                raise ValueError("Unsupported action in a reading link")
            value = action.get("/URI") if kind == "/URI" else action.get("/F")
            if hasattr(value, "get_object"):
                value = value.get_object()
            if isinstance(value, dict):
                value = value.get("/UF") or value.get("/F")
            if not isinstance(value, str):
                raise ValueError("Reading link has no bounded file/URI target")
            uri = urlsplit(value)
            if uri.scheme.lower() in {"https", "http", "mailto"} or value.startswith("#"):
                continue
            if uri.scheme or uri.netloc or uri.query or unquote(uri.path, errors="strict") not in allowed:
                raise ValueError("Final PDF contains a local target outside its portable recipient selection: " + value)
            observed.append({"page": page_number, "kind": kind, "target": value})
    return observed


def main():
    request = json.loads((SOURCE / "request.json").read_text())
    basename = request["basename"]
    assert basename in {"LLEGIU-ME", "LEEME", "README"}
    filters = request["filters"]
    assert filters == ["practice-layout.lua", "code-blocks.lua", "figure-captions.lua", "practice-finish.lua"]
    with (OUTPUT / "render.log").open("x") as log:
        context, applied = effective_source(request, log)
        command = ["pandoc", str(OUTPUT / "source.effective.json"), "--standalone", "--from=json",
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
    local_links = check_pdf_links(pdf, context)
    report = {"pages": len(pdf.pages), "diagnostics": diagnostics,
               "portable_link_context": context["context"], "applied_links": applied, "local_pdf_links": local_links,
              "review_required": True, "publishes": False}
    (OUTPUT / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
