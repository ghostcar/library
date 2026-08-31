# Deployment State

## Текущее состояние

| Контур | Версия | Где | Статус |
|--------|--------|-----|--------|
| **Test VPS (prod-стек)** | ghcr.io/ghostcar/library:00e6089 | этот VPS, compose.prod.yaml, 127.0.0.1:8001 → https://library.gorbunovr.ru | **РАЗВЁРНУТ 2026-08-31** |
| Dev (venv) | — | не используется постоянно | .env теперь prod-конфиг |
| Dev DB (55440) | postgres:15-alpine | данные перенесены в prod-БД, контейнер остался | резерв |
| Production | — | — | не планируется |

### Pending, не развёрнуто

- Source observability release: Author.Today parser v2 с полной пагинацией,
  ручное обновление, `/library/service` и migration `0014`. Production остаётся
  image `00e6089`, schema `0013` до отдельной команды deploy.
- Generic HTML polling остаётся будущим срезом до выбора конкретного разрешённого
  сайта; Litnet automation disabled по ADR-0020.

## Окружение VPS (факты 2026-08-25)

- Host nginx: 80/443, Cloudflare origin cert, sites: cypht (post.gorbunovr.ru), omniroute (llm.gorbunovr.ru), practice-loop (tracker.gorbunovr.ru), default 444.
- Docker-соседи: tracker-app-1 (127.0.0.1:8000), tracker-db-1 (127.0.0.1:5432), pl-multisession-pg (127.0.0.1:55433), tracker-nginx-1 (created, не запущен).
- OmniRoute: 127.0.0.1:20128, внешне https://llm.gorbunovr.ru (Cloudflare).
- Ресурсы: 148G диск (91G свободно), 15G RAM.

## library.gorbunovr.ru

- DNS: работает через Cloudflare proxy; внешний HTTPS-контур доступен.
- Nginx-конфиг: подготовлен в `deploy/nginx/library.conf`, применяется пользователем (`sudo`), проксирует на 127.0.0.1:8001.

## Деплой-артефакты (готовы, Phase 9)

- Dockerfile (multi-stage, non-root, healthcheck) — сборка проверена локально.
- compose.prod.yaml (web+worker+postgres, pg без портов, LIBRARY_PG_PASSWORD из .env).
- deploy/nginx/library.conf — применяет владелец после DNS.
- scripts/backup.sh / restore.sh — round-trip проверен (29 таблиц).
- docs/operations/runbook.md — деплой/rollback/backup.

## Чек-лист живого деплоя — ВЫПОЛНЕН 2026-08-26

1. DNS library.gorbunovr.ru — сделано владельцем (Cloudflare).
2. nginx library.conf — применено владельцем.
3. GHCR push — разрешено; токен gh + write:packages (docker login ghcr.io).
4. Образы: ghcr.io/ghostcar/library:053c145 (= latest).
5. Деплой: backup pre-deploy → compose.prod up → restore dev-данных (29 таблиц, alembic 0007) → smoke.
6. Внешний smoke: https://library.gorbunovr.ru healthz/login/static/CSP — ОК (локальный резолвер кэшировал negative DNS — проверялось через --resolve).
7. LLM live: auto/best-free, propose на реальном файле — proposal в форму (Громыко/Ведьма-хозяйка), decision=review.
8. Settings + ZIP: смена пароля, ZIP-импорт, root redirect, logout CSRF — проверены.

## Примечания
- .env теперь prod-конфиг: APP_ENV=test-vps, COOKIE_SECURE=true, LIBRARY_PG_PASSWORD (сгенерирован), AI ключ валиден, LIBRARY_AI_MODEL=auto/best-free.
- Dev-запуски (scripts/dev.sh) требуют явных override поверх .env.
- ui-kit (/library/ui-kit) скрыт (APP_ENV != development).

## Деплой 2026-08-27 — audit remediation

- Git: `b7351b2`; GHCR digest:
  `sha256:20f1802da01770ad3e0f7011e8c38636bbca1240a4f58fd4259e68e1644a7635`.
- Pre-deploy backup: `20260827-023750`, исходная схема `0007`; gzip/tar проверены.
- Миграция `0007 → 0008` применена до переключения web/worker.
- Post-deploy: web healthy, worker running, schema `0008`, health/ready, auth redirect,
  CSP, packaged SVG sprite и внешний HTTPS smoke — OK.
- EPUBCheck v5.2.1 подтверждён внутри worker image.
- Rollback image: `ghcr.io/ghostcar/library:053c145`; откат БД только через backup.

## Процедура dev-контура

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d   # postgres
.venv/bin/alembic upgrade head
scripts/dev.sh
```

## Деплой 2026-08-28 — source observation links

- Git/SHA: `33633da`; GHCR digest: `sha256:6d1392f55808ba9a160880e1abafe7f6941138fc7ad81c360eda286fbbe341d5`.
- Backup: `backups/pre-deploy/*-20260828-023347.*`, gzip/tar и manifest проверены.
- Миграции `0008 → 0009 → 0010` применены до переключения web/worker.
- Post-deploy: web healthy, worker running, `/healthz`/`/readyz` 200, `/library/` 303,
  `/static/icons/sprite.svg` 200.

## Деплой 2026-08-28 — responsive navigation

- Git/SHA: `a4859e7`; GHCR digest: `sha256:5debcb30c8f87f77b7d7669b75a17e8bf031941c178033077c9855994c7ff0d3`.
- Backup: `backups/pre-deploy/*-20260828-024823.*`; миграций нет.
- Web/worker переключены, health/ready 200, root redirect 303, SVG icon pack 200.

## Деплой 2026-08-28 — visual series state

- Git/SHA: `41a9068`; GHCR digest: `sha256:4bc0a090c206007f5306e5c8203a18c9f353dc8914ec548804d54ba7e17e42ab`.
- Backup: `backups/pre-deploy/*-20260828-034009.*`; миграций нет.
- Web/worker переключены, health/ready 200, root redirect 303, SVG icon pack 200.

## Деплой 2026-08-28 — source management

- Git/SHA: `a531fd1`; GHCR digest:
  `sha256:9fd2096684e3b485524e1180fc64c43ac45bce9338d3e0033ab902db4a488ec9`.
- Pre-deploy backup: `backups/pre-deploy/*-20260828-060545.*`; DB/storage gzip,
  tar listing и manifest проверены; исходная schema `0010`.
- Миграции `0010 → 0011 → 0012` применены отдельным новым контейнером до rollout.
- Web/worker переключены на `a531fd1`; web healthy, worker running, schema `0012`.
- Smoke: local health/ready, no-auth redirect, SVG/security headers и внешний HTTPS health — OK.
- Rollback image: `ghcr.io/ghostcar/library:41a9068`; DB rollback только restore backup.

## Деплой 2026-08-28 — Author.Today metadata

- Git/SHA: `8bc0f60`; GHCR digest:
  `sha256:9ba4eae181b8402ab2e119feee7d9384f01455a4d827f07c150f8cde2f6735af`.
- Backup: `backups/pre-deploy/*-20260828-063254.*`; DB/storage gzip, tar listing
  и manifest проверены; schema осталась `0012` (миграций нет).
- Web/worker переключены на `8bc0f60`; web healthy, worker running.
- Smoke: health/ready, external HTTPS, auth redirect и authenticated sources UI — OK;
  Author.Today profile/options присутствуют, ошибок в логах нет.
- Rollback image: `ghcr.io/ghostcar/library:a531fd1`; схема совместима.

## Деплой 2026-08-31 — continuation candidates + bulk AI import

- Git/SHA: `949314d`; GHCR digest:
  `sha256:f2b2cd7e0a1f2369933411f39119d928b83a76d6fe2e3db554f154cc32e8c19e`.
- Backup: `backups/pre-deploy/*-20260831-021217.*`; db gzip и storage tar
  проверены до миграции.
- Миграция `0012 → 0013` применена одноразовым контейнером до переключения
  web/worker. Оба сервиса работают на `949314d`; `/healthz` и `/readyz` = 200,
  защищённый `/library/` = 303.
- Все семь старых `stored_unmatched` пользователя были разово поставлены в
  `propose_import`; worker завершил их без cache exception, все получили
  `review_ready`. Один transient `AI gateway unreachable` обработан fallback.
- Rollback image: `ghcr.io/ghostcar/library:8bc0f60`; откат БД — только restore
  преддеплойного backup.

## Деплой 2026-08-31 — persistent storage + FB2 metadata

- Git/SHA: `1f98181`; GHCR digest:
  `sha256:db6cf76a3887bba7ed0548a024bdebc29113393301319d907b3b8483ea00f6ad`.
- Backup: `backups/pre-deploy/*-20260831-025216.*`, gzip/tar validated.
- Web and worker now explicitly use mounted `/data/storage`; verified in both
  running containers. There is no schema migration.
- Browser upload filter accepts FB2, EPUB and ZIP including `.fb2.zip`. FB2
  `title-info` is primary deterministic import evidence; a re-upload of a
  missing original restores the content-addressed object instead of silently
  rejecting it as an exact duplicate.
- Health/ready = 200 and anonymous `/library/` = 303. Owner must re-upload the
  six retained source files; no user book was uploaded during smoke.

## Деплой 2026-08-31 — guided sources and searchable assignment

- Git/SHA: `00e6089`; GHCR digest:
  `sha256:8db69ebf9d5c4d55eaa8a3aed759b459a78dea7fa80e2bf2164352bf0daf6702`.
- Backup: `backups/pre-deploy/*-20260831-082135.*`; DB gzip, storage tar and
  manifest validated, source schema `0013`. Миграций нет.
- Web/worker переключены с `1f98181` на `00e6089`; web healthy, worker running,
  persistent `/data/storage` доступен обоим, schema остаётся `0013 (head)`.
- Local/external health = 200, ready = 200, anonymous library = 303 to login,
  SVG/security headers and packaged guided-assignment templates/routes — OK.
- Свежие web/worker logs без ERROR/Traceback/500. Authenticated smoke через
  временную регистрацию не выполнялся: registration закрыта (ожидаемый 403),
  пользователь не создан. Rollback image: `1f98181`, схема совместима.
