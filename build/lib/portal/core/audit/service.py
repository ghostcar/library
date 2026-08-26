"""Audit service: records sensitive actions (master prompt 12)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from portal.core.auth.repository import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def log(
        self,
        action: str,
        *,
        user_id: UUID | None = None,
        actor_ip: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self._repository.record(
            action=action,
            user_id=user_id,
            actor_ip=actor_ip,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
