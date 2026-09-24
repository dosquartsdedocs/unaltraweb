"""Advisory, offline background checks for referenced publication images."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import stat
import sys
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .editorial_sources import Reader, corpus, default_language, relative_path, strict_json, yaml_mapping, yaml_value
from .processes import run_process

IMAGE_SUFFIXES = (".svg", ".svgz", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif", ".ico")
DIAGRAM_SUFFIXES = (".mmd", ".mermaid", ".puml", ".plantuml", ".uml")
CAPTURE_SUFFIXES = (".capture.yml", ".capture.yaml")
VEGA_SUFFIXES = (".vl.json", ".vg.json")
COMPUTE_SUFFIXES = (".qmd", ".rmd", ".r", ".py", ".ipynb")
VISUAL_SUFFIXES = tuple(sorted({*IMAGE_SUFFIXES, *DIAGRAM_SUFFIXES, *CAPTURE_SUFFIXES, *VEGA_SUFFIXES,
                                *COMPUTE_SUFFIXES, ".edited.svg", *(suffix + ".svg" for suffix in DIAGRAM_SUFFIXES)}, key=len, reverse=True))
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_TOTAL_BYTES = 128 * 1024 * 1024
MAX_IMAGES = 128
MAX_REFERENCES = 2000
CHECK_SECONDS = 30.0
IMAGE_FIELDS = {"image", "img", "cover", "cover_image", "photo", "avatar", "logo", "logo_inverse", "logo_cafe", "thumbnail", "preview"}


class ImageReferences(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        names = {"img": ("src",), "source": (), "video": ("poster",), "object": ("data",), "embed": ("src",)}.get(tag, ())
        if tag == "link" and "icon" in (values.get("rel") or ""):
            names = ("href",)
        for name in names:
            if values.get(name):
                self.references.append((self.getpos()[0], values[name]))
        if tag in {"img", "source"} and values.get("srcset"):
            srcset = values["srcset"]
            if srcset.lstrip().startswith("data:"):
                self.references.append((self.getpos()[0], "data:"))
            else:
                self.references.extend((self.getpos()[0], item.strip().split()[0]) for item in srcset.split(",") if item.strip())
        if len(self.references) > MAX_REFERENCES:
            raise ValueError("Image reference budget exceeded.")


def _metadata_images(value: Any, *, parent_image: bool = False, depth: int = 0):
    if depth > 20:
        raise ValueError("Image metadata nesting limit exceeded.")
    if isinstance(value, dict):
        for key, child in value.items():
            image_field = isinstance(key, str) and (key in IMAGE_FIELDS or (parent_image and key in {"path", "src", "file"}))
            if image_field and isinstance(child, str) and child.strip():
                yield child
            elif isinstance(child, (dict, list)):
                yield from _metadata_images(child, parent_image=image_field, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            if parent_image and isinstance(child, str) and child.strip():
                yield child
            else:
                yield from _metadata_images(child, parent_image=parent_image, depth=depth + 1)


def _source_references(text: str) -> list[tuple[int, str]]:
    # Resolve only literal supported URL sugar, never evaluate Liquid or code.
    text = re.sub(r"\{\{\s*site\.baseurl\s*\}\}", "", text)
    text = re.sub(r'''\{\{\s*(['"])(.*?)\1\s*\|\s*(?:relative_url|absolute_url)\s*\}\}''', lambda m: m[2], text)
    from .editorial_sources import blank

    text = re.sub(r"<!--.*?(?:-->|\Z)|{%\s*comment\s*%}.*?(?:{%\s*endcomment\s*%}|\Z)", lambda m: blank(m[0]), text, flags=re.S)
    visible, fence = [], ""
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            visible.append(blank(line))
        elif fence or line.startswith(("    ", "\t")):
            visible.append(blank(line))
        else:
            visible.append(re.sub(r"(`+)[^`\n]*?\1", lambda m: blank(m[0]), line))
    text = "".join(visible)
    references = []
    # Escaped and ordinary alt-text characters must be disjoint so malformed
    # labels with many backslashes cannot trigger exponential backtracking.
    for match in re.finditer(r"!\[(?:\\.|[^\\\]\n])*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))", text):
        references.append((text[:match.start()].count("\n") + 1, match[1] or match[2]))
    parser = ImageReferences()
    parser.feed(text)
    references.extend(parser.references)
    return references


def _collect(reader: Reader, config: dict, source: str, output_folder: str) -> list[dict]:
    language = default_language(config)
    if source and source.lower().endswith(VISUAL_SUFFIXES):
        relative_path(source)
        return [{"path": source, "line": 0, "reference": source, "language": language, "direct": True}]
    references = []
    if output_folder:
        paths = reader.walk(output_folder)
        if not paths or paths == [output_folder]:
            raise ValueError("Choose a non-empty rendered output directory.")
        for path in paths:
            if path.lower().endswith(".html"):
                parser = ImageReferences()
                parser.feed(reader.text(path))
                references.extend({"path": path, "line": line, "reference": url, "language": language} for line, url in parser.references)
    else:
        uw = config.get("unaltraweb") or {}
        if not isinstance(uw, dict):
            raise ValueError("unaltraweb configuration must be a mapping.")
        selected = corpus(reader, config, str(uw.get("site_profile") or ""), source)
        for path, record in selected["sources"].items():
            text = record["text"]
            if path == "_config.yml" or path.startswith("_data/"):
                data = strict_json(text) if path.endswith(".json") else yaml_value(text)
                references.extend({"path": path, "line": 0, "reference": url, "language": language, "metadata": True}
                                  for url in _metadata_images(data))
            else:
                front = re.match(r"\A---\s*\n(.*?)\n---[^\S\n]*(?:\n|\Z)", text, re.S)
                front_data = yaml_mapping(front[1]) if front else {}
                document_language = str(front_data.get("lang") or next((part for part in Path(path).parts if part in config.get("languages", [])), language))
                references.extend({"path": path, "line": 0, "reference": url, "language": document_language, "metadata": True}
                                  for url in _metadata_images(front_data))
                body = ("\n" * text[:front.end()].count("\n") + text[front.end():]) if front else text
                references.extend({"path": path, "line": line, "reference": url, "language": document_language}
                                  for line, url in _source_references(body))
            if len(references) > MAX_REFERENCES:
                raise ValueError("Image reference budget exceeded; select a smaller source.")
    if len(references) > MAX_REFERENCES:
        raise ValueError("Image reference budget exceeded; select a smaller source.")
    return references


def _local_path(item: dict, config: dict, output_folder: str) -> str:
    raw = item["reference"].strip()
    if any(token in raw for token in ("{{", "{%")):
        raise ValueError("Dynamic image references need the rendered-output check.")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        site = urllib.parse.urlsplit(str(config.get("url") or ""))
        if parsed.scheme not in {"http", "https"} or not site.netloc or parsed.netloc != site.netloc:
            raise ValueError("Remote/data images are not fetched; inspect a local published asset.")
    if parsed.fragment:
        raise ValueError("Fragment-selected images need review of that exact rendered view.")
    path = urllib.parse.unquote(parsed.path)
    if not path or "\\" in path or any(ord(c) < 32 for c in path):
        raise ValueError("Invalid local image reference.")
    baseurl = "/" + str(config.get("baseurl") or "").strip("/")
    if baseurl != "/" and path.startswith(baseurl + "/"):
        path = path[len(baseurl):]
    if output_folder:
        base = output_folder if path.startswith("/") else posixpath.dirname(item["path"])
        result = posixpath.normpath(posixpath.join(base, path.lstrip("/")))
        if not result.startswith(output_folder + "/"):
            raise ValueError("Image URL escapes the rendered output directory.")
    elif path.startswith("/") or path.startswith("assets/") or item.get("metadata") or item.get("direct"):
        result = posixpath.normpath(path.lstrip("/"))
    else:
        result = posixpath.normpath(posixpath.join(posixpath.dirname(item["path"]), path))
    relative_path(result)
    if result.split("/")[0] in {"context", ".cache", ".unaltraweb"}:
        raise ValueError("Private editorial/runtime paths are not image assets.")
    return result


def _exists(reader: Reader, path: str) -> bool:
    try:
        with reader.parent(path) as (parent, name):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Image input must be a regular, non-symlink file: {path}")
            return True
    except FileNotFoundError:
        return False


def _resolve(reader: Reader, path: str, language: str, config: dict) -> tuple[str, str]:
    original = path
    default = default_language(config)
    suffix = next((suffix for suffix in VISUAL_SUFFIXES if path.lower().endswith(suffix)), "")
    if language != default and suffix:
        stem = path[:-len(suffix)]
        codes = {*config.get("languages", []), language, default}
        if not any(stem.lower().endswith("." + str(code).lower()) for code in codes):
            variant = f"{stem}.{language}{path[-len(suffix):]}"
            if _exists(reader, variant):
                path = variant
    if not _exists(reader, path):
        raise ValueError(f"Missing image/source: {path}")
    lower = path.lower()
    if lower.endswith(DIAGRAM_SUFFIXES):
        candidates = [path + ".edited.svg", path + ".svg"]
    elif lower.endswith(CAPTURE_SUFFIXES):
        base = path.rsplit(".", 1)[0]
        candidates = [base + ".edited.svg", base + ".svg"]
    elif lower.endswith(VEGA_SUFFIXES):
        manifest = yaml_mapping(reader.text(".vegavisuals.yml"))
        entries = manifest.get("visualizations") or []
        matches = [item for item in entries if isinstance(item, dict) and item.get("source") == path]
        if len(matches) != 1 or not isinstance(matches[0].get("output"), str):
            raise ValueError("Vega image needs exactly one declared output.")
        candidates = [relative_path(matches[0]["output"])]
    elif lower.endswith(COMPUTE_SUFFIXES):
        text = reader.text(path)
        if lower.endswith(".ipynb"):
            metadata = strict_json(text).get("metadata", {}).get("unaltraweb_front_matter", {})
        else:
            if lower.endswith((".r", ".py")):
                text = "\n".join(re.sub(r"^#'? ?", "", line) for line in text.splitlines() if line.startswith("#"))
            front = re.search(r"(?:\A|\n)---\s*\n(.*?)\n---", text, re.S)
            metadata = yaml_mapping(front[1]) if front else {}
        compute = metadata.get("unaltraweb_compute") or {}
        outputs = compute.get("outputs") or ([compute["output"]] if compute.get("output") else [])
        if compute.get("mode") != "figure" or not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], str):
            raise ValueError("Computed image needs a declared mode: figure output.")
        output = relative_path(outputs[0])
        candidates = [str(Path(output).with_suffix(".edited.svg")), output]
    else:
        return path, path if path != original else original
    for output in candidates:
        if _exists(reader, output):
            return output, path
    raise ValueError(f"Render the missing image output from {path} before inspecting it.")


def _inspect(data: bytes, timeout: float) -> dict:
    env = {**os.environ, "HOME": "/proc/unaltraweb-image-check", "XDG_CACHE_HOME": "/proc/unaltraweb-image-check"}
    result = run_process([sys.executable, "-I", "-B", str(Path(__file__).with_name("image_probe.py"))],
                         input_data=data, env=env, timeout_seconds=max(.1, min(10.0, timeout)), output_limit=8192)
    if result.returncode or result.stdout_truncated or result.stderr_truncated:
        return {"state": "unverifiable", "reason": "Image decoder exceeded its limits or could not complete."}
    value = strict_json(result.stdout)
    if not isinstance(value, dict) or value.get("state") not in {"opaque", "transparent", "unverifiable"}:
        raise ValueError("Invalid image decoder result.")
    return value


def image_background_check(project: Path, source: str = "", output_folder: str = "") -> dict[str, Any]:
    images: dict[str, dict] = {}
    warnings = []
    deadline = time.monotonic() + CHECK_SECONDS
    try:
        if source and output_folder:
            raise ValueError("Choose a source or a rendered output directory, not both.")
        with Reader(project) as reader, Reader(project, max_bytes=MAX_IMAGE_BYTES, max_total_bytes=MAX_IMAGE_TOTAL_BYTES) as binary:
            config = yaml_mapping(reader.text("_config.yml", optional=True))
            references = _collect(reader, config, source, output_folder)
            cache: dict[str, dict] = {}
            for item in references:
                path, owner = "", ""
                try:
                    path = _local_path(item, config, output_folder)
                    if not output_folder:
                        path, owner = _resolve(reader, path, item["language"], config)
                    key = path
                    if key in images:
                        images[key]["reference_count"] += 1
                        if len(images[key]["references"]) < 10:
                            images[key]["references"].append({"path": item["path"], "line": item["line"]})
                        continue
                    if len(images) >= MAX_IMAGES or time.monotonic() >= deadline:
                        raise ValueError("Image inspection budget reached; inspect a smaller source explicitly.")
                    data = binary.read(path)
                    sha256 = hashlib.sha256(data).hexdigest()
                    if sha256 not in cache:
                        cache[sha256] = _inspect(data, deadline - time.monotonic())
                    result = {**cache[sha256], "sha256": sha256}
                except (OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
                    key = path or f"unresolved:{item['path']}:{item['line']}:{hashlib.sha256(item['reference'].encode()).hexdigest()}"
                    result = {"state": "unverifiable", "reason": str(exc)[:400]}
                if key in images:
                    images[key]["reference_count"] += 1
                    if len(images[key]["references"]) < 10:
                        images[key]["references"].append({"path": item["path"], "line": item["line"]})
                    continue
                record = {**result, "path": path, "owner": owner, "references": [{"path": item["path"], "line": item["line"]}], "reference_count": 1}
                images[key] = record
                if result["state"] != "opaque":
                    transparent = result["state"] == "transparent"
                    action = f"Choose an opaque background colour in {owner or path or item['path']} and export/render again."
                    if not transparent:
                        action = "Resolve the inspection reason; use supported local, self-contained images and the Pillow/CairoSVG inspection dependencies."
                    if path.endswith(".edited.svg"):
                        action = f"Review the author-owned {path} before editing its background; preserve the edited override."
                    warnings.append({"severity": "warning", "code": "UW-IMAGE-TRANSPARENT" if transparent else "UW-IMAGE-UNVERIFIABLE",
                                     "path": path or item["path"], "source": item["path"], "line": item["line"],
                                     "message": "Image has transparent or partially transparent pixels." if transparent else result.get("reason", "Image background could not be verified."),
                                     "remediation": action})
        return {"ok": True, "offline": True, "read_only": True, "source": source, "output_folder": output_folder,
                "images": list(images.values()), "image_count": len(images), "reference_count": len(references), "warnings": warnings,
                "policy": "Advisory: any opaque colour is valid; no files are changed and white is not imposed.",
                "coverage": "Local referenced raster frames and bounded self-contained SVG samples; remote/data/fragment references and unsupported SVG features are reported as unverifiable."}
    except (OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        return {"ok": False, "offline": True, "read_only": True, "images": [], "image_count": 0, "warnings": warnings,
                "error": str(exc), "source": source, "output_folder": output_folder}


def print_warnings(result: dict) -> None:
    for finding in result.get("warnings", []):
        print(f"{finding['code']}: {finding['path']}: {finding['message']} {finding['remediation']}", file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source", default="")
    parser.add_argument("--output-folder", default="")
    args = parser.parse_args(argv)
    result = image_background_check(args.project, args.source, args.output_folder)
    print_warnings(result)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
