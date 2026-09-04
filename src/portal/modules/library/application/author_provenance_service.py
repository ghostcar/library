"""Derived, owner-scoped provenance graph for Author.Today author discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.adapters.author_today_adapter import (
    AuthorTodayParseError,
    normalize_author_works_url,
)
from portal.modules.library.adapters.source_orm import (
    SourceEndpointModel,
    SourceLinkModel,
    SourceObservationModel,
    WatchRuleModel,
)
from portal.modules.library.infrastructure.orm import AuthorModel, WorkAuthorModel


@dataclass(frozen=True)
class ProvenanceBook:
    title: str
    source_url: str | None
    work_id: UUID | None
    direct_profile_evidence: bool


@dataclass
class AuthorDiscoveryEdge:
    source_author_id: UUID
    source_author_name: str
    target_author_id: UUID
    target_author_name: str
    target_manually_connected: bool
    books: list[ProvenanceBook] = field(default_factory=list)


@dataclass
class AuthorProvenance:
    author_id: UUID
    author_name: str
    source_url: str | None = None
    manually_connected: bool = False
    incoming: list[AuthorDiscoveryEdge] = field(default_factory=list)
    outgoing: list[AuthorDiscoveryEdge] = field(default_factory=list)


@dataclass
class CandidateDiscoveryEdge:
    source_author_id: UUID
    source_author_name: str
    books: list[ProvenanceBook] = field(default_factory=list)


@dataclass
class AuthorCandidate:
    slug: str
    name: str
    source_url: str
    incoming: list[CandidateDiscoveryEdge] = field(default_factory=list)


@dataclass(frozen=True)
class AuthorDiscoveryGraph:
    authors: list[AuthorProvenance]
    edges: list[AuthorDiscoveryEdge]
    manual_roots: list[AuthorProvenance]
    unattributed: list[AuthorProvenance]
    candidates: list[AuthorCandidate]


class AuthorProvenanceService:
    """Reconstruct discovery paths from stable source identities and observations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def graph(self, owner_id: UUID) -> AuthorDiscoveryGraph:
        authors = list(
            (
                await self._session.execute(
                    select(AuthorModel)
                    .where(AuthorModel.owner_id == owner_id)
                    .order_by(AuthorModel.name_normalized, AuthorModel.id)
                )
            ).scalars()
        )
        nodes = {
            author.id: AuthorProvenance(author_id=author.id, author_name=author.name)
            for author in authors
        }
        source_rows = list(
            (
                await self._session.execute(
                    select(SourceLinkModel, SourceEndpointModel)
                    .join(
                        SourceEndpointModel,
                        SourceEndpointModel.id == SourceLinkModel.source_endpoint_id,
                    )
                    .where(
                        SourceLinkModel.owner_id == owner_id,
                        SourceLinkModel.entity_type == "author",
                        SourceLinkModel.role == "metadata",
                        SourceEndpointModel.owner_id == owner_id,
                        SourceEndpointModel.adapter_id == "author_today",
                    )
                )
            ).all()
        )
        endpoint_author: dict[UUID, UUID] = {}
        author_by_source_url: dict[str, UUID] = {}
        preferred_endpoint_ids: set[UUID] = set()
        for link, endpoint in source_rows:
            node = nodes.get(link.entity_id)
            if node is None:
                continue
            endpoint_author[endpoint.id] = node.author_id
            author_by_source_url[endpoint.url] = node.author_id
            if node.source_url is None or link.is_preferred:
                node.source_url = endpoint.url
            if link.is_preferred:
                node.manually_connected = True
                preferred_endpoint_ids.add(endpoint.id)

        observation_rows = list(
            (
                await self._session.execute(
                    select(SourceObservationModel, WatchRuleModel.source_endpoint_id)
                    .join(
                        WatchRuleModel,
                        WatchRuleModel.id == SourceObservationModel.watch_rule_id,
                    )
                    .where(
                        SourceObservationModel.owner_id == owner_id,
                        SourceObservationModel.adapter_id == "author_today",
                    )
                    .order_by(SourceObservationModel.observed_at, SourceObservationModel.id)
                )
            ).all()
        )
        observed_work_ids = {
            observation.work_id
            for observation, endpoint_id in observation_rows
            if endpoint_id in preferred_endpoint_ids and observation.work_id is not None
        }
        work_authors: dict[UUID, set[UUID]] = {}
        if observed_work_ids:
            work_author_rows = (
                await self._session.execute(
                    select(WorkAuthorModel.work_id, WorkAuthorModel.author_id).where(
                        WorkAuthorModel.owner_id == owner_id,
                        WorkAuthorModel.work_id.in_(observed_work_ids),
                    )
                )
            ).all()
            for work_id, author_id in work_author_rows:
                work_authors.setdefault(work_id, set()).add(author_id)
        edge_books: dict[tuple[UUID, UUID], dict[str, ProvenanceBook]] = {}
        candidate_names: dict[str, str] = {}
        candidate_books: dict[tuple[str, UUID], dict[str, ProvenanceBook]] = {}
        for observation, endpoint_id in observation_rows:
            if endpoint_id is None or endpoint_id not in preferred_endpoint_ids:
                continue
            source_author_id = endpoint_author.get(endpoint_id)
            if source_author_id is None:
                continue
            identities = self._author_identities(observation.raw)
            direct_target_ids = {
                author_by_source_url[profile_url]
                for _name, profile_url in identities
                if profile_url in author_by_source_url
            }
            for name, profile_url in identities:
                if profile_url in author_by_source_url:
                    continue
                candidate_names.setdefault(profile_url, name)
                books = candidate_books.setdefault((profile_url, source_author_id), {})
                books.setdefault(
                    self._book_key(observation),
                    ProvenanceBook(
                        title=observation.title,
                        source_url=observation.url,
                        work_id=observation.work_id,
                        direct_profile_evidence=True,
                    ),
                )
            target_author_ids = set(direct_target_ids)
            if observation.work_id is not None:
                target_author_ids.update(
                    author_id
                    for author_id in work_authors.get(observation.work_id, set())
                    if author_id in nodes and not nodes[author_id].manually_connected
                )
            for target_author_id in target_author_ids:
                if target_author_id == source_author_id:
                    continue
                key = (source_author_id, target_author_id)
                books = edge_books.setdefault(key, {})
                books.setdefault(
                    self._book_key(observation),
                    ProvenanceBook(
                        title=observation.title,
                        source_url=observation.url,
                        work_id=observation.work_id,
                        direct_profile_evidence=target_author_id in direct_target_ids,
                    ),
                )

        edges: list[AuthorDiscoveryEdge] = []
        for (source_id, target_id), books_by_key in edge_books.items():
            source = nodes[source_id]
            target = nodes[target_id]
            edge = AuthorDiscoveryEdge(
                source_author_id=source_id,
                source_author_name=source.author_name,
                target_author_id=target_id,
                target_author_name=target.author_name,
                target_manually_connected=target.manually_connected,
                books=sorted(books_by_key.values(), key=lambda book: book.title.casefold()),
            )
            source.outgoing.append(edge)
            target.incoming.append(edge)
            edges.append(edge)

        edges.sort(
            key=lambda edge: (
                edge.source_author_name.casefold(),
                edge.target_author_name.casefold(),
            )
        )
        author_list = list(nodes.values())
        for node in author_list:
            node.incoming.sort(key=lambda edge: edge.source_author_name.casefold())
            node.outgoing.sort(key=lambda edge: edge.target_author_name.casefold())
        candidates_by_url: dict[str, AuthorCandidate] = {
            url: AuthorCandidate(
                slug=self._profile_slug(url),
                name=name,
                source_url=url,
            )
            for url, name in candidate_names.items()
        }
        for (url, source_author_id), books_by_key in candidate_books.items():
            source = nodes[source_author_id]
            candidates_by_url[url].incoming.append(
                CandidateDiscoveryEdge(
                    source_author_id=source_author_id,
                    source_author_name=source.author_name,
                    books=sorted(books_by_key.values(), key=lambda book: book.title.casefold()),
                )
            )
        candidates = sorted(candidates_by_url.values(), key=lambda item: item.name.casefold())
        for candidate in candidates:
            candidate.incoming.sort(key=lambda edge: edge.source_author_name.casefold())
        return AuthorDiscoveryGraph(
            authors=author_list,
            edges=edges,
            manual_roots=[node for node in author_list if node.manually_connected],
            unattributed=[
                node for node in author_list if not node.manually_connected and not node.incoming
            ],
            candidates=candidates,
        )

    async def accept_candidate(self, owner_id: UUID, slug: str) -> UUID | None:
        candidate = next(
            (
                candidate
                for candidate in (await self.graph(owner_id)).candidates
                if candidate.slug == slug
            ),
            None,
        )
        if candidate is None:
            return None
        from portal.modules.library.application.source_onboarding_service import (
            SourceOnboardingService,
        )

        author_id = await SourceOnboardingService(self._session).accept_author_today_candidate(
            owner_id,
            candidate.name,
            candidate.source_url,
        )
        if author_id is None:
            return None
        work_ids = {
            book.work_id
            for edge in candidate.incoming
            for book in edge.books
            if book.work_id is not None
        }
        if not work_ids:
            return author_id
        existing_work_ids = set(
            (
                await self._session.execute(
                    select(WorkAuthorModel.work_id).where(
                        WorkAuthorModel.owner_id == owner_id,
                        WorkAuthorModel.author_id == author_id,
                        WorkAuthorModel.work_id.in_(work_ids),
                    )
                )
            ).scalars()
        )
        position_rows = (
            await self._session.execute(
                select(WorkAuthorModel.work_id, WorkAuthorModel.position).where(
                    WorkAuthorModel.owner_id == owner_id,
                    WorkAuthorModel.work_id.in_(work_ids),
                )
            )
        ).all()
        next_positions: dict[UUID, int] = {}
        for work_id, position in position_rows:
            next_positions[work_id] = max(next_positions.get(work_id, 0), position + 1)
        for work_id in work_ids - existing_work_ids:
            self._session.add(
                WorkAuthorModel(
                    owner_id=owner_id,
                    work_id=work_id,
                    author_id=author_id,
                    role="author",
                    position=next_positions.get(work_id, 0),
                )
            )
        await self._session.flush()
        return author_id

    @staticmethod
    def _author_identities(raw: object) -> list[tuple[str, str]]:
        if not isinstance(raw, dict):
            return []
        values = raw.get("authors")
        if not isinstance(values, list):
            return []
        identities: list[tuple[str, str]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            name = str(value.get("name") or "").strip()
            try:
                url = normalize_author_works_url(str(value.get("url") or ""))
            except AuthorTodayParseError:
                continue
            if name and (name, url) not in identities:
                identities.append((name, url))
        return identities

    @staticmethod
    def _book_key(observation: SourceObservationModel) -> str:
        raw = observation.raw if isinstance(observation.raw, dict) else {}
        source_id = str(raw.get("work_id") or "").strip()
        publication_kind = str(raw.get("publication_kind") or "work").strip()
        if source_id:
            return f"{publication_kind}:{source_id}"
        return observation.url or observation.title.casefold()

    @staticmethod
    def _profile_slug(url: str) -> str:
        return url.removeprefix("https://author.today/u/").removesuffix("/works")
