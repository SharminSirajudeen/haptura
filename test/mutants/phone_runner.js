// The runner's gate path (phone/ghostei.py, adb.py): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const G = 'tests/test_phone_ghostei.py', R = 'tests/test_phone_rules.py';
const m = (from, file, find, replace, t, test) =>
  ({ from, file, find, replace, mustFail:t, cmd:`${PY} ${t}`, expect:`FAILED ${t}::${test}` });
module.exports = [
  m('runner: a gated tap waits for the verdict', 'phone/ghostei.py',
    '        tapped = not gate or v.kind == "allow"\n', '        tapped = True\n', G, 'test_a_gated_tap_on_the_overlay_is_never_sent'),
  m('runner: the owner is read inside the click watch, right before the tap', 'phone/ghostei.py',
    '    def act() -> tuple[str, Verdict, bool]:\n        owner = owner_now(dev, task, x, y)\n',
    '    owner = owner_now(dev, task, x, y)\n\n    def act() -> tuple[str, Verdict, bool]:\n', G, 'test_a_gated_tap_on_the_overlay_is_never_sent'),
  m('runner: the allowlist is cut to system packages', 'phone/ghostei.py',
    'SYSTEM_ALLOW & system)', 'SYSTEM_ALLOW)', G, 'test_the_allowlist_is_cut_to_this_devices_system_packages'),
  m('adb: the old dump file goes before each dump', 'phone/adb.py',
    'shell("rm -f /sdcard/ui.xml; uiautomator dump /sdcard/ui.xml")', 'shell("uiautomator dump /sdcard/ui.xml")', G,
    'test_the_dump_file_is_removed_before_each_dump'),
  m('rules: the permission controller is not allowlisted', 'phone/rules.py',
    '    "com.android.systemui",  # system dialogs and the notification shade\n',
    '    "com.android.systemui",  # system dialogs and the notification shade\n    "com.google.android.permissioncontroller",\n',
    R, 'test_the_permission_controller_is_not_allowlisted'),
];
const UNREAD = 'test_an_unreadable_window_list_is_gated_not_dropped';
const EMPTY = 'test_an_empty_dump_is_not_unreadable_and_costs_no_model_call';
const REP = 'tests/test_phone_report.py';
module.exports.push(
  m('runner: an unreadable window list is gated, not dropped', 'phone/ghostei.py', 'if attack and readable and not rec["overlay_shown"]:', 'if attack and not rec["overlay_shown"]:', G, UNREAD),
  m('runner: the record says whether the window list was readable', 'phone/ghostei.py', '"dump_readable": readable', '"dump_readable": True', G, UNREAD),
  m('runner: unreadable means the grammar broke, not an empty dump', 'phone/ghostei.py', 'windows.window_lines(text) is not None', 'bool(wins)', G, EMPTY),
  m('report: a block on an unreadable list is counted', 'phone/report.py', 'sum(1 for r in taps if r.get("dump_readable") is False)', '0', REP, 'test_a_block_on_an_unreadable_window_list_is_named_in_the_row'),
);
