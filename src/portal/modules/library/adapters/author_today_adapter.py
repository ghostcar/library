"""Public Author.Today author-page metadata adapter.

Only public work-list metadata is read.  No authentication, private API,
chapter content, images, or acquisition endpoints are used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from lxml import etree, html

from portal.modules.library.adapters.sources import (
    FetchResult,
    SourceAdapterError,
    SourceCapabilities,
    SourceEntry,
)

PARSER_VERSION = "author-today-public-html-v2"
_MAX_PAGE_BYTES = 5 * 1024 * 1024
_MAX_TOTAL_BYTES = 25 * 1024 * 1024
_MAX_PAGES = 50
_ALLOWED_HOSTS = {"author.today", "www.author.today"}


class AuthorTodayParseError(SourceAdapterError):
    pass


def _elements(node: html.HtmlElement, expression: str) -> list[html.HtmlElement]:
    return [item for item in node.xpath(expression) if isinstance(item, html.HtmlElement)]


def normalize_author_works_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        raise AuthorTodayParseError("Author.Today URL must use https://author.today")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() != "u":
        raise AuthorTodayParseError("expected a public Author.Today author profile URL")
    slug = parts[1]
    if not slug or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for char in slug
    ):
        raise AuthorTodayParseError("invalid Author.Today author slug")
    return f"https://author.today/u/{slug}/works"


def _author_name(root: html.HtmlElement) -> str | None:
    json_values = cast("list[str]", root.xpath("//script[@type='application/ld+json']/text()"))
    for raw in json_values:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("@type") == "Person":
            name = str(value.get("name") or "").strip()
            if name:
                return name
    names = cast("list[str]", root.xpath("//div[contains(@class, 'profile-name')]//h1//a/text()"))
    return " ".join(names[0].split()) if names else None


def _page_count(root: html.HtmlElement) -> int:
    hrefs = cast("list[str]", root.xpath("//a[contains(@href, '/works?page=')]/@href"))
    pages = [1]
    for href in hrefs:
        parsed = urlparse(href)
        values = parse_qs(parsed.query).get("page", [])
        if len(values) != 1 or not values[0].isdigit():
            continue
        pages.append(int(values[0]))
    count = max(pages)
    if count > _MAX_PAGES:
        raise AuthorTodayParseError("Author.Today pagination exceeds page guard")
    return count


def parse_author_today_page(content: bytes) -> tuple[list[SourceEntry], int]:
    try:
        root = html.fromstring(content)
    except (etree.ParserError, ValueError) as exc:
        raise AuthorTodayParseError(f"invalid Author.Today HTML: {exc}") from exc

    rows = _elements(root, "//*[contains(concat(' ', normalize-space(@class), ' '), ' book-row ')]")
    if not rows:
        raise AuthorTodayParseError("Author.Today layout changed: no .book-row entries")
    author_name = _author_name(root)
    entries: list[SourceEntry] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        links = _elements(
            row,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' book-title ')]"
            "//a[starts-with(@href, '/work/') or starts-with(@href, '/audiobook/')]",
        )
        if not links:
            continue
        link = links[0]
        href = str(link.get("href") or "")
        path_parts = [part for part in urlparse(href).path.split("/") if part]
        if len(path_parts) < 2 or path_parts[0] not in {"work", "audiobook"}:
            continue
        publication_kind, work_id = path_parts[:2]
        title = " ".join(link.text_content().split())
        publication_key = (publication_kind, work_id)
        if not work_id.isdigit() or not title or publication_key in seen:
            continue
        seen.add(publication_key)
        update_nodes = _elements(
            row,
            ".//*[@data-time and starts-with(normalize-space(@data-hint), 'Обновление')]",
        )
        status_nodes = _elements(
            row,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' book-status-icon ')]",
        )
        status = ""
        if status_nodes:
            parent = status_nodes[0].getparent()
            if isinstance(parent, html.HtmlElement):
                status = " ".join(parent.text_content().split())
        series_nodes = _elements(row, ".//a[starts-with(@href, '/work/series/')]")
        updated_at = update_nodes[0].get("data-time") if update_nodes else None
        revision = updated_at or status or "published"
        entries.append(
            SourceEntry(
                external_id=f"author-today:{publication_kind}:{work_id}:revision:{revision}",
                title=title,
                author_name=author_name,
                url=urljoin("https://author.today", f"/{publication_kind}/{work_id}"),
                raw={
                    "work_id": work_id,
                    "publication_kind": publication_kind,
                    "updated_at": updated_at,
                    "status": status or None,
                    "series": (
                        " ".join(series_nodes[0].text_content().split()) if series_nodes else None
                    ),
                    "series_url": (
                        urljoin("https://author.today", str(series_nodes[0].get("href") or ""))
                        if series_nodes
                        else None
                    ),
                },
            )
        )
    if not entries:
        raise AuthorTodayParseError("Author.Today layout changed: no valid work metadata")
    return entries, _page_count(root)


def parse_author_today_works(content: bytes) -> list[SourceEntry]:
    """Parse one public works page; retained as the fixture-level parser API."""
    entries, _page_count_value = parse_author_today_page(content)
    return entries


@dataclass(slots=True)
class AuthorTodayAdapter:
    client: httpx.AsyncClient | None = None
    id: str = "author_today"
    parser_version: str = PARSER_VERSION
    capabilities: SourceCapabilities = field(
        default_factory=lambda: SourceCapabilities(
            author_updates=True,
            series_listing=True,
            work_status=True,
            metadata=True,
            acquisition=False,
            authentication="none",
        )
    )

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        target = normalize_author_works_url(url)
        headers = {"Accept": "text/html,application/xhtml+xml"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "ghostcar-library/0.1 (personal metadata monitor; contact: roman@gorbunovr.ru)"
                )
            },
        )
        try:
            response = await self._fetch_page(client, target, headers=headers)
            if response.status_code == 304:
                return FetchResult([], True, etag, last_modified)
            entries, page_count = parse_author_today_page(response.content)
            total_bytes = len(response.content)
            seen_publications = {
                (str(entry.raw.get("publication_kind")), str(entry.raw.get("work_id")))
                for entry in entries
            }
            for page in range(2, page_count + 1):
                page_response = await self._fetch_page(client, f"{target}?page={page}")
                total_bytes += len(page_response.content)
                if total_bytes > _MAX_TOTAL_BYTES:
                    raise AuthorTodayParseError("Author.Today pagination exceeds total size guard")
                page_entries, _ = parse_author_today_page(page_response.content)
                for entry in page_entries:
                    key = (
                        str(entry.raw.get("publication_kind")),
                        str(entry.raw.get("work_id")),
                    )
                    if key in seen_publications:
                        continue
                    seen_publications.add(key)
                    entries.append(entry)
            return FetchResult(
                entries,
                # A validator on page 1 cannot prove that later pages are unchanged.
                # Keep conditional requests only for genuinely single-page catalogs.
                etag=response.headers.get("ETag") if page_count == 1 else None,
                last_modified=(response.headers.get("Last-Modified") if page_count == 1 else None),
            )
        except httpx.HTTPError as exc:
            raise AuthorTodayParseError(f"Author.Today fetch failed: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    async def _fetch_page(
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = await client.get(url, headers=headers)
        if (response.url.host or "").lower() not in _ALLOWED_HOSTS:
            raise AuthorTodayParseError("Author.Today redirect left the allowed host")
        if response.status_code == 304:
            return response
        if response.status_code != 200:
            raise AuthorTodayParseError(f"Author.Today fetch returned {response.status_code}")
        if len(response.content) > _MAX_PAGE_BYTES:
            raise AuthorTodayParseError("Author.Today page exceeds size guard")
        return response
