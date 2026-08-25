"""Unit tests for the FastAPI app shell (no external dependencies)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from portal.web.app import build_container, create_app
from tests.conftest import make_test_settings


@pytest.fixture
def app(tmp_path: Path):
    settings = make_test_settings(storage_root=str(tmp_path / "storage"))
    application = create_app(settings=settings)
    application.state.container = build_container(settings)
    return application


async def test_healthz(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unauthenticated_library_redirects_to_login(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/library/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_login_page_renders_and_sets_csrf(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/login")
    assert response.status_code == 200
    assert "Вход" in response.text
    assert "library_csrf" in response.cookies


async def test_openapi_lists_core_and_library_routes(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        schema = await client.get("/openapi.json")
    paths = schema.json()["paths"]
    assert "/healthz" in paths
    assert "/auth/login" in paths
    assert "/auth/register" in paths
    assert "/library/" in paths
    assert "/library/info" in paths
