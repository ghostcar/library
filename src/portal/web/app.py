"""FastAPI application factory (modular monolith shell)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from portal.core.config.config import Settings, get_settings
from portal.core.database.engine import build_container
from portal.core.module_registry.registry import ModuleRegistry
from portal.modules.library.presentation.routes import router as library_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container: dict[str, Any] = build_container(app.state.settings)
    app.state.container = container
    yield
    engine = container["engine"]
    await engine.dispose()


def create_app(
    settings: Settings | None = None,
    registry: ModuleRegistry | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    registry = registry or ModuleRegistry()

    app = FastAPI(
        title="Library Portal",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.registry = registry

    registry.register(
        "library",
        router=library_router,
        description="Personal library domain module",
    )

    @app.get("/healthz", tags=["core"])
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/readyz", tags=["core"])
    async def readyz(request: Request) -> JSONResponse:
        from sqlalchemy import text

        engine = request.app.state.container["engine"]
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready"})

    for router in registry.routers():
        app.include_router(router, prefix="/library")

    return app
