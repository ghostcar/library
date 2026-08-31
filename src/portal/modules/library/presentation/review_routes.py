"""Review actions: assign unmatched items, resolve duplicate candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import CSRFProtected, CurrentUser
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


@router.get("/import/items/{item_id}/assign", response_class=HTMLResponse)
async def assignment_page(
    request: Request,
    item_id: UUID,
    current: CurrentUser,
    session: SessionDep,
    query: Annotated[str, Query(alias="q", max_length=200)] = "",
) -> Response:
    """Offer an owner-scoped catalog search for an unmatched import item."""
    from portal.modules.library.domain import import_entities as ie
    from portal.modules.library.infrastructure.import_repositories import (
        CatalogQueries,
        ImportItemRepository,
    )

    item = await ImportItemRepository(session).get(current.user.id, item_id)
    if item is None or item.status is not ie.ItemStatus.STORED_UNMATCHED:
        return RedirectResponse("/library/import", status_code=303)

    works = await CatalogQueries(session).works_with_authors(
        current.user.id,
        limit=50,
        query=query,
    )
    return _templates.TemplateResponse(
        request,
        "assign_import_item.html",
        {
            "user": current.user,
            "title": "Выбор книги — Библиотека",
            "item": item,
            "query": query,
            "works": works,
        },
    )


@router.post("/import/items/{item_id}/assign")
async def assign_item(
    item_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    work_id: Annotated[str, Form()] = "",
) -> RedirectResponse:
    """Attach an unmatched import item's asset to an existing work (review UI)."""
    from portal.modules.library.domain import import_entities as ie
    from portal.modules.library.infrastructure.import_repositories import ImportItemRepository
    from portal.modules.library.infrastructure.repositories import AssetRepository, WorkRepository

    items = ImportItemRepository(session)
    item = await items.get(current.user.id, item_id)
    if item is None or item.status is not ie.ItemStatus.STORED_UNMATCHED:
        return RedirectResponse("/library/import", status_code=303)

    if not work_id:
        return RedirectResponse("/library/import", status_code=303)
    try:
        parsed_work_id = UUID(work_id)
    except ValueError:
        return RedirectResponse(f"/library/import/items/{item_id}/assign", status_code=303)
    work = await WorkRepository(session).get(current.user.id, parsed_work_id)
    if work is None:
        return RedirectResponse("/library/import", status_code=303)

    if item.asset_id is not None:
        asset_repo = AssetRepository(session)
        asset = await asset_repo.get(current.user.id, item.asset_id)
        if asset is not None:
            asset.work_id = work.id
            await asset_repo.update_work_link(current.user.id, asset.id, work.id)

    item.status = ie.ItemStatus.MATCHED
    item.work_id = work.id
    item.match_evidence = {**item.match_evidence, "decision": "manual_review_assign"}
    await items.update(item)
    return RedirectResponse("/library/import", status_code=303)


@router.post("/duplicates/{candidate_id}/resolve")
async def resolve_duplicate(
    candidate_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    decision: Annotated[str, Form()],
) -> RedirectResponse:
    """Confirm (mark duplicate-of) or dismiss a duplicate candidate."""
    from portal.modules.library.domain import import_entities as ie
    from portal.modules.library.infrastructure.import_repositories import (
        DuplicateCandidateRepository,
    )
    from portal.modules.library.infrastructure.repositories import AssetRepository

    candidates = DuplicateCandidateRepository(session)
    pending = await candidates.list_pending(current.user.id, limit=1000)
    candidate = next((c for c in pending if c.id == candidate_id), None)
    if candidate is None:
        return RedirectResponse("/library/import", status_code=303)

    if decision == "confirm":
        resolved = await candidates.resolve(
            current.user.id,
            candidate_id,
            ie.CandidateStatus.CONFIRMED_DUPLICATE,
        )
        if resolved:
            await AssetRepository(session).set_preferred(
                current.user.id, candidate.suspected_of_asset_id
            )
    elif decision == "dismiss":
        await candidates.resolve(
            current.user.id,
            candidate_id,
            ie.CandidateStatus.DISTINCT,
        )
    return RedirectResponse("/library/import", status_code=303)
