"""Auth API: register, login, refresh, logout, me, device tokens."""

from __future__ import annotations

import uuid as uuid_module
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from portal.core.auth.dependencies import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    AuthServiceDep,
    CSRFProtected,
    CurrentUser,
    OptionalUser,
    SettingsDep,
    clear_auth_cookies,
    issue_csrf_cookie,
    set_auth_cookies,
)
from portal.core.auth.rate_limit import RateLimiter
from portal.core.auth.service import (
    InvalidCredentialsError,
    RegistrationClosedError,
    TokenRevokedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - standard OAuth2 value, not a secret
    expires_in: int
    user: UserInfo


class UserInfo(BaseModel):
    id: str
    email: str
    display_name: str | None
    is_superuser: bool

    @classmethod
    def of(cls, user: object) -> UserInfo:
        return cls(
            id=str(user.id),  # type: ignore[attr-defined]
            email=user.email,  # type: ignore[attr-defined]
            display_name=user.display_name,  # type: ignore[attr-defined]
            is_superuser=user.is_superuser,  # type: ignore[attr-defined]
        )


class DeviceTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(default_factory=lambda: ["library:opds:read"])


class DeviceTokenResponse(BaseModel):
    id: str
    name: str | None
    scopes: list[str]
    token: str
    expires_at: str | None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _check_rate_limit(request: Request, limiter_name: str, key: str) -> None:
    limiters: dict[str, RateLimiter] = request.app.state.container["rate_limiters"]
    limiter = limiters[limiter_name]
    if not limiter.check(f"{limiter_name}:{key}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, try later",
        )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    auth: AuthServiceDep,
    settings: SettingsDep,
    actor: OptionalUser,
) -> TokenResponse:
    _check_rate_limit(request, "register", _ip(request) or "unknown")
    actor_is_superuser = actor is not None and actor.user.is_superuser

    try:
        user = await auth.register(
            payload.email,
            payload.password,
            actor_ip=_ip(request),
            actor_is_superuser=actor_is_superuser,
        )
    except RegistrationClosedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = await auth.login(payload.email, payload.password, actor_ip=_ip(request))
    set_auth_cookies(
        response,
        settings,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=result.refresh_expires_at,
    )
    issue_csrf_cookie(request, response)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserInfo.of(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    _check_rate_limit(request, "login", f"{_ip(request) or 'unknown'}:{form.username}")
    try:
        result = await auth.login(form.username, form.password, actor_ip=_ip(request))
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    set_auth_cookies(
        response,
        settings,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=result.refresh_expires_at,
    )
    issue_csrf_cookie(request, response)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserInfo.of(result.user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        result = await auth.refresh(raw, actor_ip=_ip(request))
    except TokenRevokedError as exc:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is not active",
        ) from exc
    set_auth_cookies(
        response,
        settings,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        refresh_expires_at=result.refresh_expires_at,
    )
    issue_csrf_cookie(request, response)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserInfo.of(result.user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    current: CSRFProtected,
) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is not None:
        await auth.logout(raw, actor_ip=_ip(request))
    clear_auth_cookies(response)
    response.delete_cookie(CSRF_COOKIE, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserInfo)
async def me(current: CurrentUser) -> UserInfo:
    return UserInfo.of(current.user)


@router.get("/tokens", response_model=list[dict[str, object]])
async def list_device_tokens(
    current: CurrentUser,
    auth: AuthServiceDep,
) -> list[dict[str, object]]:
    tokens = await auth.list_device_tokens(current.user)
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "scopes": t.scopes,
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "revoked": t.revoked_at is not None,
        }
        for t in tokens
    ]


@router.post("/tokens", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
async def create_device_token(
    payload: DeviceTokenRequest,
    current: CSRFProtected,
    auth: AuthServiceDep,
) -> DeviceTokenResponse:
    created = await auth.create_device_token(
        current.user,
        payload.name,
        payload.scopes,
        actor_ip=None,
    )
    return DeviceTokenResponse(
        id=str(created.token.id),
        name=created.token.name,
        scopes=created.token.scopes,
        token=created.raw_token,
        expires_at=created.token.expires_at.isoformat() if created.token.expires_at else None,
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device_token(
    token_id: str,
    current: CSRFProtected,
    auth: AuthServiceDep,
) -> Response:
    revoked = await auth.revoke_device_token(current.user, uuid_from(token_id))
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def uuid_from(value: str) -> uuid_module.UUID:
    try:
        return uuid_module.UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token id",
        ) from exc
