# TaskContext: import quality and storage incident audit

**Date:** 2026-08-31
**Status:** `deployed_ready_for_reupload`
**Goal:** diagnose unusable bulk AI metadata extraction and verify originals after
the deployment rollout.

## Findings

- `DigestBuilder` supplies OmniRoute with the filename, deterministic filename
  parse and catalog candidates only; it does not extract FB2 `title-info` or
  EPUB package metadata. The observed proposals consequently reproduce broken
  romanized underscore filenames and all require review.
- Production has 8 asset rows with storage paths, but the running containers
  contain 0 files in both configured `./storage` (`/app/storage`) and mounted
  `/data/storage`. `LIBRARY_STORAGE_ROOT=./storage` wrote originals into the
  mutable web-container layer, not `library_storage` volume.
- The pre-deploy storage archive also contains only its root. Host `storage/`
  contains seven unrelated/different-hash files plus one matching hash, so it
  must not be copied into production without per-file validation.

## Required recovery and product work

1. Do not mutate assets or copy candidate files until the owner chooses a
   recovery source for the missing originals.
2. Correct deployment configuration so `LIBRARY_STORAGE_ROOT=/data/storage`,
   then test upload survives a controlled container recreation.
3. Add deterministic FB2 (both 1.0/2.0 plus defensively unqualified variants)
   and EPUB package metadata extraction: ordered authors, title, sequence,
   language, identifiers. It becomes the primary evidence; filename is fallback.
4. Re-run only safely recoverable/re-uploaded imports with cache version bump;
   use LLM only to reconcile conflicts, not infer canonical metadata from a
   damaged filename.
5. Add a batch-review UI only for genuine conflicts and a correction feedback
   loop; it must not replace correct automatic extraction.

## Owner recovery input

- The owner has the six source files and will re-upload them after persistent
  storage and the browser archive filter are repaired.

## Deployment result

- `1f98181` is deployed. Both web and worker report `/data/storage`; smoke
  health/ready passed and no book was added during deployment.
- The owner can now submit all six sources in one upload (a `.fb2.zip` is
  accepted). Re-upload restores missing content-addressed originals and FB2
  metadata is applied before filename/LLM fallback.
