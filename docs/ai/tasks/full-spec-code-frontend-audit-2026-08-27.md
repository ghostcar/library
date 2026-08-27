# TaskContext: full-spec-code-frontend-audit-2026-08-27

```yaml
task_id: full-spec-code-frontend-audit-2026-08-27
goal: "Аудит реализации на соответствие мастер-ТЗ, ревью backend-кода и frontend/UX"
user_value: "Получить доказательный список расхождений, дефектов и рисков с приоритетами"
scope:
  in: [master prompt compliance, architecture, backend, security, tests, frontend, UX, design convergence, operational artifacts]
  out: [исправление найденных дефектов, deploy, git push, изменение VPS-инфраструктуры]
invariants:
  - "не изменять литературные тексты и пользовательские данные"
  - "не выполнять deploy/push/инфраструктурные изменения"
  - "каждое замечание подтверждать кодом, тестом или требованием"
relevant_decisions: [ADR-0001, ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013]
affected_modules: [core, library, web, tests, deploy, docs]
tests_to_run: [scripts/lint.sh, scripts/test.sh, targeted security and frontend checks]
risks:
  - "документация состояния может расходиться с текущим кодом"
  - "часть UX требует браузерной визуальной проверки"
assumptions:
  - "аудит read-only; единственное изменение — этот обязательный TaskContext"
ambiguities: []
plan:
  - "сопоставить требования мастер-промпта с кодом и тестами"
  - "проверить backend, безопасность и эксплуатационные артефакты"
  - "проверить шаблоны, CSS, адаптивность и доступность"
  - "запустить quality gates и оформить приоритизированный отчет"
checkpoints:
  - "2026-08-27: pre-fetch памяти выполнен, аудит начат"
  - "2026-08-27: 252 теста прошли; lint gate не прошёл (15 ошибок)"
  - "2026-08-27: подтверждены критичные расхождения — CSRF, outbox/transactions, tracked backups, retention; frontend shell и HTML не соответствуют требованиям"
status: done
base_commit: null
```
