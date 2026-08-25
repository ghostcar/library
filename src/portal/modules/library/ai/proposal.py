"""LLM proposal schema: strict, validated, one repair attempt (master prompt 8.4).

The model returns a PROPOSAL, never a patch or an action plan. Invalid
output routes the task to review/fallback instead of failing the pipeline.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

PROPOSAL_SCHEMA_VERSION = 1

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class MatchProposal(BaseModel):
    """Structured match proposal for an unmatched book file."""

    author: str | None = Field(default=None, max_length=256)
    title: str | None = Field(default=None, max_length=512)
    series: str | None = Field(default=None, max_length=256)
    series_index_raw: str | None = Field(default=None, max_length=32)
    match_existing_work_id: str | None = Field(default=None, max_length=64)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_review: bool = True
    field_evidence: dict[str, str] = Field(default_factory=dict)
    ambiguities: list[str] = Field(default_factory=list)


def validate_proposal(raw: str) -> MatchProposal | None:
    """Parse and validate model output. One controlled JSON repair attempt.

    Returns None when the output is unusable even after repair — the caller
    must fall back to review (master prompt 8.4).
    """
    for candidate in _json_candidates(raw):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        try:
            return MatchProposal.model_validate(data)
        except ValidationError:
            continue
    return None


def _json_candidates(raw: str) -> list[str]:
    raw = raw.strip()
    candidates: list[str] = [raw]
    # repair attempt 1: extract the outermost JSON object from chatter/markdown
    match = _JSON_BLOCK.search(raw)
    if match:
        candidates.append(match.group(0))
    # repair attempt 2: strip markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    return candidates


def proposal_to_dict(proposal: MatchProposal) -> dict[str, Any]:
    return proposal.model_dump(mode="json")


def digest_cache_key(
    digest_hash: str,
    model: str,
    prompt_version: int,
    schema_version: int = PROPOSAL_SCHEMA_VERSION,
) -> tuple[str, str, int, int]:
    return (digest_hash, model, prompt_version, schema_version)
