# Architecture Map

Стиль: модульный монолит (мастер-промпт §4.1). Слои: domain / application / infrastructure / presentation / adapters.

## Структура

```text
src/portal/
  core/                  — ядро макропортала (общие сервисы)
    config/              — typed settings (pydantic-settings, LIBRARY_*)
    database/            — async engine, session factory, Base
    module_registry/     — регистрация модулей (маршруты, флаги)
    auth/                — ОБЩАЯ АВТОРИЗАЦИЯ МАКРОПОРТАЛА (ADR-0006)
      domain.py          — User, AuthToken, scopes
      passwords.py       — argon2id
      jwt_service.py     — TokenService (HS256; интерфейс готов к RS256/JWKS)
      repository.py      — UserRepository, AuthTokenRepository, AuditRepository
      service.py         — AuthService: register/login/refresh/logout/device
      dependencies.py    — CurrentUser, OptionalUser, CSRFProtected, require_scope
      routes.py          — /auth/* API
      rate_limit.py      — in-memory sliding window
      orm.py             — users, api_tokens, audit_log
    audit/               — AuditService (failure-события — отдельной транзакцией)
    events/              — transactional outbox (orm + repository)
    jobs/                — очередь PostgreSQL, FOR UPDATE SKIP LOCKED + worker
    storage/             — StorageAdapter порт + LocalStorageAdapter (content-addressed)
    database/models.py   — реестр всех ORM-моделей (для worker/migrations)
  modules/
    library/             — доменный модуль «Библиотека»
      domain/            — сущности, VO, инварианты, события
      application/       — use cases (CatalogService), порты
      infrastructure/    — ORM, репозитории, мапперы
      presentation/      — защищённые HTML-страницы + /library/info
      templates/         — шаблоны модуля (extends base из web)
      adapters/          — OPDS + Author.Today public HTML, watch dispatch/backoff
  (normalizer: modules/library/infrastructure/normalizer/{fb2,epub,fingerprints,cover}.py)
  web/                   — app factory, composition root, SSR auth-страницы
    deps.py              — provide_session (transactional session per request)
    templates/           — base.html (токены Ghostcar), login.html
migrations/              — Alembic (0001 library, 0002 auth/audit/outbox/jobs + FK owner)
tests/                   — unit / integration
docs/                    — ai/ design/ architecture/ operations/
deploy/                  — nginx (Phase 9)
scripts/                 — dev/test/lint
```

## Потоки зависимостей

- `web` → `core.*` + `modules.library.presentation`
- `modules.library.*` → `core.auth` (только зависимости/домен), НЕ имеет своего auth
- `modules.library.application` → `domain` + порты (не infrastructure)
- Модули не импортируют ORM-модели друг друга (правило §4.1)

## Entrypoints

- Web: `src/portal/web/app.py:create_app()` → uvicorn 127.0.0.1:8001 (dev)
- Worker: `python -m portal.core.jobs.worker` (graceful shutdown, poll 2s)

## Модули

| Модуль | Статус | Маршруты |
|--------|--------|----------|
| core.auth | IMPLEMENTED | /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me, /auth/tokens, /login (SSR), /logout (SSR) |
| core.health | IMPLEMENTED | GET /healthz, /readyz |
| library | PARTIAL | dashboard/catalog/authors/series/import/normalization/sources/notifications/settings + OPDS delivery |
| FB2 continuation candidates | IMPLEMENTED, pending deploy | local FB2 extractor → `continuation_link_candidates` → manual title resolver → Work match or review candidate |

## Source monitoring

- `WatchService` выбирает реализацию по `watch_rules.adapter_id`, хранит parser version,
  делает dedup/notifications и общий degraded/backoff.
- `OPDSAdapter`: safe Atom/OPDS parser, conditional GET.
- `AuthorTodayAdapter`: только публичные `/u/<slug>/works`, HTML parser v1,
  quiet baseline и revision events; без auth/private API/content/acquisition (ADR-0019).
- `ContinuationLinkService`: не мониторинг источников, а ручная title-only
  проверка ссылки из локального FB2. Перед одним HTML GET проверяет public HTTPS
  host и applicable rules из `robots.txt`; детали — ADR-0021 и runbook.

## База данных (18 таблиц)

- core: users, api_tokens, audit_log, outbox_events, jobs
- library: authors, author_aliases, works, work_authors, series, series_aliases, series_memberships, source_records, source_author_records, source_endpoints, source_links, watch_rules, source_observations, assets (+work_id, is_preferred), asset_relations, reading_states, import_batches, import_items, duplicate_candidates, continuation_link_candidates, normalization_runs
- Все пользовательские данные: `owner_id UUID → users.id` (FK CASCADE)
