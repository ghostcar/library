# TaskContext: watched-inbox-2026-08-27

```yaml
task_id: watched-inbox-2026-08-27
goal: "Закрыть отсутствующий watched inbox без неявного single-user ownership"
scope:
  in: [typed config, safe directory polling, owner resolution, import source provenance, worker tick, tests, docs]
  out: [перемещение/удаление исходных файлов, deploy, изменение .env]
invariants:
  - "сканируются только LIBRARY_IMPORT_ROOTS"
  - "owner задаётся явно email-настройкой"
  - "файл не трогается, пока не выдержан stability window"
  - "повторный poll идемпотентен по SHA-256"
status: done
```

Проверено: `scripts/lint.sh`, `git diff --check`, полный набор — 262 passed.
