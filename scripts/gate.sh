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
# The test files that run whole episodes run only when the change can reach them: through gate/, the file itself, a
# conftest.py, EVAL.md, the Python version, pytest's config, uv.lock or this script, committed or not. A moved file
# counts at both paths. With no origin/main to compare against, every one runs.
episodes="tests/test_e2e.py tests/test_eval_table.py tests/test_agent.py tests/test_demo.py tests/test_run.py"
skip=""
if changed=$(git diff --no-renames --name-only origin/main...HEAD 2>/dev/null && git diff --no-renames --name-only HEAD); then
  for f in $episodes; do
    grep -qxE "gate/.*|$f|(.*/)?conftest\.py|EVAL\.md|\.python-version|pyproject\.toml|pytest\.ini|tox\.ini|setup\.cfg|uv\.lock|scripts/gate\.sh" \
      <<<"$changed" || skip="$skip $f"
  done
  echo "episode tests skipped:${skip:- none} (each runs when the change touches gate/, the file itself, a conftest.py, EVAL.md, .python-version, pyproject.toml, pytest.ini, tox.ini, setup.cfg, uv.lock or scripts/gate.sh)"
else
  echo "episode tests: every one runs, there is no origin/main to compare with"
fi
uv run --locked python -m pytest -q $(for f in $skip; do echo "--ignore=$f"; done)
# Chromium comes from `npx playwright install chromium`, or from /opt/pw-browsers where a container ships it
if [ -d /opt/pw-browsers ]; then export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; fi
node_modules/.bin/playwright test -c web/playwright.config.js --reporter=dot --workers=2
node test/mutants.js
