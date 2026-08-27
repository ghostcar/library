"""Tests for expand_book_archive."""

from __future__ import annotations

import io
import zipfile

import pytest

from portal.modules.library.application.import_service import expand_book_archive

FB2_BYTES = b"""\
<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body><section><p>Test book.</p></section></body>
</FictionBook>"""


def _make_fb2(name: str = "test.fb2") -> tuple[str, bytes]:
    return name, FB2_BYTES


def _make_epub(name: str = "test.epub") -> tuple[str, bytes]:
    """Minimal ZIP with mimetype entry — enough to be detected as EPUB."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container/>")
    return name, buf.getvalue()


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestExpandBookArchive:
    def test_not_zip_returns_none(self) -> None:
        assert expand_book_archive("test.bin", b"not a zip") is None

    def test_epub_returns_none(self) -> None:
        name, content = _make_epub()
        assert expand_book_archive(name, content) is None

    def test_zip_with_fb2_files(self) -> None:
        content = _make_zip(
            {
                "book1.fb2": FB2_BYTES,
                "book2.fb2": FB2_BYTES.replace(b"Test book", b"Second book"),
            }
        )
        result = expand_book_archive("archive.zip", content)
        assert result is not None
        assert len(result) == 2
        assert result[0][0] == "book1.fb2"
        assert result[1][0] == "book2.fb2"

    def test_zip_with_mixed_fb2_epub(self) -> None:
        epub_name, epub_content = _make_epub("inside.epub")
        content = _make_zip(
            {
                "novel.fb2": FB2_BYTES,
                epub_name: epub_content,
            }
        )
        result = expand_book_archive("mixed.zip", content)
        assert result is not None
        assert len(result) == 2
        names = {r[0] for r in result}
        assert "novel.fb2" in names
        assert "inside.epub" in names

    def test_zip_with_no_books_raises(self) -> None:
        content = _make_zip({"readme.txt": b"hello", "image.png": b"\x89PNG"})
        with pytest.raises(ValueError, match="no FB2/EPUB"):
            expand_book_archive("no-books.zip", content)

    def test_skips_hidden_and_macosx(self) -> None:
        content = _make_zip(
            {
                ".DS_Store": b"\x00",
                "__MACOSX/._file": b"\x00",
                "book.fb2": FB2_BYTES,
            }
        )
        result = expand_book_archive("archive.zip", content)
        assert result is not None
        assert len(result) == 1
        assert result[0][0] == "book.fb2"

    def test_skips_directories(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("subdir/", "")
            zf.writestr("subdir/book.fb2", FB2_BYTES)
        result = expand_book_archive("archive.zip", buf.getvalue())
        assert result is not None
        assert len(result) == 1

    def test_zip_bomb_entry_count(self) -> None:
        entries = {f"book{i}.fb2": FB2_BYTES for i in range(101)}
        content = _make_zip(entries)
        with pytest.raises(ValueError, match="more than 100"):
            expand_book_archive("big.zip", content, max_entries=100)

    def test_zip_bomb_entry_size(self) -> None:
        big = b"\x00" * 101
        content = _make_zip({"huge.fb2": big})
        with pytest.raises(ValueError, match="bytes"):
            expand_book_archive("bomb.zip", content, max_entry_bytes=100)

    def test_zip_bomb_total_size(self) -> None:
        entries = {f"book{i}.fb2": b"\x00" * 50 for i in range(5)}
        content = _make_zip(entries)
        with pytest.raises(ValueError, match="total uncompressed"):
            expand_book_archive("bomb.zip", content, max_total_bytes=100)

    def test_nested_path_uses_basename_only(self) -> None:
        content = _make_zip({"deep/nested/path/book.fb2": FB2_BYTES})
        result = expand_book_archive("archive.zip", content)
        assert result is not None
        assert result[0][0] == "book.fb2"

    def test_corrupt_zip_returns_none(self) -> None:
        # PK header but not a valid zip → is_zipfile returns False → None
        result = expand_book_archive("corrupt.zip", b"PK\x03\x04\x00\x00corrupt\x00\x00")
        assert result is None
