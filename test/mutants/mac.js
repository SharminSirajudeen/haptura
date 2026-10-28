// The desktop owner gate (plan §4e, Mac session): one entry per guarded line, in T0's shape.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_mac_owner.py';
module.exports = [
  { from:'mac: a failed hit-test names nobody', file:'mac/owner.py',
    find:'    if d["err"] != 0:\n', replace:'    if d["err"] == 12345:\n',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_a_failed_hit_test_names_nobody` },
  { from:'mac: no bundle falls back to the pid', file:'mac/owner.py',
    find:'        return f"pid:{self.pid}" if self.pid else ""\n', replace:'        return self.bundle\n',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_a_process_without_a_bundle_is_keyed_by_pid` },
  { from:'mac: the desktop allowlist is the one used', file:'mac/owner.py',
    find:'    return check_tap(owner.key, task_app, MAC_SYSTEM_ALLOW)\n', replace:'    return check_tap(owner.key, task_app)\n',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_the_dock_is_allowlisted` },
  { from:'mac: outside points sit OUTSIDE_PX beyond the edge', file:'mac/owner.py',
    find:'    outside = [(x - d, cy), (x + w + d, cy), (cx, y - d), (cx, y + h + d), (x - d, y - d)]\n',
    replace:'    outside = [(x - d, cy), (x + w, cy), (cx, y - d), (cx, y + h + d), (x - d, y - d)]\n',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_proof_points_alternate_and_sit_where_they_say` },
];
module.exports.push(
  { from:'mac: a bundle id counts only under /System/', file:'mac/owner.py',
    find:'        if self.bundle and self.path.startswith(SYSTEM_DIR):\n', replace:'        if self.bundle:\n',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_a_bundle_id_outside_system_is_not_trusted` },
  { from:'mac: notification and authorisation dialogs are not allowlisted', file:'mac/owner.py',
    find:'MAC_SYSTEM_ALLOW = frozenset({"com.apple.dock", "com.apple.systemuiserver"})',
    replace:'MAC_SYSTEM_ALLOW = frozenset({"com.apple.dock", "com.apple.systemuiserver", "com.apple.UserNotificationCenter"})',
    mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::test_the_dock_is_allowlisted` },
);
