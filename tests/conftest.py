"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    create_async_engine,
)

from portal.core.config.config import AppEnv, Settings
from portal.core.database.engine import Base

TEST_DB_URL_DEFAULT = "postgresql+asyncpg://library:library@127.0.0.1:55441/library_test"


def get_test_database_url() -> str:
    return os.environ.get("LIBRARY_TEST_DATABASE_URL", TEST_DB_URL_DEFAULT)


def make_test_settings(**overrides: object):
    values: dict[str, object] = {
        "app_env": AppEnv.TEST,
        "jwt_secret": "integration-test-secret-0123456789abcdef0123456789abcdef",
        "database_url": get_test_database_url(),
        "cookie_secure": False,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture
def owner_id() -> UUID:
    return uuid4()


@pytest.fixture
async def db_connection() -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(get_test_database_url())
    async with engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    session = AsyncSession(bind=db_connection, expire_on_commit=False)
    yield session
    await session.close()


@pytest.fixture(scope="session")
def _ensure_metadata() -> None:
    """Import ORM models so Base.metadata is populated."""
    from portal.modules.library.infrastructure import orm  # noqa: F401


@pytest.fixture
def metadata(_ensure_metadata: None):
    return Base.metadata
