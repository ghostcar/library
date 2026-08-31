"""Derived series state (master prompt 5.3).

The highest owned index is NEVER treated as the series end: completion
comes from user confirmation or source data, never from arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.adapters.source_orm import SourceObservationModel
from portal.modules.library.domain.enums import MembershipType, ReadingStatus
from portal.modules.library.infrastructure.orm import (
    ReadingStateModel,
    SeriesMembershipModel,
    SeriesModel,
    WorkModel,
)
from portal.modules.library.infrastructure.series_orm import SeriesUserStateModel

# statuses that mean "user stopped engaging" — override derived status
USER_OVERRIDES = {"paused", "abandoned", "completed", "planned"}


@dataclass(slots=True)
class SeriesEntry:
    work_id: UUID
    title: str
    index_raw: str
    index_sort: Decimal | None
    membership_type: MembershipType
    reading_status: ReadingStatus

    @property
    def is_read(self) -> bool:
        return self.reading_status is ReadingStatus.READ


@dataclass(slots=True)
class SeriesSourceEntry:
    observation_id: UUID
    title: str
    author_name: str | None
    url: str | None
    work_id: UUID | None
    observed_at: datetime
    publication_status: str | None
    catalog_status: str


@dataclass(slots=True)
class DerivedSeriesState:
    series_id: UUID
    title: str
    entries: list[SeriesEntry] = field(default_factory=list)
    user_status_override: str | None = None
    has_new_release: bool = False  # Phase 6: source observations
    last_observed: datetime | None = None
    waiting_release: bool = False
    observation_evidence: list[dict[str, object]] = field(default_factory=list)
    source_entries: list[SeriesSourceEntry] = field(default_factory=list)

    @property
    def source_present_count(self) -> int:
        return sum(entry.catalog_status == "present" for entry in self.source_entries)

    @property
    def source_missing_count(self) -> int:
        return sum(entry.catalog_status == "missing" for entry in self.source_entries)

    @property
    def source_ambiguous_count(self) -> int:
        return sum(entry.catalog_status == "ambiguous" for entry in self.source_entries)

    @property
    def last_read(self) -> SeriesEntry | None:
        """Highest sorted entry with status=read."""
        read_entries = [e for e in self.entries if e.is_read]
        return read_entries[-1] if read_entries else None

    @property
    def last_owned(self) -> SeriesEntry | None:
        return self.entries[-1] if self.entries else None

    @property
    def next_available_unread(self) -> SeriesEntry | None:
        """First unread entry after the last read position (or first unread overall)."""
        if not self.entries:
            return None
        last_read_index = -1
        for position, entry in enumerate(self.entries):
            if entry.is_read:
                last_read_index = position
        for entry in self.entries[last_read_index + 1 :]:
            if not entry.is_read and entry.reading_status is not ReadingStatus.ABANDONED:
                return entry
        return None

    @property
    def missing_indices(self) -> list[str]:
        """Gaps between consecutive integer sort keys (e.g. 1,2,5 -> 3,4)."""
        missing: list[str] = []
        numeric = [
            e.index_sort
            for e in self.entries
            if e.index_sort is not None and e.index_sort == e.index_sort.to_integral_value()
        ]
        from itertools import pairwise

        for prev_sort, next_sort in pairwise(numeric):
            gap = int(next_sort) - int(prev_sort)
            if gap > 1:
                missing.extend(str(int(prev_sort) + offset) for offset in range(1, gap))
        return missing

    @property
    def series_status(self) -> str:
        """Derived status; explicit user override wins (master prompt 5.3)."""
        if self.user_status_override is not None:
            return self.user_status_override
        if not self.entries:
            return "planned"
        statuses = {e.reading_status for e in self.entries}
        if all(s is ReadingStatus.READ for s in statuses):
            # all owned books read != series completed (§5.3)
            return "caught_up"
        if statuses & {ReadingStatus.READING}:
            return "in_progress"
        if statuses & {ReadingStatus.READ}:
            return "in_progress"
        if statuses == {ReadingStatus.ABANDONED}:
            return "abandoned"
        return "planned"

    @property
    def completion_confidence(self) -> str:
        if self.user_status_override == "completed":
            return "high"  # user confirmed
        return "low"  # medium arrives with source observations (Phase 6)


class SeriesStateService:
    """Read-side computation of derived series state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_series(self, owner_id: UUID, series_id: UUID) -> DerivedSeriesState | None:
        series = await self._session.get(SeriesModel, series_id)
        if series is None or series.owner_id != owner_id:
            return None

        rows = (
            await self._session.execute(
                select(SeriesMembershipModel, WorkModel, ReadingStateModel)
                .join(WorkModel, WorkModel.id == SeriesMembershipModel.work_id)
                .outerjoin(
                    ReadingStateModel,
                    (ReadingStateModel.work_id == WorkModel.id)
                    & (ReadingStateModel.owner_id == owner_id),
                )
                .where(
                    SeriesMembershipModel.series_id == series_id,
                    SeriesMembershipModel.owner_id == owner_id,
                ),
            )
        ).all()

        entries = [
            SeriesEntry(
                work_id=work.id,
                title=work.title,
                index_raw=m.index_raw,
                index_sort=m.index_sort,
                membership_type=MembershipType(m.membership_type),
                reading_status=ReadingStatus(rs.status) if rs is not None else ReadingStatus.UNREAD,
            )
            for m, work, rs in rows
        ]
        entries.sort(
            key=lambda e: (
                e.index_sort is None,
                e.index_sort if e.index_sort is not None else Decimal(0),
                e.title,
            ),
        )

        override_row = await self._session.execute(
            select(SeriesUserStateModel.status_override).where(
                SeriesUserStateModel.owner_id == owner_id,
                SeriesUserStateModel.series_id == series_id,
            ),
        )
        override = override_row.scalar_one_or_none()

        state = DerivedSeriesState(
            series_id=series.id,
            title=series.title,
            entries=entries,
            user_status_override=override,
        )
        observations = list(
            (
                await self._session.execute(
                    select(SourceObservationModel)
                    .where(
                        SourceObservationModel.owner_id == owner_id,
                        SourceObservationModel.series_id == series_id,
                    )
                    .order_by(SourceObservationModel.observed_at.desc()),
                )
            )
            .scalars()
            .all()
        )
        if observations:
            state.last_observed = observations[0].observed_at
            state.observation_evidence = [
                {
                    "source_record_id": str(o.id),
                    "observed_at": o.observed_at.isoformat(),
                    **o.match_evidence,
                }
                for o in observations[:20]
            ]
            seen_source_works: set[str] = set()
            for observation in observations:
                source_work_key = f"{observation.adapter_id}:" + str(
                    observation.raw.get("work_id")
                    or observation.url
                    or f"{observation.title}\0{observation.author_name or ''}"
                )
                if source_work_key in seen_source_works:
                    continue
                seen_source_works.add(source_work_key)
                match = str(observation.match_evidence.get("match") or "none")
                catalog_status = (
                    "present"
                    if observation.work_id is not None
                    else "ambiguous"
                    if match == "ambiguous"
                    else "missing"
                )
                state.source_entries.append(
                    SeriesSourceEntry(
                        observation_id=observation.id,
                        title=observation.title,
                        author_name=observation.author_name,
                        url=(
                            observation.url
                            if observation.url
                            and urlparse(observation.url).scheme in {"http", "https"}
                            else None
                        ),
                        work_id=observation.work_id,
                        observed_at=observation.observed_at,
                        publication_status=(
                            str(observation.raw["status"])
                            if observation.raw.get("status")
                            else None
                        ),
                        catalog_status=catalog_status,
                    )
                )
            owned_ids = {entry.work_id for entry in entries}
            state.has_new_release = any(
                entry.work_id is None or entry.work_id not in owned_ids
                for entry in state.source_entries
            )
            state.waiting_release = (
                state.next_available_unread is None
                and not state.has_new_release
                and state.series_status == "caught_up"
            )
        return state

    async def list_series_overview(self, owner_id: UUID) -> list[DerivedSeriesState]:
        series_ids = (
            (
                await self._session.execute(
                    select(SeriesModel.id).where(SeriesModel.owner_id == owner_id),
                )
            )
            .scalars()
            .all()
        )
        states: list[DerivedSeriesState] = []
        for series_id in series_ids:
            state = await self.for_series(owner_id, series_id)
            if state is not None and state.entries:
                states.append(state)
        states.sort(key=lambda s: s.title)
        return states

    async def set_user_status(
        self,
        owner_id: UUID,
        series_id: UUID,
        status: str,
    ) -> bool:
        if status not in USER_OVERRIDES:
            return False
        series = await self._session.get(SeriesModel, series_id)
        if series is None or series.owner_id != owner_id:
            return False
        from sqlalchemy import delete

        await self._session.execute(
            delete(SeriesUserStateModel).where(
                SeriesUserStateModel.owner_id == owner_id,
                SeriesUserStateModel.series_id == series_id,
            ),
        )
        self._session.add(
            SeriesUserStateModel(
                owner_id=owner_id,
                series_id=series_id,
                status_override=status,
            ),
        )
        await self._session.flush()
        return True
