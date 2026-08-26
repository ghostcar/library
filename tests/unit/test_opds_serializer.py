"""Unit tests: OPDS serializer (XML structure, namespaces, links)."""

from __future__ import annotations

from lxml import etree

from portal.modules.library.presentation.opds import serializer as ser

_ATOM = "http://www.w3.org/2005/Atom"


def _parse(xml: bytes) -> etree._Element:
    return etree.fromstring(xml)


class TestNavigationFeed:
    def test_structure_and_namespaces(self) -> None:
        xml = ser.navigation_feed(
            feed_id="urn:library:root",
            title="Моя библиотека",
            self_href="/opds",
            entries=[
                {
                    "id": "urn:library:nav:new",
                    "title": "Новые книги",
                    "href": "/opds/new",
                    "content": "5 книг",
                },
            ],
            search=True,
        )
        root = _parse(xml)
        assert root.tag == f"{{{_ATOM}}}feed"
        assert root.findtext(f"{{{_ATOM}}}title") == "Моя библиотека"
        entry = root.find(f"{{{_ATOM}}}entry")
        assert entry is not None
        assert entry.findtext(f"{{{_ATOM}}}title") == "Новые книги"
        link = entry.find(f"{{{_ATOM}}}link")
        assert link is not None
        assert link.get("href") == "/opds/new"
        assert "opds-catalog" in (link.get("type") or "")
        search_link = root.find(f"{{{_ATOM}}}link[@rel='search']")
        assert search_link is not None
        assert search_link.get("href") == "/opds/search.xml"


class TestAcquisitionFeed:
    def test_entries_with_authors_and_links(self) -> None:
        xml = ser.acquisition_feed(
            feed_id="urn:library:new",
            title="Новые книги",
            self_href="/opds/new",
            entries=[
                {
                    "work_id": "0f0e0d0c-1111-2222-3333-444455556666",
                    "title": "Книга",
                    "updated": "2026-08-26T00:00:00Z",
                    "authors": ["Автор"],
                    "series": "Цикл №2",
                    "assets": [
                        {"asset_id": "aaaa-1111", "format": "fb2"},
                        {"asset_id": "bbbb-2222", "format": "epub"},
                    ],
                },
            ],
        )
        root = _parse(xml)
        entry = root.find(f"{{{_ATOM}}}entry")
        assert entry is not None
        assert entry.findtext(f"{{{_ATOM}}}id") == "urn:uuid:0f0e0d0c-1111-2222-3333-444455556666"
        author = entry.find(f"{{{_ATOM}}}author/{{{_ATOM}}}name")
        assert author is not None and author.text == "Автор"
        links = entry.findall(f"{{{_ATOM}}}link")
        hrefs = [link.get("href") for link in links]
        assert "/opds/download/aaaa-1111" in hrefs
        types = [link.get("type") for link in links]
        assert "application/fb2+xml" in types
        assert "application/epub+zip" in types
        assert all("acquisition" in (link.get("rel") or "") for link in links)

    def test_cyrillic_titles_encoded_utf8(self) -> None:
        xml = ser.acquisition_feed(
            feed_id="x",
            title="Циклы",
            self_href="/opds/x",
            entries=[{"work_id": "1", "title": "Цветы для Элджернона", "assets": []}],
        )
        assert "Цветы для Элджернона".encode() in xml


class TestOpenSearch:
    def test_description_template(self) -> None:
        xml = ser.opensearch_description()
        root = _parse(xml)
        url = root.find("{http://a9.com/-/spec/opensearch/1.1/}Url")
        assert url is not None
        assert "{searchTerms}" in (url.get("template") or "")
