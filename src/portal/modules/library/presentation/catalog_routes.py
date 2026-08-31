"""Library catalog presentation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.modules.library.adapters.author_today_adapter import AuthorTodayParseError
from portal.modules.library.adapters.source_orm import SourceEndpointModel
from portal.modules.library.application.source_link_service import SourceLinkService
from portal.modules.library.application.source_onboarding_service import SourceOnboardingService
from portal.modules.library.infrastructure.orm import AuthorModel
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


async def _endpoints(session: Any, owner_id: UUID) -> list[SourceEndpointModel]:
    return list(
        (
            await session.execute(
                select(SourceEndpointModel)
                .where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.enabled.is_(True),
                )
                .order_by(SourceEndpointModel.name)
            )
        ).scalars()
    )


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    q: str = "",
) -> HTMLResponse:
    from portal.modules.library.infrastructure.import_repositories import CatalogQueries

    queries = CatalogQueries(session)
    works = await queries.works_with_authors(current.user.id)
    needle = q.strip().casefold()
    if needle:
        works = [
            work
            for work in works
            if needle in str(work["title"]).casefold()
            or any(
                needle in str(author).casefold() for author in cast("list[str]", work["authors"])
            )
            or any(
                needle in str(series["title"]).casefold()
                for series in cast("list[dict[str, Any]]", work["series"])
            )
        ]
    counts = await queries.counts(current.user.id)
    return _templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "user": current.user,
            "title": "Каталог — Библиотека",
            "works": works,
            "counts": counts,
            "query": q,
        },
    )


@router.get("/works/{work_id}", response_class=HTMLResponse)
async def work_page(
    request: Request,
    work_id: UUID,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    from portal.modules.library.infrastructure.import_repositories import CatalogQueries

    detail = await CatalogQueries(session).work_detail(current.user.id, work_id)
    if detail is None:
        return _templates.TemplateResponse(
            request,
            "not_found.html",
            {"user": current.user, "title": "Не найдено"},  # noqa: RUF001
            status_code=404,
        )
    detail["sources"] = await SourceLinkService(session).resolved(current.user.id, "work", work_id)
    return _templates.TemplateResponse(
        request,
        "work_detail.html",
        {
            "user": current.user,
            "title": f"{detail['title']} — Библиотека",
            "work": detail,
            "source_endpoints": await _endpoints(session, current.user.id),
        },
    )


@router.post("/authors/{author_id}/observe-author-today")
async def observe_author_today(
    author_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    url: Annotated[str, Form()],
) -> RedirectResponse:
    try:
        await SourceOnboardingService(session).connect_author_today(current.user.id, author_id, url)
    except AuthorTodayParseError:
        return RedirectResponse(f"/library/authors/{author_id}?source_error=url", status_code=303)
    return RedirectResponse(f"/library/authors/{author_id}", status_code=303)


@router.post("/authors/{author_id}/series-candidates")
async def accept_series_candidate(
    author_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    endpoint_id: Annotated[UUID, Form()],
    name: Annotated[str, Form()],
) -> RedirectResponse:
    await SourceOnboardingService(session).accept_series(
        current.user.id, author_id, endpoint_id, name
    )
    return RedirectResponse(f"/library/authors/{author_id}", status_code=303)


@router.get("/authors", response_class=HTMLResponse)
async def authors_page(request: Request, current: CurrentUser, session: SessionDep) -> HTMLResponse:
    from portal.modules.library.application.opds_catalog_service import OpdsCatalogService

    authors = await OpdsCatalogService(session).authors_list(current.user.id)
    return _templates.TemplateResponse(
        request,
        "authors.html",
        {
            "user": current.user,
            "title": "Авторы — Библиотека",
            "authors": authors,
        },
    )


@router.get("/authors/{author_id}", response_class=HTMLResponse)
async def author_page(
    request: Request, author_id: UUID, current: CurrentUser, session: SessionDep
) -> HTMLResponse:
    from portal.modules.library.application.opds_catalog_service import OpdsCatalogService

    service = OpdsCatalogService(session)
    works = await service.author_works(current.user.id, author_id)
    author = await session.get(AuthorModel, author_id)
    if works is None or author is None or author.owner_id != current.user.id:
        return _templates.TemplateResponse(
            request,
            "not_found.html",
            {"user": current.user, "title": "Не найдено"},  # noqa: RUF001
            status_code=404,
        )
    onboarding = SourceOnboardingService(session)
    return _templates.TemplateResponse(
        request,
        "author.html",
        {
            "user": current.user,
            "title": f"{author.name} — Библиотека",
            "works": works,
            "author": author,
            "sources": await SourceLinkService(session).resolved(
                current.user.id, "author", author_id
            ),
            "source_endpoints": await _endpoints(session, current.user.id),
            "author_today_status": await onboarding.author_today_status(current.user.id, author_id),
            "series_candidates": await onboarding.series_candidates(current.user.id, author_id),
            "source_error": request.query_params.get("source_error"),
        },
    )
