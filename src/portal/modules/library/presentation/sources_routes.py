"""Sources UI: adapters status, watch rules, notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select, update

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.modules.library.adapters.source_orm import SourceEndpointModel, WatchRuleModel
from portal.modules.library.adapters.sources import list_adapters
from portal.modules.library.adapters.watch_service import WatchService
from portal.modules.library.application.service_console import ServiceConsoleQueries
from portal.modules.library.application.source_link_service import SourceLinkService
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
    enabled_adapter_ids = {adapter.id for adapter in list_adapters() if adapter.enabled}
    endpoints = list(
        (
            await session.execute(
                select(SourceEndpointModel).where(SourceEndpointModel.owner_id == current.user.id)
            )
        )
        .scalars()
        .all()
    )
    return _templates.TemplateResponse(
        request,
        "sources.html",
        {
            "user": current.user,
            "title": "Источники — Библиотека",
            "adapters": list_adapters(),
            "rules": rules,
            "endpoints": endpoints,
            "opds_endpoints": [
                endpoint for endpoint in endpoints if endpoint.source_type == "opds"
            ],
            "website_endpoints": [
                endpoint for endpoint in endpoints if endpoint.source_type == "html"
            ],
            "watch_endpoints": [
                endpoint
                for endpoint in endpoints
                if endpoint.enabled and endpoint.adapter_id in enabled_adapter_ids
            ],
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
        source_endpoint_id=endpoint_id,
    )
    if created is None:
        return RedirectResponse("/library/sources?error=rule", status_code=303)
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/opds")
async def connect_opds_source(
    current: CSRFProtected,
    session: SessionDep,
    name: Annotated[str, Form()],
    adapter_id: Annotated[str, Form()],
    url: Annotated[str, Form()],
    interval_minutes: Annotated[int, Form()] = 60,
) -> RedirectResponse:
    clean_name = name.strip()
    clean_url = url.strip()
    parsed = urlparse(clean_url)
    if (
        not clean_name
        or adapter_id not in {"opds", "flibusta"}
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return RedirectResponse("/library/sources?error=opds", status_code=303)
    endpoint = (
        await session.execute(
            select(SourceEndpointModel)
            .where(
                SourceEndpointModel.owner_id == current.user.id,
                SourceEndpointModel.adapter_id == adapter_id,
                SourceEndpointModel.url == clean_url,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if endpoint is None:
        endpoint = SourceEndpointModel(
            owner_id=current.user.id,
            name=clean_name,
            source_type="opds",
            role="metadata" if adapter_id == "flibusta" else "metadata+acquisition",
            adapter_id=adapter_id,
            url=clean_url,
        )
        session.add(endpoint)
        await session.flush()
    else:
        endpoint.name = clean_name
        endpoint.role = "metadata" if adapter_id == "flibusta" else "metadata+acquisition"
        endpoint.enabled = True
    rule = (
        await session.execute(
            select(WatchRuleModel)
            .where(
                WatchRuleModel.owner_id == current.user.id,
                WatchRuleModel.source_endpoint_id == endpoint.id,
                WatchRuleModel.adapter_id == adapter_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    interval_seconds = max(5, min(interval_minutes, 1440)) * 60
    if rule is None:
        session.add(
            WatchRuleModel(
                owner_id=current.user.id,
                adapter_id=adapter_id,
                source_endpoint_id=endpoint.id,
                name=clean_name,
                url=clean_url,
                interval_seconds=interval_seconds,
                next_poll_at=datetime.now(UTC),
            )
        )
    else:
        rule.name = clean_name
        rule.url = clean_url
        rule.interval_seconds = interval_seconds
        rule.enabled = True
        rule.next_poll_at = datetime.now(UTC)
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/endpoints/{endpoint_id}/toggle")
async def toggle_endpoint(
    endpoint_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    enabled: Annotated[bool, Form()],
) -> RedirectResponse:
    endpoint = await session.get(SourceEndpointModel, endpoint_id)
    if endpoint is not None and endpoint.owner_id == current.user.id:
        endpoint.enabled = enabled
        await session.execute(
            update(WatchRuleModel)
            .where(
                WatchRuleModel.owner_id == current.user.id,
                WatchRuleModel.source_endpoint_id == endpoint_id,
            )
            .values(enabled=enabled, next_poll_at=datetime.now(UTC) if enabled else None)
        )
        await session.commit()
    return RedirectResponse("/library/sources", status_code=303)


@router.post("/sources/endpoints/{endpoint_id}/delete")
async def delete_endpoint(
    endpoint_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
) -> RedirectResponse:
    await session.execute(
        delete(WatchRuleModel).where(
            WatchRuleModel.owner_id == current.user.id,
            WatchRuleModel.source_endpoint_id == endpoint_id,
        )
    )
    await session.execute(
        delete(SourceEndpointModel).where(
            SourceEndpointModel.id == endpoint_id,
            SourceEndpointModel.owner_id == current.user.id,
        )
    )
    await session.commit()
    return RedirectResponse("/library/sources", status_code=303)


def _safe_back(back: str) -> str:
    return back if back.startswith("/library/") and not back.startswith("//") else "/library/"


@router.post("/sources/links")
async def create_source_link(
    current: CSRFProtected,
    session: SessionDep,
    endpoint_id: Annotated[UUID, Form()],
    entity_type: Annotated[str, Form()],
    entity_id: Annotated[UUID, Form()],
    role: Annotated[str, Form()],
    external_url: Annotated[str, Form()] = "",
    priority: Annotated[int, Form()] = 100,
    preferred: Annotated[bool, Form()] = False,
    back: Annotated[str, Form()] = "/library/",
) -> RedirectResponse:
    created = await SourceLinkService(session).add(
        current.user.id,
        endpoint_id=endpoint_id,
        entity_type=entity_type,
        entity_id=entity_id,
        role=role,
        external_url=external_url,
        preferred=preferred,
        priority=priority,
    )
    if not created:
        return RedirectResponse(f"{_safe_back(back)}?source_error=invalid", status_code=303)
    await session.commit()
    return RedirectResponse(_safe_back(back), status_code=303)


@router.post("/sources/links/{link_id}/prefer")
async def prefer_source_link(
    link_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    back: Annotated[str, Form()] = "/library/",
) -> RedirectResponse:
    if await SourceLinkService(session).prefer(current.user.id, link_id):
        await session.commit()
    return RedirectResponse(_safe_back(back), status_code=303)


@router.post("/sources/links/{link_id}/delete")
async def delete_source_link(
    link_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    back: Annotated[str, Form()] = "/library/",
) -> RedirectResponse:
    if await SourceLinkService(session).remove(current.user.id, link_id):
        await session.commit()
    return RedirectResponse(_safe_back(back), status_code=303)


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
    clean_url = url.strip()
    if (
        source_type not in {"opds", "html"}
        or role
        not in {
            "metadata",
            "acquisition",
            "metadata+acquisition",
        }
        or urlparse(clean_url).scheme not in {"http", "https"}
    ):
        return RedirectResponse("/library/sources?error=endpoint", status_code=303)
    allowed_adapters = {"opds", "flibusta"} if source_type == "opds" else {"html", "author_today"}
    if adapter_id not in allowed_adapters:
        return RedirectResponse("/library/sources?error=endpoint", status_code=303)
    if adapter_id == "author_today" and role != "metadata":
        return RedirectResponse("/library/sources?error=endpoint", status_code=303)
    session.add(
        SourceEndpointModel(
            owner_id=current.user.id,
            name=name.strip(),
            source_type=source_type,
            role=role,
            adapter_id=adapter_id,
            url=clean_url,
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


@router.post("/sources/rules/{rule_id}/refresh")
async def refresh_rule(
    rule_id: UUID,
    request: Request,
    current: CSRFProtected,
) -> RedirectResponse:
    outcome = await _watch_service(request).request_poll(current.user.id, rule_id)
    return RedirectResponse(f"/library/service?refresh={outcome}", status_code=303)


@router.get("/service", response_class=HTMLResponse)
async def service_page(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    snapshot = await ServiceConsoleQueries(session).snapshot(current.user.id)
    return _templates.TemplateResponse(
        request,
        "service.html",
        {
            "user": current.user,
            "title": "Сервис — Библиотека",
            "refresh_result": request.query_params.get("refresh"),
            **snapshot,
        },
    )


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
