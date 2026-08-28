#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d node_modules/playwright ]]; then
    echo "Playwright is not installed. Run: npm ci && npx playwright install chromium" >&2
    exit 2
fi

npm run test:browser
