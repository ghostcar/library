"""Integration E2E: reading state flow — transitions, history, series next, queue."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portal.modules.library.application.reading_service import (
    ReadingStateService,
)
from portal.modules.library.application.series_state_service import (
    SeriesStateService,
)
from portal.modules.library.domain.enums import ReadingStatus

pytestmark = pytest.mark.integration

EMAIL = "reader@test.example"
PASSWORD = "reader-test-pass-123"  # noqa: S105 - synthetic test credential


@pytest.fixture
async def authed(client: httpx.AsyncClient) -> tuple[httpx.AsyncClient, UUID]:
    response = await client.post(
        "/auth/register",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    owner = UUID((await client.get("/auth/me")).json()["id"])
    return client, owner


async def _create_series_with_books(
    session_factory,
    owner: UUID,
    title: str,
    indices: list[str],
) -> UUID:
    """Deterministic series setup via CatalogService."""
    from portal.modules.library.application.services import CatalogService, RegisterWorkInput
    from portal.modules.library.infrastructure.repositories import (
        AuthorRepository,
        SeriesRepository,
        WorkRepository,
    )

    work_ids: list[UUID] = []
    async with session_factory() as session, session.begin():
        catalog = CatalogService(
            works=WorkRepository(session),
            authors=AuthorRepository(session),
            series=SeriesRepository(session),
        )
        for index in indices:
            work = await catalog.register_work(
                RegisterWorkInput(
                    owner_id=owner,
                    title=f"{title} {index}",
                    author_names=[f"Автор {title}"],
                    series_title=title,
                    series_index_raw=index,
                ),
            )
            work_ids.append(work.id)
    return work_ids[0], work_ids


async def _series_id_for(factory, owner: UUID) -> UUID:
    from sqlalchemy import select

    from portal.modules.library.infrastructure.orm import SeriesModel

    async with factory() as session:
        return (
            await session.execute(
                select(SeriesModel.id).where(SeriesModel.owner_id == owner),
            )
        ).scalar_one()


def _services(client: httpx.AsyncClient):
    container = client._transport.app.state.container
    return (
        ReadingStateService(container["session_factory"]),
        container["session_factory"],
    )


class TestReadingFlow:
    async def test_mark_read_updates_series_next(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _first, work_ids = await _create_series_with_books(
            factory,
            owner,
            "Эпоха",
            ["1", "2", "3"],
        )

        await reading_service.set_status(owner, work_ids[0], ReadingStatus.READ)
        series_id = await _series_id_for(factory, owner)

        async with factory() as session:
            state = await SeriesStateService(session).for_series(owner, series_id)
        assert state is not None
        assert state.series_status == "in_progress"
        assert state.next_available_unread is not None
        assert state.next_available_unread.work_id == work_ids[1]

        # read book 2 -> next becomes 3
        await reading_service.set_status(owner, work_ids[1], ReadingStatus.READ)
        async with factory() as session:
            state = await SeriesStateService(session).for_series(owner, series_id)
        assert state is not None
        assert state.next_available_unread is not None
        assert state.next_available_unread.work_id == work_ids[2]
        assert state.last_read is not None
        assert state.last_read.work_id == work_ids[1]

    async def test_caught_up_when_all_read(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Цикл", ["1", "2"])

        for work_id in work_ids:
            await reading_service.set_status(owner, work_id, ReadingStatus.READ)
        series_id = await _series_id_for(factory, owner)

        async with factory() as session:
            state = await SeriesStateService(session).for_series(owner, series_id)
        assert state is not None
        assert state.series_status == "caught_up"
        assert state.next_available_unread is None

    async def test_history_recorded(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "История", ["1"])

        await reading_service.set_status(owner, work_ids[0], ReadingStatus.READING)
        await reading_service.set_status(owner, work_ids[0], ReadingStatus.READ)

        history = await reading_service.history_for_work(owner, work_ids[0])
        assert len(history) == 2
        assert history[0]["from_status"] == "reading"
        assert history[0]["to_status"] == "read"
        assert history[1]["from_status"] is None
        assert history[1]["to_status"] == "reading"

    async def test_illegal_transition_rejected(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Нелегал", ["1"])

        with pytest.raises(ValueError, match="illegal"):
            await reading_service.set_status(owner, work_ids[0], ReadingStatus.PAUSED)

    async def test_bulk_mark_read(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Масса", ["1", "2", "3"])

        changes = await reading_service.mark_read_bulk(owner, work_ids)
        assert len(changes) == 3
        series_id = await _series_id_for(factory, owner)

        async with factory() as session:
            state = await SeriesStateService(session).for_series(owner, series_id)
        assert state is not None
        assert state.series_status == "caught_up"

    async def test_owner_isolation(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Чужое", ["1"])

        with pytest.raises(LookupError):
            await reading_service.set_status(uuid4(), work_ids[0], ReadingStatus.READ)


class TestQueue:
    async def test_queue_next_in_series_first_then_standalone(
        self,
        authed,
    ) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        series_first, series_works = await _create_series_with_books(
            factory,
            owner,
            "Активный цикл",
            ["1", "2"],
        )
        standalone = await _create_series_with_books(factory, owner, "Одиночка", ["1"])

        # read first book of series -> series becomes in_progress
        await reading_service.set_status(owner, series_first, ReadingStatus.READ)

        queue = await reading_service.reading_queue(owner)
        assert queue, "queue must not be empty"

        reasons = [q["reason"] for q in queue]
        assert "next_in_series" in reasons  # active series first
        assert queue[0]["reason"] == "next_in_series"
        assert queue[0]["work_id"] == series_works[1]
        # the planned series' first book is queued too
        assert any(q["work_id"] == standalone[0] for q in queue)

    async def test_queue_empty_when_all_read(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Всё", ["1"])
        await reading_service.set_status(owner, work_ids[0], ReadingStatus.READ)

        queue = await reading_service.reading_queue(owner)
        assert all(q["work_id"] != work_ids[0] for q in queue)


class TestHTTPActions:
    async def test_status_button_via_http(self, authed) -> None:
        client, owner = authed
        reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Кнопка", ["1"])

        response = await client.post(
            f"/library/works/{work_ids[0]}/status",
            data={"status": "reading", "back": "/library/"},
        )
        assert response.status_code == 303

        history = await reading_service.history_for_work(owner, work_ids[0])
        assert history and history[0]["to_status"] == "reading"

        dashboard = await client.get("/library/")
        assert "Кнопка 1" in dashboard.text  # continue reading section

    async def test_series_page_renders_timeline(self, authed) -> None:
        client, owner = authed
        _reading_service, factory = _services(client)
        _f, _work_ids = await _create_series_with_books(factory, owner, "Таймлайн", ["1", "2", "5"])

        series_id = await _series_id_for(factory, owner)

        page = await client.get(f"/library/series/{series_id}")
        assert page.status_code == 200
        assert "СЛЕДУЮЩАЯ КНИГА ЦИКЛА" in page.text
        assert "пропущены: №3, №4" in page.text
        assert "статус: planned" in page.text

    async def test_series_user_override_via_http(self, authed) -> None:
        client, owner = authed
        _reading_service, factory = _services(client)
        _f, _work_ids = await _create_series_with_books(factory, owner, "Оверрайд", ["1"])

        series_id = await _series_id_for(factory, owner)

        response = await client.post(
            f"/library/series/{series_id}/user-status",
            data={"status": "paused"},
        )
        assert response.status_code == 303
        page = await client.get(f"/library/series/{series_id}")
        assert "статус: paused" in page.text

    async def test_bulk_via_http(self, authed) -> None:
        client, owner = authed
        _reading_service, factory = _services(client)
        _f, work_ids = await _create_series_with_books(factory, owner, "Булк", ["1", "2"])

        response = await client.post(
            "/library/works/status/bulk",
            data={"work_ids": [str(w) for w in work_ids], "status": "read"},
        )
        assert response.status_code == 303
        series_id = await _series_id_for(factory, owner)

        async with factory() as session:
            state = await SeriesStateService(session).for_series(owner, series_id)
        assert state is not None
        assert state.series_status == "caught_up"
