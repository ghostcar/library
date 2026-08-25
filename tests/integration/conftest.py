"""Fixtures for integration tests: app with container, HTTP client, clean DB."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from portal.web.app import build_container, create_app
from tests.conftest import get_test_database_url, make_test_settings

ALL_TABLES = [
    "audit_log",
    "api_tokens",
    "asset_relations",
    "assets",
    "author_aliases",
    "authors",
    "jobs",
    "outbox_events",
    "reading_states",
    "series_aliases",
    "series_memberships",
    "series",
    "source_author_records",
    "source_records",
    "users",
    "work_authors",
    "works",
]


@pytest.fixture
def app_settings(tmp_path: Path):
    return make_test_settings(
        storage_root=str(tmp_path / "storage"),
        cookie_secure=False,  # http test client
    )


@pytest.fixture
def app(app_settings):
    application = create_app(settings=app_settings)
    application.state.container = build_container(app_settings)
    return application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def clean_db() -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(ALL_TABLES)} CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _require_clean_db(clean_db):
    """All integration tests in this package run against a truncated DB."""
    return


@pytest.fixture
async def db_owner(db_session):
    """A real user row: library tables have FK owner_id -> users.id."""
    from uuid import uuid4

    from portal.core.auth.domain import User
    from portal.core.auth.passwords import hash_password
    from portal.core.auth.repository import UserRepository

    user = User(email=f"owner-{uuid4().hex[:8]}@test.local", password_hash=hash_password("x" * 20))
    await UserRepository(db_session).add(user)
    return user.id
