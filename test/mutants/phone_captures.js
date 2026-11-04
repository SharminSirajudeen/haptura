// The demo page's captures (phone/captures.py, web/captures/*.json): one entry per guarded line. Each names one
// parametrized node, `[replay]` or `[lab]`, of tests/test_phone_captures.py.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_phone_captures.py';
const m = (from, file, find, replace, test) =>
  ({ from, file, find, replace, mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::${test}` });
const BUILT = 'test_the_page_carries_what_the_records_build', DERIVES = 'test_the_recorded_touch_rederives_on_its_capture';
const FRAME = 'test_the_frame_is_half_the_screen';
const C = 'phone/captures.py';
module.exports = [
  m("captures: the dialog screen's allowlist without the keyboard", C, '"allow": sorted(SYSTEM_ALLOW | ghostei.device("", "", env("keyboard")).allow),', '"allow": sorted(SYSTEM_ALLOW),', `${BUILT}[replay]`),
  m("captures: the dialog screen's task app from the step before", C, 'if s["step"] == off["step"]', 'if s["step"] == off["step"] - 1', `${BUILT}[replay]`),
  m('captures: the keyboard screen built from the ungated trial', C, 'if t["arrangement"] == "gated-key"', 'if t["arrangement"] == "ungated-key"', `${BUILT}[lab]`),
  m("captures: the touch's point with its axes swapped", C, '    touch = {k: off[k] for k in ("x", "y", "verdict", "receiver_uid")}\n', '    touch = {k: off[k] for k in ("verdict", "receiver_uid")} | {"x": off["y"], "y": off["x"]}\n', `${DERIVES}[replay]`),
  m("captures: the keyboard screen's frame is another image", C, '"image": "media/lab-gated-key.png",', '"image": "media/case26-poster.png",', `${FRAME}[lab]`),
  m("captures: the dialog screen's task app edited on the page", 'web/captures/replay.json', '"task": "com.google.android.deskclock"', '"task": "com.android.settings"', `${BUILT}[replay]`),
];
