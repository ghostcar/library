"""FastAPI application factory (modular monolith shell)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from pathlib import Path as _Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
from portal.modules.library.adapters.opds_adapter import OPDSAdapter
from portal.modules.library.adapters.watch_service import WatchService
from portal.modules.library.ai.digest import DigestBuilder
from portal.modules.library.ai.omniroute import OmniRouteAdapter
from portal.modules.library.ai.proposal_service import ProposalService
from portal.modules.library.application.import_service import ImportService
from portal.modules.library.application.normalization_service import NormalizationService
from portal.modules.library.application.reading_service import ReadingStateService
from portal.modules.library.presentation import (
    catalog_routes,
    import_routes,
    normalization_routes,
    opds_settings_routes,
    proposal_routes,
    reading_routes,
    review_routes,
    settings_routes,
    sources_routes,
    ui_kit_routes,
)
from portal.modules.library.presentation.opds import routes as opds_routes
from portal.modules.library.presentation.routes import router as library_router
from portal.web.middleware import SecurityHeadersMiddleware
from portal.web.routes.auth_pages import router as auth_pages_router

logger = logging.getLogger("portal.web")


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
            "proposal_service": ProposalService(
                session_factory=session_factory,
                ai=OmniRouteAdapter(settings),
                digest_builder=DigestBuilder(),
            ),
            "reading_service": ReadingStateService(session_factory),
            "watch_service": WatchService(
                session_factory=session_factory,
                opds=OPDSAdapter(),
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

    static_dir = _Path(__file__).resolve().parents[1] / "web" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.add_middleware(SecurityHeadersMiddleware)

    error_templates = Jinja2Templates(directory=str(_Path(__file__).resolve().parent / "templates"))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        """Keep API errors JSON, but never expose bare JSON on portal pages."""
        is_portal_page = request.url.path.startswith("/library") or request.url.path == "/login"
        accepts_html = "text/html" in request.headers.get("accept", "")
        if exc.status_code == 401 and is_portal_page:
            target = quote(request.url.path, safe="/")
            return RedirectResponse(f"/auth/session?next={target}", status_code=303)
        if is_portal_page or accepts_html:
            messages = {
                403: "У вас нет доступа к этому действию или проверка безопасности устарела.",  # noqa: RUF001
                404: "Запрошенная страница не найдена.",
                422: "Проверьте заполнение формы и повторите попытку.",
                429: "Слишком много запросов. Подождите немного и повторите попытку.",
            }
            message = messages.get(exc.status_code, "Не удалось выполнить запрос.")  # noqa: RUF001
            return error_templates.TemplateResponse(
                request,
                "error.html",
                {
                    "title": f"Ошибка {exc.status_code} — Библиотека",
                    "status_code": exc.status_code,
                    "message": message,
                    "detail": str(exc.detail) if settings.is_dev else None,
                    "user": None,
                },
                status_code=exc.status_code,
            )
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        return await http_error(request, HTTPException(status_code=422, detail=exc.errors()))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled request error path=%s", request.url.path, exc_info=exc)
        return await http_error(
            request,
            HTTPException(status_code=500, detail="internal server error"),
        )

    registry.register(
        "library",
        router=library_router,
        description="Personal library domain module",
    )

    app.include_router(auth_router)
    app.include_router(auth_pages_router)
    app.include_router(import_routes.router, prefix="/library")
    app.include_router(reading_routes.router, prefix="/library")
    app.include_router(sources_routes.router, prefix="/library")
    app.include_router(opds_routes.router)  # top-level /opds for FBReader
    app.include_router(opds_settings_routes.router, prefix="/library")
    app.include_router(ui_kit_routes.router, prefix="/library")  # dev-only guard inside
    app.include_router(catalog_routes.router, prefix="/library")
    app.include_router(normalization_routes.router, prefix="/library")
    app.include_router(review_routes.router, prefix="/library")
    app.include_router(proposal_routes.router, prefix="/library")
    app.include_router(settings_routes.router, prefix="/library")
    for router in registry.routers():
        app.include_router(router, prefix="/library")

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        """Site root: the library module is the default macroportal section."""
        return RedirectResponse("/library/", status_code=307)

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
