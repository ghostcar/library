"""Reading state use cases: transitions with history, bulk actions, events."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.events.repository import OutboxRepository
from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import ReadingChangeSource, ReadingStatus
from portal.modules.library.infrastructure.orm import (
    SeriesMembershipModel,
    WorkModel,
)
from portal.modules.library.infrastructure.repositories import ReadingStateRepository
from portal.modules.library.infrastructure.series_orm import ReadingStateHistoryModel


class IllegalTransitionError(ValueError):
    pass


@dataclass(slots=True)
class StatusChange:
    work_id: UUID
    from_status: ReadingStatus | None
    to_status: ReadingStatus


class ReadingStateService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def set_status(
        self,
        owner_id: UUID,
        work_id: UUID,
        new_status: ReadingStatus,
        source: ReadingChangeSource = ReadingChangeSource.MANUAL,
    ) -> StatusChange:
        """Validated transition + history row + events (one transaction)."""
        async with self._session_factory() as session, session.begin():
            work = await session.get(WorkModel, work_id)
            if work is None or work.owner_id != owner_id:
                msg = f"work {work_id} not found"
                raise LookupError(msg)

            repo = ReadingStateRepository(session)
            state = await repo.get_for_work(owner_id, work_id)
            from_status = state.status if state else None

            if state is None:
                if new_status is not ReadingStatus.UNREAD:
                    state = de.ReadingState(owner_id=owner_id, work_id=work_id)
                    state.transition(new_status, source)
                    await repo.upsert(state)
            else:
                if state.status is new_status:
                    return StatusChange(work_id, from_status, new_status)
                state.transition(new_status, source)
                await repo.upsert(state)

            session.add(
                ReadingStateHistoryModel(
                    owner_id=owner_id,
                    work_id=work_id,
                    from_status=from_status.value if from_status else None,
                    to_status=new_status.value,
                    source=source.value,
                ),
            )
            await self._emit(session, owner_id, work_id, new_status)
            return StatusChange(work_id, from_status, new_status)

    async def mark_read_bulk(
        self,
        owner_id: UUID,
        work_ids: list[UUID],
        source: ReadingChangeSource = ReadingChangeSource.MANUAL,
    ) -> list[StatusChange]:
        changes: list[StatusChange] = []
        for work_id in work_ids:
            try:
                changes.append(
                    await self.set_status(owner_id, work_id, ReadingStatus.READ, source),
                )
            except (LookupError, ValueError):
                continue  # one bad id must not kill the bulk operation
        return changes

    async def history_for_work(
        self,
        owner_id: UUID,
        work_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            stmt = (
                select(ReadingStateHistoryModel)
                .where(
                    ReadingStateHistoryModel.owner_id == owner_id,
                    ReadingStateHistoryModel.work_id == work_id,
                )
                .order_by(ReadingStateHistoryModel.changed_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "from_status": r.from_status,
                    "to_status": r.to_status,
                    "source": r.source,
                    "changed_at": r.changed_at,
                }
                for r in rows
            ]

    async def continue_reading(self, owner_id: UUID, limit: int = 10) -> list[dict[str, object]]:
        """Works currently being read, most recently changed first."""
        async with self._session_factory() as session:
            from portal.modules.library.infrastructure.orm import ReadingStateModel

            stmt = (
                select(ReadingStateModel, WorkModel)
                .join(WorkModel, WorkModel.id == ReadingStateModel.work_id)
                .where(
                    ReadingStateModel.owner_id == owner_id,
                    ReadingStateModel.status == ReadingStatus.READING.value,
                )
                .order_by(ReadingStateModel.changed_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            return [
                {"work_id": work.id, "title": work.title, "changed_at": state.changed_at}
                for state, work in rows
            ]

    async def recently_added(self, owner_id: UUID, limit: int = 10) -> list[dict[str, object]]:
        async with self._session_factory() as session:
            stmt = (
                select(WorkModel)
                .where(WorkModel.owner_id == owner_id)
                .order_by(WorkModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [{"work_id": w.id, "title": w.title, "created_at": w.created_at} for w in rows]

    async def reading_queue(self, owner_id: UUID, limit: int = 30) -> list[dict[str, object]]:
        """Next-up books: per active series first, then standalone unread."""
        from portal.modules.library.application.series_state_service import SeriesStateService
        from portal.modules.library.infrastructure.orm import ReadingStateModel

        async with self._session_factory() as session:
            series_service = SeriesStateService(session)
            overview = await series_service.list_series_overview(owner_id)

            queue: list[dict[str, object]] = []
            seen_works: set[UUID] = set()

            # in-progress series first, then planned ones: their next unread
            active = [s for s in overview if s.series_status == "in_progress"]
            planned = [s for s in overview if s.series_status == "planned"]
            for state in [*active, *planned]:
                reason = (
                    "next_in_series" if state.series_status == "in_progress" else "start_series"
                )
                nxt = state.next_available_unread
                if nxt is not None and nxt.work_id not in seen_works:
                    seen_works.add(nxt.work_id)
                    queue.append(
                        {
                            "work_id": nxt.work_id,
                            "title": nxt.title,
                            "series_title": state.title,
                            "index_raw": nxt.index_raw,
                            "reason": reason,
                        },
                    )

            # standalone unread works (not in any series already queued)
            standalone = (
                await session.execute(
                    select(WorkModel, ReadingStateModel)
                    .outerjoin(
                        ReadingStateModel,
                        (ReadingStateModel.work_id == WorkModel.id)
                        & (ReadingStateModel.owner_id == owner_id),
                    )
                    .outerjoin(
                        SeriesMembershipModel,
                        SeriesMembershipModel.work_id == WorkModel.id,
                    )
                    .where(
                        WorkModel.owner_id == owner_id,
                        SeriesMembershipModel.id.is_(None),
                        ReadingStateModel.status.is_(None)
                        | (ReadingStateModel.status == ReadingStatus.UNREAD.value),
                    )
                    .order_by(WorkModel.created_at.desc())
                    .limit(limit),
                )
            ).all()
            for work, _state in standalone:
                if work.id not in seen_works:
                    seen_works.add(work.id)
                    queue.append(
                        {
                            "work_id": work.id,
                            "title": work.title,
                            "series_title": None,
                            "index_raw": None,
                            "reason": "unread",
                        },
                    )
            return queue[:limit]

    async def _emit(
        self,
        session: AsyncSession,
        owner_id: UUID,
        work_id: UUID,
        status: ReadingStatus,
    ) -> None:
        outbox = OutboxRepository(session)
        await outbox.enqueue(
            "BookMarkedRead" if status is ReadingStatus.READ else "SeriesProgressChanged",
            {"owner_id": str(owner_id), "work_id": str(work_id), "status": status.value},
        )
