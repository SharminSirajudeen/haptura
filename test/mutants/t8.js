// T8: the trackers and S9.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_trackers.py';
const T = 'tests/test_trackers.py';
const m = (from, file, find, replace, test) => ({ from, file, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
module.exports = [
  m('S14 on the colour swap: a look-alike must be near the prediction', 'gate/gate.py', '_dist(p[t2], guess) <= JUMP_TOL]', '_dist(p[t2], guess) < 0]', 'test_at_a_forced_crossing_the_colour_tracker_swaps_and_s14_catches_it'),
  m('S9: nearest pair first, not id order', 'gate/trackers.py', '    pairs = sorted(\n', '    pairs = list(\n', 'test_match_ids_is_greedy_on_the_closest_pair_first'),
  m('S9: unmatched ids are fresh, not reused', 'gate/trackers.py', '            k, fresh = fresh, fresh + 1\n', '            k = fresh\n', 'test_match_ids_links_by_nearest_first_position_and_mints_fresh_ids'),
  m('colour: association from the latest position', 'gate/trackers.py', '    return (float(track[visible[-1], 0]), float(track[visible[-1], 1]))\n', '    return (float(track[visible[0], 0]), float(track[visible[0], 1]))\n', 'test_colour_tracker_associates_from_the_latest_position_not_the_first'),
  m('S9: matched on the first visible frame', 'gate/trackers.py', '    return (float(track[visible[0], 0]), float(track[visible[0], 1]))\n', '    return (float(track[visible[-1], 0]), float(track[visible[-1], 1]))\n', 'test_match_ids_links_by_nearest_first_position_and_mints_fresh_ids'),
  m('colour: components are per colour', 'gate/trackers.py', '_components(np.all(frame == colour, axis=2))', '_components(frame.any(axis=2))', 'test_colour_tracker_finds_the_three_elements_with_hand_derived_centres'),
  m('colour: an absent element is NaN, not carried', 'gate/trackers.py', 'tracks[oid] = np.full((n, 2), np.nan)', 'tracks[oid] = np.zeros((n, 2))', 'test_colour_tracker_swaps_the_two_red_ids_at_the_crossing'),
  m('truth: absent frames stay NaN', 'gate/trackers.py', '    tracks: Tracks = {i: np.full((len(history), 2), np.nan) for i in ids}\n', '    tracks: Tracks = {i: np.zeros((len(history), 2)) for i in ids}\n', 'test_truth_tracker_keeps_absent_frames_nan'),
];
