# TaskContext: abstract source settings and links

- Status: in_progress
- Goal: separate source endpoint configuration from observations and support multiple metadata/acquisition sources per author, series, and work.
- Completed slices:
  - Alembic 0011: owner-scoped `source_endpoints`, polymorphic `source_links`, nullable watch-rule reference;
  - endpoint settings UI for OPDS/site and metadata/acquisition roles;
  - `/authors` and `/authors/{id}` cards;
  - direct SourceLink read-model and display on author/work cards.
- Known gaps:
  - selected endpoint is not persisted to `watch_rules.source_endpoint_id`;
  - endpoint management is create/list only; HTML adapter selection is not implemented;
  - SourceLink has no CRUD UI, preferred/priority, inheritance, merged availability state, or series-card block;
  - fresh migration/full suite and deployment are pending.
- Next: migration 0012 for preferred/priority if required, SourceLink service+CRUD, inheritance `work > series > author > global`, series UI, integration tests, then deploy 0011/0012 together.
