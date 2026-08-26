#!/usr/bin/env bash
# Regenerate requirements.lock from requirements.in (source: pyproject.toml).
# Usage: scripts/update-lock.sh   — run after changing pyproject dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."

.venv/bin/pip install --quiet pip-tools
.venv/bin/pip-compile requirements.in --output-file requirements.lock --strip-extras
echo "requirements.lock updated. Verify: pip install -r requirements.lock"
