# STATUS — фактическое состояние реализации

Обновляется по факту кода, а не намерений. Маркировка: `IMPLEMENTED` / `PARTIAL` / `PLANNED_ONLY` / `ABSENT` / `AMBIGUOUS`.

Последняя проверка: 2026-08-25 (Phase 1 auth, сессия 2)

## Фазы мастер-промпта (§20)

| Фаза | Статус | Примечание |
|------|--------|------------|
| Phase 0. Аудит и фиксация источников истины | `IMPLEMENTED` | Аудит, память, дизайн-матрица, ADR-0001..0004 |
| Phase 1. Foundation | `PARTIAL` | config/db/registry/health/auth/audit/outbox/jobs/storage — готово; UI shell (Tailwind), CI — skeleton; worker-обработчики доменных задач — нет |
| Phase 2. Catalog and import | `PARTIAL` | upload + локальные каталоги (dry-run/apply), дубликаты-кандидаты, каталог UI; watched inbox и review-UI — позже |
| Phase 3. Deterministic normalizer | `IMPLEMENTED` | FB2+EPUB, prose_compact, fingerprints, manifest, review UI, идемпотентность; EPUBCheck — skipped (нет Java) |
| Phase 4. LLM-assisted normalization | `PARTIAL` | digest/schema/adapter/policy/cache/corrections готовы; live-вызовы заблокированы невалидным ключом (OPEN_QUESTIONS #3); TOC-proposal — Phase 8 |
| Phase 5. Series and reading state | `IMPLEMENTED` | SeriesStateService, история чтения, очередь, dashboard, массовые действия; has_new_release — Phase 6 |
| Phase 6. Source monitoring | `PARTIAL` | OPDS-адаптер, scheduler/backoff/degraded, watch rules, in-app уведомления; AT/Litnet/Flibusta — disabled до исследования (ADR-0011) |
| Phase 7. Delivery (OPDS) | `IMPLEMENTED` | OPDS 1.2 каталог, device-token Basic auth, acquisition+download, search; FBReader smoke — ручной шаг |
| Phase 8. Design convergence | `PARTIAL` | tokens.css/components.css, UI kit dev-only, security headers, a11y-база; Tailwind-сборка и visual regression — TECH_DEBT |
| Phase 9. Test VPS | `PARTIAL` | Dockerfile+compose.prod+nginx+backup/restore готовы и проверены локально; GHCR push и живой деплой — после DNS и команды владельца |

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
| Нормализатор FB2/EPUB | `IMPLEMENTED` | normalizer/, NormalizationService (ADR-0008) |
| Очередь нормализации + отчёты | `IMPLEMENTED` | /library/normalization, /library/normalization/{id} |
| Download с Content-Disposition | `IMPLEMENTED` | /library/assets/{id}/download |
| Review UI (unmatched, duplicates) | `IMPLEMENTED` | assign/resolve на /library/import |
| AI matching (digest→proposal→apply) | `IMPLEMENTED` | ai/, ADR-0009; fake-server тесты; live — нужен валидный ключ |
| Кэш proposals + corrections dataset | `IMPLEMENTED` | ai_proposals, ai_corrections |
| Series state (last/next/missing/status) | `IMPLEMENTED` | SeriesStateService (ADR-0010) |
| Чтение: действия + история + очередь | `IMPLEMENTED` | ReadingStateService, /library/queue, /library/series |
| Dashboard | `IMPLEMENTED` | /library/ (продолжить/далее/недавние) |
| OPDS source adapter | `IMPLEMENTED` | adapters/opds_adapter.py, conditional GET, XXE-тест |
| Watch rules + scheduler | `IMPLEMENTED` | watch_rules, worker tick 30s, backoff+jitter, degraded |
| In-app уведомления | `IMPLEMENTED` | /library/notifications + счётчик в topbar |
| Author.Today/Litnet/Flibusta | `ABSENT` | отключены в реестре с причинами (ADR-0011, OPEN_QUESTIONS #9/#10) |
| OPDS 1.2 каталог | `IMPLEMENTED` | /opds (root/new/unread/series/authors/observations/search), ADR-0012 |
| OPDS download | `IMPLEMENTED` | /opds/download/{id}, Content-Disposition, preferred→normalized→original |
| OPDS UI (токены) | `IMPLEMENTED` | /library/opds-settings |
| Design tokens в CSS | `IMPLEMENTED` | static/css/tokens.css + components.css (обе темы) |
| UI kit page | `IMPLEMENTED` | /library/ui-kit (dev-only) |
| Security headers + CSP | `IMPLEMENTED` | SecurityHeadersMiddleware |
| Dockerfile + compose.prod | `IMPLEMENTED` | сборка проверена локально; GHCR — по команде |
| Backup/restore | `IMPLEMENTED` | scripts/backup.sh, restore.sh; round-trip пройден |
| Nginx конфиг | `IMPLEMENTED` | deploy/nginx/library.conf (применяет владелец) |
| Нормализатор / AI / source adapters / OPDS | `ABSENT` | Phase 3–7 |

## Инфраструктурные факты

- VPS: разработка идёт на целевой тестовой машине.
- Занятые порты соседей: 8000 (tracker), 5432 (tracker-db), 55433 (pl-multisession-pg), 20128 (OmniRoute), 80/443 (host nginx).
- Наш dev web: 127.0.0.1:8001. Наш PostgreSQL: dev 55440, test 55441 (только localhost).
- DNS `library.gorbunovr.ru`: отсутствует (проверено 2026-08-25).
- Sudo без пароля: нет → изменения /etc/nginx выполняет пользователь.
- `.env` создан scripts/dev.sh с сгенерированным JWT_SECRET (в Git не попадает).
