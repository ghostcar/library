"""Library catalog presentation."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import CurrentUser
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    from portal.modules.library.infrastructure.import_repositories import CatalogQueries

    queries = CatalogQueries(session)
    works = await queries.works_with_authors(current.user.id)
    counts = await queries.counts(current.user.id)
    return _templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "user": current.user,
            "title": "Каталог — Библиотека",
            "works": works,
            "counts": counts,
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
    return _templates.TemplateResponse(
        request,
        "work_detail.html",
        {"user": current.user, "title": f"{detail['title']} — Библиотека", "work": detail},
    )
