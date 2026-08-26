"""Auth domain entities (portal-wide, not library-specific)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Scopes
SCOPE_PORTAL_FULL = "portal:full"
SCOPE_LIBRARY_OPDS_READ = "library:opds:read"


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuthTokenType(StrEnum):
    REFRESH = "refresh"
    DEVICE = "device"
    API = "api"


def validate_email(email: str) -> str:
    cleaned = email.strip().lower()
    if not _EMAIL_RE.match(cleaned):
        msg = f"invalid email: {email!r}"
        raise ValueError(msg)
    return cleaned


@dataclass(slots=True)
class User:
    email: str
    password_hash: str
    display_name: str | None = None
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)

    @property
    def owner_id(self) -> UUID:
        """Owner scope for all personal data of this user."""
        return self.id


@dataclass(slots=True)
class AuthToken:
    """Refresh / device / api token. Only the hash is persisted."""

    user_id: UUID
    token_type: AuthTokenType
    token_hash: str
    scopes: list[str]
    name: str | None = None
    expires_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= utcnow():
            return False
        return True

    def revoke(self) -> None:
        self.revoked_at = utcnow()

    def touch(self) -> None:
        self.last_used_at = utcnow()
