"""Unit tests for the FastAPI app shell (no external dependencies)."""

from __future__ import annotations

import httpx
import pytest

from portal.core.config.config import AppEnv, Settings
from portal.web.app import create_app


@pytest.fixture
def app():
    settings = Settings(
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://invalid:invalid@127.0.0.1:1/none",
        _env_file=None,  # type: ignore[call-arg]
    )
    return create_app(settings=settings)


async def test_healthz(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_library_module_registered(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        info = await client.get("/library/info")
        page = await client.get("/library/")
    assert info.status_code == 200
    assert info.json()["enabled"] is True
    assert page.status_code == 200
    assert "Библиотека" in page.text


async def test_openapi_lists_library_routes(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        schema = await client.get("/openapi.json")
    paths = schema.json()["paths"]
    assert "/healthz" in paths
    assert "/library/" in paths
    assert "/library/info" in paths
