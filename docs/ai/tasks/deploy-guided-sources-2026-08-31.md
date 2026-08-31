# TaskContext: deploy guided sources release candidate

**Date:** 2026-08-31
**Status:** `complete`
**Target:** test VPS production stack at `library.gorbunovr.ru`
**Release commit:** `00e6089`
**Previous image:** `ghcr.io/ghostcar/library:1f98181`
**Schema before/after deploy:** `0013 (head)`
**Deployed image:** `ghcr.io/ghostcar/library:00e6089`
**Digest:** `sha256:8db69ebf9d5c4d55eaa8a3aed759b459a78dea7fa80e2bf2164352bf0daf6702`
**Backup:** `backups/pre-deploy/*-20260831-082135.*`

## Authorized operations

- Build and push immutable GHCR image for commit `00e6089`.
- Create and validate pre-deploy DB/storage backup.
- Apply migrations if required, switch web/worker, and run local/external smoke.
- Do not modify host nginx or unrelated services.

## Gate inherited from release candidate

- Full project suite: 294 passed.
- Full Ruff/format/mypy: green.
- Chromium shell desktop/mobile: green.
- Final source integration after searchable reconciliation: 4 passed.

## Deployment checklist

- [x] Verify release commit, running image, schema, resources.
- [x] Build and push `ghcr.io/ghostcar/library:00e6089`.
- [x] Create and validate pre-deploy backup.
- [x] Confirm migration delta: none; schema remains `0013`.
- [x] Switch web and worker to immutable image.
- [x] Verify containers, schema, health/ready, auth redirect, static/security headers,
      and authenticated product surfaces where practical.
- [x] Update canonical deployment memory and commit the deployment record.

## Smoke notes

- Local and external HTTPS health returned 200; local ready returned 200.
- Anonymous `/library/` returned 303 to `/login`; CSP and other security headers
  remained strict. New templates and both assignment routes are packaged.
- Web and worker logs contain no ERROR, Traceback, Exception, or HTTP 500.
- Registration is closed in this contour, so a temporary authenticated smoke user
  received the expected 403 and was not created. No existing user data changed.
