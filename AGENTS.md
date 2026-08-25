# AGENTS.md — Library Portal

Обязательные правила для любого агента, работающего в этом репозитории.

## Порядок чтения памяти (pre-fetch, обязателен перед любой задачей)

1. `docs/ai/README.md`
2. `docs/ai/STATUS.md`
3. `docs/ai/DECISIONS.md` и релевантные ADR из `docs/ai/adr/`
4. `docs/ai/OPEN_QUESTIONS.md`, `docs/ai/TECH_DEBT.md`
5. Поиск символов через `rg` / LSP (CodeGraph/Serena, если доступны)
6. Существующие тесты по затрагиваемым модулям
7. Создать/обновить TaskContext в `docs/ai/tasks/`

Канонический корень памяти: `docs/ai/` (см. `docs/ai/MEMORY_MANIFEST.yaml`).

## Ключевые факты

- Проект: модуль «Библиотека» персонального макропортала (greenfield, репозиторий был пуст).
- Мастер-промпт: `LIBRARY_PORTAL_MASTER_AGENT_PROMPT_RU.md` — источник требований.
- Стек: Python 3.13 (системный, venv `.venv/`), FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 15+, Jinja2 SSR + HTMX, Tailwind, pytest, Ruff, mypy, Docker Compose.
- Разработка ведётся прямо на целевой тестовой VPS. На той же машине уже работают другие сервисы: tracker (docker, 127.0.0.1:8000), OmniRoute (127.0.0.1:20128), cypht. Порт 5432 и 55433 заняты другими PostgreSQL.
- Dev-порт web: `127.0.0.1:8001`. PostgreSQL контейнера library НЕ публикует порт на хост.
- Домен тестового контура: `library.gorbunovr.ru` (DNS-записи пока нет, Cloudflare → host nginx → 127.0.0.1:8001).
- Дизайн: система «Ghostcar / Astral Gatekeeper» (тёмная) + «Solar Mode» (светлая). Источники в `design/` (вне Git), выводы — в `docs/design/`.
- Секреты: только в `.env` (gitignored). Ключ OmniRoute в Git не попадает.

## Запрещено (кратко; полный список — мастер-промпт §23)

- `git push`, merge, deploy, изменение VPS-инфраструктуры — только по явной команде пользователя.
- Изменение литературного текста книг, удаление оригиналов.
- Коммит секретов, книг, пользовательских данных.
- Деструктивные git-команды, переписывание истории main.
- Начало задачи без чтения памяти проекта.
