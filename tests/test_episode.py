"""The block runner: block lengths, the shared frame, acting reaching the schedules, the truth
slice, the clip."""

import subprocess
from pathlib import Path

import numpy as np

from gate.arena import Arena, make_scenario
from gate.episode import join_blocks, run_block, truth_slice
from gate.trackers import colour_tracker, truth_tracker


def test_two_blocks_of_30_give_62_frames_and_a_61_frame_join() -> None:
    arena = Arena(make_scenario(0, "feasible"))
    a, _ = run_block(arena, ["noop"] * 30, colour_tracker, acting=False)
    b, _ = run_block(arena, ["right"] * 30, colour_tracker, acting=True)
    assert a.shape[0] + b.shape[0] == 62
    assert join_blocks([a, b]).shape[0] == 61
    assert np.array_equal(a[-1], b[0])  # the shared frame: block 2 opens on block 1's last frame


def test_acting_steps_reach_the_schedules() -> None:
    # schedules run on acting steps only: a probe block leaves the clock at 0, an act block of 30
    # advances it to 30, past the secret remap step make_scenario drew from [5, 25]
    scenario = make_scenario(3, "remap_blocked")
    arena = Arena(scenario)
    run_block(arena, ["noop"] * 30, colour_tracker, acting=False)
    assert arena.n_act == 0
    run_block(arena, ["right"] * 30, colour_tracker, acting=True)
    assert arena.n_act == 30 > scenario.binding_schedule[1][0]


def test_truth_slice_tracks_exactly_the_block_frames() -> None:
    arena = Arena(make_scenario(1, "feasible"))
    run_block(arena, ["noop"] * 10, colour_tracker, acting=False)
    clip, tracks = run_block(arena, ["right"] * 5, truth_slice(arena, truth_tracker), acting=True)
    assert clip.shape[0] == 6
    assert all(t.shape == (6, 2) for t in tracks.values())
    assert tuple(tracks[0][0]) == arena.history[10][0]  # the block's frame 0 is history frame 10


def test_the_clip_is_saved_with_one_frame_per_step(tmp_path: Path) -> None:
    arena = Arena(make_scenario(2, "feasible"))
    path = tmp_path / "clips" / "b0.mp4"
    run_block(arena, ["up"] * 12, colour_tracker, acting=True, clip_path=path)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    assert probe.stdout.strip() == "13"
