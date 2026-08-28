# TaskContext: outbox-handlers-2026-08-28

```yaml
task_id: outbox-handlers-2026-08-28
goal: "Заменить logging-only outbox dispatch на typed registry и bounded retry policy"
scope:
  in: [outbox ORM/repository, worker dispatcher, migration, tests, docs]
  out: [внешние интеграции и новые consumers]
invariants:
  - "неизвестное событие не помечается processed"
  - "ошибки повторяются с backoff и конечным FAILED"
  - "successful handlers остаются идемпотентными"
status: done
```

Примечание: тестовый runner теперь применяет Alembic `upgrade head` перед
pytest, чтобы persistent test volume не отставал от ORM после добавления миграции.

Проверено: `scripts/lint.sh`, targeted `30 passed`, полный `scripts/test.sh` —
`263 passed`. Изменения пока не развёрнуты на Test VPS.
