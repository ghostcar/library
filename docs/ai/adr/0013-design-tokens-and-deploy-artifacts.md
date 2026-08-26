# ADR-0013: Токены в CSS, hardening, деплой-артефакты (Phase 8 + подготовка Phase 9)

Статус: accepted
Дата: 2026-08-26

## Решения

1. **Токены в коде**: `static/css/tokens.css` — CSS-переменные обеих тем
   (Astral тёмная / Solar светлая) из ghostcar tokens.md; `components.css` —
   общие компоненты (cards, buttons, chips, tables, forms). base.html
   больше не содержит inline-стилей. Tailwind-сборка отложена (TECH_DEBT):
   текущий CSS-вариант даёт ту же сходимость без Node-цепочки.

2. **UI kit**: `/library/ui-kit` — dev-only (404 вне development), каталог
   компонентов для сверки с макетами.

3. **Hardening**: SecurityHeadersMiddleware (nosniff, DENY, Referrer-Policy,
   Permissions-Policy, CSP: self + inline-styles на переходный период).
   Accessibility: skip-link, focus-visible, color-scheme meta.

4. **Образ** (§14.1): multi-stage python:3.13-slim, non-root (app),
   healthcheck на /healthz, одно image для web+worker (разные команды),
   secrets только через env. httpx перенесён в основные зависимости
   (используется prod-кодом). Сборка проверена локально; **push в GHCR —
   только по явной команде владельца** (§15.4).

5. **compose.prod.yaml**: web+worker+postgres; postgres без публикации
   порта; volumes library_pgdata_prod / library_storage; LIBRARY_PG_PASSWORD
   обязателен из .env; memory limits 512M; тег образа пинится на SHA при
   деплое (никогда :latest).

6. **Backup/restore** (§14.3): scripts/backup.sh (pg_dump + storage tar +
   manifest с alembic head; .env НЕ входит) и restore.sh (destructive,
   подтверждение, проверка alembic_version). Round-trip проверен на
   dev-контейнере (29 таблиц). Имя контейнера — LIBRARY_PG_CONTAINER.

7. **Nginx**: deploy/nginx/library.conf (443/Cloudflare origin cert,
   static cache 30d immutable, client_max_body_size 60m) — применяется
   владельцем после DNS (ADR-0003).

## Последствия
- Деплой Phase 9: build → push GHCR → на VPS: backup → pull по SHA →
  up → migrate → smoke (см. docs/operations/runbook.md).
- CSP ужесточается (убрать unsafe-inline) после полного переноса стилей.
