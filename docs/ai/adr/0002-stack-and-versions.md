# ADR-0002: Стек и версии

Статус: accepted
Дата: 2026-08-25

## Контекст

Мастер-промпт §3 задаёт технологический контур для greenfield. Система имеет Python 3.13.5; промпт предпочитает 3.12, но допускает 3.11+ при совместимости зависимостей. Пользователь принял решение: использовать актуальный системный Python (3.13) в venv; промпт признан излишне консервативным.

## Решение

- Python 3.13 (системный, venv `.venv/`; в Docker — `python:3.13-slim`).
- FastAPI + Uvicorn, async endpoints.
- Pydantic v2 (+ pydantic-settings для typed config).
- PostgreSQL 15+ (контейнер `postgres:15-alpine`), SQLAlchemy 2 async + asyncpg, Alembic.
- Jinja2 SSR + HTMX; Tailwind CSS (сборка добавляется при появлении UI, Phase 1+).
- pytest + pytest-asyncio; Ruff; mypy (выбран mypy, не Pyright).
- openai-compatible SDK для AIAdapter (Phase 4).
- Docker Compose; nginx — только как host reverse proxy на VPS (конфиг в deploy/), отдельный контейнер nginx не нужен.
- lxml + defusedxml, Pillow, EPUBCheck — при появлении нормализатора (Phase 3).
- Зависимости: `pyproject.toml` + pip (см. ADR-0005).

## Отклонения от промпта

- Python 3.13 вместо предпочтительного 3.12 — решение пользователя (2026-08-25), риск несовместимости отдельных пакетов оценивается при добавлении зависимостей.
- uv не используется: пользователь выбрал обычный venv на системном Python.
