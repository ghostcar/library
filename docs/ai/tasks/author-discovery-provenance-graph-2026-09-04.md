# TaskContext: author discovery provenance graph

**Date:** 2026-09-04
**Status:** `completed`
**Goal:** make Author.Today author discovery explainable: show which author source
led to which catalog author, through which observed books, and whether an author
was connected manually or has no reconstructable source provenance.

## User contract

1. Add an owner-scoped author provenance graph reachable from the author catalog.
2. Each discovery edge names the source author, discovered author, and deduplicated
   observed books that provide the relationship evidence.
3. Each author card summarizes its own incoming origin and outgoing discoveries.
4. Manual Author.Today roots and authors without reconstructable provenance are
   labeled explicitly; inference must not be presented as stored creation history.
5. Reconstruct the graph from existing stable source evidence; no schema migration,
   production mutation, commit, or deploy without a separate request.

## Plan

- [x] Read project memory, ADR-0023/0025, onboarding code, routes, templates, and tests.
- [x] Implement an owner-scoped provenance read model over source links/rules/observations.
- [x] Add the graph page and author-card provenance summary.
- [x] Add integration coverage for root → discovered author → evidence book.
- [x] Run focused/full verification and update project memory.

## Notes

- Existing evidence is sufficient for a derived graph: a preferred Author.Today
  author source identifies a manual root; its watch rule identifies observations;
  `raw.authors` carries stable child profile URLs; observation title/url/work_id
  identifies the evidence book.
- Historical entity creation itself was not logged. The UI therefore describes
  reconstructed source discovery and uses an explicit unknown state when no edge
  can be proven.
- Existing unrelated worktree changes are preserved.

## Result

- Added a fixed-query owner-scoped read model with manual roots, discovery edges,
  deduplicated evidence books, incoming/outgoing author views, and unknown origins.
- Added `/library/authors/graph`, linked it from `/library/authors`, and embedded the
  relevant provenance summary in every author card.
- Historical parser-v2 observations without stable author JSON are reconstructed
  only through a canonical coauthored work and a non-preferred Author.Today target;
  the UI labels that evidence as reconstructed.
- Verification: focused source/watch integration 13 passed; full suite 300 passed;
  `scripts/lint.sh` green (Ruff, formatting, mypy). `OPEN_QUESTIONS.md` and
  `TECH_DEBT.md` reviewed-no-change. No migration, production mutation, commit, or
  deploy was performed.
