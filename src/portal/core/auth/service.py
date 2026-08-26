"""Authentication use cases: bootstrap registration, login, refresh rotation, logout.

Security properties (master prompt 12):
- refresh/device tokens are persisted only as SHA-256 hashes;
- refresh rotation: used refresh token is revoked, a new one is issued;
- registration is open only while the portal has zero users (bootstrap);
  afterwards account creation requires an authenticated superuser;
- every sensitive action is written to the audit log;
- each operation is one transaction (application service owns boundaries).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.audit.service import AuditService
from portal.core.auth.domain import (
    SCOPE_PORTAL_FULL,
    AuthToken,
    AuthTokenType,
    User,
    utcnow,
)
from portal.core.auth.jwt_service import TokenPrincipal, TokenService, generate_raw_token
from portal.core.auth.passwords import hash_password, verify_password
from portal.core.auth.repository import AuditRepository, AuthTokenRepository, UserRepository
from portal.core.config.config import Settings


class AuthError(Exception):
    """Generic authentication failure (do not leak details to clients)."""


class RegistrationClosedError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class TokenRevokedError(AuthError):
    pass


@dataclass(slots=True)
class LoginResult:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(slots=True)
class DeviceTokenCreated:
    token: AuthToken
    raw_token: str


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        audit: AuditService,
        token_service: TokenService,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._audit_template = audit
        self._jwt = token_service
        self._settings = settings

    @asynccontextmanager
    async def _transaction(
        self,
    ) -> AsyncIterator[tuple[UserRepository, AuthTokenRepository, AuditService]]:
        async with self._session_factory() as session:
            async with session.begin():
                users = UserRepository(session)
                tokens = AuthTokenRepository(session)
                audit = AuditService(AuditRepository(session))
                yield users, tokens, audit

    async def _audit_alone(
        self,
        action: str,
        *,
        user_id: UUID | None = None,
        actor_ip: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Write an audit record in its own transaction.

        Failure paths raise exceptions that roll back the main transaction;
        security-relevant audit records must survive that rollback.
        """
        async with self._session_factory() as session:
            async with session.begin():
                await AuditService(AuditRepository(session)).log(
                    action,
                    user_id=user_id,
                    actor_ip=actor_ip,
                    details=details,
                )

    def _refresh_ttl(self) -> timedelta:
        return timedelta(days=self._settings.refresh_token_ttl_days)

    # --- registration -------------------------------------------------

    async def register(
        self,
        email: str,
        password: str,
        *,
        actor_ip: str | None = None,
        actor_is_superuser: bool = False,
    ) -> User:
        try:
            return await self._register_tx(
                email,
                password,
                actor_ip=actor_ip,
                actor_is_superuser=actor_is_superuser,
            )
        except RegistrationClosedError:
            await self._audit_alone(
                "register_denied",
                actor_ip=actor_ip,
                details={"email": email},
            )
            raise
        except InvalidCredentialsError as exc:
            action = (
                "register_rejected_weak_password"
                if "12 characters" in str(exc)
                else "register_duplicate_email"
            )
            await self._audit_alone(action, actor_ip=actor_ip, details={"email": email})
            raise

    async def _register_tx(
        self,
        email: str,
        password: str,
        *,
        actor_ip: str | None,
        actor_is_superuser: bool,
    ) -> User:
        async with self._transaction() as (users, _tokens, audit):
            existing_count = await users.count()
            if existing_count > 0 and not actor_is_superuser:
                msg = "registration is closed"
                raise RegistrationClosedError(msg)

            if len(password) < 12:
                msg = "password must be at least 12 characters"
                raise InvalidCredentialsError(msg)

            if await users.get_by_email(email) is not None:
                msg = "email already registered"
                raise InvalidCredentialsError(msg)

            bootstrap = existing_count == 0
            user = User(
                email=email,
                password_hash=hash_password(password),
                display_name=email.split("@", 1)[0],
                is_superuser=bootstrap,
            )
            await users.add(user)
            await audit.log(
                "register",
                user_id=user.id,
                actor_ip=actor_ip,
                details={"bootstrap": bootstrap},
            )
            return user

    # --- login --------------------------------------------------------

    async def login(self, email: str, password: str, *, actor_ip: str | None = None) -> LoginResult:
        try:
            return await self._login_tx(email, password, actor_ip=actor_ip)
        except InvalidCredentialsError:
            await self._audit_alone(
                "login_failed",
                actor_ip=actor_ip,
                details={"email": email},
            )
            raise

    async def _login_tx(
        self,
        email: str,
        password: str,
        *,
        actor_ip: str | None,
    ) -> LoginResult:
        async with self._transaction() as (users, tokens, audit):
            user = await users.get_by_email(email)
            if (
                user is None
                or not user.is_active
                or not verify_password(user.password_hash, password)
            ):
                raise InvalidCredentialsError

            refresh_raw = generate_raw_token("prt")
            expires_at = utcnow() + self._refresh_ttl()
            await tokens.add(
                AuthToken(
                    user_id=user.id,
                    token_type=AuthTokenType.REFRESH,
                    token_hash="",
                    scopes=[SCOPE_PORTAL_FULL],
                    expires_at=expires_at,
                ),
                refresh_raw,
            )
            access, access_exp = self._jwt.issue_access_token(
                str(user.id),
                [SCOPE_PORTAL_FULL],
                token_type=AuthTokenType.API,
            )
            await audit.log("login", user_id=user.id, actor_ip=actor_ip)
            return LoginResult(
                user=user,
                access_token=access,
                access_expires_at=access_exp,
                refresh_token=refresh_raw,
                refresh_expires_at=expires_at,
            )

    # --- password change -------------------------------------------------

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
        *,
        actor_ip: str | None = None,
    ) -> None:
        """Verify old password, set the new one, revoke refresh tokens.

        Device tokens (FBReader) stay valid — they are separate credentials.
        """
        async with self._transaction() as (users, tokens, audit):
            fresh = await users.get(user.id)
            if (
                fresh is None
                or not fresh.is_active
                or not verify_password(fresh.password_hash, old_password)
            ):
                await audit.log("password_change_failed", user_id=user.id, actor_ip=actor_ip)
                raise InvalidCredentialsError

            if len(new_password) < 12:
                msg = "password must be at least 12 characters"
                raise InvalidCredentialsError(msg)

            await users.update_password(user.id, hash_password(new_password))
            await tokens.revoke_all_for_user(user.id, AuthTokenType.REFRESH)
            await audit.log("password_changed", user_id=user.id, actor_ip=actor_ip)

    # --- refresh rotation ---------------------------------------------

    async def refresh(self, raw_refresh_token: str, *, actor_ip: str | None = None) -> LoginResult:
        async with self._transaction() as (users, tokens, audit):
            token = await tokens.get_active_by_raw(raw_refresh_token, AuthTokenType.REFRESH)
            if token is None:
                await audit.log("refresh_rejected", actor_ip=actor_ip)
                raise TokenRevokedError

            user = await users.get(token.user_id)
            if user is None or not user.is_active:
                await audit.log("refresh_rejected", actor_ip=actor_ip)
                raise TokenRevokedError

            await tokens.revoke(token.user_id, token.id)
            await tokens.touch(token.id)

            new_refresh_raw = generate_raw_token("prt")
            new_expires_at = utcnow() + self._refresh_ttl()
            await tokens.add(
                AuthToken(
                    user_id=user.id,
                    token_type=AuthTokenType.REFRESH,
                    token_hash="",
                    scopes=[SCOPE_PORTAL_FULL],
                    expires_at=new_expires_at,
                ),
                new_refresh_raw,
            )
            access, access_exp = self._jwt.issue_access_token(
                str(user.id),
                [SCOPE_PORTAL_FULL],
                token_type=AuthTokenType.API,
            )
            await audit.log(
                "refresh",
                user_id=user.id,
                actor_ip=actor_ip,
                entity_id=str(token.id),
            )
            return LoginResult(
                user=user,
                access_token=access,
                access_expires_at=access_exp,
                refresh_token=new_refresh_raw,
                refresh_expires_at=new_expires_at,
            )

    async def logout(self, raw_refresh_token: str, *, actor_ip: str | None = None) -> None:
        async with self._transaction() as (_users, tokens, audit):
            token = await tokens.get_active_by_raw(raw_refresh_token, AuthTokenType.REFRESH)
            if token is not None:
                await tokens.revoke(token.user_id, token.id)
                await audit.log(
                    "logout",
                    user_id=token.user_id,
                    actor_ip=actor_ip,
                    entity_id=str(token.id),
                )

    # --- device tokens (OPDS-ready, Phase 7) ---------------------------

    async def create_device_token(
        self,
        user: User,
        name: str,
        scopes: list[str],
        *,
        actor_ip: str | None = None,
    ) -> DeviceTokenCreated:
        async with self._transaction() as (_users, tokens, audit):
            raw = generate_raw_token("pdt")
            token = await tokens.add(
                AuthToken(
                    user_id=user.id,
                    token_type=AuthTokenType.DEVICE,
                    token_hash="",
                    scopes=scopes,
                    name=name,
                    expires_at=utcnow() + timedelta(days=self._settings.device_token_ttl_days),
                ),
                raw,
            )
            await audit.log(
                "device_token_created",
                user_id=user.id,
                actor_ip=actor_ip,
                entity_type="api_tokens",
                entity_id=str(token.id),
                details={"name": name, "scopes": scopes},
            )
            return DeviceTokenCreated(token=token, raw_token=raw)

    async def list_device_tokens(self, user: User) -> list[AuthToken]:
        async with self._session_factory() as session:
            tokens = AuthTokenRepository(session)
            return await tokens.list_for_user(user.id, AuthTokenType.DEVICE)

    async def revoke_device_token(
        self,
        user: User,
        token_id: UUID,
        *,
        actor_ip: str | None = None,
    ) -> bool:
        async with self._transaction() as (_users, tokens, audit):
            revoked = await tokens.revoke(user.id, token_id)
            if revoked:
                await audit.log(
                    "device_token_revoked",
                    user_id=user.id,
                    actor_ip=actor_ip,
                    entity_type="api_tokens",
                    entity_id=str(token_id),
                )
            return revoked

    # --- introspection --------------------------------------------------

    def verify_access_token(self, token: str) -> TokenPrincipal:
        return self._jwt.verify(token)


def utcnow_alias() -> datetime:
    return datetime.now(UTC)
