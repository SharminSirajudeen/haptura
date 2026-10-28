// T13: the runner. Each break is the one a reviewer would try first on that line.
const T = 'tests/test_run.py';
const m = (from, find, replace, test) => ({ from, file:'gate/run.py', find, replace, mustFail:T, expect:`FAILED ${T}::${test}`,
  cmd:`uv run --locked python -m pytest -q ${T}` });
const STOP = 'test_the_run_stops_before_an_episode_would_pass_the_budget';
module.exports = [
  m('T13: a run above its budget is refused', 'if plan["usd"] > budget:', 'if False:', 'test_a_paid_run_above_its_budget_is_refused_before_it_starts'),
  m('T13: an episode on disk is not run again', '        if not path.exists():\n', '        if True:\n', 'test_a_free_run_writes_each_log_and_a_rerun_resumes'),
  m('T13: the guard uses the measured cost when it is higher', 'step = max(each, spent / len(done)) if done else each', 'step = each', STOP),
  m('T13: spend already on disk counts', 'spent, each = sum(map(dollars, done)),', 'spent, each = 0.0,', STOP),
  m('T13: push once a seed, after its last case', 'if push and c == CASES[-1]:', 'if push:', 'test_push_commits_and_pushes_after_every_seed'),
  m('T13: SAM bills 50 frames a block', 'frames = n * SAM_MIN_FRAMES * sam', 'frames = n * 31 * sam', 'test_the_projection_by_hand'),
  m('T13: baseline a runs with the gate off', '"no-gate+SAM": (False, "sam", "muse"),', '"no-gate+SAM": (True, "sam", "muse"),', 'test_each_condition_runs_as_evals_table_says'),
  m('T13: rules-only runs S15, not Muse', '"rules-only+SAM": (True, "sam", "rules"),', '"rules-only+SAM": (True, "sam", "muse"),', 'test_each_condition_runs_as_evals_table_says'),
];
