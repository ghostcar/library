"""Library domain: entities, value objects, invariants, events.

Canonical rule: Work, SourceRecord and Asset are distinct concepts
and are never merged (master prompt 5).
"""

from __future__ import annotations

from portal.modules.library.domain.entities import (
    Asset,
    AssetRelation,
    Author,
    AuthorAlias,
    ReadingState,
    Series,
    SeriesAlias,
    SeriesMembership,
    SourceAuthorRecord,
    SourceRecord,
    Work,
    WorkAuthor,
)
from portal.modules.library.domain.enums import (
    AssetFormat,
    AssetKind,
    AssetRelationType,
    MembershipType,
    ReadingChangeSource,
    ReadingStatus,
    WorkAuthorRole,
)
from portal.modules.library.domain.events import (
    BookAcquired,
    BookFileImported,
    BookMarkedRead,
    DuplicateSuspected,
    NewReleaseDetected,
    NormalizationCompleted,
    NormalizationFailed,
    NormalizationRequested,
    NotificationRequested,
    SeriesProgressChanged,
    SourceRecordObserved,
    WorkMatched,
)
from portal.modules.library.domain.value_objects import SeriesIndex, Sha256

__all__ = [
    "Asset",
    "AssetFormat",
    "AssetKind",
    "AssetRelation",
    "AssetRelationType",
    "Author",
    "AuthorAlias",
    "BookAcquired",
    "BookFileImported",
    "BookMarkedRead",
    "DuplicateSuspected",
    "MembershipType",
    "NewReleaseDetected",
    "NormalizationCompleted",
    "NormalizationFailed",
    "NormalizationRequested",
    "NotificationRequested",
    "ReadingChangeSource",
    "ReadingState",
    "ReadingStatus",
    "Series",
    "SeriesAlias",
    "SeriesIndex",
    "SeriesMembership",
    "SeriesProgressChanged",
    "Sha256",
    "SourceAuthorRecord",
    "SourceRecord",
    "SourceRecordObserved",
    "Work",
    "WorkAuthor",
    "WorkAuthorRole",
    "WorkMatched",
]
