#!/usr/bin/env bash
# Tests. Usage: scripts/test.sh [--unit-only]
# Default: unit + integration (starts the test PostgreSQL via compose.test.yaml).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--unit-only" ]]; then
    exec .venv/bin/pytest -m 'not integration'
fi

docker compose -f compose.yaml -f compose.test.yaml up -d --wait postgres-test
export LIBRARY_TEST_DATABASE_URL="${LIBRARY_TEST_DATABASE_URL:-postgresql+asyncpg://library:library@127.0.0.1:55441/library_test}"
.venv/bin/alembic -x "database_url=$LIBRARY_TEST_DATABASE_URL" upgrade head
.venv/bin/pytest -m ''
