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
    SourceLinkModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.adapters.watch_service import WatchService
from portal.modules.library.application.source_link_service import SourceLinkService
from portal.modules.library.application.source_onboarding_service import SourceOnboardingService
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    SeriesModel,
    WorkAuthorModel,
    WorkModel,
)

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
        requests: list[dict[str, str | None]] = []

        @fake.get("/u/test/works")
        async def works(request: Request) -> Response:
            requests.append({"if_none_match": request.headers.get("if-none-match")})
            return Response(
                content=(
                    '<html><head><meta charset="utf-8"></head><body>'
                    '<script type="application/ld+json">'
                    '{"@type":"Person","name":"Автор AT"}</script>'
                    '<div class="book-row"><div class="book-title">'
                    '<a href="/work/777">Новая книга AT</a></div>'
                    '<span><i class="book-status-icon"></i> в процессе</span>'
                    '<a href="/work/series/55">Тестовый цикл</a>'
                    f'<span data-hint="Обновление " data-time="{revision["value"]}"></span>'
                    "</div></body></html>"
                ),
                media_type="text/html",
            )

        container = client._transport.app.state.container
        async with container["session_factory"]() as session:
            series = SeriesModel(
                owner_id=owner,
                title="Тестовый цикл",
                title_normalized="тестовый цикл",
            )
            session.add(series)
            await session.commit()
            series_id = series.id
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
        assert observation.series_id == series_id
        assert await service.notifications(owner) == []  # initial page is a quiet baseline
        async with container["session_factory"]() as session:
            rule = await session.get(WatchRuleModel, rule_id)
            assert rule is not None
            assert rule.parser_version == AUTHOR_TODAY_PARSER_VERSION
            assert rule.last_status == "ok"
            assert rule.last_new_count == 1
            assert rule.last_duration_ms is not None

        # Parser upgrades force a full, quiet baseline even when the old rule has an ETag.
        async with container["session_factory"]() as session:
            rule = await session.get(WatchRuleModel, rule_id)
            assert rule is not None
            rule.parser_version = "author-today-public-html-v1"
            rule.etag = '"legacy"'
            await session.commit()
        revision["value"] = "2026-08-28T02:00:00Z"
        outcome = await service.poll_rule(owner, rule_id)
        assert outcome["new"] == 1
        assert requests[-1]["if_none_match"] is None
        assert await service.notifications(owner) == []

        revision["value"] = "2026-08-28T03:00:00Z"
        outcome = await service.poll_rule(owner, rule_id)
        assert outcome["new"] == 1
        assert await service.notifications(owner) == []
        await at_client.aclose()

    async def test_author_today_notifies_only_for_tracked_series(self, authed) -> None:
        client, owner = authed
        fake = FastAPI()
        revision = {"value": "2026-09-04T01:00:00Z"}

        @fake.get("/u/test/works")
        async def works() -> Response:
            rows = "".join(
                (
                    '<div class="book-row"><div class="book-title">'
                    f'<a href="/work/{work_id}">{title}</a></div>'
                    f'<a href="/work/series/{series_id}">{series_title}</a>'
                    '<span data-hint="Обновление " '
                    f'data-time="{revision["value"]}"></span></div>'
                )
                for work_id, title, series_id, series_title in (
                    ("701", "Релиз наблюдаемого цикла", "51", "Наблюдаемый цикл"),
                    ("702", "Посторонний релиз", "52", "Другой цикл"),
                )
            )
            return Response(
                content=(
                    '<html><head><meta charset="utf-8"></head><body>'
                    '<script type="application/ld+json">'
                    '{"@type":"Person","name":"Автор AT"}</script>'
                    f"{rows}</body></html>"
                ),
                media_type="text/html",
            )

        container = client._transport.app.state.container
        async with container["session_factory"]() as session, session.begin():
            tracked = SeriesModel(
                owner_id=owner,
                title="Наблюдаемый цикл",
                title_normalized="наблюдаемый цикл",
            )
            untracked = SeriesModel(
                owner_id=owner,
                title="Другой цикл",
                title_normalized="другой цикл",
            )
            endpoint = SourceEndpointModel(
                owner_id=owner,
                name="Автор AT",
                source_type="website",
                role="metadata",
                adapter_id="author_today",
                url="https://author.today/u/test/works",
            )
            session.add_all([tracked, untracked, endpoint])
            await session.flush()
            tracked_id = tracked.id
            untracked_id = untracked.id
            endpoint_id = endpoint.id
            session.add(
                SourceLinkModel(
                    owner_id=owner,
                    source_endpoint_id=endpoint_id,
                    entity_type="series",
                    entity_id=tracked_id,
                    role="metadata",
                    external_url="https://author.today/work/series/51",
                    is_preferred=True,
                )
            )

        at_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        service = WatchService(
            session_factory=container["session_factory"],
            adapters={"author_today": AuthorTodayAdapter(client=at_client)},
        )
        rule_id = await service.create_rule(
            owner,
            adapter_id="author_today",
            name="Автор AT",
            url="https://author.today/u/test/works",
            source_endpoint_id=endpoint_id,
        )
        assert rule_id is not None

        assert (await service.poll_rule(owner, rule_id))["new"] == 2
        assert await service.notifications(owner) == []

        revision["value"] = "2026-09-04T02:00:00Z"
        assert (await service.poll_rule(owner, rule_id))["new"] == 2
        notifications = await service.notifications(owner)
        assert len(notifications) == 1
        assert "Релиз наблюдаемого цикла" in notifications[0]["title"]

        async with container["session_factory"]() as session:
            observations = list(
                (
                    await session.execute(
                        select(SourceObservationModel).where(
                            SourceObservationModel.watch_rule_id == rule_id
                        )
                    )
                ).scalars()
            )
        assert {observation.series_id for observation in observations} == {
            tracked_id,
            untracked_id,
        }
        await at_client.aclose()

    async def test_author_today_reviews_coauthor_candidate_before_source_propagation(
        self, authed
    ) -> None:
        client, owner = authed
        container = client._transport.app.state.container
        async with container["session_factory"]() as session, session.begin():
            root_author = AuthorModel(
                owner_id=owner,
                name="Корневой Автор",
                name_normalized="корневой автор",
            )
            series = SeriesModel(
                owner_id=owner,
                title="Общий цикл",
                title_normalized="общий цикл",
            )
            work = WorkModel(
                owner_id=owner,
                title="Совместная книга",
                title_normalized="совместная книга",
            )
            session.add_all([root_author, series, work])
            await session.flush()
            session.add_all(
                [
                    WorkAuthorModel(
                        owner_id=owner,
                        work_id=work.id,
                        author_id=root_author.id,
                        role="author",
                        position=0,
                    ),
                    SeriesMembershipModel(
                        owner_id=owner,
                        series_id=series.id,
                        work_id=work.id,
                        index_raw="1",
                        index_sort=1,
                        membership_type="main",
                    ),
                ]
            )
            assert await SourceOnboardingService(session).connect_author_today(
                owner,
                root_author.id,
                "https://author.today/u/root",
            )
            root_endpoint = (
                await session.execute(
                    select(SourceEndpointModel).where(
                        SourceEndpointModel.owner_id == owner,
                        SourceEndpointModel.url == "https://author.today/u/root/works",
                    )
                )
            ).scalar_one()
            await SourceLinkService(session).add(
                owner,
                endpoint_id=root_endpoint.id,
                entity_type="series",
                entity_id=series.id,
                role="metadata",
                external_url="https://author.today/work/series/55",
                preferred=True,
            )
            root_rule_id = (
                await session.execute(
                    select(WatchRuleModel.id).where(
                        WatchRuleModel.source_endpoint_id == root_endpoint.id
                    )
                )
            ).scalar_one()
            series_id = series.id
            work_id = work.id

        fake = FastAPI()

        @fake.get("/u/{slug}/works")
        async def coauthor_works(slug: str) -> Response:
            profile_name = "Корневой Автор" if slug == "root" else "Соавтор"
            third = '<a href="/u/third/works">Третий Автор</a>, ' if slug == "coauthor" else ""
            return Response(
                content=(
                    '<html><head><meta charset="utf-8"></head><body>'
                    '<script type="application/ld+json">'
                    f'{{"@type":"Person","name":"{profile_name}"}}</script>'
                    '<div class="book-row"><div class="book-title">'
                    '<a href="/work/777">Совместная книга</a></div>'
                    '<div class="book-author">'
                    f'{third}<a href="/u/root/works">Корневой Автор</a>, '
                    '<a href="/u/coauthor/works">Соавтор</a></div>'
                    '<a href="/work/series/55">Общий цикл</a></div></body></html>'
                ),
                media_type="text/html",
            )

        at_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        service = WatchService(
            session_factory=container["session_factory"],
            adapters={"author_today": AuthorTodayAdapter(client=at_client)},
        )
        assert (await service.poll_rule(owner, root_rule_id))["status"] == "ok"

        async with container["session_factory"]() as session:
            assert (
                await session.execute(
                    select(AuthorModel.id).where(
                        AuthorModel.owner_id == owner,
                        AuthorModel.name_normalized == "соавтор",
                    )
                )
            ).scalar_one_or_none() is None
            assert (
                len(
                    list(
                        (
                            await session.execute(
                                select(SourceEndpointModel).where(
                                    SourceEndpointModel.owner_id == owner,
                                    SourceEndpointModel.adapter_id == "author_today",
                                )
                            )
                        ).scalars()
                    )
                )
                == 1
            )

        # A parser refresh enriches an already-seen publication without treating
        # it as a new release or materializing the coauthor automatically.
        async with container["session_factory"]() as session, session.begin():
            observation = (
                await session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.watch_rule_id == root_rule_id
                    )
                )
            ).scalar_one()
            observation.raw = {**observation.raw, "authors": []}
            rule = await session.get(WatchRuleModel, root_rule_id)
            assert rule is not None
            rule.parser_version = "author-today-public-html-v2"

        refreshed = await service.poll_rule(owner, root_rule_id)
        assert refreshed == {"status": "ok", "not_modified": False, "new": 0}
        assert await service.notifications(owner) == []
        async with container["session_factory"]() as session:
            observation = (
                await session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.watch_rule_id == root_rule_id
                    )
                )
            ).scalar_one()
            assert {author["url"] for author in observation.raw["authors"]} == {
                "https://author.today/u/root/works",
                "https://author.today/u/coauthor/works",
            }

        authors_page = await client.get("/library/authors")
        assert authors_page.status_code == 200
        assert "НОВЫЕ КАНДИДАТЫ · 1" in authors_page.text
        assert 'href="/library/authors/candidates/coauthor"' in authors_page.text

        candidate_page = await client.get("/library/authors/candidates/coauthor")
        assert candidate_page.status_code == 200
        assert "ОТКУДА ВЗЯЛСЯ КАНДИДАТ" in candidate_page.text
        assert "Корневой Автор" in candidate_page.text
        assert "Совместная книга" in candidate_page.text
        assert "До этого портал не опрашивает профиль кандидата отдельно" in candidate_page.text

        accepted = await client.post("/library/authors/candidates/coauthor/accept")
        assert accepted.status_code == 303

        async with container["session_factory"]() as session:
            coauthor = (
                await session.execute(
                    select(AuthorModel).where(
                        AuthorModel.owner_id == owner,
                        AuthorModel.name_normalized == "соавтор",
                    )
                )
            ).scalar_one()
            coauthor_endpoint = (
                await session.execute(
                    select(SourceEndpointModel).where(
                        SourceEndpointModel.owner_id == owner,
                        SourceEndpointModel.url == "https://author.today/u/coauthor/works",
                    )
                )
            ).scalar_one()
            coauthor_rule_id = (
                await session.execute(
                    select(WatchRuleModel.id).where(
                        WatchRuleModel.source_endpoint_id == coauthor_endpoint.id
                    )
                )
            ).scalar_one()
            coauthor_link = (
                await session.execute(
                    select(SourceLinkModel).where(
                        SourceLinkModel.source_endpoint_id == coauthor_endpoint.id,
                        SourceLinkModel.entity_type == "author",
                        SourceLinkModel.entity_id == coauthor.id,
                    )
                )
            ).scalar_one()
            assert coauthor_link.is_preferred is False
            work_author_ids = set(
                (
                    await session.execute(
                        select(WorkAuthorModel.author_id).where(WorkAuthorModel.work_id == work_id)
                    )
                ).scalars()
            )
            assert coauthor.id in work_author_ids
            coauthor_id = coauthor.id
        assert accepted.headers["location"] == f"/library/authors/{coauthor_id}"

        assert (await service.poll_rule(owner, coauthor_rule_id))["status"] == "ok"
        async with container["session_factory"]() as session:
            series_links = list(
                (
                    await session.execute(
                        select(SourceLinkModel).where(
                            SourceLinkModel.owner_id == owner,
                            SourceLinkModel.entity_type == "series",
                            SourceLinkModel.entity_id == series_id,
                        )
                    )
                ).scalars()
            )
            assert {link.source_endpoint_id for link in series_links} == {
                root_endpoint.id,
                coauthor_endpoint.id,
            }
            candidates = await SourceOnboardingService(session).series_candidates(
                owner, coauthor.id
            )
            assert candidates[0]["connected"] is True
            assert (
                await session.execute(
                    select(AuthorModel.id).where(
                        AuthorModel.owner_id == owner,
                        AuthorModel.name_normalized == "третий автор",
                    )
                )
            ).scalar_one_or_none() is None

        candidates_page = await client.get("/library/authors")
        assert "НОВЫЕ КАНДИДАТЫ · 0" in candidates_page.text
        assert 'href="/library/authors/candidates/third"' not in candidates_page.text
        assert 'href="/library/authors/candidates/coauthor"' not in candidates_page.text

        graph_page = await client.get("/library/authors/graph")
        assert graph_page.status_code == 200
        assert "Происхождение авторов" in graph_page.text
        assert "Корневой Автор" in graph_page.text
        assert "Соавтор" in graph_page.text
        assert "Совместная книга" in graph_page.text
        assert "1 связей обнаружения" in graph_page.text
        assert "профиль указан источником" in graph_page.text

        coauthor_page = await client.get(f"/library/authors/{coauthor_id}")
        assert coauthor_page.status_code == 200
        assert "ПРОИСХОЖДЕНИЕ АВТОРА" in coauthor_page.text
        assert "Обнаружен через" in coauthor_page.text
        assert "Корневой Автор" in coauthor_page.text
        assert "Совместная книга" in coauthor_page.text
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
