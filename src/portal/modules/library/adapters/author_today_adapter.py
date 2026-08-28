"""Public Author.Today author-page metadata adapter.

Only public work-list metadata is read.  No authentication, private API,
chapter content, images, or acquisition endpoints are used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import cast
from urllib.parse import urljoin, urlparse

import httpx
from lxml import etree, html

from portal.modules.library.adapters.sources import (
    FetchResult,
    SourceAdapterError,
    SourceCapabilities,
    SourceEntry,
)

PARSER_VERSION = "author-today-public-html-v1"
_MAX_PAGE_BYTES = 5 * 1024 * 1024
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


def parse_author_today_works(content: bytes) -> list[SourceEntry]:
    try:
        root = html.fromstring(content)
    except (etree.ParserError, ValueError) as exc:
        raise AuthorTodayParseError(f"invalid Author.Today HTML: {exc}") from exc

    rows = _elements(root, "//*[contains(concat(' ', normalize-space(@class), ' '), ' book-row ')]")
    if not rows:
        raise AuthorTodayParseError("Author.Today layout changed: no .book-row entries")
    author_name = _author_name(root)
    entries: list[SourceEntry] = []
    seen: set[str] = set()
    for row in rows:
        links = _elements(
            row,
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' book-title ')]"
            "//a[starts-with(@href, '/work/')]",
        )
        if not links:
            continue
        link = links[0]
        href = str(link.get("href") or "")
        work_id = href.removeprefix("/work/").split("/", 1)[0]
        title = " ".join(link.text_content().split())
        if not work_id.isdigit() or not title or work_id in seen:
            continue
        seen.add(work_id)
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
                external_id=f"author-today:work:{work_id}:revision:{revision}",
                title=title,
                author_name=author_name,
                url=urljoin("https://author.today", f"/work/{work_id}"),
                raw={
                    "work_id": work_id,
                    "updated_at": updated_at,
                    "status": status or None,
                    "series": (
                        " ".join(series_nodes[0].text_content().split()) if series_nodes else None
                    ),
                },
            )
        )
    if not entries:
        raise AuthorTodayParseError("Author.Today layout changed: no valid work metadata")
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
        try:
            if self.client is not None:
                response = await self.client.get(target, headers=headers)
            else:
                async with httpx.AsyncClient(
                    timeout=20.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "ghostcar-library/0.1 "
                            "(personal metadata monitor; contact: roman@gorbunovr.ru)"
                        )
                    },
                ) as client:
                    response = await client.get(target, headers=headers)
        except httpx.HTTPError as exc:
            raise AuthorTodayParseError(f"Author.Today fetch failed: {exc}") from exc
        if (response.url.host or "").lower() not in _ALLOWED_HOSTS:
            raise AuthorTodayParseError("Author.Today redirect left the allowed host")
        if response.status_code == 304:
            return FetchResult([], True, etag, last_modified)
        if response.status_code != 200:
            raise AuthorTodayParseError(f"Author.Today fetch returned {response.status_code}")
        if len(response.content) > _MAX_PAGE_BYTES:
            raise AuthorTodayParseError("Author.Today page exceeds size guard")
        return FetchResult(
            parse_author_today_works(response.content),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )
