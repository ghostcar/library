"""Integration: manual source refresh and owner-scoped service console."""

from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select

from portal.core.jobs.orm import JobModel
from portal.modules.library.adapters.source_orm import WatchRuleModel
from portal.modules.library.infrastructure.orm import AuthorModel

pytestmark = pytest.mark.integration


async def test_manual_refresh_is_deduplicated_and_visible(client: httpx.AsyncClient) -> None:
    registered = await client.post(
        "/auth/register",
        json={"email": "service@test.example", "password": "service-test-pass-123"},
    )
    assert registered.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    owner_id = UUID(registered.json()["user"]["id"])
    container = client._transport.app.state.container

    async with container["session_factory"]() as session:
        author = AuthorModel(owner_id=owner_id, name="Автор", name_normalized="автор")
        session.add(author)
        await session.commit()
        author_id = author.id

    connected = await client.post(
        f"/library/authors/{author_id}/observe-author-today",
        data={"url": "https://author.today/u/test"},
    )
    assert connected.status_code == 303

    first = await client.post(f"/library/authors/{author_id}/refresh-author-source")
    second = await client.post(f"/library/authors/{author_id}/refresh-author-source")
    assert first.headers["location"].endswith("?refresh=queued")
    assert second.headers["location"].endswith("?refresh=queued")

    async with container["session_factory"]() as session:
        rule_id = (
            await session.execute(
                select(WatchRuleModel.id).where(WatchRuleModel.owner_id == owner_id)
            )
        ).scalar_one()
        count = await session.scalar(
            select(func.count())
            .select_from(JobModel)
            .where(
                JobModel.kind == "poll_watch",
                JobModel.payload["owner_id"].astext == str(owner_id),
                JobModel.payload["watch_rule_id"].astext == str(rule_id),
            )
        )
        assert count == 1
        session.add(
            JobModel(
                kind="foreign-secret-job",
                payload={"owner_id": str(uuid4())},
            )
        )
        await session.commit()

    author_page = await client.get(f"/library/authors/{author_id}")
    assert author_page.status_code == 200
    assert "обновление в очереди" in author_page.text
    assert "Проверить сейчас" in author_page.text

    service_page = await client.get("/library/service")
    assert service_page.status_code == 200
    assert "ОЧЕРЕДЬ ЗАДАНИЙ" in service_page.text
    assert "poll_watch" in service_page.text
    assert "НАБЛЮДЕНИЕ ЗА ИСТОЧНИКАМИ" in service_page.text
    assert "foreign-secret-job" not in service_page.text
