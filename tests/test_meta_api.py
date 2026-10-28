"""S5 to S8 against a mock transport and the T2 recordings (notes/api/, replayed from fixtures)."""

import json
import math
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import pytest

from gate import meta_api
from gate.constants import FPS
from gate.meta_api import (
    ToolCall,
    cache_key,
    cached,
    muse_turn,
    parse_tracks,
    post_json,
    sam_track,
)
from gate.types import Frames
from gate.video import encode_mp4

FIXTURES = Path(__file__).parent / "fixtures"
EVENTS = ['{"object_id": 1, "frame_index": 0}', '{"object_id": 1, "frame_index": 1}', "[DONE]"]
SSE = "".join(f"data: {e}\n\n" for e in EVENTS)
SYSTEM = (
    "You control one actuator (noop, up, down, left, right) in a scene of moving shapes. "
    "You do not know which shape, if any, obeys you. Use run_experiment to measure, then act or "
    "decline. Call exactly one tool per turn."
)
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "run_experiment",
        "description": "Run a randomized block of actions and return the evidence table.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer"},
                "p_noop": {"type": "number"},
                "dirs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["n", "p_noop", "dirs"],
        },
    },
    {
        "type": "function",
        "name": "act",
        "description": "Steer the object with this id into the goal.",
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "integer"}},
            "required": ["object_id"],
        },
    },
    {
        "type": "function",
        "name": "decline",
        "description": "Stop: no element is under your control.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


def transport(seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if json.loads(request.content).get("stream"):
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=SSE)
        return httpx.Response(
            200, json={"id": "resp_1", "output": [], "usage": {"input_tokens": 3}}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("META_API_KEY", "test-key-0123")
    return "test-key-0123"


@pytest.fixture
def replay(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("REPLAY", "1")
    monkeypatch.delenv("META_API_KEY", raising=False)
    return FIXTURES / "cache"


def arena_frames() -> Frames:
    return cast(Frames, np.load(FIXTURES / "arena128_frames.npz")["frames"])


# S5
def test_posts_the_body_to_the_meta_url_with_the_key(key: str) -> None:
    seen: list[httpx.Request] = []
    out = post_json("/responses", {"model": "muse-spark-1.3", "input": "hi"}, http=transport(seen))
    assert out == {"id": "resp_1", "output": [], "usage": {"input_tokens": 3}}
    assert str(seen[0].url) == "https://api.meta.ai/v1/responses"
    assert seen[0].method == "POST"
    assert seen[0].headers["authorization"] == f"Bearer {key}"
    assert json.loads(seen[0].content) == {"model": "muse-spark-1.3", "input": "hi"}


def test_stream_yields_each_event_in_order_and_stops_at_done(key: str) -> None:
    events: Any = post_json(
        "/responses", {"model": "sam-3.1", "stream": True}, stream=True, http=transport([])
    )
    assert isinstance(events, Iterator)
    assert list(events) == [{"object_id": 1, "frame_index": 0}, {"object_id": 1, "frame_index": 1}]


def test_the_key_comes_from_meta_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "the wrong name")
    with pytest.raises(KeyError):
        post_json("/responses", {}, http=transport([]))


# S6
def test_cache_hit_returns_the_file_without_calling_fn(tmp_path: Path) -> None:
    (tmp_path / "k.json").write_text('{"a": 1}')
    assert cached("k", lambda: pytest.fail("fn called on a hit"), tmp_path) == {"a": 1}


def test_cache_miss_calls_fn_once_and_stores_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REPLAY", raising=False)
    calls: list[int] = []

    def fn() -> list[int]:
        calls.append(1)
        return [7]

    assert cached("k", fn, tmp_path) == [7]
    assert cached("k", fn, tmp_path) == [7]
    assert calls == [1]
    assert json.loads((tmp_path / "k.json").read_text()) == [7]


def test_replay_makes_a_miss_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPLAY", "1")
    with pytest.raises(LookupError):
        cached("missing", lambda: pytest.fail("fn called under REPLAY"), tmp_path)


def test_cache_key_separates_the_parts() -> None:
    assert cache_key("ab", "c") != cache_key("a", "bc")
    assert cache_key("x", b"\x00\x01") == cache_key("x", b"\x00\x01")


# S7
def test_sam_track_replays_the_recorded_red_objects(replay: Path) -> None:
    tracks = sam_track(arena_frames(), "red object", root=replay)
    assert set(tracks) == {0, 1}
    assert all(t.shape == (30, 2) and not np.isnan(t).any() for t in tracks.values())
    # hand-derived from the first recorded line: square x 104-111, y 60-67; circle x 16-24, y 60-68
    assert tuple(tracks[0][0]) == (107.5, 63.5)
    assert tuple(tracks[1][0]) == (20.0, 64.0)
    assert np.all(np.diff(tracks[0][:, 0]) <= 0)  # the square moves left on every frame
    assert np.all(
        np.diff(tracks[1][:, 0]) >= 0
    )  # the circle moves right on every frame, through the crossing


def test_parse_tracks_reads_the_frame_marker_and_leaves_nan_gaps() -> None:
    lines = [
        "<0f>0<|box;x1=0;y1=0;x2=4;y2=4;w=10;h=10;c=0.9|><|mask;x=0;y=0;data=4,4,!!abc|>\n",
        "<2f>0<|box;x1=2;y1=2;x2=6;y2=6;w=10;h=10|>,3<|box;x1=8;y1=8;x2=10;y2=10;w=10;h=10|>\n",
    ]
    tracks = parse_tracks(lines, 3)
    assert set(tracks) == {0, 3}
    assert tuple(tracks[0][0]) == (2.0, 2.0)
    assert math.isnan(tracks[0][1][0]) and math.isnan(tracks[0][1][1])
    assert tuple(tracks[0][2]) == (4.0, 4.0)
    assert tuple(tracks[3][2]) == (9.0, 9.0)
    assert np.isnan(tracks[3][:2]).all()


def test_parse_tracks_rejects_a_line_without_a_frame_marker() -> None:
    with pytest.raises(ValueError):
        parse_tracks(["0<|box;x1=0;y1=0;x2=4;y2=4;w=10;h=10|>"], 1)


# S8
def test_muse_turn_replays_the_recorded_first_turn(replay: Path) -> None:
    reply = muse_turn(SYSTEM, "Begin. There is no evidence yet.", TOOLS, root=replay)
    assert reply.response_id == "resp_6ae1445c34aeab2287d24f79"
    assert reply.tool_calls == (
        ToolCall(
            "run_experiment",
            {"dirs": ["up", "down", "left", "right"], "n": 40, "p_noop": 0.2},
            "call_9655343e-eb65-4256-ae30-94b08610a747",
        ),
    )
    assert reply.usage["output_tokens"] == 155
    assert reply.usage["output_tokens_details"]["reasoning_tokens"] == 41


def test_muse_turn_sends_the_follow_up_with_previous_response_id(key: str, tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = [{"type": "function_call_output", "call_id": "call_1", "output": "table"}]
    reply = muse_turn(SYSTEM, result, TOOLS, "resp_prev", root=tmp_path, http=transport(seen))
    body = json.loads(seen[0].content)
    assert body["previous_response_id"] == "resp_prev"
    assert body["input"] == result
    assert body["temperature"] == 0
    assert body["reasoning"] == {"effort": "low"}
    assert reply.tool_calls == ()
    assert reply.response_id == "resp_1"


# S4
def test_encode_mp4_gives_h264_at_the_frame_size_and_rate() -> None:
    mp4 = encode_mp4(arena_frames())
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,nb_read_frames,r_frame_rate",
            "-of",
            "csv=p=0",
            "-",
        ],
        input=mp4,
        capture_output=True,
        check=True,
    )
    assert probe.stdout.decode().strip() == f"h264,128,128,{FPS}/1,30"


def test_tool_arguments_that_do_not_parse_become_empty() -> None:
    # Muse cut off at max_output_tokens: the agent loop answers {} as bad arguments
    assert meta_api._arguments('{"object_id": 3') == {}
    assert meta_api._arguments("[1, 2]") == {}
    assert meta_api._arguments('{"object_id": 3}') == {"object_id": 3}
