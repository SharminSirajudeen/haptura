// The replay runner (phone/replay.py): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_phone_replay.py';
const m = (from, find, replace, test) =>
  ({ from, file:'phone/replay.py', find, replace, mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::${test}` });
module.exports = [
  m('replay: the recorded touch goes through the gate when it is on',
    'f"input tap {x} {y}", r.app, r.gate, r.dev)', 'f"input tap {x} {y}", r.app, False, r.dev)', 'test_gate_on_the_same_touch_is_refused'),
  m('replay: the attack fires before the recorded touch', '    fire(step)\n', '', 'test_gate_off_the_recorded_touch_is_sent_after_the_attack'),
  m('replay: a label not on screen stops the replay', '    if n is None:\n        return {"gate": r.gate, "replayed": False,', '    if False:\n        return {"gate": r.gate, "replayed": False,',
    'test_a_label_no_longer_on_screen_stops_the_replay'),
  m('replay: a step the run refused is skipped', '        if "refused" in rec or rec.get("tapped") is False:\n            continue', '        if False:\n            continue',
    'test_a_step_the_run_refused_is_not_redone'),
  m('replay: a refused scroll stops the replay', 'elif a["kind"] == "scroll" and not agent.scroll(a["arg"], r)["tapped"]:', 'elif a["kind"] == "scroll" and not agent.scroll(a["arg"], r) and False:',
    'test_a_refused_scroll_stops_the_replay'),
  m('replay: an open makes that app the task app', '        r.app = a["arg"]\n', '', 'test_gate_on_the_same_touch_is_refused'),
  m('replay: the element is found by its recorded number', 'return els[i] if i < len(els) and agent.label(els[i]) == rec["label"] else None', 'return els[i] if i < len(els) else None',
    'test_a_label_no_longer_on_screen_stops_the_replay'),
];
