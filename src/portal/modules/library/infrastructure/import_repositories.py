"""Repositories for the import pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.domain import import_entities as ie
from portal.modules.library.domain.value_objects import Sha256
from portal.modules.library.infrastructure.import_orm import (
    DuplicateCandidateModel,
    ImportBatchModel,
    ImportItemModel,
)
from portal.modules.library.infrastructure.orm import AssetModel


def _batch_to_domain(m: ImportBatchModel) -> ie.ImportBatch:
    return ie.ImportBatch(
        owner_id=m.owner_id,
        source=ie.ImportSource(m.source),
        status=ie.BatchStatus(m.status),
        id=m.id,
        created_at=m.created_at,
        completed_at=m.completed_at,
    )


def _item_to_domain(m: ImportItemModel) -> ie.ImportItem:
    return ie.ImportItem(
        batch_id=m.batch_id,
        owner_id=m.owner_id,
        filename=m.filename,
        status=ie.ItemStatus(m.status),
        size_bytes=m.size_bytes,
        sha256=Sha256(m.sha256) if m.sha256 else None,
        detected_format=m.detected_format,
        asset_id=m.asset_id,
        work_id=m.work_id,
        match_evidence=dict(m.match_evidence or {}),
        error=m.error,
        id=m.id,
        created_at=m.created_at,
    )


def _candidate_to_domain(m: DuplicateCandidateModel) -> ie.DuplicateCandidate:
    return ie.DuplicateCandidate(
        owner_id=m.owner_id,
        asset_id=m.asset_id,
        suspected_of_asset_id=m.suspected_of_asset_id,
        reason=ie.DuplicateReason(m.reason),
        status=ie.CandidateStatus(m.status),
        id=m.id,
        created_at=m.created_at,
    )


class ImportBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, batch: ie.ImportBatch) -> ie.ImportBatch:
        self._session.add(
            ImportBatchModel(
                id=batch.id,
                owner_id=batch.owner_id,
                source=batch.source.value,
                status=batch.status.value,
                created_at=batch.created_at,
            ),
        )
        await self._session.flush()
        return batch

    async def get(self, owner_id: UUID, batch_id: UUID) -> ie.ImportBatch | None:
        row = await self._session.get(ImportBatchModel, batch_id)
        if row is None or row.owner_id != owner_id:
            return None
        return _batch_to_domain(row)

    async def update_status(self, batch: ie.ImportBatch) -> None:
        await self._session.execute(
            update(ImportBatchModel)
            .where(ImportBatchModel.id == batch.id)
            .values(status=batch.status.value, completed_at=batch.completed_at),
        )

    async def list_recent(self, owner_id: UUID, limit: int = 20) -> list[ie.ImportBatch]:
        stmt = (
            select(ImportBatchModel)
            .where(ImportBatchModel.owner_id == owner_id)
            .order_by(ImportBatchModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_batch_to_domain(r) for r in rows]


class ImportItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: ie.ImportItem) -> ie.ImportItem:
        self._session.add(
            ImportItemModel(
                id=item.id,
                batch_id=item.batch_id,
                owner_id=item.owner_id,
                filename=item.filename,
                status=item.status.value,
                size_bytes=item.size_bytes,
                sha256=str(item.sha256) if item.sha256 else None,
                detected_format=item.detected_format,
                asset_id=item.asset_id,
                work_id=item.work_id,
                match_evidence=item.match_evidence,
                error=item.error,
                created_at=item.created_at,
            ),
        )
        await self._session.flush()
        return item

    async def update(self, item: ie.ImportItem) -> None:
        await self._session.execute(
            update(ImportItemModel)
            .where(ImportItemModel.id == item.id)
            .values(
                status=item.status.value,
                size_bytes=item.size_bytes,
                sha256=str(item.sha256) if item.sha256 else None,
                detected_format=item.detected_format,
                asset_id=item.asset_id,
                work_id=item.work_id,
                match_evidence=item.match_evidence,
                error=item.error,
            ),
        )

    async def get(self, owner_id: UUID, item_id: UUID) -> ie.ImportItem | None:
        row = await self._session.get(ImportItemModel, item_id)
        if row is None or row.owner_id != owner_id:
            return None
        return _item_to_domain(row)

    async def list_for_batch(self, owner_id: UUID, batch_id: UUID) -> list[ie.ImportItem]:
        stmt = (
            select(ImportItemModel)
            .where(
                ImportItemModel.owner_id == owner_id,
                ImportItemModel.batch_id == batch_id,
            )
            .order_by(ImportItemModel.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_item_to_domain(r) for r in rows]

    async def list_recent_unmatched(self, owner_id: UUID, limit: int = 50) -> list[ie.ImportItem]:
        return await self.list_recent_by_status(
            owner_id,
            statuses=[ie.ItemStatus.STORED_UNMATCHED.value],
            limit=limit,
        )

    async def list_recent_by_status(
        self,
        owner_id: UUID,
        statuses: list[str],
        limit: int = 50,
    ) -> list[ie.ImportItem]:
        stmt = (
            select(ImportItemModel)
            .where(
                ImportItemModel.owner_id == owner_id,
                ImportItemModel.status.in_(statuses),
            )
            .order_by(ImportItemModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_item_to_domain(r) for r in rows]


class DuplicateCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, candidate: ie.DuplicateCandidate) -> ie.DuplicateCandidate:
        self._session.add(
            DuplicateCandidateModel(
                id=candidate.id,
                owner_id=candidate.owner_id,
                asset_id=candidate.asset_id,
                suspected_of_asset_id=candidate.suspected_of_asset_id,
                reason=candidate.reason.value,
                status=candidate.status.value,
                created_at=candidate.created_at,
            ),
        )
        await self._session.flush()
        return candidate

    async def exists_pending(
        self,
        owner_id: UUID,
        asset_id: UUID,
        suspected_of_asset_id: UUID,
    ) -> bool:
        stmt = select(DuplicateCandidateModel.id).where(
            DuplicateCandidateModel.owner_id == owner_id,
            DuplicateCandidateModel.asset_id == asset_id,
            DuplicateCandidateModel.suspected_of_asset_id == suspected_of_asset_id,
            DuplicateCandidateModel.status == ie.CandidateStatus.PENDING.value,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def list_pending(self, owner_id: UUID, limit: int = 50) -> list[ie.DuplicateCandidate]:
        stmt = (
            select(DuplicateCandidateModel)
            .where(
                DuplicateCandidateModel.owner_id == owner_id,
                DuplicateCandidateModel.status == ie.CandidateStatus.PENDING.value,
            )
            .order_by(DuplicateCandidateModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_candidate_to_domain(r) for r in rows]

    async def resolve(
        self,
        owner_id: UUID,
        candidate_id: UUID,
        decision: ie.CandidateStatus,
    ) -> bool:
        if decision is ie.CandidateStatus.PENDING:
            return False
        result = await self._session.execute(
            update(DuplicateCandidateModel)
            .where(
                DuplicateCandidateModel.owner_id == owner_id,
                DuplicateCandidateModel.id == candidate_id,
                DuplicateCandidateModel.status == ie.CandidateStatus.PENDING.value,
            )
            .values(status=decision.value),
        )
        return int(result.rowcount) > 0  # type: ignore[attr-defined]


class CatalogQueries:
    """Read-side queries for catalog UI."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def works_with_authors(
        self,
        owner_id: UUID,
        limit: int = 100,
        offset: int = 0,
        query: str = "",
    ) -> list[dict[str, object]]:
        from portal.modules.library.domain.entities import normalize_title
        from portal.modules.library.infrastructure.orm import (
            AuthorModel,
            SeriesMembershipModel,
            SeriesModel,
            WorkAuthorModel,
            WorkModel,
        )

        works_stmt = select(WorkModel).where(WorkModel.owner_id == owner_id)
        normalized_query = normalize_title(query)
        if normalized_query:
            pattern = f"%{normalized_query}%"
            works_stmt = (
                works_stmt.outerjoin(
                    WorkAuthorModel,
                    WorkAuthorModel.work_id == WorkModel.id,
                )
                .outerjoin(AuthorModel, AuthorModel.id == WorkAuthorModel.author_id)
                .outerjoin(
                    SeriesMembershipModel,
                    SeriesMembershipModel.work_id == WorkModel.id,
                )
                .outerjoin(SeriesModel, SeriesModel.id == SeriesMembershipModel.series_id)
                .where(
                    or_(
                        WorkModel.title_normalized.like(pattern),
                        AuthorModel.name_normalized.like(pattern),
                        SeriesModel.title_normalized.like(pattern),
                    ),
                )
                .distinct()
            )

        work_rows = (
            (
                await self._session.execute(
                    works_stmt.order_by(WorkModel.created_at.desc()).limit(limit).offset(offset),
                )
            )
            .scalars()
            .all()
        )
        if not work_rows:
            return []
        work_ids = [w.id for w in work_rows]

        author_rows = (
            await self._session.execute(
                select(WorkAuthorModel, AuthorModel)
                .join(AuthorModel, AuthorModel.id == WorkAuthorModel.author_id)
                .where(
                    WorkAuthorModel.work_id.in_(work_ids),
                    WorkAuthorModel.role == "author",
                )
                .order_by(WorkAuthorModel.position),
            )
        ).all()
        authors_by_work: dict[UUID, list[str]] = {}
        for link, author in author_rows:
            authors_by_work.setdefault(link.work_id, []).append(author.name)

        series_rows = (
            await self._session.execute(
                select(SeriesMembershipModel, SeriesModel)
                .join(SeriesModel, SeriesModel.id == SeriesMembershipModel.series_id)
                .where(
                    SeriesMembershipModel.work_id.in_(work_ids),
                    SeriesMembershipModel.owner_id == owner_id,
                ),
            )
        ).all()
        series_by_work: dict[UUID, list[dict[str, str]]] = {}
        for membership, series in series_rows:
            series_by_work.setdefault(membership.work_id, []).append(
                {"title": series.title, "index_raw": membership.index_raw},
            )

        return [
            {
                "id": work.id,
                "title": work.title,
                "language": work.language,
                "authors": authors_by_work.get(work.id, []),
                "series": series_by_work.get(work.id, []),
                "created_at": work.created_at,
            }
            for work in work_rows
        ]

    async def work_detail(self, owner_id: UUID, work_id: UUID) -> dict[str, object] | None:
        from portal.modules.library.infrastructure.orm import (
            AuthorModel,
            SeriesMembershipModel,
            SeriesModel,
            WorkAuthorModel,
            WorkModel,
        )

        work = await self._session.get(WorkModel, work_id)
        if work is None or work.owner_id != owner_id:
            return None

        author_rows = (
            (
                await self._session.execute(
                    select(AuthorModel)
                    .join(WorkAuthorModel, WorkAuthorModel.author_id == AuthorModel.id)
                    .where(WorkAuthorModel.work_id == work_id)
                    .order_by(WorkAuthorModel.position),
                )
            )
            .scalars()
            .all()
        )

        series_rows = (
            await self._session.execute(
                select(SeriesMembershipModel, SeriesModel)
                .join(SeriesModel, SeriesModel.id == SeriesMembershipModel.series_id)
                .where(SeriesMembershipModel.work_id == work_id),
            )
        ).all()

        asset_rows = (
            (
                await self._session.execute(
                    select(AssetModel)
                    .where(AssetModel.work_id == work_id, AssetModel.owner_id == owner_id)
                    .order_by(AssetModel.created_at),
                )
            )
            .scalars()
            .all()
        )

        return {
            "id": work.id,
            "title": work.title,
            "language": work.language,
            "description": work.description,
            "authors": list(author_rows),
            "series": [(m, s) for m, s in series_rows],
            "assets": list(asset_rows),
        }

    async def counts(self, owner_id: UUID) -> dict[str, int]:
        from portal.modules.library.infrastructure.orm import (
            AuthorModel,
            SeriesModel,
            WorkModel,
        )

        async def _count(model: type[Any]) -> int:
            stmt = select(func.count()).select_from(model)
            stmt = stmt.where(model.owner_id == owner_id)
            return int(await self._session.scalar(stmt) or 0)

        return {
            "works": await _count(WorkModel),
            "authors": await _count(AuthorModel),
            "series": await _count(SeriesModel),
            "assets": await _count(AssetModel),
        }
