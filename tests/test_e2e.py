"""T11, the offline end-to-end floor: rules-only (S15 through T10's loop, `rules_turn`) on the
real arena with truth tracking, seeds 0-19 x all six cases, no network. It proves the pipeline
before money is spent: each episode is scored by EVAL.md's right-hand column, outcome and qualifier.

One test node per (case, seed), so a seed that falls is red at once. The seeds that miss today are
pinned to their issue (measured 28 Oct): #24, S10 blind to the element control moved to once a
one-way body has pressed it against a wall. A fix turns its seeds into unexpected passes, which are
red until the pin is removed.
"""

import functools

import pytest

from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import run_block, truth_slice
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import EpisodeLog

CASES = ("feasible", "blocked", "remap_feasible", "remap_blocked", "body_remap", "body_blocked")
SEEDS = range(20)
MISSES = {("remap_feasible", 0): 24, ("remap_feasible", 12): 24}


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


def acted_before(log: EpisodeLog, i: int) -> int:
    """Act steps taken before block i: the clock the remap schedules run on."""
    return sum(len(b.actions) for b in log.blocks[:i] if b.phase == "act")


def right(log: EpisodeLog) -> bool:
    """EVAL.md's right-hand column. The remap step is the scenario's one event, in act steps."""
    sc, blocks, out = log.scenario, log.blocks, log.outcome
    step = sc.events[0][0] if sc.events else 0
    after = [b for i, b in enumerate(blocks) if acted_before(log, i) >= step]
    kinds = {b.diagnosis.kind for b in after if b.diagnosis is not None}
    return {
        "feasible": out == "success",
        "blocked": out == "decline",
        "remap_feasible": out == "success"
        and (any(b.phase == "probe" for b in after) or "target_lost" in kinds),
        "remap_blocked": out == "decline" and acted_before(log, len(blocks)) >= step,
        "body_remap": out == "success" and "body_changed" in kinds,
        "body_blocked": out == "decline"
        and any(e.label == "mine" for b in blocks for e in b.evidence),
    }[sc.case]


def pinned(case: str, seed: int) -> object:
    """The (case, seed) node, marked as its issue's known miss when it is one."""
    issue = MISSES.get((case, seed))
    why = pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"#{issue}")
    return pytest.param(case, seed, marks=[] if issue is None else [why], id=f"{case}-{seed}")


@pytest.mark.parametrize(("case", "seed"), [pinned(c, s) for c in CASES for s in SEEDS])
def test_the_episode_ends_right_by_evals_table(case: str, seed: int) -> None:
    assert right(episode(seed, case))


def test_a_body_blocked_decline_cites_the_body() -> None:
    reasons = [[b.decision for b in episode(s, "body_blocked").blocks if b.decision] for s in SEEDS]
    assert all("no live action" in r[-1].reason for r in reasons)
