# TaskContext: canonical series tracking across coauthors

**Date:** 2026-09-01
**Status:** `completed`
**Goal:** make tracking a property of the canonical series rather than one author
card, preserve every confirmed author-page source, and safely discover coauthors.

## User contract

1. If a canonical series is already tracked through one author, every other
   catalog author must see it as tracked rather than being asked to enable the
   same series again.
2. When another connected author page confirms the same series, that endpoint is
   added as an additional metadata source of the existing series.
3. Coauthors may be linked or created only from stable source identity (profile
   URL/id plus name); name-only evidence must not create or merge author cards.
4. Existing owner data and source provenance remain intact; no production deploy
   is part of this task without a separate explicit request.

## Plan

- [x] Inspect current Author.Today work metadata for stable coauthor identity.
- [x] Define canonical-series tracked state and endpoint reconciliation.
- [x] Implement safe coauthor/source discovery supported by available metadata.
- [x] Update author-card UX and targeted tests.
- [x] Run relevant/full verification and update project memory.

## Notes

- Work starts on top of commit `ccd1a91`; its persistent SSR session fix is not
  deployed yet. Production remains `d61a484`, schema `0014`.

## Result

- Parser v3 extracts allowlisted Author.Today author profiles from each work.
- Manually preferred roots perform one-hop author discovery; auto-discovered
  sources never recurse. Conflicting stable identity is left unresolved.
- A canonical series is tracked globally when any enabled watch-backed endpoint
  links it. A confirming coauthor endpoint receives a second direct series link.
- Exact matched works receive missing confirmed `WorkAuthor` rows without
  replacing existing authors/order.
- Live public markup check: Sapfir page 1 contains 30 entries, declares 11 pages,
  and exposes 6 distinct stable author profiles.
- Verification: `scripts/test.sh` 299 passed; `scripts/lint.sh` green; focused
  source integration 12 passed. No DB migration, commit, or deploy performed.
- `OPEN_QUESTIONS.md` and `TECH_DEBT.md`: reviewed, no change required.
