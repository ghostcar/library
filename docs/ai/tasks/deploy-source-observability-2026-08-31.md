# TaskContext: deploy source observability release

**Date:** 2026-08-31  
**Status:** `completed`  
**Commit:** `d61a484`  
**From:** image `00e6089`, schema `0013`  
**Target:** image `d61a484`, schema `0014`

## Plan

- [x] Verify clean code worktree, running stack and current schema/log health.
- [x] Build and publish immutable GHCR image `d61a484`.
- [x] Create and validate pre-deploy database/storage backup.
- [x] Apply migration `0014` with the new image before switching services.
- [x] Roll out web and worker; verify containers, schema and packaged assets.
- [x] Run local/external/auth/service/parser-backfill smoke and inspect logs.
- [x] Update project memory with exact artifacts and rollback instructions.

## Rollback boundary

- Previous image: `ghcr.io/ghostcar/library:00e6089`.
- Schema downgrade is not automatic. Restore the validated pre-deploy backup if
  a database rollback is required.

## Result

- Image digest: `sha256:4116cad0322726f80cbf0902166699723fe74207c5df419bda048ec74f9610d2`.
- Backup: `backups/pre-deploy/*-20260831-232648.*`, source schema `0013`.
- Current production: image `d61a484`, schema `0014`.
- Smoke: local/external health+ready, anonymous auth redirect, authenticated service
  page and author page, packaged migration/template/icon, storage mounts and logs — OK.
- Sapfir production backfill: 309 distinct publications, 21 series, zero flood notes.
