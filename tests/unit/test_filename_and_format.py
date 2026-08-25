"""Unit tests: deterministic filename parser and content-based format detection."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from portal.modules.library.application.filename_parser import parse_filename
from portal.modules.library.infrastructure.format_detection import (
    BookFormat,
    UnknownFormatError,
    detect_format,
)


class TestParseFilename:
    def test_full_pattern_with_series_and_index(self) -> None:
        parsed = parse_filename("Джеймс Кори — Пространство 05.5 — Обретение Мидаса.fb2")
        assert parsed.author == "Джеймс Кори"
        assert parsed.series == "Пространство"
        assert parsed.series_index is not None
        assert str(parsed.series_index) == "05.5"
        assert parsed.title == "Обретение Мидаса"
        assert parsed.extension == "fb2"
        assert parsed.is_well_formed

    def test_range_index(self) -> None:
        parsed = parse_filename("Автор — Цикл 2-3 — Омнибус.epub")
        assert parsed.series == "Цикл"
        assert str(parsed.series_index) == "2-3"

    def test_hyphen_separator(self) -> None:
        parsed = parse_filename("Перумов - Хранитель Мечей 01 - Рождение Магии.fb2")
        assert parsed.author == "Перумов"
        assert parsed.series == "Хранитель Мечей"
        assert parsed.title == "Рождение Магии"

    def test_author_title_only(self) -> None:
        parsed = parse_filename("Джек Лондон — Белый Клык.epub")
        assert parsed.author == "Джек Лондон"
        assert parsed.series is None
        assert parsed.series_index is None
        assert parsed.title == "Белый Клык"

    def test_title_only(self) -> None:
        parsed = parse_filename("Какая-то книга.fb2")
        assert parsed.author is None
        assert parsed.title == "Какая-то книга"
        assert not parsed.is_well_formed

    def test_underscores_as_spaces(self) -> None:
        parsed = parse_filename("Автор_Name—Серия_02—Книга.fb2")
        assert parsed.author == "Автор Name"
        assert parsed.series == "Серия"

    def test_series_without_index(self) -> None:
        parsed = parse_filename("Автор — Цикл — Книга.fb2")
        assert parsed.series == "Цикл"
        assert parsed.series_index is None

    def test_no_extension(self) -> None:
        parsed = parse_filename("Просто название")
        assert parsed.title == "Просто название"
        assert parsed.extension is None


def _minimal_fb2() -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        "<description><title-info><book-title>Тест</book-title></title-info></description>"
        "<body><section><p>Текст.</p></section></body></FictionBook>"
    ).encode()


def _minimal_epub() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>")
        archive.writestr("content.opf", "<package/>")
    return buffer.getvalue()


class TestFormatDetection:
    def test_fb2_detected_by_namespace(self) -> None:
        info = detect_format(_minimal_fb2())
        assert info.format is BookFormat.FB2

    def test_epub_detected_by_mimetype(self) -> None:
        info = detect_format(_minimal_epub())
        assert info.format is BookFormat.EPUB

    def test_plain_text_rejected(self) -> None:
        with pytest.raises(UnknownFormatError):
            detect_format(b"just some text file pretending to be a book")

    def test_zip_without_epub_mimetype_rejected(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("random.txt", "hello")
        with pytest.raises(UnknownFormatError):
            detect_format(buffer.getvalue())

    def test_fake_extension_ignored(self) -> None:
        # content decides, not the name
        with pytest.raises(UnknownFormatError):
            detect_format(b"not a book at all .fb2 bytes")

    def test_epub_zip_bomb_guard(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            for i in range(20):
                archive.writestr(f"f{i}.txt", "x" * 10)
        info = detect_format(buffer.getvalue())
        assert info.format is BookFormat.EPUB
