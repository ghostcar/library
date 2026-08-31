"""Deterministic digest builder (master prompt 8.3).

The digest contains metadata and catalog candidates ONLY — never book text.
Book text and source HTML are untrusted data and are not sent to the model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from portal.modules.library.ai.proposal import PROPOSAL_SCHEMA_VERSION
from portal.modules.library.application.filename_parser import ParsedFilename

PROMPT_VERSION = 2


@dataclass(slots=True)
class CatalogCandidate:
    work_id: UUID
    title: str
    authors: list[str] = field(default_factory=list)
    series: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": str(self.work_id),
            "title": self.title,
            "authors": self.authors,
            "series": self.series,
        }


@dataclass(slots=True)
class MatchDigest:
    filename: str
    parsed: dict[str, Any]
    candidates: list[CatalogCandidate]
    format: str | None = None
    embedded_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "filename": self.filename,
            "parsed_filename": self.parsed,
            "format": self.format,
            "embedded_metadata": self.embedded_metadata,
            "warnings": self.warnings,
            "catalog_candidates": [c.to_dict() for c in self.candidates],
        }
        return json.dumps(payload, ensure_ascii=False, indent=1)

    def digest_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def truncated_for_model(self, max_chars: int) -> str:
        """Hard cap on what we send; candidates are trimmed first, never silently."""
        payload_json = self.to_json()
        if len(payload_json) <= max_chars:
            return payload_json
        trimmed = MatchDigest(
            filename=self.filename,
            parsed=self.parsed,
            candidates=self.candidates[:3],
            format=self.format,
            warnings=[*self.warnings, "candidates_truncated_for_size"],
        )
        return trimmed.to_json()


class DigestBuilder:
    """Builds a MatchDigest for an import item from deterministic data."""

    def __init__(self, max_candidates: int = 8) -> None:
        self._max_candidates = max_candidates

    def build(
        self,
        filename: str,
        parsed: ParsedFilename,
        candidates: list[CatalogCandidate],
        *,
        detected_format: str | None = None,
        embedded_metadata: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> MatchDigest:
        return MatchDigest(
            filename=filename,
            parsed={
                "author": parsed.author,
                "title": parsed.title,
                "series": parsed.series,
                "series_index": str(parsed.series_index) if parsed.series_index else None,
                "well_formed": parsed.is_well_formed,
            },
            candidates=candidates[: self._max_candidates],
            format=detected_format,
            embedded_metadata=embedded_metadata or {},
            warnings=warnings or [],
        )
