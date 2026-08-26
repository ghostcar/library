"""OPDS device-token authentication (master prompt 10.1).

FBReader authenticates with HTTP Basic: username is informational,
password carries the raw device token (pdt_…). Bearer also accepted.
Tokens are scoped (library:opds:read), revocable, never equal to the
main JWT, and shown only once at creation.
"""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.auth.dependencies import AuthContext
from portal.core.auth.domain import SCOPE_LIBRARY_OPDS_READ, AuthTokenType
from portal.core.auth.repository import AuthTokenRepository, UserRepository
from portal.web.deps import SessionDep

_REALM = 'Basic realm="OPDS", charset="UTF-8"'


def _unauthorized(detail: str = "OPDS authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": _REALM},
    )


def _extract_raw_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise _unauthorized("malformed Basic credentials") from exc
        # username:password — the password is the device token
        _, _, password = decoded.partition(":")
        if not password:
            raise _unauthorized("device token expected as Basic password")
        return password.strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    raise _unauthorized()


async def require_opds_device(
    request: Request,
    session: SessionDep,
) -> AuthContext:
    raw = _extract_raw_token(request)
    tokens = AuthTokenRepository(session)
    token = await tokens.get_active_by_raw(raw, AuthTokenType.DEVICE)
    if token is None:
        raise _unauthorized("unknown or revoked device token")

    if SCOPE_LIBRARY_OPDS_READ not in token.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="token lacks library:opds:read scope",
        )

    users = UserRepository(session)
    user = await users.get(token.user_id)
    if user is None or not user.is_active:
        raise _unauthorized("unknown user")

    await tokens.touch(token.id)
    return AuthContext(user=user, via="bearer", scopes=frozenset(token.scopes))


OpdsDevice = Annotated[AuthContext, Depends(require_opds_device)]


async def optional_opds_device(
    request: Request,
    session: AsyncSession,
) -> AuthContext | None:
    try:
        return await require_opds_device(request, session)
    except HTTPException:
        return None
