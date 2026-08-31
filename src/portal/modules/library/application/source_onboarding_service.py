"""Catalog-first source onboarding for author and series cards."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.core.jobs.orm import JobModel, JobStatus
from portal.modules.library.adapters.author_today_adapter import normalize_author_works_url
from portal.modules.library.adapters.source_orm import (
    SourceEndpointModel,
    SourceLinkModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.application.services import CatalogService, RegisterWorkInput
from portal.modules.library.application.source_link_service import SourceLinkService
from portal.modules.library.application.source_profiles import get_author_source_profile
from portal.modules.library.domain import entities as de
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    SeriesModel,
)
from portal.modules.library.infrastructure.repositories import (
    AuthorRepository,
    SeriesRepository,
    WorkRepository,
)


class SourceOnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def connect_author_source(
        self,
        owner_id: UUID,
        author_id: UUID,
        profile_id: str,
        url: str,
    ) -> bool:
        profile = get_author_source_profile(profile_id)
        if profile is None or not profile.enabled:
            return False
        if profile.id == "author_today":
            return await self.connect_author_today(owner_id, author_id, url)
        if profile.id == "website_link":
            return await self.connect_author_website_link(owner_id, author_id, url)
        return False

    async def connect_author_website_link(self, owner_id: UUID, author_id: UUID, url: str) -> bool:
        author = await self._session.get(AuthorModel, author_id)
        target = url.strip()
        parsed = urlparse(target)
        if (
            author is None
            or author.owner_id != owner_id
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return False
        endpoint = (
            await self._session.execute(
                select(SourceEndpointModel)
                .join(
                    SourceLinkModel,
                    SourceLinkModel.source_endpoint_id == SourceEndpointModel.id,
                )
                .where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.adapter_id == "html",
                    SourceEndpointModel.url == target,
                    SourceLinkModel.entity_type == "author",
                    SourceLinkModel.entity_id == author_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if endpoint is None:
            endpoint = SourceEndpointModel(
                owner_id=owner_id,
                name=f"{parsed.hostname} · {author.name}",
                source_type="html",
                role="metadata",
                adapter_id="html",
                url=target,
            )
            self._session.add(endpoint)
            await self._session.flush()
        else:
            endpoint.enabled = True
        return await SourceLinkService(self._session).add(
            owner_id,
            endpoint_id=endpoint.id,
            entity_type="author",
            entity_id=author_id,
            role="metadata",
            external_url=target,
            preferred=False,
        )

    async def connect_author_today(self, owner_id: UUID, author_id: UUID, url: str) -> bool:
        author = await self._session.get(AuthorModel, author_id)
        if author is None or author.owner_id != owner_id:
            return False
        target = normalize_author_works_url(url)
        endpoint = (
            await self._session.execute(
                select(SourceEndpointModel)
                .join(
                    SourceLinkModel,
                    SourceLinkModel.source_endpoint_id == SourceEndpointModel.id,
                )
                .where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.adapter_id == "author_today",
                    SourceLinkModel.entity_type == "author",
                    SourceLinkModel.entity_id == author_id,
                    SourceLinkModel.role == "metadata",
                )
                .order_by(SourceEndpointModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if endpoint is None:
            endpoint = SourceEndpointModel(
                owner_id=owner_id,
                name=f"{author.name} · Author.Today",
                source_type="html",
                role="metadata",
                adapter_id="author_today",
                url=target,
            )
            self._session.add(endpoint)
            await self._session.flush()
        else:
            endpoint.name = f"{author.name} · Author.Today"
            endpoint.url = target
            endpoint.enabled = True
        linked = await SourceLinkService(self._session).add(
            owner_id,
            endpoint_id=endpoint.id,
            entity_type="author",
            entity_id=author_id,
            role="metadata",
            external_url=target,
            preferred=True,
        )
        if not linked:
            return False
        rule = (
            await self._session.execute(
                select(WatchRuleModel).where(
                    WatchRuleModel.owner_id == owner_id,
                    WatchRuleModel.source_endpoint_id == endpoint.id,
                    WatchRuleModel.adapter_id == "author_today",
                )
            )
        ).scalar_one_or_none()
        if rule is None:
            self._session.add(
                WatchRuleModel(
                    owner_id=owner_id,
                    adapter_id="author_today",
                    source_endpoint_id=endpoint.id,
                    name=author.name,
                    url=target,
                    interval_seconds=1800,
                    next_poll_at=datetime.now(UTC),
                )
            )
        else:
            rule.name = author.name
            rule.url = target
            rule.enabled = True
            rule.next_poll_at = datetime.now(UTC)
        return True

    async def author_today_status(
        self, owner_id: UUID, author_id: UUID
    ) -> dict[str, object] | None:
        row = (
            await self._session.execute(
                select(SourceEndpointModel, WatchRuleModel)
                .join(
                    SourceLinkModel,
                    SourceLinkModel.source_endpoint_id == SourceEndpointModel.id,
                )
                .outerjoin(
                    WatchRuleModel,
                    WatchRuleModel.source_endpoint_id == SourceEndpointModel.id,
                )
                .where(
                    SourceEndpointModel.owner_id == owner_id,
                    SourceEndpointModel.adapter_id == "author_today",
                    SourceLinkModel.entity_type == "author",
                    SourceLinkModel.entity_id == author_id,
                )
                .order_by(SourceEndpointModel.created_at.desc())
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            return None
        endpoint, rule = row
        job_status = None
        if rule is not None:
            job_status = (
                await self._session.execute(
                    select(JobModel.status)
                    .where(
                        JobModel.kind == "poll_watch",
                        JobModel.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                        JobModel.payload["owner_id"].astext == str(owner_id),
                        JobModel.payload["watch_rule_id"].astext == str(rule.id),
                    )
                    .order_by(JobModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        return {
            "url": endpoint.url,
            "enabled": endpoint.enabled and bool(rule and rule.enabled),
            "rule_id": rule.id if rule else None,
            "last_polled_at": rule.last_polled_at if rule else None,
            "next_poll_at": rule.next_poll_at if rule else None,
            "last_error": rule.last_error if rule else None,
            "last_status": rule.last_status if rule else None,
            "last_new_count": rule.last_new_count if rule else None,
            "last_not_modified": rule.last_not_modified if rule else None,
            "last_duration_ms": rule.last_duration_ms if rule else None,
            "job_status": job_status,
        }

    async def series_candidates(self, owner_id: UUID, author_id: UUID) -> list[dict[str, object]]:
        endpoint_ids = list(
            (
                await self._session.execute(
                    select(SourceLinkModel.source_endpoint_id).where(
                        SourceLinkModel.owner_id == owner_id,
                        SourceLinkModel.entity_type == "author",
                        SourceLinkModel.entity_id == author_id,
                        SourceLinkModel.role == "metadata",
                    )
                )
            ).scalars()
        )
        if not endpoint_ids:
            return []
        observations = list(
            (
                await self._session.execute(
                    select(SourceObservationModel, WatchRuleModel.source_endpoint_id)
                    .join(WatchRuleModel, WatchRuleModel.id == SourceObservationModel.watch_rule_id)
                    .where(
                        SourceObservationModel.owner_id == owner_id,
                        WatchRuleModel.source_endpoint_id.in_(endpoint_ids),
                    )
                )
            ).all()
        )
        grouped: dict[tuple[UUID, str], dict[str, object]] = {}
        observed_works: dict[tuple[UUID, str], set[str]] = {}
        repository = SeriesRepository(self._session)
        for observation, endpoint_id in observations:
            if endpoint_id is None:
                continue
            name = str(observation.raw.get("series") or "").strip()
            if not name:
                continue
            key = (endpoint_id, name.casefold())
            candidate = grouped.setdefault(
                key,
                {
                    "endpoint_id": key[0],
                    "name": name,
                    "url": observation.raw.get("series_url"),
                    "work_count": 0,
                    "existing_series_id": None,
                    "connected": False,
                },
            )
            work_key = self._observation_work_key(observation)
            seen = observed_works.setdefault(key, set())
            if work_key not in seen:
                seen.add(work_key)
                candidate["work_count"] = cast("int", candidate["work_count"]) + 1
            existing = await repository.find_by_title(owner_id, name)
            candidate["existing_series_id"] = existing.id if existing else None
            if existing is not None:
                candidate["connected"] = (
                    await self._session.execute(
                        select(SourceLinkModel.id).where(
                            SourceLinkModel.owner_id == owner_id,
                            SourceLinkModel.source_endpoint_id == endpoint_id,
                            SourceLinkModel.entity_type == "series",
                            SourceLinkModel.entity_id == existing.id,
                            SourceLinkModel.role == "metadata",
                        )
                    )
                ).scalar_one_or_none() is not None
        return sorted(grouped.values(), key=lambda item: str(item["name"]).casefold())

    async def accept_series(
        self, owner_id: UUID, author_id: UUID, endpoint_id: UUID, name: str
    ) -> UUID | None:
        owns_endpoint = (
            await self._session.execute(
                select(SourceLinkModel.id).where(
                    SourceLinkModel.owner_id == owner_id,
                    SourceLinkModel.source_endpoint_id == endpoint_id,
                    SourceLinkModel.entity_type == "author",
                    SourceLinkModel.entity_id == author_id,
                )
            )
        ).scalar_one_or_none()
        clean_name = name.strip()
        if owns_endpoint is None or not clean_name:
            return None
        observations = list(
            (
                await self._session.execute(
                    select(SourceObservationModel)
                    .join(WatchRuleModel, WatchRuleModel.id == SourceObservationModel.watch_rule_id)
                    .where(
                        SourceObservationModel.owner_id == owner_id,
                        WatchRuleModel.source_endpoint_id == endpoint_id,
                    )
                )
            ).scalars()
        )
        matching = [
            observation
            for observation in observations
            if str(observation.raw.get("series") or "").strip().casefold() == clean_name.casefold()
        ]
        if not matching:
            return None
        discovered_url = next(
            (
                str(observation.raw["series_url"])
                for observation in matching
                if observation.raw.get("series_url")
            ),
            None,
        )
        repository = SeriesRepository(self._session)
        series = await repository.find_by_title(owner_id, clean_name)
        if series is None:
            series = await repository.add(de.Series(owner_id=owner_id, title=clean_name))
        await SourceLinkService(self._session).add(
            owner_id,
            endpoint_id=endpoint_id,
            entity_type="series",
            entity_id=series.id,
            role="metadata",
            external_url=discovered_url,
            preferred=True,
        )
        for observation in matching:
            observation.series_id = series.id
        return series.id

    async def reconcile_source_work(
        self,
        owner_id: UUID,
        series_id: UUID,
        observation_id: UUID,
        *,
        decision: str,
        work_id: UUID | None = None,
    ) -> UUID | None:
        series = await self._session.get(SeriesModel, series_id)
        observation = await self._session.get(SourceObservationModel, observation_id)
        if (
            series is None
            or series.owner_id != owner_id
            or observation is None
            or observation.owner_id != owner_id
            or observation.series_id != series_id
        ):
            return None

        works = WorkRepository(self._session)
        if decision == "assign" and work_id is not None:
            work = await works.get(owner_id, work_id)
            if work is None:
                return None
        elif decision == "create":
            work = await CatalogService(
                works,
                AuthorRepository(self._session),
                SeriesRepository(self._session),
            ).register_work(
                RegisterWorkInput(
                    owner_id=owner_id,
                    title=observation.title,
                    author_names=[observation.author_name] if observation.author_name else [],
                    series_title=series.title,
                )
            )
        else:
            return None

        membership_exists = (
            await self._session.execute(
                select(SeriesMembershipModel.id).where(
                    SeriesMembershipModel.owner_id == owner_id,
                    SeriesMembershipModel.series_id == series_id,
                    SeriesMembershipModel.work_id == work.id,
                )
            )
        ).scalar_one_or_none()
        if membership_exists is None:
            self._session.add(
                SeriesMembershipModel(
                    owner_id=owner_id,
                    series_id=series_id,
                    work_id=work.id,
                    index_raw="unknown",
                    index_sort=None,
                    membership_type="unknown",
                )
            )

        source_key = self._observation_work_key(observation)
        revisions = list(
            (
                await self._session.execute(
                    select(SourceObservationModel).where(
                        SourceObservationModel.owner_id == owner_id,
                        SourceObservationModel.watch_rule_id == observation.watch_rule_id,
                        SourceObservationModel.adapter_id == observation.adapter_id,
                    )
                )
            ).scalars()
        )
        for revision in revisions:
            if self._observation_work_key(revision) != source_key:
                continue
            revision.work_id = work.id
            revision.series_id = series_id
            revision.match_evidence = {
                **revision.match_evidence,
                "match": "manual",
                "decision": f"source_review_{decision}",
            }

        endpoint_id = (
            await self._session.execute(
                select(WatchRuleModel.source_endpoint_id).where(
                    WatchRuleModel.id == observation.watch_rule_id,
                    WatchRuleModel.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if endpoint_id is not None:
            await SourceLinkService(self._session).add(
                owner_id,
                endpoint_id=endpoint_id,
                entity_type="work",
                entity_id=work.id,
                role="metadata",
                external_url=observation.url,
                external_id=self._observation_work_key(observation),
                preferred=True,
            )
        await self._session.flush()
        return work.id

    @staticmethod
    def _observation_work_key(observation: SourceObservationModel) -> str:
        publication_kind = str(observation.raw.get("publication_kind") or "work")
        identity = str(
            observation.raw.get("work_id")
            or observation.url
            or f"{observation.title}\0{observation.author_name or ''}"
        )
        return f"{publication_kind}:{identity}"
