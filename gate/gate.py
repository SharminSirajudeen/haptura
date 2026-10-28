"""S13, the gate, and S15, the rule policy (plan §3). S14 follows T4, since it calls S10.

Both read `Evidence.label`, which S10 derived from ALPHA_ACT and EFFECT_MIN: one derivation per
quantity. Every reason is one sentence naming the evidence it rests on, since Muse reads it.
"""

from __future__ import annotations

from collections.abc import Sequence

from gate.constants import ALPHA_PROBE, EARLY_LOOKS, EFFECT_MIN
from gate.types import Decision, Evidence, Vec

Goal = tuple[float, float, float, float]  # x0, y0, x1, y1, as Scenario.goal


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
