// T5: S13, the gate, and S15, the rule policy. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_gate.py';
const T = 'tests/test_gate.py', G = 'gate/gate.py';
const m = (from, find, replace, test) => ({ from, file:G, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
module.exports = [
  m('S13: a single mine, not any mine', '    if len(mine) != 1:\n', '    if not mine:\n', 'test_refuses_when_two_are_mine'),
  m('S13: the object must be the mine one', '    if mine[0] != object_id:\n        return Decision(\n            "refused", object_id, f"object {object_id} is not mine; object {mine[0]} is"\n        )\n', '', 'test_refuses_when_the_object_is_not_the_mine_one'),
  m('S13, S15: the label says mine, never p', 'e.label == "mine"', 'e.p0 < ALPHA_PROBE', 'test_refuses_at_p_just_above_alpha_act_since_the_label_says_not_me'),
  m('S15: the act rule comes before the budget rule',
    '    if len(mine) == 1:\n        return _act_or_decline(mine[0], target_pos, goal)\n    if blocks_used >= budget:\n        return Decision("decline", None, f"no single mine element after all {budget} looks")\n',
    '    if blocks_used >= budget:\n        return Decision("decline", None, f"no single mine element after all {budget} looks")\n    if len(mine) == 1:\n        return _act_or_decline(mine[0], target_pos, goal)\n',
    'test_acts_on_the_single_mine_when_the_goal_is_reachable'),
  m('S15: a single mine, not any mine', '    if len(mine) == 1:\n', '    if mine:\n', 'test_two_mine_is_not_a_single_mine_so_the_policy_probes'),
  m('S15: the budget is spent at >=, not >', 'if blocks_used >= budget:', 'if blocks_used > budget:', 'test_declines_when_the_budget_is_spent'),
  m('S15: three looks before the early decline', 'EARLY_LOOKS = 3', 'EARLY_LOOKS = 2', 'test_does_not_decline_early_after_two_looks'),
  m('S15: the early decline fires at three looks, not after', 'blocks_used >= EARLY_LOOKS', 'blocks_used > EARLY_LOOKS', 'test_declines_early_after_three_looks_when_every_p0_is_above_alpha_probe'),
  m('S15: every p0 above ALPHA_PROBE, not any', 'all(e.p0 > ALPHA_PROBE', 'any(e.p0 > ALPHA_PROBE', 'test_probes_within_budget_while_some_p0_is_at_or_below_alpha_probe'),
  m('S15: p0 strictly above ALPHA_PROBE', 'e.p0 > ALPHA_PROBE', 'e.p0 >= ALPHA_PROBE', 'test_probes_within_budget_while_some_p0_is_at_or_below_alpha_probe'),
  m('S15: the goal centre, not its corner', 'centre = ((goal[0] + goal[2]) / 2, (goal[1] + goal[3]) / 2)', 'centre = (goal[0], goal[1])', 'test_acts_on_the_single_mine_when_the_goal_is_reachable'),
  m('S15: an axis the goal does not need is not checked', 'need == 0 or ', '', 'test_acts_on_the_single_mine_when_the_goal_is_reachable'),
  m('S15: reachability needs the sign', 'v[axis] * need > 0 and ', '', 'test_declines_citing_the_body_when_no_live_action_moves_toward_the_goal'),
  m('S15: reachability needs the magnitude', ' and abs(v[axis]) >= EFFECT_MIN', '', 'test_a_component_of_the_right_sign_below_effect_min_does_not_count'),
  m('S15: a component of exactly EFFECT_MIN counts', 'abs(v[axis]) >= EFFECT_MIN', 'abs(v[axis]) > EFFECT_MIN', 'test_acts_on_the_single_mine_when_the_goal_is_reachable'),
];
