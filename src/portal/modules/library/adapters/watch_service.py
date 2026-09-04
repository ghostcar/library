"""Watch rules, polling with backoff, observations, in-app notifications.

Master prompt 9.3/9.4: conditional GET, per-rule interval, exponential
backoff + jitter, dedup of observations, notifications only on real
transitions, degraded status on unexpected layouts.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.modules.library.adapters.author_today_adapter import AuthorTodayAdapter
from portal.modules.library.adapters.opds_adapter import (
    OPDSAdapter,
)
from portal.modules.library.adapters.source_orm import (
    NotificationModel,
    SourceEndpointModel,
    SourceLinkModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.adapters.sources import (
    SourceAdapter,
    SourceAdapterError,
    get_adapter_descriptor,
)
from portal.modules.library.domain.entities import normalize_title
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    SeriesModel,
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
        adapters: dict[str, SourceAdapter] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._opds = opds or OPDSAdapter()
        self._adapters: dict[str, SourceAdapter] = {
            "opds": self._opds,
            "flibusta": self._opds,
            "author_today": AuthorTodayAdapter(),
        }
        if adapters:
            self._adapters.update(adapters)

    # --- rule management --------------------------------------------------

    async def create_rule(
        self,
        owner_id: UUID,
        *,
        adapter_id: str,
        name: str,
        url: str,
        interval_seconds: int = 3600,
        source_endpoint_id: UUID | None = None,
    ) -> UUID | None:
        descriptor = get_adapter_descriptor(adapter_id)
        if descriptor is None or not descriptor.enabled:
            return None
        if not url.startswith(("http://", "https://")):
            return None
        async with self._session_factory() as session, session.begin():
            minimum_interval = 1800 if adapter_id == "author_today" else 300
            rule = WatchRuleModel(
                owner_id=owner_id,
                adapter_id=adapter_id,
                source_endpoint_id=source_endpoint_id,
                name=name.strip()[:200] or "Без названия",
                url=url.strip(),
                interval_seconds=max(minimum_interval, min(interval_seconds, 86400)),
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
                    "source_endpoint_id": r.source_endpoint_id,
                    "name": r.name,
                    "url": r.url,
                    "interval_seconds": r.interval_seconds,
                    "enabled": r.enabled,
                    "degraded": r.degraded,
                    "last_polled_at": r.last_polled_at,
                    "next_poll_at": r.next_poll_at,
                    "failure_count": r.failure_count,
                    "last_error": r.last_error,
                    "parser_version": r.parser_version,
                    "last_status": r.last_status,
                    "last_new_count": r.last_new_count,
                    "last_not_modified": r.last_not_modified,
                    "last_duration_ms": r.last_duration_ms,
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

    async def request_poll(self, owner_id: UUID, rule_id: UUID) -> str:
        """Queue one immediate owner-scoped poll without duplicating active work."""
        from portal.core.jobs.orm import JobModel, JobStatus
        from portal.core.jobs.repository import JobRepository

        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            rule = (
                await session.execute(
                    select(WatchRuleModel)
                    .where(
                        WatchRuleModel.id == rule_id,
                        WatchRuleModel.owner_id == owner_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if rule is None:
                return "not_found"
            if not rule.enabled:
                return "disabled"
            pending = (
                await session.execute(
                    select(JobModel.status)
                    .where(
                        JobModel.kind == "poll_watch",
                        JobModel.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                        JobModel.payload["owner_id"].astext == str(owner_id),
                        JobModel.payload["watch_rule_id"].astext == str(rule_id),
                    )
                    .order_by(JobModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if pending is not None:
                return pending
            adapter = self._adapters.get(rule.adapter_id)
            parser_changed = adapter is not None and rule.parser_version != adapter.parser_version
            if (
                not parser_changed
                and rule.last_polled_at is not None
                and rule.last_polled_at > now - timedelta(seconds=60)
            ):
                return "cooldown"
            await JobRepository(session).enqueue(
                "poll_watch",
                {"owner_id": str(owner_id), "watch_rule_id": str(rule_id)},
            )
            rule.next_poll_at = now + timedelta(seconds=60)
            return "queued"

    # --- scheduler tick -----------------------------------------------------

    async def schedule_due(self) -> int:
        """Enqueue poll jobs for due rules. Called periodically by the worker."""
        from portal.core.jobs.repository import JobRepository

        now = datetime.now(UTC)
        enqueued = 0
        async with self._session_factory() as session, session.begin():
            due = (
                await session.execute(
                    select(WatchRuleModel.id, WatchRuleModel.owner_id)
                    .where(
                        WatchRuleModel.enabled.is_(True),
                        WatchRuleModel.next_poll_at.is_not(None),
                        WatchRuleModel.next_poll_at <= now,
                    )
                    .with_for_update(skip_locked=True),
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
        started_at = monotonic()
        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None or rule.owner_id != owner_id:
                msg = "watch rule not found"
                raise LookupError(msg)
            descriptor = get_adapter_descriptor(rule.adapter_id)
            if descriptor is None or not descriptor.enabled:
                rule.last_error = "adapter disabled"
                rule.last_status = "skipped"
                rule.last_duration_ms = round((monotonic() - started_at) * 1000)
                rule.next_poll_at = next_poll_after(1, rule.interval_seconds)
                return {"status": "skipped", "reason": "adapter disabled"}

        adapter = self._adapters.get(rule.adapter_id)
        if adapter is None:
            return await self._record_failure(
                rule_id,
                rule.owner_id,
                rule.interval_seconds,
                "adapter implementation missing",
                started_at,
            )
        parser_changed = rule.parser_version != adapter.parser_version
        try:
            result = await adapter.fetch(
                rule.url,
                etag=None if parser_changed else rule.etag,
                last_modified=None if parser_changed else rule.last_modified,
            )
        except SourceAdapterError as exc:
            return await self._record_failure(
                rule_id, rule.owner_id, rule.interval_seconds, str(exc), started_at
            )

        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None:
                return {"status": "error", "reason": "rule deleted"}
            new_count = 0
            initial_author_today_baseline = rule.adapter_id == "author_today" and (
                rule.last_polled_at is None or rule.parser_version != adapter.parser_version
            )
            tracked_series_ids = (
                await self._tracked_series_ids(session, owner_id)
                if rule.adapter_id == "author_today" and not initial_author_today_baseline
                else set()
            )
            if result.not_modified:
                new_count = 0
            else:
                for entry in result.entries:
                    observation = await self._insert_observation(
                        session, rule, entry, adapter.parser_version
                    )
                    if observation is not None:
                        new_count += 1
                    should_notify = observation is not None and (
                        rule.adapter_id != "author_today"
                        or observation.series_id in tracked_series_ids
                    )
                    if should_notify and not initial_author_today_baseline:
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
                if rule.adapter_id == "author_today" and rule.source_endpoint_id is not None:
                    from portal.modules.library.application.source_onboarding_service import (
                        SourceOnboardingService,
                    )

                    reconciliation = await SourceOnboardingService(
                        session
                    ).reconcile_author_today_poll(
                        owner_id,
                        rule.source_endpoint_id,
                        list(result.entries),
                    )
                    if any(reconciliation.values()):
                        logger.info(
                            "Author.Today source graph reconciled",
                            extra={
                                "owner_id": str(owner_id),
                                "watch_rule_id": str(rule_id),
                                **reconciliation,
                            },
                        )
            rule.etag = result.etag
            rule.last_modified = result.last_modified
            rule.last_polled_at = datetime.now(UTC)
            rule.failure_count = 0
            rule.degraded = False
            rule.last_error = None
            rule.parser_version = adapter.parser_version
            rule.last_status = "ok"
            rule.last_new_count = new_count
            rule.last_not_modified = result.not_modified
            rule.last_duration_ms = round((monotonic() - started_at) * 1000)
            rule.next_poll_at = next_poll_after(0, rule.interval_seconds)
            return {"status": "ok", "not_modified": result.not_modified, "new": new_count}

    async def _insert_observation(
        self,
        session: AsyncSession,
        rule: WatchRuleModel,
        entry: Any,  # SourceEntry
        parser_version: str,
    ) -> SourceObservationModel | None:
        """Insert and return an observation; None when already seen (dedup)."""
        from portal.modules.library.adapters.sources import SourceEntry

        assert isinstance(entry, SourceEntry)
        existing = (
            await session.execute(
                select(SourceObservationModel).where(
                    SourceObservationModel.watch_rule_id == rule.id,
                    SourceObservationModel.external_id == entry.external_id,
                ),
            )
        ).scalar_one_or_none()
        if existing is not None:
            work_id, series_id, evidence = await self._match_canonical(
                session, rule.owner_id, entry
            )
            existing.title = entry.title
            existing.author_name = entry.author_name
            existing.url = entry.url
            existing.parser_version = parser_version
            existing.raw = dict(entry.raw)
            if existing.work_id is None and work_id is not None:
                existing.work_id = work_id
            if existing.series_id is None and series_id is not None:
                existing.series_id = series_id
            if not existing.match_evidence and evidence:
                existing.match_evidence = evidence
            await session.flush()
            return None
        work_id, series_id, evidence = await self._match_canonical(session, rule.owner_id, entry)
        observation = SourceObservationModel(
            owner_id=rule.owner_id,
            watch_rule_id=rule.id,
            adapter_id=rule.adapter_id,
            external_id=entry.external_id,
            title=entry.title,
            author_name=entry.author_name,
            url=entry.url,
            parser_version=parser_version,
            raw=dict(entry.raw),
            work_id=work_id,
            series_id=series_id,
            match_evidence=evidence,
        )
        session.add(observation)
        await session.flush()
        return observation

    async def _tracked_series_ids(self, session: AsyncSession, owner_id: UUID) -> set[UUID]:
        """Return canonical series with an enabled watch-backed metadata source."""
        return set(
            (
                await session.execute(
                    select(SourceLinkModel.entity_id)
                    .join(
                        SourceEndpointModel,
                        SourceEndpointModel.id == SourceLinkModel.source_endpoint_id,
                    )
                    .join(
                        WatchRuleModel,
                        WatchRuleModel.source_endpoint_id == SourceEndpointModel.id,
                    )
                    .where(
                        SourceLinkModel.owner_id == owner_id,
                        SourceLinkModel.entity_type == "series",
                        SourceLinkModel.role == "metadata",
                        SourceEndpointModel.enabled.is_(True),
                        WatchRuleModel.enabled.is_(True),
                    )
                    .distinct()
                )
            ).scalars()
        )

    async def _match_canonical(
        self, session: AsyncSession, owner_id: UUID, entry: Any
    ) -> tuple[UUID | None, UUID | None, dict[str, object]]:
        """Link only deterministic, owner-scoped matches; leave ambiguity unresolved."""
        title = normalize_title(entry.title)
        raw_series = str(entry.raw.get("series") or "").strip()
        series_candidates = []
        if raw_series:
            series_candidates = list(
                (
                    await session.execute(
                        select(SeriesModel).where(
                            SeriesModel.owner_id == owner_id,
                            SeriesModel.title_normalized == normalize_title(raw_series),
                        )
                    )
                ).scalars()
            )
        source_series_id = series_candidates[0].id if len(series_candidates) == 1 else None
        source_series_match = (
            "exact_title"
            if source_series_id is not None
            else "ambiguous"
            if series_candidates
            else "none"
        )
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
            candidates = author_candidates
        if len(candidates) != 1:
            return (
                None,
                source_series_id,
                {
                    "match": "ambiguous" if candidates else "none",
                    "title_normalized": title,
                    "series_match": source_series_match,
                },
            )
        work = candidates[0]
        memberships = list(
            (
                await session.execute(
                    select(SeriesMembershipModel.series_id).where(
                        SeriesMembershipModel.owner_id == owner_id,
                        SeriesMembershipModel.work_id == work.id,
                    ),
                )
            )
            .scalars()
            .all()
        )
        series_id = source_series_id or (memberships[0] if len(memberships) == 1 else None)
        return (
            work.id,
            series_id,
            {
                "match": "exact_title_author" if entry.author_name else "exact_title",
                "title_normalized": title,
                "series_match": (
                    "exact_title"
                    if source_series_id is not None
                    else "unique_membership"
                    if series_id
                    else "ambiguous_or_none"
                ),
            },
        )

    async def _record_failure(
        self,
        rule_id: UUID,
        owner_id: UUID,
        interval_seconds: int,
        error: str,
        started_at: float,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            rule = await session.get(WatchRuleModel, rule_id)
            if rule is None:
                return {"status": "error", "reason": "rule deleted"}
            rule.failure_count = (rule.failure_count or 0) + 1
            rule.last_error = error[:1000]
            rule.last_status = "error"
            rule.last_new_count = None
            rule.last_not_modified = None
            rule.last_duration_ms = round((monotonic() - started_at) * 1000)
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
