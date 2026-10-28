"""T10, the agent loop and executor, on a scripted Muse and a hand-built three-element world.

The world: element 0 (the subject) starts at (40, 64); elements 1 and 2 wear its colour, so the
arena routes 1 through the subject at each block start and parks 2 halfway to the goal. Truth
tracking keeps the ids, so the S10 labels are exact: the subject is a perfect follower, mine at
the permutation floor 1e-4; element 1's only non-constant step is its jump onto the crossing route
at step 0, which no lag-0 grouping can make significant; element 2 never moves within a block. The
experiment draws its 30 actions from the agent's own stream; on it the subject ends at (38, 64)
under the identity body and at (28, 64) with `right` dead. The goal box (92..108, 56..72) has its
centre (100, 64) 31 cells right of (38, 64), so 30 steps of `right` end at x = 98, inside the box.
S14 is scripted here (its own tests are lane C's); S9, S10, S12, S13 and S15 are the real ones.
"""

from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np

from gate.agent import PROMPT, Body, Diagnose, RunBlock, _live, _pool, _steer, run_episode
from gate.arena import BODIES, Arena
from gate.constants import BLOCK_STEPS, MAX_FRAMES, MAX_MUSE_CALLS
from gate.meta_api import MuseReply, ToolCall
from gate.trackers import truth_tracker
from gate.types import Decision, Diagnosis, Element, EpisodeLog, Frames, Scenario, Tracks

RED = (230, 40, 40)
GOAL = (92.0, 56.0, 108.0, 72.0)
IDENTITY = ((0, BODIES["identity"]),)
DEAD_RIGHT = ((0, BODIES["dead_right"]),)
ALL = ["up", "down", "left", "right"]
EXPERIMENT = ("run_experiment", {"n": 30, "p_noop": 0.3, "dirs": ALL})
USAGE = {
    "input_tokens": 100,
    "output_tokens": 10,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 4},
}
LOST = "object 0 is not mine on the probe; re-probe every element"
Call = tuple[str, dict[str, Any]]


def world(maps: Any = IDENTITY, binding: Any = ((0, 0),), goal: Any = GOAL) -> Arena:
    elements = (
        Element(0, "circle", RED, "controlled", (40.0, 64.0)),
        Element(1, "square", RED, "decoy", (40.0, 100.0)),
        Element(2, "triangle", RED, "decoy", (70.0, 64.0)),
    )
    return Arena(Scenario(7, elements, binding, maps, (), goal, "feasible"))


class Muse:
    """A scripted muse_turn: the next tool call per turn, none once the script runs out."""

    def __init__(self, *calls: Call) -> None:
        self.calls = calls
        self.sent: list[tuple[str, Any, str | None]] = []

    def __call__(
        self, instructions: str, given: Any, tools: Any, previous: str | None
    ) -> MuseReply:
        k = len(self.sent)
        self.sent.append((instructions, given, previous))
        call = (ToolCall(*self.calls[k], f"c{k}"),) if k < len(self.calls) else ()
        return MuseReply("", call, f"r{k}", USAGE)

    def heard(self, turn: int) -> str:
        """Everything the executor sent on `turn`, as one string."""
        given = self.sent[turn][1]
        return given if isinstance(given, str) else "\n".join(o["output"] for o in given)


def runner(swap_block: int = -1, hide_block: int = -1) -> RunBlock:
    """T9's role: the arena steps, truth tracks; in block `swap_block` ids 0 and 2 trade places
    from frame 25 on, the way a tracker swaps two look-alikes; in `hide_block` id 0 is not seen."""
    done = [0]

    def run_block(
        arena: Arena, actions: Sequence[str], tracker: Any, acting: bool
    ) -> tuple[Frames, Tracks, str]:
        arena.start_block()
        for a in actions:
            arena.step(a, acting)
        tracks = tracker(arena.history[-len(actions) - 1 :])
        if done[0] == swap_block:
            tracks[0][25:], tracks[2][25:] = tracks[2][25:].copy(), tracks[0][25:].copy()
        if done[0] == hide_block:
            del tracks[0]
        done[0] += 1
        return np.zeros((len(actions) + 1, 1, 1, 3), np.uint8), tracks, f"clips/{done[0]}.mp4"

    return run_block


def scripted(*after_acts: str, probe: str = "body_changed", fix: str = "fix") -> Diagnose:
    """S14's role: `probe` on a probe; after an act block, stale when the target was seen on fewer
    than two frames (as S14 does since cf0a46b), else the scripted kinds in order, then ok."""
    queue = list(after_acts)

    def diagnose(
        body: Body, actions: Sequence[str], tracks: Tracks, target: int, given: Any
    ) -> Diagnosis:
        if given is not None:
            return Diagnosis(probe, fix, None, None)
        if target not in tracks or np.count_nonzero(~np.isnan(tracks[target][:, 0])) < 2:
            return Diagnosis("stale", "unseen", None, None)
        kind = queue.pop(0) if queue else "ok"
        return Diagnosis(kind, kind, (0, 2) if kind == "eyes_swapped" else None, None)

    return diagnose


def play(
    arena: Arena, muse: Muse, gated: bool, run_block: RunBlock | None = None, diagnose: Any = None
) -> EpisodeLog:
    return run_episode(
        arena,
        truth_tracker,
        "gated+truth" if gated else "no-gate+truth",
        gated,
        run_block=run_block or runner(),
        diagnose=diagnose or scripted(),
        muse_turn=muse,
    )


def test_gated_refuses_an_unsupported_act_and_ungated_runs_it() -> None:
    too_long = ("run_experiment", {"n": 40, "p_noop": 0.3, "dirs": ALL})
    muse = Muse(too_long, ("act", {"object_id": 2}), ("decline", {"reason": "no"}))
    log = play(world(), muse, gated=True)
    table = muse.heard(1)
    assert table.startswith(f"n clamped to {BLOCK_STEPS}") and len(table.splitlines()) <= 15
    assert table.endswith("advice: act 0: object 0 is the single mine and reaches the goal")
    assert muse.heard(2) == "refused: object 2 is not mine; object 0 is"
    assert [b.phase for b in log.blocks] == ["probe"] and len(log.blocks[0].actions) == BLOCK_STEPS
    assert log.blocks[0].decision == Decision("refused", 2, "object 2 is not mine; object 0 is")
    assert log.outcome == "decline"
    assert {s[0] for s in muse.sent} == {PROMPT}
    assert [s[2] for s in muse.sent] == [None, "r0", "r1"]
    assert log.usage == {
        "muse_calls": 3,
        "input_tokens": 300,
        "output_tokens": 30,
        "cached_tokens": 0,
        "reasoning_tokens": 12,
        "frames": BLOCK_STEPS + 1,
        "sam_calls": 1,
    }
    muse = Muse(too_long, ("act", {"object_id": 2}))
    log = play(world(), muse, gated=False)
    assert log.outcome == "false_act" and len(muse.sent) == 2
    assert not any(w in muse.heard(1) for w in ("mine", "p0", "advice"))


def test_an_eyes_swap_is_corrected_without_a_muse_turn() -> None:
    # goal centre (120, 64): act block 1 ends at x 98, where the swap has put id 0 on element 2,
    # parked at (78, 64); swapped back, id 0 is at 98 again and block 2 reaches the goal
    far = (112.0, 56.0, 128.0, 72.0)
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}))
    log = play(world(goal=far), muse, True, runner(swap_block=1), scripted("eyes_swapped"))
    assert len(muse.sent) == 2
    assert [b.phase for b in log.blocks] == ["probe", "act", "act"]
    diagnosis = log.blocks[1].diagnosis
    assert diagnosis is not None and diagnosis.kind == "eyes_swapped"
    assert log.outcome == "success"


def test_a_body_remap_ends_in_body_changed_with_the_new_map_and_the_goal_reached() -> None:
    # right is mirrored from the 10th act step: x goes 38 -> 58 -> 18, a stale block; the probe
    # measures right = (-2, 0); steering by it takes x 18 -> 78, then into the goal on block 3
    maps = ((0, BODIES["identity"]), (10, BODIES["mirror_x"]))
    act = ("act", {"object_id": 0})
    muse = Muse(EXPERIMENT, act, act)
    log = play(world(maps), muse, True, diagnose=scripted("stale", fix="new body"))
    assert [b.phase for b in log.blocks] == ["probe", "act", "probe", "act", "act"]
    assert Counter(log.blocks[2].actions) == dict.fromkeys(["noop", *ALL], 3)  # PROBE_STEPS = 15
    stale, probe = log.blocks[1].diagnosis, log.blocks[2].diagnosis
    assert stale is not None and stale.kind == "stale"
    assert probe is not None and probe.kind == "body_changed"
    target = log.blocks[2].evidence[0]
    assert target.label == "mine" and target.body["right"] == (-2.0, 0.0)
    assert log.blocks[2].advice == Decision("act", 0, "new body")
    assert "body_changed: new body" in muse.heard(2)
    assert log.outcome == "success" and len(muse.sent) == 3


def test_a_control_remap_ends_in_target_lost_with_the_advice_to_reprobe() -> None:
    remap = ((0, 0), (10, None))
    act, decline = ("act", {"object_id": 0}), ("decline", {"reason": "lost"})
    muse = Muse(EXPERIMENT, act, EXPERIMENT, decline)
    lost = scripted("stale", probe="target_lost", fix=LOST)
    log = play(world(binding=remap), muse, True, diagnose=lost)
    probe = log.blocks[2]
    assert probe.diagnosis is not None and probe.diagnosis.kind == "target_lost"
    assert probe.advice == Decision("probe", None, LOST)
    assert muse.heard(2).endswith(f"advice: probe: {LOST}")
    assert probe.decision is not None and probe.decision.kind == "probe"
    # the pool restarted at the diagnosis: the probe's 15 steps and the new 30, on look 3
    assert muse.heard(3).splitlines()[0] == "goal centre (100,64); look 3 of 6; 45 steps"
    assert log.outcome == "decline"
    # the same world and the same S14 ungated: no S14 runs, so the next act block is a false act
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}))
    lost = scripted("stale", probe="target_lost", fix=LOST)
    log = play(world(binding=remap), muse, False, diagnose=lost)
    assert [b.phase for b in log.blocks] == ["probe", "act"] and log.outcome == "false_act"


def test_a_target_the_tracker_loses_is_probed_and_handed_back() -> None:
    # the act block's tracks lack id 0, so S14 calls it stale; the executor keeps id 0's last
    # position, probes, and S9 finds the subject again on the probe's shared frame
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}), ("decline", {"reason": "lost"}))
    lost = scripted(probe="target_lost", fix=LOST)
    log = play(world(), muse, True, runner(hide_block=1), lost)
    stale = log.blocks[1].diagnosis
    assert [b.phase for b in log.blocks] == ["probe", "act", "probe"]
    assert stale is not None and stale.kind == "stale" and 0 in log.blocks[2].tracks
    assert log.outcome == "decline"


def test_muse_turns_stop_at_max_muse_calls() -> None:
    muse = Muse(*[("run_experiment", {"n": 2, "p_noop": 0.3, "dirs": ["up"]})] * 20)
    log = play(world(), muse, True)
    assert log.outcome == "timeout"
    assert len(muse.sent) == MAX_MUSE_CALLS and len(log.blocks) == MAX_MUSE_CALLS


def test_frames_stop_at_max_frames() -> None:
    # right is dead, so the goal is never reached; 31 + 9 * 31 = 310 = MAX_FRAMES, a 10th act
    # block would need 341
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}))
    log = play(world(DEAD_RIGHT), muse, False)
    assert log.outcome == "timeout"
    assert log.usage["frames"] == MAX_FRAMES and len(log.blocks) == 10


def test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one() -> None:
    body = {"down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (2.0, 0.0), "up": (0.0, -2.0)}
    assert _steer(_live(body), (40.0, 64.0), (100.0, 64.0)) == ("right",) * BLOCK_STEPS
    # right's 0.4 px is below EFFECT_MIN: dead; down and up tie (60.03 px), down comes first
    noisy = _steer(_live({**body, "right": (0.4, 0.0)}), (40.0, 64.0), (100.0, 64.0))
    assert "right" not in noisy and noisy[:3] == ("down", "up", "down")


def test_pool_joins_blocks_on_their_shared_frame() -> None:
    first = np.array([[0.0, 0.0], [0.0, -2.0], [0.0, -4.0]])
    back = np.array([[0.0, -4.0], [0.0, -2.0], [0.0, 0.0]])
    other = np.full((3, 2), 9.0)
    actions, tracks = _pool([(("up", "up"), {0: first}), (("down", "down"), {0: back, 1: other})])
    assert actions == ("up", "up", "down", "down")
    assert np.array_equal(tracks[0], [[0, 0], [0, -2], [0, -4], [0, -2], [0, 0]])
    nan = [np.nan, np.nan]
    assert np.array_equal(tracks[1], [nan, nan, nan, [9.0, 9.0], [9.0, 9.0]], equal_nan=True)


def test_a_success_the_tracker_fakes_is_scored_false_act() -> None:
    # right is dead, so the subject stays at x 28 while element 2 parks at (34, 64), inside the
    # goal box (32..48); the swap hands the subject's id to element 2, which the tracks put in
    # the goal; the truth read at the stop scores it false_act
    goal = (32.0, 56.0, 48.0, 72.0)
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}))
    log = play(world(DEAD_RIGHT, goal=goal), muse, False, runner(swap_block=1))
    assert [b.phase for b in log.blocks] == ["probe", "act"] and log.outcome == "false_act"


def test_bad_arguments_are_answered_and_run_nothing() -> None:
    bad = ("run_experiment", {"n": 30, "p_noop": 0.3, "dirs": ["north"]})
    muse = Muse(bad, ("act", {"object_id": 9}), ("fly", {}), ("decline", {"reason": "no"}))
    log = play(world(), muse, True)
    assert muse.heard(1).startswith("bad arguments")
    assert muse.heard(2).startswith("unknown object 9")
    assert muse.heard(3).startswith("unknown tool fly")
    assert log.blocks == () and log.outcome == "decline"
