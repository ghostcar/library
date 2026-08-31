# TaskContext: source refresh, service console, Author.Today completeness

**Date:** 2026-08-31
**Status:** `completed`
**Goal:** make source polling observable and manually triggerable, add an
owner-only service console for background work, and correct incomplete
Author.Today discovery for large author catalogs.

## User contract

1. Connected author pages expose a safe `Проверить сейчас` action and clear
   queued/running/success/error/next-run state.
2. A service section shows background queues, status/counts, recent jobs and
   source checks without exposing secrets or another owner's data.
3. Author.Today discovery is validated against the current public works surface;
   Олег Сапфир is expected to expose about 309 works and 21 series rather than the
   22 entries returned by the current first-page parser.

## Boundaries

- External checks remain metadata-only: no auth, private API, chapters, covers,
  or acquisition.
- Manual refresh queues work; it does not block the web request on external HTTP.
- Owner scope, CSRF, cooldown/dedup and bounded external responses are required.
- Production deployment remains a separate explicit action.

## Plan

- [x] Reproduce and document Author.Today pagination/load contract with versioned fixtures.
- [x] Extend adapter for bounded complete public discovery and cover with tests.
- [x] Persist source check outcome fields needed by product UI.
- [x] Add manual refresh queueing and author/source status UI.
- [x] Add service console with owner-scoped queue/watch summaries and recent work.
- [x] Run migrations/tests/lint/browser checks; update project memory.

## Verification

- Live metadata fetch: Олег Сапфир — 309 publications (185 work + 124 audiobook),
  21 series, 11 bounded pages.
- `scripts/test.sh`: 296 passed, fresh schema head `0014`.
- `scripts/lint.sh`: Ruff/format and mypy green (114 source files).
- `scripts/test-browser.sh`: desktop 1280×800 and mobile 390×844 green.
- Production intentionally unchanged: image `00e6089`, schema `0013`.
