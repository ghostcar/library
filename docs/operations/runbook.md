# Operations Runbook — Library Portal

Целевая машина: тестовый VPS (ADR-0003). Всё в `/home/roman/library`.

## Ежедневные операции

```bash
# статус стека (prod-контур)
docker compose -f compose.prod.yaml ps

# логи
docker logs library-web --tail 100
docker logs library-worker --tail 100 -f

# миграции (внутри web-контейнера)
docker compose -f compose.prod.yaml exec web alembic -x database_url="$LIBRARY_DATABASE_URL" upgrade head
```

## Backup / Restore (§14.3)

```bash
scripts/backup.sh backups/            # db + storage + manifest
scripts/restore.sh backups/db-XXX.sql.gz backups/storage-XXX.tar.gz
```

`.env` (JWT secret, AI ключи) в backup НЕ входит — храните отдельно.
Непроверенный backup считается невалидным: после restore прогоните smoke
(`/healthz`, `/readyz`, вход, OPDS-фид).

## Деплой нового образа (§14.2)

```bash
# 1. сборка и пуш образа (по согласованию)
docker build -t ghcr.io/ghostcar/library:<git-sha> .
docker push ghcr.io/ghostcar/library:<git-sha>

# 2. backup ПЕРЕД деплоем
scripts/backup.sh backups/

# 3. обновить тег в compose.prod.yaml и применить
docker compose -f compose.prod.yaml pull
docker compose -f compose.prod.yaml up -d
docker compose -f compose.prod.yaml exec web alembic -x database_url="$LIBRARY_DATABASE_URL" upgrade head

# 4. smoke
curl -s http://127.0.0.1:8001/healthz && curl -s http://127.0.0.1:8001/readyz
```

## Rollback

Только при совместимой схеме (§14.2):
```bash
# вернуть предыдущий тег образа в compose.prod.yaml
docker compose -f compose.prod.yaml up -d web worker
# БД НЕ откатывать автоматически — только через restore из backup
```

## Nginx (первичная настройка)

```bash
sudo cp deploy/nginx/library.conf /etc/nginx/sites-available/library
sudo ln -s /etc/nginx/sites-available/library /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Требует: DNS-запись library.gorbunovr.ru (Cloudflare, proxy on) и
/etc/nginx/ssl/origin.crt|key (уже есть на машине).

## Известные ограничения

- EPUBCheck не входит в образ (нет Java) — структурная валидация EPUB
  помечается skipped в manifest.
- Образы в GHCR ещё не публиковались (первый push — по команде владельца).
