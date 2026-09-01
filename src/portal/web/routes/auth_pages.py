"""Minimal SSR auth pages (login). Full UI shell arrives with Tailwind setup."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import (
    CSRF_COOKIE,
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


def _safe_next(value: str) -> str:
    return value if value.startswith("/library") and not value.startswith("//") else "/library/"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    next_path = _safe_next(request.query_params.get("next", "/library/"))
    response = _templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "title": "Вход — Библиотека", "next_path": next_path},
    )
    issue_csrf_cookie(request, response)
    return response


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    response: Response,
    username: str = Form(),
    password: str = Form(),
    next_path: str = Form("/library/", alias="next"),
    auth: AuthServiceDep = None,  # type: ignore[assignment]
    settings: SettingsDep = None,  # type: ignore[assignment]
) -> Response:
    target = _safe_next(next_path)
    limiters: dict[str, RateLimiter] = request.app.state.container["rate_limiters"]
    ip = request.client.host if request.client else "unknown"
    if not limiters["login"].check(f"login:{ip}:{username}"):
        return _templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Слишком много попыток, подождите",
                "title": "Вход",
                "next_path": target,
            },
        )
    try:
        result = await auth.login(username, password, actor_ip=ip)
    except InvalidCredentialsError:
        return _templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный email или пароль", "title": "Вход", "next_path": target},
        )
    redirect = RedirectResponse(target, status_code=303)
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
    # CSRF double-submit: cookie must match hidden form field.
    cookie_token = request.cookies.get(CSRF_COOKIE)
    form = await request.form()
    form_token: str | None = form.get("csrf_token")  # type: ignore[assignment]
    if cookie_token and form_token and cookie_token != form_token:
        from fastapi import HTTPException
        from fastapi import status as _status

        raise HTTPException(status_code=_status.HTTP_403_FORBIDDEN, detail="CSRF check failed")
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is not None:
        await auth.logout(raw, actor_ip=request.client.host if request.client else None)
    redirect = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(redirect)
    return redirect
