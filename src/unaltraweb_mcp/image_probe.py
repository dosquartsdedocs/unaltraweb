"""Bounded, file-free image decoding worker. Input is bytes on stdin, not a path."""
from __future__ import annotations

import base64
import gzip
import io
import json
import math
import re
import sys
import warnings
import xml.etree.ElementTree as ET

MAX_BYTES = 32 * 1024 * 1024
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 64_000_000
MAX_FRAMES = 32
MAX_SVG_SIDE = 1536
RASTER_FORMATS = ["PNG", "JPEG", "GIF", "WEBP", "TIFF", "BMP", "AVIF"]


def bounded_image(image) -> None:
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ValueError("Image exceeds the 16-megapixel decoding budget.")


def svg_resource(url: str, resource_type: str) -> bytes:
    """Only bounded embedded PNG/JPEG data; never open a URL or filesystem path."""
    from PIL import Image

    match = re.fullmatch(r"data:image/(?:png|jpeg);base64,([A-Za-z0-9+/=\s]+)", url)
    if match is None or len(url) > MAX_SVG_BYTES:
        raise ValueError("External or unsupported embedded SVG resources cannot be inspected.")
    data = base64.b64decode(re.sub(r"\s", "", match[1]), validate=True)
    with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as image:
        bounded_image(image)
        if getattr(image, "is_animated", False):
            raise ValueError("Animated images embedded in SVG require separate review.")
    return data


def svg_dimension(value: str, fallback: float) -> float:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(px|pt|pc|in|cm|mm)?\s*", value)
    if not match:
        return fallback
    scale = {None: 1, "px": 1, "pt": 96 / 72, "pc": 16, "in": 96, "cm": 96 / 2.54, "mm": 96 / 25.4}
    return float(match[1]) * scale[match[2]]


def inspect_svg(data: bytes) -> dict:
    from PIL import Image
    from cairosvg.surface import PNGSurface

    if len(data) > MAX_SVG_BYTES:
        raise ValueError("SVG exceeds the 8 MiB text budget.")
    text = data.decode("utf-8")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?xml-stylesheet", text, re.I):
        raise ValueError("SVG declarations and external stylesheets are not allowed in inspection.")
    root = ET.fromstring(text)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("XML input is not an SVG image.")
    for count, node in enumerate(root.iter(), 1):
        if count > 20000:
            raise ValueError("SVG node budget exceeded.")
        if node.tag.rsplit("}", 1)[-1] in {"script", "foreignObject", "animate", "animateMotion", "animateTransform", "set", "filter", "mask"}:
            raise ValueError("Dynamic SVG, masks and filters require rendered human review.")
    viewbox = re.split(r"[\s,]+", root.get("viewBox", "").strip())
    box = [float(value) for value in viewbox] if len(viewbox) == 4 else [0, 0, 300, 150]
    width = svg_dimension(root.get("width", ""), box[2])
    height = svg_dimension(root.get("height", ""), box[3])
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("SVG needs a finite positive viewport.")
    scale = min(1.0, MAX_SVG_SIDE / max(width, height))
    size = [max(1, math.ceil(width * scale)), max(1, math.ceil(height * scale))]
    # No background_color is supplied: painting one here would hide the defect.
    rendered = PNGSurface.convert(bytestring=data, output_width=size[0], output_height=size[1],
                                  unsafe=False, url_fetcher=svg_resource)
    with Image.open(io.BytesIO(rendered), formats=["PNG"]) as image:
        alpha = image.convert("RGBA").getchannel("A").getextrema()
    return {"state": "transparent" if alpha[0] < 255 else "opaque", "format": "SVG",
            "method": "svg-raster-sample", "sample_size": size, "alpha_min": alpha[0],
            "note": "Opacity is sampled at this bounded viewport, not certified at every possible scale."}


def inspect_raster(data: bytes) -> dict:
    from PIL import Image

    with Image.open(io.BytesIO(data), formats=RASTER_FORMATS) as image:
        detected = image.format
        total = 0
        for index in range(MAX_FRAMES + 1):
            try:
                image.seek(index)
            except EOFError:
                return {"state": "opaque", "format": detected, "method": "decoded-frames", "frames_checked": index, "alpha_min": 255}
            if index == MAX_FRAMES:
                raise ValueError("Image exceeds the 32-frame inspection budget.")
            bounded_image(image)
            total += image.width * image.height
            if total > MAX_TOTAL_PIXELS:
                raise ValueError("Image exceeds the total frame-pixel budget.")
            alpha = image.convert("RGBA").getchannel("A").getextrema()
            if alpha[0] < 255:
                return {"state": "transparent", "format": detected, "method": "decoded-frames",
                        "frames_checked": index + 1, "transparent_frame": index, "alpha_min": alpha[0]}
    raise ValueError("No image frame was decoded.")


def probe(data: bytes) -> dict:
    from PIL import Image

    if not data or len(data) > MAX_BYTES:
        raise ValueError("Image must be non-empty and at most 32 MiB.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        if data.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                data = stream.read(MAX_SVG_BYTES + 1)
            return inspect_svg(data)
        if data.lstrip().startswith((b"<", b"\xef\xbb\xbf")):
            return inspect_svg(data)
        return inspect_raster(data)


def main() -> int:
    sys.dont_write_bytecode = True
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        # Load trusted codecs before prohibiting regular-file growth: native
        # library discovery may probe an OS temporary directory during import.
        from PIL import Image
        if data.lstrip().startswith((b"<", b"\xef\xbb\xbf", b"\x1f\x8b")):
            from cairosvg.surface import PNGSurface
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        result = probe(data)
    except Exception as exc:
        result = {"state": "unverifiable", "reason": f"{type(exc).__name__}: {str(exc)[:300]}"}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
