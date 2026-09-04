from __future__ import annotations

import io
import sqlite3
import stat
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from datetime import date as calendar_date
from pathlib import Path
from unittest.mock import patch

from unaltraweb_mcp import calibre_import, cli


class CalibreImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "site"
        self.library = self.root / "library"
        self.project.mkdir()
        self.library.mkdir()
        (self.project / "_config.yml").write_text("theme: unaltraweb\nunaltraweb:\n  site_profile: unaltremanual\n", encoding="utf-8")
        self._create_database()
        self._add_book()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create_database(self) -> None:
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.executescript(
                """
                create table books (id integer primary key, title text, isbn text, pubdate text, path text, has_cover integer);
                create table authors (id integer primary key, name text);
                create table books_authors_link (id integer primary key, book integer, author integer);
                create table tags (id integer primary key, name text);
                create table books_tags_link (id integer primary key, book integer, tag integer);
                create table languages (id integer primary key, lang_code text);
                create table books_languages_link (id integer primary key, book integer, lang_code integer, item_order integer);
                create table publishers (id integer primary key, name text);
                create table books_publishers_link (id integer primary key, book integer, publisher integer);
                create table series (id integer primary key, name text);
                create table books_series_link (id integer primary key, book integer, series integer);
                create table identifiers (id integer primary key, book integer, type text, val text);
                insert into authors values (1, 'Test Author');
                insert into tags values (1, 'Geography');
                insert into languages values (1, 'eng');
                insert into publishers values (1, 'Test Publisher');
                insert into series values (1, 'Test Series');
                """
            )

    def _add_book(
        self,
        *,
        book_id: int = 1,
        title: str = "Test Book",
        path: str = "Test Author/Test Book (1)",
        cover: bytes | None = b"cover-one",
    ) -> None:
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute(
                "insert into books values (?, ?, ?, ?, ?, ?)",
                (book_id, title, "9780000000001", "2020-05-06 00:00:00+00:00", path, int(cover is not None)),
            )
            connection.execute("insert into books_authors_link values (?, ?, 1)", (book_id, book_id))
            connection.execute("insert into books_tags_link values (?, ?, 1)", (book_id, book_id))
            connection.execute("insert into books_languages_link values (?, ?, 1, 0)", (book_id, book_id))
            connection.execute("insert into books_publishers_link values (?, ?, 1)", (book_id, book_id))
            connection.execute("insert into books_series_link values (?, ?, 1)", (book_id, book_id))
            connection.execute("insert into identifiers values (?, ?, 'doi', ?)", (book_id, book_id, f"10.1000/{book_id}"))
        if cover is not None:
            book_dir = self.library.joinpath(*path.split("/"))
            book_dir.mkdir(parents=True)
            (book_dir / "cover.jpg").write_bytes(cover)
            (book_dir / f"book-{book_id}.epub").write_bytes(b"ebook-must-not-be-copied")

    def _arguments(self, *extra: str) -> list[str]:
        return [
            "--project",
            str(self.project),
            "import-calibre",
            "--library",
            str(self.library),
            "--source-key",
            "gis",
            "--collection-name",
            "Geography readings",
            "--collection-ref",
            "geography",
            "--collection-en",
            "Geography readings",
            "--profiles",
            "unaltreselfie,unaltreprojecte",
            "--rating",
            "4.5",
            *extra,
        ]

    def test_imports_are_serialized_per_project(self) -> None:
        first_entered = threading.Event()
        release_first = threading.Event()
        entered = 0
        failures: list[BaseException] = []

        def locked_import(*args, **kwargs):
            nonlocal entered
            entered += 1
            if entered == 1:
                first_entered.set()
                release_first.wait(timeout=2)
            return {"ok": True}

        def run_import() -> None:
            try:
                calibre_import.import_calibre(
                    self.project,
                    library=self.library,
                    source_key="gis",
                    collection_name="Geography readings",
                    profiles=["unaltremanual"],
                )
            except BaseException as exc:
                failures.append(exc)

        with patch.object(calibre_import, "_import_calibre_locked", side_effect=locked_import):
            first = threading.Thread(target=run_import)
            second = threading.Thread(target=run_import)
            first.start()
            self.assertTrue(first_entered.wait(timeout=1))
            second.start()
            time.sleep(0.1)
            self.assertEqual(entered, 1)
            release_first.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(entered, 2)

    def test_dry_run_reports_plan_without_mutating_project(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            returncode = cli.main(self._arguments())

        self.assertEqual(returncode, 0)
        self.assertIn("Books to write in this run: 1", output.getvalue())
        self.assertIn("Mode: dry-run", output.getvalue())
        self.assertEqual([path.name for path in self.project.iterdir()], ["_config.yml"])

    def test_write_preserves_metadata_and_copies_only_cover(self) -> None:
        with redirect_stdout(io.StringIO()):
            returncode = cli.main(self._arguments("--write"))

        self.assertEqual(returncode, 0)
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        text = markdown.read_text(encoding="utf-8")
        self.assertIn('title: "Test Book"', text)
        self.assertIn('calibre_source: "gis"\ncalibre_id: 1', text)
        self.assertIn('collection_name: "Geography readings"', text)
        self.assertIn('author: "Test Author"', text)
        self.assertIn('publisher: "Test Publisher"', text)
        self.assertIn('series: "Test Series"', text)
        self.assertIn('isbn: "9780000000001"', text)
        self.assertIn('doi: "10.1000/1"', text)
        self.assertIn("rating: 4.5", text)
        self.assertIn('book_language: "eng"', text)
        self.assertNotIn("Imported from Calibre", text)
        self.assertIn('cover: "/assets/img/books/calibre-gis-1-test-book.jpg"', text)
        self.assertEqual(
            (self.project / "assets/img/books/calibre-gis-1-test-book.jpg").read_bytes(),
            b"cover-one",
        )
        self.assertEqual(list(self.project.rglob("*.epub")), [])

    def test_rejects_absolute_traversing_and_malformed_book_paths(self) -> None:
        for path in ["/outside/book", "../outside", "Author//Book", r"C:\outside\book"]:
            with self.subTest(path=path):
                with sqlite3.connect(self.library / "metadata.db") as connection:
                    connection.execute("update books set path = ? where id = 1", (path,))
                with self.assertRaisesRegex(ValueError, "books.path"):
                    cli.main(self._arguments("--write"))
                self.assertEqual([path.name for path in self.project.iterdir()], ["_config.yml"])

    def test_rejects_cover_source_symlink(self) -> None:
        outside = self.root / "outside-book"
        outside.mkdir()
        (outside / "cover.jpg").write_bytes(b"outside")
        author_dir = self.library / "Linked Author"
        author_dir.mkdir()
        (author_dir / "Linked Book").symlink_to(outside, target_is_directory=True)
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update books set path = 'Linked Author/Linked Book' where id = 1")

        with self.assertRaisesRegex(RuntimeError, "source symlink"):
            cli.main(self._arguments("--write"))

        self.assertEqual([path.name for path in self.project.iterdir()], ["_config.yml"])
        self.assertEqual((outside / "cover.jpg").read_bytes(), b"outside")

    def test_rejects_symlinked_library_root(self) -> None:
        linked_library = self.root / "linked-library"
        linked_library.symlink_to(self.library, target_is_directory=True)
        arguments = self._arguments("--write")
        arguments[arguments.index(str(self.library))] = str(linked_library)

        with self.assertRaisesRegex(RuntimeError, "must not traverse symlinks"):
            cli.main(arguments)

        self.assertEqual([path.name for path in self.project.iterdir()], ["_config.yml"])

    def test_unrelated_markdown_collision_is_not_overwritten(self) -> None:
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        markdown.parent.mkdir()
        markdown.write_text("---\ntitle: Unrelated\n---\nKeep me.\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "preflight failed"):
            cli.main(self._arguments("--refresh-existing", "--write"))

        self.assertEqual(markdown.read_text(encoding="utf-8"), "---\ntitle: Unrelated\n---\nKeep me.\n")
        self.assertFalse((self.project / "assets").exists())

    def test_cover_collision_preflights_every_output_before_write(self) -> None:
        self._add_book(book_id=2, title="Zulu Book", path="Test Author/Zulu Book (2)", cover=b"cover-two")
        collision = self.project / "assets/img/books/calibre-gis-2-zulu-book.jpg"
        collision.parent.mkdir(parents=True)
        collision.write_bytes(b"unrelated-cover")

        with self.assertRaisesRegex(RuntimeError, "unrelated cover destination"):
            cli.main(self._arguments("--write"))

        self.assertEqual(collision.read_bytes(), b"unrelated-cover")
        self.assertFalse((self.project / "_books").exists())
        self.assertFalse((self.project / "assets/img/books/calibre-gis-1-test-book.jpg").exists())

    def test_refresh_requires_and_accepts_exact_import_ownership(self) -> None:
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update publishers set name = 'Updated Publisher' where id = 1")

        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertIn('publisher: "Updated Publisher"', markdown.read_text(encoding="utf-8"))

        unrelated = markdown.read_text(encoding="utf-8").replace('calibre_source: "gis"', 'calibre_source: "other"')
        markdown.write_text(unrelated, encoding="utf-8")
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update publishers set name = 'Blocked Publisher' where id = 1")

        with self.assertRaisesRegex(RuntimeError, "preflight failed"):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertEqual(markdown.read_text(encoding="utf-8"), unrelated)

    def test_refresh_recognizes_nested_markdown(self) -> None:
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        original = self.project / "_books/calibre-gis-1-test-book.md"
        nested = self.project / "_books/nested/calibre-gis-1-test-book.markdown"
        nested.parent.mkdir()
        nested.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        original.unlink()
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update publishers set name = 'Nested Publisher' where id = 1")

        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--refresh-existing", "--write"))

        self.assertIn('publisher: "Nested Publisher"', nested.read_text(encoding="utf-8"))
        self.assertFalse(original.exists())

    def test_refresh_preserves_body_and_rejects_changed_front_matter_or_cover(self) -> None:
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        markdown.write_text(markdown.read_text(encoding="utf-8") + "My reviewed notes.\n", encoding="utf-8")
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update publishers set name = 'Body Publisher' where id = 1")

        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--refresh-existing", "--write"))
        refreshed = markdown.read_text(encoding="utf-8")
        self.assertIn('publisher: "Body Publisher"', refreshed)
        self.assertTrue(refreshed.endswith("My reviewed notes.\n"))

        changed_metadata = refreshed.replace('status: "queued"', 'status: "finished"')
        markdown.write_text(changed_metadata, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "metadata changed"):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertEqual(markdown.read_text(encoding="utf-8"), changed_metadata)

        markdown.write_text(refreshed, encoding="utf-8")
        cover = self.project / "assets/img/books/calibre-gis-1-test-book.jpg"
        cover.write_bytes(b"author-edited-cover")
        with self.assertRaisesRegex(RuntimeError, "cover was edited"):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertEqual(cover.read_bytes(), b"author-edited-cover")

    def test_refresh_preserves_missing_source_cover_and_cover_mode(self) -> None:
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        cover = self.project / "assets/img/books/calibre-gis-1-test-book.jpg"

        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update books set has_cover = 0 where id = 1")
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertIn('cover: "/assets/img/books/calibre-gis-1-test-book.jpg"', markdown.read_text(encoding="utf-8"))
        self.assertEqual(cover.read_bytes(), b"cover-one")

        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update books set has_cover = 1 where id = 1")
        source_cover = self.library / "Test Author/Test Book (1)/cover.jpg"
        source_cover.write_bytes(b"updated-cover")
        cover.chmod(0o600)
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--refresh-existing", "--write"))
        self.assertEqual(cover.read_bytes(), b"updated-cover")
        self.assertEqual(stat.S_IMODE(cover.stat().st_mode), 0o600)

    def test_refresh_limit_counts_only_new_books(self) -> None:
        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        self._add_book(book_id=2, title="Alpha Book", path="Test Author/Alpha Book (2)")
        self._add_book(book_id=3, title="Zulu Book", path="Test Author/Zulu Book (3)")

        output = io.StringIO()
        with redirect_stdout(output):
            cli.main(self._arguments("--refresh-existing", "--limit", "1", "--write"))

        self.assertIn("Books selected from library: 2", output.getvalue())
        self.assertTrue((self.project / "_books/calibre-gis-2-alpha-book.md").exists())
        self.assertFalse((self.project / "_books/calibre-gis-3-zulu-book.md").exists())

    def test_refresh_preserves_fallback_date_for_undated_book(self) -> None:
        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update books set pubdate = null where id = 1")
        with patch.object(calibre_import, "date") as date_type:
            date_type.today.return_value = calendar_date(2026, 1, 2)
            with redirect_stdout(io.StringIO()):
                cli.main(self._arguments("--write"))

        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update publishers set name = 'Later Publisher' where id = 1")
        with patch.object(calibre_import, "date") as date_type:
            date_type.today.return_value = calendar_date(2026, 8, 31)
            with redirect_stdout(io.StringIO()):
                cli.main(self._arguments("--refresh-existing", "--write"))

        markdown = (self.project / "_books/calibre-gis-1-test-book.md").read_text(encoding="utf-8")
        self.assertIn("date: 2026-01-02", markdown)

    def test_rejects_non_site_destination_and_unsafe_metadata(self) -> None:
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        arguments = self._arguments("--write")
        arguments[1] = str(unrelated)
        with self.assertRaisesRegex(RuntimeError, "unaltraweb consumer site"):
            cli.main(arguments)
        self.assertEqual(list(unrelated.iterdir()), [])

        with sqlite3.connect(self.library / "metadata.db") as connection:
            connection.execute("update books set title = '<img src=x onerror=alert(1)>' where id = 1")
        with self.assertRaisesRegex(ValueError, "unsafe markup"):
            cli.main(self._arguments("--write"))
        self.assertFalse((self.project / "_books").exists())

    def test_rejects_unbounded_cover_batch(self) -> None:
        self._add_book(book_id=2, title="Second Book", path="Test Author/Second Book (2)", cover=b"cover-two")

        with patch.object(calibre_import, "MAX_IMPORT_COVER_BYTES", 10):
            with self.assertRaisesRegex(RuntimeError, "import limit"):
                cli.main(self._arguments("--write"))

        self.assertFalse((self.project / "_books").exists())

    def test_limit_bounds_metadata_loading_and_selected_book_count(self) -> None:
        self._add_book(book_id=2, title="Zulu Book", path="../unsafe", cover=None)

        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--limit", "1", "--write"))
        self.assertTrue((self.project / "_books/calibre-gis-1-test-book.md").exists())

        (self.project / "_books/calibre-gis-1-test-book.md").unlink()
        with patch.object(calibre_import, "MAX_IMPORT_BOOKS", 1):
            with self.assertRaisesRegex(RuntimeError, "safe limit"):
                cli.main(self._arguments("--write"))

    def test_rejects_unbounded_related_metadata(self) -> None:
        with patch.object(calibre_import, "MAX_RELATED_RECORDS", 0):
            with self.assertRaisesRegex(RuntimeError, "record limit"):
                cli.main(self._arguments("--write"))

    def test_commit_failure_rolls_back_completed_markdown(self) -> None:
        self._add_book(book_id=2, title="Second Book", path="Test Author/Second Book (2)", cover=b"cover-two")
        original_write = calibre_import.site_tools.site_source_write
        real_writes = 0

        def fail_second_write(*args, **kwargs):
            nonlocal real_writes
            if not kwargs.get("dry_run", True):
                real_writes += 1
                if real_writes == 2:
                    raise RuntimeError("simulated commit race")
            return original_write(*args, **kwargs)

        with patch.object(calibre_import.site_tools, "site_source_write", side_effect=fail_second_write):
            with self.assertRaisesRegex(RuntimeError, "All completed writes were rolled back"):
                cli.main(self._arguments("--write"))

        self.assertEqual(list((self.project / "_books").rglob("*.md")), [])
        self.assertFalse((self.project / "assets").exists())

    def test_keyboard_interrupt_rolls_back_completed_markdown(self) -> None:
        self._add_book(book_id=2, title="Second Book", path="Test Author/Second Book (2)", cover=b"cover-two")
        original_write = calibre_import.site_tools.site_source_write
        real_writes = 0

        def interrupt_second_write(*args, **kwargs):
            nonlocal real_writes
            if not kwargs.get("dry_run", True):
                real_writes += 1
                if real_writes == 2:
                    raise KeyboardInterrupt()
            return original_write(*args, **kwargs)

        with patch.object(calibre_import.site_tools, "site_source_write", side_effect=interrupt_second_write):
            with self.assertRaises(KeyboardInterrupt):
                cli.main(self._arguments("--write"))

        self.assertEqual(list((self.project / "_books").rglob("*.md")), [])
        self.assertFalse((self.project / "assets").exists())

    def test_post_commit_markdown_failure_rolls_back_installed_file(self) -> None:
        original_write = calibre_import.site_tools.site_source_write

        def fail_after_commit(*args, **kwargs):
            result = original_write(*args, **kwargs)
            if not kwargs.get("dry_run", True):
                raise RuntimeError("post-commit Markdown failure")
            return result

        with patch.object(calibre_import.site_tools, "site_source_write", side_effect=fail_after_commit):
            with self.assertRaisesRegex(RuntimeError, "post-commit Markdown failure"):
                cli.main(self._arguments("--write"))

        self.assertEqual(list((self.project / "_books").rglob("*.md")), [])
        self.assertFalse((self.project / "assets").exists())

    def test_post_commit_cover_failure_rolls_back_all_installed_files(self) -> None:
        original_write = calibre_import._atomic_cover_write

        def fail_after_commit(*args, **kwargs):
            original_write(*args, **kwargs)
            raise RuntimeError("post-commit cover failure")

        with patch.object(calibre_import, "_atomic_cover_write", side_effect=fail_after_commit):
            with self.assertRaisesRegex(RuntimeError, "post-commit cover failure"):
                cli.main(self._arguments("--write"))

        self.assertEqual(list((self.project / "_books").rglob("*.md")), [])
        self.assertFalse((self.project / "assets/img/books/calibre-gis-1-test-book.jpg").exists())

    def test_cover_commit_failure_rolls_back_all_outputs(self) -> None:
        self._add_book(book_id=2, title="Second Book", path="Test Author/Second Book (2)", cover=b"cover-two")
        original_write = calibre_import._atomic_cover_write
        cover_writes = 0

        def fail_second_cover(project, write):
            nonlocal cover_writes
            cover_writes += 1
            if cover_writes == 2:
                raise RuntimeError("simulated cover race")
            return original_write(project, write)

        with patch.object(calibre_import, "_atomic_cover_write", side_effect=fail_second_cover):
            with self.assertRaisesRegex(RuntimeError, "All completed writes were rolled back"):
                cli.main(self._arguments("--write"))

        self.assertEqual(list((self.project / "_books").rglob("*.md")), [])
        self.assertEqual(list((self.project / "assets").rglob("*.jpg")), [])

    def test_cover_write_rolls_back_directory_fsync_failures(self) -> None:
        relative = Path("assets/img/books/fsync.jpg")
        original_fsync = calibre_import.os.fsync

        def fail_directory_fsync(file_descriptor):
            if stat.S_ISDIR(calibre_import.os.fstat(file_descriptor).st_mode):
                raise OSError("simulated directory fsync failure")
            return original_fsync(file_descriptor)

        with patch.object(calibre_import.os, "fsync", side_effect=fail_directory_fsync):
            with self.assertRaisesRegex(OSError, "simulated directory fsync failure"):
                calibre_import._atomic_cover_write(
                    self.project,
                    calibre_import.CoverWrite(relative, b"new-cover", None, None),
                )
        self.assertFalse((self.project / relative).exists())

        target = self.project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"old-cover")
        with patch.object(calibre_import.os, "fsync", side_effect=fail_directory_fsync):
            with self.assertRaisesRegex(OSError, "simulated directory fsync failure"):
                calibre_import._atomic_cover_write(
                    self.project,
                    calibre_import.CoverWrite(relative, b"new-cover", calibre_import._sha256(b"old-cover"), b"old-cover"),
                )
        self.assertEqual(target.read_bytes(), b"old-cover")

    def test_defaults_to_site_language_and_rejects_disabled_language(self) -> None:
        (self.project / "_config.yml").write_text(
            "theme: unaltraweb\ndefault_lang: ca\nlanguages: [ca]\nunaltraweb:\n  site_profile: unaltremanual\n",
            encoding="utf-8",
        )

        with redirect_stdout(io.StringIO()):
            cli.main(self._arguments("--write"))
        markdown = self.project / "_books/calibre-gis-1-test-book.md"
        self.assertIn('lang: "ca"', markdown.read_text(encoding="utf-8"))
        self.assertIn("permalink: /ca/readings/", markdown.read_text(encoding="utf-8"))

        with self.assertRaisesRegex(ValueError, "not enabled"):
            cli.main(self._arguments("--lang", "en"))

    def test_rejects_unsafe_language_and_negative_limit(self) -> None:
        with self.assertRaises(SystemExit):
            cli.main(self._arguments("--lang", "en\npermalink: /outside/"))
        with self.assertRaises(SystemExit):
            cli.main(self._arguments("--limit", "-1"))
        with self.assertRaises(SystemExit):
            cli.main(self._arguments("--rating", "NaN"))
        with self.assertRaises(SystemExit):
            cli.main(self._arguments("--profiles", "unknown"))
        unsafe_key = self._arguments()
        unsafe_key[unsafe_key.index("gis")] = "GIS"
        with self.assertRaises(SystemExit):
            cli.main(unsafe_key)

        self.assertEqual([path.name for path in self.project.iterdir()], ["_config.yml"])


if __name__ == "__main__":
    unittest.main()
