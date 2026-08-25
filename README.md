# Library Portal

Персональная электронная библиотека — первый модуль личного макропортала (Ghostcar).

Мастер-промпт с требованиями: `LIBRARY_PORTAL_MASTER_AGENT_PROMPT_RU.md`.
Память проекта: `docs/ai/` — обязательна к прочтению перед любой задачей (`AGENTS.md`).

## Стек

Python 3.13 · FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL 15 · Jinja2 SSR + HTMX · pytest · Ruff · mypy · Docker Compose

## Быстрый старт (happy path)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env

docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
.venv/bin/alembic upgrade head

scripts/dev.sh          # web на http://127.0.0.1:8001
scripts/lint.sh         # ruff + mypy
scripts/test.sh         # unit + integration (поднимает тестовую БД)
scripts/test.sh --unit-only
```

## Порты (общая VPS, см. ADR-0003)

| Сервис | Адрес | Примечание |
|--------|-------|------------|
| web (dev) | `127.0.0.1:8001` | uvicorn с хоста |
| postgres (dev) | `127.0.0.1:55440` | только localhost |
| postgres (test) | `127.0.0.1:55441` | только localhost, отдельный volume |

На машине также работают tracker (8000, 5432), OmniRoute (20128), pl-multisession-pg (55433) — их не трогать.

## Структура

```text
src/portal/
  core/                  ядро портала: config, database, module_registry
  modules/library/       доменный модуль: domain / application / infrastructure / presentation / adapters
  web/                   app factory
migrations/              Alembic
tests/                   unit / integration
docs/ai/                 память проекта
docs/design/             дизайн-источники и выводы
design/                  референсы (вне Git)
```

## Правила для агентов

См. `AGENTS.md`. Запрещены: push/deploy без явной команды, изменение литературного текста, коммит секретов и книг.
