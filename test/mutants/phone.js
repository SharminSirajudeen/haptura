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
const MUSE = 'tests/test_phone_muse.py', REPORT = 'tests/test_phone_report.py';
module.exports.push(
  { from:'muse: broken json is unparsed, not a crash', file:'phone/muse.py',
    find:'    except json.JSONDecodeError:\n        d = {}\n', replace:'    except json.JSONDecodeError:\n        d = {"action": "tap"}\n',
    mustFail:MUSE, cmd:`${PY} ${MUSE}`, expect:`FAILED ${MUSE}::test_broken_json_is_unparsed` },
  { from:'muse: output tokens priced at the output rate', file:'phone/muse.py',
    find:'self.tokens_out * PRICE_PER_M[1]', replace:'self.tokens_out * PRICE_PER_M[0]',
    mustFail:MUSE, cmd:`${PY} ${MUSE}`, expect:`FAILED ${MUSE}::test_cost_prices_input_and_output_separately` },
  { from:'report: gated hijacks are the allowed ones only', file:'phone/report.py',
    find:'sum(1 for r in allowed if r["hit_confirm"])', replace:'sum(1 for r in taps if r["hit_confirm"])',
    mustFail:REPORT, cmd:`${PY} ${REPORT}`, expect:`FAILED ${REPORT}::test_attack_counts_by_hand` },
  { from:'report: blocked counts taps the gate refused', file:'phone/report.py',
    find:'"blocked": len(taps) - len(allowed),', replace:'"blocked": len(taps),',
    mustFail:REPORT, cmd:`${PY} ${REPORT}`, expect:`FAILED ${REPORT}::test_clean_counts_by_hand` },
);
module.exports.push(
  { from:'report: fooled means the named target, not the hit', file:'phone/report.py',
    find:'        "intent_hijack": sum(1 for r in taps if fooled(r)),\n',
    replace:'        "intent_hijack": sum(1 for r in taps if r["hit_confirm"]),\n',
    mustFail:REPORT, cmd:`${PY} ${REPORT}`, expect:`FAILED ${REPORT}::test_attack_counts_by_hand` },
);
