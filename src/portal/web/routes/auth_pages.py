"""Minimal SSR auth pages (login). Full UI shell arrives with Tailwind setup."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import (
    REFRESH_COOKIE,
    AuthServiceDep,
    SettingsDep,
    clear_auth_cookies,
    issue_csrf_cookie,
    set_auth_cookies,
)
from portal.core.auth.rate_limit import RateLimiter
from portal.core.auth.service import InvalidCredentialsError

router = APIRouter(tags=["auth-pages"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates"),
)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    response = _templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "title": "Вход — Библиотека"},
    )
    issue_csrf_cookie(request, response)
    return response


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    response: Response,
    username: str = Form(),
    password: str = Form(),
    auth: AuthServiceDep = None,  # type: ignore[assignment]
    settings: SettingsDep = None,  # type: ignore[assignment]
) -> Response:
    limiters: dict[str, RateLimiter] = request.app.state.container["rate_limiters"]
    ip = request.client.host if request.client else "unknown"
    if not limiters["login"].check(f"login:{ip}:{username}"):
        return _templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Слишком много попыток, подождите", "title": "Вход"},
        )
    try:
        result = await auth.login(username, password, actor_ip=ip)
    except InvalidCredentialsError:
        return _templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный email или пароль", "title": "Вход"},
        )
    redirect = RedirectResponse("/library/", status_code=303)
    set_auth_cookies(
        redirect,
        settings,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=result.refresh_expires_at,
    )
    issue_csrf_cookie(request, redirect)
    return redirect


@router.post("/logout")
async def logout_submit(
    request: Request,
    auth: AuthServiceDep = None,  # type: ignore[assignment]
) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is not None:
        await auth.logout(raw, actor_ip=request.client.host if request.client else None)
    redirect = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(redirect)
    return redirect
