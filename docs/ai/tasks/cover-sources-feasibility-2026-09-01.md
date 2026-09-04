# TaskContext: cover sources feasibility

**Date:** 2026-09-01
**Status:** `complete`
**Goal:** determine whether portal covers should come from local FB2/EPUB files,
official work pages, or normalization, and define a safe implementation order.

## Facts verified

- FB2 and EPUB normalizers already resolve the declared embedded cover and can
  optimize JPEG/PNG to 1600 px inside a normalized derivative.
- Covers are not extracted as standalone assets; no cover endpoint, portal render
  or OPDS image link exists. Normalization is manual and therefore cannot be the
  only cover trigger.
- Before owner-authorized cleanup, production had eight original FB2 asset rows:
  six present objects with unambiguous embedded covers and two unattached test
  placeholders referencing absent objects. The two placeholders and their import
  rows were removed on 2026-09-01; production now has six rows, six objects and
  six readable embedded covers.
- Public Author.Today work pages expose the canonical cover through `og:image`,
  JSON-LD and the visible cover image. Author works-list rows expose a CDN thumbnail
  URL, so metadata discovery does not require downloading images or chapters.

## Recommended policy

1. Extract covers at import and via an idempotent backfill job, without modifying
   originals and without requiring normalization.
2. Keep multiple cover candidates with provenance (`embedded`, `official_source`,
   `manual`) and one owner-selected preferred cover. Default priority:
   manual override → embedded local cover → official source → placeholder.
3. Normalization reuses the extractor but is not a prerequisite for portal covers.
4. Fetch an official image only for an owner-scoped canonical work, not for every
   observed source publication. Use a bounded background job, HTTPS/CDN allowlist,
   conditional GET, strict byte/pixel/content-type limits, Pillow verification and
   local content-addressed storage.
5. Serve owner-scoped portal and device-scoped OPDS image/thumbnail endpoints;
   never hotlink the user's browser directly to the external CDN.

## Proposed implementation slices

- Cover persistence + safe extractor + backfill for existing FB2/EPUB originals.
- Portal catalog/work rendering and OPDS 1.2 image/thumbnail links.
- Author.Today `cover_url` metadata, canonical-work fetch job, provenance/preference
  UI and change detection.

The feasibility audit itself changed no code or production state. Its later
data-cleanup follow-up is recorded in
`remove-missing-test-assets-2026-09-01.md`.
