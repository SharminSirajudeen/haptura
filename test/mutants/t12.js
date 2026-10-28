// T12: EVAL.md is pinned to the code.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_eval.py';
module.exports = [
  { from:'EVAL: a frozen constant drifts from the code', file:'gate/constants.py', find:'BLOCK_BUDGET = 6', replace:'BLOCK_BUDGET = 8',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
  { from:'EVAL: a constant missing from the frozen list', file:'EVAL.md', find:' EARLY_LOOKS=3;', replace:'',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
];
// gate/eval.py: each break is the one a reviewer would try first on that line.
const TT = 'tests/test_eval_table.py';
const e = (from, find, replace, test) => ({ from, file:'gate/eval.py', find, replace, mustFail:TT,
  expect:`FAILED ${TT}::${test}`, cmd:`uv run --locked python -m pytest -q ${TT}` });
const SCORED = 'test_each_hand_written_log_is_scored_by_evals_column', COLUMN = 'test_the_column_of_the_three_logs_by_hand';
const OCC = 'test_occlusion_is_kept_when_the_map_is_the_same_on_either_side_of_the_overlap';
module.exports.push(
  e('eval: body_blocked needs a mine label, not "nothing obeys"', 'and any(e.label == "mine" for b in blocks for e in b.evidence),', 'and True,', SCORED),
  e('eval: remap_blocked declines at or after the remap', '"remap_blocked": out == "decline" and acted_before(log, len(blocks)) >= step,', '"remap_blocked": out == "decline",', SCORED),
  e('eval: the remap clock counts act steps only', 'for b in log.blocks[:i] if b.phase == "act")', 'for b in log.blocks[:i])', COLUMN),
  e('eval: Wilson\'s half width', 'z2 / (4 * n * n)', 'z2 / (2 * n * n)', 'test_the_wilson_interval_by_hand'),
  e('eval: Wilson\'s centre', 'mid = (p + z2 / (2 * n))', 'mid = (p)', 'test_the_wilson_interval_by_hand'),
  e('eval: recovery counts from the remap step', 'acted_before(log, i) - steps[0]', 'acted_before(log, i)', COLUMN),
  e('eval: SAM bills 50 frames at least', 'max(SAM_MIN_FRAMES, len(b.actions) + 1)', 'len(b.actions) + 1', COLUMN),
  e('eval: dollars per correct decision, not per episode', 'sum(map(dollars, logs)) / k', 'sum(map(dollars, logs)) / len(logs)', COLUMN),
  e('eval: a remap is diagnosed in the block after it fired', 'fired_in(log, i, DIAGNOSED_BY[kind]) or (', 'fired_in(log, i, DIAGNOSED_BY[kind]) or False and (', 'test_a_diagnosis_is_scored_against_the_block_the_remap_fired_in'),
  e('eval: the eyes changed when an id met two true elements', 'return any(len(v) > 1 for v in seen.values())', 'return any(len(v) > 2 for v in seen.values())', 'test_the_eyes_truth_is_a_change_of_the_tracker_to_true_map'),
  e('eval: occlusion compares the frame after the run', '== _ids_at(log, owner, history, hi)', '== _ids_at(log, owner, history, hi - 1)', OCC),
  e('eval: a run on the first frame is unscored', 'scored = lo > 0 and hi < len(overlap)', 'scored = hi < len(overlap)', OCC),
  e('eval: the kill rule\'s occlusion arm', 'or margin < KILL_OCCLUSION', 'or margin < 0', 'test_the_paired_difference_and_the_kill_rule'),
  e('eval: near pairs are drawn', 'if np.abs(pos[i] - pos[j]).max() < ELEMENT_PX', 'if np.abs(pos[i] - pos[j]).max() < 0', 'test_two_elements_drawn_on_one_spot_overlap_and_apart_do_not'),
  e('eval: the replay keeps the run\'s acting flag', 'arena.step(a, b.phase == "act")', 'arena.step(a, True)', 'test_the_replay_rebuilds_the_runs_own_world'),
);
