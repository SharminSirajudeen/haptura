"""S13 and S15 on hand-written Evidence tuples. Each expected value is derived in its comment.

Constants used: ALPHA_ACT = 0.01 / 48 = 2.083e-4, ALPHA_PROBE = 0.2, EFFECT_MIN = 0.5 * 2 = 1.0.
"""

from collections.abc import Mapping

from gate.constants import ALPHA_ACT, ALPHA_PROBE, EFFECT_MIN
from gate.gate import check_act, rule_policy
from gate.types import Evidence, Vec

Body = Mapping[str, Vec | None]
FULL: Body = {"up": (0.0, -2.0), "down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (2.0, 0.0)}
P_FLOOR = 1e-4  # a mine element sits at the permutation floor 1 / (PERMS + 1), below ALPHA_ACT


def ev(object_id: int, label: str, p0: float = 0.5, body: Body = FULL) -> Evidence:
    """S13 and S15 read object_id, p0, body and label; the lag fields are filler."""
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
    # p0 = 2.2e-4 sits just above ALPHA_ACT = 2.083e-4, so S10 labelled the element not_me and
    # nothing is mine. S13 reads the label, never p, so even this near miss is refused.
    p0 = 2.2e-4
    assert ALPHA_ACT < p0 < ALPHA_PROBE
    d = check_act([ev(3, "not_me", p0)], 3)
    assert d.kind == "refused" and "0 elements" in d.reason


def test_acts_on_the_single_mine_when_the_goal_is_reachable() -> None:
    # Mirrored body: "left" moves +1.0 px in x, exactly EFFECT_MIN, and at least counts, so x
    # (needing +60) is reached through "left". y needs 0, so the unsampled up and down do not
    # matter. The act rule comes first: a spent budget (6 of 6) does not stop it.
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
