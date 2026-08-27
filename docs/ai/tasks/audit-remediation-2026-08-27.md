# TaskContext: audit-remediation-2026-08-27

```yaml
task_id: audit-remediation-2026-08-27
goal: "Последовательно устранить дефекты аудита: безопасность, фоновые гарантии и frontend"
user_value: "Надёжный портал с понятными HTML-ошибками, цельным дизайном и безопасными действиями"
scope:
  in: [auth UX, CSRF, errors, outbox, jobs, retention, uploads, owner scoping, audit, shell, icons, tests, memory]
  out: [deploy, git push, переписывание git history, внешняя VPS-инфраструктура]
invariants:
  - "оригиналы книг и пользовательские данные не изменяются"
  - "API сохраняет JSON-ошибки, браузерные HTML-маршруты получают HTML/redirect"
  - "все cookie-auth unsafe actions проходят CSRF"
relevant_decisions: [ADR-0006, ADR-0007, ADR-0013]
affected_modules: [core.auth, core.events, core.jobs, library.application, library.presentation, web]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks: ["широкое изменение всех HTML-форм", "миграция уникальных ограничений"]
assumptions:
  - "tracked backup пуст; удалить его только из индекса и запретить новые backups"
  - "иконки следуют Material Symbols vocabulary из дизайн-шаблонов, поставляются локальным SVG sprite"
ambiguities: []
plan: [security and errors, background reliability, data boundaries, frontend shell and icons, verification]
checkpoints:
  - "2026-08-27: remediation начат после полного аудита"
  - "2026-08-27: security/reliability remediation и responsive shell реализованы; миграция 0008 добавлена"
  - "2026-08-27: scripts/lint.sh clean; 257 tests passed; git diff --check clean"
status: done
base_commit: "f06b752"
```
