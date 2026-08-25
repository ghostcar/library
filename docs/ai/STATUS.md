# STATUS — фактическое состояние реализации

Обновляется по факту кода, а не намерений. Маркировка: `IMPLEMENTED` / `PARTIAL` / `PLANNED_ONLY` / `ABSENT` / `AMBIGUOUS`.

Последняя проверка: 2026-08-25 (Phase 0 + первый slice, сессия 1)

## Фазы мастер-промпта (§20)

| Фаза | Статус | Примечание |
|------|--------|------------|
| Phase 0. Аудит и фиксация источников истины | `IMPLEMENTED` | Аудит, память, дизайн-матрица, ADR-0001..0005 |
| Phase 1. Foundation | `PARTIAL` | config/database/registry/app/health готовы; auth, outbox/jobs, storage, UI shell — нет |
| Phase 2. Catalog and import | `PLANNED_ONLY` | Канонические сущности — в первом slice, импорт — нет |
| Phase 3. Deterministic normalizer | `PLANNED_ONLY` | — |
| Phase 4. LLM-assisted normalization | `PLANNED_ONLY` | OmniRoute доступен, модель не выбрана |
| Phase 5. Series and reading state | `PLANNED_ONLY` | — |
| Phase 6. Source monitoring | `PLANNED_ONLY` | — |
| Phase 7. Delivery (OPDS) | `PLANNED_ONLY` | — |
| Phase 8. Design convergence | `PLANNED_ONLY` | Дизайн-источники распакованы и инвентаризированы |
| Phase 9. Test VPS | `PLANNED_ONLY` | VPS уже целевой; DNS library.gorbunovr.ru отсутствует |

## Компоненты

| Компонент | Статус | Где |
|-----------|--------|-----|
| Память проекта docs/ai | `IMPLEMENTED` | docs/ai/ |
| AGENTS.md | `IMPLEMENTED` | корень |
| Дизайн-инвентаризация | `PARTIAL` | docs/design/DESIGN_SOURCE_OF_TRUTH.md |
| Design tokens (перенос в код) | `PLANNED_ONLY` | — |
| pyproject + venv + quality gates | `IMPLEMENTED` | pyproject.toml |
| Core: config | `IMPLEMENTED` | src/portal/core/config |
| Core: database | `IMPLEMENTED` | src/portal/core/database |
| Core: module registry | `IMPLEMENTED` | src/portal/core/module_registry |
| App factory + health | `IMPLEMENTED` | src/portal/web/ |
| Library domain entities | `IMPLEMENTED` | src/portal/modules/library/domain/ (12 сущностей, VO, события) |
| Library ORM + repositories | `IMPLEMENTED` | 13 таблиц, 6 репозиториев, CatalogService |
| Alembic миграция 0001 | `IMPLEMENTED` | migrations/versions/0001_library_canonical_core.py |
| Тесты (unit+integration) | `IMPLEMENTED` | 52 passed; интеграционные на PostgreSQL 15 |
| Auth | `ABSENT` | Phase 1+ |
| Импорт файлов | `ABSENT` | Phase 2 |
| Нормализатор | `ABSENT` | Phase 3 |
| AI adapter | `ABSENT` | Phase 4 |
| Series state | `ABSENT` | Phase 5 |
| Source adapters | `ABSENT` | Phase 6 |
| OPDS | `ABSENT` | Phase 7 |
| Docker Compose dev | `IMPLEMENTED` | compose.dev.yaml |
| CI (GitHub Actions) | `ABSENT` | после первого push |

## Инфраструктурные факты

- VPS: разработка идёт на целевой тестовой машине.
- Занятые порты соседей: 8000 (tracker), 5432 (tracker-db), 55433 (pl-multisession-pg), 20128 (OmniRoute), 80/443 (host nginx).
- Наш dev web: 127.0.0.1:8001. Наш PostgreSQL: без публикации порта на хост.
- DNS `library.gorbunovr.ru`: отсутствует (проверено 2026-08-25).
- Sudo без пароля: нет → изменения /etc/nginx выполняет пользователь.
