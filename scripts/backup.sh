#!/usr/bin/env bash
# Backup: PostgreSQL + storage originals/derivatives (master prompt 14.3).
# Usage: scripts/backup.sh [output-dir]
# Run on the VPS. Secrets are NOT included; .env must be backed up separately
# by the owner (contains LIBRARY_JWT_SECRET, AI keys).
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

PG_CONTAINER="${LIBRARY_PG_CONTAINER:-library-postgres-prod}"
echo "==> PostgreSQL dump (container: $PG_CONTAINER)"
docker exec "$PG_CONTAINER" pg_dump -U library -d library \
    | gzip > "$OUT/db-$STAMP.sql.gz"

echo "==> Storage archive"
STORAGE_CONTAINER="${LIBRARY_STORAGE_CONTAINER:-library-web}"
docker exec "$STORAGE_CONTAINER" tar -czf - -C /data storage \
    > "$OUT/storage-$STAMP.tar.gz"

ALEMBIC_HEAD="$(docker exec "$PG_CONTAINER" psql -U library -d library -Atc \
    'select version_num from alembic_version;' 2>/dev/null || echo unknown)"

cat > "$OUT/MANIFEST-$STAMP.txt" <<EOF
created: $(date -Iseconds)
db: db-$STAMP.sql.gz
storage: storage-$STAMP.tar.gz
alembic_head: $ALEMBIC_HEAD
EOF

echo "==> Done: $OUT/*-$STAMP.*"
echo "NOTE: .env (JWT secret, AI keys) is NOT included — back it up separately."
