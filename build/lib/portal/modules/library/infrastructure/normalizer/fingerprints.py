"""Content fingerprints (master prompt 7.1).

Visible-text fingerprint canonicalization — documented contract:
- visible text nodes are concatenated in document order;
- block-level boundaries contribute a single "\\n" separator;
- inside a text node, runs of whitespace collapse to one space
  (this normalizes only technical line-break representation);
- letters, punctuation, digits and words are never altered.

Any change to this contract bumps FINGERPRINT_VERSION.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from lxml import etree

from portal.modules.library.domain.normalization import TextFingerprints

FINGERPRINT_VERSION = 1

_WHITESPACE_RUN = re.compile(r"\s+")

# Elements whose text is body text (FB2 and XHTML share most of these).
_BLOCK_TAGS = {
    "section",
    "p",
    "poem",
    "stanza",
    "v",
    "subtitle",
    "epigraph",
    "cite",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "blockquote",
    "td",
    "th",
    "figcaption",
    "title",
    "body",
}
_SKIP_TAGS = {"style", "script", "head", "binary"}  # not visible text (binary = base64 resource)


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return etree.QName(tag).localname if tag.startswith("{") else tag


def visible_text(root: etree._Element) -> str:
    """Canonical visible text of a document tree."""
    chunks: list[str] = []

    def walk(element: etree._Element) -> None:
        tag = _local(element.tag)
        if tag in _SKIP_TAGS:
            return
        if element.text:
            text = _WHITESPACE_RUN.sub(" ", element.text).strip()
            if text:
                chunks.append(text)
        for child in element:
            child_tag = _local(child.tag)
            if child_tag in _BLOCK_TAGS and chunks:
                chunks.append("\n")
            walk(child)
            if child.tail:
                tail = _WHITESPACE_RUN.sub(" ", child.tail).strip()
                if tail:
                    chunks.append(tail)

    walk(root)
    return "".join(chunks)


def structure_fingerprint(root: etree._Element) -> str:
    """Hash of the element tag/depth skeleton (ignores attributes and text)."""
    parts: list[str] = []

    def walk(element: etree._Element, depth: int) -> None:
        parts.append(f"{depth}:{_local(element.tag)}")
        for index, child in enumerate(element):
            parts.append(f"i{index}")
            walk(child, depth + 1)

    walk(root, 0)
    return _sha("\n".join(parts))


def image_manifest_fingerprint(images: list[dict[str, Any]]) -> str:
    """Hash over sorted (href, sha256, size) of image resources."""
    lines = sorted(
        f"{img.get('href', '')}|{img.get('sha256', '')}|{img.get('size', 0)}" for img in images
    )
    return _sha("\n".join(lines))


def chapter_fingerprints(chapters: list[str]) -> list[str]:
    return [_sha(text) for text in chapters]


def compute_fingerprints(
    root: etree._Element,
    chapters: list[str],
    images: list[dict[str, Any]],
) -> TextFingerprints:
    return TextFingerprints(
        visible_text=_sha(visible_text(root)),
        structure=structure_fingerprint(root),
        images=image_manifest_fingerprint(images),
        chapters=chapter_fingerprints(chapters),
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
