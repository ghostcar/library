# Deployment State

## Текущее состояние

| Контур | Версия | Где | Статус |
|--------|--------|-----|--------|
| Dev (локальный процесс/venv) | сессия 1, Phase 0/1 | этот VPS, 127.0.0.1:8001 | не запущен постоянно |
| Dev DB | postgres:15-alpine (docker) | этот VPS, без публикации порта | поднимается compose.dev.yaml |
| Test VPS | — | — | не развернуто |
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

## Чек-лист живого деплоя (когда DNS появится)

1. Владелец: DNS-запись library.gorbunovr.ru (Cloudflare, proxy on).
2. Владелец: применить nginx-конфиг (sudo), nginx -t, reload.
3. Владелец: разрешить push образа в GHCR.
4. Агент: docker build + push ghcr.io/ghostcar/library:<sha>.
5. На VPS: backup → compose.prod up (тег <sha>) → alembic upgrade → smoke.
6. Записать версию в DEPLOYMENT_STATE.

## Процедура dev-контура

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d   # postgres
.venv/bin/alembic upgrade head
scripts/dev.sh
```
