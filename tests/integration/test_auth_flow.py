"""Integration E2E: full authentication lifecycle over HTTP (master prompt 12)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from tests.unit.test_jwt_and_passwords import make_settings as jwt_settings

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery-staple"  # noqa: S105 - synthetic test credential
EMAIL = "owner@gorbunovr.ru"


async def _register(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD},
    )


async def _login(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await client.post(
        "/auth/login",
        data={"username": email, "password": PASSWORD},
    )


class TestBootstrapRegistration:
    async def test_first_user_becomes_superuser(self, client: httpx.AsyncClient) -> None:
        response = await _register(client)
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["is_superuser"] is True
        assert "library_access" in response.cookies
        assert "library_refresh" in response.cookies
        assert "library_csrf" in response.cookies

    async def test_second_anonymous_registration_closed(self, client: httpx.AsyncClient) -> None:
        assert (await _register(client)).status_code == 201
        client.cookies.clear()  # anonymous caller: registration must be closed
        response = await _register(client, email="second@gorbunovr.ru")
        assert response.status_code == 403

    async def test_weak_password_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/auth/register",
            json={"email": EMAIL, "password": "short"},
        )
        assert response.status_code == 422  # pydantic min_length

    async def test_duplicate_email_rejected(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        response = await _register(client)
        assert response.status_code == 400


class TestLogin:
    async def test_login_success_sets_cookies(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        client.cookies.clear()
        response = await _login(client)
        assert response.status_code == 200
        assert response.json()["access_token"]
        assert "library_refresh" in response.cookies

    async def test_login_wrong_password(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        client.cookies.clear()
        response = await client.post(
            "/auth/login",
            data={"username": EMAIL, "password": "totally-wrong-password!"},
        )
        assert response.status_code == 401

    async def test_login_unknown_email(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/auth/login",
            data={"username": "ghost@nowhere.io", "password": PASSWORD},
        )
        assert response.status_code == 401


class TestSession:
    async def test_me_with_bearer(self, client: httpx.AsyncClient) -> None:
        response = await _register(client)
        token = response.json()["access_token"]
        me = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == EMAIL

    async def test_me_with_access_cookie(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        me = await client.get("/auth/me")
        assert me.status_code == 200

    async def test_me_unauthenticated(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/auth/me")).status_code == 401

    async def test_expired_access_token_rejected(self, client: httpx.AsyncClient) -> None:
        response = await _register(client)
        user_id = response.json()["user"]["id"]
        expired_settings = jwt_settings(access_token_ttl_minutes=-1)
        from portal.core.auth.jwt_service import TokenService

        token, _ = TokenService(expired_settings).issue_access_token(user_id, ["portal:full"])
        me = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 401

    async def test_garbage_token_rejected(self, client: httpx.AsyncClient) -> None:
        me = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert me.status_code == 401


class TestRefreshRotation:
    async def test_refresh_issues_new_pair_and_revokes_old(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        old_refresh = client.cookies["library_refresh"]
        client.cookies.clear()

        client.cookies.set("library_refresh", old_refresh)
        response = await client.post("/auth/refresh")
        assert response.status_code == 200
        new_refresh = response.cookies["library_refresh"]
        assert new_refresh != old_refresh

        # old refresh token must now be revoked
        client.cookies.set("library_refresh", old_refresh)
        replay = await client.post("/auth/refresh")
        assert replay.status_code == 401

        # new one still works
        client.cookies.set("library_refresh", new_refresh)
        again = await client.post("/auth/refresh")
        assert again.status_code == 200
        client.cookies.clear()

    async def test_refresh_without_cookie(self, client: httpx.AsyncClient) -> None:
        assert (await client.post("/auth/refresh")).status_code == 401


class TestLogout:
    async def test_logout_revokes_refresh(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        refresh_cookie = client.cookies["library_refresh"]
        csrf = client.cookies["library_csrf"]

        response = await client.post(
            "/auth/logout",
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 204

        client.cookies.set("library_refresh", refresh_cookie)
        replay = await client.post("/auth/refresh")
        assert replay.status_code == 401
        client.cookies.clear()


class TestCSRF:
    async def test_cookie_auth_unsafe_request_without_header_rejected(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        await _register(client)
        response = await client.post(
            "/auth/tokens",
            json={"name": "FBReader", "scopes": ["library:opds:read"]},
        )
        assert response.status_code == 403

    async def test_cookie_auth_unsafe_request_with_header_passes(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        await _register(client)
        csrf = client.cookies["library_csrf"]
        response = await client.post(
            "/auth/tokens",
            json={"name": "FBReader", "scopes": ["library:opds:read"]},
            headers={"x-csrf-token": csrf},
        )
        assert response.status_code == 201
        assert response.json()["token"].startswith("pdt_")

    async def test_bearer_auth_skips_csrf(self, client: httpx.AsyncClient) -> None:
        token = (await _register(client)).json()["access_token"]
        response = await client.post(
            "/auth/tokens",
            json={"name": "FBReader"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201


class TestDeviceTokens:
    async def test_create_list_revoke(self, client: httpx.AsyncClient) -> None:
        token = (await _register(client)).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/auth/tokens",
            json={"name": "Phone FBReader", "scopes": ["library:opds:read"]},
            headers=headers,
        )
        assert created.status_code == 201
        token_id = created.json()["id"]

        listed = await client.get("/auth/tokens", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["name"] == "Phone FBReader"

        revoked = await client.delete(f"/auth/tokens/{token_id}", headers=headers)
        assert revoked.status_code == 204

        listed_after = await client.get("/auth/tokens", headers=headers)
        assert listed_after.json()[0]["revoked"] is True

    async def test_revoke_foreign_token_not_found(self, client: httpx.AsyncClient) -> None:
        token = (await _register(client)).json()["access_token"]
        response = await client.delete(
            f"/auth/tokens/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestRateLimit:
    async def test_login_brute_force_limited(self, client: httpx.AsyncClient, app_settings) -> None:
        await _register(client)
        client.cookies.clear()
        last_response: httpx.Response | None = None
        for _ in range(app_settings.login_rate_limit + 1):
            last_response = await client.post(
                "/auth/login",
                data={"username": EMAIL, "password": "wrong-password-123"},
            )
        assert last_response is not None
        assert last_response.status_code == 429


class TestAudit:
    async def test_sensitive_actions_recorded(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        client.cookies.clear()
        await client.post(
            "/auth/login",
            data={"username": EMAIL, "password": "nope-wrong-password"},
        )
        await _login(client)

        from sqlalchemy import text

        engine = client._transport.app.state.container["engine"]
        async with engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text("SELECT action FROM audit_log ORDER BY created_at"),
                    )
                )
                .scalars()
                .all()
            )
        assert "register" in rows
        assert "login_failed" in rows
        assert "login" in rows


class TestSSR:
    async def test_login_page_flow(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        client.cookies.clear()

        page = await client.get("/login")
        assert page.status_code == 200

        submitted = await client.post(
            "/login",
            data={"username": EMAIL, "password": PASSWORD},
            follow_redirects=False,
        )
        assert submitted.status_code == 303
        assert submitted.headers["location"] == "/library/"

        library = await client.get("/library/")
        assert library.status_code == 200
        assert "Каталог" in library.text  # dashboard renders for authenticated user

    async def test_logout_via_ssr(self, client: httpx.AsyncClient) -> None:
        await _register(client)
        response = await client.post("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"
        assert "library_access" not in response.cookies or response.cookies["library_access"] == ""

        client.cookies.set("library_refresh", "anything")
        replay = await client.post("/auth/refresh")
        assert replay.status_code == 401
        client.cookies.clear()


class TestJobsAndOutbox:
    async def test_job_claim_and_complete(self, client: httpx.AsyncClient) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from portal.core.jobs.orm import JobStatus
        from portal.core.jobs.repository import JobRepository

        container = client._transport.app.state.container
        session_factory: async_sessionmaker = container["session_factory"]

        async with session_factory() as session, session.begin():
            repo = JobRepository(session)
            job_id = await repo.enqueue("noop", {"hello": "world"})

        async with session_factory() as session, session.begin():
            repo = JobRepository(session)
            claimed = await repo.claim_batch("worker-1")
            assert len(claimed) == 1
            await repo.mark_done(job_id)

        async with session_factory() as session:
            job = await JobRepository(session).get(job_id)
            assert job is not None
            assert job.status == JobStatus.DONE.value

    async def test_outbox_enqueue_and_process(self, client: httpx.AsyncClient) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from portal.core.events.repository import OutboxRepository

        container = client._transport.app.state.container
        session_factory: async_sessionmaker = container["session_factory"]

        async with session_factory() as session, session.begin():
            repo = OutboxRepository(session)
            event_id = await repo.enqueue("BookFileImported", {"asset_id": str(uuid.uuid4())})
            assert await repo.count_pending() == 1

        async with session_factory() as session, session.begin():
            repo = OutboxRepository(session)
            pending = await repo.fetch_pending()
            assert [e.id for e in pending] == [event_id]
            await repo.mark_processed(event_id)

        async with session_factory() as session:
            assert await OutboxRepository(session).count_pending() == 0
