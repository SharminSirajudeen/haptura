// T12: EVAL.md is pinned to the code.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_eval.py';
module.exports = [
  { from:'EVAL: a frozen constant drifts from the code', file:'gate/constants.py', find:'BLOCK_BUDGET = 6', replace:'BLOCK_BUDGET = 8',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
  { from:'EVAL: a constant missing from the frozen list', file:'EVAL.md', find:' EARLY_LOOKS=3;', replace:'',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
];
