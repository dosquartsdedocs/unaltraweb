"""Receiving-owner checks for Carta's published leaf letter-pdf-v1 profile.

Request snapshots and Pandoc evidence are data. Nothing in a bundle is executed.
"""
from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys

from . import artifact_handoff_v1 as wire
from .processes import run_process

PROFILE = "letter-pdf-v1"
PRODUCER_VERSION = "0.3.0rc1"
RENDERER = "sha256:ba2453fb42542433f68efd8888d628b95f256cefb9c545b3b35034d33296e340"
PDF_PATH = "payload/output/letter.pdf"
TEMPLATES = {
    "default-letter.latex": "59fc2e886e93c85136c03e158c2dbf88206df0f3a092a85eb9265d3619a46d39",
    "scrlttr2-letter.latex": "7191d054fdfb4031c305b257f627d59126954109552a1c545662447d67009f2c",
}
METADATA = ("metadata-0.yml", "metadata-1.yml", "metadata-paths.yml")
INPUT_ARGS = [*(f"--metadata-file=/work/{name}" for name in METADATA), "--from=markdown", "/work/letter.md"]
PDF_ARGS = ["--standalone", "--pdf-engine=pdflatex", "--output=/work/artifact.pdf", *INPUT_ARGS, "--template=/work/template.latex"]
AST_ARGS = ["--standalone", "--to=json", "--output=/work/parsed.json", *INPUT_ARGS]
MAX_PAYLOAD = 32 * 1024 * 1024
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)", re.MULTILINE | re.DOTALL)


def require(value, message):
    wire.require(value, "letter-pdf-v1", message)


def text_references(text):
    """Independently inspect retained text; a stale AST is not closure evidence."""
    from markdown_it import MarkdownIt
    for token in MarkdownIt("commonmark").parse(text):
        require(token.type not in {"html_block", "html_inline", "image"}, "Unsupported raw markup or image in retained text")
        if token.type == "inline":
            for child in token.children or []:
                require(child.type not in {"html_inline", "image"}, "Unsupported raw markup or image in retained text")
                if child.type == "link_open":
                    require(str(child.attrGet("href") or "").startswith(("http://", "https://", "mailto:", "#")), "Unretained local text reference")
                if child.type == "text":
                    require(not re.search(r"\\[A-Za-z]+|\[@|\$[^$]+\$", child.content), "Unsupported retained TeX/math/citation")


def metadata_references(value):
    """Inspect renderable metadata independently of possibly stale AST evidence."""
    if isinstance(value, str):
        text_references(value)
    elif isinstance(value, dict):
        for child in value.values():
            metadata_references(child)
    elif isinstance(value, list):
        for child in value:
            metadata_references(child)


def mapping(raw: bytes) -> dict:
    import yaml

    class UniqueLoader(yaml.SafeLoader):
        pass

    def construct(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            require(isinstance(key, str) and key not in result, "Duplicate or non-string YAML key")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct)
    require(len(raw) <= wire.MAX_MANIFEST_BYTES, "YAML exceeds profile limit")
    try:
        require(not any(isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for t in yaml.scan(raw)), "YAML aliases are unsupported")
        documents = [item for item in yaml.load_all(raw, Loader=UniqueLoader) if item is not None]
    except (yaml.YAMLError, RecursionError) as exc:
        raise wire.HandoffError("letter-pdf-v1", "Invalid bounded YAML") from exc
    require(len(documents) == 1 and isinstance(documents[0], dict), "Expected one YAML mapping")
    value = documents[0]
    # Bound the YAML tree without interpreting tags or rendering templates.
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(depth <= 32 and count <= 100000, "YAML exceeds tree limits")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return value


def letter(raw: bytes) -> dict:
    text = raw.decode("utf-8")
    front = FRONT_MATTER.match(text)
    require(front is not None, "Missing or incomplete letter front matter")
    meta = mapping(front.group(1).encode())
    text_references(text[front.end():])
    allowed = {"title", "lang", "draft", "date", "customdate", "re", "subject", "recipient", "opening", "ending", "signature", "logo", "postdata", "attachments", "cc", "keywords", "unaltracarta", "footer", "fontsize"}
    require(meta.keys() <= allowed, "Unsupported letter metadata")
    require(meta.get("draft") is False and bool(meta.get("date") or meta.get("customdate")), "Letter needs explicit final status and date")
    require(meta.get("lang") in {"english", "catalan", "spanish"}, "Unsupported letter language")
    require(isinstance(meta.get("title"), str) and bool(meta["title"]), "Letter needs a title")
    for key, value in meta.items():
        if key in {"recipient", "unaltracarta", "footer"}:
            continue
        if key in {"draft", "signature"}:
            require(type(value) is bool, f"{key} must be boolean")
        elif key in {"attachments", "cc"}:
            require(isinstance(value, list) and all(isinstance(item, str) for item in value), "Attachments/cc must be text labels")
        elif key == "date" and isinstance(value, date):
            pass
        else:
            require(isinstance(value, str), f"{key} must be text")
    require(meta.get("fontsize", "11pt") in {"10pt", "11pt", "12pt"}, "Unsupported font size")
    footer = meta.get("footer", {})
    require(isinstance(footer, dict) and footer.keys() <= {"hide_work_email", "show_personal_email"} and all(type(v) is bool for v in footer.values()), "Invalid footer options")
    stamp = meta.get("unaltracarta", {})
    require(isinstance(stamp, dict) and stamp.keys() <= {"version", "schema"}, "Invalid letter stamp")
    return meta


def verify(workspace: wire.Workspace, path: str, sha256: str) -> dict:
    require(wire.HASH_RE.fullmatch(sha256) is not None, "Sender SHA-256 is required")
    manifest, files, inventory = wire.Verifier(workspace).bundle(path, sha256)
    base = path.rpartition("/")[0]
    require(manifest["producer"]["name"] == "unaltracarta" and manifest["producer"]["version"] == PRODUCER_VERSION, "Unsupported producer/version")
    require(manifest["dependencies"] == [], "Composite profiles are not supported")
    require(sum(item["bytes"] for item in files.values()) <= 64 * 1024 * 1024, "Letter unit exceeds the 64 MiB receiving profile")
    require(all("variant_of" not in item and "from" not in item for item in files.values()), "This letter profile does not define post-edited PDFs or child inputs")

    def read(name: str, limit=wire.MAX_MANIFEST_BYTES):
        require(name in inventory, f"Incomplete letter: {name}")
        return workspace.read(wire.join(base, name), limit, collect=True)[2]

    request = wire.parse_json(read("payload/request.json"))
    wire.safe_path(request.get("source", ""))
    require(set(request) == {"arguments", "attachments", "author_origin", "container_root", "draft", "environment", "language", "profile", "recipient_key", "render_root", "source", "template", "validation_arguments"}, "Unsupported request fields")
    require(request["profile"] == PROFILE and request["arguments"] == PDF_ARGS and request["validation_arguments"] == AST_ARGS, "Unsupported retained render recipe")
    require(request["render_root"] == "payload/render" and request["container_root"] == "/work", "Invalid virtual render root")
    require(request["draft"] is False and request["attachments"] == "text-labels-only", "Unsupported draft/attachment mode")
    require(request["environment"] == {"HOME": "/tmp", "TEXMFCACHE": "/tmp/texmf-cache"}, "Unsupported render environment")
    template = request["template"]
    require(template in TEMPLATES and hashlib.sha256(read("payload/render/template.latex")).hexdigest() == TEMPLATES[template], "Unsupported or modified retained template")
    required = {"payload/request.json", "payload/source/original.letter.md", "payload/render/letter.md", "payload/render/template.latex", *(f"payload/render/{name}" for name in METADATA), "payload/evidence/producer.json", "payload/evidence/runtime.json", "payload/evidence/pandoc.json", PDF_PATH}
    require(required <= files.keys(), "Incomplete letter profile")
    original = letter(read("payload/source/original.letter.md"))
    prepared = letter(read("payload/render/letter.md"))
    require(original["lang"] == prepared["lang"] == request["language"], "Language binding mismatch")
    metadata = mapping(read("payload/render/metadata-0.yml"))
    strings = mapping(read("payload/render/metadata-1.yml"))
    path_doc = mapping(read("payload/render/metadata-paths.yml"))
    require(metadata.keys() <= {"author", "unaltracarta"}, "Unsupported effective metadata fields")
    for value in (original, prepared, metadata, strings):
        metadata_references(value)
    require(strings.keys() == {"strings"} and isinstance(strings["strings"], dict), "Invalid retained strings")
    require(path_doc.keys() == {"paths"} and isinstance(path_doc["paths"], dict), "Invalid path metadata")
    paths = path_doc["paths"]
    require(set(paths) == {"sources", "data", "templates", "logos", "signatures", "selfies"}, "Unexpected resource path category")
    require(all(paths[name] == "/work" for name in ("sources", "data", "templates")) and paths["selfies"] == "", "External or unretained render paths")
    require(isinstance(metadata.get("author"), dict), "Missing retained author")
    require(bool(metadata["author"].get("name") or metadata["author"].get("familyname")), "Missing author identity")
    require(isinstance(prepared.get("recipient"), dict) and bool(prepared["recipient"].get("name")), "Missing resolved recipient")
    images = metadata["author"].get("images", {})
    require(isinstance(images, dict) and images.keys() <= {"signature"}, "Unsupported author resource")
    for category, filename in (("logos", prepared.get("logo", "")), ("signatures", images.get("signature", ""))):
        require(isinstance(filename, str), "Invalid resource name")
        if filename:
            wire.safe_path(filename)
            require(PurePosixPath(filename).name == filename and PurePosixPath(filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf"}, "Unsupported drawable reference")
            require(paths[category] == f"/work/resources/{category}", "External drawable path")
            resource_path = f"payload/render/resources/{category}/{filename}"
            require(resource_path in files, "Missing retained drawable")
            required.add(resource_path)
        else:
            require(paths[category] == "", "Unretained resource directory")
    require(set(files) == required, "Unexpected payload outside the supported profile")
    require(files["payload/source/original.letter.md"]["ownership"] == "author", "Original must remain author-owned")
    require(files[PDF_PATH]["kind"] == "output" and files[PDF_PATH]["role"] == "letter-pdf", "Missing letter PDF output")
    require(files["payload/request.json"]["id"] == manifest["request"], "Request binding mismatch")
    for name, entry in files.items():
        expected_kind = "output" if name == PDF_PATH else "evidence" if name.startswith("payload/evidence/") else "input"
        require(entry["kind"] == expected_kind, "Unexpected file kind in letter profile")
    producer_raw = read("payload/evidence/producer.json")
    producer = wire.parse_json(producer_raw)
    require(producer.get("identity") == "unaltracarta-code-inventory-v1" and producer.get("version") == PRODUCER_VERSION and isinstance(producer.get("files"), dict), "Invalid producer inventory")
    require(producer["files"].get(f"assets/templates/{template}") == TEMPLATES[template], "Template is not bound to the producer inventory")
    require(manifest["producer"]["revision"] == "sha256:" + hashlib.sha256(producer_raw).hexdigest(), "Producer code identity mismatch")
    runtime = wire.parse_json(read("payload/evidence/runtime.json"))
    require(runtime.get("revision") == RENDERER and runtime.get("os") == "linux" and runtime.get("architecture") == "amd64", "Unsupported published renderer point")
    require(manifest["producer"]["runtimes"] == [{"name": "pandoc-latex", "revision": RENDERER}], "Runtime binding mismatch")
    ast = wire.parse_json(read("payload/evidence/pandoc.json"))
    require({"pandoc-api-version", "meta", "blocks"} <= ast.keys(), "Missing Pandoc evidence")
    require(isinstance(ast["meta"], dict) and isinstance(ast["blocks"], list)
            and isinstance(ast["pandoc-api-version"], list)
            and all(type(version) is int for version in ast["pandoc-api-version"]), "Invalid Pandoc evidence shape")
    pending = [ast]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            require(item.get("t") not in {"RawInline", "RawBlock", "Image", "Math", "Cite"}, "Unsupported body dependency or raw markup")
            if item.get("t") == "Link":
                content = item.get("c")
                require(isinstance(content, list) and len(content) == 3
                        and isinstance(content[-1], list) and len(content[-1]) == 2
                        and all(isinstance(value, str) for value in content[-1]), "Invalid Pandoc link evidence")
                require(content[-1][0].startswith(("https://", "http://", "mailto:", "#")), "Unretained body link")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    pdf = read(PDF_PATH, MAX_PAYLOAD)
    probe = run_process([sys.executable, str(Path(__file__).with_name("pdf_probe.py"))], input_data=pdf, timeout_seconds=15)
    require(probe.returncode == 0 and not probe.stdout_truncated, f"PDF domain check failed: {probe.stdout or probe.stderr}")
    pdf_info = wire.parse_json(probe.stdout.encode())
    require(pdf_info.get("ok") is True, "Invalid PDF structure")
    workspace.recheck()
    return {"profile": PROFILE, "manifest": manifest, "files": files, "inventory": sorted(inventory), "pdf": PDF_PATH, "pages": pdf_info["pages"], "title": prepared["title"]}
