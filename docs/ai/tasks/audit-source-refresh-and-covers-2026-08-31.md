# TaskContext: audit source refresh visibility and book covers

**Date:** 2026-08-31
**Status:** `complete`
**Goal:** report the actual user-visible/background refresh flow for author pages
and the current cover pipeline, then identify the next product fixes.

## Scope

- Read-only audit of author/source templates, routes, scheduler/watch persistence,
  notifications/logging, and normalizer/import cover handling.
- No implementation or production mutation in this task unless separately requested.

## Questions

- Where can the owner see last/next refresh, success, error, and discovered changes?
- Is a manual refresh action present and safe to add?
- Are FB2/EPUB covers extracted, stored, served, and displayed?

## Findings

- A connected Author.Today rule is due immediately, scheduler scans every 30
  seconds, and successful polls repeat every 1800 seconds. Failures use bounded
  exponential backoff; two consecutive failures mark the rule degraded.
- Author card shows source URL and last poll or last error. The sources diagnostics
  show interval/degraded/error, but neither surface shows next poll, queued/running
  state, or the previous result count. There is no manual refresh route/button.
- New/revised observations after the quiet first baseline create in-app
  notifications. Exact poll outcomes exist only in worker logs; no persistent
  user-facing check history exists.
- Production audit found four enabled Author.Today rules: three had successful
  baseline polls with zero failures; the fourth was queued for its first poll.
- Original FB2 files are preserved byte-for-byte, including embedded covers.
  Manual `prose_compact` normalization can retain and optimize one embedded
  FB2/EPUB cover to 1600px inside the derivative and records cover diagnostics in
  its manifest. Production currently has 8 original FB2 assets and zero
  normalization runs.
- There is no separate cover entity/blob, cover-serving endpoint, catalog/detail
  rendering, OPDS image link, or import-time cover extraction. Author.Today is
  metadata-only by policy and intentionally does not fetch covers.

## Recommended next slices

1. Add a CSRF-protected `Проверить сейчас` action that queues/reserves the rule
   instead of performing external HTTP in the web request; enforce owner scope and
   a short cooldown. Show last poll, next poll, last outcome/new count, and state.
2. Add local-file cover extraction/backfill: content-addressed cover storage tied
   to work/source asset, safe image validation and thumbnails, owner-scoped serving,
   catalog/work rendering, and OPDS image/thumbnail links. Never modify originals.
