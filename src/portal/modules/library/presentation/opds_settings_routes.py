"""OPDS access page: device tokens (create once, list, revoke)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import CSRFProtected, CurrentUser, SessionDep
from portal.core.auth.service import AuthService

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


def _auth_service(request: Request) -> AuthService:
    service: AuthService = request.app.state.container["auth_service"]
    return service


async def _render_settings(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
    *,
    created_token: str | None = None,
) -> HTMLResponse:
    auth = _auth_service(request)
    tokens = await auth.list_device_tokens(current.user)
    return _templates.TemplateResponse(
        request,
        "opds_settings.html",
        {
            "user": current.user,
            "title": "OPDS-доступ — Библиотека",
            "tokens": [
                {
                    "id": t.id,
                    "name": t.name,
                    "created_at": t.created_at,
                    "expires_at": t.expires_at,
                    "revoked": t.revoked_at is not None,
                }
                for t in tokens
            ],
            "created_token": created_token,
        },
    )


@router.get("/opds-settings", response_class=HTMLResponse)
async def opds_settings(
    request: Request,
    current: CurrentUser,
    session: SessionDep,
) -> HTMLResponse:
    return await _render_settings(request, current, session)


@router.post("/opds-settings/tokens")
async def create_device_token(
    request: Request,
    current: CSRFProtected,
    session: SessionDep,
    name: Annotated[str, Form()],
) -> HTMLResponse:
    auth = _auth_service(request)
    created = await auth.create_device_token(
        current.user,
        name.strip()[:64] or "Читалка",
        ["library:opds:read"],
    )
    # the raw token is displayed exactly once, never stored in plaintext
    return await _render_settings(
        request,
        current,
        session,
        created_token=created.raw_token,
    )


@router.post("/opds-settings/tokens/{token_id}/revoke")
async def revoke_device_token(
    token_id: UUID,
    request: Request,
    current: CSRFProtected,
) -> RedirectResponse:
    auth = _auth_service(request)
    await auth.revoke_device_token(current.user, token_id)
    return RedirectResponse("/library/opds-settings", status_code=303)
