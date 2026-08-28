"""Outbox repository: transactional outbox pattern (master prompt 4.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.events.orm import OutboxEventModel, OutboxStatus


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, event_type: str, payload: dict[str, Any]) -> UUID:
        event = OutboxEventModel(event_type=event_type, payload=payload)
        self._session.add(event)
        await self._session.flush()
        return event.id

    async def fetch_pending(self, limit: int = 100) -> list[OutboxEventModel]:
        stmt = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status == OutboxStatus.PENDING.value,
                (OutboxEventModel.next_attempt_at.is_(None))
                | (OutboxEventModel.next_attempt_at <= datetime.now(UTC)),
            )
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def mark_processed(self, event_id: UUID) -> None:
        await self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(status=OutboxStatus.PROCESSED.value, processed_at=datetime.now(UTC)),
        )

    async def mark_failed(
        self,
        event_id: UUID,
        error: str,
        *,
        max_attempts: int = 5,
    ) -> None:
        event = await self._session.get(OutboxEventModel, event_id)
        if event is None:
            return
        attempts = event.attempts + 1
        if attempts < max_attempts:
            delay = min(3600, 2 ** min(attempts, 10))
            await self._session.execute(
                update(OutboxEventModel)
                .where(OutboxEventModel.id == event_id)
                .values(
                    status=OutboxStatus.PENDING.value,
                    attempts=attempts,
                    last_error=error[:2000],
                    next_attempt_at=datetime.now(UTC) + timedelta(seconds=delay),
                ),
            )
            return
        await self._session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                status=OutboxStatus.FAILED.value,
                attempts=attempts,
                last_error=error[:2000],
                next_attempt_at=None,
            ),
        )

    async def count_pending(self) -> int:
        stmt = select(OutboxEventModel.id).where(
            OutboxEventModel.status == OutboxStatus.PENDING.value,
        )
        return len(list((await self._session.execute(stmt)).scalars().all()))


def new_event_id() -> uuid.UUID:
    return uuid.uuid4()
