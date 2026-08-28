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
| 0011 | accepted | Source monitoring: OPDS-адаптер реализован, AT/Litnet/Flibusta отключены до исследования; scheduler+backoff+degraded; уведомления только на переходы |
| 0012 | accepted | OPDS 1.2 delivery: Basic auth с device token (пароль), сериализатор отдельным модулем, preferred assets в acquisition |
| 0013 | accepted | Токены в CSS (обе темы) + UI kit dev-only; security headers/CSP; Docker-образ multi-stage non-root; backup/restore round-trip |
| 0014 | accepted | Модель auto/best-free и деплой в GHCR |
| 0015 | accepted | Audit remediation: HTML errors, transactional outbox, recoverable jobs, local SVG icons |
| 0016 | accepted | Typed outbox registry, bounded exponential retry и migration 0009 |
| 0017 | accepted | Formal adapter contracts и explicit capability registration |
| 0018 | accepted | Flibusta подключается как OPDS metadata-only профиль без фонового acquisition |
| 0019 | accepted | Author.Today: публичный HTML metadata-only, quiet baseline, revision events, без auth/API/content |
| 0020 | accepted | Litnet: автоматическое HTML-наблюдение не включать — соглашение запрещает automated collection |
| 0021 | accepted | FB2 continuation links: локальное evidence → ручная title-only проверка → review candidate, без автосоздания книги |
