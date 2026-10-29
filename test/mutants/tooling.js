// The gate's own guarded line. Dropping ruff's preview flag silently switches the nesting limit off.
module.exports = [
  { from:'lint: nesting limit enforced', file:'pyproject.toml', find:'preview = true', replace:'preview = false',
    mustFail:'tests/test_gate_limits.py', expect:'FAILED tests/test_gate_limits.py::test_four_deep_function_turns_ruff_red',
    cmd:'uv run --locked python -m pytest -q tests/test_gate_limits.py' },
  { from:'floorguard: a deleted test file counts only on the project paths', file:'test/floorguard.js',
    find:'if (OWN.test(f) && /', replace:'if (/', mustFail:'test/floorguard.test.js',
    expect:"a test file deleted outside the project's own paths" }
];
