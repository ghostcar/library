"""Unit tests: derived series state (ordering, gaps, next-up, status)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from portal.modules.library.application.series_state_service import (
    DerivedSeriesState,
    SeriesEntry,
)
from portal.modules.library.domain.enums import MembershipType, ReadingStatus

OWNER = uuid4()


def entry(
    index: str | None,
    status: ReadingStatus = ReadingStatus.UNREAD,
    title: str | None = None,
) -> SeriesEntry:
    from portal.modules.library.domain.value_objects import SeriesIndex

    parsed = SeriesIndex.parse(index) if index is not None else None
    return SeriesEntry(
        work_id=uuid4(),
        title=title or f"Книга {index or '?'}",
        index_raw=index or "",
        index_sort=parsed.sort_key if parsed else None,
        membership_type=MembershipType.MAIN,
        reading_status=status,
    )


def state(*entries: SeriesEntry, override: str | None = None) -> DerivedSeriesState:
    entries = sorted(
        entries,
        key=lambda e: (
            e.index_sort is None,
            e.index_sort if e.index_sort is not None else Decimal(0),
            e.title,
        ),
    )
    return DerivedSeriesState(
        series_id=uuid4(),
        title="Цикл",
        entries=list(entries),
        user_status_override=override,
    )


class TestOrdering:
    def test_sorted_by_index_with_unknown_last(self) -> None:
        s = state(entry("3"), entry("0.5"), entry("unknown"), entry("1"))
        assert [e.index_raw for e in s.entries] == ["0.5", "1", "3", "unknown"]

    def test_ranges_sort_by_lower_bound(self) -> None:
        s = state(entry("2-3"), entry("1"), entry("10"))
        assert [e.index_raw for e in s.entries] == ["1", "2-3", "10"]


class TestNextAvailable:
    def test_first_unread_after_last_read(self) -> None:
        s = state(
            entry("1", ReadingStatus.READ),
            entry("2", ReadingStatus.UNREAD),
            entry("3", ReadingStatus.UNREAD),
        )
        assert s.next_available_unread is not None
        assert s.next_available_unread.index_raw == "2"

    def test_nothing_read_gives_first_book(self) -> None:
        s = state(entry("2"), entry("1"))
        assert s.next_available_unread is not None
        assert s.next_available_unread.index_raw == "1"

    def test_all_read_gives_none(self) -> None:
        s = state(entry("1", ReadingStatus.READ), entry("2", ReadingStatus.READ))
        assert s.next_available_unread is None

    def test_abandoned_skipped_for_next(self) -> None:
        s = state(
            entry("1", ReadingStatus.READ),
            entry("2", ReadingStatus.ABANDONED),
            entry("3", ReadingStatus.UNREAD),
        )
        assert s.next_available_unread is not None
        assert s.next_available_unread.index_raw == "3"


class TestMissingIndices:
    def test_gap_detected(self) -> None:
        s = state(entry("1"), entry("2"), entry("5"))
        assert s.missing_indices == ["3", "4"]

    def test_no_gap(self) -> None:
        s = state(entry("1"), entry("2"), entry("3"))
        assert s.missing_indices == []

    def test_fractional_indices_ignored(self) -> None:
        s = state(entry("1"), entry("1.5"), entry("3"))
        # 1.5 is not integral: gap between 1 and 3 is 2 -> [2]
        assert s.missing_indices == ["2"]

    def test_unknown_index_not_in_gaps(self) -> None:
        s = state(entry("1"), entry("unknown"), entry("2"))
        assert s.missing_indices == []


class TestSeriesStatus:
    def test_planned_when_nothing_read(self) -> None:
        assert state(entry("1"), entry("2")).series_status == "planned"

    def test_in_progress_when_partially_read(self) -> None:
        s = state(entry("1", ReadingStatus.READ), entry("2", ReadingStatus.UNREAD))
        assert s.series_status == "in_progress"

    def test_caught_up_not_completed_when_all_read(self) -> None:
        # master prompt 5.3: max index read != series completed
        s = state(entry("1", ReadingStatus.READ), entry("2", ReadingStatus.READ))
        assert s.series_status == "caught_up"

    def test_user_override_wins(self) -> None:
        s = state(
            entry("1", ReadingStatus.READ),
            entry("2", ReadingStatus.UNREAD),
            override="paused",
        )
        assert s.series_status == "paused"

    def test_completed_only_by_explicit_override(self) -> None:
        s = state(
            entry("1", ReadingStatus.READ),
            entry("2", ReadingStatus.READ),
            override="completed",
        )
        assert s.series_status == "completed"
        assert s.completion_confidence == "high"

    def test_abandoned_when_all_abandoned(self) -> None:
        s = state(entry("1", ReadingStatus.ABANDONED), entry("2", ReadingStatus.ABANDONED))
        assert s.series_status == "abandoned"

    def test_confidence_low_without_confirmation(self) -> None:
        s = state(entry("1", ReadingStatus.READ))
        assert s.completion_confidence == "low"


class TestLastRead:
    def test_last_read_is_highest_read(self) -> None:
        s = state(
            entry("1", ReadingStatus.READ),
            entry("2", ReadingStatus.READ),
            entry("3", ReadingStatus.UNREAD),
        )
        assert s.last_read is not None
        assert s.last_read.index_raw == "2"

    def test_last_owned_is_highest(self) -> None:
        s = state(entry("1", ReadingStatus.READ), entry("5"))
        assert s.last_owned is not None
        assert s.last_owned.index_raw == "5"
