# TaskContext: deploy canonical entity-name navigation

**Date:** 2026-09-01
**Status:** `complete`
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

- [x] Commit the verified candidate on `main`.
- [x] Build and push immutable GHCR image tagged with the commit SHA.
- [x] Create and validate a pre-deploy DB/storage backup.
- [x] Confirm schema head and roll out web/worker with the pinned image.
- [x] Run local, external, security, authenticated and log smoke checks.
- [x] Update deployment memory and commit the deployment record.

## Result

- Release: `f404df8`.
- Image: `ghcr.io/ghostcar/library:f404df8`.
- Digest: `sha256:3292445c1810a598bbb84f3bc72e7a9c8a586021ff66ff3932060335afce73ef`.
- Backup: `backups/pre-deploy/*-20260901-084428.*` (DB 156674 bytes,
  storage 15701004 bytes, schema `0014`).
- Web healthy, worker running, both on the release digest with persistent storage.
- Local/external and authenticated smoke green. Production catalog contains 7 work,
  13 author and 7 series entity links; four tracked author pages have status spans
  and zero status anchors.
- Active refresh sessions 9→9; jobs 0→0; unread notifications 4→4; watch errors 0.
- Fresh logs contain no application errors.

## Rollback

- Image: `ghcr.io/ghostcar/library:98ae0ef`.
- Schema is compatible (`0014`, no migration). Do not automatically restore DB;
  use the new pre-deploy backup only if a data rollback is explicitly required.
