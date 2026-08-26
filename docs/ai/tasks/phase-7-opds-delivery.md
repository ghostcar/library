# TaskContext: phase-7-opds-delivery

```yaml
task_id: phase-7-opds-delivery
goal: "Phase 7: OPDS 1.2 каталог для FBReader, device-token auth, acquisition/download, поиск"
user_value: "FBReader подключается к личной библиотеке и скачивает preferred-файлы с читаемыми именами"
scope:
  in: [OPDS 1.2 сериализатор, Basic device-token auth, OpdsCatalogService, /opds* маршруты, download, OpenSearch, UI токенов, миграций нет]
  out: [OPDS 2.0 (сериализатор готов к добавлению), обложки в фидах (Phase 8), FBReader ручной smoke]
invariants:
  - "device token != JWT; отзыв режет доступ"
  - "owner scope на каждом фиде и download"
  - "raw токен показывается один раз"
relevant_decisions: [ADR-0012]
affected_modules: [presentation.opds, application.opds_catalog_service, web]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks: []
assumptions: []
ambiguities: []
plan: []
checkpoints:
  - "2026-08-26 реализовано; 225 tests passed; smoke фидов+download+search+401 пройден"
status: done
base_commit: "9e45937"
```
