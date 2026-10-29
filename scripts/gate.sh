#!/usr/bin/env bash
# The whole gate, in order: lockfile, lint, format, types, duplication, floorguard, the suite, every mutant.
# Run it before every push; scripts/ci.sh runs it in a fresh clone of the pushed commit.
# EG_MUTANTS=changed runs only the mutants a change touches (the `live` gate; `gateMode` in package.json).
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --locked --quiet
# reinstall whenever the lockfile changed since the last install (npm writes node_modules/.package-lock.json)
[ node_modules/.package-lock.json -nt package-lock.json ] || npm ci --silent
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
npx --no jscpd
node test/floorguard.test.js
node test/floorguard.js
uv run --locked python -m pytest -q
# Chromium comes from `npx playwright install chromium`, or from /opt/pw-browsers where a container ships it
if [ -d /opt/pw-browsers ]; then export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; fi
npx playwright test -c web/playwright.config.js --reporter=dot
node test/mutants.js
