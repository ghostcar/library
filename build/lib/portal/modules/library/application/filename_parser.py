"""Deterministic filename parsing (master prompt 8.1: deterministic first).

Recognized patterns (extension stripped, underscores may act as spaces):
  "Автор -- Серия 04 -- Название"  -> author, series, index, title
  "Автор -- Название"              -> author, title
  "Название"                       -> title only
Index may be "04", "0.5", "1.1", "12-13" (range), or absent.
Real separators are em/en dashes and hyphens surrounded by spaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from portal.modules.library.domain.value_objects import SeriesIndex

_DASH = "[\u2014\u2013-]"  # em dash, en dash, hyphen
_SEPARATOR = rf"\s+{_DASH}\s+"
_INDEX_IN_SERIES = re.compile(
    rf"^(?P<series>.+?)\s+(?P<index>\d+(?:[.,]\d+)?(?:{_DASH}\d+(?:[.,]\d+)?)?)$",
)
_EXTENSION = re.compile(r"\.(fb2|epub|zip)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedFilename:
    title: str
    author: str | None = None
    series: str | None = None
    series_index: SeriesIndex | None = None
    extension: str | None = None

    @property
    def is_well_formed(self) -> bool:
        """Enough evidence for deterministic auto-apply (author + title)."""
        return bool(self.author and self.title)


def parse_filename(filename: str) -> ParsedFilename:
    name = _EXTENSION.sub("", filename.strip()).strip()
    name = name.replace("_", " ")
    # em/en dashes without surrounding spaces act as separators too
    name = re.sub(r"([\u2014\u2013])", r" \1 ", name).strip()
    if not name:
        return ParsedFilename(title=filename, extension=_ext_of(filename))

    parts = re.split(_SEPARATOR, name)
    extension = _ext_of(filename)

    if len(parts) >= 3:
        author, series_part, title = parts[0], parts[1], _SEPARATOR.join(parts[2:])
        series, index = _split_series_index(series_part)
        return ParsedFilename(
            title=title.strip(),
            author=author.strip() or None,
            series=series,
            series_index=index,
            extension=extension,
        )

    if len(parts) == 2:
        author, title = parts
        return ParsedFilename(
            title=title.strip(),
            author=author.strip() or None,
            extension=extension,
        )

    return ParsedFilename(title=name.strip(), extension=extension)


def _split_series_index(series_part: str) -> tuple[str | None, SeriesIndex | None]:
    match = _INDEX_IN_SERIES.match(series_part.strip())
    if match is None:
        return (series_part.strip() or None, None)
    raw_index = match.group("index").replace(",", ".")
    return match.group("series").strip(), SeriesIndex.parse(raw_index)


def _ext_of(filename: str) -> str | None:
    match = _EXTENSION.search(filename)
    return match.group(1).lower() if match else None
