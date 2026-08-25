# STATUS — фактическое состояние реализации

Обновляется по факту кода, а не намерений. Маркировка: `IMPLEMENTED` / `PARTIAL` / `PLANNED_ONLY` / `ABSENT` / `AMBIGUOUS`.

Последняя проверка: 2026-08-25 (Phase 1 auth, сессия 2)

## Фазы мастер-промпта (§20)

| Фаза | Статус | Примечание |
|------|--------|------------|
| Phase 0. Аудит и фиксация источников истины | `IMPLEMENTED` | Аудит, память, дизайн-матрица, ADR-0001..0004 |
| Phase 1. Foundation | `PARTIAL` | config/db/registry/health/auth/audit/outbox/jobs/storage — готово; UI shell (Tailwind), CI — skeleton; worker-обработчики доменных задач — нет |
| Phase 2. Catalog and import | `PARTIAL` | upload + локальные каталоги (dry-run/apply), дубликаты-кандидаты, каталог UI; watched inbox и review-UI — позже |
| Phase 3. Deterministic normalizer | `PLANNED_ONLY` | — |
| Phase 4. LLM-assisted normalization | `PLANNED_ONLY` | OmniRoute доступен, модель не выбрана |
| Phase 5. Series and reading state | `PLANNED_ONLY` | Доменные основы (ReadingState, SeriesMembership) есть |
| Phase 6. Source monitoring | `PLANNED_ONLY` | — |
| Phase 7. Delivery (OPDS) | `PLANNED_ONLY` | Device-токены уже реализованы в core.auth |
| Phase 8. Design convergence | `PLANNED_ONLY` | Минимальный SSR на inline-токенах Ghostcar |
| Phase 9. Test VPS | `PLANNED_ONLY` | VPS уже целевой; DNS library.gorbunovr.ru отсутствует |

## Компоненты

| Компонент | Статус | Где |
|-----------|--------|-----|
| Память проекта docs/ai | `IMPLEMENTED` | docs/ai/ |
| Core: config (typed, jwt_secret required) | `IMPLEMENTED` | src/portal/core/config |
| Core: database (async engine, session) | `IMPLEMENTED` | src/portal/core/database |
| Core: module registry | `IMPLEMENTED` | src/portal/core/module_registry |
| Core: auth (users, JWT, refresh/device, CSRF, rate limit) | `IMPLEMENTED` | src/portal/core/auth (ADR-0006) |
| Core: audit log | `IMPLEMENTED` | src/portal/core/audit |
| Core: outbox (transactional) | `IMPLEMENTED` | src/portal/core/events |
| Core: jobs (FOR UPDATE SKIP LOCKED + worker) | `IMPLEMENTED` | src/portal/core/jobs |
| Core: storage port + local adapter | `IMPLEMENTED` | src/portal/core/storage |
| Library domain entities | `IMPLEMENTED` | 12 сущностей, VO, события |
| Library ORM + repositories | `IMPLEMENTED` | 13 таблиц + FK owner_id→users |
| Alembic 0001+0002 | `IMPLEMENTED` | migrations/versions/ |
| Auth SSR (login, защищённая /library, logout) | `IMPLEMENTED` | src/portal/web (inline-токены Ghostcar) |
| Auth API (/auth/*) | `IMPLEMENTED` | register/login/refresh/logout/me/tokens |
| CI (GitHub Actions) | `PARTIAL` | lint+mypy+tests; контейнеры — Phase 9 |
| Tailwind/UI shell | `ABSENT` | Phase 2+ (сейчас inline CSS) |
| Импорт: upload + local dirs | `IMPLEMENTED` | ImportService, ADR-0007 |
| Каталог UI (список, карточка) | `IMPLEMENTED` | /library/catalog, /library/works/{id} |
| Import inbox UI | `IMPLEMENTED` | /library/import (upload, scan, unmatched, duplicates) |
| Duplicate candidates | `IMPLEMENTED` | exact_content + same_work_format; review — Phase 3 |
| Watched inbox directory | `ABSENT` | Phase 6 (нужен scheduler) |
| Нормализатор / AI / source adapters / OPDS | `ABSENT` | Phase 3–7 |

## Инфраструктурные факты

- VPS: разработка идёт на целевой тестовой машине.
- Занятые порты соседей: 8000 (tracker), 5432 (tracker-db), 55433 (pl-multisession-pg), 20128 (OmniRoute), 80/443 (host nginx).
- Наш dev web: 127.0.0.1:8001. Наш PostgreSQL: dev 55440, test 55441 (только localhost).
- DNS `library.gorbunovr.ru`: отсутствует (проверено 2026-08-25).
- Sudo без пароля: нет → изменения /etc/nginx выполняет пользователь.
- `.env` создан scripts/dev.sh с сгенерированным JWT_SECRET (в Git не попадает).
