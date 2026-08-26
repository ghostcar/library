"""Retention cleanup: audit_log, processed outbox (master prompt 19).

Configured by LIBRARY_AUDIT_RETENTION_DAYS (0 = keep forever)
and LIBRARY_OUTBOX_RETENTION_DAYS (default 30).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.auth.orm import AuditLogModel
from portal.core.config.config import get_settings
from portal.core.events.orm import OutboxEventModel, OutboxStatus

logger = logging.getLogger("library.retention")


def run_retention(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Delete expired rows. Returns number of removed rows. Non-fatal."""
    settings = get_settings()
    removed = 0
    now = datetime.now(UTC)

    async def _run() -> None:
        nonlocal removed
        async with session_factory() as session, session.begin():
            if settings.audit_retention_days > 0:
                cutoff = now - timedelta(days=settings.audit_retention_days)
                result = await session.execute(
                    delete(AuditLogModel).where(AuditLogModel.created_at < cutoff),
                )
                removed += int(getattr(result, "rowcount", 0))
            cutoff_outbox = now - timedelta(days=settings.outbox_retention_days)
            result = await session.execute(
                delete(OutboxEventModel).where(
                    OutboxEventModel.status == OutboxStatus.PROCESSED.value,
                    OutboxEventModel.processed_at.is_not(None),
                    OutboxEventModel.processed_at < cutoff_outbox,
                ),
            )
            removed += int(getattr(result, "rowcount", 0))

    asyncio.get_running_loop().run_until_complete(_run())
    if removed:
        logger.info("retention removed %s rows", removed)
    return removed
