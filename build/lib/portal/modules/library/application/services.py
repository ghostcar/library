"""Catalog application service: canonical catalog use cases.

Owner scope is enforced here, not only in the UI (master prompt 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from portal.modules.library.application.ports import (
    AuthorRepositoryPort,
    SeriesRepositoryPort,
    WorkRepositoryPort,
)
from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import MembershipType, WorkAuthorRole
from portal.modules.library.domain.value_objects import SeriesIndex


@dataclass(slots=True)
class RegisterWorkInput:
    owner_id: UUID
    title: str
    author_names: list[str]
    language: str | None = None
    series_title: str | None = None
    series_index_raw: str | None = None
    series_membership_type: MembershipType = MembershipType.UNKNOWN


class CatalogService:
    """Registers canonical works, reusing existing authors/series by normalized name.

    Matching creates evidence, never silent merges: if an author/series with
    the same normalized name does not exist, a new one is created.
    """

    def __init__(
        self,
        works: WorkRepositoryPort,
        authors: AuthorRepositoryPort,
        series: SeriesRepositoryPort,
    ) -> None:
        self._works = works
        self._authors = authors
        self._series = series

    async def register_work(self, data: RegisterWorkInput) -> de.Work:
        # resolve/reuse authors first
        author_ids: list[UUID] = []
        for name in data.author_names:
            author = await self._authors.find_by_name(data.owner_id, name)
            if author is None:
                author = de.Author(owner_id=data.owner_id, name=name)
                await self._authors.add(author)
            author_ids.append(author.id)

        # reuse an existing work with the same normalized title AND a shared author;
        # title match alone is not enough (different books may share a title)
        candidates = await self._works.find_by_title(data.owner_id, data.title)
        for candidate in candidates:
            candidate_authors = {wa.author_id for wa in candidate.authors}
            if candidate_authors & set(author_ids):
                return candidate

        work = de.Work(owner_id=data.owner_id, title=data.title, language=data.language)
        for position, author_id in enumerate(author_ids):
            work.authors.append(
                de.WorkAuthor(author_id=author_id, role=WorkAuthorRole.AUTHOR, position=position),
            )
        await self._works.add(work)

        if data.series_title is not None:
            series = await self._series.find_by_title(data.owner_id, data.series_title)
            if series is None:
                series = de.Series(owner_id=data.owner_id, title=data.series_title)
                await self._series.add(series)
            membership = de.SeriesMembership(
                owner_id=data.owner_id,
                series_id=series.id,
                work_id=work.id,
                index=SeriesIndex.parse(data.series_index_raw or "unknown"),
                membership_type=data.series_membership_type,
            )
            await self._series.add_membership(membership)
        return work
