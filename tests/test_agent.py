"""T10, the agent loop and executor, on a scripted Muse and a hand-built three-element world.

The world: element 0 (the subject) starts at (40, 64); elements 1 and 2 wear its colour, so the
arena routes 1 through the subject at each block start and parks 2 halfway to the goal. Truth
tracking keeps the ids, so the S10 labels are exact: the subject is a perfect follower, mine at
the permutation floor 1e-4; element 1's only non-constant step is its jump onto the crossing route
at step 0, which no lag-0 grouping can make significant; element 2 never moves within a block. The
experiment draws its 30 actions from the agent's own stream; on it the subject ends at (38, 64)
under the identity body and at (28, 64) with `right` dead. The goal box (92..108, 56..72) has its
centre (100, 64) 31 cells right of (38, 64), so 30 steps of `right` end at x = 98, inside the box.
S14 is scripted here (its own tests are lane C's); T9, S9, S10, S12, S13 and S15 are the real
ones, T9 wrapped where a test needs the tracker to err.
"""

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from gate.agent import (
    PROMPT,
    Body,
    Diagnose,
    RunBlock,
    _live,
    _pool,
    _steer,
    rules_turn,
    run_episode,
)
from gate.arena import BODIES, Arena
from gate.constants import BLOCK_STEPS, MAX_FRAMES, MAX_LAG, MAX_MUSE_CALLS, P_NOOP
from gate.control import control_scores
from gate.episode import Tracker, run_block, truth_slice
from gate.gate import PROBE_SEED, diagnose
from gate.meta_api import MuseReply, ToolCall
from gate.trackers import truth_tracker
from gate.types import Decision, Diagnosis, Element, EpisodeLog, Frames, Scenario, Tracks

RED = (230, 40, 40)
GOAL = (92.0, 56.0, 108.0, 72.0)
NEAR = (32.0, 56.0, 48.0, 72.0)  # under DEAD_RIGHT: holds element 2's parking spot, not the subject
IDENTITY = ((0, BODIES["identity"]),)
DEAD_RIGHT = ((0, BODIES["dead_right"]),)
ALL = ["up", "down", "left", "right"]
EXPERIMENT = ("run_experiment", {"n": 30, "p_noop": 0.3, "dirs": ALL})
HALF = ("run_experiment", {"n": 15, "p_noop": 0.3, "dirs": ALL})
ACT = ("act", {"object_id": 0})
USAGE = {
    "input_tokens": 100,
    "output_tokens": 10,
    "input_tokens_details": {"cached_tokens": 5},
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
    """T9's run_block with a tracker that errs: in block `swap_block` ids 0 and 2 trade places from
    frame 25 on, the way a tracker swaps two look-alikes; in `hide_block` id 0 is not seen."""
    done = [0]

    def erring(
        arena: Arena, actions: Sequence[str], tracker: Tracker, acting: bool, clip: Path | None
    ) -> tuple[Frames, Tracks]:
        frames, tracks = run_block(arena, actions, tracker, acting, clip)
        if done[0] == swap_block:
            tracks[0][25:], tracks[2][25:] = tracks[2][25:].copy(), tracks[0][25:].copy()
        if done[0] == hide_block:
            del tracks[0]
        done[0] += 1
        return frames, tracks

    return erring


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
    arena: Arena,
    muse: Muse,
    gated: bool,
    blocks: RunBlock = run_block,
    diagnose: Diagnose | None = None,
    clips: Path | None = None,
) -> EpisodeLog:
    return run_episode(
        arena,
        truth_slice(arena, truth_tracker),
        "gated+truth" if gated else "no-gate+truth",
        gated,
        clips=clips,
        run_block=blocks,
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
    assert log.blocks[0].clip_path == ""  # no clips directory, no clip
    assert log.blocks[0].decision == Decision("refused", 2, "object 2 is not mine; object 0 is")
    assert log.outcome == "decline"
    assert {s[0] for s in muse.sent} == {PROMPT}
    assert len(PROMPT) <= 1200  # the 300-token cap, assuming about 4 characters per token
    assert [s[2] for s in muse.sent] == [None, "r0", "r1"]
    assert log.usage == {
        "muse_calls": 3,
        "input_tokens": 300,
        "output_tokens": 30,
        "cached_tokens": 15,
        "reasoning_tokens": 12,
        "frames": BLOCK_STEPS + 1,
        "sam_calls": 1,
    }
    muse = Muse(too_long, ("act", {"object_id": 2}))
    log = play(world(), muse, gated=False)
    assert log.outcome == "false_act" and len(muse.sent) == 2
    assert log.blocks[0].decision == Decision("act", 2, 'act {"object_id": 2}')
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
    # the probe's table is S14's own S10 call, so it cannot disagree with S14's verdict
    recomputed = control_scores(log.blocks[2].actions, log.blocks[2].tracks, MAX_LAG, PROBE_SEED)
    assert log.blocks[2].evidence == tuple(recomputed)
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
    # its S10 seed: scenario seed 7 * SEED_STRIDE (= MAX_FRAMES) + block index 3
    pooled = _pool([(b.actions, b.tracks) for b in log.blocks[2:4]])
    assert log.blocks[3].evidence == tuple(control_scores(*pooled, MAX_LAG, 7 * MAX_FRAMES + 3))
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


def test_each_block_saves_its_clip_under_the_name_the_episode_passed(tmp_path: Path) -> None:
    muse = Muse(EXPERIMENT, ("act", {"object_id": 0}))
    log = play(world(), muse, True, clips=tmp_path)
    assert log.outcome == "success"
    assert [b.clip_path for b in log.blocks] == [str(tmp_path / "00.mp4"), str(tmp_path / "01.mp4")]
    assert all(Path(b.clip_path).stat().st_size > 0 for b in log.blocks)


def test_muse_turns_stop_at_max_muse_calls() -> None:
    muse = Muse(*[("run_experiment", {"n": 2, "p_noop": 0.3, "dirs": ["up"]})] * 20)
    log = play(world(), muse, True)
    assert log.outcome == "timeout"
    assert len(muse.sent) == MAX_MUSE_CALLS and len(log.blocks) == MAX_MUSE_CALLS


@pytest.mark.parametrize(
    ("experiments", "frames"),
    [((EXPERIMENT,), MAX_FRAMES), ((HALF, HALF), 280)],
    ids=["fills_max_frames", "one_frame_short"],
)
def test_frames_stop_at_max_frames(experiments: tuple[Call, ...], frames: int) -> None:
    # right is dead, so act blocks of 31 frames run until the next would not fit:
    # 31 + 9 * 31 = 310 = MAX_FRAMES; 16 + 16 + 8 * 31 = 280, and a 9th act block needs 311
    log = play(world(DEAD_RIGHT), Muse(*experiments, ACT), False)
    assert log.outcome == "timeout"
    assert log.usage["frames"] == frames and len(log.blocks) == 10


def test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one() -> None:
    body = {"down": (0.0, 2.0), "left": (-2.0, 0.0), "right": (2.0, 0.0), "up": (0.0, -2.0)}
    assert _steer(_live(body), (40.0, 64.0), (100.0, 64.0)) == ("right",) * BLOCK_STEPS
    # right's 0.4 px is below EFFECT_MIN: dead; down and up tie (60.03 px), down comes first
    noisy = _steer(_live({**body, "right": (0.4, 0.0)}), (40.0, 64.0), (100.0, 64.0))
    assert "right" not in noisy and noisy[:3] == ("down", "up", "down")
    assert _live({"right": (1.0, 0.0)}) == {"right": (1.0, 0.0)}  # exactly EFFECT_MIN is alive


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
    log = play(world(DEAD_RIGHT, goal=NEAR), Muse(EXPERIMENT, ACT), False, runner(swap_block=1))
    assert [b.phase for b in log.blocks] == ["probe", "act"] and log.outcome == "false_act"


def tie_world() -> Arena:
    """Element 2 obeys from step 0 and element 0 is a decoy, so a tie broken by id goes to 0."""
    elements = (
        Element(0, "square", RED, "decoy", (40.0, 100.0)),
        Element(1, "triangle", RED, "decoy", (70.0, 30.0)),
        Element(2, "circle", RED, "controlled", (40.0, 64.0)),
    )
    return Arena(Scenario(7, elements, ((0, 2),), IDENTITY, (), GOAL, "feasible"))


def onto_target(every_frame: bool) -> RunBlock:
    """T9's run_block, then each act block puts element 0 on element 2's pixel, in the truth and
    in the tracks as the truth tracker sees it: on the block's last frame, or on all of them."""

    def hook(
        arena: Arena, actions: Sequence[str], tracker: Tracker, acting: bool, clip: Path | None
    ) -> tuple[Frames, Tracks]:
        frames, tracks = run_block(arena, actions, tracker, acting, clip)
        if acting:
            span = slice(0, None) if every_frame else slice(-1, None)
            for frame in arena.history[-len(actions) - 1 :][span]:
                frame[0] = frame[2]
            tracks[0][span] = tracks[2][span]
        return frames, tracks

    return hook


TIE_ACT = ("act", {"object_id": 2})


def test_a_tie_on_the_last_frame_is_told_apart_along_the_targets_own_track() -> None:
    # Element 2 is steered into the goal. On each act block's last frame element 0 stands on the
    # same pixel, in the truth and in the tracks, so a tie broken by id says false_act; one frame
    # back element 0 is still at its own spot, so the target's own track is element 2's: success
    arena = tie_world()
    log = play(arena, Muse(EXPERIMENT, TIE_ACT), False, onto_target(False))
    assert arena.history[-1][0] == arena.history[-1][2] and log.outcome == "success"


def test_a_tie_held_through_the_whole_block_is_not_control() -> None:
    # The same, but element 0 shares element 2's pixel on every frame of the act block: nothing
    # tells them apart, and a tie is not control
    arena = tie_world()
    log = play(arena, Muse(EXPERIMENT, TIE_ACT), False, onto_target(True))
    assert arena.history[-1][0] == arena.history[-1][2] and log.outcome == "false_act"


def test_the_eyes_fix_comes_before_the_goal_check() -> None:
    # S15 advises declining: from x 28, the centre's x 40 needs right, which is dead. Muse acts
    # anyway. The swap puts id 0 on element 2, parked at (34, 64) inside the goal box; swapped
    # back first, id 0 is the subject at x 28, outside it, so the act runs out of frames
    muse = Muse(EXPERIMENT, ACT)
    log = play(world(DEAD_RIGHT, goal=NEAR), muse, True, runner(1), scripted("eyes_swapped"))
    reason = "object 0 is mine but no live action moves it along x to the goal"
    assert muse.heard(1).endswith(f"advice: decline 0: {reason}")
    assert log.outcome == "timeout"


def test_bad_arguments_are_answered_and_run_nothing() -> None:
    bad = ("run_experiment", {"n": 30, "p_noop": 0.3, "dirs": ["north"]})
    muse = Muse(bad, ("act", {"object_id": 9}), ("fly", {}), ("decline", {"reason": "no"}))
    log = play(world(), muse, True)
    assert muse.heard(1).startswith("bad arguments")
    assert muse.heard(2).startswith("unknown object 9")
    assert muse.heard(3).startswith("unknown tool fly")
    assert log.blocks == () and log.outcome == "decline"


def test_rules_turn_answers_the_latest_advice_line() -> None:
    later = [{"output": "t\nadvice: probe: 2 mine"}, {"output": "t\nadvice: act 3: 3 is mine"}]
    act = rules_turn(PROMPT, later, None, None).tool_calls[0]
    assert (act.name, act.arguments) == ("act", {"object_id": 3})
    out = [{"output": "advice: decline: every p0 is above 0.2"}]
    decline = rules_turn(PROMPT, out, None, None).tool_calls[0]
    assert (decline.name, decline.arguments) == ("decline", {"reason": "every p0 is above 0.2"})
    first = rules_turn(PROMPT, "The goal box spans x 92 to 108.", None, None).tool_calls[0]
    probe = {"n": BLOCK_STEPS, "p_noop": P_NOOP, "dirs": ALL}
    assert (first.name, first.arguments) == ("run_experiment", probe)


def rules_only(arena: Arena) -> EpisodeLog:
    tracker = truth_slice(arena, truth_tracker)
    return run_episode(
        arena,
        tracker,
        "rules-only+truth",
        True,
        clips=None,
        run_block=run_block,
        diagnose=diagnose,
        muse_turn=rules_turn,
    )


def test_rules_only_acts_on_the_single_mine_and_reaches_the_goal() -> None:
    log = rules_only(world())
    decisions = [b.decision.kind for b in log.blocks if b.decision]
    assert log.outcome == "success" and decisions[0] == "act"
    assert log.blocks[0].advice is not None and log.blocks[0].advice.kind == "act"


def test_rules_only_relearns_a_remapped_body_and_reaches_the_goal() -> None:
    log = rules_only(world(((0, BODIES["identity"]), (10, BODIES["mirror_x"]))))
    assert [b.phase for b in log.blocks] == ["probe", "act", "probe", "act", "act"]
    found = log.blocks[2].diagnosis
    assert found is not None and found.kind == "body_changed" and log.outcome == "success"


def test_rules_only_reprobes_when_control_moves_and_then_declines() -> None:
    log = rules_only(world(binding=((0, 0), (10, None))))
    assert [b.phase for b in log.blocks] == ["probe", "act", "probe", "probe"]
    found = log.blocks[2].diagnosis
    assert found is not None and found.kind == "target_lost" and log.outcome == "decline"


def test_rules_only_declines_when_nothing_obeys() -> None:
    log = rules_only(world(binding=((0, None),)))
    assert log.outcome == "decline"
    assert all(b.decision is None or b.decision.kind != "act" for b in log.blocks)
    said = [(b.advice.reason, b.decision.reason) for b in log.blocks if b.advice and b.decision]
    assert len(said) == len(log.blocks) and all(
        a == d for a, d in said
    )  # S15 decides, word for word
