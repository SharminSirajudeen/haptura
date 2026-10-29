"""The demo tool, offline: a replayed clip is the run's own frames, the opening rule picks the
pairs, and only a picked pair is written for the page."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from gate import demo
from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import Tracker, join_blocks, run_block, truth_slice
from gate.gate import diagnose
from gate.trackers import truth_tracker
from gate.types import Decision, EpisodeLog, Frames, Tracks, from_json, to_json


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
    gated, _ = recorded(1, "feasible")  # hand: a 30-step probe, then act blocks from step 30
    probe, act = gated.blocks[0], gated.blocks[1]
    assert (probe.phase, probe.step0, len(probe.actions), act.phase, act.step0) == (
        "probe",
        0,
        30,
        "act",
        30,
    )
    commit = replace(probe, decision=Decision("act", 3, "r"))
    base = replace(gated, condition="no-gate+SAM", outcome="false_act", blocks=(commit,))
    # hand: the baseline committed to an element it did not control at frame 30, inside the first
    # 200; the gated run is right and its first act block starts at frame 30, not before
    assert demo.candidates([gated], [base]) == [(1, "feasible")]
    # a run that ended any other way after acting is not a false act
    assert demo.candidates([gated], [replace(base, outcome="timeout")]) == []
    # a false act after acting began is a lost element, not a commit to a decoy
    assert demo.candidates([gated], [replace(base, blocks=(commit, act))]) == []
    # a commit after the first 20 seconds (frame 230), against a gated run that never acted
    idle = replace(gated, blocks=(probe,))
    assert demo.candidates([idle], [base]) == [(1, "feasible")]
    assert demo.candidates([idle], [replace(base, blocks=(replace(commit, step0=200),))]) == []
    # the gated run had already acted at frame 0
    early = replace(gated, blocks=(replace(probe, phase="act"), *gated.blocks[1:]))
    assert demo.candidates([early], [base]) == []
    # the gated run is wrong: it declined a feasible case
    assert demo.candidates([replace(gated, outcome="decline")], [base]) == []
    with pytest.raises(ValueError, match="two logs"):
        demo.candidates([gated, gated], [base])


def test_only_a_picked_pair_is_written_for_the_page(tmp_path: Path) -> None:
    log, _ = recorded(1, "feasible")
    commit = replace(log.blocks[0], decision=Decision("act", 3, "r"))
    base = replace(log, condition="no-gate+SAM", outcome="false_act", blocks=(commit,))
    for name, x in (("g", log), ("b", base)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "1-feasible.json").write_text(to_json(x))
    out = tmp_path / "episodes"
    args = [str(tmp_path / "g"), str(tmp_path / "b")]
    for wrong in ("2-feasible", "01-feasible", "1feasible"):  # matched as text, never parsed
        assert demo.main([*args, wrong], out) == [(1, "feasible")] and not out.exists()
    demo.main([*args, "1-feasible"], out)
    assert sorted(p.name for p in out.iterdir()) == [
        "baseline.json",
        "baseline.mp4",
        "gated.json",
        "gated.mp4",
    ]
    assert from_json((out / "baseline.json").read_text(), EpisodeLog).outcome == "false_act"
    assert from_json((out / "gated.json").read_text(), EpisodeLog).outcome == "success"
    assert (out / "gated.mp4").read_bytes()[4:8] == b"ftyp"  # an MP4 container
