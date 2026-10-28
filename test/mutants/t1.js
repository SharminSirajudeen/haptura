// T1: the contracts and S11. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_types.py';
module.exports = [
  { from:'S11: NaN written as null', file:'gate/types.py',
    find:'return [[None if math.isnan(x) else x for x in row] for row in v.tolist()]',
    replace:'return [[x for x in row] for row in v.tolist()]',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_nan_is_written_as_null', cmd:PYTEST },
  { from:'S11: track ids read back as int', file:'gate/types.py',
    find:'return {_decode(k, kt): _decode(x, vt) for k, x in v.items()}',
    replace:'return {k: _decode(x, vt) for k, x in v.items()}',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_arrays_round_trip_with_int_ids_and_nan_gaps', cmd:PYTEST },
  { from:'S11: null read back as NaN', file:'gate/types.py',
    find:'rows = [[np.nan if x is None else x for x in row] for row in v]',
    replace:'rows = [[0.0 if x is None else x for x in row] for row in v]',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_arrays_round_trip_with_int_ids_and_nan_gaps', cmd:PYTEST },
  { from:'S11: an unsampled action stays None', file:'gate/types.py',
    find:'return None if v is None else _decode(v, inner[0])',
    replace:'return _decode(v, inner[0])',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_mirrored_body_and_unsampled_action_survive', cmd:PYTEST },
  { from:'constants: permutation floor below ALPHA_ACT', file:'gate/constants.py',
    find:'PERMS = 9999', replace:'PERMS = 999',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_alpha_act_is_computed_and_sits_above_the_permutation_floor', cmd:PYTEST },
  { from:'constants: ALPHA_ACT computed, not tuned', file:'gate/constants.py',
    find:'ALPHA_ACT = 0.01 / (ELEMENTS_MAX * BLOCK_BUDGET)', replace:'ALPHA_ACT = 0.01',
    mustFail:'tests/test_types.py', expect:'FAILED tests/test_types.py::test_alpha_act_is_computed_and_sits_above_the_permutation_floor', cmd:PYTEST }
];
