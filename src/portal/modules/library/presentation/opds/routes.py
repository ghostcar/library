"""OPDS 1.2 routes (master prompt 10.1): catalog for FBReader."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.storage.local import StorageError
from portal.modules.library.application.opds_catalog_service import OpdsCatalogService
from portal.modules.library.domain import entities as de
from portal.modules.library.infrastructure.orm import AssetModel
from portal.modules.library.presentation.opds import serializer as ser
from portal.modules.library.presentation.opds_auth import OpdsDevice
from portal.web.deps import SessionDep

router = APIRouter(prefix="/opds")

_XML = "application/atom+xml;profile=opds-catalog;kind=navigation"
_ACQ_XML = "application/atom+xml;profile=opds-catalog;kind=acquisition"


def _nav_response(
    feed_id: str,
    title: str,
    self_href: str,
    entries: list[dict[str, Any]],
    search: bool = True,
) -> Response:
    body = ser.navigation_feed(
        feed_id=feed_id,
        title=title,
        self_href=self_href,
        entries=entries,
        search=search,
    )
    return Response(content=body, media_type=_XML)


def _acq_response(
    feed_id: str,
    title: str,
    self_href: str,
    entries: list[dict[str, Any]],
    links: list[dict[str, str]] | None = None,
) -> Response:
    body = ser.acquisition_feed(
        feed_id=feed_id,
        title=title,
        self_href=self_href,
        entries=entries,
        links=links,
    )
    return Response(content=body, media_type=_ACQ_XML)


@router.get("")
@router.get("/")
async def root_catalog(current: OpdsDevice) -> Response:
    entries = [
        {"id": "urn:library:nav:new", "title": "Новые книги", "href": "/opds/new"},
        {"id": "urn:library:nav:unread", "title": "Непрочитанные", "href": "/opds/unread"},
        {"id": "urn:library:nav:series", "title": "Циклы", "href": "/opds/series"},
        {"id": "urn:library:nav:authors", "title": "Авторы", "href": "/opds/authors"},
        {
            "id": "urn:library:nav:observations",
            "title": "Новые продолжения (наблюдения)",
            "href": "/opds/observations",
        },
    ]
    return _nav_response("urn:library:root", "Моя библиотека", "/opds", entries)


@router.get("/new")
async def new_books(current: OpdsDevice, session: SessionDep) -> Response:
    entries = await OpdsCatalogService(session).recent(current.user.id)
    return _acq_response("urn:library:new", "Новые книги", "/opds/new", entries)


@router.get("/unread")
async def unread_books(current: OpdsDevice, session: SessionDep) -> Response:
    entries = await OpdsCatalogService(session).unread(current.user.id)
    return _acq_response("urn:library:unread", "Непрочитанные", "/opds/unread", entries)


@router.get("/series")
async def series_list(current: OpdsDevice, session: SessionDep) -> Response:
    rows = await OpdsCatalogService(session).series_list(current.user.id)
    entries = [
        {
            "id": f"urn:library:series:{row['id']}",
            "title": str(row["title"]),
            "content": f"{row['count']} книг",
            "href": f"/opds/series/{row['id']}",
            "entry_type": _ACQ_XML,
        }
        for row in rows
    ]
    return _nav_response("urn:library:series", "Циклы", "/opds/series", entries)


@router.get("/series/{series_id}")
async def series_feed(series_id: UUID, current: OpdsDevice, session: SessionDep) -> Response:
    entries = await OpdsCatalogService(session).series_works(current.user.id, series_id)
    if entries is None:
        return Response(status_code=404)
    feed_title = str(entries[0]["series"]) if entries and entries[0].get("series") else "Цикл"
    return _acq_response(
        f"urn:library:series:{series_id}",
        feed_title,
        f"/opds/series/{series_id}",
        entries,
    )


@router.get("/authors")
async def authors_list(current: OpdsDevice, session: SessionDep) -> Response:
    rows = await OpdsCatalogService(session).authors_list(current.user.id)
    entries = [
        {
            "id": f"urn:library:author:{row['id']}",
            "title": str(row["title"]),
            "content": f"{row['count']} произведений",
            "href": f"/opds/authors/{row['id']}",
            "entry_type": _ACQ_XML,
        }
        for row in rows
    ]
    return _nav_response("urn:library:authors", "Авторы", "/opds/authors", entries)


@router.get("/authors/{author_id}")
async def author_feed(author_id: UUID, current: OpdsDevice, session: SessionDep) -> Response:
    entries = await OpdsCatalogService(session).author_works(current.user.id, author_id)
    if entries is None:
        return Response(status_code=404)
    first_authors: list[str] = entries[0].get("authors", []) if entries else []  # type: ignore[assignment]
    feed_title = str(first_authors[0]) if first_authors else "Автор"
    return _acq_response(
        f"urn:library:author:{author_id}",
        feed_title,
        f"/opds/authors/{author_id}",
        entries,
    )


@router.get("/observations")
async def observations_feed(current: OpdsDevice, session: SessionDep) -> Response:
    entries = await OpdsCatalogService(session).observations(current.user.id)
    links = []
    for entry in entries:
        url = entry.get("source_url")
        if url:
            links.append({"rel": "related", "href": str(url), "type": "text/html"})
    return _acq_response(
        "urn:library:observations",
        "Новые продолжения (наблюдения)",
        "/opds/observations",
        entries,
        links=links,
    )


@router.get("/search.xml")
async def opensearch_description() -> Response:
    return Response(
        content=ser.opensearch_description(),
        media_type="application/opensearchdescription+xml",
    )


@router.get("/search")
async def search(current: OpdsDevice, session: SessionDep, q: str = "") -> Response:
    if not q.strip():
        return _acq_response("urn:library:search", "Поиск", "/opds/search", [])
    entries = await OpdsCatalogService(session).search(current.user.id, q)
    return _acq_response(
        "urn:library:search",
        f"Поиск: {q}",
        f"/opds/search?q={q}",
        entries,
    )


@router.get("/download/{asset_id}")
async def download_asset(
    asset_id: UUID,
    current: OpdsDevice,
    session: SessionDep,
    request: Request,
) -> Response:
    """Owner-scoped download with human-readable Content-Disposition (§6.2)."""

    asset = await session.get(AssetModel, asset_id)
    if asset is None or asset.owner_id != current.user.id:
        return Response(status_code=404)

    storage = request.app.state.container["storage"]
    try:
        path = storage._resolve(asset.storage_path)
    except StorageError:
        return Response(status_code=404)

    from portal.modules.library.infrastructure.mappers import asset_to_domain

    filename = await _human_name(session, current.user.id, asset_to_domain(asset))
    return FileResponse(path, media_type="application/octet-stream", filename=filename)


async def _human_name(session: AsyncSession, owner_id: UUID, asset: de.Asset) -> str:
    from portal.modules.library.presentation.normalization_routes import (
        _human_readable_name,
    )

    return await _human_readable_name(session, owner_id, asset)
