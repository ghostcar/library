# Sessions

Краткие факты завершённых сессий. Без chain-of-thought.

## Сессия 1 — 2026-08-25 — Phase 0 + первый slice (Phase 1)

- Прочитан мастер-промпт целиком; окружение VPS проаудировано (соседи: tracker:8000, pg:5432/55433, OmniRoute:20128, host nginx 80/443).
- Решения с пользователем: venv на системном Python 3.13 (вместо 3.12), design/ в .gitignore, dev-порт 8001, git init + remote (без push).
- Репозиторий github.com/ghostcar/library подтверждён пустым → greenfield.
- Дизайн-архивы распакованы в design/; определён primary: ghostcar-design tokens + stitch_library экраны (ADR-0004).
- Создана память docs/ai (полный скелет), AGENTS.md, ADR-0001..0005.
- Реализован первый slice: core (config/database/module_registry/app factory/health), library domain+infrastructure (канонические сущности), Alembic 0001, репозитории, тесты.
- Проверено: ruff, mypy, pytest (результаты в TaskContext tasks/phase-0-foundation.md).
- Не выполнено (по правилам): git push, deploy, изменения /etc/nginx.

## Сессия 2 — 2026-08-25 — Phase 1: общая авторизация макропортала

- Реализован core.auth по ADR-0006: users/api_tokens/audit_log, argon2id, JWT HS256 (интерфейс готов к RS256/JWKS), refresh-ротация, device-токены (OPDS-ready), CSRF double-submit, rate limit, bootstrap-регистрация.
- core.audit: failure-события пишутся отдельной транзакцией (иначе откатываются вместе с основной — найдено тестом).
- core.events (outbox) + core.jobs (SKIP LOCKED + worker skeleton) + core.storage (content-addressed, originals immutable).
- Миграция 0002: 5 таблиц core + FK owner_id→users.id на 12 таблицах library.
- SSR: /login, защищённая /library, /logout на inline-токенах Ghostcar (Astral Gatekeeper).
- CI skeleton (.github/workflows/ci.yml): ruff+mypy+unit+integration+migration check.
- Найдено/исправлено: provide_session с параметром-фабрикой ломал FastAPI (перенесён в web/deps.py с Request); PK без default в core ORM; users отсутствовал в TRUNCATE-фикстуре.
- Проверено: ruff/mypy clean, pytest 100 passed, smoke на 127.0.0.1:8001 (bootstrap → login → защищённая страница → refresh → anon register 403).
- Не выполнено: push, deploy (по правилам).

## Сессия 3 — 2026-08-25 — Phase 2: каталог и импорт (+ первый push)

- Push в origin/main выполнен по явной команде пользователя (6 коммитов Phase 0+1).
- Импортный конвейер по ADR-0007: домен ImportBatch/ImportItem/DuplicateCandidate, детекция формата по содержимому, deterministic filename parser v1, ImportService (quarantine→dedup→original→match→outbox-события), scan локальных каталогов с dry-run/apply.
- Каталог UI: /library/catalog, /library/works/{id}, /library/import (upload/scan/inbox).
- Миграция 0003: import_batches, import_items, duplicate_candidates, assets.work_id (+ FK в ORM-метаданных, именованный fk_assets_work).
- Найдено/исправлено: CatalogService не переиспользовал Work по title+авторам (плодил дубликаты); find_by_title не грузил авторов; NoDecode для LIBRARY_IMPORT_ROOTS; JSONB server_default через text().
- Проверено: lint clean, mypy clean, 126 tests passed, smoke на :8001 (login→upload→catalog→inbox→storage).
- Push: выполнен в конце сессии (команды пользователя).
