"""JWT issuance and verification (macroportal-wide).

Design for multi-service future (ADR-0006):
- Consumers depend on TokenService.verify() / TokenPrincipal only.
- HS256 with shared secret today; switching to RS256/JWKS later changes
  only this module, not its consumers.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt as pyjwt

from portal.core.auth.domain import SCOPE_PORTAL_FULL, AuthTokenType
from portal.core.config.config import Settings


@dataclass(frozen=True, slots=True)
class TokenPrincipal:
    """Authenticated identity extracted from an access token."""

    user_id: str
    jti: str
    scopes: frozenset[str]
    token_type: AuthTokenType
    expires_at: datetime

    def has_scope(self, scope: str) -> bool:
        return SCOPE_PORTAL_FULL in self.scopes or scope in self.scopes


def hash_token(raw: str) -> str:
    """SHA-256 of the raw token — the only form persisted in DB."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


def generate_raw_token(prefix: str) -> str:
    """Opaque token for refresh/device flows (never a JWT)."""
    return f"{prefix}_{secrets.token_urlsafe(48)}"


class TokenService:
    """Issues and verifies JWT access tokens."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret or ""
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)

    def issue_access_token(
        self,
        user_id: str,
        scopes: list[str],
        *,
        token_type: AuthTokenType = AuthTokenType.API,
    ) -> tuple[str, datetime]:
        now = datetime.now(UTC)
        expires_at = now + self._access_ttl
        payload: dict[str, Any] = {
            "sub": user_id,
            "jti": secrets.token_urlsafe(16),
            "scopes": scopes,
            "typ": token_type.value,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = pyjwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def verify(self, token: str) -> TokenPrincipal:
        """Raises jwt.InvalidTokenError (Expired/Invalid) on failure."""
        payload: dict[str, Any] = pyjwt.decode(
            token,
            self._secret,
            algorithms=[self._algorithm],
            options={"require": ["sub", "exp", "jti", "typ"]},
        )
        return TokenPrincipal(
            user_id=payload["sub"],
            jti=payload["jti"],
            scopes=frozenset(payload.get("scopes", [])),
            token_type=AuthTokenType(payload["typ"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
