# Deployment State

## Текущее состояние

| Контур | Версия | Где | Статус |
|--------|--------|-----|--------|
| **Test VPS (prod-стек)** | ghcr.io/ghostcar/library:053c145 | этот VPS, compose.prod.yaml, 127.0.0.1:8001 → https://library.gorbunovr.ru | **РАЗВЁРНУТ 2026-08-26** |
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

## Примечания
- .env теперь prod-конфиг: APP_ENV=test-vps, COOKIE_SECURE=true, LIBRARY_PG_PASSWORD (сгенерирован), AI ключ валиден, LIBRARY_AI_MODEL=auto/best-free.
- Dev-запуски (scripts/dev.sh) требуют явных override поверх .env.
- ui-kit (/library/ui-kit) скрыт (APP_ENV != development).

## Процедура dev-контура

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d   # postgres
.venv/bin/alembic upgrade head
scripts/dev.sh
```
