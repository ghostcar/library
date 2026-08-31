# Sessions

Краткие факты завершённых сессий. Без chain-of-thought.

## Сессия 33 — 2026-08-31 — массовый AI-разбор и соавторы

- По production-логам установлена причина 500 при повторном ручном разборе:
  `uq_ai_proposals_cache` при конкурентной/повторной вставке cache row.
- Cache write заменён на PostgreSQL `ON CONFLICT DO NOTHING`; новый unmatched
  import получает фоновый job `propose_import`, а старые записи можно поставить
  одной командой «Разобрать всё» без дублирования уже queued/reviewed items.
- LLM schema и review form поддерживают упорядоченный список авторов; каталог
  сохраняет отдельных `WorkAuthor` для каждого имени, legacy `author` совместим.
- Проверки: Ruff/mypy, 16 unit и 10 AI integration tests — green; rollout
  зафиксирован в сессии 34.

## Сессия 34 — 2026-08-31 — rollout bulk AI import

- Опубликован `ghcr.io/ghostcar/library:949314d`; перед rollout создан и проверен
  backup `*-20260831-021217.*`.
- Миграция `0012 → 0013` применена одноразовым контейнером до restart web/worker.
  Health/ready = 200, anonymous `/library/` = 303.
- Семь исторических unmatched imports пользователя поставлены одной операцией в
  `propose_import`: worker завершил все, `review_ready=7`, cache conflict не возник.

## Сессия 35 — 2026-08-31 — storage recovery safeguard

- После обнаружения потери originals в mutable container layer deployed
  `1f98181`: web и worker принудительно используют volume `/data/storage`.
- Upload picker принимает `.fb2.zip`; re-upload missing content-addressed
  original restores объект вместо простого duplicate rejection.
- FB2 `title-info` (authors/title/sequence) стал primary deterministic evidence;
  broken filename — только fallback. Health/ready и auth redirect прошли.

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

## Сессия 3 — 2026-08-25 — Phase 2: каталог и импорт (+ первый push)

- Push в origin/main выполнен по явной команде пользователя (6 коммитов Phase 0+1).
- Импортный конвейер по ADR-0007: домен ImportBatch/ImportItem/DuplicateCandidate, детекция формата по содержимому, deterministic filename parser v1, ImportService (quarantine→dedup→original→match→outbox-события), scan локальных каталогов с dry-run/apply.
- Каталог UI: /library/catalog, /library/works/{id}, /library/import (upload/scan/inbox).
- Миграция 0003: import_batches, import_items, duplicate_candidates, assets.work_id (+ FK в ORM-метаданных, именованный fk_assets_work).
- Найдено/исправлено: CatalogService не переиспользовал Work по title+авторам (плодил дубликаты); find_by_title не грузил авторов; NoDecode для LIBRARY_IMPORT_ROOTS; JSONB server_default через text().
- Проверено: lint clean, mypy clean, 126 tests passed, smoke на :8001 (login→upload→catalog→inbox→storage).
- Push: выполнен в конце сессии (команды пользователя).

## Сессия 4 — 2026-08-25 — Phase 3: детерминированный нормализатор

- Нормализатор по ADR-0008: FB2 (удаление body-изображений/binaries, пустых обёрток, metadata/section-id/TOC-заголовки), EPUB (repack mimetype-first, cover-only, orphans), cover optimizer (Pillow, JPEG/PNG, 1600px).
- Fingerprints v1: visible-text (контракт канонизации задокументирован в fingerprints.py), structure, images, chapters; инвариант текста проверяется на каждом прогоне.
- NormalizationService: конвейер §7.2, manifest §7.7, идемпотентность через unique partial index; failure фиксируется в БД до raise (урок Phase 1 повторён).
- Инфра: миграция 0004 (normalization_runs + assets.is_preferred), worker handler `normalize`, реестр ORM-моделей core/database/models.py (FK-резолюция в worker'е).
- UI: очередь+отчёт нормализации, «Нормализовать»/«Скачать» на карточке, download с Content-Disposition, review (assign unmatched, resolve duplicates).
- Найдено/исправлено: binary-элементы попадали в visible-text; worker TimeoutError на пустой очереди; request_normalization не находил run в состоянии received; Jinja2 не знает str().
- EPUBCheck: Java на VPS нет → валидация помечена skipped (TECH_DEBT).
- Проверено: lint/mypy clean, 146 tests, smoke через реального воркера (upload→normalize→derivative_ready→download→prefer).

## Сессия 5 — 2026-08-25 — Phase 4: LLM-assisted matching

- ADR-0009: OmniRouteAdapter (httpx, без tools), MatchProposal (строгая schema + 1 repair), DigestBuilder (без текста книги, hard cap), PolicyEngine (auto/review/fallback, защита от чужих UUID), ProposalService (кэш ai_proposals, коррекции ai_corrections).
- Миграция 0005. UI: propose/apply/apply-auto, шаблон proposal.html с предзаполнением.
- Подтверждён факт: ключ промпта невалиден для completions (AUTH_002) — OPEN_QUESTIONS #3; всё построено на graceful degradation.
- Тесты: 15 unit (schema/repair/digest/policy) + 7 integration на fake OpenAI-совместимом сервере (валидный/кэш/битый JSON/недоступен/без ключа/кириллица-форма/инъекция).
- Найдено/исправлено: Request-аннотации в fake-сервере не резолвились из-за __future__ annotations (импорт в функцию); ai_proposals/ai_corrections отсутствовали в TRUNCATE-фикстуре; curl -d без URL-encoding давал mojibake (сервер корректен — регрессионный тест добавлен).
- Проверено: lint/mypy clean, 168 tests, smoke: fallback при отсутствии ключа + ручное применение с кириллицей.
- Push: выполнен в конце сессии.

## Сессия 6 — 2026-08-25 — Phase 5: series/reading state

- ADR-0010: DerivedSeriesState (on-read вычисление), caught_up≠completed, override главнее, missing_indices только для целых индексов.
- ReadingStateService: валидированные переходы + история (reading_state_history), bulk, очередь (in_progress→planned→standalone), события outbox.
- Миграция 0006: reading_state_history, series_user_states.
- UI: dashboard (/), /library/queue, /library/series(+{id}), история чтения, кнопки действий на карточке произведения.
- Домен изменён: unread→read разрешён (главная мобильная кнопка §10.2) — обновлены тесты домена.
- Найдено/исправлено: ReadingStateModel не импортирован в reading_queue; planned-циклы не попадали в очередь; серия тестов чинила мутации тест-кода (work_ids/series_id путаница).
- Проверено: lint/mypy clean, 199 tests, smoke: 3 тома → mark read → dashboard «далее том 02».

## Сессия 7 — 2026-08-26 — починка CI

- CI падала с первого push. Три причины, устранены:
  1) .gitignore `storage/` матчил src/portal/core/storage/ — пакет адаптера хранилища вообще не был закоммичен (ModuleNotFoundError в CI); паттерны заанкорены: /storage/, /data/.
  2) lxml-stubs ставился руками на VPS, но отсутствовал в dev-зависимостях — mypy в CI падал на normalizer.
  3) CI postgres стартует пустым — миграции не применялись перед integration; добавлен шаг `alembic upgrade head` + усилен migration check до downgrade base → upgrade head round-trip.
- Тест jwt_secret сделан env-proof (CI экспортирует LIBRARY_JWT_SECRET глобально).
- Проверено: CI run 32924042932 — quality: success, tests: success.

## Сессия 8 — 2026-08-26 — Phase 6: source monitoring

- ADR-0011: OPDS adapter (Atom, safe-parser, conditional GET, size guard), реестр адаптеров с capabilities (OPDS вкл; AT/Litnet/Flibusta disabled с причинами), watch_rules+состояние опроса, scheduler tick в worker (30s), backoff 5м×2^n+jitter cap 6ч, degraded после 2 неудач, observations с unique-дедупом, уведомления на переходах.
- Миграция 0007: watch_rules, source_observations, notifications.
- UI: /library/sources (адаптеры+правила), /library/notifications, счётчик в topbar.
- Тесты: 10 unit (парсинг/XXE/backoff/реестр) + 5 integration на fake OPDS (poll→dedup→notify, 304, degraded-once, HTTP-управление, изоляция).
- Smoke через реального воркера: rule → schedule_due → poll ok → «Новая публикация».
- Найдено: персистентный shell держал LIBRARY_TEST_DATABASE_URL — smoke шёл в тестовую БД (лечится env -u).
- Проверено: lint/mypy clean, 214 tests.

## Сессия 9 — 2026-08-26 — Phase 7: OPDS delivery

- ADR-0012: сериализатор OPDS 1.2 отдельным модулем (dict→XML), Basic auth с device token в пароле (JWT не принимается), OpdsCatalogService (recent/unread/series/authors/search/observations), download с preferred-приоритетом, OpenSearch.
- UI: /library/opds-settings (токен показывается один раз, отзыв).
- Тесты: 4 unit сериализатора + 7 integration (Basic/Bearer, отзыв→401, JWT-не-токен, фиды, download+Content-Disposition, search, owner isolation).
- Найдено/исправлено: lxml nsmap требует None для default ns (пробел в стабах); двойной xmlns в OpenSearch; httpx-Response в fake-роутах.
- Smoke: root→series→acquisition→download с Content-Disposition, search по автору/названию, no-auth 401. FBReader — ручная проверка пользователя.
- Проверено: lint/mypy clean, 225 tests.

## Сессия 10 — 2026-08-26 — Phase 8 (design/hardening) + Phase 9 prep

- tokens.css (Astral+Solar из ghostcar токенов) + components.css; base.html без inline-стилей; StaticFiles; UI kit dev-only.
- SecurityHeadersMiddleware (CSP с inline-styles переходно), skip-link, focus-visible, color-scheme.
- Dockerfile multi-stage non-root healthcheck; compose.prod.yaml; nginx conf; backup/restore с round-trip (29 таблиц); runbook.
- Найдено/исправлено: httpx в dev-зависимостях при использовании в prod-коде (образ не собирался); ui-kit искал base.html в одной папке; backup-контейнер параметризован (LIBRARY_PG_CONTAINER).
- GHCR push не выполнялся (требуется явная команда владельца, §15.4).
- Проверено: lint/mypy clean, 225 tests, docker build OK, image imports OK, headers/static/ui-kit smoke OK.

## Сессия 11 — 2026-08-26 — закрытие долгов перед деплоем

- Lock: requirements.lock (pip-compile), Dockerfile ставит из лока (--no-deps для проекта), scripts/update-lock.sh. OQ#1 закрыт.
- Warnings: 156 → 0 (длинные JWT-секреты во всех тестах, httpx cookies через client.cookies). TECH_DEBT#6 закрыт.
- EPUBCheck: jar 5.2.1 в Docker-образе (+JRE), epubcheck.py runner (availability/parse/invocation), результат в manifest, errors → run failed; вне образа — skipped. §14.1 выполнен.
- Retention: LIBRARY_AUDIT_RETENTION_DAYS / OUTBOX_RETENTION_DAYS, worker каждые 6ч. OQ#8 закрыт.
- Тема: переключатель Astral/Solar (theme.js, CSP-safe), default Astral. OQ#6 закрыт. OQ#5 закрыт (main-only).
- Rate limiter: принято как есть (деплой = 1 процесс). TECH_DEBT#5 закрыт с триггером на будущее.
- Проверено: lint/mypy clean, 229 passed, 0 warnings.

## Сессия 12 — 2026-08-26 — модель + DEPLOY

- Модель: auto/best-free (протестированы glm-5.2:free 429, qwen3-next 503, gemma SSE; auto-free стабилен). Адаптер: stream:false + 1 ретрай. ADR-0014.
- GHCR: gh auth refresh write:packages → docker login → push a560f76 → fe30eb4 (migrations в образ) → f6b5f0e (package-data: templates/static) → a19d030 (ретрай).
- Деплой: backup pre-deploy → compose.prod up → restore (29 таблиц, 0007) → smoke. Инциденты: StaticFiles без package-data; SIGPIPE на restore; локальный DNS negative cache (--resolve обход).
- Внешний smoke: https://library.gorbunovr.ru — healthz/login/static/CSP ОК. LLM live: propose → proposal (Громыко/Ведьма-хозяйка) → review.
- OQ#2/#3 закрыты. DEPLOYMENT_STATE обновлён.

## Сессия 13 — 2026-08-26 — settings + ZIP import + security fixes

- Страница настроек: /library/settings, смена пароля (POST /library/settings/password), CSRF double-submit через form-field + cookie (обход ограничения header-only для SSR форм).
- Logout CSRF: добавлена проверка CSRF-токена в logout_submit (раньше дыра — любой сайт мог вылогинить). CSRF-токен в hidden field формы.
- Settings + logout ссылки в topbar на всех страницах (base.html).
- Root redirect: / → 307 → /library/ (до этого FastAPI отдавал 404 JSON).
- ZIP-импорт: expand_book_archive() распаковывает ZIP (не EPUB) в отдельные FB2/EPUB файлы. Защита от zip-bombs: ≤100 entries, ≤200 MiB/entry, ≤500 MiB total. Сканирование локальных каталогов подхватывает .zip.
- Тесты: 23 новых (7 settings + 12 expand_archive + 4 zip_import), итого 252.
- Деплой: образ 053c145, git main @ c363ef7.

## Сессия 14 — 2026-08-27 — remediation полного аудита

- Browser UX: вложенные `/library/*` без сессии перенаправляются на login; portal 4xx/5xx получают тематическую HTML-страницу, API сохраняет JSON.
- CSRF распространён на все unsafe library routes и SSR-формы; `back` redirect ограничен локальным `/library/`.
- Outbox переведён на транзакцию use case и обработку worker; jobs выполняются после commit claim и восстанавливаются из stale running; retention исправлен на async.
- Upload читается чанками с ранним лимитом; локальный scan хеширует потоково. Source uniqueness стала owner-scoped (Alembic 0008).
- Frontend shell: desktop sidebar, mobile bottom navigation, локальный SVG icon sprite по Material vocabulary дизайн-шаблонов, поиск каталога.
- Пустые backups и stale build/lib убраны из Git index и добавлены в `.gitignore`; история не переписывалась.
- Проверено: Ruff format/check, mypy и git diff --check clean; 257 tests passed.

## Сессия 15 — 2026-08-27 — frontend hardening + watched inbox

- Inline styles удалены из SSR; CSP усилена до local-only scripts/styles.
- Chromium smoke проверяет desktop/mobile navigation, icons и overflow.
- Watched inbox: opt-in config, explicit owner email и roots, stability window,
  bounded batch, idempotency по content hash, source provenance `inbox`.
- Исходные файлы watched inbox остаются на месте.
- Проверено: lint/mypy, diff check, 262 tests.

## Сессия 16 — 2026-08-27 — audit remediation deploy

- Коммиты `bd016d3`, `87c3459`, `b7351b2`; опубликован immutable GHCR tag `b7351b2`.
- До переключения создан и проверен backup `20260827-023750`; применена миграция 0008.
- Исправлены deploy blockers: Alembic files в runtime image, worker healthcheck,
  prod-volume backup/restore, SHA-tag injection, packaged SVG sprite.
- Smoke: local/external health, ready, HTML auth redirect, CSP, icons, worker, EPUBCheck — OK.

## Сессия 17 — 2026-08-28 — reproducible browser handoff

- Добавлены `package.json`/`package-lock.json` с pinned `playwright@1.62.1`.
- `scripts/test-browser.sh` больше не использует tracker checkout или внешний
  `NODE_PATH`; после `npm ci` запускается локальный `npm run test:browser`.
- Проверено: Chromium smoke desktop 1280×800 и mobile 390×844 — OK.

## Сессия 18 — 2026-08-28 — typed outbox retries

- Добавлены explicit event handler registry и unknown-event rejection.
- Outbox получил durable `next_attempt_at`, exponential backoff и terminal
  `failed` после 5 попыток (Alembic 0009).
- `scripts/test.sh` теперь применяет `alembic upgrade head` перед тестами.
- Проверено: lint clean, targeted 30 passed, полный набор 263 passed.
- Outbox-срез ещё не развёрнут; текущий Test VPS остаётся на `b7351b2`.

## Сессия 19 — 2026-08-28 — source observation links + deploy

- Наблюдения источников получают owner-scoped nullable links на Work/Series и match evidence;
  неоднозначные совпадения не связываются.
- SeriesStateService вычисляет `last_observed`, `has_new_release`, `waiting_release`.
- Проверено: полный набор 263 теста, Ruff и diff-check clean.
- Деплой `33633da`: backup `20260828-023347`, миграции `0008→0010`, web/worker healthy,
  health/ready/auth redirect/icons smoke OK.

## Сессия 20 — 2026-08-28 — formal adapter contracts

- Добавлен `application/contracts.py`: capabilities, Protocol-контракты source/import/notifications,
  регистрационная валидация.
- OPDS получил стабильный adapter id; неготовые интеграции не включались.
- Ruff clean, 26 targeted tests passed.

## Сессия 21 — 2026-08-28 — responsive navigation

- Desktop: полный sidebar; mobile: bottom-nav для частых действий и overflow-меню
  в topbar для Источников/Уведомлений/OPDS/Настроек.
- Добавлена иконка menu в локальный SVG sprite, fixture исправлен на существующие icon ids.
- Chromium smoke: 1280×800 и 390×844 — OK.
- Деплой `a4859e7`: backup `20260828-024823`, web/worker healthy, HTTP smoke OK.

## Сессия 22 — 2026-08-28 — visual series state

- В карточки циклов добавлены chips `новый релиз`, `ждём продолжение`, `последнее наблюдение`.
- В деталях цикла добавлен доступный disclosure evidence наблюдений.
- Деплой `41a9068`: backup `20260828-034009`, web/worker healthy, HTTP smoke OK.

## Сессия 23 — 2026-08-28 — Flibusta OPDS metadata-only

- Flibusta включена отдельным профилем generic OPDS с metadata/author/series
  capabilities и `acquisition=false`.
- В форме источников добавлен выбор `Flibusta (metadata-only)`; фоновых скачиваний нет.

## Сессия 24 — 2026-08-28 — abstract source management (partial)

- Коммиты `e857d7e`, `b8e485d`, `c54aa38`, `82fb991`, `b8f829f`, `b387f3f`:
  Flibusta profile, source endpoints/links schema 0011, endpoint settings UI,
  author cards, direct entity-source read/display.
- Production не менялся: `41a9068`, schema 0010.
- Пакет намеренно помечен PARTIAL: нет SourceLink CRUD, preferred/inheritance,
  series source UI и merged metadata/acquisition state.
- Последние targeted checks: source tests 10 passed, frontend security 3 passed,
  Ruff/diff-check clean. Full suite/fresh migration требуют повторного прогона.

## Сессия 25 — 2026-08-28 — source management completion

- Migration 0012 добавляет preferred/priority и уникальность основного источника на роль.
- Endpoint settings получили toggle/delete; provenance endpoint сохраняется в watch rule.
- Реализован owner-scoped SourceLink service и UI CRUD у автора, цикла и книги.
- Metadata/acquisition разрешаются независимо по цепочке work→series→author→global.
- Fresh migration и целевые integration: 9 passed; полный набор: 269 passed.
- Production не менялся: image `41a9068`, schema `0010`; deploy требует отдельной команды.

## Сессия 26 — 2026-08-28 — source management release gate

- Добавлен HTTP end-to-end сценарий endpoint/SourceLink UI для author/series/work,
  включая наследование и отключение endpoint.
- Chromium shell smoke прошёл на 1280×800 и 390×844.
- Fresh migration/full suite: 270 passed; targeted source integration: 3 passed.
- Release candidate готов; production по-прежнему `41a9068`, schema `0010`.

## Сессия 27 — 2026-08-28 — source management deploy

- Собран/pushed immutable image `a531fd1`, digest `sha256:9fd209…a488ec9`.
- Проверенный backup `20260828-060545` создан на schema 0010.
- Миграции 0011/0012 применены до переключения; web/worker работают на `a531fd1`.
- Local/external health, ready, auth redirect, SVG/security headers и логи — OK.

## Сессия 28 — 2026-08-28 — Author.Today public metadata adapter

- Исследованы robots.txt, публичная works page и условия; граница зафиксирована ADR-0019.
- Добавлен fail-closed HTML parser v1, conditional GET, 5 MiB guard и URL allowlist.
- Quiet baseline предотвращает flood старых книг; update time/status образуют revision event.
- Проверено: live page parsed (30 works), targeted 23 unit + 7 integration, full 281 passed.
- Деплой `8bc0f60`: backup `20260828-063254`, schema `0012`, web healthy/worker running.
- Local/external и authenticated sources UI smoke — OK; rollback image `a531fd1`.

## Сессия 29 — 2026-08-28 — Litnet source research

- Проверены публичные правила Litnet для prerequisites `OPEN_QUESTIONS#10`.
- Пользовательское соглашение прямо запрещает автоматизированный сбор информации;
  поэтому HTML adapter не реализован и остаётся disabled (ADR-0020).
- Не выполнялись авторизация, browser automation, внутренние API, сбор контента
  или изменения production; следующий допустимый источник требует собственной
  правовой и технической проверки.

## Сессия 30 — 2026-08-28 — design-context reconciliation

- Сверены Ghostcar/Stitch reference, tokens, shared components и shell template.
- Исправлен документальный drift: локальные CSS tokens/components, dev-only UI kit
  и responsive Chromium smoke уже реализованы; Tailwind намеренно не используется.
- Декоративные изображения/орбитальная графика не добавлялись: реализация сохраняет
  информативный интерфейс реальной библиотеки. Следующий узкий visual slice —
  каталог/dashboard с воспроизводимыми заполненными данными.

## Сессия 31 — 2026-08-28 — FB2 continuation-link candidates

- При импорте локального FB2 извлекаются public links с ближайшим контекстом о
  продолжении/новой книге; создаются owner-scoped review candidates (migration 0013).
- Владелец вручную проверяет только page title; HTTPS/public-host/robots/size/type/
  redirect guards fail closed. Нет чтения глав, acquisition или автосоздания work.
- Test DB migrated to 0013; unit extractor 2 passed, import integration 11 passed.
- Не deployed: VPS остаётся на image `8bc0f60`, schema `0012`.

## Сессия 32 — 2026-08-28 — robots policy documentation

- Канонически зафиксированы назначение и точная последовательность проверки
  `robots.txt` в ручном FB2 title-check: runbook, ADR, status, architecture,
  deployment state и handoff.
- Проверка не относится к импорту FB2 или source polling в целом: она выполняется
  только перед единственным внешним HTML GET по кнопке владельца и fail closed.

## Сессия 33 — 2026-08-31 — guided author source onboarding

- Коммит `642d658` заменил UUID назначения import item на owner-scoped catalog picker.
- Реализован catalog-first поток карточки автора: Author.Today URL автоматически
  создаёт endpoint/link/watch rule и ставит первую проверку в очередь.
- Persisted observations группируются в кандидаты циклов; подтверждение создаёт/reuses
  series card, связывает её с discovered URL и backfill-ит observations.
- Защита: подложное имя кандидата не создаёт серию; URL берётся только из observation.
- Проверено: Ruff, mypy, unit Author.Today 9 passed, source integration 4 passed.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 34 — 2026-08-31 — series source/catalog comparison

- `SeriesStateService` строит latest-per-source-work список и статусы `present`,
  `missing`, `ambiguous`; повторные revision observations не завышают число книг.
- Карточка серии показывает сводные счётчики, внешние ссылки и прямую ссылку на
  локальную карточку для найденных книг.
- Исправлен matching будущих релизов: точное название уже принятой серии сохраняет
  `series_id` observation даже при отсутствии canonical work.
- Проверено: 28 unit, 11 source/watch integration, Ruff и mypy — green.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 35 — 2026-08-31 — source work reconciliation

- Missing/ambiguous строки на карточке серии получили catalog picker и отдельную
  явную операцию «Создать карточку»; UUID пользователю не показывается.
- Reconciliation owner-scoped: выбор проверяется по владельцу; обновляются все
  revision observations той же внешней книги, создаётся series membership и
  прямая metadata source link книги.
- Создание использует `CatalogService`: author/series переиспользуются по
  каноническим правилам; title-only evidence само по себе ничего не создаёт.
- Проверено: 19 series unit, 4 source integration, Ruff и mypy — green.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 36 — 2026-08-31 — guided website profiles and source settings

- Добавлен product-level registry профилей автора: Author.Today=`watch`, другой
  сайт=`link`, Litnet=`disabled` с актуальной причиной ADR-0020.
- Карточка автора подключает профиль одной формой. Manual website link создаёт
  owner+author-scoped endpoint/link и никогда не создаёт фоновое правило.
- Экран источников разделён на OPDS и сайты; OPDS one-step идемпотентно создаёт
  endpoint+watch rule, а adapter/rule details убраны в технический disclosure.
- Toggle/delete endpoint теперь синхронно управляет связанным watch rule.
- Проверено: 14 source/frontend unit, 4 source integration, Ruff и mypy — green.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 37 — 2026-08-31 — guided sources release gate

- Fresh migration test приведён к фактическому head `0013` и обязательной таблице
  `continuation_link_candidates`; первый full run был 293 passed + 1 stale assertion.
- Исправлены три full-mypy typing issue в `SourceLinkService` без изменения SQL
  поведения; семь старых файлов механически приведены к текущему Ruff formatter.
- Финальный единый прогон: 294 passed за 175.54s; Ruff check/format и mypy по 113
  source-файлам — green; Chromium shell desktop/mobile — green.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 38 — 2026-08-31 — searchable import assignment

- Убран неполный select первых 250 книг из inbox; каждый unmatched file ведёт на
  отдельный поиск по названию, автору или циклу с SQL-фильтрацией до лимита.
- Экран даёт два понятных пути: owner-scoped привязка к найденной книге либо
  явный разбор метаданных для новой карточки. UUID-поля удалены и из proposal UI.
- Некорректный/чужой work id не применяется; скрытый id остаётся только внутренним
  значением подтверждённого результата поиска.
- Проверено: import integration 14 passed, full suite 294 passed, Ruff/format/mypy
  green, Chromium shell desktop/mobile green.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 39 — 2026-08-31 — searchable source-work reconciliation

- Удалён select первых 250 catalog works из карточки серии и соответствующий
  тяжёлый запрос при каждом открытии страницы.
- Missing/ambiguous source work теперь открывает отдельный owner-scoped поиск по
  title/author/series; исходное название автоматически становится первым запросом.
- На основном и поисковом экранах создание новой карточки остаётся отдельным
  явным действием; запись проходит через прежнюю проверенную reconciliation boundary.
- Проверено: source integration 4 passed, полный Ruff/format/mypy green; предыдущий
  полный gate 294 passed + Chromium desktop/mobile остаётся актуален.
- Production не менялся: image `1f98181`, schema `0013`.

## Сессия 40 — 2026-08-31 — guided sources deploy

- Immutable image `00e6089` опубликован в GHCR с digest
  `sha256:8db69e…f6702`; pre-deploy backup `20260831-082135` проверен, schema `0013`.
- Миграционного delta нет. Web и worker переключены с `1f98181` на `00e6089`,
  persistent storage доступен обоим контейнерам.
- Local/external health 200, ready 200, auth redirect 303, SVG/CSP/security headers,
  новые templates/routes и отсутствие ERROR/Traceback/500 в логах — подтверждены.
- Временная регистрация для authenticated smoke отклонена ожидаемым 403, потому что
  registration закрыта; проверено, что тестовый пользователь не создан.
- Rollback: image `1f98181`; schema совместима, backup требуется только для DB restore.
