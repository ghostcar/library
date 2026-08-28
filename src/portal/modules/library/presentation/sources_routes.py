"""Sources UI: adapters status, watch rules, notifications."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.modules.library.adapters.source_orm import SourceEndpointModel
from portal.modules.library.adapters.sources import list_adapters
from portal.modules.library.adapters.watch_service import WatchService
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _watch_service(request: Request) -> WatchService:
    service: WatchService = request.app.state.container["watch_service"]
    return service


@router.get("/sources", response_class=HTMLResponse)
async def sources_page(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    service = _watch_service(request)
    rules = await service.list_rules(current.user.id)
    endpoints = list((await session.execute(
        select(SourceEndpointModel).where(SourceEndpointModel.owner_id == current.user.id)
    )).scalars().all())
    return _templates.TemplateResponse(
        request,
        "sources.html",
        {
            "user": current.user,
            "title": "Источники — Библиотека",
            "adapters": list_adapters(),
            "rules": rules,
            "endpoints": endpoints,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/sources/rules")
async def create_rule(
    request: Request,
    current: CSRFProtected,
    adapter_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    url: Annotated[str, Form()],
    interval_minutes: Annotated[int, Form()] = 60,
    endpoint_id: Annotated[UUID | None, Form()] = None,
) -> RedirectResponse:
    if endpoint_id is not None:
        async with request.app.state.container["session_factory"]() as endpoint_session:
            endpoint = await endpoint_session.get(SourceEndpointModel, endpoint_id)
            if endpoint is None or endpoint.owner_id != current.user.id or not endpoint.enabled:
                return RedirectResponse("/library/sources?error=endpoint", status_code=303)
            adapter_id, url = endpoint.adapter_id, endpoint.url
    service = _watch_service(request)
    created = await service.create_rule(
        current.user.id,
        adapter_id=adapter_id,
        name=name,
        url=url,
        interval_seconds=interval_minutes * 60,
    )
    if created is None:
        return RedirectResponse("/library/sources?error=rule", status_code=303)
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/endpoints")
async def create_endpoint(
    request: Request,
    current: CSRFProtected,
    session: SessionDep,
    name: Annotated[str, Form()],
    source_type: Annotated[str, Form()],
    role: Annotated[str, Form()],
    adapter_id: Annotated[str, Form()],
    url: Annotated[str, Form()],
) -> RedirectResponse:
    if source_type not in {"opds", "html"} or role not in {
        "metadata", "acquisition", "metadata+acquisition"
    }:
        return RedirectResponse("/library/sources?error=endpoint", status_code=303)
    session.add(
        SourceEndpointModel(
            owner_id=current.user.id,
            name=name.strip(),
            source_type=source_type,
            role=role,
            adapter_id=adapter_id,
            url=url.strip(),
        )
    )
    await session.commit()
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/rules/{rule_id}/delete")
async def delete_rule(
    rule_id: UUID,
    request: Request,
    current: CSRFProtected,
) -> RedirectResponse:
    service = _watch_service(request)
    await service.delete_rule(current.user.id, rule_id)
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: UUID,
    request: Request,
    current: CSRFProtected,
    enabled: Annotated[bool, Form()],
) -> RedirectResponse:
    service = _watch_service(request)
    await service.set_rule_enabled(current.user.id, rule_id, enabled)
    return RedirectResponse("/library/sources", status_code=303)


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    current: CurrentUser,
) -> HTMLResponse:
    service = _watch_service(request)
    notifications = await service.notifications(current.user.id)
    return _templates.TemplateResponse(
        request,
        "notifications.html",
        {
            "user": current.user,
            "title": "Уведомления — Библиотека",
            "notifications": notifications,
        },
    )


@router.post("/notifications/read-all")
async def read_all_notifications(
    request: Request,
    current: CSRFProtected,
) -> RedirectResponse:
    service = _watch_service(request)
    await service.mark_all_read(current.user.id)
    return RedirectResponse("/library/notifications", status_code=303)
