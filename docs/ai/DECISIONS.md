# Decisions Index

Индекс архитектурных решений. Детали — в `adr/`.

| ADR | Статус | Заголовок |
|-----|--------|-----------|
| 0001 | accepted | Greenfield: модульный монолит, ядро портала + модуль library |
| 0002 | accepted | Стек и версии: Python 3.13, FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 15 |
| 0003 | accepted | Среда разработки на целевой VPS: порты, изоляция от соседних сервисов |
| 0004 | accepted | Дизайн: Ghostcar/Astral Gatekeeper + Solar Mode как источник истины |
| 0005 | accepted | Управление зависимостями: venv на системном Python, pyproject.toml, pip |
| 0006 | accepted | Общая авторизация макропортала в core.auth (JWT + refresh/device токены, готовность к RS256/JWKS) |
| 0007 | accepted | Импортный конвейер: quarantine→детекция→dedup→original→deterministic matching; дубликаты — кандидаты, не удаления |
| 0008 | accepted | Детерминированный нормализатор: prose_compact, fingerprints-инвариант текста, manifest, идемпотентность |
| 0009 | accepted | LLM-assisted matching через OmniRoute: digest без текста книги, строгая schema, policy engine, кэш, graceful fallback |
| 0010 | accepted | Производное состояние циклов: caught_up ≠ completed, user override главнее, unread→read разрешён напрямую |
