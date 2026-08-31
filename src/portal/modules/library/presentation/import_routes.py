"""Library import presentation: upload, inbox, local-dir scan (HTMX-friendly)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.core.config.config import Settings
from portal.web.deps import SessionDep

if TYPE_CHECKING:
    from portal.modules.library.application.import_service import ImportService

if TYPE_CHECKING:
    from portal.modules.library.application.import_service import ImportService

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _import_service(request: Request) -> ImportService:
    service: ImportService = request.app.state.container["import_service"]
    return service


async def _inbox_context(
    session: AsyncSession,
    request: Request,
    owner_id: UUID,
    scan_result: Sequence[object] | None = None,
) -> dict[str, object]:
    from portal.modules.library.application.continuation_link_service import ContinuationLinkService
    from portal.modules.library.infrastructure.import_repositories import (
        CatalogQueries,
        DuplicateCandidateRepository,
        ImportBatchRepository,
        ImportItemRepository,
    )
    settings: Settings = request.app.state.settings
    unmatched = await ImportItemRepository(session).list_recent_unmatched(owner_id)
    return {
        "user_id": owner_id,
        "batches": await ImportBatchRepository(session).list_recent(owner_id),
        "unmatched": unmatched,
        "can_enqueue_ai": any(not item.match_evidence.get("ai_status") for item in unmatched),
        "assignable_works": await CatalogQueries(session).works_with_authors(owner_id, limit=250),
        "duplicates": await ImportItemRepository(session).list_recent_by_status(
            owner_id,
            statuses=["duplicate", "rejected", "failed"],
            limit=20,
        ),
        "candidates": await DuplicateCandidateRepository(session).list_pending(owner_id),
        "continuation_candidates": await ContinuationLinkService(session).list_pending(owner_id),
        "max_file_mb": settings.max_file_mb,
        "max_files": settings.max_files_per_batch,
        "scan_roots": settings.import_roots,
        "watched_inbox_enabled": settings.watched_inbox_enabled,
        "watched_inbox_interval_seconds": settings.watched_inbox_interval_seconds,
        "scan_result": scan_result,
    }


@router.get("/import", response_class=HTMLResponse)
async def import_page(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    context = await _inbox_context(session, request, current.user.id)
    return _templates.TemplateResponse(
        request,
        "import.html",
        {"user": current.user, "title": "Импорт — Библиотека", **context},
    )


@router.post("/continuation-links/{candidate_id}/resolve")
async def resolve_continuation_link(
    candidate_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
) -> RedirectResponse:
    from portal.modules.library.application.continuation_link_service import ContinuationLinkService

    await ContinuationLinkService(session).resolve_title(current.user.id, candidate_id)
    return RedirectResponse("/library/import", status_code=303)


@router.post("/continuation-links/{candidate_id}/dismiss")
async def dismiss_continuation_link(
    candidate_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
) -> RedirectResponse:
    from portal.modules.library.application.continuation_link_service import ContinuationLinkService

    await ContinuationLinkService(session).dismiss(current.user.id, candidate_id)
    return RedirectResponse("/library/import", status_code=303)


@router.post("/import/upload")
async def upload_files(
    request: Request,
    current: CSRFProtected,
    files: Annotated[list[UploadFile], File()],
) -> RedirectResponse:
    service = _import_service(request)
    settings: Settings = request.app.state.settings
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(status_code=413, detail="too many files")
    uploads: list[tuple[str, bytes]] = []
    for upload in files:
        chunks: list[bytes] = []
        total = 0
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_file_bytes:
                raise HTTPException(status_code=413, detail=f"file too large: {upload.filename}")
            chunks.append(chunk)
        content = b"".join(chunks)
        uploads.append((upload.filename or "unnamed", content))
    try:
        await service.import_uploads(current.user.id, uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/library/import", status_code=303)


@router.post("/import/propose-unmatched")
async def enqueue_pending_proposals(
    current: CSRFProtected,
    session: SessionDep,
) -> RedirectResponse:
    """Queue old unmatched imports once, without duplicating queued work."""
    from portal.core.jobs.repository import JobRepository
    from portal.modules.library.infrastructure.import_repositories import ImportItemRepository

    items = await ImportItemRepository(session).list_recent_unmatched(current.user.id)
    jobs = JobRepository(session)
    repository = ImportItemRepository(session)
    for item in items:
        if item.match_evidence.get("ai_status"):
            continue
        item.match_evidence["ai_status"] = "queued"
        await repository.update(item)
        await jobs.enqueue(
            "propose_import",
            {"owner_id": str(current.user.id), "item_id": str(item.id)},
        )
    return RedirectResponse("/library/import", status_code=303)


@router.post("/import/scan", response_class=HTMLResponse)
async def scan_directories(
    request: Request,
    current: CSRFProtected,
    session: SessionDep,
    apply: Annotated[bool, Form()] = False,
) -> Response:
    from portal.modules.library.infrastructure.repositories import AssetRepository

    service = _import_service(request)
    settings: Settings = request.app.state.settings
    roots = [Path(r) for r in settings.import_roots]
    known = await AssetRepository(session).all_hashes(current.user.id)
    entries = await service.scan_directories(current.user.id, roots, known_hashes=known)

    if apply:
        await service.import_from_scan(current.user.id, entries)
        return RedirectResponse("/library/import", status_code=303)

    context = await _inbox_context(session, request, current.user.id, scan_result=entries)
    return _templates.TemplateResponse(
        request,
        "import.html",
        {"user": current.user, "title": "Импорт — Библиотека", **context},
    )
