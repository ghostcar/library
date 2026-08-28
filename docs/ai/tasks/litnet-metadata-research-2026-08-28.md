# TaskContext: Litnet public metadata adapter research

**Date:** 2026-08-28  
**Status:** `completed_no_implementation`  
**Scope:** complete the prerequisite investigation for `OPEN_QUESTIONS#10`; implementation is conditional on public rules and a stable, safely parseable surface.

## Goal

Determine whether a Litnet adapter can observe public author/work metadata without authentication, private APIs, protected-content access, acquisition, or bypassing technical restrictions.

## Non-goals

- Downloading books, chapters, covers, or any protected content.
- Browser automation, credential use, undocumented API calls, or bypassing robots/rate limits/anti-bot controls.
- Enabling or deploying an adapter before the evidence and tests justify it.

## Acceptance criteria

1. Record official terms/robots/API evidence and the public URL shape inspected.
2. Decide explicitly: implement a metadata-only adapter, or retain Litnet disabled.
3. If implementation is permissible: version selectors, add a captured synthetic fixture and parser/fetch/flow tests; preserve conditional requests, size guard, rate limit, and fast disable path.
4. Update the relevant ADR, memory, and this TaskContext with factual results.

## Safety constraints

Only one public page may be inspected after checking robots and official rules. Any ambiguity or explicit prohibition ends implementation and leaves the source disabled.

## Result

- Official Litnet user terms, current on 2026-08-28, expressly prohibit use of
  automated programs to collect information from the site.
- This is an explicit prohibition, so no author/listing page polling, parser,
  fixture, request or endpoint was added.
- `litnet` remains disabled. The decision is ADR-0020; reopening requires an
  official API/RSS with compatible terms or Litnet's written permission.
