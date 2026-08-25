"""Job repository: PostgreSQL-backed queue with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.jobs.orm import JobModel, JobStatus


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        run_at: datetime | None = None,
        max_attempts: int = 5,
    ) -> UUID:
        job = JobModel(
            kind=kind,
            payload=payload,
            max_attempts=max_attempts,
            run_at=run_at or datetime.now(UTC),
        )
        self._session.add(job)
        await self._session.flush()
        return job.id

    async def claim_batch(self, worker_id: str, limit: int = 10) -> Sequence[JobModel]:
        """Atomically claim queued jobs (SKIP LOCKED — safe for N workers)."""
        stmt = (
            select(JobModel)
            .where(
                JobModel.status == JobStatus.QUEUED.value,
                JobModel.run_at <= datetime.now(UTC),
            )
            .order_by(JobModel.run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = (await self._session.execute(stmt)).scalars().all()
        if jobs:
            await self._session.execute(
                update(JobModel)
                .where(JobModel.id.in_([j.id for j in jobs]))
                .values(status=JobStatus.RUNNING.value, locked_at=datetime.now(UTC)),
            )
        return jobs

    async def mark_done(self, job_id: UUID) -> None:
        await self._session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(
                status=JobStatus.DONE.value,
                updated_at=datetime.now(UTC),
                locked_at=None,
            ),
        )

    async def mark_failed(self, job_id: UUID, error: str, *, retry: bool) -> None:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            return
        attempts = job.attempts + 1
        if retry and attempts < job.max_attempts:
            await self._session.execute(
                update(JobModel)
                .where(JobModel.id == job_id)
                .values(
                    status=JobStatus.QUEUED.value,
                    attempts=attempts,
                    last_error=error[:2000],
                    updated_at=datetime.now(UTC),
                    locked_at=None,
                ),
            )
        else:
            await self._session.execute(
                update(JobModel)
                .where(JobModel.id == job_id)
                .values(
                    status=JobStatus.FAILED.value,
                    attempts=attempts,
                    last_error=error[:2000],
                    updated_at=datetime.now(UTC),
                    locked_at=None,
                ),
            )

    async def get(self, job_id: UUID) -> JobModel | None:
        return await self._session.get(JobModel, job_id)
