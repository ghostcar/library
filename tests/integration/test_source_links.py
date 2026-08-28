"""Integration: owner-scoped source links and inherited selection."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from portal.modules.library.adapters.source_orm import SourceEndpointModel
from portal.modules.library.application.source_link_service import SourceLinkService
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    SeriesModel,
    WorkAuthorModel,
    WorkModel,
)

pytestmark = pytest.mark.integration


async def test_source_resolution_precedence_and_owner_scope(db_session, db_owner) -> None:
    author = AuthorModel(owner_id=db_owner, name="Автор", name_normalized="автор")
    series = SeriesModel(owner_id=db_owner, title="Цикл", title_normalized="цикл")
    work = WorkModel(owner_id=db_owner, title="Книга", title_normalized="книга")
    metadata = SourceEndpointModel(
        owner_id=db_owner,
        name="Официальный сайт",
        source_type="html",
        role="metadata",
        adapter_id="html",
        url="https://author.example/",
    )
    files = SourceEndpointModel(
        owner_id=db_owner,
        name="OPDS",
        source_type="opds",
        role="acquisition",
        adapter_id="opds",
        url="https://files.example/opds",
    )
    db_session.add_all([author, series, work, metadata, files])
    await db_session.flush()
    db_session.add_all(
        [
            WorkAuthorModel(owner_id=db_owner, work_id=work.id, author_id=author.id),
            SeriesMembershipModel(
                owner_id=db_owner,
                series_id=series.id,
                work_id=work.id,
                index_raw="1",
            ),
        ]
    )
    await db_session.flush()

    service = SourceLinkService(db_session)
    assert await service.add(
        db_owner,
        endpoint_id=metadata.id,
        entity_type="author",
        entity_id=author.id,
        role="metadata",
        external_url="https://author.example/books",
        preferred=True,
    )
    assert await service.add(
        db_owner,
        endpoint_id=files.id,
        entity_type="series",
        entity_id=series.id,
        role="acquisition",
        external_url="https://files.example/series/1",
    )

    resolved = await service.resolved(db_owner, "work", work.id)
    assert [(item["role"], item["inherited_from"]) for item in resolved] == [
        ("metadata", "author"),
        ("acquisition", "series"),
    ]
    assert all(item["direct"] is False for item in resolved)
    assert await service.resolved(uuid4(), "work", work.id) == []

    assert await service.add(
        db_owner,
        endpoint_id=metadata.id,
        entity_type="work",
        entity_id=work.id,
        role="metadata",
        external_url="https://author.example/book",
        preferred=True,
    )
    resolved = await service.resolved(db_owner, "work", work.id)
    work_metadata = next(item for item in resolved if item["role"] == "metadata")
    assert work_metadata["inherited_from"] == "work"
    assert work_metadata["direct"] is True


async def test_source_link_rejects_foreign_entity_and_unsafe_url(db_session, db_owner) -> None:
    endpoint = SourceEndpointModel(
        owner_id=db_owner,
        name="OPDS",
        source_type="opds",
        role="metadata+acquisition",
        adapter_id="opds",
        url="https://example.test/opds",
    )
    db_session.add(endpoint)
    await db_session.flush()
    service = SourceLinkService(db_session)

    assert not await service.add(
        db_owner,
        endpoint_id=endpoint.id,
        entity_type="work",
        entity_id=uuid4(),
        role="metadata",
        external_url=None,
    )
    work = WorkModel(owner_id=db_owner, title="Книга", title_normalized="книга")
    db_session.add(work)
    await db_session.flush()
    assert not await service.add(
        db_owner,
        endpoint_id=endpoint.id,
        entity_type="work",
        entity_id=work.id,
        role="metadata",
        external_url="javascript:alert(1)",
    )


async def test_source_management_http_flow(client: httpx.AsyncClient) -> None:
    registered = await client.post(
        "/auth/register",
        json={"email": "source-ui@test.example", "password": "source-ui-pass-123"},
    )
    assert registered.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    owner_id = UUID(registered.json()["user"]["id"])

    container = client._transport.app.state.container
    async with container["session_factory"]() as session:
        author = AuthorModel(owner_id=owner_id, name="Автор UI", name_normalized="автор ui")
        series = SeriesModel(owner_id=owner_id, title="Цикл UI", title_normalized="цикл ui")
        work = WorkModel(owner_id=owner_id, title="Книга UI", title_normalized="книга ui")
        session.add_all([author, series, work])
        await session.flush()
        session.add_all(
            [
                WorkAuthorModel(owner_id=owner_id, work_id=work.id, author_id=author.id),
                SeriesMembershipModel(
                    owner_id=owner_id,
                    series_id=series.id,
                    work_id=work.id,
                    index_raw="1",
                ),
            ]
        )
        await session.commit()
        author_id, series_id, work_id = author.id, series.id, work.id

    response = await client.post(
        "/library/sources/endpoints",
        data={
            "name": "Официальный сайт",
            "source_type": "html",
            "role": "metadata",
            "adapter_id": "html",
            "url": "https://author.example/",
        },
    )
    assert response.status_code == 303
    async with container["session_factory"]() as session:
        endpoint = (
            await session.execute(
                select(SourceEndpointModel).where(SourceEndpointModel.owner_id == owner_id)
            )
        ).scalar_one()
        endpoint_id = endpoint.id

    response = await client.post(
        "/library/sources/links",
        data={
            "endpoint_id": str(endpoint_id),
            "entity_type": "author",
            "entity_id": str(author_id),
            "role": "metadata",
            "external_url": "https://author.example/books",
            "preferred": "true",
            "back": f"/library/authors/{author_id}",
        },
    )
    assert response.status_code == 303

    author_page = await client.get(f"/library/authors/{author_id}")
    assert author_page.status_code == 200
    assert "Автор UI" in author_page.text
    assert "Официальный сайт" in author_page.text
    assert "основной" in author_page.text

    series_page = await client.get(f"/library/series/{series_id}")
    assert series_page.status_code == 200
    assert "унаследован: author" in series_page.text
    work_page = await client.get(f"/library/works/{work_id}")
    assert work_page.status_code == 200
    assert "релиз отслеживается" in work_page.text
    assert "унаследован: author" in work_page.text

    response = await client.post(
        f"/library/sources/endpoints/{endpoint_id}/toggle",
        data={"enabled": "false"},
    )
    assert response.status_code == 303
    work_page = await client.get(f"/library/works/{work_id}")
    assert "Официальный сайт" not in work_page.text
