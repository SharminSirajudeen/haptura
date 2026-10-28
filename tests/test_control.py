"""S10 and S12 on synthesised tracks: no arena, every expected value derived by hand in a comment.

Tracks are (x, y) pixels, origin top-left, `up` is -y, one step is CELL_PX (plan §3). Frame 0 is
before the first action and frame t+1 follows action t.
"""

from collections import Counter
from collections.abc import Mapping, Sequence

import numpy as np
import pytest

from gate import constants as c
from gate.control import control_scores, design_block
from gate.types import Array, Evidence, Vec

DIRS = ("up", "down", "left", "right")
STEP = float(c.CELL_PX)
STILL = (0.0, 0.0)
BODY = {"up": (0.0, -STEP), "down": (0.0, STEP), "left": (-STEP, 0.0), "right": (STEP, 0.0)}
FLOOR = 1 / (c.PERMS + 1)  # the smallest p a permutation test reports: no shuffle reaches S
CENTRE = (c.W / 2, c.H / 2)  # 30 balanced steps of CELL_PX cannot reach a wall from here
NOISE = 1.5 * STEP  # the step noise of the follower whose two blocks are pooled


def design(seed: int) -> tuple[str, ...]:
    return design_block(np.random.default_rng(seed), c.BLOCK_STEPS, c.P_NOOP, DIRS)


def walk(
    actions: Sequence[str],
    body: Mapping[str, Vec] = BODY,
    start: Vec = CENTRE,
    lag: int = 0,
    noise: float = 0.0,
    seed: int = 0,
    drift: Vec = STILL,
) -> Array:
    """Frame t+1 = frame t + body[a_{t-lag}] + drift + noise; no-ops and steps before a_0 drift."""
    rng = np.random.default_rng(seed)
    steps = [body.get(actions[t - lag], STILL) if t >= lag else STILL for t in range(len(actions))]
    d = np.array(steps) + np.array(drift) + rng.normal(0.0, noise, (len(actions), 2))
    track: Array = np.vstack([np.zeros((1, 2)), np.cumsum(d, axis=0)]) + np.array(start)
    return track


def score(actions: Sequence[str], track: Array, seed: int = 0) -> Evidence:
    return control_scores(actions, {1: track}, c.MAX_LAG, seed)[0]


def test_pure_echo_at_lag_2_is_echo_with_best_lag_2() -> None:
    # d_t = body[a_{t-2}]: grouping d_{t+2} by a_t gives pure groups, the largest S_2 any labelling
    # reaches, so no shuffle ties it and p_2 = FLOOR. a_t is drawn independently of a_{t-2}, so p_0
    # is not below ALPHA_ACT, and lags 1, 3 and 4 pair a_t with another independent action.
    acts = design(0)
    ev = score(acts, walk(acts, lag=2))
    assert (ev.label, ev.best_lag, ev.p_best) == ("echo", 2, FLOOR)
    assert ev.p0 > c.ALPHA_ACT


def test_independent_random_walk_is_not_me() -> None:
    # Steps of sd 3 CELL_PX drawn without reading the actions: p_0 is a draw from near-uniform, and
    # the group means differ by about 3 CELL_PX / sqrt(6) > EFFECT_MIN by chance alone, so only the
    # p rule keeps this object from `mine`.
    acts = design(0)
    ev = score(acts, walk(acts, body={}, noise=3 * STEP, seed=1))
    assert ev.label == "not_me"
    assert ev.p0 > 0.05
    assert ev.effect >= c.EFFECT_MIN


def test_perfect_follower_is_mine_at_the_floor_on_20_designs() -> None:
    # Pure groups: the within-group spread is zero, so S_0 is the maximum over labellings and only
    # a relabelling that swaps whole groups of equal size ties it (about 1 in 1e16 shuffles of 30
    # steps). Count 0, p = (1 + 0) / (PERMS + 1). The body is the exact map, so effect = CELL_PX.
    for seed in range(20):
        acts = design(seed)
        ev = score(acts, walk(acts), seed)
        assert (ev.p0, ev.label, ev.effect) == (FLOOR, "mine", STEP), seed
        assert ev.body == BODY, seed


def test_mirrored_follower_on_a_drift_is_mine_and_a_dead_action_has_no_effect() -> None:
    # `right` moves the element left, `down` moves nothing, and the whole scene drifts +1 px in y
    # per step, no-ops included. e_{a,0} = m_{a,0} - m_{noop,0} removes the drift: e_right =
    # (-CELL_PX, 0), e_down = (0, 0), so ‖e_down‖ = 0 < EFFECT_MIN and effect = CELL_PX. The groups
    # are still pure, so p_0 = FLOOR.
    mirrored = {"up": BODY["up"], "down": STILL, "left": BODY["right"], "right": BODY["left"]}
    acts = design(0)
    ev = score(acts, walk(acts, body=mirrored, drift=(0.0, 1.0)))
    assert (ev.label, ev.p0) == ("mine", FLOOR)
    assert ev.body["right"] == pytest.approx((-STEP, 0.0))
    dead = ev.body["down"]
    assert dead is not None and np.hypot(*dead) < c.EFFECT_MIN
    assert ev.effect == pytest.approx(STEP)


def test_a_follower_below_effect_min_is_not_mine() -> None:
    # The map is BODY at a quarter cell: pure groups, so p_0 = FLOOR, but effect = CELL_PX / 4 <
    # EFFECT_MIN refuses `mine`; no lag >= 1 is significant, so it is not `echo` either.
    acts = design(0)
    ev = score(acts, walk(acts, body={a: (v[0] / 4, v[1] / 4) for a, v in BODY.items()}))
    assert (ev.p0, ev.label) == (FLOOR, "not_me")
    assert ev.effect == pytest.approx(STEP / 4)


def test_nan_gaps_are_dropped_not_zero_filled() -> None:
    # Frames 4 and 5 are lost, so steps 3, 4, 5 (`left`, `noop`, `down`) are dropped and the 17
    # remaining steps are still pure groups: p_0 = FLOOR and the body is exact. Zero-filling the
    # frames would put a jump of about -CENTRE into `left` and +CENTRE into `down`; keeping the NaN
    # steps would make both means NaN.
    acts = (
        *("right", "noop", "up", "left", "noop", "down", "right", "up", "noop", "left"),
        *("down", "noop", "right", "up", "left", "noop", "down", "right", "noop", "up"),
    )
    track = walk(acts)
    track[4:6] = np.nan
    ev = score(acts, track)
    assert (ev.p0, ev.label) == (FLOOR, "mine")
    assert ev.body == BODY


def test_steps_at_a_wall_are_dropped_on_either_axis_and_either_frame() -> None:
    # Two followers read by a tracker that puts a centroid clamped at a wall 1 px inside the arena's
    # ELEMENT_PX/2 (the +1 of the margin). A sits at the left wall (x 5 for a true 4), B at the
    # bottom wall (y 123 for a true 124). A step is dropped when either frame touches: for A that
    # leaves steps 2 (right, 6->8), 3 (left, 8->6) and 4 (noop); for B steps 7 (up, 122->120), 8
    # (down, 120->122), 9 and 12 (noop). Both bodies are then exact, and A never leaves its wall on
    # `up` or `down`, so those have no sample. Kept wrongly, A's step 1 (5->6, from the wall) would
    # make right (1.5, 0) and its step 5 (6->5, into the wall) left (-1.5, 0); B's steps 10, 13, 14
    # (down at the wall: +1, +1, 0) would make down (0, 1).
    acts = (
        *("left", "right", "right", "left", "noop", "left", "up", "up", "down", "noop"),
        *("down", "up", "noop", "down", "down"),
    )
    ax = [5, 5, 6, 8, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    ay = [64, 64, 64, 64, 64, 64, 64, 62, 60, 62, 62, 64, 62, 62, 64, 66]
    bx = [64, 62, 64, 66, 64, 64, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62]
    by = [123, 123, 123, 123, 123, 123, 123, 122, 120, 122, 122, 123, 122, 122, 123, 123]
    a, b = np.array([ax, ay], float).T, np.array([bx, by], float).T
    ev_a, ev_b = control_scores(acts, {1: a, 2: b}, c.MAX_LAG, 0)
    assert ev_a.body == {"right": (2.0, 0.0), "left": (-2.0, 0.0), "up": None, "down": None}
    assert ev_b.body == {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": None, "right": None}


def test_pooling_two_blocks_gives_a_noisy_follower_a_smaller_p() -> None:
    # One follower with step noise of sd NOISE, seen in two 30-step blocks. Alone, each block
    # separates the group means by CELL_PX against a standard error of NOISE / sqrt(n_a); pooled,
    # every n_a doubles, the standard error falls by sqrt(2), and the permutation p falls with it.
    acts1, acts2 = design(0), design(1)
    t1 = walk(acts1, noise=NOISE, seed=10)
    t2 = walk(acts2, start=(float(t1[-1, 0]), float(t1[-1, 1])), noise=NOISE, seed=11)
    p1, p2 = score(acts1, t1).p0, score(acts2, t2).p0
    pooled = score(acts1 + acts2, np.vstack([t1, t2[1:]])).p0
    assert FLOOR < min(p1, p2), (p1, p2)
    assert pooled < min(p1, p2), (p1, p2, pooled)


def test_no_evidence_gives_p_one_at_every_lag_and_the_smaller_lag_on_a_tie() -> None:
    # A still object: every group mean equals the grand mean, so S = 0 in the observed row and in
    # every shuffle; all PERMS shuffles tie and p = (1 + PERMS) / (PERMS + 1) = 1 at every lag. An
    # object parked in the corner has every step dropped and the same zero S. Lags 1..4 tie at 1,
    # so best_lag is the smaller, 1. The still body is (0, 0) per action; the parked one has none.
    acts = design(0)
    still = np.tile(CENTRE, (len(acts) + 1, 1))
    parked = np.tile((5.0, 5.0), (len(acts) + 1, 1))
    ev_still, ev_parked = control_scores(acts, {3: still, 9: parked}, c.MAX_LAG, 0)
    assert [ev_still.object_id, ev_parked.object_id] == [3, 9]
    for ev in (ev_still, ev_parked):
        assert (ev.p0, ev.best_lag, ev.p_best, ev.effect, ev.label) == (1.0, 1, 1.0, 0.0, "not_me")
    assert ev_still.body == {a: STILL for a in DIRS}
    assert ev_parked.body == {a: None for a in DIRS}


def test_design_block_has_the_noop_rate_the_floor_and_balanced_directions() -> None:
    # n = 15, p_noop = 0.2: round(3.0) = 3 no-ops and 12 moves over 4 directions, 3 each (the S14
    # probe). n = 30, p_noop = 0.3: 9 no-ops and 21 moves, 6 + 5 + 5 + 5. n = 25, p_noop = 0.3: 7.5
    # rounds to 8, within 1 of p_noop * n. n = 10, p_noop = 0.1 would give 1 no-op; the floor is 2.
    probe = Counter(design_block(np.random.default_rng(0), 15, 0.2, DIRS))
    assert probe == {a: 3 for a in (*DIRS, "noop")}
    block = Counter(design(0))
    assert (block["noop"], block.total()) == (9, 30)
    assert sorted(block[a] for a in DIRS) == [5, 5, 5, 6]
    assert abs(Counter(design_block(np.random.default_rng(0), 25, 0.3, DIRS))["noop"] - 7.5) <= 1
    assert Counter(design_block(np.random.default_rng(0), 10, 0.1, DIRS))["noop"] == 2


def test_design_block_order_comes_from_the_rng() -> None:
    # The same seed gives the same block, different seeds different orders, and the 9 no-ops are
    # not all in the first 9 places (1 in C(30, 9) ≈ 1.4e7 for a shuffled block).
    assert design(3) == design(3)
    assert design(0) != design(1)
    assert "noop" in design(0)[9:]
