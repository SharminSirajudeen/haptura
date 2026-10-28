// Phone lane (plan §4b): one entry per guarded line, in T0's shape. The list test/mutants.list.js picks this file up.
const PY = 'uv run --locked python -m pytest -q';
const RULES = 'tests/test_phone_rules.py', UI = 'tests/test_phone_ui.py';
module.exports = [
  { from:'owner rule: foreign window blocked', file:'phone/rules.py',
    find:'    return Verdict("block", f"window owned by {owner or \'unknown\'}, not the task app {task_pkg}")\n',
    replace:'    return Verdict("allow", f"window owned by {owner or \'unknown\'}, not the task app {task_pkg}")\n',
    mustFail:RULES, cmd:`${PY} ${RULES}`, expect:`FAILED ${RULES}::test_foreign_owner_blocked` },
  { from:'owner rule: the allow parameter is the one used', file:'phone/rules.py',
    find:'    if owner in allow:\n', replace:'    if owner in SYSTEM_ALLOW:\n',
    mustFail:RULES, cmd:`${PY} ${RULES}`, expect:`FAILED ${RULES}::test_allowlist_parameter_is_the_one_used` },
  { from:'owner rule: a block names the owner', file:'phone/rules.py',
    find:'f"window owned by {owner or \'unknown\'}, not the task app {task_pkg}"', replace:'"window owner is not the task app"',
    mustFail:RULES, cmd:`${PY} ${RULES}`, expect:`FAILED ${RULES}::test_unknown_owner_blocked` },
  { from:'ui: the smallest containing node wins', file:'phone/ui.py',
    find:'    return min(hits, key=area, default=None)\n', replace:'    return max(hits, key=area, default=None)\n',
    mustFail:UI, cmd:`${PY} ${UI}`, expect:`FAILED ${UI}::test_point_in_the_confirm_button_reaches_it` },
  { from:'ui: the y range is checked', file:'phone/ui.py',
    find:'n.bounds[0] <= x < n.bounds[2] and n.bounds[1] <= y < n.bounds[3]]', replace:'n.bounds[0] <= x < n.bounds[2]]',
    mustFail:UI, cmd:`${PY} ${UI}`, expect:`FAILED ${UI}::test_point_on_the_scrim_reaches_the_overlay_root` },
  { from:'ui: the bottom edge is exclusive', file:'phone/ui.py',
    find:'n.bounds[1] <= y < n.bounds[3]]', replace:'n.bounds[1] <= y <= n.bounds[3]]',
    mustFail:UI, cmd:`${PY} ${UI}`, expect:`FAILED ${UI}::test_bottom_edge_is_exclusive` },
];
