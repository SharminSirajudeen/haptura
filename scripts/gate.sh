#!/usr/bin/env bash
# The whole gate, in order: lockfile, lint, format, types, duplication, floorguard, the suite, every mutant.
# Run it before every push; scripts/ci.sh runs it in a fresh clone of the pushed commit.
# EG_MUTANTS=changed runs only the mutants a change touches (the `live` gate; see CLAUDE.md, "Gate:").
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --locked --quiet
[ -d node_modules ] || npm ci --silent
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
npx --no jscpd
node test/floorguard.test.js
node test/floorguard.js
uv run --locked python -m pytest -q
node test/mutants.js
