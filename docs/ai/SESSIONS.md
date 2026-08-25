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
