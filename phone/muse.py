"""The phone lane's one network call: Muse Spark proposes the next action from a screenshot.

Reads META_API_KEY from the environment; the shell that starts the runner loads it from
~/.config/control-gate/meta.env. The key is never logged.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

MODEL = "muse-spark-1.3"
URL = "https://api.meta.ai/v1/responses"
# USD per million input and output tokens, from a third-party listing (plan §4c); T2 corrects it.
PRICE_PER_M = (1.25, 4.25)
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


def propose(task: str, png: bytes, size: tuple[int, int]) -> Proposal:
    """One Responses API call with the screenshot; a failed call becomes an `error` proposal."""
    image = "data:image/png;base64," + base64.b64encode(png).decode()
    content = [
        {"type": "input_text", "text": PROMPT.format(task=task, w=size[0], h=size[1])},
        {"type": "input_image", "image_url": image},
    ]
    body = {"model": MODEL, "input": [{"role": "user", "content": content}]}
    auth = "Bearer " + os.environ["META_API_KEY"]
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    req = urllib.request.Request(URL, json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
    except urllib.error.URLError as e:
        return Proposal("error", -1, -1, "", str(e)[:200], 0, 0)
    text = "".join(c.get("text", "") for o in d.get("output", []) for c in (o.get("content") or []))
    usage = d.get("usage", {})
    return parse(text, (int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))))
