// T11: the wiring only the offline end-to-end run exercises (S15's advice line, the rules turn, S14's verdict on
// the log). Each runs its one test, not the file: the file is 20 seeds x 6 cases, a minute alone.
const T = 'tests/test_e2e.py', A = 'gate/agent.py';
const m = (from, find, replace, test) => ({ from, file:A, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`,
  cmd:`uv run --locked python -m pytest -q "${T}::${test}"` });
module.exports = [
  m('T11: the rules turn reads the advice line S15 writes', 'return f"advice: {advice.kind}{target}: {advice.reason}"',
    'return f"advice: {advice.kind}{target} {advice.reason}"', 'test_every_case_that_cannot_succeed_is_declined[blocked]'),
  m('T11: a rules decline carries S15\'s reason to the log', 'call = ToolCall("decline", {"reason": reason}, "rules")',
    'call = ToolCall("decline", {}, "rules")', 'test_a_body_blocked_decline_cites_the_body_after_control_was_found'),
  m('T11: the diagnostic probe records its verdict on the block', 'advice=advice, diagnosis=found\n', 'advice=advice\n',
    'test_every_remap_feasible_success_went_through_target_lost'),
];
