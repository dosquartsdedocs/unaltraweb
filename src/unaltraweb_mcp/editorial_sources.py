"""Bounded, read-only projection of reader-facing site sources (not an interpreter)."""
from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
import re
import stat
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator


MAX_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 16 * MAX_BYTES
MAX_PATHS = 5000
MAX_FRAGMENTS = 10000
CONTENT_ROOTS = ("_pages", "_posts", "_news", "_projects", "_outputs", "_chapters", "_documentation", "_books", "_theses")
TEXT_SUFFIXES = {".md", ".markdown", ".html", ".qmd", ".rmd"}
PUBLIC_FIELDS = {"title", "short_title", "description", "excerpt", "summary", "bio", "caption", "alt"}
GENRES = {"prose", "bio", "news", "chapter", "procedure", "reference", "preface", "quote", "example", "cv"}


def default_language(config: dict[str, Any]) -> str:
    uw = config.get("unaltraweb") or {}
    languages = config.get("languages") or []
    return str(uw.get("default_lang") or uw.get("lang") or config.get("default_lang") or config.get("lang")
               or (languages[0] if isinstance(languages, list) and languages else "en"))


class EditorialError(ValueError):
    pass


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def strict_json(text: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EditorialError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=lambda value: (_ for _ in ()).throw(EditorialError(f"Non-finite JSON: {value}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EditorialError(f"Invalid editorial JSON: {exc}") from exc


def yaml_value(text: str) -> Any:
    try:
        import yaml
    except ImportError:
        # The modular wheel has a restricted YAML fallback. Native gem checks
        # install PyYAML explicitly and need no MCP orchestration modules.
        from .site_tools import load_yaml_text
        stripped = re.sub(r"\A\s*---\s*\n", "", text).strip()
        if stripped in {"[]", "{}"}:
            return strict_json(stripped)
        if stripped.startswith("- "):
            return load_yaml_text("items:\n" + "\n".join("  " + line for line in stripped.splitlines())).get("items", [])
        value = load_yaml_text(text)
    else:
        class UniqueLoader(yaml.SafeLoader):
            pass

        def mapping(loader, node):
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=True)
                if not isinstance(key, (str, int, float, bool)) or key in result:
                    raise EditorialError("Editorial YAML requires unique scalar mapping keys.")
                result[key] = loader.construct_object(value_node, deep=True)
            return result

        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        try:
            value = yaml.load(text, Loader=UniqueLoader)
        except yaml.YAMLError as exc:
            raise EditorialError(f"Invalid editorial YAML: {exc}") from exc
    return value


def yaml_mapping(text: str) -> dict[str, Any]:
    value = yaml_value(text)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise EditorialError("Expected a YAML mapping.")
    return value


def relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or raw.startswith("/") or "\\" in raw or any(ord(c) < 32 for c in raw):
        raise EditorialError("Use a literal project-relative editorial path.")
    if any(part in {"", ".", "..", ".git"} for part in raw.split("/")) or any(c in raw for c in "*?[]"):
        raise EditorialError(f"Unsafe editorial path: {raw}")
    return raw


class Reader:
    """Descriptor-relative reads; never follows an input symlink or creates files."""
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve(strict=True)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.cache: dict[str, bytes | None] = {}
        self.walk_cache: dict[tuple[str, bool], list[str]] = {}
        self.total = 0
        self.visited = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    @contextlib.contextmanager
    def parent(self, relative: str) -> Iterator[tuple[int, str]]:
        parts = relative_path(relative).split("/")
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def read(self, relative: str, *, optional: bool = False) -> bytes | None:
        relative_path(relative)
        if relative in self.cache:
            value = self.cache[relative]
            if value is None and not optional:
                raise EditorialError(f"Missing editorial input: {relative}")
            return value
        try:
            with self.parent(relative) as (parent, name):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
                        raise EditorialError(f"Editorial input must be a bounded regular file: {relative}")
                    data = bytearray()
                    while len(data) <= MAX_BYTES:
                        chunk = os.read(fd, min(65536, MAX_BYTES + 1 - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)
                    after = os.fstat(fd)
                    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                    if len(data) > MAX_BYTES or identity(before) != identity(after) or identity(after) != identity(current):
                        raise EditorialError(f"Editorial input changed while being read: {relative}")
                    value = bytes(data)
                finally:
                    os.close(fd)
        except FileNotFoundError as exc:
            if not optional:
                raise EditorialError(f"Missing editorial input: {relative}") from exc
            value = None
        except OSError as exc:
            raise EditorialError(f"Unsafe or unreadable editorial input {relative}: {exc}") from exc
        self.total += len(value or b"")
        if self.total > MAX_TOTAL_BYTES:
            raise EditorialError("Editorial input budget exceeded; select a smaller target.")
        self.cache[relative] = value
        return value

    def text(self, relative: str, *, optional: bool = False) -> str:
        data = self.read(relative, optional=optional)
        try:
            text = (data or b"").decode("utf-8")
        except UnicodeError as exc:
            raise EditorialError(f"Editorial input is not UTF-8: {relative}") from exc
        if "\x00" in text:
            raise EditorialError(f"NUL in editorial input: {relative}")
        return text

    def walk(self, relative: str, *, include_hidden: bool = False) -> list[str]:
        relative_path(relative)
        cache_key = (relative, include_hidden)
        if cache_key in self.walk_cache:
            return self.walk_cache[cache_key]
        result: list[str] = []

        def visit(fd: int, prefix: str, depth: int):
            if depth > 24:
                raise EditorialError("Editorial directory depth exceeded.")
            for name in sorted(os.listdir(fd)):
                self.visited += 1
                if self.visited > MAX_PATHS:
                    raise EditorialError("Editorial path budget exceeded.")
                path = f"{prefix}/{name}"
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    raise EditorialError(f"Symlink is not an editorial input: {path}")
                if name.startswith(".") and not include_hidden:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, path, depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    result.append(path)
                else:
                    raise EditorialError(f"Special file is not an editorial input: {path}")
        try:
            with self.parent(relative) as (parent, name):
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    result.append(relative)
                else:
                    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    try:
                        visit(fd, relative, 0)
                    finally:
                        os.close(fd)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise EditorialError(f"Unsafe editorial source tree {relative}: {exc}") from exc
        self.walk_cache[cache_key] = result
        return result

    def root_pages(self) -> list[str]:
        """Only root-level Jekyll page candidates, not repository prose."""
        names = os.listdir(self.fd)
        if len(names) > MAX_PATHS:
            raise EditorialError("Editorial root path budget exceeded.")
        return sorted(name for name in names if not name.startswith((".", "_"))
                      and name not in {"README.md", "AGENTS.md", "CONTRIBUTING.md", "CHANGELOG.md", "TODO.md"}
                      and Path(name).suffix.lower() in TEXT_SUFFIXES)


def blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def prose_projection(text: str, *, mask_quotes: bool = True) -> str:
    for pattern in (r"<!--.*?(?:-->|\Z)", r"{%\s*comment\s*%}.*?(?:{%\s*endcomment\s*%}|\Z)",
                    r"<(pre|code|script|style|blockquote|q)\b[^>]*>.*?</\1\s*>",
                    r"(?<!`)(`+)(?!`)[^`\n]*?\1(?!`)", r"\$\$.*?\$\$|\$[^$\n]+\$", r"{%.*?%}|{{.*?}}",
                    r"\{:[^\n}]*\}", r"(?<!!)\[([^]\n]+)\]\(([^)\n]+)\)"):
        if pattern.startswith(r"(?<!!)"):
            text = re.sub(pattern, lambda m: " " + m[1] + blank(m[0][len(m[1]) + 1:]), text)
        else:
            text = re.sub(pattern, lambda m: blank(m[0]), text, flags=re.S | re.I)
    if mask_quotes:
        text = re.sub(r'"[^"\n]+"|“[^”\n]+”|«[^»\n]+»', lambda m: blank(m[0]), text)
    return text


def fragment(path: str, text: str, *, line: int, field: str = "", kind: str = "prose", genre: str = "prose", language: str = "en", ordinal: int = 0) -> dict[str, Any]:
    return {"id": digest(canonical([path, line, field, kind, ordinal]))[:24], "path": path,
            "line": line, "field": field, "kind": kind, "genre": genre, "language": language,
            "text": text, "prose": prose_projection(text)}


class HTMLFragments(HTMLParser):
    def __init__(self, path: str, language: str, genre: str, *, line_offset: int = 0):
        super().__init__(convert_charrefs=True)
        self.path, self.language, self.genre = path, language, genre
        self.line_offset = line_offset
        self.stack: list[str] = []
        self.fragments: list[dict[str, Any]] = []

    def add(self, text: str, kind="prose", field=""):
        if text.strip():
            if len(self.fragments) >= MAX_FRAGMENTS:
                raise EditorialError("HTML fragment budget exceeded.")
            self.fragments.append(fragment(self.path, text, line=self.getpos()[0] + self.line_offset,
                                           field=field, kind=kind, genre=self.genre, language=self.language,
                                           ordinal=len(self.fragments)))

    def handle_starttag(self, tag, attrs):
        if tag in {"pre", "code", "script", "style", "blockquote", "q"}:
            self.stack.append(tag)
        if tag == "html":
            self.language = dict(attrs).get("lang") or self.language
        if not self.stack:
            for key, value in attrs:
                if key in {"alt", "title"} and value:
                    self.add(value, "metadata", f"{tag}.{key}")

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]

    def handle_data(self, data):
        if not self.stack:
            self.add(data)


def metadata_fragments(path: str, value: Any, language: str, genre: str, *, config: bool = False) -> list[dict[str, Any]]:
    result = []
    public_config = {"title", "short_title", "description", "author", "unaltraweb"}
    def visit(node, pointer="", key="", depth=0):
        if depth > 20 or len(result) > MAX_FRAGMENTS:
            raise EditorialError("Public metadata exceeds editorial limits.")
        if isinstance(node, dict):
            for name, child in node.items():
                if not isinstance(name, str):
                    continue
                if config and not pointer and name not in public_config:
                    continue
                if name in {"editorial", "pdf", "computations", "features", "release"}:
                    continue
                visit(child, pointer + "/" + name.replace("~", "~0").replace("/", "~1"), name, depth + 1)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{pointer}/{index}", key, depth + 1)
        elif isinstance(node, str) and node.strip():
            localized = re.fullmatch(r"(.+)_(ca|en|es)(?:_[A-Za-z]+)?", key)
            base = localized[1] if localized else key
            if base in PUBLIC_FIELDS:
                result.append(fragment(path, node, line=0, field=pointer, kind="prose" if base == "bio" else "metadata",
                                       genre="bio" if base == "bio" else genre,
                                       language=localized[2] if localized else language, ordinal=len(result)))
    visit(value)
    return result


def document_fragments(path: str, text: str, language: str, genre: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    front: dict[str, Any] = {}
    body, offset = text, 0
    match = re.match(r"\A---\s*\r?\n(.*?)\r?\n---[^\S\n]*(?:\r?\n|\Z)", text, flags=re.S)
    if match:
        front = yaml_mapping(match[1])
        body, offset = text[match.end():], text[:match.end()].count("\n")
    language = str(front.get("lang") or language)
    local = front.get("editorial") or {}
    if not isinstance(local, dict) or set(local) - {"genre"}:
        raise EditorialError(f"Unsupported editorial front matter: {path}")
    genre = str(local.get("genre") or genre)
    if genre not in GENRES:
        raise EditorialError(f"Unknown editorial genre in {path}: {genre}")
    result = metadata_fragments(path, front, language, genre)
    projected = prose_projection(body, mask_quotes=False)
    if Path(path).suffix.lower() == ".html":
        parser = HTMLFragments(path, language, genre, line_offset=offset)
        parser.feed(projected)
        result.extend(parser.fragments)
        return front, result
    fence = ""
    for line, (original, raw) in enumerate(zip(body.splitlines(), projected.splitlines()), offset + 1):
        stripped = raw.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = ""
            continue
        if marker:
            fence = marker[1]
            continue
        # A single blockquote is an attributed/example surface for semantic
        # review. Higher-depth unaltraweb callouts remain ordinary prose.
        if re.match(r"^>(?!>)", stripped):
            result.append(fragment(path, original, line=line, genre="quote", language=language, ordinal=len(result)))
            continue
        if raw.startswith(("    ", "\t")):
            continue
        if not stripped:
            continue
        image = re.compile(r'!\[([^]\n]*)\]\(([^)\n]*?)(?:\s+"([^"\n]*)")?\)')
        for item in image.finditer(raw):
            for label, content in (("alt", item[1]), ("caption", item[3])):
                if content:
                    result.append(fragment(path, content, line=line, field=label, kind="metadata", genre=genre,
                                           language=language, ordinal=len(result)))
        raw = image.sub(lambda m: blank(m[0]), raw)
        if "<" in raw:
            parser = HTMLFragments(path, language, genre)
            parser.feed(raw)
            for item in parser.fragments:
                if item["kind"] == "metadata":
                    result.append(fragment(path, item["text"], line=line, field=item["field"], kind="metadata",
                                           genre=genre, language=language, ordinal=len(result)))
        raw = re.sub(r"<(?!insert\b)[^>]+>", lambda m: blank(m[0]), raw, flags=re.I)
        if raw.strip():
            unit = fragment(path, original, line=line, kind="heading" if stripped.startswith("#") else "prose",
                            genre=genre, language=language, ordinal=len(result))
            unit["prose"] = prose_projection(raw)
            result.append(unit)
    return front, result


def corpus(reader: Reader, config: dict[str, Any], profile: str, target: str = "", *, manual_only: bool = False) -> dict[str, Any]:
    if not isinstance(target, str):
        raise EditorialError("Editorial target must be a string.")
    if target:
        target = relative_path(target)
    default_lang = default_language(config)
    uw = config.get("unaltraweb") or {}
    manual = uw.get("manual") or {}
    if not isinstance(manual, dict):
        raise EditorialError("Manual configuration must be a mapping.")
    collection = str(manual.get("collection") or "chapters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", collection):
        raise EditorialError("Unsafe manual collection name.")
    roots = {f"_{collection}", "_pages"} if manual_only else set(CONTENT_ROOTS) | {"_data", f"_{collection}"}
    extra = config.get("collections") or {}
    if not manual_only and isinstance(extra, dict):
        roots.update("_" + key for key in extra if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", str(key)))
    root_pages = reader.root_pages() if not manual_only else []
    if target and target != "_config.yml" and target.split("/")[0] not in roots and target not in root_pages:
        raise EditorialError("Editorial target must be reader-facing content or public metadata.")
    paths = ([target] if Path(target).suffix else reader.walk(target)) if target else [path for root in sorted(roots) for path in reader.walk(root)]
    if not target:
        paths.extend(root_pages)
    if not target and not manual_only and reader.read("_config.yml", optional=True) is not None:
        paths.append("_config.yml")
    excludes = config.get("exclude") or []
    if not isinstance(excludes, list):
        raise EditorialError("Site exclude must be a list.")
    languages = config.get("languages") or [default_lang, "ca", "es", "en"]
    if not isinstance(languages, list) or any(not isinstance(lang, str) for lang in languages):
        raise EditorialError("Site languages must be a list of language codes.")
    sources, fragments, skipped = {}, [], []
    for path in sorted(set(paths)):
        if any(isinstance(pattern, str) and (fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("/") + "/")) for pattern in excludes):
            skipped.append({"path": path, "reason": "excluded by site configuration"})
            continue
        suffix = Path(path).suffix.lower()
        metadata = path == "_config.yml" or path.startswith("_data/")
        if suffix not in ({".yml", ".yaml", ".json"} if metadata else TEXT_SUFFIXES):
            continue
        content = reader.text(path)
        if path in root_pages and not re.match(r"\A---\s*\r?\n", content):
            skipped.append({"path": path, "reason": "root document has no Jekyll front matter"})
            continue
        lang = next((part for part in Path(path).parts if part in languages), default_lang)
        genre = "news" if path.startswith(("_news/", "_posts/")) else "chapter" if path.startswith(f"_{collection}/") else "reference" if profile == "unaltredocs" else "prose"
        if metadata:
            if suffix == ".json":
                data = strict_json(content)
            else:
                data = yaml_value(content)
            units = metadata_fragments(path, data, lang, genre, config=path == "_config.yml")
        else:
            front, units = document_fragments(path, content, lang, genre)
            profiles = front.get("profiles") or []
            if isinstance(profiles, str):
                profiles = [profiles]
            if not isinstance(profiles, list) or any(not isinstance(item, str) for item in profiles):
                raise EditorialError(f"Invalid profiles in {path}.")
            if front.get("published") is False or (profiles and profile not in profiles):
                skipped.append({"path": path, "reason": "not published in this profile"})
                continue
            if manual_only and path.startswith("_pages/") and front.get("layout") not in {"manual-home", "manual-chapter"} and "unaltremanual" not in profiles:
                continue
        sources[path] = {"path": path, "sha256": digest(content.encode()), "text": content, "editable_source": path}
        fragments.extend(units)
        if len(fragments) > MAX_FRAGMENTS:
            raise EditorialError("Editorial fragment budget exceeded; select a smaller target.")
    # A generated chapter is inspected as published, but its executable owner is
    # the editing target and is part of the review fingerprint.
    ownership = reader.text(".unaltraweb/computations.lock.json", optional=True)
    if ownership:
        lock = strict_json(ownership)
        if not isinstance(lock, dict) or lock.get("version") != 1 or not isinstance(lock.get("records"), dict):
            raise EditorialError("Invalid computation ownership inventory.")
        for owner, record in lock["records"].items():
            if not isinstance(record, dict) or not isinstance(record.get("output", {}), dict):
                raise EditorialError("Invalid computation ownership record.")
            output = record.get("output", {}).get("path")
            if output is not None and not isinstance(output, str):
                raise EditorialError("Invalid computed output path.")
            if output in sources:
                relative_path(owner)
                if Path(owner).suffix.lower() not in {".qmd", ".rmd", ".r", ".py", ".ipynb"}:
                    raise EditorialError("Computed prose needs an executable source owner.")
                sources[output]["editable_source"] = owner
                sources[output]["owner_sha256"] = digest(reader.read(owner))
                sources[output]["ownership_sha256"] = digest(canonical(record))
    if target and not sources:
        raise EditorialError(f"No selected publishable sources for target: {target}")
    return {"sources": sources, "fragments": fragments, "skipped": skipped,
            "coverage": "Markdown/HTML prose and public metadata fields; code, math and quotations require semantic/rendered review."}
