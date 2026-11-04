#!/usr/bin/env bash
# The one CI job: the gate in a clean, reused worktree at the pushed commit — nothing from this checkout — posted to GitHub as the
# commit status `gate/local` when `gh` is signed in; otherwise the result line is printed for pasting on the pull
# request. scripts/merge.sh refuses without the status.
# Which gate runs is package.json's `gateMode` at the gated commit: `development` (also when absent) runs every
# mutant, `live` runs the mutants the change touches (EG_MUTANTS=changed). GATE=gate forces the full run.
# Usage: scripts/ci.sh [ref]   (default: the current branch's pushed head)
set -euo pipefail
repo=$(git remote get-url origin | sed -E 's#.*github\.com[:/]##; s#\.git$##')
ref=${1:-origin/$(git rev-parse --abbrev-ref HEAD)}
git fetch -q origin
sha=$(git rev-parse "$ref^{commit}")
git branch -r --contains "$sha" | grep -q . || { echo "gate: $sha is not on origin; push it first"; exit 1; }
mode=$(git show "$sha:package.json" | grep -m1 -oE '"gateMode": *"(development|live)"' | grep -oE 'development|live' || true)  # the mode of the commit gated
if [ "$mode" = live ]; then default=gate:fast; else default=gate; fi
gate=${GATE:-$default}
post(){ gh auth status >/dev/null 2>&1 && gh api -X POST "repos/$repo/statuses/$sha" -f state="$1" -f context=gate/local -f description="$2" >/dev/null || true; }
post pending "clean worktree + scripts/gate.sh ($gate)"
top=$(git rev-parse --show-toplevel)
wt="${XDG_CACHE_HOME:-$HOME/.cache}/gate/$(basename "$top")-$(printf '%s' "$top" | shasum | cut -c1-8)"; log="$wt.log"
git worktree prune
if [ -e "$wt/.git" ]; then git -C "$wt" checkout -q --force --detach "$sha"; else mkdir -p "$(dirname "$wt")"; git worktree add -q --force --detach "$wt" "$sha"; fi
git -C "$wt" clean -q -ffdx; start=$(date +%s)
if cd "$wt" \
   && npm ci --silent >"$log" 2>&1 && EG_MUTANTS=$([ "$gate" = gate:fast ] && echo changed || true) scripts/gate.sh >>"$log" 2>&1; then
  post success "$gate exit 0 in $(( ($(date +%s) - start) / 60 )) min: $(grep -m1 'mutants:' "$log" | cut -c1-80)"
  echo "gate/local success on $sha ($gate)"
else
  post failure "$gate failed — log: $log"
  tail -20 "$log"; echo "gate/local FAILURE on $sha (log $log)"; exit 1
fi
