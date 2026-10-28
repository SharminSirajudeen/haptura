"""T8 on T2's synthetic clip: a red circle and a red square cross with a 2-frame occlusion."""

import math
from pathlib import Path
from typing import cast

import numpy as np

from gate.trackers import colour_tracker, match_ids, truth_tracker
from gate.types import Frames

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
