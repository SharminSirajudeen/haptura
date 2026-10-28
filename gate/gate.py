"""S13, the gate; S14, the diagnosis after an act block; S15, the rule policy (plan §3).

All three read `Evidence.label`, which S10 derived from ALPHA_ACT and EFFECT_MIN: one derivation per
quantity. Every reason is one sentence naming the evidence it rests on, since Muse reads it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from gate.constants import ALPHA_PROBE, EARLY_LOOKS, EFFECT_MIN, JUMP_TOL, MAX_LAG, STALE_TOL
from gate.control import Floats, Ints, at_wall, control_scores
from gate.types import Array, Decision, Diagnosis, Evidence, Tracks, Vec

Goal = tuple[float, float, float, float]  # x0, y0, x1, y1, as Scenario.goal
PROBE_SEED = 0  # S14's S10 call on the probe: fixed, so a diagnosis replays exactly


def check_act(evidence: Sequence[Evidence], object_id: int) -> Decision:
    """S13: act only when `object_id` is the single element labelled mine."""
    mine = [e.object_id for e in _mine(evidence)]
    if len(mine) != 1:
        reason = f"{len(mine)} elements are labelled mine {mine}, not one"
        return Decision("refused", object_id, reason)
    if mine[0] != object_id:
        return Decision(
            "refused", object_id, f"object {object_id} is not mine; object {mine[0]} is"
        )
    return Decision("act", object_id, f"object {object_id} is the single element labelled mine")


def rule_policy(
    evidence: Sequence[Evidence], blocks_used: int, budget: int, target_pos: Vec, goal: Goal
) -> Decision:
    """S15, in this order: act on the single mine when the goal is reachable; decline citing the
    body when it is not; decline when the budget is spent, or when every p0 is above ALPHA_PROBE
    after EARLY_LOOKS looks; else probe."""
    mine = _mine(evidence)
    if len(mine) == 1:
        return _act_or_decline(mine[0], target_pos, goal)
    if blocks_used >= budget:
        return Decision("decline", None, f"no single mine element after all {budget} looks")
    if blocks_used >= EARLY_LOOKS and all(e.p0 > ALPHA_PROBE for e in evidence):
        reason = f"every p0 is above {ALPHA_PROBE} after {blocks_used} looks"
        return Decision("decline", None, reason)
    reason = f"{len(mine)} elements are labelled mine after {blocks_used} of {budget} looks"
    return Decision("probe", None, reason)


def _act_or_decline(e: Evidence, target_pos: Vec, goal: Goal) -> Decision:
    """Act on the mine element `e` when its live body reaches the goal's centre, else decline."""
    centre = ((goal[0] + goal[2]) / 2, (goal[1] + goal[3]) / 2)
    live = [v for v in e.body.values() if v is not None]
    missing = [
        name
        for axis, name in enumerate("xy")
        if not _reaches(live, axis, centre[axis] - target_pos[axis])
    ]
    if missing:
        axes = " and ".join(missing)
        reason = (
            f"object {e.object_id} is mine but no live action moves it along {axes} to the goal"
        )
        return Decision("decline", e.object_id, reason)
    return Decision(
        "act", e.object_id, f"object {e.object_id} is the single mine and reaches the goal"
    )


def _reaches(live: list[Vec], axis: int, need: float) -> bool:
    """Nothing is needed on `axis`, or a live vector moves `need`'s way by at least EFFECT_MIN."""
    return need == 0 or any(v[axis] * need > 0 and abs(v[axis]) >= EFFECT_MIN for v in live)


def _mine(evidence: Sequence[Evidence]) -> list[Evidence]:
    """The elements S10 labelled mine: the label is read, never re-derived from p."""
    return [e for e in evidence if e.label == "mine"]


def diagnose(
    body: Mapping[str, Vec | None],
    actions: Sequence[str],
    tracks: Tracks,
    target_id: int,
    probe: tuple[Sequence[str], Tracks] | None = None,
) -> Diagnosis:
    """S14, first rule that holds: eyes_swapped, stale, ok. With `probe` given, S10 on the probe
    alone decides body_changed or target_lost. An action with no measured vector, and every step
    at a wall, predicts no motion."""
    if probe is not None:
        return _reprobe(probe[0], probe[1], target_id)
    pos = tracks.get(target_id)
    if pos is None or np.count_nonzero(~np.isnan(pos).any(axis=1)) < 2:
        # nothing to predict from: a belief is wrong, and the probe decides which
        return Diagnosis(
            "stale", f"object {target_id} was not seen in this block; probe it", None, None
        )
    steps = np.array([body[a] or (0.0, 0.0) for a in actions])
    wall = at_wall(pos)
    steps[wall[:-1] | wall[1:]] = 0.0
    moved: Floats = np.vstack([np.zeros((1, 2)), np.cumsum(steps, axis=0)])
    seen = np.flatnonzero(~np.isnan(pos).any(axis=1))
    swap = _swap(tracks, target_id, moved, seen)
    if swap is not None:
        other, t2 = swap
        fix = f"tracker ids {target_id} and {other} swapped at frame {t2}; swap them back"
        return Diagnosis("eyes_swapped", fix, (target_id, other), None)
    first, last = seen[0], seen[-1]
    residual = _dist(pos[last], _predict(pos, moved, first, last))
    if residual > STALE_TOL:
        fix = f"object {target_id} ended {residual:.1f} px from its prediction; probe its body"
        return Diagnosis("stale", fix, None, None)
    return Diagnosis(
        "ok", f"object {target_id} ended {residual:.1f} px from its prediction", None, None
    )


def _swap(tracks: Tracks, target_id: int, moved: Floats, seen: Ints) -> tuple[int, int] | None:
    """(other id, t2) for the first span between visible frames t1 and t2 where the target lands
    more than JUMP_TOL from its prediction and another track is within JUMP_TOL of it."""
    pos = tracks[target_id]
    for t1, t2 in zip(seen[:-1], seen[1:]):
        guess = _predict(pos, moved, t1, t2)
        near = [o for o, p in tracks.items() if _dist(p[t2], guess) <= JUMP_TOL]
        if _dist(pos[t2], guess) > JUMP_TOL and near:
            return near[0], int(t2)
    return None


def _predict(pos: Array, moved: Floats, t1: int, t2: int) -> Floats:
    """The target at visible frame t1 plus the body's steps t1..t2-1, wall steps skipped."""
    guess: Floats = pos[t1] + moved[t2] - moved[t1]
    return guess


def _dist(a: Floats, b: Floats) -> float:
    """Euclidean distance; NaN, which compares false, where either point is missing."""
    return float(np.linalg.norm(a - b))


def _reprobe(actions: Sequence[str], tracks: Tracks, target_id: int) -> Diagnosis:
    """S14 on the diagnostic probe: body_changed with the new map if S10 labels the target mine."""
    found = [
        e for e in control_scores(actions, tracks, MAX_LAG, PROBE_SEED) if e.object_id == target_id
    ]
    mine = _mine(found)
    if mine:
        fix = f"object {target_id} is mine on the probe with a new body map; steer by it"
        return Diagnosis("body_changed", fix, None, mine[0].body)
    fix = f"object {target_id} is not mine on the probe; re-probe every element"
    return Diagnosis("target_lost", fix, None, None)
