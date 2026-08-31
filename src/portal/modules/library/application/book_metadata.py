"""Safe, deterministic metadata extraction from locally supplied book files."""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from portal.modules.library.infrastructure.normalizer.fb2 import FB2ParseError, parse_fb2


@dataclass(frozen=True, slots=True)
class EmbeddedBookMetadata:
    title: str | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    series: str | None = None
    series_index_raw: str | None = None
    language: str | None = None

    @property
    def usable_for_catalog(self) -> bool:
        return bool(self.title and self.authors)

    def to_evidence(self) -> dict[str, object]:
        return {
            "title": self.title,
            "authors": list(self.authors),
            "series": self.series,
            "series_index_raw": self.series_index_raw,
            "language": self.language,
        }


def _local(element: etree._Element) -> str:
    return etree.QName(element.tag).localname if isinstance(element.tag, str) else ""


def _child(parent: etree._Element, name: str) -> etree._Element | None:
    return next((element for element in parent if _local(element) == name), None)


def _text(element: etree._Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join(str(part) for part in element.itertext()).strip()
    return value or None


def extract_fb2_metadata(content: bytes) -> EmbeddedBookMetadata:
    """Read only title-info; support FB2 1.0, 2.0 and namespace-less files."""
    try:
        root = parse_fb2(content)
    except FB2ParseError:
        return EmbeddedBookMetadata()
    description = next((element for element in root if _local(element) == "description"), None)
    title_info = _child(description, "title-info") if description is not None else None
    if title_info is None:
        return EmbeddedBookMetadata()
    authors: list[str] = []
    for author in (element for element in title_info if _local(element) == "author"):
        parts = ("first-name", "middle-name", "last-name", "nickname")
        name = " ".join(filter(None, (_text(_child(author, part)) for part in parts))).strip()
        if name and name.casefold() not in {item.casefold() for item in authors}:
            authors.append(name)
    sequence = _child(title_info, "sequence")
    return EmbeddedBookMetadata(
        title=_text(_child(title_info, "book-title")),
        authors=tuple(authors),
        series=(sequence.get("name") or "").strip() if sequence is not None else None,
        series_index_raw=(sequence.get("number") or "").strip() if sequence is not None else None,
        language=_text(_child(title_info, "lang")),
    )


def extract_embedded_metadata(content: bytes, format_name: str) -> EmbeddedBookMetadata:
    # EPUB package metadata is the next slice; FB2 is the recovery format at hand.
    return extract_fb2_metadata(content) if format_name == "fb2" else EmbeddedBookMetadata()
