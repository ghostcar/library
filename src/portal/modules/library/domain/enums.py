"""Domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class MembershipType(StrEnum):
    MAIN = "main"
    SIDE = "side"
    PREQUEL = "prequel"
    COLLECTION = "collection"
    UNKNOWN = "unknown"


class ReadingStatus(StrEnum):
    UNREAD = "unread"
    READING = "reading"
    READ = "read"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class ReadingChangeSource(StrEnum):
    MANUAL = "manual"
    OPDS = "opds"
    IMPORT = "import"


class WorkAuthorRole(StrEnum):
    AUTHOR = "author"
    TRANSLATOR = "translator"
    EDITOR = "editor"


class AssetFormat(StrEnum):
    FB2 = "fb2"
    EPUB = "epub"


class AssetKind(StrEnum):
    ORIGINAL = "original"
    NORMALIZED = "normalized"
    CONVERTED = "converted"


class AssetRelationType(StrEnum):
    NORMALIZED = "normalized"
    CONVERTED = "converted"
    DUPLICATE_OF = "duplicate_of"
