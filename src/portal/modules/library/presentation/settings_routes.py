"""User settings: change password."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import (
    CSRF_COOKIE,
    CSRFProtected,
    CurrentUser,
    clear_auth_cookies,
)
from portal.core.auth.service import AuthService, InvalidCredentialsError
from portal.web.deps import SessionDep

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


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, current: CurrentUser) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": current.user,
            "title": "Настройки — Библиотека",
            "error": None,
            "success": False,
            "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
        },
    )


@router.post("/settings/password", response_model=None)
async def change_password(
    request: Request,
    current: CSRFProtected,
    session: SessionDep,
    old_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
) -> HTMLResponse | RedirectResponse:
    auth = _auth_service(request)
    ip = request.client.host if request.client else None
    try:
        await auth.change_password(
            current.user,
            old_password,
            new_password,
            actor_ip=ip,
        )
    except InvalidCredentialsError:
        return _templates.TemplateResponse(
            request,
            "settings.html",
            {
                "user": current.user,
                "title": "Настройки — Библиотека",
                "error": "Неверный текущий пароль или новый короче 12 символов",
                "success": False,
                "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            },
            status_code=400,
        )
    # Refresh tokens revoked → force re-login; device tokens (FBReader) stay.
    response = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(response)
    return response
