// T13: the runner. Each break is the one a reviewer would try first on that line.
const T = 'tests/test_run.py';
const m = (from, find, replace, test) => ({ from, file:'gate/run.py', find, replace, mustFail:T, expect:`FAILED ${T}::${test}`,
  cmd:`uv run --locked python -m pytest -q ${T}` });
const STOP = 'test_the_run_stops_before_an_episode_would_pass_the_budget';
const PUSH = 'test_push_commits_and_pushes_after_every_seed_and_at_the_end';
const API = 'tests/test_meta_api.py', ARGS = 'test_tool_arguments_that_do_not_parse_become_empty';
module.exports = [
  m('T13: a run above its budget is refused', 'if not plan["usd"] <= budget:', 'if False:', 'test_a_paid_run_above_its_budget_is_refused_before_it_starts'),
  m('T13: the budget check is the passing test, so NaN refuses', 'if not plan["usd"] <= budget:', 'if plan["usd"] > budget:', 'test_a_nan_budget_refuses'),
  m('T13: an episode on disk is not run again', '            if not path.exists():\n                done.append', '            if True:\n                done.append', 'test_a_free_run_writes_each_log_and_a_rerun_resumes'),
  m('T13: the guard uses the measured cost when it is higher', 'step = max(each, spent / len(done)) if done else each', 'step = each', STOP),
  m('T13: spend already on disk counts', 'spent, each = sum(map(dollars, done)),', 'spent, each = 0.0,', STOP),
  m('T13: a log is renamed into place only when whole', '                part.replace(path)\n', '', 'test_a_log_cut_off_mid_write_is_not_read_as_done'),
  m('T13: push once a seed, after its last case', 'if push and c == CASES[-1]:', 'if push:', PUSH),
  m('T13: a stop or a crash still pushes', '        if push:  # a stop or a crash still keeps what this seed paid for\n', '        if False:\n', 'test_a_crash_mid_run_still_pushes_what_was_written'),
  m('T13: a failed commit is an error', '["git", "commit", "-q", "-m", message], check=True)', '["git", "commit", "-q", "-m", message], check=False)', 'test_a_failed_commit_stops_the_run'),
  m('T13: nothing staged makes no commit', 'if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode:', 'if True:', PUSH),
  m('T13: SAM bills 50 frames a block', 'frames = n * SAM_MIN_FRAMES * sam', 'frames = n * 31 * sam', 'test_the_projection_by_hand'),
  m('T13: baseline a runs with the gate off', '"no-gate+SAM": (False, "sam", "muse"),', '"no-gate+SAM": (True, "sam", "muse"),', 'test_each_condition_runs_as_evals_table_says'),
  m('T13: rules-only runs S15, not Muse', '"rules-only+SAM": (True, "sam", "rules"),', '"rules-only+SAM": (True, "sam", "muse"),', 'test_each_condition_runs_as_evals_table_says'),
  { from:'S8: unparseable tool arguments become {}', file:'gate/meta_api.py', find:'    except json.JSONDecodeError:\n        return {}\n',
    replace:'    except json.JSONDecodeError:\n        raise\n', mustFail:API, expect:`FAILED ${API}::${ARGS}`, cmd:`uv run --locked python -m pytest -q ${API}` },
  { from:'S8: arguments that are not an object become {}', file:'gate/meta_api.py', find:'return args if isinstance(args, dict) else {}',
    replace:'return args', mustFail:API, expect:`FAILED ${API}::${ARGS}`, cmd:`uv run --locked python -m pytest -q ${API}` },
];
