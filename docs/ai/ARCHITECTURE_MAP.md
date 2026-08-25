# Architecture Map

Стиль: модульный монолит (мастер-промпт §4.1). Слои: domain / application / infrastructure / presentation / adapters.

## Структура

```text
src/portal/
  core/                  — ядро макропортала (общие сервисы)
    config/              — typed settings (pydantic-settings)
    database/            — async engine, session, base
    module_registry/     — регистрация модулей (маршруты, события)
    auth/                — PLANNED (Phase 1+)
    events/ jobs/ audit/ notifications/ — PLANNED (Phase 1)
  modules/
    library/             — доменный модуль «Библиотека»
      domain/            — сущности, VO, инварианты, события
      application/       — use cases, порты
      infrastructure/    — SQLAlchemy модели, репозитории
      presentation/      — HTML/HTMX, JSON, OPDS (позже)
      adapters/          — реализации внешних источников (позже)
  web/                   — FastAPI app factory, маршруты core
migrations/              — Alembic
tests/                   — unit / integration / contract / e2e
docs/                    — ai/ design/ architecture/ operations/
deploy/                  — nginx, compose для VPS (позже)
scripts/                 — dev/test/lint
```

## Потоки зависимостей

- `web` → `core` + `modules.library.presentation`
- `modules.library.application` → `domain` (не зависит от infrastructure)
- `modules.library.infrastructure` → `domain`, `core.database`
- Модули не импортируют ORM-модели друг друга (правило §4.1).

## Entrypoints

- Web: `src/portal/web/app.py:create_app()` → uvicorn, порт 8001 (dev)
- CLI/worker: PLANNED (Phase 1+)

## Модули

| Модуль | Статус | Маршруты |
|--------|--------|----------|
| core.health | IMPLEMENTED | `GET /healthz` |
| library | PARTIAL (domain+infra) | `GET /library/` (заглушка) |

## База данных

- PostgreSQL 15+ (контейнер, порт не публикуется на хост)
- Alembic: `migrations/versions/0001_library_canonical_core.py`
- Схема: authors, author_aliases, works, work_authors, series, series_aliases, series_memberships, source_records, assets, asset_relations, reading_states (детали — в миграции и DOMAIN_GLOSSARY.md)
