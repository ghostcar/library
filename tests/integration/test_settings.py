"""Tests for settings page and password change."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from portal.core.auth.dependencies import CSRF_COOKIE

EMAIL = "settings-test@example.com"
PASSWORD = "test-password-123"  # noqa: S105 - synthetic test credential
NEW_PASSWORD = "brand-new-password-12345"  # noqa: S105 - synthetic test credential


@pytest.fixture
async def authed(app: Any, client: httpx.AsyncClient) -> httpx.AsyncClient:
    resp = await client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 201
    assert "library_csrf" in client.cookies
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    return client


@pytest.mark.anyio
async def test_settings_page_requires_auth(app: Any) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/library/settings", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/auth/session?next=/library/settings"


@pytest.mark.anyio
async def test_settings_page_renders(app: Any, authed: httpx.AsyncClient) -> None:
    resp = await authed.get("/library/settings")
    assert resp.status_code == 200
    assert "СМЕНА ПАРОЛЯ" in resp.text
    assert "csrf_token" in resp.text


@pytest.mark.anyio
async def test_change_password_wrong_old(app: Any, authed: httpx.AsyncClient) -> None:
    csrf = authed.cookies.get(CSRF_COOKIE, "")
    resp = await authed.post(
        "/library/settings/password",
        data={
            "old_password": "wrong-password-here",
            "new_password": NEW_PASSWORD,
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Неверный текущий пароль" in resp.text


@pytest.mark.anyio
async def test_change_password_short_new(app: Any, authed: httpx.AsyncClient) -> None:
    csrf = authed.cookies.get(CSRF_COOKIE, "")
    resp = await authed.post(
        "/library/settings/password",
        data={
            "old_password": PASSWORD,
            "new_password": "short",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_change_password_success(app: Any, authed: httpx.AsyncClient) -> None:
    csrf = authed.cookies.get(CSRF_COOKIE, "")
    resp = await authed.post(
        "/library/settings/password",
        data={
            "old_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    # old password no longer works
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp2 = await c.post(
            "/auth/login",
            data={"username": EMAIL, "password": PASSWORD},
            follow_redirects=False,
        )
        assert resp2.status_code == 401

        # new password works
        resp3 = await c.post(
            "/auth/login",
            data={"username": EMAIL, "password": NEW_PASSWORD},
            follow_redirects=False,
        )
        assert resp3.status_code == 200
        assert "library_access" in resp3.cookies


@pytest.mark.anyio
async def test_change_password_no_csrf(app: Any, authed: httpx.AsyncClient) -> None:
    del authed.headers["x-csrf-token"]
    resp = await authed.post(
        "/library/settings/password",
        data={
            "old_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "csrf_token": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_logout_csrf_protection(app: Any, authed: httpx.AsyncClient) -> None:
    """Logout requires CSRF token (prevents CSRF logout attacks)."""
    resp = await authed.post(
        "/logout",
        data={"csrf_token": "wrong-token"},
        follow_redirects=False,
    )
    assert resp.status_code == 403

    # correct CSRF → logout succeeds
    csrf = authed.cookies.get(CSRF_COOKIE, "")
    resp2 = await authed.post(
        "/logout",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    assert resp2.headers["location"] == "/login"
