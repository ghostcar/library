"""Author.Today public metadata parser/fetch contract."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from portal.modules.library.adapters.author_today_adapter import (
    AuthorTodayAdapter,
    AuthorTodayParseError,
    normalize_author_works_url,
    parse_author_today_works,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "author_today_works_v1.html"


def test_parse_public_author_work_metadata() -> None:
    entries = parse_author_today_works(FIXTURE.read_bytes())
    assert [entry.external_id for entry in entries] == [
        "author-today:work:101:revision:2026-08-28T01:02:03Z",
        "author-today:work:102:revision:завершено",
    ]
    assert entries[0].title == "Новая книга"
    assert entries[0].author_name == "Тестовый Автор"
    assert entries[0].url == "https://author.today/work/101"
    assert entries[0].raw == {
        "work_id": "101",
        "publication_kind": "work",
        "updated_at": "2026-08-28T01:02:03Z",
        "status": "в процессе",
        "series": "Тестовый цикл",
        "series_url": "https://author.today/work/series/55",
    }


def test_parser_fails_closed_on_layout_change() -> None:
    with pytest.raises(AuthorTodayParseError, match="layout changed"):
        parse_author_today_works("<html><body><h1>Автор</h1></body></html>".encode())


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://author.today/u/test", "https://author.today/u/test/works"),
        ("https://author.today/u/test/works", "https://author.today/u/test/works"),
    ],
)
def test_profile_url_normalized(url: str, expected: str) -> None:
    assert normalize_author_works_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://author.today/u/test",
        "https://example.com/u/test",
        "https://author.today/work/101",
        "https://author.today/u/bad%2Fslug",
    ],
)
def test_non_public_or_foreign_url_rejected(url: str) -> None:
    with pytest.raises(AuthorTodayParseError):
        normalize_author_works_url(url)


async def test_fetch_uses_conditional_headers_and_handles_304() -> None:
    seen: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["etag"] = request.headers.get("if-none-match")
        return httpx.Response(304)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await AuthorTodayAdapter(client=client).fetch(
        "https://author.today/u/test", etag='"v1"'
    )
    assert result.not_modified
    assert seen == {"url": "https://author.today/u/test/works", "etag": '"v1"'}
    await client.aclose()


async def test_fetches_bounded_pagination_and_includes_audiobooks() -> None:
    requested: list[str] = []

    def page(publication_id: int, *, kind: str = "work", last_page: int = 1) -> str:
        pagination = (
            f'<a href="/u/test/works?page={last_page}">{last_page}</a>' if last_page > 1 else ""
        )
        return (
            '<html><body><script type="application/ld+json">'
            '{"@type":"Person","name":"Автор AT"}</script>'
            f'<div class="book-row"><div class="book-title"><a href="/{kind}/{publication_id}">'
            f"Публикация {publication_id}</a></div>"
            '<a href="/work/series/55">Цикл</a></div>'
            f"{pagination}</body></html>"
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        page_number = int(request.url.params.get("page", "1"))
        if page_number == 1:
            return httpx.Response(
                200,
                text=page(101, last_page=3),
                headers={"ETag": '"page-one"', "Last-Modified": "Mon, 31 Aug 2026 10:00:00 GMT"},
            )
        if page_number == 2:
            return httpx.Response(200, text=page(102, kind="audiobook", last_page=3))
        return httpx.Response(200, text=page(103, last_page=3))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await AuthorTodayAdapter(client=client).fetch("https://author.today/u/test")
    assert requested == [
        "https://author.today/u/test/works",
        "https://author.today/u/test/works?page=2",
        "https://author.today/u/test/works?page=3",
    ]
    assert [entry.external_id for entry in result.entries] == [
        "author-today:work:101:revision:published",
        "author-today:audiobook:102:revision:published",
        "author-today:work:103:revision:published",
    ]
    assert result.entries[1].url == "https://author.today/audiobook/102"
    assert result.etag is None
    assert result.last_modified is None
    await client.aclose()
