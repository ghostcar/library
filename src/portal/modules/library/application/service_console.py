"""Owner-scoped read model for background processing diagnostics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.events.orm import OutboxEventModel
from portal.core.jobs.orm import JobModel
from portal.modules.library.adapters.source_orm import WatchRuleModel


def _short(value: object) -> str:
    text = str(value or "")
    return f"{text[:8]}…" if len(text) > 8 else text


def _job_target(job: JobModel) -> str:
    fields = {
        "poll_watch": ("watch_rule_id", "правило"),
        "normalize_import": ("run_id", "разбор"),
        "propose_import": ("item_id", "файл"),
    }
    key, label = fields.get(job.kind, ("batch_id", "объект"))
    value = job.payload.get(key)
    return f"{label} {_short(value)}" if value else "—"


class ServiceConsoleQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self, owner_id: UUID) -> dict[str, Any]:
        owner = str(owner_id)
        job_count_rows = (
            await self._session.execute(
                select(JobModel.status, func.count())
                .where(JobModel.payload["owner_id"].astext == owner)
                .group_by(JobModel.status)
            )
        ).all()
        job_counts: dict[str, int] = {status: count for status, count in job_count_rows}
        job_kind_rows = (
            await self._session.execute(
                select(JobModel.kind, func.count())
                .where(JobModel.payload["owner_id"].astext == owner)
                .group_by(JobModel.kind)
            )
        ).all()
        job_kind_counts: dict[str, int] = {kind: count for kind, count in job_kind_rows}
        jobs = list(
            (
                await self._session.execute(
                    select(JobModel)
                    .where(JobModel.payload["owner_id"].astext == owner)
                    .order_by(JobModel.created_at.desc())
                    .limit(100)
                )
            ).scalars()
        )
        outbox_count_rows = (
            await self._session.execute(
                select(OutboxEventModel.status, func.count())
                .where(OutboxEventModel.payload["owner_id"].astext == owner)
                .group_by(OutboxEventModel.status)
            )
        ).all()
        outbox_counts: dict[str, int] = {status: count for status, count in outbox_count_rows}
        events = list(
            (
                await self._session.execute(
                    select(OutboxEventModel)
                    .where(OutboxEventModel.payload["owner_id"].astext == owner)
                    .order_by(OutboxEventModel.created_at.desc())
                    .limit(100)
                )
            ).scalars()
        )
        rules = list(
            (
                await self._session.execute(
                    select(WatchRuleModel)
                    .where(WatchRuleModel.owner_id == owner_id)
                    .order_by(WatchRuleModel.created_at.desc())
                )
            ).scalars()
        )
        return {
            "job_counts": job_counts,
            "job_kind_counts": job_kind_counts,
            "jobs": [
                {
                    "id": job.id,
                    "kind": job.kind,
                    "target": _job_target(job),
                    "status": job.status,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "run_at": job.run_at,
                    "updated_at": job.updated_at,
                    "last_error": job.last_error,
                }
                for job in jobs[:30]
            ],
            "outbox_counts": outbox_counts,
            "events": [
                {
                    "id": event.id,
                    "type": event.event_type,
                    "status": event.status,
                    "attempts": event.attempts,
                    "created_at": event.created_at,
                    "processed_at": event.processed_at,
                    "last_error": event.last_error,
                }
                for event in events[:20]
            ],
            "rules": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "adapter_id": rule.adapter_id,
                    "enabled": rule.enabled,
                    "degraded": rule.degraded,
                    "last_status": rule.last_status,
                    "last_new_count": rule.last_new_count,
                    "last_duration_ms": rule.last_duration_ms,
                    "last_polled_at": rule.last_polled_at,
                    "next_poll_at": rule.next_poll_at,
                    "failure_count": rule.failure_count,
                    "last_error": rule.last_error,
                    "parser_version": rule.parser_version,
                }
                for rule in rules
            ],
        }
