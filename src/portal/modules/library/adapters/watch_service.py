"""Watch rules, polling with backoff, observations, in-app notifications.

Master prompt 9.3/9.4: conditional GET, per-rule interval, exponential
backoff + jitter, dedup of observations, notifications only on real
transitions, degraded status on unexpected layouts.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.modules.library.adapters.opds_adapter import (
    OPDSAdapter,
    OPDSParseError,
)
from portal.modules.library.adapters.source_orm import (
    NotificationModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.adapters.sources import get_adapter_descriptor
from portal.modules.library.domain.entities import normalize_title
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    WorkAuthorModel,
    WorkModel,
)

logger = logging.getLogger("library.sources")

BACKOFF_BASE_SECONDS = 300  # 5 min
BACKOFF_CAP_SECONDS = 6 * 3600  # 6 h
JITTER_SECONDS = 60
DEGRADED_THRESHOLD = 2  # consecutive failures


def next_poll_after(failure_count: int, interval_seconds: int) -> datetime:
    """Success: interval. Failure: exponential backoff + jitter, capped."""
    if failure_count == 0:
        delay = interval_seconds
    else:
        delay = min(BACKOFF_BASE_SECONDS * (2 ** (failure_count - 1)), BACKOFF_CAP_SECONDS)
        delay += random.randint(0, JITTER_SECONDS)  # noqa: S311 - jitter, not crypto
    return datetime.now(UTC) + timedelta(seconds=delay)


class WatchService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        opds: OPDSAdapter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._opds = opds or OPDSAdapter()

    # --- rule management --------------------------------------------------

    async def create_rule(
        self,
        owner_id: UUID,
        *,
        adapter_id: str,
        name: str,
        url: str,
        interval_seconds: int = 3600,
    ) -> UUID | None:
        descriptor = get_adapter_descriptor(adapter_id)
        if descriptor is None or not descriptor.enabled:
            return None
        if not url.startswith(("http://", "https://")):
            return None
        async with self._session_factory() as session, session.begin():
            rule = WatchRuleModel(
                owner_id=owner_id,
                adapter_id=adapter_id,
                name=name.strip()[:200] or "Без названия",
                url=url.strip(),
                interval_seconds=max(300, min(interval_seconds, 86400)),
                next_poll_at=datetime.now(UTC),
            )
            session.add(rule)
            await session.flush()
            return rule.id

    async def list_rules(self, owner_id: UUID) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(WatchRuleModel)
                .where(WatchRuleModel.owner_id == owner_id)
                .order_by(WatchRuleModel.created_at.desc())
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "adapter_id": r.adapter_id,
                    "name": r.name,
                    "url": r.url,
                    "interval_seconds": r.interval_seconds,
                    "enabled": r.enabled,
                    "degraded": r.degraded,
                    "last_polled_at": r.last_polled_at,
                    "next_poll_at": r.next_poll_at,
                    "failure_count": r.failure_count,
                    "last_error": r.last_error,
                }
                for r in rows
            ]

    async def delete_rule(self, owner_id: UUID, rule_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                delete(WatchRuleModel).where(
                    WatchRuleModel.owner_id == owner_id,
                    WatchRuleModel.id == rule_id,
                ),
            )
            return int(result.rowcount) > 0  # type: ignore[attr-defined]

    async def set_rule_enabled(self, owner_id: UUID, rule_id: UUID, enabled: bool) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(WatchRuleModel)
                .where(WatchRuleModel.owner_id == owner_id, WatchRuleModel.id == rule_id)
                .values(enabled=enabled, next_poll_at=datetime.now(UTC) if enabled else None),
            )
            return int(result.rowcount) > 0  # type: ignore[attr-defined]

    # --- scheduler tick -----------------------------------------------------

    async def schedule_due(self) -> int:
        """Enqueue poll jobs for due rules. Called periodically by the worker."""
        from portal.core.jobs.repository import JobRepository

        now = datetime.now(UTC)
        enqueued = 0
        async with self._session_factory() as session, session.begin():
            due = (
                await session.execute(
                    select(WatchRuleModel.id, WatchRuleModel.owner_id).where(
                        WatchRuleModel.enabled.is_(True),
                        WatchRuleModel.next_poll_at.is_not(None),
                        WatchRuleModel.next_poll_at <= now,
                    ),
                )
            ).all()
            jobs = JobRepository(session)
            for rule_id, owner_id in due:
                await jobs.enqueue(
                    "poll_watch",
                    {"owner_id": str(owner_id), "watch_rule_id": str(rule_id)},
                )
                # reserve the slot so the next tick doesn't double-enqueue
                await session.execute(
                    update(WatchRuleModel)
                    .where(WatchRuleModel.id == rule_id)
                    .values(next_poll_at=now + timedelta(seconds=60)),
                )
                enqueued += 1
        return enqueued

    # --- polling ------------------------------------------------------------

    async def poll_rule(self, owner_id: UUID, rule_id: UUID) -> dict[str, Any]:
        """Execute one poll for a rule: fetch, dedup observations, notify."""
        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None or rule.owner_id != owner_id:
                msg = "watch rule not found"
                raise LookupError(msg)
            descriptor = get_adapter_descriptor(rule.adapter_id)
            if descriptor is None or not descriptor.enabled:
                rule.last_error = "adapter disabled"
                rule.next_poll_at = next_poll_after(1, rule.interval_seconds)
                return {"status": "skipped", "reason": "adapter disabled"}

        try:
            result = await self._opds.fetch(
                rule.url,
                etag=rule.etag,
                last_modified=rule.last_modified,
            )
        except OPDSParseError as exc:
            return await self._record_failure(
                rule_id, rule.owner_id, rule.interval_seconds, str(exc)
            )

        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None:
                return {"status": "error", "reason": "rule deleted"}
            new_count = 0
            if result.not_modified:
                new_count = 0
            else:
                for entry in result.entries:
                    inserted = await self._insert_observation(session, rule, entry)
                    if inserted:
                        new_count += 1
                        session.add(
                            NotificationModel(
                                owner_id=owner_id,
                                kind="new_release",
                                title=f"Новая публикация: {entry.title}",
                                body=(
                                    f"Источник: {descriptor.title}. "
                                    f"Автор: {entry.author_name or 'неизвестен'}. "
                                    f"Файл не скачан — доступно для получения по ссылке."
                                ),
                                data={
                                    "watch_rule_id": str(rule_id),
                                    "external_id": entry.external_id,
                                    "url": entry.url,
                                    "author": entry.author_name,
                                },
                            ),
                        )
            rule.etag = result.etag
            rule.last_modified = result.last_modified
            rule.last_polled_at = datetime.now(UTC)
            rule.failure_count = 0
            rule.degraded = False
            rule.last_error = None
            rule.next_poll_at = next_poll_after(0, rule.interval_seconds)
            return {"status": "ok", "not_modified": result.not_modified, "new": new_count}

    async def _insert_observation(
        self,
        session: AsyncSession,
        rule: WatchRuleModel,
        entry: Any,  # SourceEntry
    ) -> bool:
        """Insert observation; False when already seen (dedup)."""
        from portal.modules.library.adapters.sources import SourceEntry

        assert isinstance(entry, SourceEntry)
        exists = (
            await session.execute(
                select(SourceObservationModel.id).where(
                    SourceObservationModel.watch_rule_id == rule.id,
                    SourceObservationModel.external_id == entry.external_id,
                ),
            )
        ).scalar_one_or_none()
        if exists is not None:
            return False
        work_id, series_id, evidence = await self._match_canonical(session, rule.owner_id, entry)
        session.add(
            SourceObservationModel(
                owner_id=rule.owner_id,
                watch_rule_id=rule.id,
                adapter_id=rule.adapter_id,
                external_id=entry.external_id,
                title=entry.title,
                author_name=entry.author_name,
                url=entry.url,
                parser_version=PARSER_VERSION_LOCAL,
                raw=dict(entry.raw),
                work_id=work_id,
                series_id=series_id,
                match_evidence=evidence,
            ),
        )
        await session.flush()
        return True

    async def _match_canonical(
        self, session: AsyncSession, owner_id: UUID, entry: Any
    ) -> tuple[UUID | None, UUID | None, dict[str, object]]:
        """Link only deterministic, owner-scoped matches; leave ambiguity unresolved."""
        title = normalize_title(entry.title)
        stmt = select(WorkModel).where(
            WorkModel.owner_id == owner_id,
            WorkModel.title_normalized == title,
        )
        candidates = list((await session.execute(stmt)).scalars().all())
        if entry.author_name:
            author = normalize_title(entry.author_name)
            author_stmt = (
                select(WorkModel)
                .join(WorkAuthorModel, WorkAuthorModel.work_id == WorkModel.id)
                .join(AuthorModel, AuthorModel.id == WorkAuthorModel.author_id)
                .where(
                    WorkModel.owner_id == owner_id,
                    WorkModel.title_normalized == title,
                    AuthorModel.name_normalized == author,
                )
            )
            author_candidates = list((await session.execute(author_stmt)).scalars().all())
            if author_candidates:
                candidates = author_candidates
        if len(candidates) != 1:
            return None, None, {
                "match": "ambiguous" if candidates else "none",
                "title_normalized": title,
            }
        work = candidates[0]
        memberships = list(
            (
                await session.execute(
                    select(SeriesMembershipModel.series_id).where(
                        SeriesMembershipModel.owner_id == owner_id,
                        SeriesMembershipModel.work_id == work.id,
                    ),
                )
            ).scalars().all()
        )
        series_id = memberships[0] if len(memberships) == 1 else None
        return work.id, series_id, {
            "match": "exact_title_author" if entry.author_name else "exact_title",
            "title_normalized": title,
            "series_match": "unique_membership" if series_id else "ambiguous_or_none",
        }

    async def _record_failure(
        self,
        rule_id: UUID,
        owner_id: UUID,
        interval_seconds: int,
        error: str,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None:
                return {"status": "error", "reason": "rule deleted"}
            rule.failure_count = (rule.failure_count or 0) + 1
            rule.last_error = error[:1000]
            rule.last_polled_at = datetime.now(UTC)
            rule.next_poll_at = next_poll_after(rule.failure_count, interval_seconds)
            was_degraded = rule.degraded
            if rule.failure_count >= DEGRADED_THRESHOLD:
                rule.degraded = True
            degraded_now = rule.degraded and not was_degraded
            if degraded_now:
                session.add(
                    NotificationModel(
                        owner_id=owner_id,
                        kind="source_degraded",
                        title=f"Источник деградировал: {rule.name}",
                        body=f"Повторные ошибки опроса: {error[:300]}",
                        data={"watch_rule_id": str(rule_id)},
                    ),
                )
            return {"status": "error", "reason": error, "failures": rule.failure_count}

    # --- notifications --------------------------------------------------------

    async def notifications(self, owner_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(NotificationModel)
                .where(NotificationModel.owner_id == owner_id)
                .order_by(NotificationModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "title": r.title,
                    "body": r.body,
                    "read": r.read_at is not None,
                    "created_at": r.created_at,
                    "data": r.data,
                }
                for r in rows
            ]

    async def unread_count(self, owner_id: UUID) -> int:
        async with self._session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count())
                    .select_from(NotificationModel)
                    .where(
                        NotificationModel.owner_id == owner_id,
                        NotificationModel.read_at.is_(None),
                    ),
                )
                or 0,
            )

    async def mark_all_read(self, owner_id: UUID) -> int:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(NotificationModel)
                .where(
                    NotificationModel.owner_id == owner_id,
                    NotificationModel.read_at.is_(None),
                )
                .values(read_at=datetime.now(UTC)),
            )
            return int(result.rowcount)  # type: ignore[attr-defined]


PARSER_VERSION_LOCAL = "opds-atom-v1"
