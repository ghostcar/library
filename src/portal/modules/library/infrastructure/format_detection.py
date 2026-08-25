"""Book format detection by content, never by extension (master prompt 6.3)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum

_FB2_NAMESPACES = (
    b"http://www.gribuser.ru/xml/fictionbook/2.0",
    b"http://www.gribuser.ru/xml/fictionbook/1.0",
)
_ZIP_MAGIC = b"PK\x03\x04"
_XML_DECL = b"<?xml"
_EPUB_MIMETYPE = b"application/epub+zip"
_MAX_MIMETYPE_ENTRY = 1024  # bytes; a legit mimetype entry is tiny


class BookFormat(StrEnum):
    FB2 = "fb2"
    EPUB = "epub"


class UnknownFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FormatInfo:
    format: BookFormat


def detect_format(content: bytes) -> FormatInfo:
    if _looks_like_fb2(content):
        return FormatInfo(BookFormat.FB2)
    if _looks_like_epub(content):
        return FormatInfo(BookFormat.EPUB)
    msg = "file is neither FB2 nor EPUB (detected by content)"
    raise UnknownFormatError(msg)


def _looks_like_fb2(content: bytes) -> bool:
    head = content[:4096].lstrip()
    if not head.startswith(_XML_DECL) and not head.startswith(b"<"):
        return False
    return any(ns in content[:8192] for ns in _FB2_NAMESPACES)


def _looks_like_epub(content: bytes) -> bool:
    if not content.startswith(_ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            # zip bomb guard for detection: only stat entries, read one tiny file
            if len(archive.infolist()) > 10_000:
                return False
            if "mimetype" not in archive.namelist():
                return False
            info = archive.getinfo("mimetype")
            if info.file_size > _MAX_MIMETYPE_ENTRY:
                return False
            return archive.read("mimetype").strip() == _EPUB_MIMETYPE
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError):
        return False
