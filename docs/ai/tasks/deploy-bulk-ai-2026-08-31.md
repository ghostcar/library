# TaskContext: deploy bulk AI import and continuation candidates

**Date:** 2026-08-31  
**Status:** `completed`  
**Goal:** deploy commits `84e8bed..949314d` to the test VPS, with backup,
migration `0013`, and smoke checks.

## Scope

- Build and publish immutable GHCR image from `949314d`.
- Back up production database and storage before any schema change.
- Upgrade Alembic `0012 → 0013`, start web and worker on the new image.
- Check health, SSR auth redirect, worker logs, and automated import queue.

## Safety

- No data deletion; rollback is previous image plus pre-deploy backup.
- `0013` is additive; bulk AI queue has no schema migration.

## Result

- Image `ghcr.io/ghostcar/library:949314d` published with digest
  `sha256:f2b2cd7e0a1f2369933411f39119d928b83a76d6fe2e3db554f154cc32e8c19e`.
- Pre-deploy backup `*-20260831-021217.*` validated; migration `0012 → 0013`
  applied before web/worker rollout.
- Both containers healthy. `/healthz` and `/readyz` return 200; anonymous
  `/library/` returns 303.
- Seven old unmatched imports were queued once; all jobs are `done`, and all
  items are `review_ready`. No `uq_ai_proposals_cache` error occurred.
