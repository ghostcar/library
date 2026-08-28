# TaskContext: source observations and derived series state

- Status: in_progress
- Goal: deterministically link source observations to owner-scoped canonical works/series and expose `last_observed`, `has_new_release`, and `waiting_release` with evidence.
- Scope: nullable observation links, migration, watch ingestion matching, series-state read model, tests, deploy.
- Safety: ambiguous title/author matches remain unlinked; no automatic work/series creation.
- Validation: full `scripts/test.sh`, lint, production backup/migration/smoke.
