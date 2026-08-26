"""Library module presentation routes (HTML/HTMX-first, JSON for tooling)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()

_templates = Jinja2Templates(
    directory=[
        str(Path(__file__).resolve().parents[1] / "templates"),
        str(Path(__file__).resolve().parents[3] / "web" / "templates"),
    ],
)


@router.get("/info")
async def library_info(request: Request) -> dict[str, object]:
    registry = request.app.state.registry
    return {
        "module": "library",
        "enabled": registry.is_enabled("library"),
        "version": "0.1.0",
    }
