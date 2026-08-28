# Deployment State

## Текущее состояние

| Контур | Версия | Где | Статус |
|--------|--------|-----|--------|
| **Test VPS (prod-стек)** | ghcr.io/ghostcar/library:41a9068 | этот VPS, compose.prod.yaml, 127.0.0.1:8001 → https://library.gorbunovr.ru | **РАЗВЁРНУТ 2026-08-28** |
| Dev (venv) | — | не используется постоянно | .env теперь prod-конфиг |
| Dev DB (55440) | postgres:15-alpine | данные перенесены в prod-БД, контейнер остался | резерв |
| Production | — | — | не планируется |

## Окружение VPS (факты 2026-08-25)

- Host nginx: 80/443, Cloudflare origin cert, sites: cypht (post.gorbunovr.ru), omniroute (llm.gorbunovr.ru), practice-loop (tracker.gorbunovr.ru), default 444.
- Docker-соседи: tracker-app-1 (127.0.0.1:8000), tracker-db-1 (127.0.0.1:5432), pl-multisession-pg (127.0.0.1:55433), tracker-nginx-1 (created, не запущен).
- OmniRoute: 127.0.0.1:20128, внешне https://llm.gorbunovr.ru (Cloudflare).
- Ресурсы: 148G диск (91G свободно), 15G RAM.

## library.gorbunovr.ru

- DNS: отсутствует. Добавляет пользователь (Cloudflare, proxy on).
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
