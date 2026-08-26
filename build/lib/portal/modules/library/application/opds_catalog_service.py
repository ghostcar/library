"""OPDS catalog queries (read side). Returns plain dicts for serializers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.adapters.source_orm import SourceObservationModel
from portal.modules.library.infrastructure.orm import (
    AssetModel,
    AuthorModel,
    ReadingStateModel,
    SeriesMembershipModel,
    SeriesModel,
    WorkAuthorModel,
    WorkModel,
)


class OpdsCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _authors_for_works(self, work_ids: list[UUID]) -> dict[UUID, list[str]]:
        if not work_ids:
            return {}
        rows = (
            await self._session.execute(
                select(WorkAuthorModel.work_id, AuthorModel.name)
                .join(AuthorModel, AuthorModel.id == WorkAuthorModel.author_id)
                .where(
                    WorkAuthorModel.work_id.in_(work_ids),
                    WorkAuthorModel.role == "author",
                )
                .order_by(WorkAuthorModel.position),
            )
        ).all()
        result: dict[UUID, list[str]] = {}
        for work_id, name in rows:
            result.setdefault(work_id, []).append(name)
        return result

    async def _series_for_works(self, work_ids: list[UUID]) -> dict[UUID, str]:
        if not work_ids:
            return {}
        rows = (
            await self._session.execute(
                select(SeriesMembershipModel.work_id, SeriesModel.title)
                .join(SeriesModel, SeriesModel.id == SeriesMembershipModel.series_id)
                .where(SeriesMembershipModel.work_id.in_(work_ids)),
            )
        ).all()
        return {work_id: title for work_id, title in rows}

    async def _assets_for_works(
        self,
        owner_id: UUID,
        work_ids: list[UUID],
    ) -> dict[UUID, list[dict[str, object]]]:
        """Preferred asset first, then original; normalized derivatives win via is_preferred."""
        if not work_ids:
            return {}
        rows = (
            (
                await self._session.execute(
                    select(AssetModel)
                    .where(
                        AssetModel.owner_id == owner_id,
                        AssetModel.work_id.in_(work_ids),
                    )
                    .order_by(
                        # preferred first; then normalized derivatives, then originals
                        AssetModel.is_preferred.desc(),
                        (AssetModel.kind == "original").asc(),
                        AssetModel.created_at.asc(),
                    ),
                )
            )
            .scalars()
            .all()
        )
        by_work: dict[UUID, list[dict[str, object]]] = {}
        for asset in rows:
            if asset.work_id is None:
                continue
            by_work.setdefault(asset.work_id, []).append(
                {"asset_id": asset.id, "format": asset.format},
            )
        return by_work

    async def _works_entries(
        self,
        owner_id: UUID,
        works: list[WorkModel],
    ) -> list[dict[str, object]]:
        work_ids = [w.id for w in works]
        authors = await self._authors_for_works(work_ids)
        series = await self._series_for_works(work_ids)
        assets = await self._assets_for_works(owner_id, work_ids)
        return [
            {
                "work_id": work.id,
                "title": work.title,
                "updated": work.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if work.updated_at
                else None,
                "authors": authors.get(work.id, []),
                "series": series.get(work.id),
                "assets": assets.get(work.id, []),
            }
            for work in works
        ]

    async def recent(self, owner_id: UUID, limit: int = 50) -> list[dict[str, object]]:
        works = (
            (
                await self._session.execute(
                    select(WorkModel)
                    .where(WorkModel.owner_id == owner_id)
                    .order_by(WorkModel.created_at.desc())
                    .limit(limit),
                )
            )
            .scalars()
            .all()
        )
        return await self._works_entries(owner_id, list(works))

    async def unread(self, owner_id: UUID, limit: int = 50) -> list[dict[str, object]]:
        stmt = (
            select(WorkModel)
            .outerjoin(
                ReadingStateModel,
                (ReadingStateModel.work_id == WorkModel.id)
                & (ReadingStateModel.owner_id == owner_id),
            )
            .where(
                WorkModel.owner_id == owner_id,
                or_(
                    ReadingStateModel.status.is_(None),
                    ReadingStateModel.status == "unread",
                    ReadingStateModel.status == "reading",
                ),
            )
            .order_by(WorkModel.created_at.desc())
            .limit(limit)
        )
        works = (await self._session.execute(stmt)).scalars().all()
        return await self._works_entries(owner_id, list(works))

    async def series_list(self, owner_id: UUID) -> list[dict[str, object]]:
        rows = (
            await self._session.execute(
                select(
                    SeriesModel.id,
                    SeriesModel.title,
                    func.count(SeriesMembershipModel.id),
                )
                .join(
                    SeriesMembershipModel,
                    SeriesMembershipModel.series_id == SeriesModel.id,
                )
                .where(SeriesModel.owner_id == owner_id)
                .group_by(SeriesModel.id, SeriesModel.title)
                .order_by(SeriesModel.title),
            )
        ).all()
        return [{"id": sid, "title": title, "count": int(count)} for sid, title, count in rows]

    async def series_works(self, owner_id: UUID, series_id: UUID) -> list[dict[str, object]] | None:
        series = await self._session.get(SeriesModel, series_id)
        if series is None or series.owner_id != owner_id:
            return None
        works = (
            (
                await self._session.execute(
                    select(WorkModel)
                    .join(
                        SeriesMembershipModel,
                        SeriesMembershipModel.work_id == WorkModel.id,
                    )
                    .where(
                        SeriesMembershipModel.series_id == series_id,
                        SeriesMembershipModel.owner_id == owner_id,
                    )
                    .order_by(SeriesMembershipModel.index_sort.nulls_last(), WorkModel.title),
                )
            )
            .scalars()
            .all()
        )
        entries = await self._works_entries(owner_id, list(works))
        for entry, work in zip(entries, works, strict=False):
            membership = (
                await self._session.execute(
                    select(SeriesMembershipModel.index_raw).where(
                        SeriesMembershipModel.series_id == series_id,
                        SeriesMembershipModel.work_id == work.id,
                    ),
                )
            ).scalar_one_or_none()
            if membership:
                entry["series"] = f"{series.title} №{membership}"
        return entries

    async def authors_list(self, owner_id: UUID) -> list[dict[str, object]]:
        rows = (
            await self._session.execute(
                select(
                    AuthorModel.id,
                    AuthorModel.name,
                    func.count(WorkAuthorModel.id),
                )
                .join(WorkAuthorModel, WorkAuthorModel.author_id == AuthorModel.id)
                .where(AuthorModel.owner_id == owner_id)
                .group_by(AuthorModel.id, AuthorModel.name)
                .order_by(AuthorModel.sort_name.nulls_last(), AuthorModel.name),
            )
        ).all()
        return [{"id": aid, "title": name, "count": int(count)} for aid, name, count in rows]

    async def author_works(self, owner_id: UUID, author_id: UUID) -> list[dict[str, object]] | None:
        author = await self._session.get(AuthorModel, author_id)
        if author is None or author.owner_id != owner_id:
            return None
        works = (
            (
                await self._session.execute(
                    select(WorkModel)
                    .join(WorkAuthorModel, WorkAuthorModel.work_id == WorkModel.id)
                    .where(WorkAuthorModel.author_id == author_id)
                    .order_by(WorkModel.title),
                )
            )
            .scalars()
            .all()
        )
        return await self._works_entries(owner_id, list(works))

    async def search(self, owner_id: UUID, query: str, limit: int = 50) -> list[dict[str, object]]:
        pattern = f"%{query.strip().casefold()}%"
        stmt = (
            select(WorkModel)
            .outerjoin(WorkAuthorModel, WorkAuthorModel.work_id == WorkModel.id)
            .outerjoin(AuthorModel, AuthorModel.id == WorkAuthorModel.author_id)
            .where(
                WorkModel.owner_id == owner_id,
                or_(
                    WorkModel.title_normalized.ilike(pattern),
                    AuthorModel.name_normalized.ilike(pattern),
                ),
            )
            .distinct()
            .order_by(WorkModel.title)
            .limit(limit)
        )
        works = (await self._session.execute(stmt)).scalars().all()
        return await self._works_entries(owner_id, list(works))

    async def observations(self, owner_id: UUID, limit: int = 50) -> list[dict[str, object]]:
        """Watched-feed items: new releases not yet owned ('доступна для получения')."""
        rows = (
            (
                await self._session.execute(
                    select(SourceObservationModel)
                    .where(SourceObservationModel.owner_id == owner_id)
                    .order_by(SourceObservationModel.observed_at.desc())
                    .limit(limit),
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "work_id": r.id,  # not a real work: serializer uses urn:uuid of observation
                "title": r.title,
                "updated": r.observed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "authors": [r.author_name] if r.author_name else [],
                "series": f"Источник: {r.adapter_id}",
                "assets": [],
                "source_url": r.url,
            }
            for r in rows
        ]
