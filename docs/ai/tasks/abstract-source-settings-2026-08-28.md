# TaskContext: abstract source settings and links

- Status: completed (code + tests; deployment pending explicit command)
- Goal: separate source endpoint configuration from observations and support multiple metadata/acquisition sources per author, series, and work.
- Completed slices:
  - Alembic 0011: owner-scoped `source_endpoints`, polymorphic `source_links`, nullable watch-rule reference;
  - endpoint settings UI for OPDS/site and metadata/acquisition roles;
  - `/authors` and `/authors/{id}` cards;
  - direct SourceLink read-model and display on author/work cards.
  - migration 0012: preferred source and priority with one preferred link per entity/role;
  - endpoint toggle/delete and persisted `watch_rules.source_endpoint_id`;
  - owner-scoped SourceLink create/update-by-key/prefer/delete with URL validation;
  - independent role resolution `work > series > author > global` (series also inherits author links);
  - shared source block on author/series/work cards with merged release/file state;
  - fresh migration and current full suite: 270 passed.
- Remaining follow-up:
  - HTML endpoints are declarative settings/links; actual per-site HTML polling adapters remain a separate slice;
  - deploy repository schema 0011/0012 only after explicit user command.
