"""The phone lane's one model call: Muse Spark proposes the next action from a screenshot.

The network path is S5 `post_json` and the replay cache is S6 `cached` (gate/meta_api.py, plan §4d
P7): this file owns only the prompt, the parsing and the price.
"""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from openai import OpenAIError

from gate.meta_api import cache_key, cached, post_json

MODEL = "muse-spark-1.3"
# USD per million input and output tokens (notes/api.md: dev.meta.ai pricing page, 28 Oct 2026).
PRICE_PER_M = (1.25, 4.25)
# S6 keys on the screenshot, so it never hits across runs: this lane's pay-once is the JSONL
# resume in ghostei.py, and this directory is kept out of git (notes/mac-lane.md).
CACHE = Path("cache/phone")
PROMPT = (
    "You are an AI agent operating an Android phone (screen {w}x{h} pixels) for the user.\n"
    "User task: {task}\n"
    "Look at the current screen and choose your single next action. Reply with JSON only:\n"
    '{{"action": "tap" | "back" | "stop", "x": int, "y": int, "target_text": "label you tap", '
    '"reason": "short"}}'
)


@dataclass(frozen=True)
class Proposal:
    action: str  # tap | back | stop | unparsed | error
    x: int
    y: int
    target_text: str
    reason: str
    tokens_in: int
    tokens_out: int

    @property
    def cost_usd(self) -> float:
        return (self.tokens_in * PRICE_PER_M[0] + self.tokens_out * PRICE_PER_M[1]) / 1e6


def as_int(v: object) -> int:
    try:
        return int(float(str(v)))
    except ValueError:
        return -1


def parse(text: str, tokens: tuple[int, int]) -> Proposal:
    """The JSON object in the model's text, or an `unparsed` proposal carrying the raw text."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d: dict[str, Any] = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    action = str(d.get("action", "unparsed"))
    reason = str(d.get("reason", text[:200]))
    target = str(d.get("target_text", ""))
    return Proposal(action, as_int(d.get("x", -1)), as_int(d.get("y", -1)), target, reason, *tokens)


def propose(task: str, png: bytes, size: tuple[int, int], evidence: str = "") -> Proposal:
    """One Responses API call with the screenshot; a failed call becomes an `error` proposal."""
    image = "data:image/png;base64," + base64.b64encode(png).decode()
    text = PROMPT.format(task=task, w=size[0], h=size[1]) + evidence
    content = [
        {"type": "input_text", "text": text},
        {"type": "input_image", "image_url": image},
    ]
    # temperature 0 is honoured (notes/api.md); the G3 runs of 28 Oct 04:48–05:30 predate this line
    body = {"model": MODEL, "temperature": 0, "input": [{"role": "user", "content": content}]}
    key = cache_key(json.dumps(body, sort_keys=True))
    try:
        d = cast(dict[str, Any], cached(key, lambda: post_json("/responses", body), CACHE))
    except OpenAIError as e:
        return Proposal("error", -1, -1, "", str(e)[:200], 0, 0)
    parts = (c.get("text", "") for o in d.get("output", []) for c in (o.get("content") or []))
    usage = d.get("usage", {})
    tokens = (int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))
    return parse("".join(parts), tokens)
