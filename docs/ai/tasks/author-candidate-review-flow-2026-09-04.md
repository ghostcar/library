# TaskContext: author candidate review flow

**Date:** 2026-09-04
**Status:** `completed`
**Goal:** replace automatic coauthor/source/rule creation with an explicit,
evidence-first candidate review flow on the Authors page.

## User contract

1. Stable coauthor profiles found by a manually connected Author.Today source stay
   as derived candidates until the owner explicitly accepts them.
2. `/library/authors` has a distinct candidate section separate from canonical
   catalog authors.
3. Opening a candidate shows its focused provenance graph: parent authors and the
   exact observed books that produced the candidate.
4. Accepting a candidate explicitly creates or reuses the canonical author,
   connects the Author.Today endpoint, and enables its watch rule.
5. Existing automatically created authors/sources are not deleted or rewritten by
   this change; cleanup requires a separate explicit operation.

## Plan

- [x] Read project memory, ADR-0023/0025, current discovery/provenance code and tests.
- [x] Add a derived candidate read model and focused candidate provenance view.
- [x] Move coauthor materialization behind an owner-confirmed POST boundary.
- [x] Add the candidate section and accept action to the Authors UI.
- [x] Update regression tests and run focused/full verification.
- [x] Update project memory with the verified result.

## Notes

- Candidate identity is the validated Author.Today slug/profile URL already stored
  in `SourceObservation.raw.authors`; no new persistence is required for pending
  candidates.
- Existing non-preferred author source links remain canonical authors and therefore
  do not reappear as candidates.
- Existing unrelated worktree changes are preserved.

## Result

- Unknown stable coauthor profiles from preferred roots remain derived candidates;
  polling creates no author, endpoint, source link, watch rule, or WorkAuthor for them.
- The Authors page has a separate candidate section. Candidate clicks open a focused
  provenance graph; acceptance revalidates the owner-scoped candidate server-side,
  materializes its canonical/source records, and links evidence works.
- Accepted candidates remain non-preferred child sources, preserving bounded
  one-hop discovery. Existing auto-created data is untouched.
- A parser refresh now enriches already-deduplicated observations in place while
  preserving canonical links and producing neither a new-release count nor a
  notification. This makes repeat analysis useful for candidate discovery.
- Verification: focused source/watch integration 13 passed; full suite 300 passed;
  `scripts/lint.sh` green. `OPEN_QUESTIONS.md` and `TECH_DEBT.md` reviewed-no-change.
  No migration, production mutation, commit, or deploy was performed.
