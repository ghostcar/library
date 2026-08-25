"""Import domain: batches, items, duplicate candidates (master prompt 5.1, 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from portal.modules.library.domain.value_objects import Sha256


def utcnow() -> datetime:
    return datetime.now(UTC)


class ImportSource(StrEnum):
    UPLOAD = "upload"
    LOCAL_DIR = "local_dir"
    INBOX = "inbox"
    URL = "url"


class BatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ItemStatus(StrEnum):
    PENDING = "pending"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    STORED_UNMATCHED = "stored_unmatched"
    MATCHED = "matched"
    FAILED = "failed"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED_DUPLICATE = "confirmed_duplicate"
    DISTINCT = "distinct"


class DuplicateReason(StrEnum):
    EXACT_CONTENT = "exact_content"
    SAME_WORK_FORMAT = "same_work_format"


@dataclass(slots=True)
class ImportBatch:
    owner_id: UUID
    source: ImportSource
    status: BatchStatus = BatchStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None

    def mark_running(self) -> None:
        self.status = BatchStatus.RUNNING

    def finish(self, *, failed_items: int) -> None:
        if failed_items == 0:
            self.status = BatchStatus.COMPLETED
        elif self.status is BatchStatus.RUNNING:
            self.status = BatchStatus.PARTIAL
        self.completed_at = utcnow()


@dataclass(slots=True)
class ImportItem:
    batch_id: UUID
    owner_id: UUID
    filename: str
    status: ItemStatus = ItemStatus.PENDING
    size_bytes: int | None = None
    sha256: Sha256 | None = None
    detected_format: str | None = None
    asset_id: UUID | None = None
    work_id: UUID | None = None
    match_evidence: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)

    def reject(self, reason: str) -> None:
        self.status = ItemStatus.REJECTED
        self.error = reason

    def fail(self, reason: str) -> None:
        self.status = ItemStatus.FAILED
        self.error = reason


@dataclass(slots=True)
class DuplicateCandidate:
    owner_id: UUID
    asset_id: UUID
    suspected_of_asset_id: UUID
    reason: DuplicateReason
    status: CandidateStatus = CandidateStatus.PENDING
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
