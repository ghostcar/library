"""Integration tests: repositories against real PostgreSQL.

Run via scripts/test.sh (starts compose.test.yaml) or:
    pytest -m integration
Requires LIBRARY_TEST_DATABASE_URL (default 127.0.0.1:55441/library_test).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from portal.modules.library.application.services import CatalogService, RegisterWorkInput
from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import (
    AssetFormat,
    AssetKind,
    MembershipType,
    ReadingChangeSource,
    ReadingStatus,
)
from portal.modules.library.domain.value_objects import Sha256
from portal.modules.library.infrastructure.repositories import (
    AssetRepository,
    AuthorRepository,
    ReadingStateRepository,
    SeriesRepository,
    SourceRecordRepository,
    WorkRepository,
)

pytestmark = pytest.mark.integration

SHA_A = "ab" * 32
SHA_B = "cd" * 32


async def test_register_work_roundtrip(db_session) -> None:
    owner = uuid4()
    works = WorkRepository(db_session)
    authors = AuthorRepository(db_session)
    series = SeriesRepository(db_session)
    service = CatalogService(works=works, authors=authors, series=series)

    work = await service.register_work(
        RegisterWorkInput(
            owner_id=owner,
            title="Обретение Мидаса",
            author_names=["Джеймс Кори"],
            language="ru",
            series_title="Пространство",
            series_index_raw="5.5",
            series_membership_type=MembershipType.MAIN,
        ),
    )

    loaded = await works.get(owner, work.id)
    assert loaded is not None
    assert loaded.title == "Обретение Мидаса"
    assert loaded.language == "ru"
    assert len(loaded.authors) == 1

    series_row = await series.find_by_title(owner, "Пространство")
    assert series_row is not None
    memberships = await series.list_memberships(owner, series_row.id)
    assert len(memberships) == 1
    assert str(memberships[0].index) == "5.5"
    assert memberships[0].index_sort is not None


async def test_find_by_title_is_case_and_whitespace_insensitive(db_session) -> None:
    owner = uuid4()
    works = WorkRepository(db_session)
    await works.add(de.Work(owner_id=owner, title="The  Green Mile"))

    found = await works.find_by_title(owner, "the green mile")
    assert len(found) == 1


async def test_owner_isolation(db_session) -> None:
    owner_a, owner_b = uuid4(), uuid4()
    works = WorkRepository(db_session)
    await works.add(de.Work(owner_id=owner_a, title="Приватная книга"))

    found = await works.find_by_title(owner_a, "Приватная книга")
    assert len(found) == 1
    assert await works.get(owner_b, found[0].id) is None
    assert await works.find_by_title(owner_b, "Приватная книга") == []


async def test_asset_deduplication_by_sha256(db_session) -> None:
    owner = uuid4()
    assets = AssetRepository(db_session)
    await assets.add(
        de.Asset(
            owner_id=owner,
            sha256=Sha256(SHA_A),
            format=AssetFormat.FB2,
            kind=AssetKind.ORIGINAL,
            size_bytes=1024,
            storage_path=f"originals/ab/{SHA_A}.fb2",
            original_filename="Круз — Эпоха мёртвых 01 — Начало.fb2",
        ),
    )
    duplicate = await assets.get_by_sha256(owner, Sha256(SHA_A))
    assert duplicate is not None
    assert duplicate.original_filename == "Круз — Эпоха мёртвых 01 — Начало.fb2"

    other_owner = await assets.get_by_sha256(uuid4(), Sha256(SHA_A))
    assert other_owner is None


async def test_asset_relation_normalized_derivative(db_session) -> None:
    owner = uuid4()
    assets = AssetRepository(db_session)
    original = await assets.add(
        de.Asset(
            owner_id=owner,
            sha256=Sha256(SHA_A),
            format=AssetFormat.FB2,
            kind=AssetKind.ORIGINAL,
            size_bytes=100,
            storage_path=f"originals/ab/{SHA_A}.fb2",
        ),
    )
    derivative = await assets.add(
        de.Asset(
            owner_id=owner,
            sha256=Sha256(SHA_B),
            format=AssetFormat.EPUB,
            kind=AssetKind.NORMALIZED,
            size_bytes=80,
            storage_path=f"derivatives/cd/{SHA_B}.epub",
        ),
    )
    await assets.add_relation(
        de.AssetRelation(
            owner_id=owner,
            asset_id=derivative.id,
            related_asset_id=original.id,
            relation_type=de.AssetRelationType.NORMALIZED,
        ),
    )
    assert await assets.get(owner, derivative.id) is not None


async def test_source_record_unique_per_adapter_external(db_session) -> None:
    owner = uuid4()
    records = SourceRecordRepository(db_session)
    record = await records.add(
        de.SourceRecord(
            owner_id=owner,
            adapter_id="author_today",
            external_id="12345",
            url="https://author.today/work/12345",
            raw_metadata={"title": "Тест"},
        ),
    )
    found = await records.get_by_external(owner, "author_today", "12345")
    assert found is not None
    assert found.id == record.id

    work_repo = WorkRepository(db_session)
    work = de.Work(owner_id=owner, title="Связанная книга")
    await work_repo.add(work)
    assert await records.link_work(owner, record.id, work.id)
    assert (await records.get_by_external(owner, "author_today", "12345")).work_id == work.id  # type: ignore[union-attr]


async def test_reading_state_upsert_and_transition(db_session) -> None:
    owner = uuid4()
    works = WorkRepository(db_session)
    states = ReadingStateRepository(db_session)
    work = de.Work(owner_id=owner, title="Книга с прогрессом")
    await works.add(work)

    state = de.ReadingState(owner_id=owner, work_id=work.id)
    await states.upsert(state)
    loaded = await states.get_for_work(owner, work.id)
    assert loaded is not None
    assert loaded.status is ReadingStatus.UNREAD

    loaded.transition(ReadingStatus.READING, ReadingChangeSource.MANUAL)
    await states.upsert(loaded)
    again = await states.get_for_work(owner, work.id)
    assert again is not None
    assert again.status is ReadingStatus.READING
    assert again.change_source is ReadingChangeSource.MANUAL


async def test_series_memberships_ordered_by_sort_key(db_session) -> None:
    owner = uuid4()
    series_repo = SeriesRepository(db_session)
    works = WorkRepository(db_session)
    series = de.Series(owner_id=owner, title="Эпоха мёртвых")
    await series_repo.add(series)

    for raw in ["3", "1", "2", "unknown"]:
        work = de.Work(owner_id=owner, title=f"Книга {raw}")
        await works.add(work)
        await series_repo.add_membership(
            de.SeriesMembership(
                owner_id=owner,
                series_id=series.id,
                work_id=work.id,
                index=de.SeriesIndex.parse(raw),
            ),
        )

    memberships = await series_repo.list_memberships(owner, series.id)
    ordered_raws = [m.index.raw for m in memberships]
    assert ordered_raws[:3] == ["1", "2", "3"]  # numeric first, ascending
    assert ordered_raws[3] == "unknown"  # null sort key last
