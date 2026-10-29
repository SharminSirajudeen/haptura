// The arena: the scenario, the dynamics and the picture. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_arena.py';
const T = 'tests/test_arena.py';
const m = (from, find, replace, test) => ({ from, file:'gate/arena.py', find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
const SECRET = 'test_the_secret_step_covers_5_to_block_steps_minus_5';
const LAYOUT = 'test_every_scenario_is_laid_out_without_overlap_inside_the_frame';
const LOOK = 'test_every_scenario_has_two_look_alikes_and_an_echo_and_a_replay';
const GOAL = 'test_the_goal_lies_along_a_live_action_unless_the_body_is_blocked';
const WALL = 'test_a_one_way_axis_is_the_goals_and_the_goal_sits_on_its_live_wall';
const TOWARD = 'test_a_body_remap_changes_the_action_that_moves_toward_the_goal';
const MAPS = 'test_make_scenario_draws_exactly_the_eight_action_maps';
const FIRST_ACT = 'test_a_remap_case_with_the_first_act_at_step_40_fires_after_step_40';
const ECHO = 'test_an_echo_moves_by_the_action_lag_steps_ago';
const LAGS = 'test_echo_lags_cover_one_to_max_lag';
const FRAME = 'test_elements_never_leave_the_frame_and_stay_on_whole_cells';
const ARRIVAL = 'test_the_crossing_arrives_at_a_seeded_step_between_5_and_15_along_either_axis';
const AIM = 'test_each_block_aims_the_crossing_at_the_bound_elements_current_position';
const HALFWAY = 'test_the_look_alike_on_the_goal_route_sits_halfway_on_the_grid';
const MASKS = 'test_mask_pixel_counts_and_bounding_boxes';
const PIXEL = 'test_render_puts_the_expected_colour_at_a_known_pixel';
const REMAP = 'test_after_the_remap_step_the_old_element_ignores_actions';
const BODY = 'test_after_the_body_remap_step_the_new_map_applies';
module.exports = [
  // make_scenario: what the scenario contains
  m('scenario: the secret step starts at 5', 'step = int(rng.integers(5, BLOCK_STEPS - 4))', 'step = int(rng.integers(0, BLOCK_STEPS - 4))', SECRET),
  m('scenario: the secret step ends at BLOCK_STEPS - 5', 'step = int(rng.integers(5, BLOCK_STEPS - 4))', 'step = int(rng.integers(5, BLOCK_STEPS))', SECRET),
  m('scenario: at least ELEMENTS_MAX - 2 elements', 'n = ELEMENTS_MAX - int(rng.integers(0, 3))', 'n = ELEMENTS_MAX - int(rng.integers(0, 4))', LAYOUT),
  m('scenario: at most ELEMENTS_MAX elements', 'n = ELEMENTS_MAX - int(rng.integers(0, 3))', 'n = ELEMENTS_MAX + 1 - int(rng.integers(0, 3))', LAYOUT),
  m('scenario: elements start apart', '>= 2 * ELEMENT_PX for p in avoid + out', '>= ELEMENT_PX for p in avoid + out', LAYOUT),
  m('scenario: the others wear distinct colours', 'rng.permutation(len(PALETTE))[:n]', 'rng.integers(0, len(PALETTE), n)', LOOK),
  m('scenario: both look-alikes wear the subject colour', 'colours[1] = colours[2] = colours[0]', 'colours[1] = colours[0]', LOOK),
  m('scenario: look-alikes differ in shape', '*[s for s in SHAPES if s != shape0]', '*[shape0, shape0]', LOOK),
  m('scenario: an echo exists', '"decoy", "decoy", "echo", "replay"]', '"decoy", "decoy", "decoy", "replay"]', LOOK),
  m('scenario: a replay exists', '"decoy", "decoy", "echo", "replay"]', '"decoy", "decoy", "echo", "decoy"]', LOOK),
  m('scenario: the goal is BLOCK_STEPS cells from the subject', 'reach = BLOCK_STEPS * CELL_PX + GOAL_PX // 2', 'reach = BLOCK_STEPS * CELL_PX', 'test_the_goal_is_at_least_block_steps_cells_from_the_subject'),
  m('scenario: the goal stays inside the frame', 'hi = min(W - MARGIN, W - GOAL_PX // 2 - sign * reach)', 'hi = W - MARGIN', 'test_the_goal_is_at_least_block_steps_cells_from_the_subject'),
  m('scenario: body_blocked puts the goal where the dead action goes', '    if case == "body_blocked":\n        return sorted(UNITS - _live(bodies[0]))\n', '', GOAL),
  m('scenario: body_blocked draws a dead action', 'deads if case == "body_blocked" else list(BODIES)', 'list(BODIES)', GOAL),
  m('scenario: a body remap changes the map, and the action toward the goal', 'if _pool(case, [body, k])]', 'if k != body]', TOWARD),
  m('scenario: a control remap is logged', 'if len(binding) > 1:', 'if len(binding) > 2:', 'test_control_remap_cases_switch_at_the_secret_step_and_log_it'),
  m('scenario: a body remap is logged as one', '"body_remap", f"{body} -> {swap}"', '"body", f"{body} -> {swap}"', 'test_body_remap_switches_the_map_at_the_secret_step_and_logs_it'),
  m('scenario: control passes to a decoy', '"remap_feasible": ((0, 0), (step, 5))', '"remap_feasible": ((0, 0), (step, 4))', 'test_control_remap_cases_switch_at_the_secret_step_and_log_it'),
  m('scenario: blocked binds nothing', '"blocked": ((0, None),)', '"blocked": ((0, 0),)', 'test_a_blocked_scenario_has_no_controlled_binding'),
  m('scenario: the secret step is a plain int', 'step = int(rng.integers(5, BLOCK_STEPS - 4))', 'step = rng.integers(5, BLOCK_STEPS - 4)', 'test_every_case_survives_json_with_no_numpy_scalar_in_it'),
  m('scenario: all randomness is seeded', 'rng = np.random.default_rng(seed)', 'rng = np.random.default_rng()', 'test_same_seed_same_scenario_and_same_world'),
  m('scenario: mirrored on x', '"mirror_x": {**DIRS, "left": DIRS["right"], "right": DIRS["left"]},', '"mirror_x": {**DIRS},', MAPS),
  m('scenario: mirrored on y', '"mirror_y": {**DIRS, "up": DIRS["down"], "down": DIRS["up"]},', '"mirror_y": {**DIRS},', MAPS),
  m('scenario: rotated the right way', '(0.0 - dy, dx) for a, (dx, dy) in DIRS.items()', '(dy, 0.0 - dx) for a, (dx, dy) in DIRS.items()', MAPS),
  m('scenario: noop is never dead', 'for a in ACTIONS[1:]}', 'for a in ACTIONS}', MAPS),
  // Arena: the schedules, the dynamics, the crossing
  m('arena: schedules count acting steps', 'if step <= self.n_act]', 'if step <= len(self.acts)]', FIRST_ACT),
  m('arena: only acting steps advance the clock', 'self.n_act += acting', 'self.n_act += 1', FIRST_ACT),
  m('arena: control follows the binding', 'elif e.id == bound:', 'elif e.kind == "controlled":', REMAP),
  m('arena: the body map follows its schedule', 'self._at(sc.action_maps)', 'sc.action_maps[0][1]', BODY),
  m('arena: the controlled element moves by the map', 'rows.append(pos + body[action])', 'rows.append(pos + DIRS[action])', 'test_a_mirrored_map_moves_left_on_right_and_a_dead_action_moves_nothing'),
  m('arena: an echo is d steps late', 'body[self.acts[t - late] if t >= late else "noop"]', 'body[self.acts[t - late + 1] if t + 1 >= late else "noop"]', ECHO),
  m('arena: an echo moves by the body map', 'body[self.acts[t - late] if t >= late else "noop"]', 'DIRS[self.acts[t - late] if t >= late else "noop"]', ECHO),
  m('arena: echo lags reach MAX_LAG', 'self._plan.integers(1, MAX_LAG + 1)', 'self._plan.integers(1, MAX_LAG)', LAGS),
  m('arena: echo lags are at least 1', 'self._plan.integers(1, MAX_LAG + 1)', 'self._plan.integers(0, MAX_LAG + 1)', LAGS),
  m('arena: a replay walks another seed', 'np.random.default_rng([seed + 1, 1])', 'np.random.default_rng([seed, 1])', 'test_decoys_and_replays_walk_by_their_own_stream'),
  m('arena: a decoy draws one of five actions', 'self._walk.integers(0, 5, size=n)', 'self._walk.integers(0, 4, size=n)', 'test_decoys_and_replays_walk_by_their_own_stream'),
  m('arena: edges clamp at the near wall', 'np.clip(np.array(rows), HALF, LIMIT)', 'np.clip(np.array(rows), 0, LIMIT)', FRAME),
  m('arena: edges clamp at the far wall', 'LIMIT = np.array([W, H]) - HALF', 'LIMIT = np.array([W, H])', FRAME),
  m('arena: the crossing aims at the current position', 'x = self.positions()[0 if bound is None else bound]', 'x = np.array(self.history[0][0 if bound is None else bound])', AIM),
  m('arena: blocked crossings aim at element 0', 'x = self.positions()[0 if bound is None else bound]', 'x = self.positions()[bound]', ARRIVAL),
  m('arena: arrival is no earlier than step 5', 'self._plan.integers(5, 16), self._plan.integers(2)', 'self._plan.integers(3, 16), self._plan.integers(2)', ARRIVAL),
  m('arena: arrival is no later than step 15', 'self._plan.integers(5, 16), self._plan.integers(2)', 'self._plan.integers(5, 20), self._plan.integers(2)', ARRIVAL),
  m('arena: the crossing uses both axes', 'self._plan.integers(5, 16), self._plan.integers(2)', 'self._plan.integers(5, 16), self._plan.integers(1)', ARRIVAL),
  m('arena: the arrival frame is the arrival step', 'steps = np.arange(1, BLOCK_STEPS + 1)[:, None]', 'steps = np.arange(0, BLOCK_STEPS)[:, None]', ARRIVAL),
  m('arena: the crossing runs toward the farther wall', 'STEP if x[axis] < W / 2 else -STEP', 'STEP', 'test_the_crossing_runs_toward_the_farther_wall_so_the_element_is_whole_again'),
  m('arena: each block restarts its plan', 'route: np.tile(parked, (BLOCK_STEPS, 1))}\n        self.j = 0\n', 'route: np.tile(parked, (BLOCK_STEPS, 1))}\n', AIM),
  m('arena: the crossing and the parked one keep their roles', 'cross, route = self._look', 'route, cross = self._look', HALFWAY),
  m('arena: the second look-alike sits on the route', 'parked = _halfway(x, np.array([g0 + g2, g1 + g3]) / 2)', 'parked = np.array([g0 + g2, g1 + g3]) / 2', HALFWAY),
  m('arena: the parked point is on the grid', 'return (x + g) // (2 * STEP) * STEP', 'return (x + g) / 2', HALFWAY),
  // render: the picture
  m('render: a later id is on top', 'for e in arena.scenario.elements:\n        frame', 'for e in reversed(arena.scenario.elements):\n        frame', PIXEL),
  m('render: x is the column', 'SHAPE_MASKS[e.shape](xs - cx, ys - cy)', 'SHAPE_MASKS[e.shape](xs - cy, ys - cx)', PIXEL),
  m('render: pixels are sampled at their centres', 'np.mgrid[0:H, 0:W] + 0.5', 'np.mgrid[0:H, 0:W]', MASKS),
  m('render: the square is 8 by 8', '"square": lambda dx, dy: (abs(dx) < HALF) & (abs(dy) < HALF),', '"square": lambda dx, dy: abs(dx) < HALF,', MASKS),
  m('render: the circle has radius ELEMENT_PX / 2', 'dx * dx + dy * dy < HALF * HALF', 'dx * dx + dy * dy < HALF', MASKS),
  m('render: the triangle fills its box', '(dy + HALF + 0.5) / 2', '(dy + HALF) / 2', MASKS),
];
// A feasible-type case stays reachable whatever the agent's own probe does, and a body remap shows in the steering.
module.exports.push(
  m('scenario: on a one-way axis the goal sits on the wall', 'g[axis], half[axis] = (W - HALF if sign > 0 else HALF), HALF', 'half[axis] = HALF', WALL),
  m('scenario: the live side\'s wall, not the dead side\'s', '(W - HALF if sign > 0 else HALF)', '(W - HALF if sign < 0 else HALF)', WALL),
  m('scenario: the one-way goal is the strip the clamp holds an element in', 'else HALF), HALF', 'else HALF), GOAL_PX / 2', WALL),
  m('scenario: a one-way axis must be the goal\'s', ' if ways <= {u})', ')', WALL),
  m('scenario: a body remap changes the action toward the goal', 'u for u in moved_apart if ways', 'u for u in UNITS if ways', TOWARD),
);
