"""Integration E2E: normalization pipeline — run, invariant, prefer, idempotence."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures.books import fb2_document
from portal.modules.library.application.normalization_service import AssetNotFoundError

pytestmark = pytest.mark.integration

EMAIL = "normalizer@test.example"
PASSWORD = "normalize-test-pass-123"  # noqa: S105 - synthetic test credential


@pytest.fixture
async def authed_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    response = await client.post(
        "/auth/register",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    return client


async def _upload(client: httpx.AsyncClient, upload: tuple[str, bytes]) -> None:
    name, content = upload
    response = await client.post(
        "/library/import/upload",
        files=[("files", (name, content, "application/octet-stream"))],
    )
    assert response.status_code == 303


async def _first_original_asset_id(client: httpx.AsyncClient) -> str:
    import re

    page = await client.get("/library/catalog")
    match = re.search(r"/library/works/([0-9a-f-]+)", page.text)
    assert match is not None
    work_page = await client.get(f"/library/works/{match.group(1)}")
    asset_match = re.search(r"/library/assets/([0-9a-f-]+)/normalize", work_page.text)
    assert asset_match is not None
    return asset_match.group(1)


class TestNormalizationFlow:
    async def test_full_pipeline(
        self,
        authed_client: httpx.AsyncClient,
        app_settings,
    ) -> None:
        await _upload(
            authed_client,
            ("Киз — Классика 01 — Цветы для Элджернона.fb2", fb2_document(body_images=2)),
        )
        asset_id = await _first_original_asset_id(authed_client)

        # request normalization
        response = await authed_client.post(f"/library/assets/{asset_id}/normalize")
        assert response.status_code == 303
        run_location = response.headers["location"]
        run_id = run_location.rsplit("/", 1)[-1]

        # execute (worker does this in production; here directly)
        service = authed_client._transport.app.state.container["normalization_service"]
        from uuid import UUID as U

        owner_response = await authed_client.get("/auth/me")
        owner_id = owner_response.json()["id"]
        result = await service.execute_run(U(owner_id), U(run_id))
        assert result.state.value in {"derivative_ready", "needs_review"}
        assert result.derivative_asset_id is not None

        # report page renders
        report = await authed_client.get(f"/library/normalization/{run_id}")
        assert report.status_code == 200
        assert "ИНВАРИАНТ ТЕКСТА" in report.text
        assert "True" in report.text  # text_invariant_ok

        # derivative is downloadable
        from urllib.parse import unquote

        download = await authed_client.get(f"/library/assets/{result.derivative_asset_id}/download")
        assert download.status_code == 200
        disposition = unquote(download.headers.get("content-disposition", ""))
        assert "attachment" in disposition
        assert "Киз" in disposition
        assert disposition.endswith(".fb2")

        # prefer
        prefer = await authed_client.post(f"/library/normalization/{run_id}/prefer")
        assert prefer.status_code == 303

    async def test_idempotent_request_returns_existing_run(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        await _upload(
            authed_client,
            ("Лукьяненко — Черновик.fb2", fb2_document(title="Черновик")),
        )
        asset_id = await _first_original_asset_id(authed_client)

        service = authed_client._transport.app.state.container["normalization_service"]
        from uuid import UUID as U

        owner_response = await authed_client.get("/auth/me")
        owner_id = U(owner_response.json()["id"])

        first = await service.request_normalization(owner_id, U(asset_id))
        await service.execute_run(owner_id, first.run_id)
        second = await service.request_normalization(owner_id, U(asset_id))

        assert second.idempotent is True
        assert second.run_id == first.run_id

    async def test_text_invariant_violation_fails_run(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        await _upload(
            authed_client, ("Автор Н — Книга Инвариант.fb2", fb2_document(title="Книга Инвариант"))
        )
        asset_id = await _first_original_asset_id(authed_client)

        service = authed_client._transport.app.state.container["normalization_service"]
        from uuid import UUID as U

        owner_response = await authed_client.get("/auth/me")
        owner_id = U(owner_response.json()["id"])
        result = await service.request_normalization(owner_id, U(asset_id))

        # tamper the transformer by monkeypatching serialization to alter text
        from portal.modules.library.infrastructure.normalizer import fb2 as fb2_mod

        original_transform = fb2_mod.transform_fb2

        def tampered_transform(root, profile):
            serialized, actions, cover = original_transform(root, profile)
            return serialized.replace("Текст".encode(), b"TEKST"), actions, cover

        fb2_mod.transform_fb2 = tampered_transform
        try:
            with pytest.raises(Exception, match="invariant"):
                await service.execute_run(owner_id, result.run_id)
        finally:
            fb2_mod.transform_fb2 = original_transform

        run = await service.get_run(owner_id, result.run_id)
        assert run is not None
        assert run["state"] == "failed"

    async def test_owner_isolation_on_run_access(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        await _upload(
            authed_client,
            ("Автор О — Произведение Один.fb2", fb2_document(title="Произведение Один")),
        )
        asset_id = await _first_original_asset_id(authed_client)
        service = authed_client._transport.app.state.container["normalization_service"]
        from uuid import UUID as U
        from uuid import uuid4

        owner_response = await authed_client.get("/auth/me")
        owner_id = U(owner_response.json()["id"])
        result = await service.request_normalization(owner_id, U(asset_id))

        assert await service.get_run(uuid4(), result.run_id) is None
        with pytest.raises(AssetNotFoundError):
            await service.execute_run(uuid4(), result.run_id)
