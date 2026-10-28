"""T8 on T2's synthetic clip: a red circle and a red square cross with a 2-frame occlusion."""

import math
from pathlib import Path
from typing import cast

import numpy as np

from gate.arena import Arena, make_scenario, render
from gate.constants import JUMP_TOL
from gate.gate import diagnose
from gate.trackers import colour_tracker, match_ids, truth_tracker
from gate.types import Frames, Tracks

FIXTURES = Path(__file__).parent / "fixtures"


def arena_frames() -> Frames:
    return cast(Frames, np.load(FIXTURES / "arena128_frames.npz")["frames"])


def test_colour_tracker_finds_the_three_elements_with_hand_derived_centres() -> None:
    tracks = colour_tracker(arena_frames())
    # frame 0: circle centre drawn at (20, 64), radius 4; square x 104..111, y 60..67 -> (107.5,
    # 63.5);
    # triangle rows 16..24 hold 1,1,3,3,5,5,7,7,9 pixels (41): sum y*count = 880, 880/41 = 21.46;
    # x = 100
    at0 = sorted(tuple(np.round(t[0], 1)) for t in tracks.values() if not np.isnan(t[0, 0]))
    assert at0 == [(20.0, 64.0), (100.0, 21.5), (107.5, 63.5)]
    assert len(tracks) == 3


def test_colour_tracker_swaps_the_two_red_ids_at_the_crossing() -> None:
    tracks = colour_tracker(arena_frames())
    red = [t for t in tracks.values() if not np.isnan(t[0, 0]) and abs(t[0, 1] - 64) < 1]
    circle = next(
        t for t in red if t[0, 0] < 60
    )  # followed the circle, which moves right, before the crossing
    assert circle[5, 0] > circle[0, 0]
    # after the crossing (frames 14-15 merge the blobs) the same id follows the square, moving left
    assert circle[29, 0] < circle[18, 0] < 64
    assert np.isnan(circle[14, 0])  # one blob for two elements: one id is absent there


def test_colour_tracker_associates_from_the_latest_position_not_the_first() -> None:
    # Two red squares walk right 3 px per frame, A along y=20 from x=10 and B along y=40 from x=70.
    # At frame 20 A's blob (70, 20) is 20 px from B's frame-0 position and 60 px from A's own, so
    # association from first positions hands it to B's id; from latest positions it is 3 px from A.
    frames = np.zeros((30, 64, 256, 3), np.uint8)
    for t in range(30):
        for x, y in ((10 + 3 * t, 20), (70 + 3 * t, 40)):
            frames[t, y - 4 : y + 4, x - 4 : x + 4] = (220, 40, 40)
    tracks = colour_tracker(frames)
    assert len(tracks) == 2
    for track in tracks.values():
        assert np.all(np.diff(track[:, 0]) == 3.0)
        assert np.all(track[:, 1] == track[0, 1])


def test_match_ids_links_by_nearest_first_position_and_mints_fresh_ids() -> None:
    tracks = {
        7: np.array([[math.nan, math.nan], [10.0, 10.0], [52.0, 50.0]]),  # first visible at frame 1
        8: np.array([[50.0, 50.0], [30.0, 30.0], [10.0, 10.0]]),  # the two tracks trade places
        9: np.array([[90.0, 90.0], [90.0, 90.0], [90.0, 90.0]]),  # nothing near it
        4: np.array([[120.0, 5.0], [120.0, 5.0], [120.0, 5.0]]),  # nothing near it either
    }
    reference = {3: (11.0, 9.0), 5: (52.0, 50.0)}
    # by first visible positions 7 -> 3 (distance 1.4) and 8 -> 5 (2.0); by last positions it
    # would be
    # the other way round; 9 and 4 match nothing and get the fresh ids 6 and 7
    assert match_ids(tracks, reference) == {7: 3, 8: 5, 9: 6, 4: 7}


def test_match_ids_is_greedy_on_the_closest_pair_first() -> None:
    tracks = {1: np.array([[0.0, 0.0]]), 2: np.array([[3.0, 0.0]])}
    reference = {10: (2.0, 0.0), 11: (6.0, 0.0)}
    # closest pair is (2 -> 10) at distance 1; then 1 takes 11 (distance 6) rather than the taken 10
    assert match_ids(tracks, reference) == {2: 10, 1: 11}


def test_truth_tracker_keeps_absent_frames_nan() -> None:
    history = [{1: (5.0, 5.0), 2: (9.0, 9.0)}, {1: (7.0, 5.0)}]
    tracks = truth_tracker(history)
    assert tuple(tracks[1][1]) == (7.0, 5.0)
    assert tuple(tracks[2][0]) == (9.0, 9.0)
    assert np.isnan(tracks[2][1]).all()


def _steered_block(seed: int) -> tuple[dict[str, tuple[float, float]], list[str], Tracks, Tracks]:
    """One act block on a feasible identity-map scenario, steering the subject straight at the
    goal.
    """
    scenario = make_scenario(seed, "feasible")
    body = dict(scenario.action_maps[0][1])
    arena = Arena(scenario)
    arena.start_block()
    frames, actions = [render(arena)], []
    gx = (scenario.goal[0] + scenario.goal[2]) / 2
    gy = (scenario.goal[1] + scenario.goal[3]) / 2
    for _ in range(30):
        x, y = arena.positions()[0]
        horizontal = abs(gx - x) >= abs(gy - y)
        act = ("right" if gx > x else "left") if horizontal else ("down" if gy > y else "up")
        actions.append(act)
        arena.step(act, True)
        frames.append(render(arena))
    return body, actions, colour_tracker(np.array(frames)), truth_tracker(arena.history)


def _subject_id(tracks: Tracks, truth: Tracks) -> int:
    start = truth[0][0]
    return min(
        tracks, key=lambda i: float(np.nan_to_num(np.hypot(*(tracks[i][0] - start)), nan=1e9))
    )


def test_at_a_forced_crossing_the_colour_tracker_swaps_and_s14_catches_it() -> None:
    # seed 34: measured 28 Oct, the subject's colour id drifts 26.5 px off its true path after the
    # crossing
    body, actions, tracks, truth = _steered_block(34)
    cid = _subject_id(tracks, truth)
    assert np.nanmax(np.hypot(*(tracks[cid] - truth[0]).T)) > 2 * JUMP_TOL
    d = diagnose(body, actions, tracks, cid)
    assert d.kind == "eyes_swapped"
    assert d.swap is not None and d.swap[0] == cid


def test_where_the_colour_tracker_holds_s14_reports_no_swap() -> None:
    # seed 5, an identity map: measured 28 Oct, the colour id stays on the subject through the
    # block (0.7 px). Seed 0 was the witness until #21 moved its goal: it draws `up` dead.
    body, actions, tracks, truth = _steered_block(5)
    cid = _subject_id(tracks, truth)
    assert np.nanmax(np.hypot(*(tracks[cid] - truth[0]).T)) <= JUMP_TOL
    assert diagnose(body, actions, tracks, cid).kind == "ok"
