# TaskContext: guided source onboarding and import assignment

**Date:** 2026-08-31
**Status:** `in_progress`
**Goal:** replace technical source/watch setup and UUID file assignment with a
catalog-first workflow.

## User contract

1. A book import creates/uses author and series cards from reliable metadata.
2. On an author card, adding an author page discovers series candidates; the
   user selects candidates to observe. Confirmation creates cards, links and
   watchers without exposing endpoint/link/rule internals.
3. A series card shows source books and a direct comparison with local catalog:
   present, missing locally, and ambiguous.
4. A manually added file is auto-matched when evidence is sufficient; otherwise
   its review offers a searchable list of existing books plus a clear create-new
   action, never a UUID field.

## Existing boundaries

- `SourceLink` and `WatchRule` already hold the underlying relationships but
  current UI exposes them as infrastructure.
- Author.Today adapter currently emits works, not series candidates. Generic
  source contracts need an explicit discovery capability and reviewable
  persisted candidates.
- Import inbox currently has `work_id` UUID assignment; replace it only after
  a catalog picker endpoint/form has integration coverage.

## Progress

- Import inbox now renders a catalog picker (title, authors, first series) for
  manual assignment; UUID input is removed. The existing owner-scoped assign
  route remains the enforcement point.
- Author card now has one-step Author.Today onboarding. It atomically creates or
  reuses endpoint/link/watch rule. Poll observations are grouped into series
  candidates; acceptance creates/reuses a series card, links its source and
  backfills matching observations with the canonical series id.
- Candidate acceptance is observation-backed: forged form values cannot create a
  series and the series URL is taken from persisted source evidence. Connected
  candidates become a stable `отслеживается` state instead of retaining an action.

## Series comparison checkpoint

- Implemented latest-per-source-work comparison on the series card. Revisions of
  the same external work are deduplicated; states are `present`, `missing`, and
  `ambiguous`.
- Exact owner-scoped source series titles now set `series_id` even when no local
  work matches, so future releases appear on the accepted series card.
- Next: add owner-confirmed reconciliation for a missing/ambiguous source work:
  choose an existing catalog work or explicitly create a new candidate/card. Do
  not auto-create from title-only evidence.
