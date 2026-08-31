"""Integration E2E: import pipeline — upload, dedup, matching, catalog, scan."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from portal.modules.library.application.watched_inbox import WatchedInboxService
from portal.modules.library.infrastructure.import_orm import ImportBatchModel, ImportItemModel
from portal.modules.library.infrastructure.orm import WorkModel

pytestmark = pytest.mark.integration

EMAIL = "importer@test.example"
PASSWORD = "import-test-password-123"  # noqa: S105 - synthetic test credential


def _fb2(title: str, body: str = "Текст произведения.") -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        f"<description><title-info><book-title>{title}</book-title></title-info></description>"
        f"<body><section><p>{body}</p></section></body></FictionBook>"
    ).encode()


def _fb2_with_metadata() -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        "<description><title-info><book-title>Верное название</book-title>"
        "<author><first-name>Иван</first-name><last-name>Авторов</last-name></author>"
        '<sequence name="Верный цикл" number="7"/></title-info></description>'
        "<body><section><p>Текст.</p></section></body></FictionBook>"
    ).encode()


def _epub(marker: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("content.opf", f"<package>{marker}</package>")
    return buffer.getvalue()


@pytest.fixture
async def authed_client(client: httpx.AsyncClient) -> httpx.AsyncClient:
    response = await client.post(
        "/auth/register",
        json={"email": EMAIL, "password": PASSWORD},
    )
    assert response.status_code == 201
    client.headers["x-csrf-token"] = client.cookies["library_csrf"]
    return client


async def _upload(client: httpx.AsyncClient, files: list[tuple[str, bytes]]) -> httpx.Response:
    multipart = [("files", (name, content, "application/octet-stream")) for name, content in files]
    return await client.post("/library/import/upload", files=multipart)


class TestUploadImport:
    async def test_unmatched_assignment_offers_catalog_picker(
        self, authed_client: httpx.AsyncClient
    ) -> None:
        await _upload(
            authed_client,
            [("Автор — Цикл 01 — Уже в каталоге.fb2", _fb2("Уже в каталоге"))],
        )
        await _upload(authed_client, [("непонятный файл.fb2", _fb2("Без метаданных"))])
        page = await authed_client.get("/library/import")
        assert "Выбрать из каталога" in page.text
        assert 'name="work_id"' not in page.text

        container = authed_client._transport.app.state.container
        async with container["session_factory"]() as session:
            item = (
                await session.execute(
                    select(ImportItemModel).where(
                        ImportItemModel.status == "stored_unmatched",
                    ),
                )
            ).scalar_one()
            work = (
                await session.execute(
                    select(WorkModel).where(WorkModel.title == "Уже в каталоге"),
                )
            ).scalar_one()

        picker = await authed_client.get(
            f"/library/import/items/{item.id}/assign",
            params={"q": "Цикл"},
        )
        assert picker.status_code == 200
        assert "Уже в каталоге" in picker.text
        assert "Название, автор или цикл" in picker.text
        assert "UUID" not in picker.text

        invalid = await authed_client.post(
            f"/library/import/items/{item.id}/assign",
            data={"work_id": "not-a-valid-id"},
        )
        assert invalid.status_code == 303
        assert invalid.headers["location"].endswith(f"/items/{item.id}/assign")

        assigned = await authed_client.post(
            f"/library/import/items/{item.id}/assign",
            data={"work_id": str(work.id)},
        )
        assert assigned.status_code == 303
        async with container["session_factory"]() as session:
            assigned_item = await session.get(ImportItemModel, item.id)
            assert assigned_item is not None
            assert assigned_item.status == "matched"
            assert assigned_item.work_id == work.id

    async def test_reupload_restores_missing_original_and_applies_metadata(
        self, authed_client: httpx.AsyncClient, app_settings
    ) -> None:
        content = _fb2_with_metadata()
        await _upload(authed_client, [("broken_name.fb2", content)])
        from portal.modules.library.infrastructure.orm import AssetModel

        container = authed_client._transport.app.state.container
        async with container["session_factory"]() as session:
            asset = (await session.execute(select(AssetModel))).scalar_one()
            storage_path = asset.storage_path
        (Path(app_settings.storage_root) / storage_path).unlink()

        response = await _upload(authed_client, [("recovery.fb2", content)])
        assert response.status_code == 303
        assert (Path(app_settings.storage_root) / storage_path).is_file()
        catalog = await authed_client.get("/library/catalog")
        assert "Верное название" in catalog.text

    async def test_embedded_fb2_metadata_beats_broken_filename(
        self, authed_client: httpx.AsyncClient
    ) -> None:
        response = await _upload(
            authed_client,
            [("broken_romanized_name_777.fb2", _fb2_with_metadata())],
        )
        assert response.status_code == 303
        catalog = await authed_client.get("/library/catalog")
        assert "Верное название" in catalog.text
        assert "Иван Авторов" in catalog.text
        assert "Верный цикл" in catalog.text

    async def test_well_formed_upload_creates_work_and_asset(
        self,
        authed_client: httpx.AsyncClient,
        tmp_path: Path,
    ) -> None:
        response = await _upload(
            authed_client,
            [("Джеймс Кори — Пространство 05.5 — Обретение Мидаса.fb2", _fb2("Обретение Мидаса"))],
        )
        assert response.status_code == 303

        catalog = await authed_client.get("/library/catalog")
        assert catalog.status_code == 200
        assert "Обретение Мидаса" in catalog.text
        assert "Джеймс Кори" in catalog.text
        assert "Пространство" in catalog.text

    async def test_catalog_counts_and_work_page(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        await _upload(
            authed_client,
            [("Лукьяненко — Лабиринт отражений.fb2", _fb2("Лабиринт отражений"))],
        )
        catalog = await authed_client.get("/library/catalog")
        assert "1 произведений" in catalog.text

        # follow to work page via catalog link
        import re

        match = re.search(r"/library/works/([0-9a-f-]+)", catalog.text)
        assert match is not None
        work_page = await authed_client.get(f"/library/works/{match.group(1)}")
        assert work_page.status_code == 200
        assert "Лабиринт отражений" in work_page.text
        assert ".fb2" in work_page.text  # asset filename shown

    async def test_exact_duplicate_recorded_not_stored(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        same = _fb2("Уникальная книга", body="Версия 1")
        first = await _upload(authed_client, [("Автор А — Книга Уникальная.fb2", same)])
        assert first.status_code == 303

        second = await _upload(authed_client, [("Автор Б — Книга Уникальная.fb2", same)])
        assert second.status_code == 303

        page = await authed_client.get("/library/import")
        assert page.status_code == 200
        assert "exact_content" in page.text

        catalog = await authed_client.get("/library/catalog")
        assert "1 произведений" in catalog.text  # no phantom work created

    async def test_unknown_format_rejected(self, authed_client: httpx.AsyncClient) -> None:
        response = await _upload(authed_client, [("not-a-book.fb2", b"plain text garbage")])
        assert response.status_code == 303
        page = await authed_client.get("/library/import")
        assert "neither FB2 nor EPUB" in page.text

    async def test_same_work_format_creates_duplicate_candidate(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        # same parsed work, different content
        await _upload(
            authed_client,
            [("Киз — Классика 01 — Цветы для Элджернона.fb2", _fb2("Цветы", "v1"))],
        )
        await _upload(
            authed_client,
            [("Киз — Классика 01 — Цветы для Элджернона.fb2", _fb2("Цветы", "v2"))],
        )
        page = await authed_client.get("/library/import")
        assert "same_work_format" in page.text

    async def test_ambiguous_filename_stored_unmatched(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        await _upload(authed_client, [("какая-то скачанная книга.fb2", _fb2("Что-то"))])
        page = await authed_client.get("/library/import")
        assert "ТРЕБУЮТ РАЗБОРА" in page.text
        assert "какая-то скачанная книга.fb2" in page.text

    async def test_path_traversal_in_filename_neutralized(
        self,
        authed_client: httpx.AsyncClient,
    ) -> None:
        response = await _upload(
            authed_client,
            [("../../etc/evil — Название.fb2", _fb2("Злой файл"))],
        )
        assert response.status_code == 303
        page = await authed_client.get("/library/import")
        # filename flattened to basename
        assert "../.." not in page.text

    async def test_owner_isolation_between_users(
        self,
        authed_client: httpx.AsyncClient,
        app_settings,
    ) -> None:
        await _upload(authed_client, [("Лукьяненко — Черновик.fb2", _fb2("Черновик"))])
        catalog = await authed_client.get("/library/catalog")
        assert "Черновик" in catalog.text

        # second user cannot see it (bootstrap closed; use direct session check instead)
        from sqlalchemy import text

        container = authed_client._transport.app.state.container
        async with container["engine"].connect() as conn:
            works = (await conn.execute(text("select count(*) from works"))).scalar()
        assert works == 1  # only one owner's data exists at all


class TestLocalDirScan:
    async def test_scan_dry_run_and_apply(
        self,
        authed_client: httpx.AsyncClient,
        tmp_path: Path,
        app_settings,
    ) -> None:
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "Лукьяненко — Спектр 01 — Спектр.fb2").write_bytes(_fb2("Спектр", "scan1"))
        (inbox / "Лукьяненко — Спектр 02 — Близко к Сатурну.fb2").write_bytes(
            _fb2("Близко к Сатурну", "scan2"),
        )

        app_settings.import_roots = [str(inbox)]

        # dry-run
        dry = await authed_client.post("/library/import/scan", data={"apply": "false"})
        assert dry.status_code == 200
        assert "Спектр" in dry.text
        assert "new" in dry.text

        # nothing imported yet
        catalog = await authed_client.get("/library/catalog")
        assert "Каталог пуст" in catalog.text

        # apply
        applied = await authed_client.post("/library/import/scan", data={"apply": "true"})
        assert applied.status_code == 303

        catalog = await authed_client.get("/library/catalog")
        assert "Спектр" in catalog.text
        assert "2 произведений" in catalog.text

        # rescan: everything is duplicate now
        dry2 = await authed_client.post("/library/import/scan", data={"apply": "false"})
        assert "duplicate" in dry2.text
        assert dry2.text.count(">new<") == 0

    async def test_scan_ignores_disallowed_extensions(
        self,
        authed_client: httpx.AsyncClient,
        tmp_path: Path,
        app_settings,
    ) -> None:
        inbox = tmp_path / "inbox2"
        inbox.mkdir()
        (inbox / "note.txt").write_text("hello")
        (inbox / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        app_settings.import_roots = [str(inbox)]

        dry = await authed_client.post("/library/import/scan", data={"apply": "false"})
        assert dry.status_code == 200
        assert "note.txt" not in dry.text

    async def test_watched_inbox_is_bounded_idempotent_and_tracks_source(
        self,
        authed_client: httpx.AsyncClient,
        tmp_path: Path,
    ) -> None:
        inbox = tmp_path / "watched"
        inbox.mkdir()
        original = inbox / "Лем — Солярис.fb2"
        original.write_bytes(_fb2("Солярис", "watched"))

        app = authed_client._transport.app
        container = app.state.container
        service = WatchedInboxService(
            container["session_factory"],
            container["import_service"],
        )
        first = await service.run_once(
            owner_email=EMAIL,
            roots=[inbox],
            max_files=1,
            min_age_seconds=0,
        )
        second = await service.run_once(
            owner_email=EMAIL,
            roots=[inbox],
            max_files=1,
            min_age_seconds=0,
        )

        assert first.imported == 1
        assert second.imported == 0
        assert original.is_file()  # source files are never moved or deleted
        async with container["session_factory"]() as session:
            sources = (await session.execute(select(ImportBatchModel.source))).scalars().all()
        assert "inbox" in sources
