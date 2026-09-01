# TaskContext: entity-title navigation

**Date:** 2026-09-01
**Status:** `complete`
**Goal:** make canonical entity names the consistent primary links to work,
author and series cards throughout the SSR portal.

## User contract

1. Clicking a canonical series title opens its series card, including series
   candidates shown on an author page.
2. Clicking a canonical author name opens the author card.
3. Clicking a canonical work title opens the work card.
4. Status chips such as «отслеживается» communicate state and are not the only or
   primary navigation target.
5. Names without an existing canonical card remain plain text; actions to create
   or reconcile them remain explicit.

## Plan

- [x] Inventory entity names/status links in all library templates and read models.
- [x] Add missing canonical IDs to read models where necessary.
- [x] Apply consistent accessible title-link markup across affected pages.
- [x] Add HTTP/browser regression coverage.
- [x] Run verification and update project memory.

## Result

- Catalog cards are no longer one outer anchor: work, each author and each series
  title navigate independently to their canonical cards.
- Author series candidates link through the series name when a canonical series
  exists; «отслеживается» / «есть карточка» are non-interactive status chips.
- Work detail, dashboard, reading queue, series list/detail and both catalog pickers
  use canonical name links. Source URLs remain separate explicit external links.
- Read models expose author references, series IDs and queue series IDs without
  changing persistence or the database schema.
- While compiling every template, an existing `notifications.html` `endif`/`endfor`
  defect was found and fixed.

## Verification

- `scripts/test.sh`: **299 passed**.
- `scripts/lint.sh`: Ruff check/format and mypy green (114 source files).
- `scripts/test-browser.sh`: desktop 1280×800 and mobile 390×844 green when run
  outside the filesystem sandbox (Chromium sandbox-host restriction).
- All Jinja templates compile; `git diff --check` is clean.

## Boundary

- Deployed 2026-09-01 as image `ghcr.io/ghostcar/library:f404df8`; schema remains
  `0014`. Rollback image is `98ae0ef`.
