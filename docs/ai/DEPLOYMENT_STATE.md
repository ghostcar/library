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

## Процедура деплоя тестового контура

Пока ручная (Phase 9 автоматизирует):

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d   # db + web + worker
.venv/bin/alembic upgrade head
```

Backup/restore runbooks: PLANNED (Phase 9).
