# TaskContext: persistent web session across service restarts

**Date:** 2026-09-01  
**Status:** `completed`

## Symptom

The owner observes that every web/worker restart returns the portal to the login
page even though the database and `.env` persist.

## Plan

- [x] Verify production JWT secret stability and persisted refresh-token state without exposing secrets.
- [x] Reproduce session behavior with an expired access cookie across two app instances.
- [x] Implement safe SSR session renewal using the persisted refresh token.
- [x] Preserve bearer/API behavior, CSRF protection and explicit logout semantics.
- [x] Add integration/security regression coverage and update ADR/memory.
- [x] Run full quality gate; prepare a separate deployment only after verification.

## Verification

- Production diagnosis: host/runtime JWT-secret fingerprints match; 8 active
  persisted refresh sessions survived the last container recreation.
- Auth integration: 31 passed, including expired access + rebuilt app container.
- Full suite: 298 passed; fresh migration remains `0014`.
- Ruff/format/mypy and Chromium desktop/mobile: green.
- Production intentionally unchanged until an explicit deploy command.
