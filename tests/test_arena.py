"""The arena: hand-built worlds where a number can be derived by hand, `make_scenario`'s own
scenarios where a property can. The maps and steps below are written out here, not imported, so a
wrong table in gate/arena.py shows.
"""

from collections.abc import Mapping, Sequence
from functools import cache

import numpy as np
import numpy.typing as npt
import pytest

from gate.arena import Arena, make_scenario, masks, render
from gate.constants import BLOCK_STEPS, ELEMENTS_MAX, MAX_LAG, W
from gate.types import Element, Scenario, Vec, from_json, to_json

Colour = tuple[int, int, int]
Pos = npt.NDArray[np.float64]

RED, GREEN = (200, 30, 30), (30, 200, 30)
CASES = ("feasible", "blocked", "remap_feasible", "remap_blocked", "body_remap", "body_blocked")
MOVES = ("up", "down", "left", "right")
IDENTITY: dict[str, Vec] = {
    "noop": (0.0, 0.0),
    "up": (0.0, -2.0),
    "down": (0.0, 2.0),
    "left": (-2.0, 0.0),
    "right": (2.0, 0.0),
}
MIRROR_X = {**IDENTITY, "left": (2.0, 0.0), "right": (-2.0, 0.0)}
MIRROR_Y = {**IDENTITY, "up": (0.0, 2.0), "down": (0.0, -2.0)}
ROTATE = {  # 90 degrees clockwise on screen: right goes down, down goes left, left up, up right
    "noop": (0.0, 0.0),
    "up": (2.0, 0.0),
    "down": (-2.0, 0.0),
    "left": (0.0, -2.0),
    "right": (0.0, 2.0),
}
DEAD = {a: {**IDENTITY, a: (0.0, 0.0)} for a in MOVES}
EIGHT_MAPS = {frozenset(m.items()) for m in (IDENTITY, MIRROR_X, MIRROR_Y, ROTATE, *DEAD.values())}
Binding = tuple[tuple[int, int | None], ...]
Maps = tuple[tuple[int, Mapping[str, Vec]], ...]


@cache
def scenarios(case: str = "") -> list[Scenario]:
    """Seeds 0..39 of one case, or of every case."""
    return [make_scenario(seed, c) for c in CASES if case in ("", c) for seed in range(40)]


def world(
    *elements: tuple[str, Colour, str, Vec],
    bound: Binding = ((0, 0),),
    maps: Maps = ((0, IDENTITY),),
    seed: int = 0,
    goal: tuple[float, float, float, float] = (100.0, 100.0, 116.0, 116.0),
) -> Scenario:
    """A hand-built scenario: (shape, colour, kind, position) per element, ids by order."""
    els = tuple(Element(i, *e) for i, e in enumerate(elements))
    return Scenario(seed, els, bound, maps, (), goal, "feasible")


def stacked(arena: Arena) -> Pos:
    """The arena's history as an array [T + 1, n, 2]."""
    return np.array([[frame[i] for i in sorted(frame)] for frame in arena.history])


def play(sc: Scenario, actions: Sequence[str], first_act: int = 0, block: int = 0) -> Pos:
    """Every element's position per frame, [T + 1, n, 2], after taking `actions` in order."""
    arena = Arena(sc)
    for t, action in enumerate(actions):
        if block and t % block == 0:
            arena.start_block()
        arena.step(action, t >= first_act)
    return stacked(arena)


def random_actions(seed: int, n: int) -> list[str]:
    return [str(a) for a in np.random.default_rng(seed).choice(("noop", *MOVES), n)]


def obeyed(sc: Scenario, steps: int, first_act: int = 0) -> npt.NDArray[np.bool_]:
    """[steps, n]: whether an element's step differs between four runs that press up, down, left
    or right throughout, that is, whether it obeyed the actions at that step."""
    moves = np.diff(np.stack([play(sc, [a] * steps, first_act) for a in MOVES]), axis=1)
    return np.asarray((moves != moves[:1]).any(axis=(0, 3)))


def visible_fractions(sc: Scenario, actions: Sequence[str], hider: int) -> tuple[list[float], Pos]:
    """Per frame of one block, the share of element 0's pixels not covered by `hider`'s."""
    arena = Arena(sc)
    arena.start_block()
    shown = []
    for action in [None, *actions]:
        if action is not None:
            arena.step(action, True)
        m = masks(arena)
        shown.append(float((m[0] & ~m[hider]).sum() / m[0].sum()))
    return shown, stacked(arena)


def trio(x: Vec, goal: tuple[float, float, float, float], seed: int = 0) -> Scenario:
    """A controlled square at x and two look-alikes of its colour, the shape of a planned block."""
    return world(
        ("square", RED, "controlled", x),
        ("circle", RED, "decoy", (100.0, 100.0)),
        ("triangle", RED, "decoy", (100.0, 20.0)),
        goal=goal,
        seed=seed,
    )


def test_the_controlled_element_moves_exactly_one_cell_on_right() -> None:
    arena = Arena(world(("square", RED, "controlled", (60.0, 60.0))))
    arena.step("right", True)
    arena.step("up", True)
    # hand: (60, 60) + one cell (CELL_PX = 2) in +x = (62, 60); `up` is -y: (62, 60) + (0, -2).
    # The history maps id to (x, y) per frame, and frame 0 exists before the first action
    assert arena.history == [{0: (60.0, 60.0)}, {0: (62.0, 60.0)}, {0: (62.0, 58.0)}]


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("body", [IDENTITY, MIRROR_X])
def test_an_echo_moves_by_the_action_lag_steps_ago(seed: int, body: Mapping[str, Vec]) -> None:
    sc = world(
        ("circle", RED, "controlled", (60.0, 60.0)),
        ("square", GREEN, "echo", (30.0, 30.0)),
        maps=((0, body),),
        seed=seed,
    )
    d = Arena(sc).lag[1]
    moves = np.diff(play(sc, ["right", "down", *["noop"] * MAX_LAG])[:, 1], axis=0)
    # hand: `right` at step 0 moves the echo by body["right"] at step d, `down` at step 1 by
    # body["down"] at step d + 1; every other step is a noop and moves nothing
    want = np.zeros_like(moves)
    want[d], want[d + 1] = body["right"], body["down"]
    assert 1 <= d <= MAX_LAG
    assert np.array_equal(moves, want)


def test_echo_lags_cover_one_to_max_lag() -> None:
    lags = {Arena(make_scenario(seed, "feasible")).lag[3] for seed in range(60)}
    assert lags == set(range(1, MAX_LAG + 1))  # hand: drawn from 1..MAX_LAG = {1, 2, 3, 4}


@pytest.mark.parametrize("target", [1, None])
def test_after_the_remap_step_the_old_element_ignores_actions(target: int | None) -> None:
    sc = world(
        ("square", RED, "controlled", (64.0, 64.0)),
        ("circle", GREEN, "decoy", (64.0, 80.0)),
        bound=((0, 0), (6, target)),
    )
    got = obeyed(sc, 12)
    # hand: element 0 obeys act steps 0..5; from step 6 control passes to element 1 (or to none)
    assert got[:, 0].tolist() == [True] * 6 + [False] * 6
    assert got[:, 1].tolist() == [False] * 6 + [target == 1] * 6


def test_a_remap_case_with_the_first_act_at_step_40_fires_after_step_40() -> None:
    for seed in range(5):
        sc = make_scenario(seed, "remap_feasible")
        fires = sc.binding_schedule[1][0]
        assert 5 <= fires <= BLOCK_STEPS - 5
        # hand: the schedule counts from the first act step (40), so element 5, the decoy that
        # takes over, first obeys at step 40 + fires, never during the 40 steps before
        assert np.flatnonzero(obeyed(sc, 70, first_act=40)[:, 5])[0] == 40 + fires


def test_a_mirrored_map_moves_left_on_right_and_a_dead_action_moves_nothing() -> None:
    one = ("square", RED, "controlled", (60.0, 60.0))
    mirrored = play(world(one, maps=((0, MIRROR_X),)), ["right"])
    dead = play(world(one, maps=((0, DEAD["left"]),)), ["left", "right"])
    assert mirrored[1, 0].tolist() == [58.0, 60.0]  # hand: 60 - one cell
    assert dead[:, 0].tolist() == [[60.0, 60.0], [60.0, 60.0], [62.0, 60.0]]


def test_after_the_body_remap_step_the_new_map_applies() -> None:
    sc = world(("square", RED, "controlled", (60.0, 60.0)), maps=((0, IDENTITY), (6, MIRROR_X)))
    # hand: `right` is +2 for act steps 0..5 (60 to 72) and -2 for steps 6 and 7 (72 to 68)
    assert play(sc, ["right"] * 8)[:, 0, 0].tolist() == [60, 62, 64, 66, 68, 70, 72, 70, 68]
    # first act at step 3: the remap is act step 6, global step 9: +2 nine times (78), then -2
    late = play(sc, ["right"] * 12, first_act=3)[:, 0, 0]
    assert late.tolist() == [60 + 2 * min(t, 9) - 2 * max(t - 9, 0) for t in range(13)]


def test_make_scenario_draws_exactly_the_eight_action_maps() -> None:
    seen = {frozenset(sc.action_maps[0][1].items()) for sc in scenarios()}
    assert seen == EIGHT_MAPS  # identity, two mirrors, a rotation, and each of four dead actions


def test_a_blocked_scenario_has_no_controlled_binding() -> None:
    for sc in scenarios("blocked"):
        assert [who for _, who in sc.binding_schedule] == [None]
        assert all(e.kind != "controlled" for e in sc.elements)
    for sc in (s for s in scenarios() if s.case != "blocked"):
        assert sc.binding_schedule[0] == (0, 0) and sc.elements[0].kind == "controlled"


def test_control_remap_cases_switch_at_the_secret_step_and_log_it() -> None:
    for sc in (s for s in scenarios() if s.case.startswith("remap_")):
        (step, who), (event_step, kind, detail) = sc.binding_schedule[1], sc.events[0]
        assert sc.binding_schedule[0] == (0, 0) and len(sc.events) == 1
        assert step == event_step and kind == "control_remap"
        assert (who, detail) == (
            (5, "0 -> 5") if sc.case == "remap_feasible" else (None, "0 -> None")
        )
        assert sc.elements[5].kind == "decoy"  # the new element was a decoy until then
        assert len(sc.action_maps) == 1


def test_body_remap_switches_the_map_at_the_secret_step_and_logs_it() -> None:
    for sc in scenarios("body_remap"):
        (first_step, first), (step, second) = sc.action_maps
        assert first_step == 0 and first != second
        assert sc.events == ((step, "body_remap", sc.events[0][2]),)
        assert sc.binding_schedule == ((0, 0),)


def test_cases_without_a_remap_log_nothing() -> None:
    for sc in (s for s in scenarios() if s.case in ("feasible", "blocked", "body_blocked")):
        assert sc.events == () and len(sc.action_maps) == 1 and len(sc.binding_schedule) == 1


def test_the_secret_step_covers_5_to_block_steps_minus_5() -> None:
    steps = {make_scenario(s, "remap_blocked").binding_schedule[1][0] for s in range(200)}
    assert steps == set(range(5, BLOCK_STEPS - 4))  # hand: 5..25 inclusive with BLOCK_STEPS = 30


def test_every_scenario_is_laid_out_without_overlap_inside_the_frame() -> None:
    for sc in scenarios():
        pts = np.array([e.pos for e in sc.elements])
        assert ELEMENTS_MAX - 2 <= len(pts) <= ELEMENTS_MAX
        assert [e.id for e in sc.elements] == list(range(len(pts)))
        assert pts.min() >= 4 and pts.max() <= W - 4 and (pts % 2 == 0).all()  # whole cells
        centre = np.array([sc.goal[0] + sc.goal[2], sc.goal[1] + sc.goal[3]]) / 2
        apart = [np.abs(a - b).max() for i, a in enumerate(pts) for b in pts[i + 1 :]]
        assert min(apart) >= 16  # hand: two 8 px elements and a gap of at least one element
        assert np.abs(pts - centre).max(axis=1).min() >= 16  # nothing starts in the goal


def test_every_scenario_has_two_look_alikes_and_an_echo_and_a_replay() -> None:
    for sc in scenarios():
        subject, *rest = sc.elements
        same = [e for e in rest if e.colour == subject.colour]
        assert [e.id for e in same] == [1, 2] and all(e.kind == "decoy" for e in same)
        assert {subject.shape, same[0].shape, same[1].shape} == {"circle", "square", "triangle"}
        assert [e.kind for e in rest[2:5]] == ["echo", "replay", "decoy"]  # ids 3, 4, 5
        assert len({e.colour for e in sc.elements}) == len(sc.elements) - 2


def test_the_goal_is_at_least_block_steps_cells_from_the_subject() -> None:
    for sc in scenarios():
        (x, y), (x0, y0, x1, y1) = sc.elements[0].pos, sc.goal
        # hand: cells from the subject to the nearest point of the goal rectangle, 2 px a cell
        cells = (max(x0 - x, 0, x - x1) + max(y0 - y, 0, y - y1)) / 2
        assert cells >= BLOCK_STEPS
        assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= W


def test_the_goal_lies_along_a_live_action_unless_the_body_is_blocked() -> None:
    for sc in scenarios():
        pos = np.array(sc.elements[0].pos)
        centre = np.array([sc.goal[0] + sc.goal[2], sc.goal[1] + sc.goal[3]]) / 2
        x0, y0, x1, y1 = sc.goal
        corners = [np.array(c) for c in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
        want = tuple(2.0 * np.sign(centre - pos))
        reach = [want in {tuple(v) for v in m.values()} for _, m in sc.action_maps]
        assert reach == [sc.case != "body_blocked"] * len(sc.action_maps)
        if sc.case == "body_blocked":
            (dead,) = [a for a, v in sc.action_maps[0][1].items() if a != "noop" and v == (0, 0)]
            # hand: every corner of the goal is on the dead action's side of the subject
            assert all(np.dot(IDENTITY[dead], c - pos) > 0 for c in corners)


def one_way(m: Mapping[str, Vec]) -> list[Vec]:
    """The live steps of a map whose opposite step is dead: the axis it leaves one-way."""
    live = {v for v in m.values() if v != (0.0, 0.0)}
    return [v for v in live if (-v[0], -v[1]) not in live]


def test_a_one_way_axis_is_the_goals_and_the_goal_sits_on_its_live_wall() -> None:
    # issue 21: the agent's own probe drifts an element the one way it can go; a goal in mid-frame
    # on that axis can be passed for good. The goal is the strip the clamp holds an element in, its
    # centre the clamp, so every position on the axis can still reach that centre.
    hand = make_scenario(0, "feasible")
    assert hand.action_maps[0][1]["up"] == (0.0, 0.0)  # hand: seed 0 draws `up` dead, so...
    assert hand.goal[1::2] == (120.0, 128.0)  # ...the goal is the bottom 8 px, centre 124 = 128 - 4
    for sc in scenarios():
        pos = np.array(sc.elements[0].pos)
        lo, hi = np.array(sc.goal[:2]), np.array(sc.goal[2:])
        way = np.sign((lo + hi) / 2 - pos)
        steps = [v for _, m in sc.action_maps for v in one_way(m)]
        for v in steps if sc.case != "body_blocked" else []:
            k = 0 if v[0] else 1
            strip = (W - 8.0, float(W)) if v[k] > 0 else (0.0, 8.0)  # hand: an 8 px element
            assert way[k] == np.sign(v[k]) and (lo[k], hi[k]) == strip


def toward_goal(sc: Scenario) -> list[list[str]]:
    """Per map of the body schedule, the actions that step the subject straight at the goal."""
    centre = np.array([sc.goal[0] + sc.goal[2], sc.goal[1] + sc.goal[3]]) / 2
    want = tuple(2.0 * np.sign(centre - np.array(sc.elements[0].pos)))
    return [[a for a, v in m.items() if v == want] for _, m in sc.action_maps]


def test_a_body_remap_changes_the_action_that_moves_toward_the_goal() -> None:
    # a remap that leaves this action alone never shows in the steering, so the diagnosis misses it
    hand = make_scenario(2, "body_remap")
    assert [m for _, m in hand.action_maps] == [IDENTITY, MIRROR_X]
    # hand: the goal (34, 60) is left of the subject (102, 60): `left` under identity, then `right`
    assert toward_goal(hand) == [["left"], ["right"]]
    for sc in scenarios("body_remap"):
        first, then = toward_goal(sc)
        assert first != then, sc.seed


def test_same_seed_same_scenario_and_same_world() -> None:
    assert make_scenario(7, "remap_feasible") == make_scenario(7, "remap_feasible")
    assert make_scenario(7, "feasible") != make_scenario(8, "feasible")
    acts = ["right", "up", "noop", "left"] * 8
    sc = make_scenario(7, "feasible")
    assert np.array_equal(play(sc, acts, block=BLOCK_STEPS), play(sc, acts, block=BLOCK_STEPS))


def test_every_case_survives_json_with_no_numpy_scalar_in_it() -> None:
    # the JSON writer refuses a numpy integer, and equality would hide a numpy float
    for case in CASES:
        sc = make_scenario(3, case)
        assert from_json(to_json(sc), Scenario) == sc


def test_a_forced_crossing_hides_the_element_underneath_then_it_reappears_whole() -> None:
    shown, h = visible_fractions(make_scenario(0, "feasible"), ["noop"] * BLOCK_STEPS, 1)
    # hand: the look-alike (id 1, on top) runs through element 0's still position at 2 px a frame,
    # so at the arrival frame and its two neighbours the centres are 0, 2 and 2 px apart. Counting
    # mask pixels (square 64, circle 52, triangle 40) for every ordered pair of shapes, the top
    # one covers over half of the other in at least 2 of those frames (3 for a square over a
    # circle, seed 0's pair); from 8 px apart they no longer touch
    low = [t for t, share in enumerate(shown) if share < 0.5]
    (arrival,) = np.flatnonzero((h[:, 1] == h[0, 0]).all(axis=1))
    assert len(low) >= 2 and arrival in low and 5 <= arrival <= 15
    assert shown[0] == 1.0 and shown[-1] == 1.0 and low[-1] < len(shown) - 1


def test_the_crossing_arrives_at_a_seeded_step_between_5_and_15_along_either_axis() -> None:
    arrivals, axes = set(), set()
    for case in ("feasible", "blocked"):  # blocked: through the fixed decoy, element 0
        for seed in range(100):
            h = play(make_scenario(seed, case), ["noop"] * BLOCK_STEPS, block=BLOCK_STEPS)
            (frame,) = np.flatnonzero((h[:, 1] == h[0, 0]).all(axis=1))
            arrivals.add(int(frame))
            axes.add(int(np.flatnonzero(h[frame + 1, 1] - h[frame, 1])[0]))
    assert arrivals == set(range(5, 16))  # hand: a seeded frame, 5..15 inclusive
    assert axes == {0, 1}  # it runs along x or along y


def test_each_block_aims_the_crossing_at_the_bound_elements_current_position() -> None:
    sc = trio((40.0, 64.0), (100.0, 56.0, 116.0, 72.0))
    h = play(sc, ["right"] * BLOCK_STEPS + ["noop"] * BLOCK_STEPS, block=BLOCK_STEPS)
    # hand: 30 steps of +2 take element 0 from x = 40 to 100; block 1's look-alike runs through
    # (100, 64), once, and never through the old (40, 64)
    hits = np.flatnonzero((h[30:, 1] == [100.0, 64.0]).all(axis=1))
    assert h[30, 0].tolist() == [100.0, 64.0] and len(hits) == 1 and 5 <= hits[0] <= 15
    assert not (h[30:, 1] == h[0, 0]).all(axis=1).any()


def test_the_crossing_runs_toward_the_farther_wall_so_the_element_is_whole_again() -> None:
    # hand: at x = 120 a run toward the near wall would stop at 124, 4 px from element 0, and keep
    # it half hidden for good; toward the far side it leaves, whatever axis the seed draws
    for seed in range(12):
        shown, _ = visible_fractions(
            trio((120.0, 64.0), (0.0, 0.0, 16.0, 16.0), seed), ["noop"] * BLOCK_STEPS, 1
        )
        assert shown[-1] == 1.0


def test_the_look_alike_on_the_goal_route_sits_halfway_on_the_grid() -> None:
    sc = trio((20.0, 64.0), (78.0, 56.0, 94.0, 72.0))
    h = play(sc, ["noop"] * 5, block=BLOCK_STEPS)
    # hand: goal centre (86, 64); halfway is (53, 64), rounded down to the 2 px grid: (52, 64)
    assert (h[1:, 2] == [52.0, 64.0]).all()


def test_the_parked_look_alike_does_not_move_in_the_first_block() -> None:
    for sc in (s for s in scenarios() if s.case in ("feasible", "blocked")):
        h = play(sc, ["noop"] * BLOCK_STEPS, block=BLOCK_STEPS)
        # make_scenario and start_block agree on it
        assert np.ptp(h[:, 2], axis=0).tolist() == [0.0, 0.0]


@pytest.mark.parametrize("seed", range(6))
def test_steering_to_the_goal_runs_into_the_look_alike_on_the_route(seed: int) -> None:
    sc = make_scenario(seed, "feasible")
    pos = np.array(sc.elements[0].pos)
    centre = np.array([sc.goal[0] + sc.goal[2], sc.goal[1] + sc.goal[3]]) / 2
    want = tuple(2.0 * np.sign(centre - pos))
    (steer,) = [a for a, v in sc.action_maps[0][1].items() if tuple(v) == want]
    shown, _ = visible_fractions(sc, [steer] * BLOCK_STEPS, 2)
    # hand: halfway is 34 px = 17 steps along the route, or at most 52 px = 26 steps when a one-way
    # axis puts the goal on a wall (the subject starts at least 20 px from the other wall, the
    # strip's centre is 4 px from this one: 104 px at most), so 30 steps pass it; at 2 px a step the
    # centres are 2, 0 and 2 px apart for three frames, and the one on top hides over half of the
    # other in at least 2 of them (the same count as the crossing, for every pair of shapes)
    assert sum(share < 0.5 for share in shown) >= 2


@pytest.mark.parametrize("case", CASES)
def test_look_alike_tracks_do_not_depend_on_the_actions(case: str) -> None:
    sc = make_scenario(0, case)
    runs = [play(sc, random_actions(k, BLOCK_STEPS), block=BLOCK_STEPS) for k in (1, 2)]
    takes_over = {5} if case == "remap_feasible" else set()  # obeys once the remap fires
    free = [e.id for e in sc.elements if e.kind in ("decoy", "replay") and e.id not in takes_over]
    assert np.array_equal(runs[0][:, free], runs[1][:, free])  # look-alikes, replay, decoys
    assert not np.array_equal(runs[0][:, 3], runs[1][:, 3])  # the echo does follow the actions
    if case != "blocked":
        assert not np.array_equal(runs[0][:, 0], runs[1][:, 0])  # and so does the controlled one


@pytest.mark.parametrize(("kind", "stream"), [("decoy", 5), ("replay", 6)])
def test_decoys_and_replays_walk_by_their_own_stream(kind: str, stream: int) -> None:
    # seed 5: a decoy draws from the scenario's seed, a replay from another one, seed + 1 = 6
    sc = world(
        ("circle", RED, "controlled", (64.0, 64.0)), ("square", GREEN, kind, (64.0, 64.0)), seed=5
    )
    draws = np.random.default_rng([stream, 1]).integers(0, 5, size=(30, 2))[:, 1]
    steps = np.array([IDENTITY[a] for a in ("noop", "up", "down", "left", "right")])
    # hand: one of five actions a step; from the centre 30 steps cannot reach a wall (64 - 60 = 4)
    want = 64 + np.cumsum(steps[draws], axis=0)
    assert np.array_equal(play(sc, ["noop"] * 30)[1:, 1], want)


def test_elements_never_leave_the_frame_and_stay_on_whole_cells() -> None:
    corner = world(("square", RED, "controlled", (4.0, 4.0)))
    far = world(("square", RED, "controlled", (124.0, 124.0)))
    # hand: a centre stops at ELEMENT_PX / 2 = 4 from the top-left and W - 4 = 124 at the far corner
    assert play(corner, ["left", "up", "right"])[:, 0].tolist() == [[4, 4], [4, 4], [4, 4], [6, 4]]
    assert play(far, ["right", "down", "left"])[:, 0].tolist() == [[124, 124]] * 3 + [[122, 124]]
    acts = random_actions(3, 300)
    for case in ("feasible", "remap_feasible"):
        h = play(make_scenario(1, case), acts, block=BLOCK_STEPS)
        assert h.min() >= 4 and h.max() <= 124 and (h % 2 == 0).all()


def test_mask_pixel_counts_and_bounding_boxes() -> None:
    sc = world(
        ("circle", RED, "decoy", (30.0, 30.0)),
        ("square", RED, "decoy", (60.0, 60.0)),
        ("triangle", RED, "decoy", (90.0, 90.0)),
    )
    shapes = masks(Arena(sc))
    # hand: a square is 8 x 8 = 64 px; the circle's 8 rows hold 4, 6, 8, 8, 8, 8, 6, 4 = 52; the
    # triangle's rows hold 2, 2, 4, 4, 6, 6, 8, 8 = 40 (apex up). Each spans the 8 px box around
    # its centre, so the box centre is the element's position
    assert [int(shapes[i].sum()) for i in range(3)] == [52, 64, 40]
    for i, c in enumerate((30, 60, 90)):
        assert np.flatnonzero(shapes[i].any(axis=0))[[0, -1]].tolist() == [c - 4, c + 3]
        assert np.flatnonzero(shapes[i].any(axis=1))[[0, -1]].tolist() == [c - 4, c + 3]


def test_render_puts_the_expected_colour_at_a_known_pixel() -> None:
    frame = render(
        Arena(
            world(("square", RED, "decoy", (20.0, 30.0)), ("square", GREEN, "decoy", (22.0, 30.0)))
        )
    )
    # hand: element 0 covers columns 16..23 and rows 26..33, element 1 columns 18..25, same rows;
    # a pixel is [row, column]; the later id is drawn on top where they overlap
    assert frame.shape == (128, 128, 3) and frame.dtype == np.uint8
    assert frame[30, 17].tolist() == list(RED)  # only element 0
    assert frame[30, 20].tolist() == list(GREEN)  # both, element 1 on top
    assert frame[30, 25].tolist() == list(GREEN)  # only element 1
    assert frame[30, 26].tolist() == [0, 0, 0] and frame[20, 30].tolist() == [0, 0, 0]
    assert frame[0, 0].tolist() == [0, 0, 0]
