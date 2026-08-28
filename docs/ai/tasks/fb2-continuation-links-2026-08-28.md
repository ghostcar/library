# TaskContext: FB2 continuation-link candidates

**Date:** 2026-08-28  
**Status:** `completed_not_deployed`  
**Goal:** extract author-provided continuation links from locally owned/imported FB2
files, resolve only public page titles where policy permits, match existing works,
and present missing works as reviewable candidates.

## Safety boundary

- Original and literary text are never changed; only link metadata and a bounded
  context fragment are analysed.
- No downloads, chapter/cover extraction, authentication, cookies, browser
  automation, undocumented APIs, or automatic catalog creation.
- External resolution is opt-in per discovered link, HTTPS-only, robots-aware,
  SSRF-safe, size/time bounded, redirect-checked and title-only.
- A missing/ambiguous match remains a candidate pending user confirmation.

## Acceptance criteria

1. Versioned FB2 link extractor with fixtures and continuation-context scoring.
2. Owner-scoped, deduplicated review records with links to source work.
3. Safe title resolver and title-based catalog matching; no automatic work create.
4. SSR review UI with explicit action; tests, migration and updated memory.

## Result

- Versioned local FB2 extraction stores only `https?` links with nearby
  continuation wording; normal files and literary text are unchanged.
- Migration `0013` adds owner-scoped, deduplicated candidates. Import UI provides
  explicit title check/dismiss actions and distinguishes an exact existing catalog
  match from a candidate for a new book.
- The title check is HTTPS/public-host/robots-aware and bounded to robots.txt plus
  one HTML response; it neither follows redirects nor downloads content/files.
- Exact operational semantics and rationale for `robots.txt` are in
  `docs/ai/runbooks/fb2-continuation-link-check.md`.
- Checks: Ruff + mypy clean; extractor unit tests 2 passed; migration to test DB
  and 11 import integration tests passed. No production deployment was performed.
