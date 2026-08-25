"""Web-layer FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def provide_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Transactional session per request; factory from app.state.container."""
    container = cast("dict[str, Any]", request.app.state.container)
    factory = container["session_factory"]
    async with factory() as session:
        async with session.begin():
            yield session


SessionDep = Annotated[AsyncSession, Depends(provide_session)]

__all__ = ["SessionDep", "provide_session"]
