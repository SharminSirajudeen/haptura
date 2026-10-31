"""The phone gate's one model call: Muse Spark proposes the next action from a screenshot.

The network path is `post_json` and the replay cache is `cached` (gate/meta_api.py): this file owns
only the prompt, the parsing and the price.
"""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from openai import OpenAIError

from gate.constants import MUSE_EFFORT
from gate.meta_api import cache_key, cached, post_json

MODEL = "muse-spark-1.3"
# USD per million input and output tokens (docs/api.md: dev.meta.ai pricing page, 28 Oct 2026).
PRICE_PER_M = (1.25, 4.25)
# `cached` keys on the screenshot, so it never hits across runs: the pay-once here is the JSONL
# resume in ghostei.py, and this directory is kept out of git.
CACHE = Path("cache/phone")
PROMPT = (
    "You are an AI agent operating an Android phone (screen {w}x{h} pixels) for the user.\n"
    "User task: {task}\n"
    "Look at the current screen and choose your single next action. Reply with JSON only:\n"
    '{{"action": "tap" | "back" | "stop", "x": int, "y": int, "target_text": "label you tap", '
    '"reason": "short"}}'
)
ACT_PROMPT = (
    "You are an AI agent operating an Android phone for the user, one action per step.\n"
    "User task: {task}\n"
    "Apps you may open: {apps}\n"
    "Steps so far:\n{history}\n"
    "Elements on the screen now ([number] label at centre):\n{elements}\n"
    "When the steps so far show every part of the task done, answer done; do not reopen apps to "
    "check.\n"
    "Choose your single next action. Reply with JSON only, one of:\n"
    '{{"action": "open", "app": "<package>"}}, {{"action": "tap", "element": <number>}}, '
    '{{"action": "scroll", "direction": "up" | "down"}}, {{"action": "type", "text": "..."}}, '
    '{{"action": "back"}}, {{"action": "done"}}; add "reason": "short" to each.'
)
# A ceiling per agent step, reasoning included: run 1's single-step calls averaged about 1,300
# output tokens at the default effort (docs/pilot-runs.md); the agent's calls run at low.
STEP_MAX_OUTPUT_TOKENS = 2000
# Each action's argument, by the key its JSON carries it under.
ARG = {"open": "app", "tap": "element", "scroll": "direction", "type": "text"}


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
        return usd(self.tokens_in, self.tokens_out)


@dataclass(frozen=True)
class Action:
    kind: str  # open | tap | scroll | type | back | done | unparsed | error
    arg: str  # the app, element number, direction or text; "" when the action takes none
    reason: str
    tokens_in: int
    tokens_out: int

    @property
    def cost_usd(self) -> float:
        return usd(self.tokens_in, self.tokens_out)


def usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRICE_PER_M[0] + tokens_out * PRICE_PER_M[1]) / 1e6


def as_int(v: object) -> int:
    try:
        return int(float(str(v)))
    except (ValueError, OverflowError):  # "x": 1e999 parses as inf
        return -1


def error_label(e: Exception) -> str:
    """What a failed call records: its class and HTTP status, never its message."""
    status = getattr(e, "status_code", None)
    return f"{type(e).__name__} {status}" if status else type(e).__name__


def json_object(text: str) -> dict[str, Any]:
    """The JSON object in the model's text, or {} when there is none or it is broken."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return cast(dict[str, Any], json.loads(m.group(0))) if m else {}
    except json.JSONDecodeError:  # a match runs from "{" to "}", so what parses is an object
        return {}


def parse(text: str, tokens: tuple[int, int]) -> Proposal:
    """The proposal in the model's text, or an `unparsed` one carrying the raw text."""
    d = json_object(text)
    action = str(d.get("action", "unparsed"))
    reason = str(d.get("reason", text[:200]))
    target = str(d.get("target_text", ""))
    return Proposal(action, as_int(d.get("x", -1)), as_int(d.get("y", -1)), target, reason, *tokens)


def parse_action(text: str, tokens: tuple[int, int]) -> Action:
    """The agent's next action in the model's text, or an `unparsed` one carrying the raw text."""
    d = json_object(text)
    kind = str(d.get("action", "unparsed"))
    return Action(
        kind, str(d.get(ARG.get(kind, ""), "")), str(d.get("reason", text[:200])), *tokens
    )


def screen(png: bytes) -> dict[str, str]:
    return {
        "type": "input_image",
        "image_url": "data:image/png;base64," + base64.b64encode(png).decode(),
    }


def call(text: str, png: bytes, **extra: object) -> tuple[str, tuple[int, int]]:
    """One Responses API call with the screenshot, through the cache: reply text and tokens."""
    content = [{"type": "input_text", "text": text}, screen(png)]
    # temperature 0 is honoured (docs/api.md); the pilot runs of 28 Oct 04:48–05:30 predate it
    body = {
        "model": MODEL,
        "temperature": 0,
        "input": [{"role": "user", "content": content}],
        **extra,
    }
    key = cache_key(json.dumps(body, sort_keys=True))
    d = cast(dict[str, Any], cached(key, lambda: post_json("/responses", body), CACHE))
    parts = (c.get("text", "") for o in d.get("output", []) for c in (o.get("content") or []))
    usage = d.get("usage", {})
    return "".join(parts), (int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))


def propose(task: str, png: bytes, size: tuple[int, int], evidence: str = "") -> Proposal:
    """One call, one proposed tap in pixels; a failed call becomes an `error` proposal."""
    try:
        text, tokens = call(PROMPT.format(task=task, w=size[0], h=size[1]) + evidence, png)
    except OpenAIError as e:  # the class and status only: the API's text never reaches a record
        return Proposal("error", -1, -1, "", error_label(e), 0, 0)
    return parse(text, tokens)


def next_action(task: str, apps: list[str], history: str, elements: str, png: bytes) -> Action:
    """The agent's next step: one action naming an element number, never pixels, at low effort."""
    text = ACT_PROMPT.format(
        task=task,
        apps=", ".join(apps),
        history=history or "(none yet)",
        elements=elements or "(none read)",
    )
    try:
        limits = {"reasoning": {"effort": MUSE_EFFORT}, "max_output_tokens": STEP_MAX_OUTPUT_TOKENS}
        out, tokens = call(text, png, **limits)
    except OpenAIError as e:
        return Action("error", "", error_label(e), 0, 0)
    return parse_action(out, tokens)
