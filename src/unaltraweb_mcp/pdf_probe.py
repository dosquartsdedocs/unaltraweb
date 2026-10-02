"""Bounded, non-rendering inspection of a retained PDF, read from stdin."""
from __future__ import annotations

import io
import json
import resource
import sys


def main() -> int:
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    try:
        from pypdf import PdfReader
        from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

        raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024 or not raw.startswith(b"%PDF-"):
            raise ValueError("PDF exceeds the 32 MiB letter profile or has no PDF header")
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 64:
            raise ValueError("Encrypted PDFs or documents outside 1–64 pages are unsupported")
        pending = [(reader.trailer, False)]
        visited = set()
        count = 0
        while pending:
            value, action = pending.pop()
            count += 1
            if count > 100000:
                raise ValueError("PDF object graph exceeds the inspection bound")
            if isinstance(value, IndirectObject):
                # A shared object may first be visited through an inert alias,
                # then as an action. Validate both contexts independently.
                key = (value.idnum, value.generation, action)
                if key in visited:
                    continue
                visited.add(key)
                pending.append((value.get_object(), action))
            elif isinstance(value, DictionaryObject):
                if any(key in value for key in ("/JavaScript", "/JS", "/EmbeddedFiles", "/AA")):
                    raise ValueError("Active PDF content or embedded files are unsupported")
                if value.get("/Type") == "/Filespec" or (isinstance(value, StreamObject) and "/F" in value):
                    raise ValueError("PDF external file references are unsupported")
                is_action = action or value.get("/Type") == "/Action"
                if is_action:
                    if value.get("/S") not in ("/GoTo", "/URI"):
                        raise ValueError("Only internal destinations and textual URI links are supported")
                    if value.get("/S") == "/URI" and not str(value.get("/URI", "")).startswith(("https://", "http://", "mailto:")):
                        raise ValueError("Unsupported PDF URI action")
                pending.extend((child, "open-action" if key == "/OpenAction" else key == "/A" or (is_action and key == "/Next")) for key, child in value.items())
            elif isinstance(value, ArrayObject):
                # OpenAction may be an internal destination array; Next arrays
                # contain actions and must retain action validation context.
                pending.extend((child, False if action == "open-action" else action) for child in value)
        print(json.dumps({"ok": True, "pages": len(reader.pages)}))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
