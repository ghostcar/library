"""Integration: watch rule poll flow against a fake OPDS server."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request, Response
from sqlalchemy import select

from portal.modules.library.adapters.author_today_adapter import (
    PARSER_VERSION as AUTHOR_TODAY_PARSER_VERSION,
)
from portal.modules.library.adapters.author_today_adapter import AuthorTodayAdapter
from portal.modules.library.adapters.opds_adapter import OPDSAdapter
from portal.modules.library.adapters.source_orm import (
    SourceEndpointModel,
    SourceObservationModel,
)
from portal.modules.library.adapters.watch_service import WatchService

pytestmark = pytest.mark.integration

EMAIL = "watcher@test.example"
PASSWORD = "watch-test-pass-123"  # noqa: S105 - synthetic test credential

FEED_V1 = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:feed:1</id><title>Полка</title>
  <entry><id>urn:book:1</id><title>Старая книга</title>
    <author><name>Автор</name></author></entry>
</feed>
"""

FEED_V2 = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>urn:feed:1</id><title>Полка</title>
  <entry><id>urn:book:1</id><title>Старая книга</title>
    <author><name>Автор</name></author></entry>
  <entry><id>urn:book:2</id><title>НОВАЯ КНИГА</title>
    <author><name>Автор</name></author>
    <link rel="http://opds-spec.org/acquisition" href="/books/new.fb2"/></entry>
</feed>
"""


def _fake_opds_app(
    feed: str | None,
    *,
    status: int = 200,
    etag: str | None = '"v1"',
    support_conditional: bool = True,
):
    app = FastAPI()
    calls: list[dict[str, Any]] = []

    @app.get("/opds/feed")
    async def feed_route(request: Request) -> Response:
        calls.append(
            {
                "if_none_match": request.headers.get("if-none-match"),
                "if_modified_since": request.headers.get("if-modified-since"),
            },
        )
        if support_conditional and etag and request.headers.get("if-none-match") == etag:
            return Response(status_code=304)
        if feed is None:
            return Response(status_code=status)
        return Response(
            content=feed,
            media_type="application/atom+xml",
            headers={"ETag": etag} if etag else {},
        )

    app.calls = calls  # type: ignore[attr-defined]
    return app


def _service_for(client: httpx.AsyncClient, ai_app) -> WatchService:
    container = client._transport.app.state.container
    transport = httpx.ASGITransport(app=ai_app)
    return WatchService(
        session_factory=container["session_factory"],
        opds=OPDSAdapter(client=httpx.AsyncClient(transport=transport)),
    )


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


class TestPollFlow:
    async def test_author_today_public_metadata_poll(self, authed) -> None:
        client, owner = authed
        fake = FastAPI()
        revision = {"value": "2026-08-28T01:00:00Z"}

        @fake.get("/u/test/works")
        async def works() -> Response:
            return Response(
                content=(
                    '<html><head><meta charset="utf-8"></head><body>'
                    '<script type="application/ld+json">'
                    '{"@type":"Person","name":"Автор AT"}</script>'
                    '<div class="book-row"><div class="book-title">'
                    '<a href="/work/777">Новая книга AT</a></div>'
                    '<span><i class="book-status-icon"></i> в процессе</span>'
                    f'<span data-hint="Обновление " data-time="{revision["value"]}"></span>'
                    "</div></body></html>"
                ),
                media_type="text/html",
            )

        container = client._transport.app.state.container
        at_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        service = WatchService(
            session_factory=container["session_factory"],
            adapters={"author_today": AuthorTodayAdapter(client=at_client)},
        )
        rule_id = await service.create_rule(
            owner,
            adapter_id="author_today",
            name="Автор AT",
            url="https://author.today/u/test",
            interval_seconds=300,
        )
        assert rule_id is not None
        assert (await service.list_rules(owner))[0]["interval_seconds"] == 1800
        outcome = await service.poll_rule(owner, rule_id)
        assert outcome == {"status": "ok", "not_modified": False, "new": 1}

        async with container["session_factory"]() as session:
            observation = (
                await session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.watch_rule_id == rule_id
                    )
                )
            ).scalar_one()
        assert observation.adapter_id == "author_today"
        assert observation.external_id == ("author-today:work:777:revision:2026-08-28T01:00:00Z")
        assert observation.parser_version == AUTHOR_TODAY_PARSER_VERSION
        assert observation.raw["status"] == "в процессе"
        assert await service.notifications(owner) == []  # initial page is a quiet baseline

        revision["value"] = "2026-08-28T02:00:00Z"
        outcome = await service.poll_rule(owner, rule_id)
        assert outcome["new"] == 1
        notifications = await service.notifications(owner)
        assert len(notifications) == 1
        assert "Новая книга AT" in notifications[0]["title"]
        await at_client.aclose()

    async def test_rule_keeps_selected_endpoint(self, authed) -> None:
        client, owner = authed
        container = client._transport.app.state.container
        async with container["session_factory"]() as session:
            endpoint = SourceEndpointModel(
                owner_id=owner,
                name="OPDS",
                source_type="opds",
                role="metadata",
                adapter_id="opds",
                url="http://opds/feed",
            )
            session.add(endpoint)
            await session.commit()
            endpoint_id = endpoint.id

        service = _service_for(client, _fake_opds_app(FEED_V1))
        rule_id = await service.create_rule(
            owner,
            adapter_id="opds",
            name="Endpoint rule",
            url="http://opds/feed",
            source_endpoint_id=endpoint_id,
        )
        assert rule_id is not None
        rules = await service.list_rules(owner)
        assert rules[0]["source_endpoint_id"] == endpoint_id

    async def test_poll_creates_observations_and_notifications_once(
        self,
        authed,
    ) -> None:
        client, owner = authed
        ai_app = _fake_opds_app(FEED_V1)
        service = _service_for(client, ai_app)

        rule_id = await service.create_rule(
            owner, adapter_id="opds", name="Полка", url="http://opds/opds/feed"
        )
        assert rule_id is not None

        # first poll: one observation + one notification
        outcome = await service.poll_rule(owner, rule_id)
        assert outcome["status"] == "ok"
        assert outcome["new"] == 1

        # second poll: same feed -> dedup, no new notifications
        outcome2 = await service.poll_rule(owner, rule_id)
        assert outcome2["status"] == "ok"
        assert outcome2["new"] == 0

        notifications = await service.notifications(owner)
        assert len(notifications) == 1
        assert "Старая книга" in notifications[0]["title"]

        # feed updated with a new book -> new notification (real transition)
        ai_app2 = _fake_opds_app(FEED_V2, etag='"v2"')
        service2 = _service_for(client, ai_app2)
        outcome3 = await service2.poll_rule(owner, rule_id)
        assert outcome3["new"] == 1
        notifications = await service.notifications(owner)
        assert len(notifications) == 2
        assert "НОВАЯ КНИГА" in notifications[0]["title"]
        assert notifications[0]["kind"] == "new_release"

    async def test_conditional_get_sends_etag_and_handles_304(
        self,
        authed,
    ) -> None:
        client, owner = authed
        ai_app = _fake_opds_app(FEED_V1)
        service = _service_for(client, ai_app)

        rule_id = await service.create_rule(
            owner, adapter_id="opds", name="Полка", url="http://opds/opds/feed"
        )
        await service.poll_rule(owner, rule_id)
        await service.poll_rule(owner, rule_id)  # sends If-None-Match -> 304

        calls = ai_app.calls  # type: ignore[attr-defined]
        assert len(calls) == 2
        assert calls[0]["if_none_match"] is None
        assert calls[1]["if_none_match"] == '"v1"'

    async def test_failures_degrade_and_notify_once(
        self,
        authed,
    ) -> None:
        client, owner = authed
        broken = _fake_opds_app(None, status=500)
        service = _service_for(client, broken)

        rule_id = await service.create_rule(
            owner, adapter_id="opds", name="Сломан", url="http://opds/opds/feed"
        )
        await service.poll_rule(owner, rule_id)  # failure 1
        outcome = await service.poll_rule(owner, rule_id)  # failure 2 -> degraded

        assert outcome["status"] == "error"
        assert outcome["failures"] >= 2

        notifications = await service.notifications(owner)
        degraded_notes = [n for n in notifications if n["kind"] == "source_degraded"]
        assert len(degraded_notes) == 1  # only on transition, not every failure

        rules = await service.list_rules(owner)
        assert rules[0]["degraded"] is True

    async def test_rule_management_via_http(
        self,
        authed,
    ) -> None:
        client, owner = authed
        service = _service_for(client, _fake_opds_app(FEED_V1))

        response = await client.post(
            "/library/sources/rules",
            data={
                "adapter_id": "opds",
                "name": "HTTP полка",
                "url": "http://opds/opds/feed",
                "interval_minutes": "60",
            },
        )
        assert response.status_code == 303

        page = await client.get("/library/sources")
        assert "HTTP полка" in page.text
        assert "отключён —" in page.text  # disabled adapters listed with reasons

        rules = await service.list_rules(owner)
        rule_id = rules[0]["id"]

        # Flibusta is an enabled metadata-only profile.
        flibusta_rule = await service.create_rule(
            owner,
            adapter_id="flibusta",
            name="x",
            url="http://x/feed",
        )
        assert flibusta_rule is not None

        # delete via HTTP
        response = await client.post(f"/library/sources/rules/{rule_id}/delete")
        assert response.status_code == 303
        await service.delete_rule(owner, flibusta_rule)
        assert await service.list_rules(owner) == []

    async def test_owner_isolation_on_poll(self, authed) -> None:
        client, owner = authed
        service = _service_for(client, _fake_opds_app(FEED_V1))
        rule_id = await service.create_rule(
            owner, adapter_id="opds", name="x", url="http://opds/feed"
        )
        with pytest.raises(LookupError):
            await service.poll_rule(uuid4(), rule_id)
