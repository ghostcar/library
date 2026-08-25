#!/usr/bin/env bash
# Dev server: web on 127.0.0.1:8001 + dev PostgreSQL. Usage: scripts/dev.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Ensure .env exists with a generated JWT secret
if [[ ! -f .env ]]; then
    cp .env.example .env
    secret=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")
    sed -i "s|^LIBRARY_JWT_SECRET=.*|LIBRARY_JWT_SECRET=${secret}|" .env
    echo ".env created with generated LIBRARY_JWT_SECRET"
fi

docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
export LIBRARY_DATABASE_URL="${LIBRARY_DATABASE_URL:-postgresql+asyncpg://library:library@127.0.0.1:55440/library}"
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn portal.web.app:create_app --factory --host 127.0.0.1 --port 8001
