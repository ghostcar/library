"""Policy engine (master prompt 8.5) and proposal application service.

Decision matrix:
- deterministic well-formed filename (phase 2) already auto-applies;
- LLM proposal with explicit candidate match + confidence >= threshold
  -> auto-apply;
- proposal without candidate match but with author+title -> create candidate
  entities (never silent merge into an unknown work) and mark for review;
- invalid/unavailable AI -> deterministic fallback (review);
- user correction always overrides the proposal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.modules.library.ai.digest import PROMPT_VERSION, CatalogCandidate, DigestBuilder
from portal.modules.library.ai.omniroute import AIUnavailableError, OmniRouteAdapter
from portal.modules.library.ai.orm import AICorrectionModel, AIProposalModel
from portal.modules.library.ai.proposal import (
    PROPOSAL_SCHEMA_VERSION,
    MatchProposal,
    digest_cache_key,
    proposal_to_dict,
    validate_proposal,
)
from portal.modules.library.application.filename_parser import parse_filename
from portal.modules.library.domain import import_entities as ie
from portal.modules.library.infrastructure.import_repositories import ImportItemRepository
from portal.modules.library.infrastructure.orm import AuthorModel, WorkAuthorModel, WorkModel

logger = logging.getLogger("library.ai")

AUTO_APPLY_CONFIDENCE = 0.85


class PolicyDecision:
    AUTO_APPLY = "auto_apply"
    REVIEW = "review"
    FALLBACK = "fallback"


@dataclass(slots=True)
class ProposalOutcome:
    decision: str  # PolicyDecision.*
    proposal: MatchProposal | None
    digest_hash: str | None
    cached: bool
    note: str


class PolicyEngine:
    @staticmethod
    def decide(
        proposal: MatchProposal,
        candidates: list[CatalogCandidate],
        *,
        ai_available: bool,
    ) -> str:
        candidate_ids = {str(c.work_id) for c in candidates}

        if proposal.match_existing_work_id:
            if proposal.match_existing_work_id in candidate_ids and (
                proposal.confidence >= AUTO_APPLY_CONFIDENCE and not proposal.requires_review
            ):
                return PolicyDecision.AUTO_APPLY
            return PolicyDecision.REVIEW

        if (
            proposal.author_names
            and proposal.title
            and proposal.confidence >= AUTO_APPLY_CONFIDENCE
        ):
            # new entities are created as candidates, never merged silently
            return PolicyDecision.REVIEW if proposal.requires_review else PolicyDecision.AUTO_APPLY

        if not ai_available:
            return PolicyDecision.FALLBACK
        return PolicyDecision.REVIEW


class ProposalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: OmniRouteAdapter,
        digest_builder: DigestBuilder | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._digest_builder = digest_builder or DigestBuilder()

    async def propose_for_item(self, owner_id: UUID, item_id: UUID) -> ProposalOutcome:
        """Build digest, consult cache/AI, validate, decide."""
        async with self._session_factory() as session, session.begin():
            items = ImportItemRepository(session)
            item = await items.get(owner_id, item_id)
            if item is None:
                msg = "import item not found"
                raise LookupError(msg)

            parsed = parse_filename(item.filename)
            candidates = await self._catalog_candidates(session, owner_id, parsed.title or "")
            digest = self._digest_builder.build(
                item.filename,
                parsed,
                candidates,
                detected_format=item.detected_format,
                warnings=[item.error] if item.error else None,
            )

        digest_hash = digest.digest_hash()
        cache_key = digest_cache_key(
            digest_hash,
            self._ai.model,
            PROMPT_VERSION,
            PROPOSAL_SCHEMA_VERSION,
        )

        cached = await self._cache_get(*cache_key)
        if cached is not None:
            proposal = validate_proposal(cached)
            if proposal is not None:
                decision = PolicyEngine.decide(
                    proposal,
                    digest.candidates,
                    ai_available=True,
                )
                return ProposalOutcome(
                    decision=decision,
                    proposal=proposal,
                    digest_hash=digest_hash,
                    cached=True,
                    note="from cache",
                )

        if not self._ai.is_configured() or not self._ai_enabled():
            return ProposalOutcome(
                decision=PolicyDecision.FALLBACK,
                proposal=None,
                digest_hash=digest_hash,
                cached=False,
                note="AI is not configured; deterministic review only",
            )

        try:
            response = await self._ai.complete(
                digest.truncated_for_model(self._max_input_chars()),
            )
        except AIUnavailableError as exc:
            logger.info("AI unavailable, falling back: %s", exc)
            return ProposalOutcome(
                decision=PolicyDecision.FALLBACK,
                proposal=None,
                digest_hash=digest_hash,
                cached=False,
                note=f"AI unavailable: {exc}",
            )

        proposal = validate_proposal(response.content)
        if proposal is None:
            return ProposalOutcome(
                decision=PolicyDecision.REVIEW,
                proposal=None,
                digest_hash=digest_hash,
                cached=False,
                note="invalid AI output; routed to review",
            )

        await self._cache_put(cache_key, proposal_to_dict(proposal), response.content)
        decision = PolicyEngine.decide(proposal, digest.candidates, ai_available=True)
        return ProposalOutcome(
            decision=decision,
            proposal=proposal,
            digest_hash=digest_hash,
            cached=False,
            note=f"decision={decision}",
        )

    async def apply_proposal(
        self,
        owner_id: UUID,
        item_id: UUID,
        proposal: MatchProposal,
        *,
        corrected: bool,
    ) -> UUID:
        """Apply an approved proposal: attach to existing work or create entities.

        Records the (possibly corrected) outcome for the evaluation dataset.
        """
        async with self._session_factory() as session, session.begin():
            items = ImportItemRepository(session)
            item = await items.get(owner_id, item_id)
            if item is None:
                msg = "import item not found"
                raise LookupError(msg)

            work_id: UUID | None = None
            if proposal.match_existing_work_id:
                work_id = UUID(proposal.match_existing_work_id)
            elif proposal.author_names and proposal.title:
                from portal.modules.library.application.services import (
                    CatalogService,
                    RegisterWorkInput,
                )
                from portal.modules.library.infrastructure.repositories import (
                    AuthorRepository,
                    SeriesRepository,
                    WorkRepository,
                )

                catalog = CatalogService(
                    works=WorkRepository(session),
                    authors=AuthorRepository(session),
                    series=SeriesRepository(session),
                )
                work = await catalog.register_work(
                    RegisterWorkInput(
                        owner_id=owner_id,
                        title=proposal.title,
                        author_names=proposal.author_names,
                        series_title=proposal.series,
                        series_index_raw=proposal.series_index_raw,
                    ),
                )
                work_id = work.id

            if item.asset_id is not None and work_id is not None:
                from portal.modules.library.infrastructure.repositories import AssetRepository

                await AssetRepository(session).update_work_link(
                    owner_id,
                    item.asset_id,
                    work_id,
                )

            item.status = ie.ItemStatus.MATCHED
            item.work_id = work_id
            item.match_evidence = {
                **item.match_evidence,
                "decision": "llm_proposal_applied",
                "corrected_by_user": corrected,
                "confidence": proposal.confidence,
            }
            await items.update(item)

            session.add(
                _correction_model(
                    owner_id=owner_id,
                    item_id=item.id,
                    digest_hash=None,
                    proposal=proposal_to_dict(proposal),
                    applied={
                        "work_id": str(work_id) if work_id else None,
                        "corrected": corrected,
                    },
                ),
            )
            return work_id or item.id

    async def auto_process_for_item(self, owner_id: UUID, item_id: UUID) -> ProposalOutcome:
        """Run one queued proposal; only policy-approved results mutate the catalog."""
        outcome = await self.propose_for_item(owner_id, item_id)
        if outcome.proposal is not None and outcome.decision == PolicyDecision.AUTO_APPLY:
            await self.apply_proposal(owner_id, item_id, outcome.proposal, corrected=False)
            return outcome

        async with self._session_factory() as session, session.begin():
            item = await ImportItemRepository(session).get(owner_id, item_id)
            if item is not None:
                item.match_evidence = {
                    **item.match_evidence,
                    "ai_status": "review_ready" if outcome.proposal else "unavailable",
                    "ai_note": outcome.note,
                    "ai_decision": outcome.decision,
                }
                await ImportItemRepository(session).update(item)
        return outcome

    # --- internals ---------------------------------------------------------

    def _ai_enabled(self) -> bool:
        from portal.core.config.config import get_settings

        return get_settings().ai_enabled

    def _max_input_chars(self) -> int:
        from portal.core.config.config import get_settings

        return get_settings().ai_max_input_chars

    async def _catalog_candidates(
        self,
        session: AsyncSession,
        owner_id: UUID,
        title_hint: str,
    ) -> list[CatalogCandidate]:
        """Lightweight candidate search: normalized title substring match."""
        if not title_hint.strip():
            return []
        stmt = (
            select(WorkModel)
            .where(
                WorkModel.owner_id == owner_id,
                WorkModel.title_normalized.ilike(f"%{title_hint.strip().casefold()[:60]}%"),
            )
            .limit(5)
        )
        work_rows = (await session.execute(stmt)).scalars().all()
        candidates: list[CatalogCandidate] = []
        for work in work_rows:
            author_rows = (
                (
                    await session.execute(
                        select(AuthorModel)
                        .join(WorkAuthorModel, WorkAuthorModel.author_id == AuthorModel.id)
                        .where(WorkAuthorModel.work_id == work.id),
                    )
                )
                .scalars()
                .all()
            )
            candidates.append(
                CatalogCandidate(
                    work_id=work.id,
                    title=work.title,
                    authors=[a.name for a in author_rows],
                ),
            )
        return candidates

    async def _cache_get(
        self, digest_hash: str, model: str, prompt_version: int, schema_version: int
    ) -> str | None:
        async with self._session_factory() as session:
            stmt = select(AIProposalModel.raw_response).where(
                AIProposalModel.digest_hash == digest_hash,
                AIProposalModel.model == model,
                AIProposalModel.prompt_version == prompt_version,
                AIProposalModel.schema_version == schema_version,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def _cache_put(
        self,
        key: tuple[str, str, int, int],
        proposal: dict[str, Any],
        raw_response: str,
    ) -> None:
        digest_hash, model, prompt_version, schema_version = key
        async with self._session_factory() as session, session.begin():
            await session.execute(
                insert(AIProposalModel)
                .values(
                    digest_hash=digest_hash,
                    model=model,
                    prompt_version=prompt_version,
                    schema_version=schema_version,
                    proposal=proposal,
                    raw_response=raw_response,
                )
                .on_conflict_do_nothing(
                    index_elements=["digest_hash", "model", "prompt_version", "schema_version"]
                )
            )


def _correction_model(
    *,
    owner_id: UUID,
    item_id: UUID | None,
    digest_hash: str | None,
    proposal: dict[str, Any],
    applied: dict[str, Any],
) -> AICorrectionModel:
    return AICorrectionModel(
        owner_id=owner_id,
        import_item_id=item_id,
        digest_hash=digest_hash,
        proposal=proposal,
        applied=applied,
        source="llm",
    )
