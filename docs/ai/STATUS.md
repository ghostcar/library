# STATUS — фактическое состояние реализации

Обновляется по факту кода, а не намерений. Маркировка: `IMPLEMENTED` / `PARTIAL` / `PLANNED_ONLY` / `ABSENT` / `AMBIGUOUS`.

Последняя проверка: 2026-08-31 (guided source + searchable import assignment: 294 tests + full lint + Chromium green; production remains `1f98181`, schema 0013)

## Фазы мастер-промпта (§20)

| Фаза | Статус | Примечание |
|------|--------|------------|
| Phase 0. Аудит и фиксация источников истины | `IMPLEMENTED` | Аудит, память, дизайн-матрица, ADR-0001..0004 |
| Phase 1. Foundation | `IMPLEMENTED` | config/db/registry/health/auth/audit/outbox/jobs/storage/CI — готово; UI shell — Tailwind отложен (TECH_DEBT#4) |
| Phase 2. Catalog and import | `IMPLEMENTED` | upload (FB2/EPUB/ZIP-архивы), локальные каталоги, дубликаты-кандидаты, каталог UI, review UI; watched inbox — Phase 6 |
| Phase 3. Deterministic normalizer | `IMPLEMENTED` | FB2+EPUB, prose_compact, fingerprints, manifest, review UI, идемпотентность; EPUBCheck — skipped (нет Java) |
| Phase 4. LLM-assisted normalization | `IMPLEMENTED` | auto/best-free, ретрай на cold-start, live propose в проде, кэш, corrections, UI propose/apply |
| Phase 5. Series and reading state | `IMPLEMENTED` | SeriesStateService, история чтения, очередь, dashboard, массовые действия; derived source evidence включено |
| Phase 6. Source monitoring | `PARTIAL` | OPDS/Flibusta, source management и Author.Today public HTML metadata adapter развёрнуты; Litnet намеренно не реализуется (ADR-0020) |
| Phase 7. Delivery (OPDS) | `IMPLEMENTED` | OPDS 1.2 каталог, device-token Basic auth, acquisition+download, search; FBReader smoke — ручной шаг |
| Phase 8. Design convergence | `IMPLEMENTED` | responsive shell, full desktop sidebar, mobile bottom-nav + overflow menu, local SVG icons, themed errors, strict CSP; Chromium smoke desktop/mobile |
| Phase 9. Test VPS | `IMPLEMENTED` | РАЗВЁРНУТО: ghcr.io/ghostcar/library:1f98181, schema 0013, https://library.gorbunovr.ru |

## Компоненты

| Компонент | Статус | Где |
|-----------|--------|-----|
| Память проекта docs/ai | `IMPLEMENTED` | docs/ai/ |
| Core: config (typed, jwt_secret required) | `IMPLEMENTED` | src/portal/core/config |
| Core: database (async engine, session) | `IMPLEMENTED` | src/portal/core/database |
| Core: module registry | `IMPLEMENTED` | src/portal/core/module_registry |
| Core: auth (users, JWT, refresh/device, CSRF+forms, rate limit) | `IMPLEMENTED` | src/portal/core/auth (ADR-0006, CSRF accepts form field) |
| Core: audit log | `IMPLEMENTED` | src/portal/core/audit |
| Core: outbox (transactional) | `IMPLEMENTED` | transactional events, typed registry, exponential retry до 5 попыток, terminal failed |
| Core: jobs (FOR UPDATE SKIP LOCKED + worker) | `IMPLEMENTED` | claim до handler; stale running jobs requeue через 15 мин |
| Core: storage port + local adapter | `IMPLEMENTED` | src/portal/core/storage |
| Frontend CSP / responsive shell | `IMPLEMENTED` | без inline CSS/JS; local SVG sprite; Chromium smoke desktop/mobile |
| Library domain entities | `IMPLEMENTED` | 12 сущностей, VO, события |
| Library ORM + repositories | `IMPLEMENTED` | 13 таблиц + FK owner_id→users |
| Alembic 0001+0013 | `IMPLEMENTED` | Код, Test DB и VPS schema head=0013 |
| Auth SSR (login, защищённая /library, logout, settings) | `IMPLEMENTED` | src/portal/web (password change, CSRF-защищённый logout) |
| Auth API (/auth/*) | `IMPLEMENTED` | register/login/refresh/logout/me/tokens |
| CI (GitHub Actions) | `IMPLEMENTED` | quality (ruff+mypy) + tests (unit+integration+migration) — green |
| UI shell | `IMPLEMENTED` | desktop sidebar + mobile bottom nav + local SVG sprite; локальные CSS components/utilities, без inline CSS |
| Импорт: upload (FB2/EPUB/ZIP) + local dirs | `IMPLEMENTED` | persistent `/data/storage`, ImportService + expand_book_archive; FB2 `title-info` primary, filename fallback (ADR-0007) |
| Каталог UI (список, карточка) | `IMPLEMENTED` | /library/catalog, /library/works/{id} |
| Import inbox UI | `IMPLEMENTED` | /library/import (upload, scan, unmatched, duplicates) |
| Duplicate candidates | `IMPLEMENTED` | exact_content + same_work_format; review — Phase 3 |
| Watched inbox directory | `IMPLEMENTED` | opt-in worker poll; explicit roots+owner; stability window; bounded/idempotent import |
| Нормализатор FB2/EPUB | `IMPLEMENTED` | normalizer/, NormalizationService (ADR-0008) |
| Очередь нормализации + отчёты | `IMPLEMENTED` | /library/normalization, /library/normalization/{id} |
| Download с Content-Disposition | `IMPLEMENTED` | /library/assets/{id}/download |
| Review UI (unmatched, duplicates) | `IMPLEMENTED` | inbox → owner-scoped поиск существующей книги по title/author/series либо явное создание; UUID не показывается |
| AI matching (digest→proposal→apply) | `IMPLEMENTED` | ai/, queued bulk proposal for unmatched imports, idempotent cache and ordered co-authors; ADR-0009/0022; live — нужен валидный ключ |
| Кэш proposals + corrections dataset | `IMPLEMENTED` | ai_proposals, ai_corrections |
| Series state (last/next/missing/status) | `IMPLEMENTED` | SeriesStateService: last_observed, has_new_release, waiting_release, evidence |
| Чтение: действия + история + очередь | `IMPLEMENTED` | ReadingStateService, /library/queue, /library/series |
| Dashboard | `IMPLEMENTED` | /library/ (продолжить/далее/недавние) |
| OPDS source adapter | `IMPLEMENTED` | adapters/opds_adapter.py, conditional GET, XXE-тест |
| Watch rules + scheduler | `IMPLEMENTED` | watch_rules, worker tick 30s, backoff+jitter, degraded |
| In-app уведомления | `IMPLEMENTED` | /library/notifications + счётчик в topbar |
| Author.Today metadata | `IMPLEMENTED` | public `/u/<slug>/works`, conditional GET, quiet baseline/revisions, без auth/API/content; deployed (ADR-0019) |
| Litnet | `ABSENT` | намеренно отключён: пользовательское соглашение запрещает automated collection (ADR-0020) |
| Flibusta OPDS metadata | `IMPLEMENTED` | отдельный профиль поверх OPDS; acquisition=false, фоновые скачивания отсутствуют |
| OPDS 1.2 каталог | `IMPLEMENTED` | /opds (root/new/unread/series/authors/observations/search), ADR-0012 |
| OPDS download | `IMPLEMENTED` | /opds/download/{id}, Content-Disposition, preferred→normalized→original |
| OPDS UI (токены) | `IMPLEMENTED` | /library/opds-settings |
| Settings page (password change) | `IMPLEMENTED` | /library/settings, CSRF-защищённый form POST |
| ZIP archive import | `IMPLEMENTED` | expand_book_archive: ZIP → FB2/EPUB, zip-bomb guards |
| Root redirect (/ → /library/) | `IMPLEMENTED` | src/portal/web/app.py (307 redirect) |
| Design tokens в CSS | `IMPLEMENTED` | static/css/tokens.css + components.css (обе темы) |
| UI kit page | `IMPLEMENTED` | /library/ui-kit (dev-only) |
| Security headers + CSP | `IMPLEMENTED` | SecurityHeadersMiddleware |
| Dockerfile + compose.prod | `IMPLEMENTED` | multi-stage non-root, EPUBCheck jar, package-data; образ в GHCR |
| Backup/restore | `IMPLEMENTED` | scripts/backup.sh, restore.sh; round-trip пройден |
| Nginx конфиг | `IMPLEMENTED` | deploy/nginx/library.conf (применён владельцем) |
| LLM live (auto/best-free) | `IMPLEMENTED` | propose работает в проде; ретрай на cold-start |
| Browser error UX + CSRF forms | `IMPLEMENTED` | 401 → login; portal HTML errors; unsafe library forms CSRF-protected |
| Formal adapter contracts | `IMPLEMENTED` | `application/contracts.py`: capabilities, source/import/notification Protocols, registration validation |
| Abstract source endpoints | `IMPLEMENTED` | product UI разделён на OPDS/сайты; OPDS one-step создаёт endpoint+rule; toggle/delete синхронно управляют правилом; технический CRUD сохранён для диагностики |
| Entity source links | `IMPLEMENTED` | owner-scoped CRUD, preferred/priority и независимое наследование metadata/acquisition: work→series→author→global; UI у author/series/work |
| Author catalog UI | `IMPLEMENTED` | `/library/authors`, именованная карточка автора, произведения и управление источниками |
| Guided source onboarding | `PARTIAL` | локально: реестр профилей на карточке автора; Author.Today автонаблюдается, другой сайт сохраняется как ссылка, Litnet disabled; далее кандидаты циклов, сравнение и searchable reconciliation книг без UUID. Второй разрешённый HTML auto-adapter пока отсутствует (ADR-0023) |
| FB2 continuation-link candidates | `IMPLEMENTED` | local FB2 context extraction → manual HTTPS title check with robots/public-host guards → exact catalog match or review candidate; migration 0013 deployed (ADR-0021/runbook) |

## Инфраструктурные факты

- VPS: разработка идёт на целевой тестовой машине.
- Занятые порты соседей: 8000 (tracker), 5432 (tracker-db), 55433 (pl-multisession-pg), 20128 (OmniRoute), 80/443 (host nginx).
- Наш dev web: 127.0.0.1:8001. Наш PostgreSQL: dev 55440, test 55441 (только localhost).
- DNS `library.gorbunovr.ru`: работает (Cloudflare proxy, Cloudflare DNS). Локальный резолвер VPS может кэшировать negative → проверять через 1.1.1.1 или --resolve.
- Sudo без пароля: нет → изменения /etc/nginx выполняет пользователь.
- `.env`: prod-конфиг (JWT secret, LIBRARY_PG_PASSWORD, AI ключ валиден, модель auto/best-free). В Git не попадает.
