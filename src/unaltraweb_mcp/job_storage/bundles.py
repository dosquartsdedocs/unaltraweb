"""Complete-tree and local-reference checks for retained native job products.

This module is also executed, unchanged, in the bounded volume utility. Bundle
schemas and historical integration records remain artifact-handoff-v1.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from unaltraweb_mcp import artifact_handoff_v1 as handoff

VALIDATOR_SHA256 = globals().get("_SOURCE_SHA256") or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MAX_TEXT = 16*1024*1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def check(root, manifest_path, expected_sha256):
    references = []
    with closing(handoff.Workspace(str(root))) as workspace:
        verifier = handoff.Verifier(workspace)
        document, files, _ = verifier.bundle(manifest_path, expected_sha256)
        prefix = manifest_path.rpartition("/")[0]

        def raw(relative, limit=MAX_TEXT):
            return workspace.read(handoff.join(prefix, relative), limit, collect=True)[2]

        def resource(source, target, *, project_relative=False):
            if not target or target.startswith("#"):
                return
            parsed = urlsplit(target)
            if parsed.scheme == "data":
                require(re.fullmatch(r"data:image/(png|jpeg|jpg);base64,[A-Za-z0-9+/=\s]+", target) is not None,
                        "Unsupported embedded SVG resource")
                decoded = base64.b64decode(target.partition(",")[2], validate=True)
                require(len(decoded) <= MAX_TEXT, "Embedded SVG resource exceeds its bound")
                return
            require(not parsed.scheme and not parsed.netloc and not parsed.query and not parsed.path.startswith("/"),
                    "Unretained remote or absolute rendering resource: " + target)
            decoded = unquote(parsed.path)
            require("\\" not in decoded and "\x00" not in decoded, "Unsafe rendering reference")
            base = str(PurePosixPath(source).parent)
            if project_relative:
                match = re.match(r"(payload/(?:inputs|results)/project)/", source)
                require(match is not None, "Vega source has no declared project resource root")
                base = match.group(1)
            resolved = posixpath.normpath(posixpath.join(base, decoded))
            handoff.safe_path(resolved)
            require(resolved in files, "Missing retained resource: " + resolved)
            references.append({"source": source, "target": resolved, "sha256": files[resolved]["sha256"]})

        def css_references(source, text):
            import tinycss2
            values = tinycss2.parse_component_value_list(text)

            def visit(tokens):
                for token in tokens:
                    require(token.type != "error", "Unverifiable SVG stylesheet")
                    if token.type == "url":
                        resource(source, token.value)
                    elif token.type == "function":
                        if token.lower_name == "url":
                            content = [item for item in token.arguments if item.type not in {"whitespace", "comment"}]
                            require(len(content) == 1 and content[0].type in {"string", "url", "ident"}, "Unverifiable CSS URL")
                            resource(source, content[0].value)
                        else:
                            visit(token.arguments)
                    elif hasattr(token, "content"):
                        visit(token.content)
            visit(values)
            require(not re.search(r"(?i)@import\b", text), "External/imported SVG stylesheets require an explicit supported profile")

        for relative, entry in files.items():
            if relative.endswith(".edited.svg"):
                original = files.get(relative.removesuffix(".edited.svg") + ".svg")
                require(original is not None and entry.get("variant_of") == original["id"] and entry["ownership"] == "author",
                        "Edited SVG does not retain its declared original")
                references.append({"source": relative, "target": original["path"], "sha256": original["sha256"]})
            if relative.lower().endswith(".svg"):
                content = raw(relative)
                require(b"<!DOCTYPE" not in content.upper() and b"<!ENTITY" not in content.upper(), "SVG external entities are unsupported")
                tree = ET.fromstring(content)
                require(tree.tag.rsplit("}", 1)[-1] == "svg", "Expected a retained SVG document")
                for element in tree.iter():
                    tag = element.tag.rsplit("}", 1)[-1]
                    require(tag != "script", "Executable SVG content is unsupported")
                    for name, value in element.attrib.items():
                        local = name.rsplit("}", 1)[-1]
                        require(not local.lower().startswith("on"), "Executable SVG attributes are unsupported")
                        if local in {"href", "src"}:
                            if tag == "a" and urlsplit(value).scheme in {"http", "https"}:
                                continue
                            resource(relative, value)
                        if local == "style" or "url(" in value.lower():
                            css_references(relative, value)
                    if tag == "style":
                        css_references(relative, element.text or "")
            elif relative.endswith((".vl.json", ".vg.json")):
                spec = handoff.parse_json(raw(relative))
                pending = [spec]
                while pending:
                    value = pending.pop()
                    if isinstance(value, dict):
                        if "url" in value:
                            require(isinstance(value["url"], str), "Dynamic Vega data references are unsupported")
                            resource(relative, value["url"], project_relative=True)
                        pending.extend(value.values())
                    elif isinstance(value, list):
                        pending.extend(value)

        request_entry = next(item for item in document["files"] if item["id"] == document["request"])
        request = handoff.parse_json(raw(request_entry["path"], handoff.MAX_MANIFEST_BYTES))
        if document["producer"]["name"] == "unaltraweb":
            require(request.get("kind") == "unaltraweb.job-request" and type(request.get("schema_version")) is int
                    and request["schema_version"] == 1, "Unsupported native job request")
            inputs = request.get("inputs")
            require(isinstance(inputs, list), "Missing effective input inventory")
            expected = set()
            for item in inputs:
                target = "payload/inputs/" + handoff.safe_path(item["path"])
                require(target not in expected and target in files, "Missing or duplicate native input")
                expected.add(target)
                require((files[target]["sha256"], files[target]["bytes"]) == (item["sha256"], item["bytes"]), "Native input differs from its effective request")
            actual = {path for path in files if path.startswith("payload/inputs/") and path != request_entry["path"]}
            require(actual == expected, "Unresolved native source/resource inventory")
            profile = "unaltraweb-job-v1"
        else:
            raise ValueError("Producer domain has not yet been accepted by this receiver: " + document["producer"]["name"])
        workspace.recheck()
        report = {"ok": True, "domain_profile": profile, "bundle_sha256": expected_sha256,
                  "validator_sha256": VALIDATOR_SHA256, "bundles": verifier.bundle_count,
                  "verified_files": len(workspace.snapshots), "references": references,
                  "files": [{"path": name, "sha256": item["sha256"], "bytes": item["bytes"]} for name, item in sorted(files.items())]}
        report["evidence_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
        return report
