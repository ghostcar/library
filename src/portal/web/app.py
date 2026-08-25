"""FastAPI application factory (modular monolith shell)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from portal.core.audit.service import AuditService
from portal.core.auth.jwt_service import TokenService
from portal.core.auth.rate_limit import RateLimiter
from portal.core.auth.repository import AuditRepository
from portal.core.auth.routes import router as auth_router
from portal.core.auth.service import AuthService
from portal.core.config.config import Settings, get_settings
from portal.core.database.engine import build_container as build_db_container
from portal.core.module_registry.registry import ModuleRegistry
from portal.core.storage.local import LocalStorageAdapter
from portal.modules.library.application.import_service import ImportService
from portal.modules.library.application.normalization_service import NormalizationService
from portal.modules.library.presentation import (
    catalog_routes,
    import_routes,
    normalization_routes,
    review_routes,
)
from portal.modules.library.presentation.routes import router as library_router
from portal.web.routes.auth_pages import router as auth_pages_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container: dict[str, Any] = build_container(app.state.settings)
    app.state.container = container
    yield
    engine = container["engine"]
    await engine.dispose()


def build_container(settings: Settings) -> dict[str, Any]:
    """Composition root for the whole portal."""
    container = build_db_container(settings)
    token_service = TokenService(settings)
    session_factory = container["session_factory"]
    audit_service = AuditService(AuditRepository(session_factory()))
    auth_service = AuthService(
        session_factory=session_factory,
        audit=audit_service,
        token_service=token_service,
        settings=settings,
    )
    storage = LocalStorageAdapter(Path(settings.storage_root))
    container.update(
        {
            "token_service": token_service,
            "audit_service": audit_service,
            "auth_service": auth_service,
            "storage": storage,
            "import_service": ImportService(
                session_factory=session_factory,
                storage=storage,
                max_file_bytes=settings.max_file_bytes,
                max_files_per_batch=settings.max_files_per_batch,
            ),
            "normalization_service": NormalizationService(
                session_factory=session_factory,
                storage=storage,
            ),
            "rate_limiters": {
                "login": RateLimiter(settings.login_rate_limit, settings.rate_limit_window_seconds),
                "register": RateLimiter(
                    settings.register_rate_limit,
                    settings.rate_limit_window_seconds,
                ),
            },
        },
    )
    return container


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

    app.include_router(auth_router)
    app.include_router(auth_pages_router)
    app.include_router(import_routes.router, prefix="/library")
    app.include_router(catalog_routes.router, prefix="/library")
    app.include_router(normalization_routes.router, prefix="/library")
    app.include_router(review_routes.router, prefix="/library")
    for router in registry.routers():
        app.include_router(router, prefix="/library")

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

    return app
