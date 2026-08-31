# TaskContext: searchable series source reconciliation

**Date:** 2026-08-31
**Status:** `complete`
**Goal:** replace the bounded catalog select on discovered series books with an
owner-scoped searchable assignment flow.

## Contract

- The series card keeps its source/catalog comparison and explicit create action.
- Missing or ambiguous source books link to a dedicated search by title, author,
  or series; catalog filtering happens before the result limit.
- The selected work id remains internal and is validated by the existing
  owner-scoped reconciliation service.
- No UUID field or long embedded catalog select appears in the UI.

## Verification plan

- Extend source onboarding integration coverage through search and assignment.
- Run full Ruff/mypy and relevant integration tests; update canonical memory.

## Result

- Series source entries now expose `Найти в каталоге` and a separate explicit
  create action; the 250-work select and its page-load catalog query are gone.
- The dedicated screen searches normalized title/author/series, initially using
  the source title, and displays at most 50 owner-scoped results.
- Existing reconciliation remains the single write boundary for owner, series,
  observation, and selected-work validation.
- Verification: source integration 4 passed; full Ruff/format/mypy green. The
  immediately preceding full project gate remains 294 passed and Chromium
  desktop/mobile green.
- Production remains image `1f98181`, schema `0013`.
