"""Normalization domain: profiles, runs, actions, fingerprints (master prompt 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from portal.modules.library.domain.value_objects import Sha256

NORMALIZER_VERSION = "1.0.0"


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProfileName(StrEnum):
    METADATA_ONLY = "metadata_only"
    SAFE = "safe"
    PROSE_COMPACT = "prose_compact"
    READER_NEUTRAL = "reader_neutral"
    MANUAL_CLEANUP = "manual_cleanup"


@dataclass(frozen=True, slots=True)
class Profile:
    """Normalization profile (master prompt 7.3). Text modification is always forbidden."""

    name: ProfileName
    version: int
    rebuild_toc_when_unambiguous: bool
    images_cover_only: bool
    keep_visible_captions: bool
    optimize_cover: bool
    cover_max_dimension: int
    strict_text_fingerprint: bool


PROFILES: dict[ProfileName, Profile] = {
    ProfileName.METADATA_ONLY: Profile(
        name=ProfileName.METADATA_ONLY,
        version=1,
        rebuild_toc_when_unambiguous=False,
        images_cover_only=False,
        keep_visible_captions=True,
        optimize_cover=False,
        cover_max_dimension=0,
        strict_text_fingerprint=True,
    ),
    ProfileName.SAFE: Profile(
        name=ProfileName.SAFE,
        version=1,
        rebuild_toc_when_unambiguous=True,
        images_cover_only=False,
        keep_visible_captions=True,
        optimize_cover=False,
        cover_max_dimension=0,
        strict_text_fingerprint=True,
    ),
    ProfileName.PROSE_COMPACT: Profile(
        name=ProfileName.PROSE_COMPACT,
        version=1,
        rebuild_toc_when_unambiguous=True,
        images_cover_only=True,
        keep_visible_captions=True,
        optimize_cover=True,
        cover_max_dimension=1600,
        strict_text_fingerprint=True,
    ),
    ProfileName.READER_NEUTRAL: Profile(
        name=ProfileName.READER_NEUTRAL,
        version=1,
        rebuild_toc_when_unambiguous=True,
        images_cover_only=False,
        keep_visible_captions=True,
        optimize_cover=False,
        cover_max_dimension=0,
        strict_text_fingerprint=True,
    ),
    ProfileName.MANUAL_CLEANUP: Profile(
        name=ProfileName.MANUAL_CLEANUP,
        version=1,
        rebuild_toc_when_unambiguous=False,
        images_cover_only=False,
        keep_visible_captions=True,
        optimize_cover=False,
        cover_max_dimension=0,
        strict_text_fingerprint=True,
    ),
}

DEFAULT_PROFILE = ProfileName.PROSE_COMPACT


class RunState(StrEnum):
    RECEIVED = "received"
    QUARANTINED = "quarantined"
    FORMAT_DETECTED = "format_detected"
    ANALYZED = "analyzed"
    METADATA_PROPOSED = "metadata_proposed"
    NORMALIZATION_PLANNED = "normalization_planned"
    TRANSFORMED = "transformed"
    VALIDATED = "validated"
    DERIVATIVE_READY = "derivative_ready"
    PREFERRED = "preferred"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ActionKind(StrEnum):
    PARSE = "parse"
    REMOVE_BODY_IMAGES = "remove_body_images"
    REMOVE_UNUSED_BINARIES = "remove_unused_binaries"
    REMOVE_EMPTY_WRAPPERS = "remove_empty_wrappers"
    NORMALIZE_METADATA = "normalize_metadata"
    REBUILD_TOC = "rebuild_toc"
    OPTIMIZE_COVER = "optimize_cover"
    REPACK_ZIP = "repack_zip"
    REMOVE_ORPHANED_RESOURCES = "remove_orphaned_resources"
    VERIFY_TEXT_INVARIANT = "verify_text_invariant"
    VALIDATE = "validate"


@dataclass(slots=True)
class RunAction:
    kind: ActionKind
    detail: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "detail": self.detail, "at": self.at.isoformat()}


@dataclass(slots=True)
class TextFingerprints:
    """Content fingerprints before/after transformation (master prompt 7.1)."""

    visible_text: str
    structure: str
    images: str
    chapters: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NormalizationRun:
    owner_id: UUID
    input_asset_id: UUID
    profile: ProfileName
    profile_version: int
    normalizer_version: str
    state: RunState = RunState.RECEIVED
    derivative_asset_id: UUID | None = None
    needs_review: bool = False
    review_reason: str | None = None
    actions: list[RunAction] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    id: UUID = field(default_factory=uuid4)
    input_sha256: Sha256 | None = None
    output_sha256: Sha256 | None = None
    created_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None

    def transition(self, state: RunState, action: RunAction | None = None) -> None:
        self.state = state
        if action is not None:
            self.actions.append(action)

    def finish_review(self, reason: str) -> None:
        self.state = RunState.NEEDS_REVIEW
        self.needs_review = True
        self.review_reason = reason
        self.completed_at = utcnow()

    def fail(self, reason: str) -> None:
        self.state = RunState.FAILED
        self.error = reason
        self.completed_at = utcnow()
