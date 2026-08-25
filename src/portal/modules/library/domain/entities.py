"""Domain entities with invariants. Pure Python, no ORM imports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from portal.modules.library.domain.enums import (
    AssetFormat,
    AssetKind,
    AssetRelationType,
    MembershipType,
    ReadingChangeSource,
    ReadingStatus,
    WorkAuthorRole,
)
from portal.modules.library.domain.value_objects import SeriesIndex, Sha256

_TITLE_RE = re.compile(r"\s+")

_ALLOWED_READING_TRANSITIONS: dict[ReadingStatus, frozenset[ReadingStatus]] = {
    ReadingStatus.UNREAD: frozenset({ReadingStatus.READING}),
    ReadingStatus.READING: frozenset(
        {ReadingStatus.READ, ReadingStatus.PAUSED, ReadingStatus.ABANDONED},
    ),
    ReadingStatus.PAUSED: frozenset({ReadingStatus.READING, ReadingStatus.ABANDONED}),
    ReadingStatus.ABANDONED: frozenset({ReadingStatus.UNREAD}),
    ReadingStatus.READ: frozenset({ReadingStatus.UNREAD}),
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_title(title: str) -> str:
    """Casefold + collapse whitespace; used for matching, never for display."""
    return _TITLE_RE.sub(" ", title).strip().casefold()


@dataclass(slots=True)
class Author:
    owner_id: UUID
    name: str
    sort_name: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            msg = "author name must not be empty"
            raise ValueError(msg)
        self.name = self.name.strip()
        if self.sort_name is None:
            parts = self.name.split()
            self.sort_name = parts[-1] if parts else self.name


@dataclass(slots=True)
class AuthorAlias:
    owner_id: UUID
    author_id: UUID
    alias: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.alias or not self.alias.strip():
            msg = "author alias must not be empty"
            raise ValueError(msg)
        self.alias = self.alias.strip()


@dataclass(slots=True)
class WorkAuthor:
    author_id: UUID
    role: WorkAuthorRole = WorkAuthorRole.AUTHOR
    position: int = 0


@dataclass(slots=True)
class Work:
    owner_id: UUID
    title: str
    language: str | None = None
    description: str | None = None
    id: UUID = field(default_factory=uuid4)
    authors: list[WorkAuthor] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            msg = "work title must not be empty"
            raise ValueError(msg)
        self.title = self.title.strip()

    @property
    def title_normalized(self) -> str:
        return normalize_title(self.title)

    def add_author(self, author_id: UUID, role: WorkAuthorRole = WorkAuthorRole.AUTHOR) -> None:
        if any(wa.author_id == author_id and wa.role == role for wa in self.authors):
            return
        self.authors.append(WorkAuthor(author_id=author_id, role=role, position=len(self.authors)))
        self.updated_at = _utcnow()


@dataclass(slots=True)
class Series:
    owner_id: UUID
    title: str
    description: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            msg = "series title must not be empty"
            raise ValueError(msg)
        self.title = self.title.strip()

    @property
    def title_normalized(self) -> str:
        return normalize_title(self.title)


@dataclass(slots=True)
class SeriesAlias:
    owner_id: UUID
    series_id: UUID
    alias: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.alias or not self.alias.strip():
            msg = "series alias must not be empty"
            raise ValueError(msg)
        self.alias = self.alias.strip()


@dataclass(slots=True)
class SeriesMembership:
    owner_id: UUID
    series_id: UUID
    work_id: UUID
    index: SeriesIndex
    membership_type: MembershipType = MembershipType.UNKNOWN
    id: UUID = field(default_factory=uuid4)

    @property
    def index_sort(self) -> Decimal | None:
        return self.index.sort_key


@dataclass(slots=True)
class SourceRecord:
    """Observation of a work page on an external source. Never canonical truth."""

    owner_id: UUID
    adapter_id: str
    external_id: str
    work_id: UUID | None = None
    url: str | None = None
    raw_metadata: dict[str, object] = field(default_factory=dict)
    parser_version: str | None = None
    last_observed_at: datetime = field(default_factory=_utcnow)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.adapter_id or not self.adapter_id.strip():
            msg = "source record adapter_id must not be empty"
            raise ValueError(msg)
        if not self.external_id or not self.external_id.strip():
            msg = "source record external_id must not be empty"
            raise ValueError(msg)


@dataclass(slots=True)
class SourceAuthorRecord:
    owner_id: UUID
    adapter_id: str
    external_id: str
    author_id: UUID | None = None
    url: str | None = None
    raw_metadata: dict[str, object] = field(default_factory=dict)
    last_observed_at: datetime = field(default_factory=_utcnow)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)


@dataclass(slots=True)
class Asset:
    """Physical file addressed by content SHA-256. Originals are immutable."""

    owner_id: UUID
    sha256: Sha256
    format: AssetFormat
    kind: AssetKind
    size_bytes: int
    storage_path: str
    original_filename: str | None = None
    work_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            msg = "asset size_bytes must not be negative"
            raise ValueError(msg)
        if not self.storage_path or not self.storage_path.strip():
            msg = "asset storage_path must not be empty"
            raise ValueError(msg)


@dataclass(slots=True)
class AssetRelation:
    owner_id: UUID
    asset_id: UUID
    related_asset_id: UUID
    relation_type: AssetRelationType
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.asset_id == self.related_asset_id:
            msg = "asset relation must reference two distinct assets"
            raise ValueError(msg)


@dataclass(slots=True)
class ReadingState:
    owner_id: UUID
    work_id: UUID
    status: ReadingStatus = ReadingStatus.UNREAD
    progress_percent: int | None = None
    change_source: ReadingChangeSource = ReadingChangeSource.MANUAL
    id: UUID = field(default_factory=uuid4)
    changed_at: datetime = field(default_factory=_utcnow)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.progress_percent is not None and not 0 <= self.progress_percent <= 100:
            msg = "progress_percent must be within 0..100"
            raise ValueError(msg)

    def transition(
        self,
        new_status: ReadingStatus,
        source: ReadingChangeSource = ReadingChangeSource.MANUAL,
    ) -> None:
        allowed = _ALLOWED_READING_TRANSITIONS[self.status]
        if new_status not in allowed:
            msg = f"illegal reading state transition {self.status} -> {new_status}"
            raise ValueError(msg)
        self.status = new_status
        self.change_source = source
        self.changed_at = _utcnow()

    @staticmethod
    def can_transition(current: ReadingStatus, new: ReadingStatus) -> bool:
        return new in _ALLOWED_READING_TRANSITIONS[current]
