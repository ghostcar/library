"""Safe scheduled import from explicitly configured local directories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.auth.orm import UserModel
from portal.modules.library.application.import_service import ImportService
from portal.modules.library.domain.import_entities import ImportSource
from portal.modules.library.infrastructure.repositories import AssetRepository

logger = logging.getLogger("library.watched_inbox")


@dataclass(frozen=True, slots=True)
class WatchedInboxResult:
    discovered: int
    imported: int


class WatchedInboxService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        importer: ImportService,
    ) -> None:
        self._session_factory = session_factory
        self._importer = importer

    async def run_once(
        self,
        *,
        owner_email: str,
        roots: list[Path],
        max_files: int,
        min_age_seconds: int,
    ) -> WatchedInboxResult:
        """Import at most one bounded batch; source files remain untouched."""
        async with self._session_factory() as session:
            owner_id = (
                await session.execute(
                    select(UserModel.id).where(
                        func.lower(UserModel.email) == owner_email.strip().lower(),
                        UserModel.is_active.is_(True),
                    ),
                )
            ).scalar_one_or_none()
            if owner_id is None:
                raise LookupError("watched inbox owner is missing or inactive")
            known_hashes = await AssetRepository(session).all_hashes(owner_id)

        entries = await self._importer.scan_directories(
            owner_id,
            roots,
            known_hashes=known_hashes,
            min_age_seconds=min_age_seconds,
        )
        fresh = [entry for entry in entries if entry.verdict == "new"][:max_files]
        if fresh:
            await self._importer.import_from_scan(
                owner_id,
                fresh,
                source=ImportSource.INBOX,
            )
        return WatchedInboxResult(discovered=len(entries), imported=len(fresh))
