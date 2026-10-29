"""The JSON round trip on a hand-written EpisodeLog.

Every contract type, a NaN gap, a mirrored body map and an unsampled action.
"""

import dataclasses
import math

import numpy as np

from gate import constants
from gate.types import (
    BlockRecord,
    Decision,
    Diagnosis,
    Element,
    EpisodeLog,
    Evidence,
    Scenario,
    Tracks,
    from_json,
    to_json,
)


def make_log() -> EpisodeLog:
    tracks: Tracks = {
        3: np.array([[10.0, 20.0], [math.nan, math.nan], [12.0, 20.0]]),
        5: np.array([[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]]),
    }
    scenario = Scenario(
        seed=7,
        elements=(
            Element(3, "circle", (220, 40, 40), "controlled", (10.0, 20.0)),
            Element(5, "square", (220, 40, 40), "decoy", (0.0, 0.0)),
        ),
        binding_schedule=((0, 3), (12, None)),
        action_maps=((0, {"up": (0.0, -2.0), "right": (-2.0, 0.0)}),),
        events=((12, "control_remap", "3 -> none"),),
        goal=(100.0, 100.0, 120.0, 120.0),
        case="remap_blocked",
    )
    evidence = Evidence(
        object_id=3,
        p0=0.0001,
        best_lag=2,
        p_best=0.4,
        effect=2.0,
        body={"up": (0.0, -2.0), "right": (-2.0, 0.0), "left": None},
        label="mine",
    )
    block = BlockRecord(
        step0=0,
        phase="act",
        actions=("right", "noop", "up"),
        clip_path="clips/7/0.mp4",
        tracks=tracks,
        evidence=(evidence,),
        advice=Decision("act", 3, "single mine"),
        decision=Decision("act", 3, "followed the advice"),
        diagnosis=Diagnosis("eyes_swapped", "ids 3 and 5 swapped at frame 14", (3, 5), None),
    )
    return EpisodeLog(
        scenario=scenario,
        condition="gated+sam",
        blocks=(block,),
        outcome="success",
        metrics={"blocks": 1.0},
        usage={"tokens": 310, "frames": 31},
    )


def without_tracks(log: EpisodeLog) -> EpisodeLog:
    blocks = tuple(dataclasses.replace(b, tracks={}) for b in log.blocks)
    return dataclasses.replace(log, blocks=blocks)


def test_round_trip_keeps_every_field_but_the_arrays() -> None:
    log = make_log()
    back = from_json(to_json(log), EpisodeLog)
    assert without_tracks(back) == without_tracks(log)


def test_arrays_round_trip_with_int_ids_and_nan_gaps() -> None:
    back = from_json(to_json(make_log()), EpisodeLog)
    tracks = back.blocks[0].tracks
    assert set(tracks) == {3, 5}
    assert np.array_equal(tracks[3], make_log().blocks[0].tracks[3], equal_nan=True)
    assert tracks[5].shape == (3, 2)
    assert tracks[5].dtype == np.float64


def test_nan_is_written_as_null() -> None:
    text = to_json(make_log())
    assert "NaN" not in text
    assert "[null, null]" in text


def test_mirrored_body_and_unsampled_action_survive() -> None:
    back = from_json(to_json(make_log()), EpisodeLog)
    assert back.scenario.action_maps[0][1]["right"] == (-2.0, 0.0)
    assert back.blocks[0].evidence[0].body["left"] is None
    assert back.blocks[0].diagnosis is not None
    assert back.blocks[0].diagnosis.swap == (3, 5)
    assert back.blocks[0].diagnosis.body is None


def test_alpha_act_is_computed_and_sits_above_the_permutation_floor() -> None:
    assert constants.ALPHA_ACT == 0.01 / (constants.ELEMENTS_MAX * constants.BLOCK_BUDGET)
    assert 1 / (constants.PERMS + 1) < constants.ALPHA_ACT < constants.ALPHA_PROBE
