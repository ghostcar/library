"""Extract likely continuation links from already-local FB2 files.

No URLs are fetched here.  The parser is deliberately independent from the
normalizer so analysis never changes an original or derived book file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from lxml import etree

from portal.modules.library.infrastructure.normalizer.fb2 import parse_fb2

_XLINK = "http://www.w3.org/1999/xlink"
_MAX_CONTEXT = 500
_CONTINUATION = re.compile(
    r"\b(продолжени[ея]|следующ(?:ая|ую|ее|ий)|нов(?:ая|ую|ое) книг|"  # noqa: RUF001
    r"следующ(?:ая|ую) част|цикл[аеуы]|читать далее)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ExtractedContinuationLink:
    url: str
    context: str


def _href(element: etree._Element) -> str | None:
    return element.get(f"{{{_XLINK}}}href") or element.get("href")


def _context(element: etree._Element) -> str:
    parent = element.getparent()
    node = parent if parent is not None else element
    return " ".join(" ".join(str(part) for part in node.itertext()).split())[:_MAX_CONTEXT]


def _nearby_link_text(element: etree._Element) -> str:
    """Text directly adjacent to one link, not the whole paragraph's links."""
    previous = element.getprevious()
    parent = element.getparent()
    before = parent.text if previous is None and parent is not None else None
    if previous is not None:
        before = previous.tail
    return " ".join(part for part in (before, element.text, element.tail) if part)


def extract_continuation_links(content: bytes) -> list[ExtractedContinuationLink]:
    """Return unique public links whose nearby FB2 text signals a continuation."""
    root = parse_fb2(content)
    found: list[ExtractedContinuationLink] = []
    seen: set[str] = set()
    for element in root.iter():
        href = (_href(element) or "").strip()
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or href in seen:
            continue
        if not _CONTINUATION.search(_nearby_link_text(element)):
            continue
        context = _context(element)
        seen.add(href)
        found.append(ExtractedContinuationLink(url=href, context=context))
    return found
