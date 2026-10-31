// EVAL.md is pinned to the code.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_eval.py';
module.exports = [
  { from:'EVAL: a frozen constant drifts from the code', file:'gate/constants.py', find:'BLOCK_BUDGET = 6', replace:'BLOCK_BUDGET = 8',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
  { from:'EVAL: a constant missing from the frozen list', file:'EVAL.md', find:' EARLY_LOOKS=3;', replace:'',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_freezes_every_constant_at_its_current_value', cmd:PYTEST },
  { from:'EVAL: the kill seeds in the code drift from EVAL.md', file:'gate/eval.py', find:'KILL_SEEDS = range(1010, 1020)', replace:'KILL_SEEDS = range(20)',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_names_the_kill_seeds', cmd:PYTEST },
  { from:'EVAL: the kill seeds in EVAL.md drift from the code', file:'EVAL.md', find:'**Kill test:** seeds 1010–1019', replace:'**Kill test:** seeds 0–19',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_names_the_kill_seeds', cmd:PYTEST },
  { from:'EVAL: the model in the code drifts from EVAL.md', file:'gate/meta_api.py', find:'MUSE_MODEL = "muse-wonder-1.0"', replace:'MUSE_MODEL = "muse-spark-1.3"',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_names_the_model_the_arena_runs', cmd:PYTEST },
  { from:'EVAL: the model in EVAL.md drifts from the code', file:'EVAL.md', find:'Muse Wonder (`muse-wonder-1.0`)', replace:'Muse Wonder (`muse-spark-1.3`)',
    mustFail:'tests/test_eval.py', expect:'FAILED tests/test_eval.py::test_eval_md_names_the_model_the_arena_runs', cmd:PYTEST },
];
// gate/eval.py: each break is the one a reviewer would try first on that line.
const TT = 'tests/test_eval_table.py';
const e = (from, find, replace, test) => ({ from, file:'gate/eval.py', find, replace, mustFail:TT,
  expect:`FAILED ${TT}::${test}`, cmd:`uv run --locked python -m pytest -q ${TT}` });
const SCORED = 'test_each_hand_written_log_is_scored_by_evals_column', COLUMN = 'test_the_column_of_the_three_logs_by_hand';
const CACHED = 'test_cached_input_tokens_cost_the_cached_price';
const OCC = 'test_occlusion_is_kept_when_each_of_the_pair_keeps_its_id', KILL = 'test_the_kill_decision_at_its_boundaries';
module.exports.push(
  e('eval: body_blocked needs a mine label, not "nothing obeys"', 'and any(e.label == "mine" for b in blocks for e in b.evidence),', 'and True,', SCORED),
  e('eval: remap_blocked declines at or after the remap', '"remap_blocked": out == "decline" and acted_before(log, len(blocks)) >= step,', '"remap_blocked": out == "decline",', SCORED),
  e('eval: the remap clock counts act steps only', 'for b in log.blocks[:i] if b.phase == "act")', 'for b in log.blocks[:i])', COLUMN),
  e('eval: Wilson\'s half width', 'z2 / (4 * n * n)', 'z2 / (2 * n * n)', 'test_the_wilson_interval_by_hand'),
  e('eval: Wilson\'s centre', 'mid = (p + z2 / (2 * n))', 'mid = (p)', 'test_the_wilson_interval_by_hand'),
  e('eval: recovery counts from the remap step', 'acted_before(log, i) - steps[0]', 'acted_before(log, i)', COLUMN),
  e('eval: Muse Wonder\'s prices', 'MUSE_USD_IN, MUSE_USD_CACHED, MUSE_USD_OUT = 4.00e-6, 0.20e-6, 20.00e-6', 'MUSE_USD_IN, MUSE_USD_CACHED, MUSE_USD_OUT = 1.25e-6, 0.15e-6, 4.25e-6', COLUMN),
  e('eval: cached input costs the cached price', 'cached_tokens * MUSE_USD_CACHED', 'cached_tokens * MUSE_USD_IN', CACHED),
  e('eval: the cached tokens are part of the input tokens', 'uncached = input_tokens - cached_tokens', 'uncached = input_tokens', CACHED),
  e('eval: dollars read the log\'s cached tokens', 'u.get("cached_tokens", 0)', '0', CACHED),
  e('eval: SAM bills 50 frames at least', 'max(SAM_MIN_FRAMES, len(b.actions) + 1)', 'len(b.actions) + 1', COLUMN),
  e('eval: dollars per correct decision, not per episode', 'sum(map(dollars, logs)) / k', 'sum(map(dollars, logs)) / len(logs)', COLUMN),
  e('eval: a remap is diagnosed in the block after it fired', 'fired_in(log, i, DIAGNOSED_BY[kind]) or (', 'fired_in(log, i, DIAGNOSED_BY[kind]) or False and (', 'test_a_diagnosis_is_scored_against_the_block_the_remap_fired_in'),
  e('eval: the eyes changed when an id met two true elements', 'return any(len(v) > 1 for v in seen.values())', 'return any(len(v) > 2 for v in seen.values())', 'test_the_eyes_truth_is_a_change_of_the_tracker_to_true_map'),
  e('eval: after the run, the search goes on to the next frame held apart', 'range(hi, stop))', 'range(hi, hi + 1))', OCC),
  e('eval: a run with no frame held apart before it is unscored', 'scored = before is not None and hi < len(overlap)', 'scored = hi < len(overlap)', OCC),
  e('eval: a run reaching the episode end is unscored', 'scored = before is not None and hi < len(overlap)', 'scored = before is not None', OCC),
  e('eval: the kill rule rethinks at a difference of exactly KILL_DIFF', 'return diff > KILL_DIFF and', 'return diff >= KILL_DIFF and', KILL),
  e('eval: an occlusion lead of exactly KILL_OCCLUSION passes', 'and margin >= KILL_OCCLUSION', 'and margin > KILL_OCCLUSION', KILL),
  e('eval: NaN is a rethink, never a pass', 'return diff > KILL_DIFF and margin >= KILL_OCCLUSION', 'return not (diff <= KILL_DIFF or margin < KILL_OCCLUSION)', KILL),
  e('eval: two logs of one episode are an error', 'if len(set(keys)) != len(keys):', 'if False:', 'test_two_logs_of_one_episode_are_an_error'),
  e('eval: the kill rule is judged on seeds 1010-1019', 'for x in logs if x.scenario.seed in KILL_SEEDS]', 'for x in logs]', 'test_the_kill_line_on_real_logs'),
  e('eval: near pairs are drawn', 'if np.abs(pos[i] - pos[j]).max() < ELEMENT_PX', 'if np.abs(pos[i] - pos[j]).max() < 0', 'test_two_elements_drawn_on_one_spot_overlap_and_apart_do_not'),
  e('eval: the replay keeps the run\'s acting flag', 'arena.step(a, b.phase == "act")', 'arena.step(a, True)', 'test_the_replay_rebuilds_the_runs_own_world'),
);
