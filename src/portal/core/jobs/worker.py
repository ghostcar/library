"""Worker process: claims jobs from the PostgreSQL queue and runs handlers.

Run: .venv/bin/python -m portal.core.jobs.worker
Handlers register by kind; unknown kinds fail the job with a clear error.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.config.config import get_settings
from portal.core.database.engine import build_container
from portal.core.jobs.repository import JobRepository

logger = logging.getLogger("portal.worker")

Handler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, Handler] = {}


def register_handler(kind: str, handler: Handler) -> None:
    _handlers[kind] = handler


async def _noop_handler(payload: dict[str, Any]) -> None:
    logger.info("noop job payload=%s", payload)


register_handler("noop", _noop_handler)


async def process_batch(
    session_factory: async_sessionmaker[AsyncSession],
    batch_size: int = 10,
) -> int:
    """Claim and process one batch. Returns number of processed jobs."""
    processed = 0
    async with session_factory() as session:
        async with session.begin():
            jobs_repo = JobRepository(session)
            jobs = await jobs_repo.claim_batch("worker", limit=batch_size)
            for job in jobs:
                handler = _handlers.get(job.kind)
                try:
                    if handler is None:
                        msg = f"no handler for job kind '{job.kind}'"
                        raise LookupError(msg)
                    await handler(dict(job.payload))
                    await jobs_repo.mark_done(job.id)
                except Exception as exc:
                    logger.exception("job %s (%s) failed", job.id, job.kind)
                    await jobs_repo.mark_failed(job.id, str(exc), retry=True)
                processed += 1
    return processed


async def run_forever(poll_interval_seconds: float = 2.0) -> None:
    settings = get_settings()
    container = build_container(settings)
    session_factory = container["session_factory"]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker started (db=%s)", settings.database_url.split("@")[-1])
    while not stop.is_set():
        try:
            count = await process_batch(session_factory)
            if count == 0:
                with_any = await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
                if with_any:
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
