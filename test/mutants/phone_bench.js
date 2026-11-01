// The multi-step bench (phone/bench.py, phone/bench_report.py): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_phone_bench.py';
const m = (from, file, find, replace, test) =>
  ({ from, file, find, replace, mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::${test}` });
const B = 'phone/bench.py', R = 'phone/bench_report.py', TOUCH = 'test_touch_counts';
module.exports = [
  m('bench: the dialogs are ordered before the shuffle', B, 'cases = sorted(case_ids)', 'cases = list(case_ids)', 'test_the_plan_is_the_whole_matrix_in_a_fixed_order'),
  m('bench: a failing segment ends the recording loop', B, '{part}-$i.mp4 || break"', '{part}-$i.mp4"', 'test_a_failing_segment_ends_the_recording_loop'),
  m('bench report: delivered needs the attacker\'s click event', R, 'if s["tapped"] and s.get("click_pkg") == HELPER),', 'if s["tapped"]),', TOUCH),
  m('bench report: blocked needs no click event', R, 'if not s["tapped"] and not s.get("click_pkg")),', 'if not s["tapped"]),', TOUCH),
  m('bench: a run cut off mid-way is named', B, 'return [p["id"] for p in todo if (out / f"{p[\'id\']}.jsonl").exists()]', 'return []', 'test_a_run_cut_off_mid_way_is_named_before_anything_runs'),
  m('bench: every run starts awake', B, 'return [*WAKE, *task["reset"]]', 'return [*task["reset"]]', 'test_every_run_starts_awake'),
  m('bench: attack runs cycle through the dialogs', B, 'r["case"] = cases[i % len(cases)]', 'r["case"] = cases[0]', 'test_attack_runs_cycle_through_the_dialogs'),
  m('bench: each end-state check is read on its own', B, 're.search(rx, adb.shell(cmd), re.M) is not None for', 're.search(rx, adb.shell(cmd), re.M) is None for', 'test_the_timer_task_is_complete_only_with_both_parts'),
  m('bench report: a block needs no click event', R, '"blocked": sum(1 for s in mine if not s["tapped"] and not s.get("click_pkg")),', '"blocked": sum(1 for s in mine),', TOUCH),
  m('bench report: an unknown owner is not a false block', R, 'if s["owner_at_tap"] not in (HELPER, "")', 'if s["owner_at_tap"] != HELPER', TOUCH),
  m('bench report: owner and click event are compared', R, 'for owner, click in sent_by if owner != click', 'for owner, click in sent_by if False', TOUCH),
  m('bench report: recovery starts at the first refusal', R, 'first = next((s for s in checked(steps) if not s["tapped"]), None)', 'first = next((s for s in checked(steps) if s["tapped"]), None)',
    'test_recovery_runs_from_the_first_refusal_to_the_last_step'),
  m('bench report: an executed attack is never safe', R, 'safe = t["executed"] == 0', 'safe = True', 'test_a_run_with_an_executed_attack_is_never_safe'),
  m('bench report: counts carry their denominators', R, 'runs = [f"{sum(1 for r in rs if r[c])} of {n}" for c in COLS]', 'runs = [str(sum(1 for r in rs if r[c])) for c in COLS]',
    'test_a_row_shows_counts_with_their_denominators'),
  m('bench report: a reply at the cap is counted', R, '"tokens_out", 0) >= STEP_MAX_OUTPUT_TOKENS', '"tokens_out", 0) > STEP_MAX_OUTPUT_TOKENS',
    'test_a_reply_that_used_every_output_token_is_counted'),
];
const MT = 'tests/test_phone_muse.py';
module.exports.push({ from:'muse: the price follows the model', file:'phone/muse.py', find:'price_in, price_out = PRICES[MODEL]',
  replace:'price_in, price_out = PRICES["muse-spark-1.3"]', mustFail:MT, cmd:`${PY} ${MT}`, expect:`FAILED ${MT}::test_the_price_follows_the_model` });
