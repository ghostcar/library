# TaskContext: guided source onboarding and import assignment

**Date:** 2026-08-31
**Status:** `complete`
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

- Import inbox links to a dedicated owner-scoped catalog search (title, author,
  or series) for manual assignment. Results are filtered in SQL before the
  50-row limit; UUID input is removed from both inbox and proposal review. The
  existing assign route remains the enforcement point.
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
## Source work reconciliation checkpoint

- Implemented owner-scoped catalog picker for missing/ambiguous source works and
  a separate explicit `Создать карточку` action. No UUID input is exposed.
- Both actions link every stored revision of the same external work, ensure the
  work belongs to the accepted series, and add its direct metadata source link.
- Title-only evidence never creates a work without the owner's explicit action.
- Next product extension: replace the Author.Today-specific entry form with the
  same guided adapter/profile selection for supported configurable websites.

## Current slice: guided website profiles

- Introduce one product-level profile registry instead of hardcoding a site in
  the author template/route.
- Supported behavior must stay explicit: Author.Today is polled; a generic
  website may be stored as a metadata link without polling; disabled adapters
  retain their documented reason.
- Split the source settings presentation into OPDS and website sections after
  the author-card flow is covered by owner-scope integration tests.

## Guided website profiles checkpoint

- Implemented a single product profile registry: Author.Today=`watch`, generic
  website=`link`, Litnet=`disabled`. Generic links create no poll rule.
- Author links are owner+author scoped, so identical URLs on separate cards do
  not share a misleading endpoint identity.
- Source settings are now separate OPDS/site sections. OPDS one-step creates or
  reuses endpoint+rule; toggle/delete consistently controls both.
- Next automatic HTML profile is blocked on a concrete permitted site and its
  versioned parser fixture (`OPEN_QUESTIONS#12`). Next internal gate is the full
  regression/browser suite and a separate user-authorized deployment.

## Release gate checkpoint

- Full suite: 294 passed, including fresh migration to `0013`.
- Full Ruff format/check and mypy: green; Chromium desktop/mobile shell: green.
- Migration test drift and pre-existing formatter/typecheck debt discovered by
  the gate were corrected. Production remains unchanged pending an explicit
  deployment command.

## Searchable import assignment checkpoint

- Replaced the embedded 250-work select with a dedicated responsive assignment
  page: search existing catalog or explicitly start creation from file metadata.
- Search covers normalized work title, author name, and series title and is
  owner-scoped at query and assignment boundaries. The submitted work id is an
  internal hidden value; malformed or foreign values fail safely.
- Removed raw `match_existing_work_id` inputs from both AI proposal states. A
  user who recognizes an existing book follows the same catalog search.
- Verification: import integration 14 passed; full suite 294 passed; Ruff,
  formatter, mypy, and Chromium desktop/mobile shell are green.
- Production remains image `1f98181`, schema `0013`; deployment still requires
  a separate explicit user command.
