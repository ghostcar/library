"""Domain events (master prompt 4.2).

Events are facts. Handlers must be idempotent; delivery via
transactional outbox arrives in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4, init=False)
    occurred_at: datetime = field(default_factory=_now, init=False)


@dataclass(frozen=True, slots=True)
class BookFileImported(DomainEvent):
    owner_id: UUID
    asset_id: UUID
    import_batch_id: UUID | None = None
    filename: str | None = None


@dataclass(frozen=True, slots=True)
class WorkMatched(DomainEvent):
    owner_id: UUID
    work_id: UUID
    asset_id: UUID
    confidence: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DuplicateSuspected(DomainEvent):
    owner_id: UUID
    asset_id: UUID
    suspected_of_asset_id: UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizationRequested(DomainEvent):
    owner_id: UUID
    asset_id: UUID
    profile: str


@dataclass(frozen=True, slots=True)
class NormalizationCompleted(DomainEvent):
    owner_id: UUID
    run_id: UUID
    input_asset_id: UUID
    output_asset_id: UUID


@dataclass(frozen=True, slots=True)
class NormalizationFailed(DomainEvent):
    owner_id: UUID
    run_id: UUID
    input_asset_id: UUID
    reason: str


@dataclass(frozen=True, slots=True)
class SourceRecordObserved(DomainEvent):
    owner_id: UUID
    source_record_id: UUID
    adapter_id: str
    external_id: str


@dataclass(frozen=True, slots=True)
class NewReleaseDetected(DomainEvent):
    owner_id: UUID
    work_id: UUID | None
    series_id: UUID | None
    source_record_id: UUID


@dataclass(frozen=True, slots=True)
class BookAcquired(DomainEvent):
    owner_id: UUID
    work_id: UUID | None
    asset_id: UUID
    acquisition_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class BookMarkedRead(DomainEvent):
    owner_id: UUID
    work_id: UUID
    reading_state_id: UUID


@dataclass(frozen=True, slots=True)
class SeriesProgressChanged(DomainEvent):
    owner_id: UUID
    series_id: UUID
    work_id: UUID


@dataclass(frozen=True, slots=True)
class NotificationRequested(DomainEvent):
    owner_id: UUID
    channel: str
    payload: dict[str, Any] = field(default_factory=dict)
