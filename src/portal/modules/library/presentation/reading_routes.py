"""Reading actions and dashboard routes (mobile-first, master prompt 10.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from portal.core.auth.dependencies import CSRFProtected, CurrentUser, OptionalUser
from portal.modules.library.adapters.source_orm import SourceEndpointModel
from portal.modules.library.adapters.watch_service import WatchService
from portal.modules.library.application.reading_service import ReadingStateService
from portal.modules.library.application.series_state_service import SeriesStateService
from portal.modules.library.application.source_link_service import SourceLinkService
from portal.modules.library.domain.enums import ReadingChangeSource, ReadingStatus
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _reading_service(request: Request) -> ReadingStateService:
    service: ReadingStateService = request.app.state.container["reading_service"]
    return service


def _safe_back(back: str, fallback: str) -> str:
    return back if back.startswith("/library/") and not back.startswith("//") else fallback


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, current: OptionalUser) -> Response:
    if current is None:
        return RedirectResponse("/login", status_code=303)
    service = _reading_service(request)
    continue_reading = await service.continue_reading(current.user.id)
    recently_added = await service.recently_added(current.user.id)
    queue = await service.reading_queue(current.user.id, limit=5)
    watch: WatchService = request.app.state.container["watch_service"]
    unread = await watch.unread_count(current.user.id)
    return _templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": current.user,
            "title": "Библиотека",
            "continue_reading": continue_reading,
            "recently_added": recently_added,
            "queue": queue,
            "unread_notifications": unread,
        },
    )


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request, current: CurrentUser) -> HTMLResponse:
    service = _reading_service(request)
    queue = await service.reading_queue(current.user.id)
    return _templates.TemplateResponse(
        request,
        "queue.html",
        {"user": current.user, "title": "Очередь чтения — Библиотека", "queue": queue},
    )


@router.get("/series/{series_id}", response_class=HTMLResponse)
async def series_page(
    request: Request,
    series_id: UUID,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    series_service = SeriesStateService(session)
    state = await series_service.for_series(current.user.id, series_id)
    if state is None:
        return _templates.TemplateResponse(
            request,
            "not_found.html",
            {"user": current.user, "title": "Не найдено"},  # noqa: RUF001
            status_code=404,
        )
    return _templates.TemplateResponse(
        request,
        "series.html",
        {
            "user": current.user,
            "title": f"{state.title} — Библиотека",
            "state": state,
            "sources": await SourceLinkService(session).resolved(
                current.user.id, "series", series_id
            ),
            "source_endpoints": list(
                (
                    await session.execute(
                        select(SourceEndpointModel)
                        .where(
                            SourceEndpointModel.owner_id == current.user.id,
                            SourceEndpointModel.enabled.is_(True),
                        )
                        .order_by(SourceEndpointModel.name)
                    )
                ).scalars()
            ),
        },
    )


@router.get("/series", response_class=HTMLResponse)
async def series_overview(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    series_service = SeriesStateService(session)
    states = await series_service.list_series_overview(current.user.id)
    return _templates.TemplateResponse(
        request,
        "series_list.html",
        {"user": current.user, "title": "Циклы — Библиотека", "states": states},
    )


@router.post("/works/{work_id}/status")
async def set_reading_status(
    request: Request,
    work_id: UUID,
    current: CSRFProtected,
    status: Annotated[str, Form()],
    back: Annotated[str, Form()] = "/library/queue",
) -> RedirectResponse:
    service = _reading_service(request)
    try:
        new_status = ReadingStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unknown reading status") from exc
    try:
        await service.set_status(current.user.id, work_id, new_status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="work not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="reading transition is not allowed") from exc
    return RedirectResponse(_safe_back(back, "/library/queue"), status_code=303)


@router.post("/works/status/bulk")
async def bulk_status(
    request: Request,
    current: CSRFProtected,
    work_ids: Annotated[list[str], Form()],
    status: Annotated[str, Form()],
    back: Annotated[str, Form()] = "/library/import",
) -> RedirectResponse:
    service = _reading_service(request)
    work_uuids = []
    for raw in work_ids:
        try:
            work_uuids.append(UUID(raw))
        except ValueError:
            continue
    if status not in {s.value for s in ReadingStatus}:
        raise HTTPException(status_code=400, detail="unknown reading status")
    await service.mark_read_bulk(current.user.id, work_uuids, ReadingChangeSource.MANUAL)
    return RedirectResponse(_safe_back(back, "/library/queue"), status_code=303)


@router.post("/series/{series_id}/user-status")
async def set_series_user_status(
    series_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    status: Annotated[str, Form()],
) -> RedirectResponse:
    series_service = SeriesStateService(session)
    if not await series_service.set_user_status(current.user.id, series_id, status):
        raise HTTPException(status_code=400, detail="unknown series or status")
    return RedirectResponse(f"/library/series/{series_id}", status_code=303)


@router.get("/works/{work_id}/history")
async def work_history(
    work_id: UUID,
    current: CurrentUser,
    request: Request,
) -> HTMLResponse:
    service = _reading_service(request)
    history = await service.history_for_work(current.user.id, work_id)
    return _templates.TemplateResponse(
        request,
        "reading_history.html",
        {"user": current.user, "title": "История чтения", "history": history, "work_id": work_id},
    )
