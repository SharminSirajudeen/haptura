"""T11, the offline end-to-end floor: rules-only (S15 through T10's loop, `rules_turn`) on the
real arena with truth tracking, seeds 0-19 x all six cases, no network. It proves the pipeline
before money is spent, scored against EVAL.md's outcome table and its qualifier column.

What holds is asserted; what the arena does not yet guarantee is pinned as a known defect (#21): a
one-way body lets the agent's own probe push the element where the goal is unreachable, and a body
remap may not touch the actions the steering uses.
"""

import functools

import pytest

from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import run_block, truth_slice
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import EpisodeLog

SEEDS = range(20)


@functools.cache
def episode(seed: int, case: str) -> EpisodeLog:
    arena = Arena(make_scenario(seed, case))
    return run_episode(
        arena,
        truth_slice(arena, truth_tracker),
        "rules-only+truth",
        True,
        clips=None,
        run_block=run_block,
        diagnose=diagnose,
        muse_turn=rules_turn,
    )


def defect_21(why: str) -> pytest.MarkDecorator:
    """Issue #21 pinned: the assertion fails today; a crash is not this defect; a pass is red."""
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"#21: {why}")


def diagnosed(log: EpisodeLog, kind: str) -> bool:
    return any(b.diagnosis is not None and b.diagnosis.kind == kind for b in log.blocks)


def acted(log: EpisodeLog) -> bool:
    return any(b.phase == "act" for b in log.blocks)


@pytest.mark.parametrize("case", ["blocked", "remap_blocked", "body_blocked"])
def test_every_case_that_cannot_succeed_is_declined(case: str) -> None:
    assert [episode(s, case).outcome for s in SEEDS] == ["decline"] * len(SEEDS)


def test_a_body_blocked_decline_cites_the_body_after_control_was_found() -> None:
    for s in SEEDS:
        log = episode(s, "body_blocked")
        last = [b.decision for b in log.blocks if b.decision][-1]
        found = any(e.label == "mine" for b in log.blocks for e in b.evidence)
        assert "no live action" in last.reason and found, s


def test_every_remap_feasible_success_went_through_target_lost() -> None:
    wins = [s for s in SEEDS if episode(s, "remap_feasible").outcome == "success"]
    assert wins and all(diagnosed(episode(s, "remap_feasible"), "target_lost") for s in wins)


@defect_21("a one-way body makes a feasible case unreachable after the probe")
@pytest.mark.parametrize("case", ["feasible", "remap_feasible", "body_remap"])
def test_every_feasible_type_case_succeeds(case: str) -> None:
    assert [episode(s, case).outcome for s in SEEDS] == ["success"] * len(SEEDS)


@defect_21("the probe's drift ends some remap_blocked runs before the remap")
def test_every_remap_blocked_decline_comes_after_acting_began() -> None:
    assert all(acted(episode(s, "remap_blocked")) for s in SEEDS)


@defect_21("a body remap may not touch the actions the steering uses")
def test_every_body_remap_success_went_through_body_changed() -> None:
    wins = [s for s in SEEDS if episode(s, "body_remap").outcome == "success"]
    assert all(diagnosed(episode(s, "body_remap"), "body_changed") for s in wins)
