# TaskContext: phase-8-9-design-deploy

```yaml
task_id: phase-8-9-design-deploy
goal: "Phase 8 (токены, UI kit, hardening) + подготовка Phase 9 (образ, compose.prod, nginx, backup/restore)"
user_value: "Единый визуальный язык на всех экранах; защита заголовками; деплой сводится к командам из runbook"
scope:
  in: [tokens.css/components.css, base refactor, UI kit dev-only, security headers, Dockerfile, compose.prod.yaml, nginx conf, backup/restore+round-trip, runbook]
  out: [Tailwind-сборка (TECH_DEBT), visual regression, обложки в фидах, GHCR push, живой деплой (нет DNS)]
invariants:
  - "цвета/типографика только из tokens.css"
  - "UI kit недоступен вне development"
  - "образ non-root, secrets не в слоях"
  - "backup не содержит .env"
relevant_decisions: [ADR-0013, ADR-0004, ADR-0003]
affected_modules: [web, deploy, scripts, docs.operations]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "CSP содержит unsafe-inline styles до полного переноса стилей"
  - "FBReader smoke и живой деплой ждут владельца (DNS/GHCR)"
assumptions: []
ambiguities: []
plan: []
checkpoints:
  - "2026-08-26 реализовано; 225 tests passed; docker build+imports OK; backup round-trip OK; headers/static/ui-kit smoke OK"
status: done
base_commit: "6a17097"
```
