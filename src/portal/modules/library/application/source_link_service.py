"""Owner-scoped source links and inherited source selection."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.adapters.source_orm import SourceEndpointModel, SourceLinkModel
from portal.modules.library.infrastructure.orm import (
    AuthorModel,
    SeriesMembershipModel,
    SeriesModel,
    WorkAuthorModel,
    WorkModel,
)

ENTITY_TYPES = {"author", "series", "work"}
SOURCE_ROLES = {"metadata", "acquisition"}


class SourceLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def entity_exists(self, owner_id: UUID, entity_type: str, entity_id: UUID) -> bool:
        models = {"author": AuthorModel, "series": SeriesModel, "work": WorkModel}
        model = models.get(entity_type)
        if model is None:
            return False
        row = await self._session.get(model, entity_id)
        return row is not None and row.owner_id == owner_id

    async def add(
        self,
        owner_id: UUID,
        *,
        endpoint_id: UUID,
        entity_type: str,
        entity_id: UUID,
        role: str,
        external_url: str | None,
        external_id: str | None = None,
        preferred: bool = False,
        priority: int = 100,
    ) -> bool:
        clean_url = external_url.strip() if external_url else None
        if clean_url and urlparse(clean_url).scheme not in {"http", "https"}:
            return False
        endpoint = await self._session.get(SourceEndpointModel, endpoint_id)
        if (
            endpoint is None
            or endpoint.owner_id != owner_id
            or role not in SOURCE_ROLES
            or endpoint.role not in {role, "metadata+acquisition"}
            or not await self.entity_exists(owner_id, entity_type, entity_id)
        ):
            return False
        if preferred:
            await self._session.execute(
                update(SourceLinkModel)
                .where(
                    SourceLinkModel.owner_id == owner_id,
                    SourceLinkModel.entity_type == entity_type,
                    SourceLinkModel.entity_id == entity_id,
                    SourceLinkModel.role == role,
                )
                .values(is_preferred=False),
            )
        existing = (
            await self._session.execute(
                select(SourceLinkModel).where(
                    SourceLinkModel.source_endpoint_id == endpoint_id,
                    SourceLinkModel.entity_type == entity_type,
                    SourceLinkModel.entity_id == entity_id,
                    SourceLinkModel.role == role,
                    SourceLinkModel.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = SourceLinkModel(
                owner_id=owner_id,
                source_endpoint_id=endpoint_id,
                entity_type=entity_type,
                entity_id=entity_id,
                role=role,
                external_url=clean_url,
                external_id=external_id.strip() if external_id else None,
                is_preferred=preferred,
                priority=max(0, min(priority, 1000)),
            )
            self._session.add(existing)
        else:
            existing.external_url = clean_url
            existing.external_id = external_id.strip() if external_id else None
            existing.is_preferred = preferred
            existing.priority = max(0, min(priority, 1000))
        await self._session.flush()
        return True

    async def remove(self, owner_id: UUID, link_id: UUID) -> bool:
        result = await self._session.execute(
            delete(SourceLinkModel).where(
                SourceLinkModel.id == link_id,
                SourceLinkModel.owner_id == owner_id,
            ),
        )
        return bool(result.rowcount)

    async def prefer(self, owner_id: UUID, link_id: UUID) -> bool:
        link = await self._session.get(SourceLinkModel, link_id)
        if link is None or link.owner_id != owner_id:
            return False
        await self._session.execute(
            update(SourceLinkModel)
            .where(
                SourceLinkModel.owner_id == owner_id,
                SourceLinkModel.entity_type == link.entity_type,
                SourceLinkModel.entity_id == link.entity_id,
                SourceLinkModel.role == link.role,
            )
            .values(is_preferred=False),
        )
        link.is_preferred = True
        await self._session.flush()
        return True

    async def _direct(
        self, owner_id: UUID, entity_type: str, entity_ids: list[UUID], role: str
    ) -> list[tuple[SourceLinkModel, SourceEndpointModel]]:
        if not entity_ids:
            return []
        return list(
            (
                await self._session.execute(
                    select(SourceLinkModel, SourceEndpointModel)
                    .join(
                        SourceEndpointModel,
                        SourceEndpointModel.id == SourceLinkModel.source_endpoint_id,
                    )
                    .where(
                        SourceLinkModel.owner_id == owner_id,
                        SourceLinkModel.entity_type == entity_type,
                        SourceLinkModel.entity_id.in_(entity_ids),
                        SourceLinkModel.role == role,
                        SourceEndpointModel.enabled.is_(True),
                    )
                    .order_by(
                        SourceLinkModel.is_preferred.desc(),
                        SourceLinkModel.priority,
                        SourceEndpointModel.name,
                    ),
                )
            ).all()
        )

    async def resolved(
        self, owner_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[dict[str, Any]]:
        if not await self.entity_exists(owner_id, entity_type, entity_id):
            return []
        result: list[dict[str, Any]] = []
        for role in ("metadata", "acquisition"):
            levels: list[tuple[str, list[UUID]]] = [(entity_type, [entity_id])]
            if entity_type == "work":
                series_ids = list(
                    (
                        await self._session.execute(
                            select(SeriesMembershipModel.series_id).where(
                                SeriesMembershipModel.owner_id == owner_id,
                                SeriesMembershipModel.work_id == entity_id,
                            ),
                        )
                    ).scalars()
                )
                author_ids = list(
                    (
                        await self._session.execute(
                            select(WorkAuthorModel.author_id).where(
                                WorkAuthorModel.owner_id == owner_id,
                                WorkAuthorModel.work_id == entity_id,
                            ),
                        )
                    ).scalars()
                )
                levels.extend([("series", series_ids), ("author", author_ids)])
            elif entity_type == "series":
                author_ids = list(
                    (
                        await self._session.execute(
                            select(WorkAuthorModel.author_id)
                            .join(
                                SeriesMembershipModel,
                                SeriesMembershipModel.work_id == WorkAuthorModel.work_id,
                            )
                            .where(
                                WorkAuthorModel.owner_id == owner_id,
                                SeriesMembershipModel.owner_id == owner_id,
                                SeriesMembershipModel.series_id == entity_id,
                            )
                            .distinct()
                        )
                    ).scalars()
                )
                levels.append(("author", author_ids))
            rows: list[tuple[SourceLinkModel, SourceEndpointModel]] = []
            inherited_from = entity_type
            for kind, ids in levels:
                rows = await self._direct(owner_id, kind, ids, role)
                if rows:
                    inherited_from = kind
                    break
            if not rows:
                endpoints = list(
                    (
                        await self._session.execute(
                            select(SourceEndpointModel)
                            .where(
                                SourceEndpointModel.owner_id == owner_id,
                                SourceEndpointModel.enabled.is_(True),
                                SourceEndpointModel.role.in_([role, "metadata+acquisition"]),
                            )
                            .order_by(SourceEndpointModel.name),
                        )
                    ).scalars()
                )
                result.extend(
                    self._view(None, endpoint, role, "global", entity_type)
                    for endpoint in endpoints
                )
            else:
                result.extend(
                    self._view(link, endpoint, role, inherited_from, entity_type)
                    for link, endpoint in rows
                )
        return result

    @staticmethod
    def _view(
        link: SourceLinkModel | None,
        endpoint: SourceEndpointModel,
        role: str,
        inherited_from: str,
        requested_type: str,
    ) -> dict[str, Any]:
        return {
            "id": link.id if link else None,
            "endpoint_id": endpoint.id,
            "name": endpoint.name,
            "role": role,
            "url": (link.external_url if link else None) or endpoint.url,
            "preferred": bool(link and link.is_preferred),
            "inherited_from": inherited_from,
            "direct": link is not None and inherited_from == requested_type,
            "specific_url": bool(link and link.external_url),
        }
