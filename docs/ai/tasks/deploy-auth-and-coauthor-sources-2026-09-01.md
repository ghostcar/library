# TaskContext: deploy persistent auth and coauthor source propagation

**Date:** 2026-09-01
**Status:** `completed`
**Goal:** deploy commit `98ae0ef` to the test-VPS production-shaped stack,
including pending auth commit `ccd1a91`, with backup and post-rollout validation.

## Plan

- [x] Verify clean Git state, current image/schema, deployment procedure and secrets presence.
- [x] Create and validate pre-deploy PostgreSQL/storage backup.
- [x] Build and publish immutable GHCR image `98ae0ef`.
- [x] Confirm schema compatibility/head and roll web/worker to the new image.
- [x] Verify health, readiness, auth continuation surface, worker and parser-v3 quiet baseline.
- [x] Update deployment memory and commit the operational record.

## Boundaries

- No schema migration is expected beyond already deployed `0014`.
- Do not expose `.env` values or user/book payloads in logs.
- Rollback image: `ghcr.io/ghostcar/library:d61a484`; database restore only from
  the new verified pre-deploy backup if data rollback becomes necessary.

## Result

- Image digest: `sha256:6281a53fb27e8495df9750a8afe92e1743d88054014622d1b60e33bd6fdb9e44`.
- Backup: `backups/pre-deploy/*-20260901-072728.*`, schema `0014`.
- Web/worker run `98ae0ef`; local/external health and ready are 200.
- Auth: `/library/` routes through `/auth/session`; no-cookie fallback preserves
  safe `next`, external `next` is rejected, response is `no-store`, 9 active
  refresh rows persisted through recreate.
- Source rollout: 19/19 AT rules v3/ok, zero active poll jobs/errors, notification
  count unchanged at 4. Aggregate graph after baseline: 20 authors, 19 AT
  endpoints, 13 series links, 1789 observations, 6 multi-source series.
- Authenticated service/authors pages return 200; both containers see 12 storage
  files; fresh logs contain no ERROR/Traceback/500.
