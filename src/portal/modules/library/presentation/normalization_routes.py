"""Normalization presentation: request run, queue, report, prefer, download."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.modules.library.application.normalization_service import (
    AssetNotFoundError,
    NormalizationError,
    NormalizationService,
)
from portal.modules.library.domain import entities as de
from portal.modules.library.domain import normalization as nz
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _normalization_service(request: Request) -> NormalizationService:
    service: NormalizationService = request.app.state.container["normalization_service"]
    return service


def _import_service(request: Request) -> object:
    return request.app.state.container["import_service"]


@router.get("/normalization", response_class=HTMLResponse)
async def normalization_page(
    request: Request,
    current: CurrentUser,
) -> HTMLResponse:
    service = _normalization_service(request)
    runs = await service.list_runs(current.user.id)
    return _templates.TemplateResponse(
        request,
        "normalization.html",
        {
            "user": current.user,
            "title": "Нормализация — Библиотека",
            "runs": runs,
        },
    )


@router.get("/normalization/{run_id}", response_class=HTMLResponse)
async def run_report(
    request: Request,
    run_id: UUID,
    current: CurrentUser,
) -> HTMLResponse:
    service = _normalization_service(request)
    run = await service.get_run(current.user.id, run_id)
    if run is None:
        return _templates.TemplateResponse(
            request,
            "not_found.html",
            {"user": current.user, "title": "Не найдено"},  # noqa: RUF001
            status_code=404,
        )
    return _templates.TemplateResponse(
        request,
        "normalization_run.html",
        {
            "user": current.user,
            "title": f"Прогон {str(run_id)[:8]} — Библиотека",
            "run": run,
        },
    )


@router.post("/assets/{asset_id}/normalize")
async def request_normalization(
    request: Request,
    asset_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    profile: str = "prose_compact",
) -> RedirectResponse:
    service = _normalization_service(request)
    try:
        result = await service.request_normalization(
            current.user.id,
            asset_id,
            nz.ProfileName(profile),
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="asset not found") from exc
    except (NormalizationError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="normalization request rejected") from exc

    if not result.idempotent:
        from portal.core.jobs.repository import JobRepository

        # request session is already transactional (provide_session)
        await JobRepository(session).enqueue(
            "normalize",
            {"owner_id": str(current.user.id), "run_id": str(result.run_id)},
        )
    return RedirectResponse(f"/library/normalization/{result.run_id}", status_code=303)


@router.post("/normalization/{run_id}/prefer")
async def prefer_derivative(
    run_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    request: Request,
) -> RedirectResponse:
    service = _normalization_service(request)
    if not await service.prefer_derivative(current.user.id, run_id):
        raise HTTPException(status_code=404, detail="normalization run not found")
    return RedirectResponse(f"/library/normalization/{run_id}", status_code=303)


@router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    current: CurrentUser,
    session: SessionDep,
    request: Request,
) -> Response:
    """Owner-scoped download with human-readable Content-Disposition (§6.2)."""
    from portal.core.storage.local import StorageError
    from portal.modules.library.infrastructure.repositories import AssetRepository

    assets = AssetRepository(session)
    asset = await assets.get(current.user.id, asset_id)
    if asset is None:
        return Response(status_code=404)

    storage = request.app.state.container["storage"]
    try:
        path = storage._resolve(asset.storage_path)
    except StorageError:
        return Response(status_code=404)

    filename = await _human_readable_name(session, current.user.id, asset)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename,
    )


async def _human_readable_name(
    session: AsyncSession,
    owner_id: UUID,
    asset: de.Asset,
) -> str:
    """'Автор — Серия 04 — Название.ext' (master prompt 6.2)."""
    from sqlalchemy import select

    from portal.modules.library.infrastructure.orm import (
        AuthorModel,
        SeriesMembershipModel,
        SeriesModel,
        WorkAuthorModel,
        WorkModel,
    )

    extension = asset.original_filename.rsplit(".", 1)[-1] if asset.original_filename else "bin"
    if asset.work_id is None:
        base = asset.original_filename or f"asset-{asset.id}"
        return base if "." in base else f"{base}.{extension}"

    work_row = await session.get(WorkModel, asset.work_id)
    if work_row is None:
        return f"asset-{asset.id}.{extension}"

    parts: list[str] = []
    author_rows = (
        (
            await session.execute(
                select(AuthorModel)
                .join(WorkAuthorModel, WorkAuthorModel.author_id == AuthorModel.id)
                .where(WorkAuthorModel.work_id == work_row.id)
                .order_by(WorkAuthorModel.position),
            )
        )
        .scalars()
        .all()
    )
    if author_rows:
        parts.append(author_rows[0].name)

    membership = (
        await session.execute(
            select(SeriesMembershipModel, SeriesModel)
            .join(SeriesModel, SeriesModel.id == SeriesMembershipModel.series_id)
            .where(SeriesMembershipModel.work_id == work_row.id),
        )
    ).first()
    if membership is not None:
        m, series_row = membership
        if m.index_raw:
            parts.append(f"{series_row.title} {m.index_raw}")
        else:
            parts.append(series_row.title)

    parts.append(work_row.title)
    name = " — ".join(parts)
    safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip()
    return f"{safe}.{extension}"
