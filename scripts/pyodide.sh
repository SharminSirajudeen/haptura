#!/usr/bin/env bash
# Pyodide, the Python runtime the demo page runs the gate with (web/gate.js), into web/vendor/pyodide/: one pinned
# release, fetched from its GitHub release and checked against its hash, with its licence (MPL-2.0) and the licence of
# the CPython it bundles (PSF-2.0). Never committed (web/vendor/ is ignored); scripts/gate.sh and
# .github/workflows/pages.yml run this first. Idempotent per version.
set -euo pipefail
cd "$(dirname "$0")/.."
V=314.0.7
PY=3.14.2  # the CPython inside this release (its pyodide-lock.json)
TAR_SHA=2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95
LICENCE_SHA=1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5
PY_LICENCE_SHA=b0e25a78cffb43f4d92de8b61ccfa1f1f98ecbc22330b54b5251e7b6ba010231
dir=web/vendor/pyodide
[ "$(cat "$dir/VERSION" 2>/dev/null)" = "$V" ] && [ -f "$dir/pyodide.asm.wasm" ] && [ -f "$dir/LICENSE-CPython" ] && exit 0
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
get(){ curl -fsSL --retry 3 -o "$tmp/$1" "$2"; }
get core.tar.bz2 "https://github.com/pyodide/pyodide/releases/download/$V/pyodide-core-$V.tar.bz2"
get LICENSE "https://raw.githubusercontent.com/pyodide/pyodide/$V/LICENSE"
get LICENSE-CPython "https://raw.githubusercontent.com/python/cpython/v$PY/LICENSE"
printf '%s  %s\n%s  %s\n%s  %s\n' "$TAR_SHA" "$tmp/core.tar.bz2" "$LICENCE_SHA" "$tmp/LICENSE" "$PY_LICENCE_SHA" "$tmp/LICENSE-CPython" \
  | shasum -a 256 -c - >/dev/null
# the loader, the runtime, the interpreter and the standard library: nothing else of the release
tar -xjf "$tmp/core.tar.bz2" -C "$tmp" pyodide/pyodide.mjs pyodide/pyodide.asm.mjs pyodide/pyodide.asm.wasm pyodide/python_stdlib.zip pyodide/pyodide-lock.json
rm -rf "$dir" && mkdir -p "$dir" && mv "$tmp"/pyodide/* "$tmp/LICENSE" "$tmp/LICENSE-CPython" "$dir"/ && echo "$V" >"$dir/VERSION"
echo "pyodide $V (CPython $PY) in $dir"
