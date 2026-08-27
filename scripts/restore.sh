#!/usr/bin/env bash
# Restore: PostgreSQL + storage from a backup made by scripts/backup.sh.
# Usage: scripts/restore.sh <db-dump.sql.gz> [storage.tar.gz]
# DESTRUCTIVE: drops and recreates the public schema. Run on the VPS.
set -euo pipefail
cd "$(dirname "$0")/.."

DB_DUMP="${1:?usage: restore.sh <db-dump.sql.gz> [storage.tar.gz]}"
STORAGE_TAR="${2:-}"

read -r -p "This will DROP the current schema and restore from $DB_DUMP. Continue? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "aborted"; exit 1; }

echo "==> Drop and recreate schema"
PG_CONTAINER="${LIBRARY_PG_CONTAINER:-library-postgres-prod}"
docker exec "$PG_CONTAINER" psql -U library -d library \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "==> Restore PostgreSQL"
gunzip -c "$DB_DUMP" | docker exec -i "$PG_CONTAINER" psql -U library -d library -q

echo "==> Verify migrations"
PG_CONTAINER="${LIBRARY_PG_CONTAINER:-library-postgres-prod}"
docker exec "$PG_CONTAINER" psql -U library -d library \
    -c "select version_num from alembic_version;"

if [[ -n "$STORAGE_TAR" ]]; then
    echo "==> Restore storage"
    STORAGE_CONTAINER="${LIBRARY_STORAGE_CONTAINER:-library-web}"
    docker exec -i "$STORAGE_CONTAINER" tar -xzf - -C /data < "$STORAGE_TAR"
fi

echo "==> Done. Restart web+worker: docker compose -f compose.prod.yaml up -d --force-recreate web worker"
