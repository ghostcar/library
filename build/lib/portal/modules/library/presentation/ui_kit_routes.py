"""Dev-only UI kit page (master prompt 11.1.7). Not mounted outside development."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


@router.get("/ui-kit", response_class=HTMLResponse)
async def ui_kit(request: Request) -> HTMLResponse:
    settings = request.app.state.settings
    if not settings.is_dev:
        return HTMLResponse("UI kit is available in development only", status_code=404)
    return _templates.TemplateResponse(
        request,
        "ui_kit.html",
        {"title": "UI Kit — Ghostcar"},
    )
