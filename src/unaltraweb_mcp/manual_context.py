"""Create-only, producer-resolved manual context v1. No renderer or receiver runs.

Sources are snapshotted with the existing descriptor-relative reader; the native
manual resolvers see that bounded snapshot, never an arbitrary consumer root.
The retained job uses the same no-follow/create-only primitives as private PDFs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import unicodedata
import html
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
import yaml

from . import __version__
from . import manual_pdf_preview as fs
from .editorial_sources import Reader, default_language, digest, relative_path, yaml_mapping
from .practice_pdf import _manual_builder, _write
from .manual_context_media import image_references, validate_image
from .runtime_identity import active_runtime, fingerprint

MAX_FILE = 10 * 1024**2
MAX_TOTAL = 256 * 1024**2
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
LANGUAGE = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8}){0,2}\Z")


def canonical(value):
    # The integration fingerprint is canonical JSON WITHOUT a trailing newline.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def label(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 300 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} requires a non-empty bounded text value")
    return value


def local_path(raw):
    url = urlsplit(raw)
    if url.scheme or url.netloc or url.query or url.fragment or raw.startswith("//"):
        raise ValueError(f"External/decorated visual reference {raw!r}; prepare a local effective figure first")
    value = relative_path(unquote(url.path.lstrip("/"), errors="strict"))
    if len(value) > 240 or ":" in value or any(part.startswith(".") for part in Path(value).parts):
        raise ValueError(f"Unsafe public resource path: {raw}")
    return value


class Snapshot:
    def __init__(self, reader, root):
        self.reader, self.root = reader, root
        self.mtimes = {}
        self.public_roots = {"assets", "_data", "_includes", "_bibliography", "_chapters", "_documentation", "_pages", "_layouts", "_plugins", "_sass"}

    def public(self, name):
        relative_path(name)
        if name.split("/")[0] not in self.public_roots or any(part.startswith(".") for part in name.split("/")):
            raise ValueError(f"Resource is outside the public manual source roots: {name}")
        return name

    def copy(self, name, *, optional=False):
        data = self.reader.read(name, optional=optional)
        if data is not None and not (self.root / name).exists():
            if name.endswith((".yml", ".yaml")):
                try:
                    if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for token in yaml.scan(data)):
                        raise ValueError(f"{name}: aliases/anchors are not supported in export source configuration")
                except yaml.YAMLError as exc:
                    raise ValueError(f"{name}: invalid YAML: {exc}") from exc
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            with self.reader.parent(name) as (parent, base):
                info = os.stat(base, dir_fd=parent, follow_symlinks=False)
            self.mtimes[name] = info.st_mtime_ns
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        return data

    def tree(self, name, suffixes=None):
        names = self.reader.walk(name)
        for path in names:
            if suffixes is None or Path(path).suffix.lower() in suffixes:
                self.copy(path)
        return names


def split_sections(text, ref, title):
    """Heading line maps give exact non-overlapping blocks, not subtree copies."""
    lines = text.splitlines(keepends=True)
    headings = []
    tokens = MarkdownIt("commonmark").parse(text)
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.level == 0:
            content = tokens[index + 1].content
            explicit = re.search(r"\s*\{#([\w.-]+)\}\s*$", content)
            title_text = content[:explicit.start()].strip() if explicit else content
            anchor = explicit[1] if explicit else re.sub(r"[^\w.-]+", "-", unicodedata.normalize("NFC", title_text).casefold()).strip("-")
            if not anchor:
                raise ValueError(f"{ref}: heading needs an explicit stable {{#anchor}}")
            headings.append((token.map[0], int(token.tag[1:]), anchor, label(title_text, "heading title")))
    if not headings or headings[0][0] > 0:
        headings.insert(0, (0, 0, "intro", title))
    result, seen = [], set()
    for index, (start, level, anchor, heading_title) in enumerate(headings):
        stop = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        block = "".join(lines[start:stop])
        if not block.strip():
            continue
        identifier = label(ref + "#" + anchor, "section ID")
        if identifier in seen:
            raise ValueError(f"Duplicate section {identifier}; give headings distinct explicit anchors")
        seen.add(identifier)
        path = f"sections/{ref}/{digest(identifier.encode())[:24]}.md"
        result.append(({"id": identifier, "title": heading_title, "level": level, "path": path}, block))
    if not result or len(result) > 2000:
        raise ValueError(f"{ref}: requires 1–2000 readable sections")
    return result


def protect_code_blocks(text, protect):
    """Preserve fenced (including unclosed) and indented literal code exactly."""
    lines = text.splitlines(keepends=True)
    spans = sorted({tuple(token.map) for token in MarkdownIt("commonmark").parse(text)
                    if token.type in {"fence", "code_block"} and token.map}, reverse=True)
    for start, end in spans:
        value = "".join(lines[start:end])
        ending = "\n" if value.endswith("\n") else ""
        lines[start:end] = [protect((value[:-1] if ending else value,)) + ending]
    return "".join(lines)


class Projection:
    def __init__(self, snapshot, manual, config, language, factory):
        self.snapshot, self.manual, self.config, self.language = snapshot, manual, config, language
        self.default = default_language(config)
        self.languages = config.get("languages") or [self.default]
        self.figures, self.files = {}, {}
        from .manual_context_sources import Sources
        self.sources = Sources(snapshot, factory, manual)
        self.bibliography = None
        self.expanded_bytes = 0

    def figure(self, raw, alt, caption, credits):
        source = self.snapshot.public(local_path(raw))
        self.snapshot.copy(source)
        suffix = next((s for s in self.manual.VISUAL_LOCALIZATION_SUFFIXES if source.lower().endswith(s)), "")
        if suffix and self.language != self.default:
            stem = source[:-len(suffix)]
            if not any(stem.lower().endswith("." + code.lower()) for code in self.languages):
                self.snapshot.copy(f"{stem}.{self.language}{suffix}", optional=True)
        selected = self.manual.localized_visual_source(self.snapshot.root, source, language=self.language,
                        default_language=self.default, languages=self.languages)
        language = self.default
        selected_suffix = next((s for s in self.manual.VISUAL_LOCALIZATION_SUFFIXES if selected.lower().endswith(s)), "")
        stem = selected[:-len(selected_suffix)] if selected_suffix else selected
        for code in self.languages:
            if stem.lower().endswith("." + code.lower()):
                language = code
        original, effective, resolution = self.sources.resolve(selected)
        language = self.sources.records.get(original, {}).get("language", language)
        data = self.snapshot.copy(effective)
        validate_image(data, effective)
        for value in (alt, caption, credits):
            if len(value) > 4000:
                raise ValueError("Figure alt/caption/credits exceed the v1 4000-character limit")
        key = digest(canonical([selected, alt, caption, credits]))
        destination = f"figures/{key}{Path(effective).suffix.lower()}"
        self.files[destination] = data
        self.figures[destination] = {"id": "figure-" + key, "path": destination, "alt": alt, "caption": caption,
            "credits": credits, "language": language, "source": {"path": original, "sha256": digest(self.snapshot.copy(original))},
            "resolution": resolution}
        return "/" + destination

    def bibliography_entries(self):
        if self.bibliography is None:
            settings = self.config.get("unaltraweb", {}).get("manual", {})
            filename = settings.get("bibliography_file") or "manual.bib"
            self.snapshot.copy(self.snapshot.public("_bibliography/" + filename))
            path = self.manual.bibliography_source(self.snapshot.root, self.config)
            if path is None:
                raise ValueError("Citations require the manual bibliography to be enabled")
            import bibtexparser
            from bibtexparser.customization import convert_to_unicode
            entries = bibtexparser.loads(path.read_text()).entries
            if len(entries) > 5000 or len({row["ID"] for row in entries}) != len(entries):
                raise ValueError("Bibliography has duplicate keys or exceeds its bound")
            self.bibliography = {row["ID"]: convert_to_unicode(row) for row in entries}
        return self.bibliography

    def references(self, keys):
        entries = self.bibliography_entries()
        lines = []
        for key in sorted(set(keys)):
            if key not in entries:
                raise ValueError(f"Unknown citation key {key}; add a verified manual bibliography entry")
            entry = entries[key]
            if not entry.get("title"):
                raise ValueError(f"Bibliography entry {key} has no title")
            fields = [entry.get(field, "") for field in ("author", "editor", "year", "title", "journal", "booktitle", "publisher")]
            line = f"- **{key}**: " + ". ".join(value for value in fields if value)
            for field in ("doi", "url", "manual_url", "website"):
                value = entry.get(field)
                if value:
                    url = "https://doi.org/" + value.removeprefix("https://doi.org/") if field == "doi" else value
                    parsed = urlsplit(url)
                    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                        raise ValueError(f"Bibliography {key}: unsupported {field} URL")
                    line += " " + f"[{field}](<{url}>)"
            lines.append(line)
        return "\n".join(lines) + "\n"

    def includes(self, text, source, chain=()):
        if len(chain) >= 16:
            raise ValueError("Manual include depth exceeds 16")
        def include(match):
            filename = match[2].strip().strip("\"'")
            if filename == "manual-bibliography.liquid" and match[1] == "include":
                body = self.references(self.bibliography_entries())
                self.expanded_bytes += len(body.encode())
                if self.expanded_bytes > 16 * 1024**2:
                    raise ValueError("Manual includes exceed the 16 MiB expansion budget")
                return body
            if not re.fullmatch(r"[A-Za-z0-9_./-]+\.(?:md|markdown|liquid|html)", filename):
                raise ValueError(f"{source}: portable includes require a literal filename without parameters")
            name = ("_includes/" if match[1] == "include" else str(Path(source).parent) + "/") + filename
            self.snapshot.public(name)
            if name in chain:
                raise ValueError(f"Recursive manual include: {name}")
            body = self.snapshot.copy(name).decode("utf-8")
            self.expanded_bytes += len(body.encode())
            if self.expanded_bytes > 16 * 1024**2:
                raise ValueError("Manual includes exceed the 16 MiB expansion budget")
            return self.includes(body, name, (*chain, name))
        protected = []
        prefix = "UWCONTEXTINCLUDE"
        while prefix in text:
            prefix += "X"
        def protect(match):
            protected.append(match[0])
            return f"{prefix}{len(protected)-1}TOKEN"
        text = protect_code_blocks(text, protect)
        text = self.manual.MARKDOWN_INLINE_CODE_RE.sub(protect, text)
        text = re.sub(r"{%\s*(include|include_relative)\s+([^%]+?)\s*%}", include, text)
        for index in reversed(range(len(protected))):
            text = text.replace(f"{prefix}{index}TOKEN", protected[index])
        return text

    def text(self, text, source):
        protected = []
        prefix = "UNALTRAWEBEXPORTPROTECTED"
        while prefix in text:
            prefix += "X"
        def protect(match):
            protected.append(match[0])
            return f"{prefix}{len(protected)-1}TOKEN"
        def restore(value):
            for index in reversed(range(len(protected))):
                value = value.replace(f"{prefix}{index}TOKEN", protected[index])
            return value
        text = protect_code_blocks(text, protect)
        text = self.manual.MARKDOWN_INLINE_CODE_RE.sub(protect, text)
        text = self.includes(text, source)
        # Protect literal examples introduced by an include too.
        text = protect_code_blocks(text, protect)
        text = self.manual.MARKDOWN_INLINE_CODE_RE.sub(protect, text)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        text = self.manual.BASEURL_RE.sub("", text)
        cited = []
        def cite(match):
            keys = [key.lstrip("@") for key in match[1].split()]
            entries = self.bibliography_entries()
            if any(key not in entries for key in keys):
                raise ValueError(f"{source}: unknown manual citation key")
            cited.extend(keys)
            return "[" + "; ".join(keys) + "]"
        text = self.manual.CITE_RE.sub(cite, text)
        if "{%" in text or "{{" in text:
            raise ValueError(f"{source}: unresolved Liquid/include; use a supported portable component")
        def component(match):
            caption = match.groupdict().get("caption") or ""
            credit, _ = self.manual.caption_source_attribute(match.groupdict().get("attrs") or "")
            return "\n\n" + "\n\n".join(value for value in (caption, match.group("body"), credit) if value) + "\n\n"
        text = self.manual.TABLE_DIV_RE.sub(component, text)
        text = self.manual.SUBFIGURES_DIV_RE.sub(component, text)
        text = self.manual.LISTING_DIV_RE.sub(component, text)
        if re.search(r"^:::", text, re.M):
            raise ValueError(f"{source}: unsupported/malformed manual component")
        if self.manual.CALLOUT_BLOCK_RE.search(text):
            for code in {self.manual.normalize_callout_language(self.language), self.manual.normalize_callout_language(self.default)}:
                for suffix in (".yml", ".yaml"):
                    langfile = str(self.config.get("data_dir") or "_data") + "/i18n/" + code + suffix
                    self.snapshot.copy(self.snapshot.public(langfile), optional=True)
            labels, _ = self.manual.resolve_callout_labels(self.snapshot.root, self.config, self.language)
            def callout(match):
                marks = match.group("marks")
                kind = self.manual.CALLOUT_STYLES[min(len(marks), 6)][1]
                body = "\n".join("> " + line[len(marks):].lstrip(" \t") for line in match.group("block").splitlines())
                return "> **" + labels[kind] + "**\n>\n" + body
            text = self.manual.CALLOUT_BLOCK_RE.sub(callout, text)
        def image(match):
            credit, _ = self.manual.caption_source_attribute(match.group("attrs") or "")
            alt = restore(match.group("alt"))
            caption = restore(match.group("double_title") or match.group("single_title") or alt)
            credit = restore(credit)
            path = self.figure(match.group("path"), alt, caption, credit)
            title = caption.replace('"', '&quot;')
            result = f'![{alt}]({path} "{title}")'
            return result + (f"\n\n{credit}\n" if credit else "")
        text = self.manual.IMAGE_RE.sub(image, text)
        text = self.html_images(text)
        if cited:
            text += "\n\n## References {#manual-context-references}\n\n" + self.references(cited)
        return restore(text)

    def html_images(self, text):
        owner = self
        class Images(HTMLParser):
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if (tag in {"script", "iframe", "object", "embed", "svg", "source", "video", "audio", "link", "style"}
                        or any(name.startswith("on") or name in {"srcset", "poster"} for name in values)
                        or "url(" in values.get("style", "").lower()):
                    raise ValueError(f"Unsupported active/external HTML component <{tag}>; prepare portable text/figures")
                if tag == "img":
                    original = self.get_starttag_text()
                    if sum(name == "src" for name, _ in attrs) != 1:
                        raise ValueError("HTML image requires exactly one literal src")
                    alt, caption, credits = (values.get(key) or "" for key in ("alt", "title", "data-caption-source"))
                    target = owner.figure(values["src"], alt, caption or alt, credits)
                    rendered = '<img src="' + target + '" alt="' + html.escape(alt, quote=True) + '" title="' + html.escape(caption, quote=True) + '">'
                    replacements.append((original, rendered))
            handle_startendtag = handle_starttag
        replacements = []
        parser = Images()
        parser.feed(text)
        for old, new in replacements:
            text = text.replace(old, new)
        return text


def git_identity(project):
    fs._require_git_root(project)
    revision = fs._run_git(project, ["rev-parse", "HEAD"]).stdout.decode().strip()
    date = fs._run_git(project, ["show", "-s", "--format=%cI", "HEAD"]).stdout.decode().strip()
    dirty = bool(fs._run_git(project, ["status", "--porcelain", "--untracked-files=normal"]).stdout)
    return revision, date, dirty


def producer_identity(factory):
    observed = fingerprint(Path(__file__).parent)
    if not observed["available"]:
        raise ValueError("Cannot fingerprint the producer package")
    active = active_runtime()
    if active and active.startup_package["sha256"] != observed["sha256"]:
        raise ValueError("Loaded MCP code differs from disk; reconnect normally before exporting")
    helpers = {}
    with Reader(factory, max_bytes=MAX_FILE, max_total_bytes=MAX_TOTAL) as reader:
        for path in ("scripts/manual/build_pdf.py", "scripts/computations/render.py", "scripts/web_captures/render.py"):
            helpers[path] = digest(reader.read(path))
    return {"name": "unaltraweb", "version": __version__, "revision": "sha256:" + digest(canonical({"package": observed["sha256"], "helpers": helpers}))}


def unchanged(project, cache, walks):
    with Reader(project, max_bytes=MAX_FILE, max_total_bytes=MAX_TOTAL) as reader:
        for name, data in cache.items():
            if reader.read(name, optional=data is None) != data:
                raise ValueError(f"Source changed during export: {name}; retry with a new export name")
        for (root, hidden), expected in walks.items():
            if reader.walk(root, include_hidden=hidden) != expected:
                raise ValueError(f"Source inventory changed during export: {root}")


def prepare(project, factory, language="", chapters=None, sections=None):
    identity = git_identity(project)
    producer = producer_identity(factory)
    manual = _manual_builder(factory)
    with Reader(project, max_bytes=MAX_FILE, max_total_bytes=MAX_TOTAL) as reader, tempfile.TemporaryDirectory(prefix="unaltraweb-manual-context-") as temporary:
        snapshot = Snapshot(reader, Path(temporary))
        config = yaml_mapping(snapshot.copy("_config.yml").decode("utf-8"))
        uw = config.get("unaltraweb") or {}
        if not isinstance(uw, dict):
            raise ValueError("unaltraweb must be a mapping")
        if uw.get("site_profile") != "unaltremanual":
            raise ValueError("manual_context_export requires the bound unaltremanual workspace")
        settings = uw.get("manual") or {}
        if not isinstance(settings, dict):
            raise ValueError("unaltraweb.manual must be a mapping")
        if not isinstance(config.get("exclude"), list) or "tmp" not in {str(value).rstrip("/") for value in config["exclude"]}:
            raise ValueError("Add tmp/ to _config.yml exclude before retaining manual exports")
        if any(str(value).strip("/").split("/")[0] in {"tmp", "."} for value in config.get("include", [])):
            raise ValueError("Jekyll include must not expose tmp/manual-context")
        manual_id = label(settings.get("id"), "unaltraweb.manual.id (stable logical manual identity)")
        selected_language = language or default_language(config)
        languages = config.get("languages") or [default_language(config)]
        if (not isinstance(languages, list) or any(not isinstance(code, str) or not LANGUAGE.fullmatch(code) for code in languages)
                or not isinstance(selected_language, str) or not LANGUAGE.fullmatch(selected_language) or selected_language not in languages):
            raise ValueError("Select a configured manual language")
        collection = settings.get("collection") or "chapters"
        if not isinstance(collection, str) or not REF.fullmatch(collection):
            raise ValueError("Invalid manual collection")
        snapshot.public_roots.add("_" + collection)
        snapshot.tree("_" + collection, {".md", ".markdown"})
        config["default_lang"] = default_language(config)
        projection = Projection(snapshot, manual, config, selected_language, factory)
        _, candidates, _ = manual.manual_sources(snapshot.root, config, selected_language, for_pdf=False)
        if not 1 <= len(candidates) <= 500:
            raise ValueError("Manual context v1 supports 1–500 chapters")
        known = [front.get("ref") for _, front, _ in candidates]
        if any(not isinstance(ref, str) or not REF.fullmatch(ref) for ref in known) or len({ref.casefold() for ref in known}) != len(known):
            raise ValueError("Selected-language chapters require unique stable ref values")
        if chapters is not None and (not chapters or len(set(chapters)) != len(chapters) or set(chapters) - set(known)):
            raise ValueError("Chapter selection must contain distinct existing refs in the selected language")
        chapter_rows, section_ids = [], set()
        files = {}
        for order, (path, front, body) in enumerate(candidates):
            ref = front["ref"]
            if chapters is not None and ref not in chapters:
                continue
            source = path.relative_to(snapshot.root).as_posix()
            title = label(front.get("title"), "chapter title")
            if "\x00" in body:
                raise ValueError(f"{source}: manual text contains NUL bytes")
            parts = split_sections(projection.text(body, source), ref, title)
            section_ids.update(part["id"] for part, _ in parts)
            if sections is not None:
                parts = [(part, block) for part, block in parts if part["id"] in sections]
            if not parts:
                continue
            for part, block in parts:
                data = block.encode("utf-8")
                if len(data) > 4 * 1024**2:
                    raise ValueError("Section exceeds 4 MiB; select smaller authored sections")
                files[part["path"]] = data
            if sum(len(data) for data in files.values()) > MAX_TOTAL:
                raise ValueError("Manual text exceeds the export budget; select fewer chapters")
            chapter_rows.append({"ref": ref, "title": title, "order": order, "source_sha256": digest(snapshot.copy(source)), "sections": [part for part, _ in parts]})
        if sections is not None and (not sections or len(set(sections)) != len(sections) or set(sections) - section_ids):
            raise ValueError("Section selection must contain distinct exact section IDs in the selected chapters")
        if not chapter_rows:
            raise ValueError("Selection has no readable sections")
        used = set()
        for chapter in chapter_rows:
            chapter_images = []
            for section in chapter["sections"]:
                chapter_images.extend(image_references(files[section["path"]].decode("utf-8")))
            if len(chapter_images) > 256:
                raise ValueError(f"{chapter['ref']}: exceeds Itemarium's 256 figure references per bank")
            for reference in chapter_images:
                if reference not in {"/" + path for path in projection.figures}:
                    raise ValueError(f"Unresolved figure {reference!r}; use a supported literal image/component")
                used.add(reference[1:])
        files.update({path: projection.files[path] for path in used})
        inputs = {name: digest(data) for name, data in reader.cache.items() if data is not None}
        source_date = identity[1] if not identity[2] else datetime.fromtimestamp(max(snapshot.mtimes.values()) / 1e9, timezone.utc).isoformat()
        manifest = {"format": "unaltraweb-manual-context", "format_version": 1, "producer": producer,
            "manual": {"id": manual_id, "title": label(manual.localized(settings.get("title") or config.get("title"), selected_language), "manual title"),
                       "language": selected_language, "revision": identity[0], "source_sha256": digest(canonical(inputs)), "source_date": source_date, "dirty": identity[2]},
            "exported_at": datetime.now(timezone.utc).isoformat(), "chapters": chapter_rows,
            "figures": [projection.figures[path] for path in sorted(used)],
            "files": {name: {"sha256": digest(data), "size_bytes": len(data)} for name, data in sorted(files.items())}}
        if len(files) > 10000 or len(used) > 4096 or sum(len(data) for data in files.values()) > MAX_TOTAL:
            raise ValueError("Selection exceeds the portable package budget; export fewer chapters")
        unchanged(project, reader.cache, reader.walk_cache)
        if git_identity(project) != identity or producer_identity(factory) != producer:
            raise ValueError("Manual or producer identity changed during export; retry")
        evidence = {key: value for key, value in projection.sources.evidence.items()
                    if key in {row["resolution"].get("receipt_sha256") for row in manifest["figures"]}}
        return manifest, files, dict(reader.cache), dict(reader.walk_cache), identity, evidence


def export(project, factory, name, *, language="", chapters=None, sections=None):
    project, factory = Path(project).resolve(strict=True), Path(factory).resolve(strict=True)
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("Export name must be a safe name of at most 64 characters")
    for values in (chapters, sections):
        if values is not None and (not isinstance(values, list) or len(values) > 2000 or any(not isinstance(value, str) for value in values)):
            raise ValueError("Chapter/section selection must be a bounded list of strings")
    active = active_runtime()
    if active and active.project != project:
        raise ValueError("Export must use the connection's bound manual workspace")
    job = Path("tmp/manual-context") / name
    fs._require_generated_path(project, job, label="Retained manual context export")
    manifest, files, inputs, walks, identity, evidence = prepare(project, factory, language, chapters, sections)
    files = {"manual-context.json": canonical(manifest), **files}
    if len(files["manual-context.json"]) > 8 * 1024**2:
        raise ValueError("Manifest exceeds 8 MiB")
    root_fd = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    job_fd = None
    try:
        parent = fs._open_directory(root_fd, job.parent, create=True)
        try:
            os.mkdir(job.name, 0o700, dir_fd=parent)
            job_fd = os.open(job.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileExistsError as exc:
            raise ValueError(f"Export {job} already exists; retain it and choose a new name") from exc
        finally:
            os.close(parent)
        for path, data in files.items():
            _write(job_fd, "content/" + path, data)
        archive_fd = os.open("manual-context.tar.gz", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=job_fd)
        with os.fdopen(archive_fd, "wb") as output:
            with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                    for path, data in sorted(files.items()):
                        info = tarfile.TarInfo(path)
                        info.size, info.mode = len(data), 0o644
                        archive.addfile(info, io.BytesIO(data))
            output.flush()
            os.fsync(output.fileno())
        with Reader(project, max_bytes=128 * 1024**2, max_total_bytes=512 * 1024**2) as retained:
            archive_bytes = retained.read(f"{job}/manual-context.tar.gz")
            expected_tree = {f"{job}/manual-context.tar.gz", *[f"{job}/content/{path}" for path in files]}
            if set(retained.walk(job.as_posix(), include_hidden=True)) != expected_tree:
                raise ValueError("Retained export contains unexpected files; unsealed job preserved")
            for path, data in files.items():
                if retained.read(f"{job}/content/{path}") != data:
                    raise ValueError("Retained content changed before sealing")
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            seen = set()
            for member in archive:
                if (member.name not in files or member.name in seen or not member.isfile()
                        or member.size != len(files[member.name]) or archive.extractfile(member).read() != files[member.name]):
                    raise ValueError("Retained archive differs from its exact content closure")
                seen.add(member.name)
            if seen != files.keys():
                raise ValueError("Retained archive is incomplete")
        unchanged(project, inputs, walks)
        if git_identity(project) != identity or producer_identity(factory) != manifest["producer"]:
            raise ValueError("Source/producer changed before sealing; unsealed export retained")
        fs._require_generated_path(project, job, label="Retained manual context export")
        receipt = {"schema_version": 1, "kind": "unaltraweb-manual-context-export", "producer": manifest["producer"],
                   "manual": manifest["manual"], "package": f"{job}/manual-context.tar.gz", "sha256": digest(archive_bytes),
                   "manifest_sha256": digest(files["manual-context.json"]), "inputs": {key: digest(data) if data is not None else None for key, data in inputs.items()},
                   "files": manifest["files"], "resolution_evidence": evidence, "publishes": False}
        raw_receipt = canonical(receipt)
        observed = os.stat(job, dir_fd=root_fd, follow_symlinks=False)
        opened = os.fstat(job_fd)
        if (observed.st_dev, observed.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("Retained export directory changed before sealing")
        _write(job_fd, "receipt.json", raw_receipt)
        return {"ok": True, "state": "sealed", "publishes": False, "path": receipt["package"], "sha256": receipt["sha256"],
                "receipt": f"{job}/receipt.json", "receipt_sha256": digest(raw_receipt), "producer": manifest["producer"], "manual": manifest["manual"],
                "chapters": len(manifest["chapters"]), "sections": sum(len(row["sections"]) for row in manifest["chapters"]), "figures": len(manifest["figures"])}
    finally:
        if job_fd is not None:
            os.close(job_fd)
        os.close(root_fd)
