// T4: S10 control_scores and S12 design_block. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_control.py';
const T = 'tests/test_control.py', F = 'gate/control.py';
const m = (from, find, replace, test) => ({ from, file:F, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
const FOLLOWER = 'test_perfect_follower_is_mine_at_the_floor_on_20_designs';
const LOST = 'test_an_action_whose_every_step_is_lost_has_no_body';
const WALL = 'test_an_element_pressed_to_a_wall_is_mine_through_its_moves_along_it';
const NO_EVIDENCE = 'test_no_evidence_gives_p_one_at_every_lag_and_the_smaller_lag_on_a_tie';
const ECHO = 'test_pure_echo_at_lag_2_is_echo_with_best_lag_2';
const DESIGN = 'test_design_block_has_the_noop_rate_the_floor_and_balanced_directions';
module.exports = [
  m('S10: the grand mean is the reference, not the no-op mean (index 2 of the sorted names)', '(means - grand) ** 2', '(means - means[:, 2:3]) ** 2', FOLLOWER),
  m('S10: a shuffle that ties the observed S counts against it', 'spread[1:] >= spread[0]', 'spread[1:] > spread[0]', NO_EVIDENCE),
  m('S10: the observed labelling counts itself', '(1 + int(np.count_nonzero(spread[1:] >= spread[0])))', 'int(np.count_nonzero(spread[1:] >= spread[0]))', FOLLOWER),
  m('S10: the labels are shuffled', '    rng.permuted(rows[1:], axis=1, out=rows[1:])\n', '', FOLLOWER),
  m('S10: an empty group adds nothing to S', 'spread = np.nansum(', 'spread = np.sum(', NO_EVIDENCE),
  m('S10: ties go to the smaller lag', 'best = 1 + int(np.argmin(p[1:]))', 'best = max_lag - int(np.argmin(p[:0:-1]))', NO_EVIDENCE),
  m('S10: lag k pairs a_t with d_{t+k}', 'lab, disp = labels[: len(labels) - k][keep], d[k:][keep]', 'lab, disp = labels[k:][keep], d[k:][keep]', ECHO),
  m('S10: a lost frame is dropped, not zero-filled', 'd = pos[1:] - pos[:-1]', 'd = np.diff(np.nan_to_num(pos), axis=0)', 'test_nan_gaps_are_dropped_not_zero_filled'),
  m('S10: a step at a wall is kept (#24): the old rule, back', '    ok = ~np.isnan(d).any(axis=1)\n', '    far = (np.minimum(pos, 128 - pos) > 5).all(axis=1)\n    ok = ~np.isnan(d).any(axis=1) & far[:-1] & far[1:]\n', WALL),
  m('S10: a step with a NaN is dropped', 'ok = ~np.isnan(d).any(axis=1)\n', 'ok = np.ones(len(d), dtype=bool)\n', 'test_nan_gaps_are_dropped_not_zero_filled'),
  m('S10: the body is referenced to the no-op mean', 'e = means - means[names.index(NOOP)]', 'e = means', 'test_mirrored_follower_on_a_drift_is_mine_and_a_dead_action_has_no_effect'),
  m('S10: an action with no sample is None, not zero', 'a: None if np.isnan(e[i]).any() else', 'a: (0.0, 0.0) if np.isnan(e[i]).any() else', LOST),
  m('S10: mine needs p_0 below ALPHA_ACT', 'if p[0] < ALPHA_ACT and effect >= EFFECT_MIN:', 'if effect >= EFFECT_MIN:', 'test_independent_random_walk_is_not_me'),
  m('S10: mine needs an effect of at least EFFECT_MIN', 'if p[0] < ALPHA_ACT and effect >= EFFECT_MIN:', 'if p[0] < ALPHA_ACT:', 'test_a_follower_below_effect_min_is_not_mine'),
  m('S10: echo reads p_best, not p_0', 'elif p[best] < ALPHA_ACT:', 'elif p[0] < ALPHA_ACT:', ECHO),
  m('S12: at least 2 no-ops', 'n_noop = max(2, round(p_noop * n))', 'n_noop = round(p_noop * n)', DESIGN),
  m('S12: the no-op count follows p_noop', 'n_noop = max(2, round(p_noop * n))', 'n_noop = max(2, round(0.3 * n))', DESIGN),
  m('S12: the directions are balanced', 'dirs[(start + i) % len(dirs)]', 'str(rng.choice(dirs))', DESIGN),
  m('S12: the order is drawn from the rng', '    rng.shuffle(pool)\n', '', 'test_design_block_order_comes_from_the_rng'),
];
