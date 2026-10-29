// The rules-only wiring on the real arena (the rule policy's advice line, the rules turn, the diagnosis' verdict on the log).
// tests/test_agent.py breaks on these too, in hand-built worlds; here each must also break an end-to-end node.
// Each runs its one node, not the file: the file is 20 seeds x 6 cases, a minute alone.
const T = 'tests/test_e2e.py', A = 'gate/agent.py';
const m = (from, find, replace, test) => ({ from, file:A, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`,
  cmd:`uv run --locked python -m pytest -q "${T}::${test}"` });
const RIGHT = 'test_the_episode_ends_right_by_evals_table';
module.exports = [
  m('end to end: the rules turn reads the advice line the rule policy writes', 'return f"advice: {advice.kind}{target}: {advice.reason}"',
    'return f"advice: {advice.kind}{target} {advice.reason}"', `${RIGHT}[blocked-0]`),
  m('end to end: a rules decline carries the rule policy\'s reason to the log', 'call = ToolCall("decline", {"reason": reason}, "rules")',
    'call = ToolCall("decline", {}, "rules")', 'test_a_body_blocked_decline_cites_the_body'),
  m('end to end: the diagnostic probe records its verdict on the block', 'advice=advice, diagnosis=found\n', 'advice=advice\n',
    `${RIGHT}[body_remap-2]`),
];
