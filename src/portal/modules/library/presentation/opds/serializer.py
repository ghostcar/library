"""OPDS 1.2 serializer (master prompt 10.1).

Pure functions: catalog data (dicts) -> Atom XML. The application layer
never touches XML, so an OPDS 2.0 serializer can be added later without
touching domain/application code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from lxml import etree

_ATOM = "http://www.w3.org/2005/Atom"
_OPDS = "http://opds-spec.org/2010/catalog"
_OPDS_ROOT = f"{{{_ATOM}}}"

NAV_TYPE = "application/atom+xml;profile=opds-catalog;kind=navigation"
ACQ_TYPE = "application/atom+xml;profile=opds-catalog;kind=acquisition"
OPENSEARCH_TYPE = "application/opensearchdescription+xml"

_FORMAT_MEDIA_TYPES = {
    "fb2": "application/fb2+xml",
    "epub": "application/epub+zip",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sub(
    parent: etree._Element,
    tag: str,
    text: str | None = None,
    **attrs: str,
) -> etree._Element:
    attr_map: dict[str, str] = dict(attrs)
    element = etree.SubElement(parent, tag, attr_map)
    if text is not None:
        element.text = text
    return element


def navigation_feed(
    *,
    feed_id: str,
    title: str,
    self_href: str,
    entries: list[dict[str, Any]],
    search: bool = False,
) -> bytes:
    """Navigation feed: links to other feeds, no acquisition entries."""
    root = etree.Element(_OPDS_ROOT + "feed", nsmap={None: _ATOM, "opds": _OPDS})  # type: ignore[dict-item]  # lxml default ns needs None)
    _sub(root, "id", feed_id)
    _sub(root, "title", title)
    _sub(root, "updated", _now())
    _sub(
        root,
        "link",
        rel="self",
        href=self_href,
        type=NAV_TYPE,
    )
    if search:
        _sub(
            root,
            "link",
            rel="search",
            type=OPENSEARCH_TYPE,
            href="/opds/search.xml",
        )
    for entry in entries:
        entry_el = _sub(root, "entry")
        _sub(entry_el, "id", str(entry["id"]))
        _sub(entry_el, "title", entry["title"])
        _sub(entry_el, "updated", entry.get("updated") or _now())
        if entry.get("content"):
            content = _sub(entry_el, "content", entry["content"])
            content.set("type", "text")
        _sub(
            entry_el,
            "link",
            rel="subsection",
            href=entry["href"],
            type=entry.get("entry_type", NAV_TYPE),
        )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def acquisition_feed(
    *,
    feed_id: str,
    title: str,
    self_href: str,
    entries: list[dict[str, Any]],
    links: list[dict[str, str]] | None = None,
) -> bytes:
    """Acquisition feed: book entries with download links."""
    root = etree.Element(_OPDS_ROOT + "feed", nsmap={None: _ATOM, "opds": _OPDS})  # type: ignore[dict-item]  # lxml default ns needs None)
    _sub(root, "id", feed_id)
    _sub(root, "title", title)
    _sub(root, "updated", _now())
    _sub(root, "link", rel="self", href=self_href, type=ACQ_TYPE)
    for link in links or []:
        _sub(root, "link", **link)

    for entry in entries:
        entry_el = _sub(root, "entry")
        _sub(entry_el, "id", f"urn:uuid:{entry['work_id']}")
        _sub(entry_el, "title", entry["title"])
        _sub(entry_el, "updated", entry.get("updated") or _now())
        for author in entry.get("authors", []) or []:
            author_el = _sub(entry_el, "author")
            _sub(author_el, "name", author)
        if entry.get("series"):
            content = _sub(entry_el, "content", entry["series"])
            content.set("type", "text")
        for asset in entry.get("assets", []):
            media_type = _FORMAT_MEDIA_TYPES.get(asset["format"], "application/octet-stream")
            _sub(
                entry_el,
                "link",
                rel="http://opds-spec.org/acquisition",
                href=f"/opds/download/{asset['asset_id']}",
                type=media_type,
            )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def opensearch_description(base_path: str = "/opds") -> bytes:
    opensearch_ns = "http://a9.com/-/spec/opensearch/1.1/"
    root = etree.Element(
        "{%s}OpenSearchDescription" % opensearch_ns,  # noqa: UP031 - lxml tag format
        nsmap={None: opensearch_ns},  # type: ignore[dict-item]
    )
    _sub(root, "ShortName", "Library")
    _sub(root, "Description", "Поиск по личной библиотеке")
    _sub(
        root,
        "Url",
        type="application/atom+xml;profile=opds-catalog;kind=acquisition",
        template=f"{base_path}/search?q={{searchTerms}}",
    )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def new_feed_id(prefix: str) -> str:
    return f"urn:uuid:{UUID(int=0)}:{prefix}"
