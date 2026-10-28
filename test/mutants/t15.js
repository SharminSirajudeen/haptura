// The demo's fixture stays in the EpisodeLog schema S11 writes.
module.exports = [
  { from:'web fixture: the schema the page reads', file:'gate/types.py', find:'    phase: str  # probe | act\n', replace:'    phase: str  # probe | act\n    lane: str\n',
    mustFail:'tests/test_web_fixture.py', expect:'FAILED tests/test_web_fixture.py::test_the_web_fixture_round_trips_through_s11',
    cmd:'uv run --locked python -m pytest -q tests/test_web_fixture.py' },
];
// gate/demo.py: the page's panes come from real logs, by the plan's rule.
const TD = 'tests/test_demo.py';
const d = (from, find, replace, test) => ({ from, file:'gate/demo.py', find, replace, mustFail:TD, expect:`FAILED ${TD}::${test}`,
  cmd:`uv run --locked python -m pytest -q ${TD}` });
const RULE = 'test_the_plans_rule_picks_the_pairs', WRITE = 'test_only_a_picked_pair_is_written_for_the_page';
module.exports.push(
  d('demo: the clip is every replayed frame', 'np.stack(replay(log, render)[1])', 'np.stack(replay(log, render)[1][:1])', 'test_the_clip_is_the_runs_own_frames'),
  d('demo: the baseline must have acted on what it did not control', 'for x in baseline if x.outcome == "false_act"}', 'for x in baseline}', RULE),
  d('demo: the gated run must be right', 'for x in gated if right(x)}', 'for x in gated}', RULE),
  d('demo: a pair the rule did not pick is refused', '        if (int(seed), case) not in pairs:\n', '        if False:\n', WRITE),
  d('demo: each pane gets its own log', '(("gated", gated), ("baseline", baseline))', '(("gated", baseline), ("baseline", gated))', WRITE),
);
