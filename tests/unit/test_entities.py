"""Unit tests for domain entities and invariants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import (
    AssetFormat,
    AssetKind,
    MembershipType,
    ReadingChangeSource,
    ReadingStatus,
)
from portal.modules.library.domain.value_objects import SeriesIndex, Sha256


class TestWork:
    def test_title_stripped(self) -> None:
        work = de.Work(owner_id=uuid4(), title="  Название  ")
        assert work.title == "Название"

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValueError, match="title"):
            de.Work(owner_id=uuid4(), title="   ")

    def test_title_normalized(self) -> None:
        work = de.Work(owner_id=uuid4(), title="The  Green Mile")
        assert work.title_normalized == "the green mile"

    def test_add_author_idempotent(self) -> None:
        work = de.Work(owner_id=uuid4(), title="T")
        author = uuid4()
        work.add_author(author)
        work.add_author(author)
        assert len(work.authors) == 1
        assert work.authors[0].position == 0


class TestAuthorSeries:
    def test_author_name_required(self) -> None:
        with pytest.raises(ValueError, match="author"):
            de.Author(owner_id=uuid4(), name=" ")

    def test_author_sort_name_defaults_to_last_word(self) -> None:
        author = de.Author(owner_id=uuid4(), name="Андрей Круз")
        assert author.sort_name == "Круз"

    def test_series_title_required(self) -> None:
        with pytest.raises(ValueError, match="series"):
            de.Series(owner_id=uuid4(), title="")


class TestSourceRecord:
    def test_adapter_and_external_id_required(self) -> None:
        with pytest.raises(ValueError, match="adapter_id"):
            de.SourceRecord(owner_id=uuid4(), adapter_id=" ", external_id="123")
        with pytest.raises(ValueError, match="external_id"):
            de.SourceRecord(owner_id=uuid4(), adapter_id="author_today", external_id="")


class TestAsset:
    def test_valid_sha256(self) -> None:
        sha = Sha256("a" * 64)
        assert sha.prefix == "aa"

    def test_invalid_sha256_rejected(self) -> None:
        with pytest.raises(ValueError, match="sha256"):
            Sha256("not-a-hash")

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValueError, match="size"):
            de.Asset(
                owner_id=uuid4(),
                sha256=Sha256("a" * 64),
                format=AssetFormat.FB2,
                kind=AssetKind.ORIGINAL,
                size_bytes=-1,
                storage_path="originals/aa/aaa.fb2",
            )

    def test_asset_relation_self_reference_rejected(self) -> None:
        same = uuid4()
        with pytest.raises(ValueError, match="distinct"):
            de.AssetRelation(
                owner_id=uuid4(),
                asset_id=same,
                related_asset_id=same,
                relation_type=de.AssetRelationType.NORMALIZED,
            )


class TestReadingState:
    def test_initial_state_is_unread(self, owner_id) -> None:
        state = de.ReadingState(owner_id=owner_id, work_id=uuid4())
        assert state.status is ReadingStatus.UNREAD

    def test_legal_transitions(self, owner_id) -> None:
        state = de.ReadingState(owner_id=owner_id, work_id=uuid4())
        state.transition(ReadingStatus.READING)
        state.transition(ReadingStatus.PAUSED)
        state.transition(ReadingStatus.READING)
        state.transition(ReadingStatus.READ)
        assert state.status is ReadingStatus.READ

    def test_illegal_transition_rejected(self, owner_id) -> None:
        state = de.ReadingState(owner_id=owner_id, work_id=uuid4())
        with pytest.raises(ValueError, match="illegal"):
            state.transition(ReadingStatus.READ)

    def test_return_to_queue_from_abandoned(self, owner_id) -> None:
        state = de.ReadingState(owner_id=owner_id, work_id=uuid4())
        state.transition(ReadingStatus.READING)
        state.transition(ReadingStatus.ABANDONED)
        state.transition(ReadingStatus.UNREAD, ReadingChangeSource.MANUAL)
        assert state.status is ReadingStatus.UNREAD

    def test_progress_bounds(self, owner_id) -> None:
        with pytest.raises(ValueError, match="progress"):
            de.ReadingState(owner_id=owner_id, work_id=uuid4(), progress_percent=101)

    def test_can_transition_static(self) -> None:
        assert de.ReadingState.can_transition(ReadingStatus.UNREAD, ReadingStatus.READING)
        assert not de.ReadingState.can_transition(ReadingStatus.UNREAD, ReadingStatus.READ)


class TestSeriesMembership:
    def test_membership_sort_key(self, owner_id) -> None:
        m = de.SeriesMembership(
            owner_id=owner_id,
            series_id=uuid4(),
            work_id=uuid4(),
            index=SeriesIndex.parse("2.5"),
            membership_type=MembershipType.MAIN,
        )
        assert m.index_sort is not None
        assert m.index_sort.as_tuple().exponent == -1 or float(m.index_sort) == 2.5
