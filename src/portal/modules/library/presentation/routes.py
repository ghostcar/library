"""Library module presentation routes (HTML/HTMX-first, JSON for tooling)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from portal.core.auth.dependencies import OptionalUser

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


@router.get("/", response_class=HTMLResponse)
async def library_index(request: Request, current: OptionalUser) -> Response:
    if current is None:
        return RedirectResponse("/login", status_code=303)
    return _templates.TemplateResponse(
        request,
        "library_index.html",
        {"user": current.user, "title": "Библиотека"},
    )


@router.get("/info")
async def library_info(request: Request) -> dict[str, object]:
    registry = request.app.state.registry
    return {
        "module": "library",
        "enabled": registry.is_enabled("library"),
        "version": "0.1.0",
    }
