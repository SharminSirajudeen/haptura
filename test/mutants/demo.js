// The demo's fixture stays in the EpisodeLog schema the JSON writer writes.
module.exports = [
  { from:'web fixture: the schema the page reads', file:'gate/types.py', find:'    phase: str  # probe | act\n', replace:'    phase: str  # probe | act\n    extra: str\n',
    mustFail:'tests/test_web_fixture.py', expect:'FAILED tests/test_web_fixture.py::test_the_web_fixture_round_trips_through_json',
    cmd:'uv run --locked python -m pytest -q tests/test_web_fixture.py' },
];
// gate/demo.py: the page's panes come from real logs, by the opening rule.
const TD = 'tests/test_demo.py';
const d = (from, find, replace, test) => ({ from, file:'gate/demo.py', find, replace, mustFail:TD, expect:`FAILED ${TD}::${test}`,
  cmd:`uv run --locked python -m pytest -q ${TD}` });
const RULE = 'test_the_opening_rule_picks_the_pairs', WRITE = 'test_only_a_picked_pair_is_written_for_the_page';
module.exports.push(
  d('demo: the clip is every replayed frame', 'np.stack(replay(log, render)[1])', 'np.stack(replay(log, render)[1][:1])', 'test_the_clip_is_the_runs_own_frames'),
  d('demo: the baseline must have ended in a false act', 'log.outcome != "false_act" or not acted', 'not acted', RULE),
  d('demo: within the first 20 seconds', 'f <= FIRST_FRAMES', 'f <= 10 * FIRST_FRAMES', RULE),
  d('demo: while the gated run had not acted', 'out += [] if any(b.phase == "act" and b.step0 < f for b in g.blocks) else [k]', 'out += [k]', RULE),
  d('demo: the gated run must be right', 'for k, x in one_each(gated).items() if right(x)}', 'for k, x in one_each(gated).items()}', RULE),
  d('demo: two logs for one episode are an error', 'if len(by) != len(logs):', 'if False:', RULE),
  d('demo: a pair the rule did not pick is refused', 'if len(argv) > 2 and argv[2] not in names:', 'if False:', WRITE),
  d('demo: each pane gets its own log', 'write(gated[names[argv[2]]], "gated", out)', 'write(baseline[names[argv[2]]], "gated", out)', WRITE),
);
// web/episodes/: the pair the page plays is the first the rule lists for the kill test, byte for byte the kill test's own logs.
const WP = 'tests/test_web_fixture.py', PAIR = 'test_the_page_plays_the_first_pair_the_rule_picks_from_the_kill_test';
const p = (from, file, find, replace) => ({ from, file, find, replace, mustFail:WP, expect:`FAILED ${WP}::${PAIR}`,
  cmd:`uv run --locked python -m pytest -q ${WP}` });
module.exports.push(
  p('web pair: the rule lists its pairs by seed, the first one lowest', 'gate/demo.py', '    return sorted(out)\n', '    return sorted(out, reverse=True)\n'),
  p('web pair: the gated log is the kill test\'s own', 'web/episodes/gated.json', '"sam_calls": 6', '"sam_calls": 7'),
  p('web pair: the baseline log is the kill test\'s own', 'web/episodes/baseline.json', '"outcome": "false_act"', '"outcome": "timeout"'),
);
