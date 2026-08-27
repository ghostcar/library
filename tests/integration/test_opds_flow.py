"""Integration: OPDS delivery flow — device tokens, feeds, download, revocation."""

from __future__ import annotations

import base64

import httpx
import pytest

pytestmark = pytest.mark.integration

EMAIL = "opds@test.example"
PASSWORD = "opds-test-pass-123"  # noqa: S105 - synthetic test credential


def _basic(username: str, password: str) -> dict[str, str]:
    raw = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


@pytest.fixture
async def authed(client: httpx.AsyncClient) -> tuple[httpx.AsyncClient, str]:
    response = await client.post(
        "/auth/register",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    return client, EMAIL


async def _upload_book(
    client: httpx.AsyncClient,
    filename: str,
    title: str,
    body: str = "Текст книги.",
) -> None:
    content = (
        '<?xml version="1.0"?><FictionBook '
        'xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        f"<body><section><p>{body}</p></section></body></FictionBook>"
    ).encode()
    response = await client.post(
        "/library/import/upload",
        files=[("files", (filename, content, "application/octet-stream"))],
    )
    assert response.status_code == 303


async def _create_token(client: httpx.AsyncClient, name: str, csrf: str) -> str:
    response = await client.post(
        "/auth/tokens",
        json={"name": name, "scopes": ["library:opds:read"]},
        headers={"x-csrf-token": csrf},
    )
    assert response.status_code == 201
    return response.json()["token"]


class TestDeviceTokenAuth:
    async def test_basic_auth_grants_access(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        token = await _create_token(client, "FBReader", client.cookies["library_csrf"])

        response = await client.get("/opds", headers=_basic("reader@x", token))
        assert response.status_code == 200
        assert "application/atom+xml" in response.headers["content-type"]

        # Bearer also works
        response = await client.get("/opds", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    async def test_wrong_or_revoked_token_401(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        token = await _create_token(client, "Phone", client.cookies["library_csrf"])

        # garbage token
        response = await client.get("/opds", headers=_basic("x", "pdt_wrong"))
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

        # main JWT is NOT a device token (§10.1)
        jwt_token = client.cookies["library_access"]
        response = await client.get("/opds", headers=_basic("x", jwt_token))
        assert response.status_code == 401

        # revocation cuts access
        tokens_list = await client.get("/auth/tokens")
        token_id = tokens_list.json()[0]["id"]
        await client.delete(
            f"/auth/tokens/{token_id}",
            headers={"x-csrf-token": client.cookies["library_csrf"]},
        )
        response = await client.get("/opds", headers=_basic("x", token))
        assert response.status_code == 401

    async def test_no_credentials_401_with_www_authenticate(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        response = await client.get("/opds")
        assert response.status_code == 401
        assert "Basic" in response.headers["WWW-Authenticate"]


class TestCatalogFeeds:
    async def test_root_navigation_and_series_feed(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        token = await _create_token(client, "FB", client.cookies["library_csrf"])
        await _upload_book(client, "Киз — Классика 01 — Цветы для Элджернона.fb2", "Цветы")

        headers = _basic("x", token)

        root = await client.get("/opds", headers=headers)
        assert "Циклы" in root.text
        assert "/opds/search.xml" in root.text

        series = await client.get("/opds/series", headers=headers)
        assert "Классика" in series.text

        import re

        series_id = re.search(r"/opds/series/([0-9a-f-]+)", series.text).group(1)  # type: ignore[union-attr]
        series_feed = await client.get(f"/opds/series/{series_id}", headers=headers)
        assert "Цветы для Элджернона" in series_feed.text
        assert "/opds/download/" in series_feed.text
        assert "application/fb2+xml" in series_feed.text

    async def test_unread_and_search(self, authed: tuple[httpx.AsyncClient, str]) -> None:
        client, _email = authed
        token = await _create_token(client, "FB", client.cookies["library_csrf"])
        await _upload_book(client, "Лукьяненко — Черновик.fb2", "Черновик")
        headers = _basic("x", token)

        unread = await client.get("/opds/unread", headers=headers)
        assert "Черновик" in unread.text

        found = await client.get("/opds/search", params={"q": "Лукьяненко"}, headers=headers)
        assert "Черновик" in found.text

        empty = await client.get("/opds/search", params={"q": "несуществующее"}, headers=headers)
        assert "Поиск" in empty.text

    async def test_download_with_content_disposition(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        token = await _create_token(client, "FB", client.cookies["library_csrf"])
        await _upload_book(
            client,
            "Киз — Классика 01 — Цветы для Элджернона.fb2",
            "Цветы",
        )
        headers = _basic("x", token)

        new_feed = await client.get("/opds/new", headers=headers)
        import re

        asset_id = re.search(r"/opds/download/([0-9a-f-]+)", new_feed.text).group(1)  # type: ignore[union-attr]
        download = await client.get(f"/opds/download/{asset_id}", headers=headers)
        assert download.status_code == 200
        from urllib.parse import unquote

        disposition = unquote(download.headers["content-disposition"])
        assert "Киз" in disposition
        assert disposition.endswith(".fb2")

    async def test_owner_isolation_between_users(
        self,
        authed: tuple[httpx.AsyncClient, str],
    ) -> None:
        client, _email = authed
        token = await _create_token(client, "FB", client.cookies["library_csrf"])
        await _upload_book(client, "Приватная — Книга.fb2", "Приватная")
        headers = _basic("x", token)

        new_feed = await client.get("/opds/new", headers=headers)
        import re

        asset_id = re.search(r"/opds/download/([0-9a-f-]+)", new_feed.text).group(1)  # type: ignore[union-attr]

        # second user: superuser creates an account, then their own device token
        from uuid import UUID as U

        service = client._transport.app.state.container["auth_service"]
        second = await service.register(
            "second@test.example",
            "second-user-pass-123",
            actor_is_superuser=True,
        )
        created = await service.create_device_token(second, "FB2", ["library:opds:read"])

        other_headers = _basic("x", created.raw_token)
        empty_feed = await client.get("/opds/new", headers=other_headers)
        assert "Приватная" not in empty_feed.text
        assert "<entry>" not in empty_feed.text

        foreign_download = await client.get(
            f"/opds/download/{asset_id}",
            headers=other_headers,
        )
        assert foreign_download.status_code == 404

        # owner's token cannot be reused by second user's identity: token IS identity
        me = U((await client.get("/auth/me", headers=headers)).json()["id"])
        assert str(me) != str(second.id)
