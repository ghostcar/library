# TaskContext: bulk AI import and co-authors

**Date:** 2026-08-31  
**Status:** `completed_not_deployed`  
**Goal:** repair failed repeated AI proposals, enqueue analysis for every newly
unmatched imported asset, and preserve multiple authors in proposal/apply flow.

## Evidence

- Live logs show `uq_ai_proposals_cache` duplicate-key failures from repeated
  `propose_for_item()` calls, causing browser 500 responses.
- Newly uploaded FB2 files only emit `BookFileImported`; no proposal job exists.
- The catalogue supports multiple `WorkAuthor` records, but AI schema and form
  currently carry one `author` string.

## Acceptance criteria

1. Proposal cache insert is idempotent under repeat/concurrency.
2. Every newly unmatched import enqueues one background proposal job; existing
   unmatched items have a one-click batch enqueue; automatic application remains
   policy-gated and review is never silently applied.
3. Proposal contract, UI and application preserve ordered co-authors.
4. Existing single-author cache/forms remain compatible; tests cover the flow.

## Result

- Live diagnostic: duplicate `uq_ai_proposals_cache` caused the observed 500 on
  repeated manual proposal. PostgreSQL conflict-safe cache insert fixes this.
- Newly unmatched imports enqueue `propose_import`; worker auto-applies only the
  existing high-confidence policy and records other results for review.
- The import inbox offers one `Разобрать всё` action for unmatched items created
  before this change; it skips already queued/reviewed items.
- `authors[]` preserves ordered co-authors while legacy singular `author` cache
  rows/forms remain valid. Catalog receives separate WorkAuthor links.
- Checks: Ruff/mypy clean; 16 unit tests and 10 AI integration tests passed.
