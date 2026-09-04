# TaskContext: deploy candidate review and reclassify discovered authors

**Date:** 2026-09-04
**Status:** `completed`
**Goal:** deploy the release-notification filter, author provenance graph and
review-first coauthor candidate flow, then safely rebuild derived Author.Today
candidate state from the six existing books.

## User contract

1. Commit and deploy the completed release.
2. Move safely removable, automatically discovered source-only authors back to
   derived candidates and clean up their generated endpoints/rules.
3. Reanalyse existing Author.Today observations and run a fresh coauthor discovery
   iteration.
4. Never delete or modify uploaded files, canonical books, series, or author cards
   already attached to those books.

## Safety plan

- [x] Re-read project memory and deployment runbook.
- [x] Make parser refreshes enrich deduplicated observations without generating
  duplicate release notifications.
- [x] Run the full test/lint gate and commit the release.
- [x] Create and validate a PostgreSQL + storage backup before rollout.
- [x] Build/push an immutable image and deploy web/worker; verify schema and smoke.
- [x] Audit exact production author/source relationships and resolve a guarded
  cleanup set containing only non-preferred, source-only auto-discovered authors.
- [x] Create a second validated backup, apply the guarded cleanup, and verify all
  protected entity/file counts and IDs are unchanged.
- [x] Force a quiet refresh of preferred root sources, wait for completion, and
  verify candidates/provenance and notification counts.
- [x] Update deployment memory and commit the operational record.

## Protected invariants

- All original asset rows and storage objects present before maintenance.
- All canonical work and series rows.
- Every author that has a `work_authors` relationship, plus every preferred/manual
  author source.
- Existing `work_authors` and `series_memberships` relationships.
- No literary content or uploaded object is rewritten.

## Notes

- Pending candidates remain a derived read model from preferred-root observation
  evidence; they do not require candidate rows in the database.
- Cleanup will stop before mutation unless its exact target set can be proven to
  exclude every protected invariant.

## Result

- Release `e03dfa9` passed 300 tests plus Ruff/format/mypy, was published as
  `ghcr.io/ghostcar/library:e03dfa9` and deployed without a schema change.
- Valid backups: `pre-deploy/*-20260904-085831.*` and
  `pre-cleanup/*-20260904-090220.*`; both contain DB, full storage and schema-0014
  manifests and passed gzip/tar validation.
- A guarded transaction removed exactly 15 non-preferred source-only authors and
  their generated endpoints/rules. Protected entity hashes and the complete
  storage-tree hash were identical before and after cleanup.
- Quiet reanalysis refreshed all four preferred Author.Today roots with parser v3,
  `status=ok`, `new=0`; no author or notification was created. All 15 removed
  profiles now appear as candidates with parent-author and book evidence.
- Authenticated smoke returned 200 for `/library/authors`, the whole provenance
  graph and a focused candidate graph. Web is healthy, worker is running, and the
  notification total remains 56.
