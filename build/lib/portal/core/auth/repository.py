"""Repositories for portal auth (users, tokens) and audit log."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.auth.domain import AuthToken, AuthTokenType, User, utcnow
from portal.core.auth.jwt_service import hash_token
from portal.core.auth.orm import AuditLogModel, AuthTokenModel, UserModel


def _scopes_to_str(scopes: list[str]) -> str:
    return " ".join(scopes)


def _scopes_from_str(value: str) -> list[str]:
    return value.split() if value else []


def _token_to_domain(m: AuthTokenModel) -> AuthToken:
    return AuthToken(
        user_id=m.user_id,
        token_type=AuthTokenType(m.token_type),
        token_hash=m.token_hash,
        scopes=_scopes_from_str(m.scopes),
        name=m.name,
        expires_at=m.expires_at,
        id=m.id,
        revoked_at=m.revoked_at,
        last_used_at=m.last_used_at,
        created_at=m.created_at,
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        self._session.add(
            UserModel(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                display_name=user.display_name,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at,
                updated_at=user.updated_at,
            ),
        )
        await self._session.flush()
        return user

    async def count(self) -> int:
        return int(await self._session.scalar(select(func.count()).select_from(UserModel)) or 0)

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return self._to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.strip().lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(m: UserModel) -> User:
        return User(
            email=m.email,
            password_hash=m.password_hash,
            display_name=m.display_name,
            id=m.id,
            is_active=m.is_active,
            is_superuser=m.is_superuser,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class AuthTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: AuthToken, raw_token: str) -> AuthToken:
        self._session.add(
            AuthTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_type=token.token_type.value,
                token_hash=hash_token(raw_token),
                scopes=_scopes_to_str(token.scopes),
                name=token.name,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                created_at=token.created_at,
            ),
        )
        await self._session.flush()
        return token

    async def get_active_by_raw(
        self,
        raw_token: str,
        token_type: AuthTokenType,
    ) -> AuthToken | None:
        stmt = select(AuthTokenModel).where(
            AuthTokenModel.token_hash == hash_token(raw_token),
            AuthTokenModel.token_type == token_type.value,
            AuthTokenModel.revoked_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        token = _token_to_domain(row)
        if not token.is_active:
            return None
        return token

    async def touch(self, token_id: UUID) -> None:
        await self._session.execute(
            update(AuthTokenModel)
            .where(AuthTokenModel.id == token_id)
            .values(last_used_at=utcnow()),
        )

    async def revoke(self, owner_user_id: UUID, token_id: UUID) -> bool:
        stmt = (
            update(AuthTokenModel)
            .where(
                AuthTokenModel.id == token_id,
                AuthTokenModel.user_id == owner_user_id,
                AuthTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount) > 0  # type: ignore[attr-defined]

    async def revoke_all_for_user(self, user_id: UUID, token_type: AuthTokenType) -> int:
        stmt = (
            update(AuthTokenModel)
            .where(
                AuthTokenModel.user_id == user_id,
                AuthTokenModel.token_type == token_type.value,
                AuthTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def list_for_user(self, user_id: UUID, token_type: AuthTokenType) -> list[AuthToken]:
        stmt = (
            select(AuthTokenModel)
            .where(
                AuthTokenModel.user_id == user_id,
                AuthTokenModel.token_type == token_type.value,
            )
            .order_by(AuthTokenModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_token_to_domain(r) for r in rows]


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        user_id: UUID | None,
        actor_ip: str | None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            AuditLogModel(
                action=action,
                user_id=user_id,
                actor_ip=actor_ip,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
            ),
        )
        await self._session.flush()


def _json_default(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    return json.dumps(value)
