"""Async database engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from portal.core.config.config import Settings


class Base(DeclarativeBase):
    """Shared declarative base for all modules."""


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def provide_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session."""
    async with session_factory() as session:
        async with session.begin():
            yield session


def build_container(settings: Settings) -> dict[str, Any]:
    """Minimal composition root: engine + session factory."""
    engine = create_engine(settings)
    return {
        "settings": settings,
        "engine": engine,
        "session_factory": create_session_factory(engine),
    }
