#!/usr/bin/env bash
# Lint + typecheck. Usage: scripts/lint.sh
set -euo pipefail
cd "$(dirname "$0")/.."

.venv/bin/ruff check src tests migrations
.venv/bin/ruff format --check src tests migrations
.venv/bin/mypy
