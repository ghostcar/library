#!/usr/bin/env bash
# Dev server: web on 127.0.0.1:8001 + dev PostgreSQL. Usage: scripts/dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
export LIBRARY_DATABASE_URL="${LIBRARY_DATABASE_URL:-postgresql+asyncpg://library:library@127.0.0.1:55440/library}"
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn portal.web.app:create_app --factory --host 127.0.0.1 --port 8001 --reload
