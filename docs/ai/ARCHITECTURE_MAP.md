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

## Browser session continuity

- Access JWT remains short-lived (15 minutes); the opaque 30-day refresh token is
  persisted in PostgreSQL and scoped to cookie path `/auth`.
- A portal 401 redirects to allowlisted `GET /auth/session?next=/library/...`.
  `AuthService.resume` validates the active refresh row, issues a fresh access JWT
  without rotating the refresh token, refreshes CSRF and redirects back. This is
  idempotent across concurrent tabs and survives web-container recreation.
- API Bearer failures still return 401. Explicit `/auth/refresh` still rotates the
  refresh token; logout/password change still revoke it.

## Модули

| Модуль | Статус | Маршруты |
|--------|--------|----------|
| core.auth | IMPLEMENTED | /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/me, /auth/tokens, /login (SSR), /logout (SSR) |
| core.health | IMPLEMENTED | GET /healthz, /readyz |
| library | PARTIAL | dashboard/catalog/authors/series/import/normalization/sources/service/notifications/settings + OPDS delivery |
| FB2 continuation candidates | IMPLEMENTED, pending deploy | local FB2 extractor → `continuation_link_candidates` → manual title resolver → Work match or review candidate |

## Source monitoring

- `WatchService` выбирает реализацию по `watch_rules.adapter_id`, хранит parser version,
  делает dedup/notifications и общий degraded/backoff.
- `OPDSAdapter`: safe Atom/OPDS parser, conditional GET.
- `AuthorTodayAdapter`: только публичные `/u/<slug>/works`, HTML parser v2;
  bounded traversal страниц (до 50/25 MiB) включает электронные и аудиопубликации,
  quiet baseline/revision events; без auth/private API/content/acquisition. Для
  многостраничного каталога validator первой страницы не сохраняется (ADR-0019/0024).
- `WatchService.request_poll` ставит owner-scoped `poll_watch`, не дублирует
  queued/running job и применяет минутный cooldown. Смена parser version сбрасывает
  conditional validators и создаёт тихий full backfill.
- `/library/service` — owner-scoped read model PostgreSQL jobs, transactional outbox
  и watch rules; payload целиком не выводится, target UUID сокращаются.
- `SourceOnboardingService`: catalog-first orchestration с карточки автора: создаёт
  endpoint/link/rule, группирует серии из persisted observations и по подтверждению
  создаёт/reuses series card с source link. Для missing/ambiguous source work
  выполняет owner-confirmed reconciliation: owner-scoped выбор existing work либо
  явное создание через `CatalogService`, membership и direct work source link
  (ADR-0023).
- Author.Today parser v3 сохраняет stable profile identities соавторов. Poll
  reconciliation считает tracking свойством canonical Series, автоматически
  добавляет второй endpoint к уже отслеживаемому циклу и выполняет только one-hop
  discovery от manually preferred author source. Auto-discovered sources не
  расширяют граф рекурсивно; name-only/conflicting identity не merge-ится
  (ADR-0025).
- `AuthorProvenanceService` строит owner-scoped read-only граф происхождения без
  отдельной таблицы: preferred author source = ручной root; root watch observation
  + stable child profile = direct edge; для старых deduplicated observations edge
  восстанавливается через canonical work coauthorship только к non-preferred AT
  profile. Каждое ребро несёт дедуплицированные книги-evidence и уровень доказательства.
- Тот же read model выделяет неизвестные stable profiles из observations preferred
  roots как `AuthorCandidate`. `/library/authors` показывает их отдельно, focused
  `/authors/candidates/{slug}` раскрывает parent→candidate evidence, а CSRF POST
  повторно валидирует owner-scoped candidate и только затем создаёт author/source/rule
  и canonical WorkAuthor links. Poll reconciliation сам авторов больше не создаёт.
- Для missing/ambiguous source entry карточка серии ведёт на отдельный
  `/series/{series_id}/source-works/{observation_id}/assign`: начальный запрос равен
  source title, дальнейший поиск использует общий normalized title/author/series
  read model. Запись по-прежнему выполняет `reconcile_source_work`.
- `source_profiles.py` — продуктовый реестр guided-профилей автора. Он явно
  различает `watch`, manual `link` и `disabled`; generic link никогда не создаёт
  watch rule. Author endpoints изолированы по owner+author, даже при одинаковом URL.
- `/library/sources/opds` атомарно создаёт/reuses OPDS endpoint и watch rule.
  Toggle/delete endpoint синхронно выключает/удаляет связанное правило; основной UI
  разделён на OPDS и сайты, низкоуровневые статусы скрыты в diagnostics disclosure.
- `SeriesStateService` дедуплицирует ревизии source observations по внешней книге и
  строит сравнение с локальным каталогом: `present`, `missing`, `ambiguous`.
- `WatchService._match_canonical` связывает новую отсутствующую локально книгу с
  принятой серией по точному owner-scoped названию из source metadata; поэтому
  новые релизы продолжают появляться на карточке серии.
- Author.Today сохраняет observations всего авторского каталога для discovery и
  reconciliation, но создаёт `new_release` только если observation связана с
  канонической серией, у которой есть enabled watch-backed metadata source. Явно
  подключённые OPDS-ленты сохраняют feed-wide уведомления.
- `ContinuationLinkService`: не мониторинг источников, а ручная title-only
  проверка ссылки из локального FB2. Перед одним HTML GET проверяет public HTTPS
  host и applicable rules из `robots.txt`; детали — ADR-0021 и runbook.
- `ImportService` ставит каждый `stored_unmatched` item в `core.jobs` как
  `propose_import`; worker вызывает `ProposalService`. Import inbox может разово
  поставить в ту же очередь старые items без `ai_status` (ADR-0022).
- Ручное назначение unmatched item вынесено на
  `/library/import/items/{item_id}/assign`: `CatalogQueries` фильтрует owner-scoped
  каталог по нормализованным title/author/series до лимита результатов. UI
  предлагает либо выбрать результат, либо явно перейти к созданию карточки из
  метаданных; технический UUID пользователю не вводится и не показывается.

## База данных (18 таблиц)

- core: users, api_tokens, audit_log, outbox_events, jobs
- library: authors, author_aliases, works, work_authors, series, series_aliases, series_memberships, source_records, source_author_records, source_endpoints, source_links, watch_rules, source_observations, assets (+work_id, is_preferred), asset_relations, reading_states, import_batches, import_items, duplicate_candidates, continuation_link_candidates, normalization_runs
- Все пользовательские данные: `owner_id UUID → users.id` (FK CASCADE)
