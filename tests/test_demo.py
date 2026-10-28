"""T15's demo tool, offline: a replayed clip is the run's own frames, the plan's rule picks the
pairs, and only a picked pair is written for the page."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np

from gate import demo
from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import Tracker, join_blocks, run_block, truth_slice
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import EpisodeLog, Frames, Tracks, from_json, to_json


def recorded(seed: int, case: str) -> tuple[EpisodeLog, list[Frames]]:
    """A free rules-only episode, and every block's frames as the run itself rendered them."""
    seen: list[Frames] = []

    def keep(
        arena: Arena,
        actions: Sequence[str],
        tracker: Tracker,
        acting: bool,
        path: Path | None = None,
    ) -> tuple[Frames, Tracks]:
        frames, tracks = run_block(arena, actions, tracker, acting, path)
        seen.append(frames)
        return frames, tracks

    arena = Arena(make_scenario(seed, case))
    log = run_episode(
        arena,
        truth_slice(arena, truth_tracker),
        "rules-only+truth",
        True,
        clips=None,
        run_block=keep,
        diagnose=diagnose,
        muse_turn=rules_turn,
    )
    return log, seen


def test_the_clip_is_the_runs_own_frames() -> None:
    log, seen = recorded(1, "remap_feasible")  # a remap: the acting flag decides when it fires
    assert np.array_equal(demo.clip(log), join_blocks(seen))


def test_the_plans_rule_picks_the_pairs() -> None:
    log, _ = recorded(1, "feasible")
    other = replace(log, scenario=replace(log.scenario, seed=2))
    gated = [log, other, replace(log, scenario=replace(log.scenario, seed=3), outcome="decline")]
    baseline = [replace(x, outcome="false_act") for x in gated] + [replace(log, outcome="success")]
    # hand: seeds 1 and 2 are right gated and false_act ungated; seed 3's gated run declined a
    # feasible case, so it is wrong; the baseline's success on seed 1 is a second log, not a pick
    assert demo.candidates(gated, baseline[:3]) == [(1, "feasible"), (2, "feasible")]
    assert demo.candidates(gated, [replace(log, outcome="success")]) == []


def test_only_a_picked_pair_is_written_for_the_page(tmp_path: Path) -> None:
    log, _ = recorded(1, "feasible")
    for name, x in (("g", log), ("b", replace(log, condition="no-gate+SAM", outcome="false_act"))):
        (tmp_path / name).mkdir()
        (tmp_path / name / "1-feasible.json").write_text(to_json(x))
    out = tmp_path / "episodes"
    args = [str(tmp_path / "g"), str(tmp_path / "b")]
    assert demo.main([*args, "2-feasible"], out) == [(1, "feasible")] and not out.exists()
    demo.main([*args, "1-feasible"], out)
    assert sorted(p.name for p in out.iterdir()) == [
        "baseline.json",
        "baseline.mp4",
        "gated.json",
        "gated.mp4",
    ]
    assert from_json((out / "baseline.json").read_text(), EpisodeLog).outcome == "false_act"
    assert (out / "gated.mp4").read_bytes()[4:8] == b"ftyp"  # an MP4 container
