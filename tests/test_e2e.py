"""The offline end-to-end floor: rules-only (the rule policy through the agent loop, `rules_turn`)
on the real arena with truth tracking, seeds 0-19 x all six cases, no network. It proves the
pipeline before money is spent: each episode is scored by EVAL.md's right-hand column
(`gate.eval.right`).

One test node per (case, seed), so a seed that falls is red at once. All 120 end right since the
wall rule was rewritten (the control test keeps the steps at a wall, measured 28 Oct); a miss
found later is pinned as a strict expected failure.
"""

import functools

import pytest

from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import run_block, truth_slice
from gate.eval import right
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import EpisodeLog

CASES = ("feasible", "blocked", "remap_feasible", "remap_blocked", "body_remap", "body_blocked")
SEEDS = range(20)
NODES = [(c, s) for c in CASES for s in SEEDS]


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


@pytest.mark.parametrize(("case", "seed"), NODES, ids=[f"{c}-{s}" for c, s in NODES])
def test_the_episode_ends_right_by_evals_table(case: str, seed: int) -> None:
    assert right(episode(seed, case))


def test_a_body_blocked_decline_cites_the_body() -> None:
    reasons = [[b.decision for b in episode(s, "body_blocked").blocks if b.decision] for s in SEEDS]
    assert all("no live action" in r[-1].reason for r in reasons)
