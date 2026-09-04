# TaskContext: remove missing test asset rows

**Date:** 2026-09-01
**Status:** `complete`
**Goal:** remove exactly the two owner-confirmed test `assets` rows whose storage
objects are absent, without touching the six real original FB2 files.

## Safety plan

- [x] Resolve exact missing asset IDs from production DB + mounted storage.
- [x] Inspect every FK relationship and affected work/import state.
- [x] Create and validate a fresh pre-cleanup DB backup.
- [x] Delete only the resolved rows in one transaction with an exact count guard.
- [x] Verify six original assets/files/covers remain and portal health is green.
- [x] Record the operational result in project memory.

## Boundary

- User explicitly confirmed the two missing-file rows are test placeholders and
  authorized deletion.
- Do not delete or modify any storage object, work, author, series or book content.

## Result

- Fresh backup `backups/pre-cleanup/*-20260901-170016.*` was validated before
  mutation: DB gzip 171422 bytes, storage tar 15701004 bytes, schema `0014`.
- Deleted exactly two `stored_unmatched` import placeholders and their two
  unattached, non-preferred original asset rows in one guarded transaction:
  `71188d34-fa3b-4a66-b5eb-8c573960ca00` and
  `e5f07f51-442a-4e42-b3ef-816145b8b9e7`.
- No storage object, work, author, series, batch or book content was deleted.
  Both referenced storage objects were already absent.
- Post-check: deleted asset IDs and import placeholders are absent; six original
  asset rows remain, all six storage objects exist, and all six FB2 files expose
  a valid embedded cover.
- `library-web` remains Docker-healthy, `library-worker` running, and in-container
  `/healthz` / `/readyz` return `ok` / `ready`. Host-loopback curl is unavailable
  from the current restricted shell namespace and is not an application failure.
