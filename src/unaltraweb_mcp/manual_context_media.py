"""The portable v1 receiver's image boundary, without an Itemarium dependency.

No conversion, rendering, resource fetching or execution takes place here.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

IMAGE_TYPES = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".webp": "WEBP", ".svg": "SVG"}
MAX_IMAGE = 10 * 1024**2


def validate_image(data: bytes, path: str) -> None:
    suffix = Path(path).suffix.lower()
    if suffix not in IMAGE_TYPES or not 0 < len(data) <= MAX_IMAGE:
        raise ValueError(f"{path}: v1 requires a standalone PNG/JPEG/GIF/WebP/SVG of at most 10 MiB; prepare a compatible output explicitly")
    if suffix != ".svg":
        from PIL import Image
        try:
            with Image.open(io.BytesIO(data), formats=[IMAGE_TYPES[suffix]]) as image:
                if image.width * image.height > 64_000_000:
                    raise ValueError(f"{path}: image exceeds the 64-megapixel inspection bound")
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError(f"{path}: invalid or oversized raster; prepare a bounded compatible output: {exc}") from exc
        return
    text = data.decode("utf-8")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)|<\?xml-stylesheet", text, re.I):
        raise ValueError(f"{path}: standalone SVG must not contain DTD/entities/stylesheets")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f"{path}: invalid SVG XML: {exc}") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError(f"{path}: XML is not an SVG")
    for count, node in enumerate(root.iter(), 1):
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if count > 20000:
            raise ValueError(f"{path}: SVG exceeds the node budget")
        if tag in {"script", "foreignobject", "image", "iframe", "animate", "animatemotion", "animatetransform", "set"}:
            raise ValueError(f"{path}: Itemarium v1 cannot receive SVG <{tag}> (including embedded capture rasters); prepare an explicitly reviewed standalone output or coordinate a receiver extension")
        for key, value in node.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if name.startswith("on") or (name in {"href", "src"} and value and not value.startswith("#")):
                raise ValueError(f"{path}: active/external SVG reference")
            _css(value, path)
        _css(node.text or "", path)


def _css(value: str, path: str) -> None:
    lowered = value.lower()
    without_local = re.sub(r"url\(#[a-z_][-:.a-z0-9_]*\)", "", lowered)
    if any(token in without_local for token in ("@import", "url(", "javascript:", "expression(", "\\")):
        raise ValueError(f"{path}: external or unsupported SVG style resource")


def image_references(markdown: str) -> list[str]:
    """Inspect the same embedded/link forms the receiver inspects, including bad URIs."""
    found = []

    class Images(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "img":
                found.append(dict(attrs).get("src", ""))

    parser = MarkdownIt("commonmark")
    parser.validateLink = lambda value: True
    html = Images()
    def visit(tokens):
        for token in tokens:
            if token.type == "image":
                found.append(token.attrGet("src") or "")
            elif token.type in {"html_block", "html_inline"}:
                html.feed(token.content)
            elif token.type == "link_open":
                href = token.attrGet("href") or ""
                url = urlsplit(href)
                if not url.scheme and not url.netloc and Path(url.path).suffix.lower() in IMAGE_TYPES:
                    found.append(href)
            if token.children:
                visit(token.children)
    visit(parser.parse(markdown))
    return found
