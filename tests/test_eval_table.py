"""gate/eval.py on three hand-written EpisodeLogs whose metrics are worked out by hand in the
comments, plus hand-written histories for the eyes and occlusion metrics, and one real episode for
the replay. Prices are docs/api.md's: SAM $0.20 per 1k frames (50 at least per block), Muse
$1.25 / $4.25 per million input / output tokens.
"""

import functools
import math
from collections.abc import Sequence
from dataclasses import replace

import numpy as np
import pytest

from gate import eval as ev
from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import run_block, truth_slice
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import (
    BlockRecord,
    Decision,
    Diagnosis,
    Element,
    EpisodeLog,
    Evidence,
    Scenario,
    Tracks,
    Vec,
)

IDENTITY = {
    "noop": (0.0, 0.0),
    "up": (0.0, -2.0),
    "down": (0.0, 2.0),
    "left": (-2.0, 0.0),
    "right": (2.0, 0.0),
}
RED = (200, 30, 30)
Events = tuple[tuple[int, str, str], ...]


def scenario(case: str, events: Events = (), at: tuple[Vec, ...] = ((64.0, 64.0),)) -> Scenario:
    els = tuple(Element(i, ("circle", "square")[i], RED, "decoy", p) for i, p in enumerate(at))
    return Scenario(0, els, ((0, 0),), ((0, IDENTITY),), events, (100.0, 100.0, 116.0, 116.0), case)


def block(
    step0: int, phase: str, n: int, kind: str = "", said: str = "", did: str = ""
) -> BlockRecord:
    """n noop actions; `kind` the diagnosis, `said` the advice, `did` the decision ('' for none)."""
    evidence = (Evidence(0, 0.0, 1, 1.0, 2.0, {}, "mine" if kind == "mine" else "not_me"),)
    advice = Decision(said, None, "") if said else None
    decision = Decision(did, None, "") if did else None
    found = Diagnosis(kind, "", None, None) if kind not in ("", "mine") else None
    return BlockRecord(step0, phase, ("noop",) * n, "", {}, evidence, advice, decision, found)


def log(
    case: str, out: str, blocks: list[BlockRecord], tokens: tuple[int, int], events: Events = ()
) -> EpisodeLog:
    usage = {"input_tokens": tokens[0], "output_tokens": tokens[1]}
    return EpisodeLog(scenario(case, events), "gated+SAM", tuple(blocks), out, {}, usage)


REMAP = ((10, "control_remap", "0 -> None"),)
# L1, feasible: a 30-step probe, then a 30-step act block that reaches the goal.
L1 = log("feasible", "success", [block(0, "probe", 30), block(30, "act", 30, "ok")], (1000, 200))
# L2, remap_blocked: act from step 0, the remap fires at act step 10 inside that block, the
# diagnosis says stale, the 15-step diagnostic probe says target_lost, one more probe, then the
# decline.
L2 = log(
    "remap_blocked",
    "decline",
    [
        block(0, "probe", 30, said="act", did="act"),
        block(30, "act", 30, "stale"),
        block(60, "probe", 15, "target_lost", said="probe", did="probe"),
        block(75, "probe", 30, said="decline", did="decline"),
    ],
    (3000, 300),
    REMAP,
)
# L3, body_blocked: declines without any block ever labelling an element mine ("nothing obeys"),
# after Muse acted against probe advice once.
L3 = log(
    "body_blocked",
    "decline",
    [
        block(0, "probe", 30, said="probe", did="act"),
        block(30, "probe", 30, said="decline", did="decline"),
    ],
    (2000, 100),
)
LOGS = [L1, L2, L3]


def test_each_hand_written_log_is_scored_by_evals_column() -> None:
    # hand: L1 succeeds on feasible; L2 declines after 30 act steps, past the remap at 10;
    # L3 declines with no mine anywhere, which EVAL calls "nothing obeys", so it is wrong
    assert [ev.right(x) for x in LOGS] == [True, True, False]
    late = log("remap_blocked", "decline", [block(0, "probe", 30)], (0, 0), REMAP)
    assert not ev.right(late)  # hand: 0 act steps, so the decline came before the remap


def test_the_wilson_interval_by_hand() -> None:
    # hand, z = 1.959964, z^2 = 3.841459. k=1, n=1: centre (1 + 1.920729) / 4.841459 = 0.603275,
    # half 1.959964 * sqrt(3.841459 / 4) / 4.841459 = 0.396725, so [0.206550, 1.0].
    assert ev.wilson(1, 1) == pytest.approx((0.206550, 1.0), abs=1e-6)
    # k=1, n=2: centre 1.460365 / 2.920729 = 0.5, half 1.959964 * sqrt(0.125 + 0.240091) /
    # 2.920729 = 0.405469, so [0.094531, 0.905469].
    assert ev.wilson(1, 2) == pytest.approx((0.094531, 0.905469), abs=1e-6)


def test_the_column_of_the_three_logs_by_hand() -> None:
    cells = ev.column(LOGS, {k: [0, 0] for k in ev.KINDS}, {"probe": [0, 0, 0], "act": [0, 0, 0]})
    assert cells["six-case score"] == "2/3 = 0.67"
    assert cells["headline 1: right on blocked and remap cases"] == "1/2 = 0.50 [0.09, 0.91]"
    assert cells["headline 2: success on feasible"] == "1/1 = 1.00 [0.21, 1.00]"
    assert cells["false-action rate"] == "0/3 = 0.00"
    assert cells["correct declines on body_blocked"] == "0/1 = 0.00"
    # hand: L2's target_lost block starts after 30 act steps; the remap fired at 10: 20 steps
    assert cells["act steps to recover, control remap"] == "20.0 steps, 1 of 1 recovered"
    assert cells["act steps to recover, body remap"] == "none, 0 of 0 recovered"
    assert cells["advice overruled (in right episodes)"] == "1 (0)"  # L3's act against probe
    assert cells["blocks per episode"] == "2.67"  # hand: (2 + 4 + 2) / 3
    # hand: billed frames 50 per block (each has 16 or 31 frames): 100, 200, 100; 400 / 3 = 133
    assert cells["billed SAM frames per episode"] == "133"
    # hand: L1 $0.00125 + $0.00085 + $0.02; L2 $0.00375 + $0.001275 + $0.04; L3 $0.0025 +
    # $0.000425 + $0.02; all $0.09005 over 2 right = $0.0450
    assert cells["dollars per correct decision"] == "$0.0450"
    assert cells["input / output tokens per correct decision"] == "3000 / 300"  # 6000/2, 600/2
    assert cells["input / output tokens per episode"] == "2000 / 200"  # hand: 6000/3, 600/3


def test_two_logs_of_one_episode_are_an_error() -> None:
    with pytest.raises(ValueError, match="two logs"):
        ev.table([L1, L1])


def test_a_diagnosis_is_scored_against_the_block_the_remap_fired_in() -> None:
    # hand: L2's remap fired at act step 10, inside block 1 (act steps 0..29); block 2's
    # target_lost follows it, so it is right; the same verdict with no remap in the log is wrong
    assert ev.diagnosis_right(L2, 2, []) is True
    calm = log("remap_blocked", "decline", list(L2.blocks), (0, 0))
    assert ev.diagnosis_right(calm, 2, []) is False
    assert ev.diagnosis_right(L2, 1, []) is None  # stale is neither eyes, body nor control


def test_the_kill_decision_at_its_boundaries() -> None:
    assert ev.kill_passes(0.15, 0.25)
    assert not ev.kill_passes(0.10, 0.5)  # hand: EVAL.md rethinks at a difference <= 0.10
    assert ev.kill_passes(0.11, 0.20)  # hand: and at an occlusion lead below 0.20, so 0.20 passes
    assert not ev.kill_passes(0.5, 0.19)
    assert not ev.kill_passes(math.nan, 0.5) and not ev.kill_passes(0.5, math.nan)


@functools.cache
def truth_logs(seed: int) -> tuple[EpisodeLog, ...]:
    """Seed `seed`'s six cases, rules-only with the truth tracker."""
    out = []
    for case in (
        "feasible",
        "blocked",
        "remap_feasible",
        "remap_blocked",
        "body_remap",
        "body_blocked",
    ):
        arena = Arena(make_scenario(seed, case))
        out.append(
            run_episode(
                arena,
                truth_slice(arena, truth_tracker),
                "gated+SAM",
                True,
                clips=None,
                run_block=run_block,
                diagnose=diagnose,
                muse_turn=rules_turn,
            )
        )
    return tuple(out)


def relabel(logs: Sequence[EpisodeLog], condition: str, outcome: str = "") -> list[EpisodeLog]:
    return [replace(x, condition=condition, outcome=outcome or x.outcome) for x in logs]


def test_the_kill_line_on_real_logs() -> None:
    gated = list(truth_logs(ev.KILL_SEEDS[0]))
    assert ev.paired_difference(gated, relabel(gated, "x", "timeout")) == (1.0, 6)  # hand: 6 - 0
    logs = gated + relabel(gated, "no-gate+SAM", "timeout") + relabel(gated, "gated+colour")
    # hand: all six right against none, so 1.000 over 6 pairs; the truth tracker keeps every
    # identity under both labels, so the lead is 0, below 0.20: rethink
    line = ev.kill_rule(logs)
    assert "= 1.000 over 6 pairs" in line and "SAM 1.000 - colour 1.000 = 0.000" in line
    assert line.endswith("**Rethink.**")
    # with no block run, no overlap is ever scored: NaN, which is a rethink, never a pass
    empty = [replace(x, blocks=()) for x in gated]
    blank = empty + relabel(empty, "no-gate+SAM", "timeout") + relabel(empty, "gated+colour")
    assert "SAM nan" in ev.kill_rule(blank) and ev.kill_rule(blank).endswith("**Rethink.**")
    # a seed outside KILL_SEEDS is not judged
    late = [replace(x, scenario=replace(x.scenario, seed=100)) for x in logs]
    assert ev.kill_rule(late).startswith("Kill rule: not computed")


# Two true elements that never move, at x = 10 and x = 40; the block has 4 steps, 5 frames.
STILL: list[dict[int, Vec]] = [{0: (10.0, 10.0), 1: (40.0, 10.0)}] * 5
SWAPPED: Tracks = {  # the tracker's ids 7 and 8 trade places at frame 3
    7: np.array([[10.0, 10.0]] * 3 + [[40.0, 10.0]] * 2),
    8: np.array([[40.0, 10.0]] * 3 + [[10.0, 10.0]] * 2),
}
HELD: Tracks = {7: np.array([[10.0, 10.0]] * 5), 8: np.array([[40.0, 10.0]] * 5)}


def one_block(tracks: Tracks) -> EpisodeLog:
    b = BlockRecord(0, "act", ("noop",) * 4, "", tracks, (), None, None, None)
    return EpisodeLog(scenario("feasible"), "gated+colour", (b,), "success", {}, {})


def test_the_eyes_truth_is_a_change_of_the_tracker_to_true_map() -> None:
    # hand: id 7 is nearest element 0 on frames 0-2 and element 1 on frames 3-4
    assert ev.eyes_changed(one_block(SWAPPED).blocks[0], STILL)
    assert not ev.eyes_changed(one_block(HELD).blocks[0], STILL)


P: ev.Pairs = frozenset({(0, 1)})
E: ev.Pairs = frozenset()
NAN = [math.nan, math.nan]


def test_occlusion_is_kept_when_each_of_the_pair_keeps_its_id() -> None:
    pairs = [E, P, P, E, E]  # hand: elements 0 and 1 overlap on frames 1 and 2
    # hand: before (frame 0) 0 is held by 7 and 1 by 8; after (frame 3) by 8 and 7: none kept
    assert ev.occlusion(one_block(SWAPPED), STILL, pairs)["act"] == [0, 2, 0]
    assert ev.occlusion(one_block(HELD), STILL, pairs)["act"] == [2, 2, 0]
    # hand: a run on the first frame has no frame before it: unscored
    assert ev.occlusion(one_block(HELD), STILL, [P, E, E, E, E])["act"] == [0, 0, 1]
    # an id changing on element 2, outside the pair, does not count against the pair
    third = [{**f, 2: (70.0, 10.0)} for f in STILL]
    renamed = {
        **HELD,
        9: np.array([[70.0, 10.0]] * 3 + [NAN] * 2),
        10: np.array([NAN] * 3 + [[70.0, 10.0]] * 2),
    }
    assert ev.occlusion(one_block(renamed), third, pairs)["act"] == [2, 2, 0]
    # element 1 is never held apart again after the run: not kept
    lost = {7: HELD[7], 8: np.array([[40.0, 10.0]] * 3 + [NAN] * 2)}
    assert ev.occlusion(one_block(lost), STILL, pairs)["act"] == [0, 2, 0]
    # element 1 merges with its neighbour on frame 3, then is held again by 8 on frame 4: kept
    merged = {7: HELD[7], 8: np.array([[40.0, 10.0]] * 3 + [NAN, [40.0, 10.0]])}
    assert ev.occlusion(one_block(merged), STILL, pairs)["act"] == [2, 2, 0]
    # hand: a run reaching the episode's last frame has no frame after it: unscored
    assert ev.occlusion(one_block(HELD), STILL, [E, E, E, P, P])["act"] == [0, 0, 2]


def test_the_replay_rebuilds_the_runs_own_world() -> None:
    sc = make_scenario(1, "remap_feasible")  # a remap: the acting flag decides when it fires
    arena = Arena(sc)
    run = run_episode(
        arena,
        truth_slice(arena, truth_tracker),
        "rules-only+truth",
        True,
        clips=None,
        run_block=run_block,
        diagnose=diagnose,
        muse_turn=rules_turn,
    )
    history, overlap = ev.replay(run, ev.overlapping)
    assert history == arena.history and len(overlap) == len(history)


def test_two_elements_drawn_on_one_spot_overlap_and_apart_do_not() -> None:
    # hand: an 8 px circle and square on the same centre share the whole circle
    together = EpisodeLog(
        scenario("feasible", at=((64.0, 64.0), (64.0, 64.0))), "x", (), "", {}, {}
    )
    apart = EpisodeLog(scenario("feasible", at=((64.0, 64.0), (72.0, 64.0))), "x", (), "", {}, {})
    assert ev.replay(together, ev.overlapping)[1] == [frozenset({(0, 1)})]
    assert ev.replay(apart, ev.overlapping)[1] == [frozenset()]
