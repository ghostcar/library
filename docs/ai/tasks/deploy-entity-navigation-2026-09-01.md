# TaskContext: deploy canonical entity-name navigation

**Date:** 2026-09-01
**Status:** `in_progress`
**Goal:** safely deploy the verified entity-name navigation candidate to the test
VPS production-shaped stack.

## Release input

- Current production image: `ghcr.io/ghostcar/library:98ae0ef`.
- Current schema: `0014`.
- Candidate verification: 299 tests, Ruff/format/mypy and Chromium desktop/mobile
  green; no database migration.
- Candidate changes are recorded in
  `tasks/entity-title-navigation-2026-09-01.md`.

## Plan

- [ ] Commit the verified candidate on `main`.
- [ ] Build and push immutable GHCR image tagged with the commit SHA.
- [ ] Create and validate a pre-deploy DB/storage backup.
- [ ] Confirm schema head and roll out web/worker with the pinned image.
- [ ] Run local, external, security, authenticated and log smoke checks.
- [ ] Update deployment memory and commit the deployment record.

## Rollback

- Image: `ghcr.io/ghostcar/library:98ae0ef`.
- Schema is compatible (`0014`, no migration). Do not automatically restore DB;
  use the new pre-deploy backup only if a data rollback is explicitly required.
