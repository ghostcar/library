"""Integration: owner-scoped source links and inherited selection."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from portal.modules.library.adapters.source_orm import (
    SourceEndpointModel,
    SourceLinkModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.application.series_state_service import SeriesStateService
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


async def test_author_source_onboarding_creates_series_from_observation(
    client: httpx.AsyncClient,
) -> None:
    registered = await client.post(
        "/auth/register",
        json={"email": "onboarding@test.example", "password": "onboarding-pass-123"},
    )
    assert registered.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    owner_id = UUID(registered.json()["user"]["id"])
    container = client._transport.app.state.container

    async with container["session_factory"]() as session:
        author = AuthorModel(
            owner_id=owner_id,
            name="Автор наблюдения",
            name_normalized="автор наблюдения",
        )
        session.add(author)
        await session.commit()
        author_id = author.id

    invalid = await client.post(
        f"/library/authors/{author_id}/observe-author-today",
        data={"url": "https://example.com/u/test"},
    )
    assert invalid.status_code == 303
    assert invalid.headers["location"].endswith("?source_error=url")
    error_page = await client.get(invalid.headers["location"])
    assert "Нужна публичная страница автора" in error_page.text

    response = await client.post(
        f"/library/authors/{author_id}/observe-author-today",
        data={"url": "https://author.today/u/test"},
    )
    assert response.status_code == 303

    async with container["session_factory"]() as session:
        endpoint = (
            await session.execute(
                select(SourceEndpointModel).where(SourceEndpointModel.owner_id == owner_id)
            )
        ).scalar_one()
        rule = (
            await session.execute(select(WatchRuleModel).where(WatchRuleModel.owner_id == owner_id))
        ).scalar_one()
        author_link = (
            await session.execute(
                select(SourceLinkModel).where(
                    SourceLinkModel.owner_id == owner_id,
                    SourceLinkModel.entity_type == "author",
                )
            )
        ).scalar_one()
        assert endpoint.url == "https://author.today/u/test/works"
        assert rule.source_endpoint_id == endpoint.id
        assert author_link.entity_id == author_id
        session.add(
            SourceObservationModel(
                owner_id=owner_id,
                watch_rule_id=rule.id,
                adapter_id="author_today",
                external_id="author-today:work:777:revision:published",
                title="Первая книга цикла",
                author_name="Автор наблюдения",
                url="https://author.today/work/777",
                parser_version="author-today-public-v1",
                raw={
                    "work_id": "777",
                    "series": "Найденный цикл",
                    "series_url": "https://author.today/work/series/55",
                },
            )
        )
        session.add(
            SourceObservationModel(
                owner_id=owner_id,
                watch_rule_id=rule.id,
                adapter_id="author_today",
                external_id="author-today:work:777:revision:updated",
                title="Первая книга цикла",
                author_name="Автор наблюдения",
                url="https://author.today/work/777",
                parser_version="author-today-public-v1",
                raw={
                    "work_id": "777",
                    "series": "Найденный цикл",
                    "series_url": "https://author.today/work/series/55",
                },
            )
        )
        await session.commit()
        endpoint_id = endpoint.id

    page = await client.get(f"/library/authors/{author_id}")
    assert page.status_code == 200
    assert "Найденный цикл" in page.text
    assert "1 книг" in page.text

    forged = await client.post(
        f"/library/authors/{author_id}/series-candidates",
        data={"endpoint_id": str(endpoint_id), "name": "Подложный цикл"},
    )
    assert forged.status_code == 303
    async with container["session_factory"]() as session:
        assert (
            await session.execute(select(SeriesModel).where(SeriesModel.owner_id == owner_id))
        ).scalar_one_or_none() is None

    accepted = await client.post(
        f"/library/authors/{author_id}/series-candidates",
        data={"endpoint_id": str(endpoint_id), "name": "Найденный цикл"},
    )
    assert accepted.status_code == 303
    async with container["session_factory"]() as session:
        series = (
            await session.execute(select(SeriesModel).where(SeriesModel.owner_id == owner_id))
        ).scalar_one()
        series_link = (
            await session.execute(
                select(SourceLinkModel).where(
                    SourceLinkModel.owner_id == owner_id,
                    SourceLinkModel.entity_type == "series",
                )
            )
        ).scalar_one()
        observations = list(
            (
                await session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.owner_id == owner_id
                    )
                )
            ).scalars()
        )
        assert series.title == "Найденный цикл"
        assert series_link.entity_id == series.id
        assert series_link.external_url == "https://author.today/work/series/55"
        assert all(observation.series_id == series.id for observation in observations)

        present_work = WorkModel(
            owner_id=owner_id,
            title="Книга уже в каталоге",
            title_normalized="книга уже в каталоге",
        )
        assigned_work = WorkModel(
            owner_id=owner_id,
            title="Выбранная существующая книга",
            title_normalized="выбранная существующая книга",
        )
        session.add_all([present_work, assigned_work])
        await session.flush()
        rule_id = (
            await session.execute(
                select(WatchRuleModel.id).where(WatchRuleModel.owner_id == owner_id)
            )
        ).scalar_one()
        ambiguous_observation = SourceObservationModel(
            owner_id=owner_id,
            watch_rule_id=rule_id,
            adapter_id="author_today",
            external_id="author-today:work:999:revision:published",
            title="Неоднозначная книга",
            author_name="Автор наблюдения",
            url="https://author.today/work/999",
            parser_version="author-today-public-v1",
            series_id=series.id,
            match_evidence={"match": "ambiguous"},
            raw={"work_id": "999", "series": series.title},
        )
        session.add_all(
            [
                SourceObservationModel(
                    owner_id=owner_id,
                    watch_rule_id=rule_id,
                    adapter_id="author_today",
                    external_id="author-today:work:888:revision:published",
                    title=present_work.title,
                    author_name="Автор наблюдения",
                    url="https://author.today/work/888",
                    parser_version="author-today-public-v1",
                    work_id=present_work.id,
                    series_id=series.id,
                    match_evidence={"match": "exact_title_author"},
                    raw={"work_id": "888", "series": series.title},
                ),
                ambiguous_observation,
            ]
        )
        await session.commit()
        series_id = series.id
        assigned_work_id = assigned_work.id
        derived = await SeriesStateService(session).for_series(owner_id, series_id)
        assert derived is not None
        missing_observation_id = next(
            entry.observation_id
            for entry in derived.source_entries
            if entry.title == "Первая книга цикла"
        )
        ambiguous_observation_id = ambiguous_observation.id

    page = await client.get(f"/library/authors/{author_id}")
    assert "отслеживается" in page.text
    assert "Подключить наблюдение" not in page.text

    series_page = await client.get(f"/library/series/{series_id}")
    assert series_page.status_code == 200
    assert "КНИГИ У ИСТОЧНИКА (3)" in series_page.text
    assert "1 есть в каталоге" in series_page.text
    assert "1 нет в каталоге" in series_page.text
    assert "1 нужно уточнить" in series_page.text
    assert "Книга уже в каталоге" in series_page.text
    assert "Неоднозначная книга" in series_page.text
    assert "Найти в каталоге" in series_page.text
    assert 'id="source-work-' not in series_page.text

    picker = await client.get(
        f"/library/series/{series_id}/source-works/{missing_observation_id}/assign",
        params={"q": "Выбранная"},
    )
    assert picker.status_code == 200
    assert "Сопоставить книгу источника" in picker.text
    assert "Выбранная существующая книга" in picker.text
    assert "Название, автор или цикл" in picker.text
    assert "UUID" not in picker.text

    assigned = await client.post(
        f"/library/series/{series_id}/source-works/{missing_observation_id}/reconcile",
        data={"decision": "assign", "work_id": str(assigned_work_id)},
    )
    assert assigned.status_code == 303
    after_assign = await client.get(f"/library/series/{series_id}")
    assert "2 есть в каталоге" in after_assign.text
    assert "нет в каталоге" not in after_assign.text

    created = await client.post(
        f"/library/series/{series_id}/source-works/{ambiguous_observation_id}/reconcile",
        data={"decision": "create", "work_id": ""},
    )
    assert created.status_code == 303
    after_create = await client.get(f"/library/series/{series_id}")
    assert "3 есть в каталоге" in after_create.text
    assert "нужно уточнить" not in after_create.text

    async with container["session_factory"]() as session:
        created_work = (
            await session.execute(
                select(WorkModel).where(
                    WorkModel.owner_id == owner_id,
                    WorkModel.title_normalized == "неоднозначная книга",
                )
            )
        ).scalar_one()
        memberships = list(
            (
                await session.execute(
                    select(SeriesMembershipModel).where(
                        SeriesMembershipModel.owner_id == owner_id,
                        SeriesMembershipModel.series_id == series_id,
                        SeriesMembershipModel.work_id.in_([assigned_work_id, created_work.id]),
                    )
                )
            ).scalars()
        )
        reconciled_777 = list(
            (
                await session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.owner_id == owner_id,
                        SourceObservationModel.raw["work_id"].astext == "777",
                    )
                )
            ).scalars()
        )
        assert len(memberships) == 2
        assert len(reconciled_777) == 2
        assert all(row.work_id == assigned_work_id for row in reconciled_777)

    blocked = await client.post(
        f"/library/authors/{author_id}/sources",
        data={"profile_id": "litnet", "url": "https://litnet.com/ru/example"},
    )
    assert blocked.status_code == 303
    assert blocked.headers["location"].endswith("?source_error=profile")
    blocked_page = await client.get(blocked.headers["location"])
    assert "Этот профиль или URL нельзя подключить" in blocked_page.text

    linked = await client.post(
        f"/library/authors/{author_id}/sources",
        data={"profile_id": "website_link", "url": "https://writer.example/books"},
    )
    assert linked.status_code == 303
    linked_page = await client.get(f"/library/authors/{author_id}")
    assert "writer.example/books" in linked_page.text
    assert "без фонового опроса" in linked_page.text

    async with container["session_factory"]() as session:
        website_endpoint = (
            await session.execute(
                select(SourceEndpointModel).where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.adapter_id == "html",
                )
            )
        ).scalar_one()
        website_link = (
            await session.execute(
                select(SourceLinkModel).where(
                    SourceLinkModel.owner_id == owner_id,
                    SourceLinkModel.source_endpoint_id == website_endpoint.id,
                    SourceLinkModel.entity_type == "author",
                )
            )
        ).scalar_one()
        rules = list(
            (
                await session.execute(
                    select(WatchRuleModel).where(WatchRuleModel.owner_id == owner_id)
                )
            ).scalars()
        )
        assert website_link.external_url == "https://writer.example/books"
        assert len(rules) == 1

    for _ in range(2):
        opds_connected = await client.post(
            "/library/sources/opds",
            data={
                "name": "Семейный OPDS",
                "adapter_id": "opds",
                "url": "https://books.example/opds",
                "interval_minutes": "15",
            },
        )
        assert opds_connected.status_code == 303

    sources_page = await client.get("/library/sources")
    assert sources_page.status_code == 200
    assert "НАБЛЮДАЕМЫЕ OPDS" in sources_page.text
    assert "НАБЛЮДАЕМЫЕ САЙТЫ" in sources_page.text
    assert "Семейный OPDS" in sources_page.text

    async with container["session_factory"]() as session:
        opds_endpoint = (
            await session.execute(
                select(SourceEndpointModel).where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.adapter_id == "opds",
                )
            )
        ).scalar_one()
        opds_rule = (
            await session.execute(
                select(WatchRuleModel).where(
                    WatchRuleModel.owner_id == owner_id,
                    WatchRuleModel.source_endpoint_id == opds_endpoint.id,
                )
            )
        ).scalar_one()
        assert opds_endpoint.role == "metadata+acquisition"
        assert opds_rule.interval_seconds == 900
        opds_endpoint_id = opds_endpoint.id

    disabled = await client.post(
        f"/library/sources/endpoints/{opds_endpoint_id}/toggle",
        data={"enabled": "false"},
    )
    assert disabled.status_code == 303
    async with container["session_factory"]() as session:
        assert not (await session.get(SourceEndpointModel, opds_endpoint_id)).enabled
        disabled_rule = (
            await session.execute(
                select(WatchRuleModel).where(WatchRuleModel.source_endpoint_id == opds_endpoint_id)
            )
        ).scalar_one()
        assert not disabled_rule.enabled
        assert disabled_rule.next_poll_at is None

    deleted = await client.post(f"/library/sources/endpoints/{opds_endpoint_id}/delete")
    assert deleted.status_code == 303
    async with container["session_factory"]() as session:
        assert await session.get(SourceEndpointModel, opds_endpoint_id) is None
        assert (
            await session.execute(
                select(WatchRuleModel).where(WatchRuleModel.source_endpoint_id == opds_endpoint_id)
            )
        ).scalar_one_or_none() is None
