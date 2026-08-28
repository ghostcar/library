# TaskContext: Author.Today public metadata adapter

- Status: completed (code/tests; deployment pending explicit command)
- Goal: observe public Author.Today author work pages for new/updated works without authentication or content acquisition.
- Safety boundary:
  - only public `/u/<slug>/works` pages allowed by current robots.txt;
  - metadata only: work id/title/url, author name, public status/update time and series label;
  - no private API, guest tokens, login automation, chapter text, covers or downloads;
  - conditional GET, 5 MiB guard, explicit User-Agent, minimum watch interval 30 minutes.
- Parser contract:
  - versioned synthetic fixtures derived from observed public markup;
  - `.book-row`, `.book-title a[href^='/work/']`, Person JSON-LD;
  - unexpected layout must fail closed and enter normal degraded/backoff flow.
- Plan:
  1. add HTML parser/fetch adapter and adapter dispatch in WatchService;
  2. enable only Author.Today-compatible HTML endpoints/rules in UI;
  3. unit, contract and integration tests;
  4. update ADR/memory, commit; deploy only after explicit instruction.
- Results:
  - parser validated against a live public author page (30 works) and synthetic fixture;
  - quiet initial baseline plus revision notifications for later update/status changes;
  - WatchService dispatches by adapter and stores per-adapter parser version;
  - 23 targeted unit + 7 integration passed; full suite 281 passed;
  - repository-only change; deployed image remains `a531fd1`.
