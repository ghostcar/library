"""Worker process: claims jobs from the PostgreSQL queue and runs handlers.

Run: .venv/bin/python -m portal.core.jobs.worker
Handlers register by kind; unknown kinds fail the job with a clear error.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.config.config import get_settings
from portal.core.database import models as _models  # noqa: F401 - register ORM
from portal.core.database.engine import build_container
from portal.core.jobs.repository import JobRepository

logger = logging.getLogger("portal.worker")

Handler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, Handler] = {}
EventHandler = Callable[[dict[str, Any]], Awaitable[None]]
_event_handlers: dict[str, EventHandler] = {}


def register_handler(kind: str, handler: Handler) -> None:
    _handlers[kind] = handler


def register_event_handler(event_type: str, handler: EventHandler) -> None:
    """Register an idempotent typed event consumer by explicit event name."""
    _event_handlers[event_type] = handler


async def _noop_handler(payload: dict[str, Any]) -> None:
    logger.info("noop job payload=%s", payload)


async def _normalize_handler(payload: dict[str, Any]) -> None:
    from portal.core.config.config import get_settings
    from portal.core.storage.local import LocalStorageAdapter
    from portal.modules.library.application.normalization_service import (
        NormalizationService,
    )
    from portal.modules.library.domain import normalization as nz

    settings = get_settings()
    container = build_container(settings)
    service = NormalizationService(
        session_factory=container["session_factory"],
        storage=LocalStorageAdapter(Path(settings.storage_root)),
    )
    try:
        owner_id = UUID(payload["owner_id"])
        run_id = UUID(payload["run_id"])
        result = await service.execute_run(owner_id, run_id)
        logger.info(
            "normalization run %s -> state=%s derivative=%s",
            run_id,
            result.state.value,
            result.derivative_asset_id,
        )
        if result.state is nz.RunState.FAILED:
            msg = "normalization run failed"
            raise RuntimeError(msg)
    finally:
        await container["engine"].dispose()


async def _poll_watch_handler(payload: dict[str, Any]) -> None:
    from portal.modules.library.adapters.opds_adapter import OPDSAdapter
    from portal.modules.library.adapters.watch_service import WatchService

    settings = get_settings()
    container = build_container(settings)
    service = WatchService(
        session_factory=container["session_factory"],
        opds=OPDSAdapter(),
    )
    try:
        owner_id = UUID(payload["owner_id"])
        rule_id = UUID(payload["watch_rule_id"])
        outcome = await service.poll_rule(owner_id, rule_id)
        logger.info("poll %s -> %s", rule_id, outcome)
    finally:
        await container["engine"].dispose()


register_handler("noop", _noop_handler)
register_handler("normalize", _normalize_handler)
register_handler("poll_watch", _poll_watch_handler)


async def _observed_event_handler(payload: dict[str, Any]) -> None:
    """Default durable observer until a feature consumer is installed."""
    logger.info("domain event observed payload=%s", payload)


for _event_type in (
    "BookFileImported",
    "WorkMatched",
    "DuplicateSuspected",
    "NormalizationRequested",
    "NormalizationCompleted",
    "NormalizationFailed",
    "SourceRecordObserved",
    "NewReleaseDetected",
    "BookAcquired",
    "BookMarkedRead",
    "SeriesProgressChanged",
    "NotificationRequested",
):
    register_event_handler(_event_type, _observed_event_handler)


async def run_retention_safe(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Daily retention cleanup (audit_log, outbox). Non-fatal."""
    try:
        from portal.core.retention import run_retention

        await run_retention(session_factory)
    except Exception:
        logger.exception("retention tick failed")


async def schedule_due_watches(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Enqueue poll jobs for due watch rules (throttled, non-fatal)."""
    try:
        from portal.modules.library.adapters.opds_adapter import OPDSAdapter
        from portal.modules.library.adapters.watch_service import WatchService

        service = WatchService(
            session_factory=session_factory,
            opds=OPDSAdapter(),
        )
        enqueued = await service.schedule_due()
        if enqueued:
            logger.info("scheduler enqueued %s watch polls", enqueued)
    except Exception:
        logger.exception("watch scheduler tick failed")


async def run_watched_inbox_safe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Poll configured local inbox roots; disabled by default and non-fatal."""
    settings = get_settings()
    if not settings.watched_inbox_enabled:
        return
    try:
        from portal.core.storage.local import LocalStorageAdapter
        from portal.modules.library.application.import_service import ImportService
        from portal.modules.library.application.watched_inbox import WatchedInboxService

        importer = ImportService(
            session_factory=session_factory,
            storage=LocalStorageAdapter(Path(settings.storage_root)),
            max_file_bytes=settings.max_file_bytes,
            max_files_per_batch=settings.max_files_per_batch,
        )
        result = await WatchedInboxService(session_factory, importer).run_once(
            owner_email=settings.watched_inbox_owner_email or "",
            roots=[Path(root) for root in settings.import_roots],
            max_files=settings.max_files_per_batch,
            min_age_seconds=settings.watched_inbox_min_age_seconds,
        )
        if result.imported:
            logger.info(
                "watched inbox discovered=%s imported=%s",
                result.discovered,
                result.imported,
            )
    except Exception:
        logger.exception("watched inbox tick failed")


async def process_batch(
    session_factory: async_sessionmaker[AsyncSession],
    batch_size: int = 10,
) -> int:
    """Claim and process one batch. Returns number of processed jobs."""
    processed = 0
    async with session_factory() as session, session.begin():
        jobs_repo = JobRepository(session)
        await jobs_repo.requeue_stale()
        jobs = list(await jobs_repo.claim_batch("worker", limit=batch_size))
        claimed = [(job.id, job.kind, dict(job.payload)) for job in jobs]

    for job_id, kind, payload in claimed:
        handler = _handlers.get(kind)
        try:
            if handler is None:
                msg = f"no handler for job kind '{kind}'"
                raise LookupError(msg)
            await handler(payload)
            async with session_factory() as session, session.begin():
                await JobRepository(session).mark_done(job_id)
        except Exception as exc:
            logger.exception("job %s (%s) failed", job_id, kind)
            async with session_factory() as session, session.begin():
                await JobRepository(session).mark_failed(job_id, str(exc), retry=True)
        processed += 1
    return processed


async def process_outbox(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Dispatch durable domain events. Current handlers are idempotent observers."""
    from portal.core.events.repository import OutboxRepository

    async with session_factory() as session, session.begin():
        repo = OutboxRepository(session)
        events = await repo.fetch_pending(limit=100)
        for event in events:
            try:
                handler = _event_handlers.get(event.event_type)
                if handler is None:
                    raise LookupError(f"no outbox handler for event '{event.event_type}'")
                await handler(dict(event.payload))
                await repo.mark_processed(event.id)
            except Exception as exc:
                logger.exception("outbox event %s failed", event.id)
                await repo.mark_failed(event.id, str(exc))
        return len(events)


async def run_forever(poll_interval_seconds: float = 2.0) -> None:
    settings = get_settings()
    container = build_container(settings)
    session_factory = container["session_factory"]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker started (db=%s)", settings.database_url.split("@")[-1])
    last_schedule_check = 0.0
    last_retention_check = 0.0
    last_inbox_check = 0.0
    while not stop.is_set():
        try:
            count = await process_batch(session_factory)
            count += await process_outbox(session_factory)
            now = asyncio.get_running_loop().time()
            if now - last_schedule_check >= 30.0:
                last_schedule_check = now
                await schedule_due_watches(session_factory)
            if now - last_inbox_check >= settings.watched_inbox_interval_seconds:
                last_inbox_check = now
                await run_watched_inbox_safe(session_factory)
            if now - last_retention_check >= 6 * 3600.0:
                last_retention_check = now
                await run_retention_safe(session_factory)
            if count == 0:
                try:
                    stopped: bool = await asyncio.wait_for(
                        stop.wait(),
                        timeout=poll_interval_seconds,
                    )
                except TimeoutError:
                    stopped = False
                if stopped:
                    break
        except Exception:
            logger.exception("worker loop error")
            await asyncio.sleep(poll_interval_seconds)
    engine = container["engine"]
    await engine.dispose()
    logger.info("worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
