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
    '    if w and task_pkg in pkgs and (len(pkgs) == 1 or f" {task_pkg}/" in w.name):\n        return task_pkg\n', '', 'test_a_shared_system_uid_resolves_to_the_task_app_it_contains'),
  m('windows: an allowlisted package of the uid is preferred',
    'min(pkgs & allow, default=min(pkgs, default=""))', 'min(pkgs, default="")', 'test_an_allowlisted_package_of_the_uid_is_named'),
];
module.exports.push(
  m('windows: an owner field outside a list breaks the grammar',
    '        return "ownerUid=" not in line\n', '        return True\n', 'test_a_title_that_ends_the_list_early_blocks_everything'),
  m('windows: a window line names each trusted field once',
    '        return all(line.count(f) == 1 for f in TRUSTED)\n', '        return True\n',
    'test_a_title_that_repeats_a_trusted_field_blocks_everything'),
  m('windows: any other line in a list breaks the grammar',
    '    return bool(NOT_A_WINDOW.match(line))\n', '    return True\n',
    'test_a_title_that_strands_the_real_fields_on_a_stray_line_blocks_everything'),
  m('windows: a list ends at the first line as shallow as its header',
    '            r.in_list = False  # the list ended', '            pass  # the list ended', 'test_the_full_dump_parses_and_other_sections_are_ignored'),
  m('windows: only display 0 is ours',
    '        if display == "0":\n', '        if display:\n', 'test_a_window_on_another_display_is_not_ours'),
);
module.exports.push(
  m('windows: a transform line is the whole line',
    '( \\([A-Z ]+\\))?$|', '( \\([A-Z ]+\\))?|', 'test_a_title_that_forges_its_flags_onto_a_transform_line_blocks_everything'),
  m('windows: window indices run 0, 1, 2 with no repeat',
    ' or int(n.group(1)) != self.index:', ':', 'test_a_title_that_adds_a_window_line_blocks_everything'),
);
module.exports.push(
  m('windows: one window list per display',
    '        if SECTION.match(line) and self.display in self.listed:\n',
    '        if SECTION.match(line) and not self.display:\n', 'test_a_title_that_forges_a_list_header_blocks_everything'),
  m('windows: a window line carries its list\'s display',
    'or m.group(2) != self.display or', 'or', 'test_a_title_that_forges_a_list_header_blocks_everything'),
);
module.exports.push(
  m('windows: window indices are ASCII digits', 'INDEX = re.compile(r"^ +(\\d+): name=", re.ASCII)', 'INDEX = re.compile(r"^ +(\\d+): name=")',
    'test_only_ascii_digits_number_a_window_or_a_display'),
);
module.exports.push(
  m('windows: a shared uid needs the task component in the window name',
    ' and (len(pkgs) == 1 or f" {task_pkg}/" in w.name):', ':', 'test_a_shared_uid_window_without_the_tasks_component_is_not_the_task_app'),
  m('windows: shown counts only visible, touchable windows',
    '    return any(w.uid in mine and not w.flags & SKIP for w in windows)\n', '    return any(w.uid in mine for w in windows)\n',
    'test_the_overlay_is_shown_whether_or_not_it_has_focus'),
);
module.exports.push(
  m('windows: a mirrored window may have a negative id', ', id=-?\\d+, displayId=', ', id=\\d+, displayId=',
    'test_a_screen_recording_mirror_display_is_read_not_rejected'),
);
