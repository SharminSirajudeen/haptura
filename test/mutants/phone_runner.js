// The runner's gate path (phone/ghostei.py, adb.py): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const G = 'tests/test_phone_ghostei.py', R = 'tests/test_phone_rules.py';
const m = (from, file, find, replace, t, test) =>
  ({ from, file, find, replace, mustFail:t, cmd:`${PY} ${t}`, expect:`FAILED ${t}::${test}` });
module.exports = [
  m('runner: a gated tap waits for the verdict', 'phone/ghostei.py',
    '        tapped = not gate or v.kind == "allow"\n', '        tapped = True\n', G, 'test_a_gated_tap_on_the_overlay_is_never_sent'),
  m('runner: the owner is read inside the click watch, right before the tap', 'phone/ghostei.py',
    '    def act() -> tuple[windows.Window | None, str, Verdict, bool, list[int], str]:\n        marks = [time.perf_counter_ns()]\n        dump = adb.input_dump()\n',
    '    dump = adb.input_dump()\n\n    def act() -> tuple[windows.Window | None, str, Verdict, bool, list[int], str]:\n        marks = [time.perf_counter_ns()]\n', G, 'test_a_gated_tap_on_the_overlay_is_never_sent'),
  m('runner: the allowlist is cut to system packages', 'phone/ghostei.py',
    'SYSTEM_ALLOW & packages(system_list))', 'SYSTEM_ALLOW)', G, 'test_the_allowlist_is_cut_to_this_devices_system_packages'),
  m('adb: the old dump file goes before each dump', 'phone/adb.py',
    'shell("rm -f /sdcard/ui.xml; uiautomator dump /sdcard/ui.xml")', 'shell("uiautomator dump /sdcard/ui.xml")', G,
    'test_the_dump_file_is_removed_before_each_dump'),
  m('rules: the permission controller is not allowlisted', 'phone/rules.py',
    '    "com.android.systemui",  # system dialogs and the notification shade\n',
    '    "com.android.systemui",  # system dialogs and the notification shade\n    "com.google.android.permissioncontroller",\n',
    R, 'test_the_permission_controller_is_not_allowlisted'),
];
const LABKEY = 'test_the_keyboard_over_a_focused_task_app_is_named_and_refused', CLOCK = 'test_the_timing_marks_bracket_the_dump_and_the_send';
module.exports.push(
  m('runner: a tap is judged by the window that receives it, not the focused one', 'phone/ghostei.py',
    'w = windows.receiver(windows.parse_windows(text), x, y)', 'w = windows.focused(windows.parse_windows(text), text)', G, LABKEY),
  m('runner: the first mark is taken before the dump', 'phone/ghostei.py',
    '        marks = [time.perf_counter_ns()]\n        dump = adb.input_dump()\n', '        dump = adb.input_dump()\n        marks = [time.perf_counter_ns()]\n', G, CLOCK),
  m('runner: the last mark is taken after the send', 'phone/ghostei.py',
    'marks + [time.perf_counter_ns() if tapped else marks[-1]]', 'marks + [marks[-1]]', G, CLOCK),
  m('runner: a refused tap has no send time', 'phone/ghostei.py',
    'marks + [time.perf_counter_ns() if tapped else marks[-1]]', 'marks + [time.perf_counter_ns()]', G, 'test_a_refused_tap_has_no_send_time'),
);
module.exports.push(
  m('runner: the record names the receiving window', 'phone/ghostei.py', '"receiver_uid": w.uid if w else None,', '"receiver_uid": None,', G, 'test_the_record_names_the_receiver_and_what_a_focus_check_would_say'),
  m('runner: the record carries the tap point', 'phone/ghostei.py', '        "x": x,\n        "y": y,\n', '', G, 'test_the_record_carries_the_tap_point'),
  m('runner: the focus comparator reads the focused window', 'phone/ghostei.py',
    'focus = focus_owner(dump, dev, task)', 'focus = owner', G, 'test_the_record_names_the_receiver_and_what_a_focus_check_would_say'),
);
const UNREAD = 'test_an_unreadable_window_list_is_gated_not_dropped';
const EMPTY = 'test_an_empty_dump_is_not_unreadable_and_costs_no_model_call';
const REP = 'tests/test_phone_report.py';
module.exports.push(
  m('runner: an unreadable window list is gated, not dropped', 'phone/ghostei.py', 'if attack and readable and not rec["overlay_shown"]:', 'if attack and not rec["overlay_shown"]:', G, UNREAD),
  m('runner: the record says whether the window list was readable', 'phone/ghostei.py', '"dump_readable": readable', '"dump_readable": True', G, UNREAD),
  m('runner: unreadable means the grammar broke, not an empty dump', 'phone/ghostei.py', 'windows.window_lines(text) is not None', 'bool(wins)', G, EMPTY),
  m('report: a block on an unreadable list is counted', 'phone/report.py', 'sum(1 for r in taps if r.get("dump_readable") is False)', '0', REP, 'test_a_block_on_an_unreadable_window_list_is_named_in_the_row'),
);
const FIRST = 'test_a_case_runs_on_the_first_package_of_its_app_that_can_start';
module.exports.push(
  m('runner: a case runs on the first package of its app that can start', 'phone/ghostei.py', 'for p in PKG.get(a, ()) if p in startable', 'for p in PKG.get(a, ())[:1] if p in startable', G, FIRST),
  m('runner: startable packages are read by package name', 'phone/ghostei.py', 'ln.strip().split("/")[0]', 'ln.strip()', G, 'test_startable_packages_are_read_from_the_launcher_list'),
);
