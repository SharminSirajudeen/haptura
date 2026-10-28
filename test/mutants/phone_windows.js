// The touch owner from the input dispatcher's window list (phone/windows.py, Mac session): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_phone_windows.py';
const m = (from, find, replace, test) =>
  ({ from, file:'phone/windows.py', find, replace, mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::${test}` });
module.exports = [
  m('windows: spy windows never take the touch',
    'SKIP = frozenset({"NOT_VISIBLE", "NOT_TOUCHABLE", "SPY"})', 'SKIP = frozenset({"NOT_VISIBLE", "NOT_TOUCHABLE"})',
    'test_spy_and_untouchable_windows_are_skipped'),
  m('windows: an input sink swallows the touch',
    '        return None if SINK in w.flags else w\n', '        return w\n', 'test_a_visible_input_sink_swallows_the_touch'),
  m('windows: the region includes its top edge',
    'a <= x < c and b <= y < d', 'a <= x < c and b < y < d', 'test_a_region_includes_its_top_edge'),
  m('windows: focus matched by the full name',
    'if m and w.name == m.group(1)', 'if m', 'test_focus_is_matched_by_the_full_window_name'),
  m('windows: the task app is found in a shared uid',
    '    if task_pkg in pkgs:\n        return task_pkg\n', '', 'test_a_shared_system_uid_resolves_to_the_task_app_it_contains'),
  m('windows: an allowlisted package of the uid is preferred',
    'min(pkgs & allow, default=min(pkgs, default=""))', 'min(pkgs, default="")', 'test_an_allowlisted_package_of_the_uid_is_named'),
];
