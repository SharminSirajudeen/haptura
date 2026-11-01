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
];
