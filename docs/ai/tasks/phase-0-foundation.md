# TaskContext: phase-0-foundation

```yaml
task_id: phase-0-foundation
goal: "Phase 0 (аудит, память, дизайн-инвентаризация) + первый vertical slice (§24.11): скелет проекта, core, канонические сущности library, миграция, репозитории, тесты"
user_value: "Рабочий воспроизводимый фундамент: приложение поднимается, БД мигрирует, каноническая модель зафиксирована, quality gates зелёные"
scope:
  in:
    - распаковка и инвентаризация design-архивов
    - docs/ai память + AGENTS.md + ADR-0001..0005
    - pyproject.toml, venv, ruff/mypy/pytest
    - core: config, database, module_registry, app factory, health
    - library domain: Author, AuthorAlias, Work, Series, SeriesMembership, SourceRecord, Asset, AssetRelation, ReadingState (домен)
    - library infrastructure: ORM + репозитории + Alembic 0001
    - compose.dev.yaml (postgres без публикации порта), .env.example, scripts
    - тесты unit + integration
  out:
    - auth, импорт файлов, нормализатор, AI, OPDS, source adapters, UI-шаблоны
    - git push, deploy, изменения /etc/nginx
invariants:
  - "Work != SourceRecord != Asset"
  - "owner_id во всех пользовательских таблицах"
  - "внешний ID уникален в паре adapter_id+external_id"
  - "литературный текст не изменяется (нет кода, его касающегося)"
relevant_decisions: [ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0005]
affected_modules: [core, modules.library, web]
affected_symbols: [create_app, Settings, ModuleRegistry, Work, Asset, SourceRecord]
tests_to_run: [scripts/lint.sh, scripts/test.sh]
risks:
  - "Python 3.13 vs предпочтительный 3.12: следить за совместимостью пакетов"
  - "Интеграционные тесты требуют Docker/PostgreSQL на машине"
assumptions:
  - "API-ключ OmniRoute из промпта валиден (проверено /v1/models 200)"
  - "DNS library.gorbunovr.ru добавит пользователь позже"
ambiguities:
  - "базовая тема UI (OPEN_QUESTIONS #6)"
plan:
  - "распаковать дизайн, инвентаризация"
  - "память + ADR"
  - "скелет проекта и core"
  - "library domain + infra + миграция"
  - "тесты + quality gates"
  - "compose + scripts + README"
checkpoints:
  - "2026-08-25 окружение и память: git init, remote, дизайн распакован, docs/ai создан, ADR-0001..0005"
  - "2026-08-25 скелет: pyproject+venv(3.13.5), ruff 0.16/mypy strict/pytest настроены"
  - "2026-08-25 core+library: app factory, healthz/readyz, module registry, domain (12 сущностей), ORM (13 таблиц), репозитории, CatalogService, Alembic 0001"
  - "2026-08-25 quality gates: ruff clean, mypy clean (28 файлов), pytest 52 passed (unit+integration, PostgreSQL 15)"
  - "2026-08-25 smoke: uvicorn на 127.0.0.1:8001, /healthz /readyz /library/info /library/ — 200"
status: done
base_commit: "(пустой репозиторий)"

## Итоги (фактические результаты)

- Исправлено в процессе: alembic env.py — run_migrations без begin_transaction откатывал DDL; flush на границах репозиториев (порядок вставки FK без relationship()); test_database_url из conftest собирался pytest'ом как тест.
- Коммиты: 0c0c7a4 (memory/docs), 7371e1c (core), c7b64e9 (library domain) — локальные, push не выполнялся.
- Следующий шаг: Phase 1 — auth core, outbox/jobs, storage port, UI shell.
```

## Checkpoints

### 2026-08-25 — окружение и память

- Проверено: git init выполнен, remote добавлен (push запрещён); дизайн-архивы распакованы; OmniRoute доступен (200 /v1/models).
- Изменено: AGENTS.md, docs/ai/* (14 документов), docs/design/DESIGN_SOURCE_OF_TRUTH.md, ADR-0001..0005, .gitignore.
- Следующий шаг: скелет проекта.
