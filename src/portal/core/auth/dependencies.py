"""FastAPI auth dependencies: current user (bearer or cookie), scopes, CSRF."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, Response, status

from portal.core.audit.service import AuditService
from portal.core.auth.domain import SCOPE_PORTAL_FULL, User
from portal.core.auth.jwt_service import TokenService
from portal.core.auth.repository import UserRepository
from portal.core.auth.service import AuthService
from portal.core.config.config import Settings
from portal.web.deps import SessionDep

if TYPE_CHECKING:
    from portal.core.auth.rate_limit import RateLimiter

ACCESS_COOKIE = "library_access"
REFRESH_COOKIE = "library_refresh"
CSRF_COOKIE = "library_csrf"
CSRF_HEADER = "x-csrf-token"

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(slots=True)
class AuthContext:
    user: User
    via: Literal["bearer", "cookie"]
    scopes: frozenset[str]


def _container(request: Request) -> dict[str, Any]:
    return cast("dict[str, Any]", request.app.state.container)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_settings_dep(request: Request) -> Settings:
    return cast("Settings", _container(request)["settings"])


def get_token_service(request: Request) -> TokenService:
    return cast("TokenService", _container(request)["token_service"])


def get_auth_service(request: Request) -> AuthService:
    return cast("AuthService", _container(request)["auth_service"])


def get_audit_service(request: Request) -> AuditService:
    return cast("AuditService", _container(request)["audit_service"])


def get_rate_limiters(request: Request) -> dict[str, RateLimiter]:
    return cast("dict[str, RateLimiter]", _container(request)["rate_limiters"])


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthContext:
    """Resolve the caller from Authorization: Bearer or the access cookie."""
    auth_header = request.headers.get("authorization", "")
    token_value: str | None = None
    via: Literal["bearer", "cookie"] = "bearer"

    if auth_header.lower().startswith("bearer "):
        token_value = auth_header[7:].strip()
    elif (cookie := request.cookies.get(ACCESS_COOKIE)) is not None:
        token_value = cookie
        via = "cookie"

    if token_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_service = TokenService(settings)
    try:
        principal = token_service.verify(token_value)
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    users = UserRepository(session)
    user = await users.get(uuid.UUID(principal.user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    return AuthContext(user=user, via=via, scopes=principal.scopes)


CurrentUser = Annotated[AuthContext, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthContext | None:
    try:
        return await get_current_user(request, session, settings)
    except HTTPException:
        return None


OptionalUser = Annotated[AuthContext | None, Depends(get_optional_user)]


async def require_csrf(request: Request, current: CurrentUser) -> AuthContext:
    """CSRF double-submit check for cookie-authenticated unsafe requests."""
    if current.via == "bearer" or request.method not in _UNSAFE_METHODS:
        return current
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if cookie_token is None or header_token is None or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF check failed")
    return current


CSRFProtected = Annotated[AuthContext, Depends(require_csrf)]


def require_scope(scope: str) -> Any:
    """Dependency factory: require a concrete scope on the caller."""

    async def _dependency(current: CurrentUser) -> AuthContext:
        if SCOPE_PORTAL_FULL in current.scopes or scope in current.scopes:
            return current
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    return _dependency


def set_auth_cookies(
    response: Response,
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str,
    refresh_expires_at: object,
) -> None:

    secure = settings.cookie_secure or settings.is_production
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=_seconds_until(refresh_expires_at, settings.refresh_token_ttl_days * 86400),
        path="/auth",
    )


def _seconds_until(expires_at: object, fallback: int) -> int:
    if isinstance(expires_at, datetime):
        delta = expires_at - datetime.now(UTC)
        return max(0, int(delta.total_seconds()))
    return fallback


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/auth")


def issue_csrf_cookie(request: Request, response: Response) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        httponly=False,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        max_age=3600,
        path="/",
    )


__all__ = [
    "ACCESS_COOKIE",
    "CSRF_COOKIE",
    "CSRF_HEADER",
    "REFRESH_COOKIE",
    "AuthServiceDep",
    "CSRFProtected",
    "CurrentUser",
    "OptionalUser",
    "SessionDep",
    "clear_auth_cookies",
    "get_current_user",
    "get_token_service",
    "issue_csrf_cookie",
    "require_scope",
    "set_auth_cookies",
]
