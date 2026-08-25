"""Async repositories for the library module.

Repositories accept/return domain entities; ORM never leaks upward.
Every method filters by owner_id (owner scoping, master prompt 12).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.domain import entities as de
from portal.modules.library.domain.value_objects import SeriesIndex, Sha256
from portal.modules.library.infrastructure import mappers as mp
from portal.modules.library.infrastructure import orm


class AuthorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, author: de.Author) -> de.Author:
        self._session.add(mp.author_to_orm(author))
        await self._session.flush()
        return author

    async def add_alias(self, alias: de.AuthorAlias) -> None:
        self._session.add(
            orm.AuthorAliasModel(
                owner_id=alias.owner_id,
                author_id=alias.author_id,
                alias=alias.alias,
                alias_normalized=de.normalize_title(alias.alias),
            ),
        )

    async def get(self, owner_id: UUID, author_id: UUID) -> de.Author | None:
        row = await self._session.get(orm.AuthorModel, author_id)
        if row is None or row.owner_id != owner_id:
            return None
        return mp.author_to_domain(row)

    async def find_by_name(self, owner_id: UUID, name: str) -> de.Author | None:
        stmt = select(orm.AuthorModel).where(
            orm.AuthorModel.owner_id == owner_id,
            orm.AuthorModel.name_normalized == de.normalize_title(name),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mp.author_to_domain(row) if row else None


class WorkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, work: de.Work) -> de.Work:
        self._session.add(mp.work_to_orm(work))
        await self._session.flush()
        self._session.add_all(mp.work_authors_to_orm(work))
        await self._session.flush()
        return work

    async def get(self, owner_id: UUID, work_id: UUID) -> de.Work | None:
        row = await self._session.get(orm.WorkModel, work_id)
        if row is None or row.owner_id != owner_id:
            return None
        author_rows: Sequence[orm.WorkAuthorModel] = (
            (
                await self._session.execute(
                    select(orm.WorkAuthorModel)
                    .where(orm.WorkAuthorModel.work_id == work_id)
                    .order_by(orm.WorkAuthorModel.position),
                )
            )
            .scalars()
            .all()
        )
        return mp.work_to_domain(row, list(author_rows))

    async def find_by_title(self, owner_id: UUID, title: str) -> list[de.Work]:
        stmt = (
            select(orm.WorkModel)
            .where(
                orm.WorkModel.owner_id == owner_id,
                orm.WorkModel.title_normalized == de.normalize_title(title),
            )
            .order_by(orm.WorkModel.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mp.work_to_domain(r) for r in rows]

    async def list(self, owner_id: UUID, limit: int = 50, offset: int = 0) -> list[de.Work]:
        stmt = (
            select(orm.WorkModel)
            .where(orm.WorkModel.owner_id == owner_id)
            .order_by(orm.WorkModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mp.work_to_domain(r) for r in rows]


class SeriesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, series: de.Series) -> de.Series:
        self._session.add(mp.series_to_orm(series))
        await self._session.flush()
        return series

    async def add_alias(self, alias: de.SeriesAlias) -> None:
        self._session.add(
            orm.SeriesAliasModel(
                owner_id=alias.owner_id,
                series_id=alias.series_id,
                alias=alias.alias,
                alias_normalized=de.normalize_title(alias.alias),
            ),
        )

    async def get(self, owner_id: UUID, series_id: UUID) -> de.Series | None:
        row = await self._session.get(orm.SeriesModel, series_id)
        if row is None or row.owner_id != owner_id:
            return None
        return mp.series_to_domain(row)

    async def find_by_title(self, owner_id: UUID, title: str) -> de.Series | None:
        stmt = select(orm.SeriesModel).where(
            orm.SeriesModel.owner_id == owner_id,
            orm.SeriesModel.title_normalized == de.normalize_title(title),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mp.series_to_domain(row) if row else None

    async def add_membership(self, membership: de.SeriesMembership) -> None:
        self._session.add(mp.membership_to_orm(membership))
        await self._session.flush()

    async def list_memberships(self, owner_id: UUID, series_id: UUID) -> list[de.SeriesMembership]:
        stmt = (
            select(orm.SeriesMembershipModel)
            .where(
                orm.SeriesMembershipModel.owner_id == owner_id,
                orm.SeriesMembershipModel.series_id == series_id,
            )
            .order_by(orm.SeriesMembershipModel.index_sort.nulls_last())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mp.membership_to_domain(r) for r in rows]


class SourceRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: de.SourceRecord) -> de.SourceRecord:
        self._session.add(mp.source_record_to_orm(record))
        await self._session.flush()
        return record

    async def get_by_external(
        self,
        owner_id: UUID,
        adapter_id: str,
        external_id: str,
    ) -> de.SourceRecord | None:
        stmt = select(orm.SourceRecordModel).where(
            orm.SourceRecordModel.owner_id == owner_id,
            orm.SourceRecordModel.adapter_id == adapter_id,
            orm.SourceRecordModel.external_id == external_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mp.source_record_to_domain(row) if row else None

    async def link_work(self, owner_id: UUID, record_id: UUID, work_id: UUID) -> bool:
        row = await self._session.get(orm.SourceRecordModel, record_id)
        if row is None or row.owner_id != owner_id:
            return False
        row.work_id = work_id
        return True


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, asset: de.Asset) -> de.Asset:
        self._session.add(mp.asset_to_orm(asset))
        await self._session.flush()
        return asset

    async def get_by_sha256(self, owner_id: UUID, sha256: Sha256) -> de.Asset | None:
        stmt = select(orm.AssetModel).where(
            orm.AssetModel.owner_id == owner_id,
            orm.AssetModel.sha256 == str(sha256),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mp.asset_to_domain(row) if row else None

    async def get(self, owner_id: UUID, asset_id: UUID) -> de.Asset | None:
        row = await self._session.get(orm.AssetModel, asset_id)
        if row is None or row.owner_id != owner_id:
            return None
        return mp.asset_to_domain(row)

    async def add_relation(self, relation: de.AssetRelation) -> None:
        self._session.add(
            orm.AssetRelationModel(
                owner_id=relation.owner_id,
                asset_id=relation.asset_id,
                related_asset_id=relation.related_asset_id,
                relation_type=relation.relation_type.value,
            ),
        )


class ReadingStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, state: de.ReadingState) -> de.ReadingState:
        stmt = select(orm.ReadingStateModel).where(
            orm.ReadingStateModel.owner_id == state.owner_id,
            orm.ReadingStateModel.work_id == state.work_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            self._session.add(mp.reading_state_to_orm(state))
            return state
        row.status = state.status.value
        row.progress_percent = state.progress_percent
        row.change_source = state.change_source.value
        row.changed_at = state.changed_at
        return mp.reading_state_to_domain(row)

    async def get_for_work(self, owner_id: UUID, work_id: UUID) -> de.ReadingState | None:
        stmt = select(orm.ReadingStateModel).where(
            orm.ReadingStateModel.owner_id == owner_id,
            orm.ReadingStateModel.work_id == work_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mp.reading_state_to_domain(row) if row else None


def parse_series_index(raw: str) -> SeriesIndex:
    return SeriesIndex.parse(raw)
