# TaskContext: phase-6-source-monitoring

```yaml
task_id: phase-6-source-monitoring
goal: "Phase 6: наблюдение за источниками (OPDS), scheduler/backoff/degraded, watch rules, in-app уведомления"
user_value: "Новые книги в наблюдаемых OPDS-лентах приходят уведомлением; сбои источника видны и не теряют данные"
scope:
  in: [OPDS adapter, реестр адаптеров+capabilities, watch rules, scheduler tick, backoff, observations+dedup, notifications UI, миграция 0007]
  out: [AT/Litnet/Flibusta адаптеры (исследование отдельно), Telegram/email, acquisition-автоскачивание]
invariants:
  - "отключённый адаптер не создаёт правила/jobs"
  - "уведомление только на реальный переход (первое наблюдение)"
  - "временная ошибка не удаляет наблюдения"
  - "credentials только env, не БД"
relevant_decisions: [ADR-0011]
affected_modules: [modules.library.adapters, core.jobs.worker, web]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks: []
assumptions: []
ambiguities: []
plan: []
checkpoints:
  - "2026-08-26 реализовано; 214 tests passed; smoke через реального воркера пройден"
status: done
base_commit: "f91c823"
```
