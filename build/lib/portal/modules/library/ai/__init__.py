"""AI-assisted matching: digest, proposal schema, OmniRoute adapter, policy."""

from __future__ import annotations

from portal.modules.library.ai.digest import CatalogCandidate, DigestBuilder, MatchDigest
from portal.modules.library.ai.omniroute import AIUnavailableError, OmniRouteAdapter
from portal.modules.library.ai.proposal import MatchProposal, validate_proposal
from portal.modules.library.ai.proposal_service import (
    PolicyDecision,
    PolicyEngine,
    ProposalOutcome,
    ProposalService,
)

__all__ = [
    "AIUnavailableError",
    "CatalogCandidate",
    "DigestBuilder",
    "MatchDigest",
    "MatchProposal",
    "OmniRouteAdapter",
    "PolicyDecision",
    "PolicyEngine",
    "ProposalOutcome",
    "ProposalService",
    "validate_proposal",
]
