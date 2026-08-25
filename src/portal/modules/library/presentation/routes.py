"""Library module presentation routes (HTML/HTMX-first, JSON for tooling)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def library_index(request: Request) -> HTMLResponse:
    registry = request.app.state.registry
    enabled = registry.is_enabled("library")
    return HTMLResponse(
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<title>Библиотека</title></head><body>"
        "<h1>Библиотека</h1>"
        f"<p>Модуль зарегистрирован: {enabled}</p>"
        "</body></html>",
    )


@router.get("/info")
async def library_info(request: Request) -> dict[str, object]:
    registry = request.app.state.registry
    return {
        "module": "library",
        "enabled": registry.is_enabled("library"),
        "version": "0.1.0",
    }
