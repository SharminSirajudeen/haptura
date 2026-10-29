"""`check_act`, `diagnose` and `rule_policy` on hand-written Evidence and tracks. Each expected
value is derived by hand.

Constants used: ALPHA_ACT = 0.01 / 48 = 2.083e-4, ALPHA_PROBE = 0.2, EFFECT_MIN = 0.5 * 2 = 1.0,
STALE_TOL = 1.5 * 2 = 3.0, JUMP_TOL = 2.5 * 2 = 5.0; the walls hold an element's centre in
[HALF, 128 - HALF] = [4, 124] on each axis.
"""

import math
from collections.abc import Mapping, Sequence

import numpy as np

from gate.constants import ALPHA_ACT, ALPHA_PROBE, EFFECT_MIN, PROBE_STEPS
from gate.control import design_block
from gate.gate import check_act, diagnose, rule_policy
from gate.types import Array, Evidence, Tracks, Vec

Body = Mapping[str, Vec | None]
FULL: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (2.0, 0.0)}
P_FLOOR = 1e-4  # a mine element sits at the permutation floor 1 / (PERMS + 1), below ALPHA_ACT


def ev(object_id: int, label: str, p0: float = 0.5, body: Body = FULL) -> Evidence:
    """`check_act` and the rule policy read object_id, p0, body and label; the lag fields are
    filler."""
    return Evidence(object_id, p0, 1, p0, 2.0, body, label)


MINE = ev(3, "mine", P_FLOOR)
OTHER = ev(5, "not_me")
# target at (10, 50); goal box (60, 40)-(80, 60) has centre (70, 50): x needs +60, y needs 0
TARGET: Vec = (10.0, 50.0)
GOAL = (60.0, 40.0, 80.0, 60.0)
BUDGET = 6


def test_acts_on_the_single_mine() -> None:
    d = check_act([MINE, OTHER], 3)
    assert d.kind == "act" and d.object_id == 3


def test_refuses_when_two_are_mine() -> None:
    d = check_act([MINE, ev(5, "mine", P_FLOOR)], 3)
    assert d.kind == "refused" and "2 elements" in d.reason


def test_refuses_when_the_object_is_not_the_mine_one() -> None:
    d = check_act([MINE, OTHER], 5)
    assert d.kind == "refused" and d.object_id == 5 and "object 5 is not mine" in d.reason


def test_refuses_at_p_just_above_alpha_act_since_the_label_says_not_me() -> None:
    # p0 = 2.2e-4 sits just above ALPHA_ACT = 2.083e-4, so the control test labelled the element
    # not_me and nothing is mine. `check_act` reads the label, never p, so even this near miss is
    # refused.
    p0 = 2.2e-4
    assert ALPHA_ACT < p0 < ALPHA_PROBE
    d = check_act([ev(3, "not_me", p0)], 3)
    assert d.kind == "refused" and "0 elements" in d.reason


def test_acts_on_the_single_mine_when_the_goal_is_reachable() -> None:
    # Mirrored body: "left" moves +1.0 px in x, exactly EFFECT_MIN, and at least counts, so x
    # (needing +60) is reached through "left". y = 50 is inside the goal's band 40..60, so the
    # unsampled up and down do not matter. The act rule comes first: a spent budget (6 of 6)
    # does not stop it.
    body: Body = {"up": None, "down": None, "left": (EFFECT_MIN, 0.0), "right": (-2.0, 0.0)}
    d = rule_policy([ev(3, "mine", P_FLOOR, body), OTHER], BUDGET, BUDGET, TARGET, GOAL)
    assert d.kind == "act" and d.object_id == 3


def test_declines_citing_the_body_when_no_live_action_moves_toward_the_goal() -> None:
    # Goal box (60, 10)-(80, 30) has centre (70, 20): x needs +60, y needs -30. "up" (0, -2)
    # covers y. "right" has no samples and "left" moves -2 in x, so nothing moves +x: decline,
    # naming the axis.
    body: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": (-2.0, 0.0), "right": None}
    d = rule_policy([ev(3, "mine", P_FLOOR, body)], 1, BUDGET, TARGET, (60.0, 10.0, 80.0, 30.0))
    assert d.kind == "decline" and d.object_id == 3 and "along x" in d.reason


def test_an_axis_inside_the_goals_band_needs_nothing_though_off_its_centre() -> None:
    # A tracker reads an element held at the right wall at x = 123.5, inside the goal's x band
    # 120..128 but 0.5 px short of its centre 124. Pushing right into the wall does
    # nothing, so "right" is dead; only y (60 -> centre 40) needs a move, and "up" makes it.
    body: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (0.0, 0.0)}
    d = rule_policy(
        [ev(3, "mine", P_FLOOR, body)], 1, BUDGET, (123.5, 60.0), (120.0, 32.0, 128.0, 48.0)
    )
    assert d.kind == "act" and d.object_id == 3


def test_a_component_of_the_right_sign_below_effect_min_does_not_count() -> None:
    # "right" moves +0.6 px in x: the right sign but below EFFECT_MIN = 1.0, so it is dead and x
    # (needing +60) stays unreachable.
    body: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (0.6, 0.0)}
    d = rule_policy([ev(3, "mine", P_FLOOR, body)], 1, BUDGET, TARGET, GOAL)
    assert d.kind == "decline" and d.object_id == 3


def test_two_mine_is_not_a_single_mine_so_the_policy_probes() -> None:
    # Two elements labelled mine is not a single mine; 1 of 6 looks used: probe.
    d = rule_policy([MINE, ev(5, "mine", P_FLOOR)], 1, BUDGET, TARGET, GOAL)
    assert d.kind == "probe" and d.object_id is None


def test_probes_within_budget_while_some_p0_is_at_or_below_alpha_probe() -> None:
    # 3 of 6 looks used, enough for the early rule, but p0 = 0.2 is not above ALPHA_PROBE = 0.2,
    # so not every element is above it: probe.
    d = rule_policy([OTHER, ev(7, "not_me", ALPHA_PROBE)], 3, BUDGET, TARGET, GOAL)
    assert d.kind == "probe" and d.object_id is None


def test_declines_when_the_budget_is_spent() -> None:
    # 6 of 6 looks used and nothing is mine: decline. p0 = 0.05 is below ALPHA_PROBE, so the
    # budget rule is the one that fires.
    d = rule_policy([ev(3, "not_me", 0.05)], BUDGET, BUDGET, TARGET, GOAL)
    assert d.kind == "decline" and d.object_id is None and "6 looks" in d.reason


def test_declines_early_after_three_looks_when_every_p0_is_above_alpha_probe() -> None:
    # 3 of 6 looks used; p0 of 0.5 and 0.3 are both above ALPHA_PROBE = 0.2: decline early.
    d = rule_policy([OTHER, ev(7, "not_me", 0.3)], 3, BUDGET, TARGET, GOAL)
    assert d.kind == "decline" and d.object_id is None and "p0" in d.reason


def test_does_not_decline_early_after_two_looks() -> None:
    # The same evidence after 2 looks: 2 < 3, so the early rule waits and the policy probes.
    d = rule_policy([OTHER, ev(7, "not_me", 0.3)], 2, BUDGET, TARGET, GOAL)
    assert d.kind == "probe"


# The diagnosis. Tracks are (x, y) per frame; frame t+1 follows action t.
NAN = (math.nan, math.nan)
FAR = (90.0, 90.0)  # a decoy nowhere near the target
DIRS = ("up", "down", "left", "right")
MIRROR: Body = {"up": (0.0, 2.0), "down": (0.0, -2.0), "left": (2.0, 0.0), "right": (-2.0, 0.0)}


def track(*points: Vec) -> Array:
    return np.array(points, dtype=np.float64)


def follow(actions: Sequence[str], body: Body, start: Vec) -> Array:
    """The positions of an element that moves body[a] on each action and stays put otherwise."""
    steps = [body.get(a) or (0.0, 0.0) for a in actions]
    out: Array = np.vstack([start, np.array(start) + np.cumsum(steps, axis=0)])
    return out


# A dead steering action used twice: "right" no longer moves the target, "left" was never sampled.
STALE_BODY: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": None, "right": (2.0, 0.0)}
STALE_ACTIONS = ("right", "up", "right", "up", "left")
STALE_TRACKS: Tracks = {
    1: track((40, 64), (40, 64), (40, 62), (40, 62), (40, 60), (40, 60)),
    2: track(FAR, FAR, FAR, FAR, FAR, FAR),
}


def test_stale_when_a_dead_steering_action_was_used_twice() -> None:
    # Prediction from frame 0: right + up + right + up + left (None, so no motion) = (+4, -4),
    # so (44, 60). The target ends at (40, 60): summed residual 4 = 2 * CELL_PX > STALE_TOL = 3.
    # Every one-step span misses by at most 2 px, under JUMP_TOL: no swap.
    d = diagnose(STALE_BODY, STALE_ACTIONS, STALE_TRACKS, 1)
    assert d.kind == "stale" and "4.0 px" in d.fix and d.swap is None and d.body is None


def test_ok_with_one_px_jitter_on_every_frame() -> None:
    # True x = 40 + 2t for t = 0..7; the tracker adds +1 px on even frames. Prediction from frame 0
    # is 41 + 7 * 2 = 55; the last frame reads 54: summed residual 1 px <= STALE_TOL.
    xs = (41, 42, 45, 46, 49, 50, 53, 54)
    d = diagnose(FULL, ("right",) * 7, {1: track(*((x, 64) for x in xs))}, 1)
    assert d.kind == "ok" and "1.0 px" in d.fix


def test_a_jump_with_no_look_alike_near_is_stale_not_a_swap() -> None:
    # The last step lands at x = 56 against a prediction of 48: 8 px > JUMP_TOL, but the only other
    # track is at (90, 90), far from (48, 64), so it is no swap; the summed residual 8 > 3 is stale.
    tracks: Tracks = {
        1: track((40, 64), (42, 64), (44, 64), (46, 64), (56, 64)),
        2: track(FAR, FAR, FAR, FAR, FAR),
    }
    assert diagnose(FULL, ("right",) * 4, tracks, 1).kind == "stale"


def test_an_eyes_swap_across_a_3_frame_occlusion_is_caught_at_the_reappearance_frame() -> None:
    # Both ids vanish on frames 3-5. Span 2 -> 6 predicts (44 + 4 * 2, 64) = (52, 64). Id 1 comes
    # back at the look-alike's (60, 70), hypot(8, 6) = 10 px off; id 2 comes back at (52, 64), on
    # the prediction: swapped at frame 6.
    tracks: Tracks = {
        1: track((40, 64), (42, 64), (44, 64), NAN, NAN, NAN, (60, 70), (60, 70), (60, 70)),
        2: track((60, 70), (60, 70), (60, 70), NAN, NAN, NAN, (52, 64), (54, 64), (56, 64)),
    }
    d = diagnose(FULL, ("right",) * 8, tracks, 1)
    assert d.kind == "eyes_swapped" and d.swap == (1, 2) and "frame 6" in d.fix


def test_crossing_a_look_alike_without_a_swap_is_not_flagged() -> None:
    # Id 1 passes over the look-alike at (50, 64); both vanish on frames 4-6. Span 3 -> 7 predicts
    # (46 + 8, 64) = (54, 64): id 1 is on it (0 px) while the look-alike sits 4 px away, within
    # JUMP_TOL. The target did not miss its prediction, so no swap; the summed residual is 0.
    tracks: Tracks = {
        1: track((40, 64), (42, 64), (44, 64), (46, 64), NAN, NAN, NAN, (54, 64), (56, 64)),
        2: track(*([(50, 64)] * 4 + [NAN] * 3 + [(50, 64)] * 2)),
    }
    assert diagnose(FULL, ("right",) * 8, tracks, 1).kind == "ok"


def test_ok_when_the_target_pushes_into_a_wall() -> None:
    # The walls hold every predicted step as they hold the element: three "left" from x = 4 stay
    # at 4, and three "down" from y = 124 stay at 124: residual 0 both times. Unheld, they would
    # predict x = -2 and y = 130: 6 px > STALE_TOL = 3, stale.
    assert diagnose(FULL, ("left",) * 3, {1: track(*[(4, 64)] * 4)}, 1).kind == "ok"
    assert diagnose(FULL, ("down",) * 3, {1: track(*[(64, 124)] * 4)}, 1).kind == "ok"


def test_ok_when_the_target_slides_along_a_wall() -> None:
    # x = 4 is at the left wall on every frame; each "up" still predicts y - 2, so (4, 64) goes to
    # (4, 58) as seen: residual 0. With every step at a wall skipped, the old rule, the
    # prediction would stay at (4, 64): 6 px > STALE_TOL = 3, stale.
    slide = track((4, 64), (4, 62), (4, 60), (4, 58))
    assert diagnose(FULL, ("up",) * 3, {1: slide}, 1).kind == "ok"


def probe_actions() -> tuple[str, ...]:
    # design_block with n = PROBE_STEPS = 15 and p_noop = 0.2: round(3) = 3 no-ops and 12 moves, 3
    # of each.
    acts = design_block(np.random.default_rng(0), PROBE_STEPS, 0.2, DIRS)
    assert sorted(acts.count(a) for a in (*DIRS, "noop")) == [3] * 5
    return acts


def test_body_changed_on_a_probe_where_the_target_follows_a_mirrored_body() -> None:
    # The target obeys MIRROR from (64, 64): 15 steps of 2 px keep it inside [34, 94], off every
    # wall. Three of each action make p0 sit at the 1e-4 floor < ALPHA_ACT (PROBE_STEPS),
    # effect 2 >= EFFECT_MIN: mine. Each e_a = mean of three identical vectors - noop mean (0, 0),
    # so the new map is MIRROR exactly. The act block alone would read stale.
    acts = probe_actions()
    probe = (acts, {1: follow(acts, MIRROR, (64.0, 64.0))})
    d = diagnose(STALE_BODY, STALE_ACTIONS, STALE_TRACKS, 1, probe)
    assert d.kind == "body_changed" and d.body == MIRROR and d.swap is None


def test_target_lost_on_a_probe_where_the_target_ignores_the_actions() -> None:
    # The target drifts +2 px in x on every step whatever the action: every group mean equals the
    # grand mean, S = 0 under every shuffle, p0 = 1: not mine. Element 2 obeys FULL and is mine,
    # but the probe decides on the target alone.
    acts = probe_actions()
    drift = dict.fromkeys((*DIRS, "noop"), (2.0, 0.0))
    tracks = {1: follow(acts, drift, (30.0, 64.0)), 2: follow(acts, FULL, (64.0, 64.0))}
    d = diagnose(STALE_BODY, STALE_ACTIONS, STALE_TRACKS, 1, (acts, tracks))
    assert d.kind == "target_lost" and d.body is None


def test_a_target_never_seen_in_the_block_is_stale_so_the_probe_decides() -> None:
    body = {"right": (2.0, 0.0)}
    hidden = {7: np.full((4, 2), np.nan)}
    assert diagnose(body, ["right"] * 3, hidden, 7).kind == "stale"
    assert diagnose(body, ["right"] * 3, {}, 7).kind == "stale"
    once = {7: np.array([[40.0, 40.0], [np.nan, np.nan], [np.nan, np.nan], [np.nan, np.nan]])}
    assert diagnose(body, ["right"] * 3, once, 7).kind == "stale"
