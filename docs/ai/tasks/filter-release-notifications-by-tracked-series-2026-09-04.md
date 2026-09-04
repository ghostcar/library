# TaskContext: filter release notifications by tracked series

**Date:** 2026-09-04
**Status:** `completed`
**Goal:** stop Author.Today author-catalog polls from notifying about publications
outside the canonical series the owner explicitly tracks.

## User contract

1. Author-level polling may continue to collect observations needed for discovery
   and source reconciliation.
2. A new Author.Today observation creates a release notification only when it is
   deterministically linked to a canonical series with an enabled watch-backed
   metadata source.
3. Explicit OPDS feed rules retain their existing feed-wide notification behavior.
4. No production deploy or mutation of existing user data is part of this task.

## Plan

- [x] Read project memory, relevant ADRs, monitoring code, and integration tests.
- [x] Implement the tracked-series notification boundary.
- [x] Add regression coverage for mixed tracked/untracked author releases.
- [x] Run focused and proportional full verification.
- [x] Update project memory with the verified result.

## Notes

- Root cause: `WatchService.poll_rule` currently creates `new_release` immediately
  for every inserted author-catalog observation; the already-computed
  `SourceObservation.series_id` is not used as a notification filter.
- Existing unrelated edits in `docs/ai/DEPLOYMENT_STATE.md`, `docs/ai/SESSIONS.md`,
  and two untracked TaskContext files are preserved.

## Result

- Author.Today `new_release` eligibility now requires the inserted observation's
  `series_id` to belong to the owner's enabled watch-backed canonical series.
- Untracked and unresolved entries remain persisted as observations without a
  notification; OPDS behavior remains feed-wide.
- Verification: focused integration 9 passed; full suite 300 passed;
  `scripts/lint.sh` green (Ruff, formatting, mypy).
- `OPEN_QUESTIONS.md` and `TECH_DEBT.md`: reviewed, no change required. No schema
  migration, production data mutation, commit, or deploy was performed.
