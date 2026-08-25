"""Portal-level authentication core.

This package owns users, credentials and tokens for the whole
macroportal. Domain modules (library now, others later) consume it via
FastAPI dependencies and the TokenVerifier interface — they never
implement their own login (master prompt 12, ADR-0006).
"""

from __future__ import annotations

from portal.core.auth.domain import AuthToken, AuthTokenType, User
from portal.core.auth.jwt_service import TokenPrincipal, TokenService
from portal.core.auth.passwords import hash_password, verify_password

__all__ = [
    "AuthToken",
    "AuthTokenType",
    "TokenPrincipal",
    "TokenService",
    "User",
    "hash_password",
    "verify_password",
]
