"""The Meta Model API: S5 `post_json`, S6 `cached`, S7 `sam_track`, S8 `muse_turn`.

S5 is the only network function. Everything rides the official SDK's generic `post`, so its
retries on 429 and 503 and its server-sent-event parsing come free. The key is read from
`META_API_KEY` and never logged. Every paid call goes through the cache, so `REPLAY=1` reruns an
evaluation offline and deterministically.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
from openai import OpenAI, Stream

from gate.constants import MUSE_EFFORT, MUSE_MAX_OUTPUT_TOKENS
from gate.types import Frames, Tracks
from gate.video import encode_mp4

BASE_URL = "https://api.meta.ai/v1"
SAM_MODEL = "sam-3.1"
MUSE_MODEL = "muse-spark-1.3"
CACHE_DIR = Path("cache")
# A SAM output line: a frame marker, then comma-separated records of `id<|box;...|><|mask;...|>`.
FRAME = re.compile(r"^<(\d+)f>")
BOX = re.compile(
    r"(\d+)<\|box;x1=(-?\d+);y1=(-?\d+);x2=(-?\d+);y2=(-?\d+);w=\d+;h=\d+(?:;c=[\d.]+)?\|>"
)


def post_json(
    path: str, body: dict[str, Any], *, stream: bool = False, http: httpx.Client | None = None
) -> dict[str, Any] | Iterator[dict[str, Any]]:
    """S5: POST `body` to `path` under the Meta base URL.

    Returns the parsed JSON object, or with `stream=True` an iterator of the parsed `data:`
    events in order, ending at `[DONE]`. `http` lets a test substitute a transport.
    """
    client = OpenAI(api_key=os.environ["META_API_KEY"], base_url=BASE_URL, http_client=http)
    if not stream:
        return cast(dict[str, Any], client.post(path, cast_to=object, body=body))
    events = client.post(path, cast_to=object, body=body, stream=True, stream_cls=Stream[object])
    return (cast(dict[str, Any], e) for e in events)


def cache_key(*parts: str | bytes) -> str:
    """The sha256 of the parts, each length-prefixed so no two part lists collide."""
    h = hashlib.sha256()
    for p in parts:
        b = p.encode() if isinstance(p, str) else p
        h.update(f"{len(b)}:".encode())
        h.update(b)
    return h.hexdigest()


def cached(key: str, fn: Callable[[], Any], root: Path = CACHE_DIR) -> Any:
    """S6: the value stored for `key`, else `fn()` stored under it; under REPLAY=1 a miss errors."""
    path = root / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    if os.environ.get("REPLAY") == "1":
        raise LookupError(f"REPLAY=1 and no cached response for {key}")
    value = fn()
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def sam_track(
    frames: Frames, prompt: str, *, root: Path = CACHE_DIR, http: httpx.Client | None = None
) -> Tracks:
    """S7: SAM 3.1 tracks for `prompt` over the clip: box centres per frame, NaN where absent."""
    key = cache_key(SAM_MODEL, prompt, str(frames.shape), frames.tobytes())
    lines = cached(key, lambda: _sam_lines(frames, prompt, http), root)
    return parse_tracks(lines, frames.shape[0])


def _sam_lines(frames: Frames, prompt: str, http: httpx.Client | None) -> list[str]:
    url = "data:video/mp4;base64," + base64.b64encode(encode_mp4(frames)).decode()
    content = [{"type": "input_text", "text": prompt}, {"type": "input_video", "video_url": url}]
    body = {
        "model": SAM_MODEL,
        "stream": True,
        "metadata": {"mask_encoding": "one_bit", "include_confidence": "true"},
        "input": [{"type": "message", "role": "user", "content": content}],
    }
    events = cast(Iterator[dict[str, Any]], post_json("/responses", body, stream=True, http=http))
    return [e["delta"] for e in events if e.get("type") == "response.output_text.delta"]


def parse_tracks(lines: list[str], n_frames: int) -> Tracks:
    """One line per frame with a match; the frame index is the `<Nf>` marker, never the position."""
    tracks: Tracks = {}
    for line in lines:
        marker = FRAME.match(line)
        if marker is None:
            raise ValueError(f"SAM line without a frame marker: {line[:60]!r}")
        frame = int(marker.group(1))
        for oid, x1, y1, x2, y2 in BOX.findall(line):
            track = tracks.setdefault(int(oid), np.full((n_frames, 2), np.nan))
            track[frame] = ((int(x1) + int(x2)) / 2, (int(y1) + int(y2)) / 2)
    return tracks


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass(frozen=True)
class MuseReply:
    text: str
    tool_calls: tuple[ToolCall, ...]
    response_id: str
    usage: dict[str, Any]


def muse_turn(
    instructions: str,
    input: str | list[dict[str, Any]],
    tools: list[dict[str, Any]],
    previous_response_id: str | None = None,
    *,
    root: Path = CACHE_DIR,
    http: httpx.Client | None = None,
) -> MuseReply:
    """S8: one Muse Spark turn on the Responses API, temperature 0, the lowest reasoning effort."""
    body: dict[str, Any] = {
        "model": MUSE_MODEL,
        "instructions": instructions,
        "input": input,
        "tools": tools,
        "temperature": 0,
        "reasoning": {"effort": MUSE_EFFORT},
        "max_output_tokens": MUSE_MAX_OUTPUT_TOKENS,
    }
    if previous_response_id is not None:
        body["previous_response_id"] = previous_response_id
    key = cache_key(json.dumps(body, sort_keys=True))
    raw = cached(key, lambda: post_json("/responses", body, http=http), root)
    return _reply(raw)


def _arguments(text: str) -> dict[str, Any]:
    """A tool call's JSON arguments; {} when they do not parse (cut off at max_output_tokens), which
    the agent loop answers as bad arguments. A cached reply that crashed would crash every rerun."""
    try:
        args = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _reply(raw: dict[str, Any]) -> MuseReply:
    output = raw["output"]
    text = "".join(
        c["text"]
        for o in output
        if o["type"] == "message"
        for c in o["content"]
        if c["type"] == "output_text"
    )
    calls = tuple(
        ToolCall(o["name"], _arguments(o["arguments"]), o["call_id"])
        for o in output
        if o["type"] == "function_call"
    )
    return MuseReply(text, calls, raw["id"], raw["usage"])
