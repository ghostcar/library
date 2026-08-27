"""AI proposal routes: propose for unmatched item, apply (with corrections)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import CSRFProtected
from portal.modules.library.ai.proposal import MatchProposal
from portal.modules.library.ai.proposal_service import (
    PolicyDecision,
    ProposalService,
)
from portal.web.deps import SessionDep

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _proposal_service(request: Request) -> ProposalService:
    service: ProposalService = request.app.state.container["proposal_service"]
    return service


@router.post("/import/items/{item_id}/propose")
async def propose_for_item(
    request: Request,
    item_id: UUID,
    current: CSRFProtected,
) -> Response:
    service = _proposal_service(request)
    try:
        outcome = await service.propose_for_item(current.user.id, item_id)
    except LookupError:
        return RedirectResponse("/library/import", status_code=303)

    proposal = outcome.proposal
    return _templates.TemplateResponse(
        request,
        "proposal.html",
        {
            "user": current.user,
            "title": "Разбор файла — Библиотека",
            "item_id": item_id,
            "outcome": outcome,
            "proposal": proposal,
            "decision": outcome.decision,
            "auto_applyable": outcome.decision == PolicyDecision.AUTO_APPLY,
        },
    )


@router.post("/import/items/{item_id}/apply")
async def apply_proposal(
    request: Request,
    item_id: UUID,
    current: CSRFProtected,
    session: SessionDep,
    author: Annotated[str, Form()] = "",
    title: Annotated[str, Form()] = "",
    series: Annotated[str, Form()] = "",
    series_index_raw: Annotated[str, Form()] = "",
    match_existing_work_id: Annotated[str, Form()] = "",
) -> RedirectResponse:
    """Apply the (possibly user-corrected) proposal."""
    service = _proposal_service(request)
    proposal = MatchProposal(
        author=author.strip() or None,
        title=title.strip() or None,
        series=series.strip() or None,
        series_index_raw=series_index_raw.strip() or None,
        match_existing_work_id=match_existing_work_id.strip() or None,
        confidence=1.0 if author or title else 0.0,
        requires_review=False,
        field_evidence={"source": "user_confirmed_form"},
    )
    corrected = proposal.author is not None  # user saw the form; treat as review step
    try:
        await service.apply_proposal(
            current.user.id,
            item_id,
            proposal,
            corrected=corrected,
        )
    except LookupError:
        pass
    return RedirectResponse("/library/import", status_code=303)


@router.post("/import/items/{item_id}/apply-auto")
async def apply_auto(
    item_id: UUID,
    current: CSRFProtected,
    request: Request,
) -> RedirectResponse:
    """Apply the cached proposal as-is (auto-apply decision)."""
    service = _proposal_service(request)
    try:
        outcome = await service.propose_for_item(current.user.id, item_id)
    except LookupError:
        return RedirectResponse("/library/import", status_code=303)
    if outcome.proposal is None or outcome.decision != PolicyDecision.AUTO_APPLY:
        return RedirectResponse(f"/library/import/items/{item_id}/propose", status_code=303)
    await service.apply_proposal(
        current.user.id,
        item_id,
        outcome.proposal,
        corrected=False,
    )
    return RedirectResponse("/library/import", status_code=303)
