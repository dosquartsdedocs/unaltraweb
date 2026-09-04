from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import site_tools


MAX_COVER_BYTES = 64 * 1024 * 1024
MAX_IMPORT_COVER_BYTES = 256 * 1024 * 1024
MAX_METADATA_TEXT_LENGTH = 16 * 1024
MAX_IMPORT_BOOKS = 500
MAX_RELATED_RECORDS = 100_000


@dataclass(frozen=True)
class Book:
    calibre_id: int
    title: str
    authors: list[str]
    publisher: str | None
    series: str | None
    isbn: str | None
    doi: str | None
    pubdate: str | None
    path: PurePosixPath
    has_cover: bool
    tags: list[str]
    languages: list[str]


@dataclass(frozen=True)
class ExistingMarkdown:
    relative: Path
    content: str
    sha256: str
    calibre_source: str | None
    calibre_id: int | None
    cover: str | None
    metadata_sha256: str | None
    cover_sha256: str | None
    body: str


@dataclass(frozen=True)
class CoverWrite:
    relative: Path
    content: bytes
    expected_sha256: str | None
    original_content: bytes | None
    mode: int = 0o644
    original_mode: int | None = None


@dataclass(frozen=True)
class BookWrite:
    book: Book
    markdown_relative: Path
    markdown: str
    expected_sha256: str | None
    original_markdown: str | None
    cover_write: CoverWrite | None
    diff: str


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "book"


def yaml_scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_scalar(value) for value in values) + "]"


def first_year(pubdate: str | None) -> int | None:
    if not pubdate:
        return None
    match = re.match(r"^(\d{4})", pubdate)
    if not match:
        return None
    year = int(match.group(1))
    if year <= 1:
        return None
    return year


def first_date(pubdate: str | None, fallback: str | None = None) -> str:
    if not pubdate:
        return fallback or str(date.today())
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", pubdate)
    if match and int(match.group(1)) > 1:
        return match.group(0)
    year = first_year(pubdate)
    if year:
        return f"{year}-01-01"
    return fallback or str(date.today())


def language_label(codes: list[str]) -> str | None:
    labels = [code for code in codes if code]
    return ", ".join(labels) if labels else None


def _metadata_text(value: object, description: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{description} must be{' a non-empty' if required else ''} text value.")
    if len(value) > MAX_METADATA_TEXT_LENGTH:
        raise ValueError(f"{description} is too long.")
    if "<" in value or ">" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{description} contains unsafe markup or control characters.")
    return value


def _book_path(value: object, calibre_id: int) -> PurePosixPath:
    label = f"Calibre books.path for book {calibre_id}"
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty relative POSIX path.")
    if "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} is malformed.")
    parts = value.split("/")
    windows_path = PureWindowsPath(value)
    if value.startswith("/") or windows_path.drive or windows_path.is_absolute():
        raise ValueError(f"{label} must not be absolute.")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{label} must not contain empty or traversing components.")
    return PurePosixPath(*parts)


def _metadata_connection(library: Path) -> sqlite3.Connection:
    root_fd = _open_directory(library, "Calibre library")
    metadata_fd: int | None = None
    try:
        try:
            metadata_fd = os.open(
                "metadata.db",
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=root_fd,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"No metadata.db found at {library / 'metadata.db'}") from exc
        except OSError as exc:
            raise RuntimeError(f"Could not open Calibre metadata.db safely: {exc}") from exc
        metadata = os.fstat(metadata_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("Calibre metadata.db must be a regular file.")

        descriptor_root = Path("/proc/self/fd")
        if not descriptor_root.is_dir():
            descriptor_root = Path("/dev/fd")
        if not descriptor_root.is_dir():
            raise RuntimeError("This host does not expose descriptor-backed paths required for safe Calibre access.")
        connection = sqlite3.connect(f"file:{descriptor_root / str(metadata_fd)}?mode=ro", uri=True)
        connection.execute("pragma query_only = on")
        return connection
    finally:
        if metadata_fd is not None:
            os.close(metadata_fd)
        os.close(root_fd)


def _bounded_rows(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    description: str,
):
    for index, row in enumerate(connection.execute(query, parameters)):
        if index >= MAX_RELATED_RECORDS:
            raise RuntimeError(f"Calibre {description} exceeds the safe record limit ({MAX_RELATED_RECORDS}).")
        yield row


def _select_book_ids(
    library: Path,
    *,
    requested_ids: set[int] | None,
    imported_ids: set[int],
    refresh_existing: bool,
    limit: int | None,
) -> tuple[int, list[int]]:
    connection = _metadata_connection(library)
    try:
        library_count = int(connection.execute("select count(*) from books").fetchone()[0])
        parameters: tuple[object, ...] = ()
        query = "select id from books"
        if requested_ids:
            placeholders = ", ".join("?" for _ in requested_ids)
            query += f" where id in ({placeholders})"
            parameters = tuple(sorted(requested_ids))
        query += " order by title collate nocase"

        selected: list[int] = []
        available_ids: set[int] = set()
        new_count = 0
        for (book_id,) in connection.execute(query, parameters):
            available_ids.add(book_id)
            if book_id in imported_ids:
                if refresh_existing:
                    selected.append(book_id)
                continue
            if limit is not None and new_count >= limit:
                continue
            selected.append(book_id)
            new_count += 1
        if requested_ids:
            missing_ids = sorted(requested_ids - available_ids)
            if missing_ids:
                raise RuntimeError(f"Book IDs not found in library: {', '.join(str(item) for item in missing_ids)}")
        if len(selected) > MAX_IMPORT_BOOKS:
            raise RuntimeError(
                f"Calibre import selected {len(selected)} books; use --limit or --ids to stay within the safe limit ({MAX_IMPORT_BOOKS})."
            )
        return library_count, selected
    finally:
        connection.close()


def grouped_values(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[object, ...],
    description: str,
) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for book_id, value in _bounded_rows(connection, query, parameters, description):
        grouped.setdefault(book_id, []).append(_metadata_text(value, description, required=True))
    return grouped


def load_books(library: Path, book_ids: list[int]) -> list[Book]:
    if not book_ids:
        return []
    connection = _metadata_connection(library)
    try:
        placeholders = ", ".join("?" for _ in book_ids)
        parameters = tuple(book_ids)
        authors = grouped_values(
            connection,
            f"""
            select bal.book, authors.name
            from books_authors_link bal
            join authors on authors.id = bal.author
            where bal.book in ({placeholders})
            order by bal.id
            """,
            parameters,
            "Calibre author",
        )
        tags = grouped_values(
            connection,
            f"""
            select btl.book, tags.name
            from books_tags_link btl
            join tags on tags.id = btl.tag
            where btl.book in ({placeholders})
            order by tags.name
            """,
            parameters,
            "Calibre tag",
        )
        languages = grouped_values(
            connection,
            f"""
            select bll.book, languages.lang_code
            from books_languages_link bll
            join languages on languages.id = bll.lang_code
            where bll.book in ({placeholders})
            order by bll.item_order, bll.id
            """,
            parameters,
            "Calibre language code",
        )
        publishers = {
            book_id: _metadata_text(value, "Calibre publisher", required=True)
            for book_id, value in _bounded_rows(
                connection,
                f"""
                select bpl.book, publishers.name
                from books_publishers_link bpl
                join publishers on publishers.id = bpl.publisher
                where bpl.book in ({placeholders})
                """,
                parameters,
                "publisher records",
            )
        }
        series = {
            book_id: _metadata_text(value, "Calibre series", required=True)
            for book_id, value in _bounded_rows(
                connection,
                f"""
                select bsl.book, series.name
                from books_series_link bsl
                join series on series.id = bsl.series
                where bsl.book in ({placeholders})
                """,
                parameters,
                "series records",
            )
        }
        identifiers: dict[int, dict[str, str]] = {}
        for book_id, identifier_type, identifier_value in _bounded_rows(
            connection,
            f"""
            select book, lower(type), val
            from identifiers
            where book in ({placeholders})
            order by id
            """,
            parameters,
            "identifier records",
        ):
            identifier_name = _metadata_text(identifier_type, "Calibre identifier type", required=True)
            identifier = _metadata_text(identifier_value, f"Calibre {identifier_name} identifier", required=True)
            identifiers.setdefault(book_id, {})[identifier_name.lower()] = identifier

        books = []
        for row in _bounded_rows(
            connection,
            f"""
            select id, title, isbn, pubdate, path, has_cover
            from books
            where id in ({placeholders})
            order by title collate nocase
            """,
            parameters,
            "book records",
        ):
            book_id, title, isbn, pubdate, path, has_cover = row
            book_identifiers = identifiers.get(book_id, {})
            books.append(
                Book(
                    calibre_id=book_id,
                    title=_metadata_text(title, f"Calibre title for book {book_id}", required=True),
                    authors=authors.get(book_id, []),
                    publisher=publishers.get(book_id),
                    series=series.get(book_id),
                    isbn=_metadata_text(isbn, f"Calibre ISBN for book {book_id}") or book_identifiers.get("isbn"),
                    doi=book_identifiers.get("doi"),
                    pubdate=pubdate,
                    path=_book_path(path, book_id),
                    has_cover=bool(has_cover),
                    tags=tags.get(book_id, []),
                    languages=languages.get(book_id, []),
                )
            )
        return books
    finally:
        connection.close()


def normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def duplicate_title_groups(books: list[Book]) -> list[list[Book]]:
    grouped: dict[str, list[Book]] = {}
    for book in books:
        grouped.setdefault(normalized_title(book.title), []).append(book)
    return [group for group in grouped.values() if len(group) > 1]


def markdown_for_book(
    book: Book,
    *,
    source_key: str,
    collection_name: str,
    collection_ref: str | None,
    collection_labels: dict[str, str],
    profiles: list[str],
    lang: str,
    status: str,
    rating: int | float | None,
    cover_path: str | None,
    cover_sha256: str | None,
    fallback_date: str,
    body: str = "",
) -> str:
    slug = f"calibre-{source_key}-{book.calibre_id}-{slugify(book.title)}"
    author = " & ".join(book.authors) if book.authors else None
    year = first_year(book.pubdate)
    book_language = language_label(book.languages)

    lines = [
        "layout: book-review",
        f"lang: {yaml_scalar(lang)}",
        f"ref: {slug}",
        f"profiles: {yaml_list(profiles)}",
        f"permalink: /{lang}/readings/{slug}/",
        f"title: {yaml_scalar(book.title)}",
        f"calibre_source: {yaml_scalar(source_key)}",
        f"calibre_id: {book.calibre_id}",
        f"status: {yaml_scalar(status)}",
        f"date: {first_date(book.pubdate, fallback_date)}",
    ]
    if collection_ref:
        lines.append(f"collection_ref: {yaml_scalar(collection_ref)}")
    lines.append(f"collection_name: {yaml_scalar(collection_name)}")
    for label_lang, label in collection_labels.items():
        lines.append(f"collection_{label_lang}: {yaml_scalar(label)}")
    if author:
        lines.append(f"author: {yaml_scalar(author)}")
    if book.publisher:
        lines.append(f"publisher: {yaml_scalar(book.publisher)}")
    if book.series:
        lines.append(f"series: {yaml_scalar(book.series)}")
    if year:
        lines.append(f"year: {year}")
    if book.isbn:
        lines.append(f"isbn: {yaml_scalar(book.isbn)}")
    if book.doi:
        lines.append(f"doi: {yaml_scalar(book.doi)}")
    if rating is not None:
        lines.append(f"rating: {rating}")
    if book_language:
        lines.append(f"book_language: {yaml_scalar(book_language)}")
    if cover_path:
        lines.append(f"cover: {yaml_scalar(cover_path)}")
    if cover_sha256:
        lines.append(f"calibre_cover_sha256: {yaml_scalar(cover_sha256)}")
    if book.tags:
        lines.append("tags:")
        for tag in book.tags:
            lines.append(f"  - {yaml_scalar(tag)}")
    metadata_sha256 = _sha256("\n".join(lines).encode("utf-8"))
    marker_index = lines.index(f"calibre_id: {book.calibre_id}") + 1
    lines.insert(marker_index, f"calibre_metadata_sha256: {yaml_scalar(metadata_sha256)}")
    front_matter = "\n".join(lines)
    return f"---\n{front_matter}\n---\n{body}"


def parse_profiles(value: str) -> list[str]:
    profiles = [item.strip() for item in value.split(",") if item.strip()]
    if not profiles:
        raise argparse.ArgumentTypeError("At least one profile is required")
    invalid = sorted(set(profiles) - set(site_tools.PROFILE_CONTRACTS))
    if invalid:
        raise argparse.ArgumentTypeError(f"Unsupported profile: {', '.join(invalid)}")
    return profiles


def parse_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid book id: {item}") from exc
    if not ids:
        raise argparse.ArgumentTypeError("At least one id is required")
    return ids


def parse_source_key(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value):
        raise argparse.ArgumentTypeError("Source key must be a lowercase slug beginning with a letter")
    return value


def parse_rating(value: str) -> int | float:
    try:
        rating = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid rating: {value}") from exc
    if not math.isfinite(rating) or rating < 0 or rating > 5:
        raise argparse.ArgumentTypeError("Rating must be between 0 and 5")
    return int(rating) if rating.is_integer() else rating


def parse_language(value: str) -> str:
    language = value.strip()
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
        raise argparse.ArgumentTypeError("Language must be a BCP 47-style language tag")
    return language


def parse_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid limit: {value}") from exc
    if limit < 0:
        raise argparse.ArgumentTypeError("Limit must not be negative")
    return limit


def _open_directory(path: Path, description: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    absolute = Path(os.path.abspath(path))
    current_fd: int | None = None
    try:
        current_fd = os.open(os.sep, flags)
        for part in absolute.parts[1:]:
            metadata = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise RuntimeError(f"{description} path must not traverse symlinks: {absolute}")
            if not stat.S_ISDIR(metadata.st_mode):
                raise RuntimeError(f"{description} path is not a directory: {absolute}")
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except OSError as exc:
        if current_fd is not None:
            os.close(current_fd)
        raise RuntimeError(f"Could not open {description} safely: {absolute}: {exc}") from exc
    except Exception:
        if current_fd is not None:
            os.close(current_fd)
        raise


def _cover_source(library_fd: int, book: Book) -> bytes | None:
    if not book.has_cover:
        return None
    current_fd = os.dup(library_fd)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        for part in book.path.parts:
            try:
                metadata = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            except FileNotFoundError:
                return None
            if stat.S_ISLNK(metadata.st_mode):
                raise RuntimeError(f"Calibre cover path for book {book.calibre_id} traverses a source symlink: {book.path}")
            if not stat.S_ISDIR(metadata.st_mode):
                raise RuntimeError(f"Calibre cover path for book {book.calibre_id} is not a directory: {book.path}")
            try:
                next_fd = os.open(part, flags, dir_fd=current_fd)
            except OSError as exc:
                raise RuntimeError(f"Calibre cover path for book {book.calibre_id} changed or traverses a symlink: {book.path}") from exc
            os.close(current_fd)
            current_fd = next_fd

        try:
            metadata = os.stat("cover.jpg", dir_fd=current_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError(f"Calibre cover for book {book.calibre_id} must not be a source symlink.")
        content, _ = site_tools._read_regular_at(
            current_fd,
            "cover.jpg",
            max_bytes=MAX_COVER_BYTES,
            description=f"Calibre cover for book {book.calibre_id}",
        )
        return content
    finally:
        os.close(current_fd)


def _front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            return "\n".join(lines[1:index])
    return ""


def _markdown_body(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return ""
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") == "---":
            return text[offset:]
    return ""


def _metadata_hash(front_matter: str) -> str:
    managed_lines = [
        line
        for line in front_matter.splitlines()
        if not line.startswith("calibre_metadata_sha256:")
    ]
    return _sha256("\n".join(managed_lines).encode("utf-8"))


def _managed_date(front_matter: str) -> str | None:
    match = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})\s*$", front_matter, flags=re.MULTILINE)
    return match.group(1) if match else None


def _import_metadata(text: str) -> tuple[str | None, int | None, str | None, str | None, str | None]:
    front_matter = _front_matter(text)
    try:
        parsed = site_tools.load_yaml_text(front_matter)
    except (TypeError, ValueError):
        return None, None, None, None, None
    if not isinstance(parsed, dict):
        return None, None, None, None, None
    raw_source = parsed.get("calibre_source")
    source = raw_source if isinstance(raw_source, str) and re.fullmatch(r"[a-z0-9-]+", raw_source) else None
    raw_id = parsed.get("calibre_id")
    calibre_id = raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) and raw_id >= 0 else None
    raw_cover = parsed.get("cover")
    cover = raw_cover if isinstance(raw_cover, str) else None
    raw_metadata_sha256 = parsed.get("calibre_metadata_sha256")
    metadata_sha256 = raw_metadata_sha256 if isinstance(raw_metadata_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", raw_metadata_sha256) else None
    raw_cover_sha256 = parsed.get("calibre_cover_sha256")
    cover_sha256 = raw_cover_sha256 if isinstance(raw_cover_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", raw_cover_sha256) else None
    return source, calibre_id, cover, metadata_sha256, cover_sha256


def _existing_markdown(project: Path) -> list[ExistingMarkdown]:
    books_root = project / "_books"
    if not books_root.is_dir():
        return []
    records = []
    candidates = sorted(
        path for path in books_root.rglob("*")
        if path.suffix.lower() in {".md", ".markdown"}
    )
    for path in candidates:
        relative = path.relative_to(project)
        source = site_tools.site_source_read(project, relative.as_posix())
        calibre_source, calibre_id, cover, metadata_sha256, cover_sha256 = _import_metadata(source["content"])
        records.append(
            ExistingMarkdown(
                relative=relative,
                content=source["content"],
                sha256=source["sha256"],
                calibre_source=calibre_source,
                calibre_id=calibre_id,
                cover=cover,
                metadata_sha256=metadata_sha256,
                cover_sha256=cover_sha256,
                body=_markdown_body(source["content"]),
            )
        )
    return records


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _cover_target(project: Path, relative: Path) -> tuple[bytes, str, int] | None:
    root_fd = site_tools._open_project_root(project)
    parent_fd: int | None = None
    try:
        try:
            parent_fd = site_tools._open_scaffold_directory(root_fd, relative.parent, create=False)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise RuntimeError(f"Could not inspect cover destination safely: {relative}: {exc}") from exc
        try:
            metadata = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError(f"Cover destination must not be a symlink: {relative}")
        content, _ = site_tools._read_regular_at(
            parent_fd,
            relative.name,
            max_bytes=MAX_COVER_BYTES,
            description=f"Cover destination {relative}",
        )
        return content, _sha256(content), stat.S_IMODE(metadata.st_mode)
    finally:
        if parent_fd is not None:
            os.close(parent_fd)
        os.close(root_fd)


def _atomic_cover_write(project: Path, write: CoverWrite) -> None:
    root_fd = site_tools._open_project_root(project)
    try:
        parent_fd = site_tools._open_scaffold_directory(root_fd, write.relative.parent, create=True)
    except Exception:
        os.close(root_fd)
        raise
    temporary = f".unaltraweb-calibre-cover-{os.getpid()}-{time.time_ns()}"
    backup = f".unaltraweb-calibre-cover-backup-{os.getpid()}-{time.time_ns()}"
    temp_fd: int | None = None
    backup_present = False
    installed_identity: tuple[int, int] | None = None
    locked = False
    committed = False
    try:
        fcntl.flock(parent_fd, fcntl.LOCK_EX)
        locked = True
        temp_fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o644,
            dir_fd=parent_fd,
        )
        site_tools._write_all(temp_fd, write.content)
        os.fchmod(temp_fd, write.mode)
        os.fsync(temp_fd)

        if write.expected_sha256 is not None:
            current, metadata = site_tools._read_regular_at(
                parent_fd,
                write.relative.name,
                max_bytes=MAX_COVER_BYTES,
                description=f"Cover destination {write.relative}",
            )
            current_metadata = os.stat(write.relative.name, dir_fd=parent_fd, follow_symlinks=False)
            if _sha256(current) != write.expected_sha256 or site_tools._path_identity(metadata) != site_tools._path_identity(current_metadata):
                raise RuntimeError(f"Cover changed after Calibre import preflight: {write.relative}")
            os.rename(write.relative.name, backup, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            backup_present = True
            moved, moved_metadata = site_tools._read_regular_at(
                parent_fd,
                backup,
                max_bytes=MAX_COVER_BYTES,
                description=f"Cover backup {write.relative}",
            )
            if _sha256(moved) != write.expected_sha256 or site_tools._path_identity(moved_metadata) != site_tools._path_identity(metadata):
                site_tools._restore_private_backup(parent_fd, write.relative.name, backup, None)
                backup_present = False
                raise RuntimeError(f"Cover changed in the final Calibre import window: {write.relative}")

        try:
            os.link(temporary, write.relative.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
        except FileExistsError as exc:
            if backup_present:
                site_tools._restore_private_backup(parent_fd, write.relative.name, backup, None)
                backup_present = False
            raise RuntimeError(f"Cover destination appeared after Calibre import preflight: {write.relative}") from exc
        installed_identity = site_tools._path_identity(os.stat(write.relative.name, dir_fd=parent_fd, follow_symlinks=False))
        if backup_present:
            after, after_metadata = site_tools._read_regular_at(
                parent_fd,
                backup,
                max_bytes=MAX_COVER_BYTES,
                description=f"Cover backup {write.relative}",
            )
            if _sha256(after) != write.expected_sha256 or site_tools._path_identity(after_metadata) != site_tools._path_identity(metadata):
                site_tools._restore_private_backup(parent_fd, write.relative.name, backup, installed_identity)
                backup_present = False
                installed_identity = None
                raise RuntimeError(f"Cover changed in the final Calibre import window: {write.relative}")
        os.fsync(parent_fd)
        os.unlink(temporary, dir_fd=parent_fd)
        temporary = ""
        if backup_present:
            os.unlink(backup, dir_fd=parent_fd)
            backup_present = False
        committed = True
    finally:
        if backup_present:
            try:
                site_tools._restore_private_backup(parent_fd, write.relative.name, backup, installed_identity)
            except (OSError, RuntimeError):
                pass
        elif not committed and installed_identity is not None:
            try:
                site_tools._unlink_if_identity(parent_fd, write.relative.name, installed_identity)
            except OSError:
                pass
        if temp_fd is not None:
            os.close(temp_fd)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        if locked:
            fcntl.flock(parent_fd, fcntl.LOCK_UN)
        os.close(parent_fd)
        os.close(root_fd)


def _atomic_cover_delete(project: Path, relative: Path, expected_sha256: str) -> None:
    root_fd = site_tools._open_project_root(project)
    parent_fd: int | None = None
    locked = False
    tombstone = f".unaltraweb-calibre-cover-delete-{os.getpid()}-{time.time_ns()}"
    moved = False
    try:
        parent_fd = site_tools._open_scaffold_directory(root_fd, relative.parent, create=False)
        fcntl.flock(parent_fd, fcntl.LOCK_EX)
        locked = True
        content, metadata = site_tools._read_regular_at(
            parent_fd,
            relative.name,
            max_bytes=MAX_COVER_BYTES,
            description=f"Cover rollback {relative}",
        )
        path_metadata = os.stat(relative.name, dir_fd=parent_fd, follow_symlinks=False)
        if _sha256(content) != expected_sha256 or site_tools._path_identity(metadata) != site_tools._path_identity(path_metadata):
            raise RuntimeError(f"Cover changed before rollback: {relative}")
        os.rename(relative.name, tombstone, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        moved = True
        rechecked, rechecked_metadata = site_tools._read_regular_at(
            parent_fd,
            tombstone,
            max_bytes=MAX_COVER_BYTES,
            description=f"Cover rollback {relative}",
        )
        if _sha256(rechecked) != expected_sha256 or site_tools._path_identity(rechecked_metadata) != site_tools._path_identity(metadata):
            os.rename(tombstone, relative.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            moved = False
            raise RuntimeError(f"Cover changed in the final rollback window: {relative}")
        os.unlink(tombstone, dir_fd=parent_fd)
        moved = False
        os.fsync(parent_fd)
    finally:
        if moved and parent_fd is not None:
            try:
                os.rename(tombstone, relative.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except OSError:
                pass
        if locked and parent_fd is not None:
            fcntl.flock(parent_fd, fcntl.LOCK_UN)
        if parent_fd is not None:
            os.close(parent_fd)
        os.close(root_fd)


def _rollback_import(project: Path, markdown_plans: list[BookWrite], cover_writes: list[CoverWrite]) -> list[str]:
    errors: list[str] = []
    for cover in reversed(cover_writes):
        try:
            installed_sha256 = _sha256(cover.content)
            current = _cover_target(project, cover.relative)
            if current is None:
                if cover.original_content is None:
                    continue
                raise RuntimeError(f"Cover disappeared before rollback: {cover.relative}")
            if cover.expected_sha256 is not None and current[1] == cover.expected_sha256:
                continue
            if current[1] != installed_sha256:
                raise RuntimeError(f"Cover changed before rollback: {cover.relative}")
            if cover.original_content is None:
                _atomic_cover_delete(project, cover.relative, installed_sha256)
            else:
                _atomic_cover_write(
                    project,
                    CoverWrite(
                        cover.relative,
                        cover.original_content,
                        installed_sha256,
                        cover.content,
                        mode=cover.original_mode or 0o644,
                    ),
                )
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"cover {cover.relative}: {exc}")
    for plan in reversed(markdown_plans):
        try:
            installed_sha256 = _sha256(plan.markdown.encode("utf-8"))
            try:
                current = site_tools.site_source_read(project, plan.markdown_relative.as_posix())
            except (FileNotFoundError, RuntimeError) as exc:
                missing = isinstance(exc, FileNotFoundError) or isinstance(exc.__cause__, FileNotFoundError)
                if not missing:
                    raise
                if plan.original_markdown is None:
                    continue
                raise RuntimeError(f"Markdown disappeared before rollback: {plan.markdown_relative}") from exc
            if plan.expected_sha256 is not None and current["sha256"] == plan.expected_sha256:
                continue
            if current["sha256"] != installed_sha256:
                raise RuntimeError(f"Markdown changed before rollback: {plan.markdown_relative}")
            if plan.original_markdown is None:
                site_tools.site_source_delete(
                    project,
                    plan.markdown_relative.as_posix(),
                    expected_sha256=installed_sha256,
                    dry_run=False,
                    confirm_delete=True,
                )
            else:
                site_tools.site_source_write(
                    project,
                    plan.markdown_relative.as_posix(),
                    plan.original_markdown,
                    expected_sha256=installed_sha256,
                    dry_run=False,
                )
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"Markdown {plan.markdown_relative}: {exc}")
    return errors


def _import_calibre_locked(
    project: Path,
    *,
    library: Path,
    source_key: str,
    collection_name: str,
    collection_ref: str | None = None,
    collection_labels: dict[str, str] | None = None,
    profiles: list[str],
    ids: set[int] | None = None,
    lang: str | None = None,
    status: str = "queued",
    rating: int | float | None = None,
    limit: int | None = None,
    write: bool = False,
    refresh_existing: bool = False,
) -> dict[str, object]:
    project = site_tools.project_path(project)
    project_fd = site_tools._open_project_root(project)
    os.close(project_fd)
    if not site_tools.detect_site(project)["is_unaltraweb_site"]:
        raise RuntimeError(f"Calibre imports require an unaltraweb consumer site: {project}")
    library = Path(os.path.abspath(library.expanduser()))
    library_fd = _open_directory(library, "Calibre library")
    os.close(library_fd)
    run_date = str(date.today())

    try:
        selected_source_key = parse_source_key(source_key)
    except argparse.ArgumentTypeError as exc:
        raise ValueError(str(exc)) from exc
    selected_collection_ref = slugify(collection_ref) if collection_ref else None
    collection_name = _metadata_text(collection_name, "Collection name", required=True)
    status = _metadata_text(status, "Reading status", required=True)
    config = site_tools.site_config(project)
    selected_lang = lang or str(config.get("default_lang") or config.get("lang") or "en")
    try:
        lang = parse_language(selected_lang)
    except argparse.ArgumentTypeError as exc:
        raise ValueError(str(exc)) from exc
    configured_languages = config.get("languages")
    if isinstance(configured_languages, list):
        enabled_languages = [str(value) for value in configured_languages]
        if enabled_languages and lang not in enabled_languages:
            raise ValueError(f"Language '{lang}' is not enabled in the destination site")
    if limit is not None and limit < 0:
        raise ValueError("Limit must not be negative")
    labels = {
        label_lang: _metadata_text(label, f"Collection label {label_lang}", required=True)
        for label_lang, label in (collection_labels or {}).items()
    }
    if rating is not None and (not isinstance(rating, (int, float)) or isinstance(rating, bool) or not math.isfinite(rating) or rating < 0 or rating > 5):
        raise ValueError("Rating must be a finite number between 0 and 5")
    existing = _existing_markdown(project)
    by_import: dict[tuple[str, int], list[ExistingMarkdown]] = {}
    for record in existing:
        if record.calibre_source is not None and record.calibre_id is not None:
            by_import.setdefault((record.calibre_source, record.calibre_id), []).append(record)
    imported_ids = {
        record.calibre_id
        for record in existing
        if record.calibre_source == selected_source_key and record.calibre_id is not None
    }
    library_count, selected_ids = _select_book_ids(
        library,
        requested_ids=ids,
        imported_ids=imported_ids,
        refresh_existing=refresh_existing,
        limit=limit,
    )
    selected_books = load_books(library, selected_ids)

    library_fd = _open_directory(library, "Calibre library")
    source_covers: dict[int, bytes | None] = {}
    total_cover_bytes = 0
    try:
        for book in selected_books:
            cover = _cover_source(library_fd, book)
            if cover is not None:
                total_cover_bytes += len(cover)
                if total_cover_bytes > MAX_IMPORT_COVER_BYTES:
                    raise RuntimeError(
                        f"Selected covers exceed the {MAX_IMPORT_COVER_BYTES // (1024 * 1024)} MiB import limit; use --limit or --ids."
                    )
            source_covers[book.calibre_id] = cover
    finally:
        os.close(library_fd)

    plans: list[BookWrite] = []
    conflicts: list[str] = []
    for book in selected_books:
        conflict_count = len(conflicts)
        owned_records = by_import.get((selected_source_key, book.calibre_id), [])
        if len(owned_records) > 1:
            paths = ", ".join(record.relative.as_posix() for record in owned_records)
            conflicts.append(f"multiple Markdown files claim source '{selected_source_key}' and Calibre ID {book.calibre_id}: {paths}")
            continue
        owned = owned_records[0] if owned_records else None
        fallback_date = run_date
        if owned is not None:
            front_matter = _front_matter(owned.content)
            if owned.metadata_sha256 is None or _metadata_hash(front_matter) != owned.metadata_sha256:
                conflicts.append(
                    f"managed metadata changed or lacks a refresh baseline: {owned.relative}; preserve it and import without --refresh-existing"
                )
                continue
            fallback_date = _managed_date(front_matter) or run_date
        generated_slug = f"calibre-{selected_source_key}-{book.calibre_id}-{slugify(book.title)}"
        markdown_relative = owned.relative if owned is not None else Path("_books") / f"{generated_slug}.md"
        source_cover = source_covers[book.calibre_id]
        cover_write = None
        cover_path = None
        cover_sha256 = None
        if source_cover is not None:
            cover_relative = Path("assets/img/books") / f"{markdown_relative.stem}.jpg"
            cover_path = f"/{cover_relative.as_posix()}"
            source_cover_sha256 = _sha256(source_cover)
            try:
                target = _cover_target(project, cover_relative)
            except (OSError, RuntimeError, ValueError) as exc:
                conflicts.append(str(exc))
            else:
                if target is None:
                    if owned is not None and owned.cover not in {None, cover_path}:
                        conflicts.append(f"managed cover path changed: {owned.relative}")
                    else:
                        cover_sha256 = source_cover_sha256
                        cover_write = CoverWrite(cover_relative, source_cover, None, None)
                elif owned is None or owned.cover != cover_path:
                    conflicts.append(f"unrelated cover destination already exists: {cover_relative}")
                elif owned.cover_sha256 is None:
                    if target[1] != source_cover_sha256:
                        conflicts.append(f"managed cover lacks a safe refresh baseline: {cover_relative}")
                    else:
                        cover_sha256 = source_cover_sha256
                elif target[1] != owned.cover_sha256:
                    conflicts.append(f"managed cover was edited after import: {cover_relative}")
                else:
                    cover_sha256 = source_cover_sha256
                    if target[0] != source_cover:
                        cover_write = CoverWrite(
                            cover_relative,
                            source_cover,
                            target[1],
                            target[0],
                            mode=target[2],
                            original_mode=target[2],
                        )
        elif owned is not None and owned.cover:
            if not owned.cover.startswith("/assets/img/books/"):
                conflicts.append(f"managed cover path is outside assets/img/books: {owned.relative}")
            else:
                cover_relative = Path(owned.cover.lstrip("/"))
                try:
                    target = _cover_target(project, cover_relative)
                except (OSError, RuntimeError, ValueError) as exc:
                    conflicts.append(str(exc))
                else:
                    if target is None:
                        conflicts.append(f"managed cover is missing and Calibre has no replacement: {cover_relative}")
                    elif owned.cover_sha256 is None or target[1] != owned.cover_sha256:
                        conflicts.append(f"managed cover was edited or lacks a refresh baseline: {cover_relative}")
                    else:
                        cover_path = owned.cover
                        cover_sha256 = owned.cover_sha256

        if len(conflicts) != conflict_count:
            continue

        markdown = markdown_for_book(
            book,
            source_key=selected_source_key,
            collection_name=collection_name,
            collection_ref=selected_collection_ref,
            collection_labels=labels,
            profiles=profiles,
            lang=lang,
            status=status,
            rating=rating,
            cover_path=cover_path,
            cover_sha256=cover_sha256,
            fallback_date=fallback_date,
            body=owned.body if owned is not None else "",
        )

        expected_sha256 = owned.sha256 if owned is not None else None
        try:
            preview = site_tools.site_source_write(
                project,
                markdown_relative.as_posix(),
                markdown,
                expected_sha256=expected_sha256 or "",
                create_only=expected_sha256 is None,
                dry_run=True,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            conflicts.append(f"{markdown_relative}: {exc}")
            continue
        plans.append(
            BookWrite(
                book,
                markdown_relative,
                markdown,
                expected_sha256,
                owned.content if owned is not None else None,
                cover_write,
                str(preview["diff"]["text"]),
            )
        )

    if conflicts:
        details = "\n".join(f"- {message}" for message in sorted(set(conflicts)))
        raise RuntimeError(f"Calibre import preflight failed; no project files were written:\n{details}")

    if write:
        written_markdown: list[BookWrite] = []
        written_covers: list[CoverWrite] = []
        try:
            for plan in plans:
                written_markdown.append(plan)
                site_tools.site_source_write(
                    project,
                    plan.markdown_relative.as_posix(),
                    plan.markdown,
                    expected_sha256=plan.expected_sha256 or "",
                    create_only=plan.expected_sha256 is None,
                    dry_run=False,
                )
            for plan in plans:
                if plan.cover_write is not None:
                    written_covers.append(plan.cover_write)
                    _atomic_cover_write(project, plan.cover_write)
        except BaseException as exc:
            rollback_errors = _rollback_import(project, written_markdown, written_covers)
            suffix = f" Rollback failures: {'; '.join(rollback_errors)}" if rollback_errors else " All completed writes were rolled back."
            if isinstance(exc, (OSError, RuntimeError, ValueError)):
                raise RuntimeError(f"Calibre import failed while committing outputs: {exc}.{suffix}") from exc
            if rollback_errors:
                raise RuntimeError(f"Calibre import was interrupted.{suffix}") from exc
            raise

    duplicates = duplicate_title_groups(selected_books)
    return {
        "project": str(project),
        "library": str(library),
        "library_count": library_count,
        "selected_count": len(selected_books),
        "already_imported_count": len(imported_ids),
        "write_count": len(plans),
        "cover_count": sum(source_covers[book.calibre_id] is not None for book in selected_books),
        "source_key": selected_source_key,
        "mode": "write" if write else "dry-run",
        "duplicate_titles": [
            {"title": group[0].title, "ids": [book.calibre_id for book in group]}
            for group in duplicates
        ],
        "items": [
            {
                "calibre_id": plan.book.calibre_id,
                "title": plan.book.title,
                "path": plan.markdown_relative.as_posix(),
                "diff": plan.diff,
            }
            for plan in plans
        ],
    }


def import_calibre(
    project: Path,
    *,
    library: Path,
    source_key: str,
    collection_name: str,
    collection_ref: str | None = None,
    collection_labels: dict[str, str] | None = None,
    profiles: list[str],
    ids: set[int] | None = None,
    lang: str | None = None,
    status: str = "queued",
    rating: int | float | None = None,
    limit: int | None = None,
    write: bool = False,
    refresh_existing: bool = False,
) -> dict[str, object]:
    project = site_tools.project_path(project)
    project_fd = site_tools._open_project_root(project)
    try:
        fcntl.flock(project_fd, fcntl.LOCK_EX)
        return _import_calibre_locked(
            project,
            library=library,
            source_key=source_key,
            collection_name=collection_name,
            collection_ref=collection_ref,
            collection_labels=collection_labels,
            profiles=profiles,
            ids=ids,
            lang=lang,
            status=status,
            rating=rating,
            limit=limit,
            write=write,
            refresh_existing=refresh_existing,
        )
    finally:
        fcntl.flock(project_fd, fcntl.LOCK_UN)
        os.close(project_fd)


def print_summary(result: dict[str, object]) -> None:
    print(f"Calibre library: {result['library']}")
    print(f"Books in library: {result['library_count']}")
    print(f"Books selected from library: {result['selected_count']}")
    print(f"Already imported for source '{result['source_key']}': {result['already_imported_count']}")
    print(f"Books to write in this run: {result['write_count']}")
    print(f"Books with local covers in this run: {result['cover_count']}")
    duplicate_titles = result["duplicate_titles"]
    if duplicate_titles:
        print("Duplicate titles in this run:")
        for group in duplicate_titles:
            ids = ", ".join(str(book_id) for book_id in group["ids"])
            print(f"  - {group['title']}: {ids}")
    print(f"Mode: {result['mode']}")
    for item in result["items"]:
        print(f"- {item['calibre_id']}: {item['title']} -> {item['path']}")
        if result["mode"] == "dry-run" and item["diff"]:
            print(item["diff"])
