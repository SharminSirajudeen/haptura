"""The agent loop and the executor.

Muse Spark makes every act, probe or decline call through three tools; the executor runs the world
and every number. One flag separates the conditions: `gated=True` puts `check_act` before `act`,
`diagnose` after each act block and the advice line under each table; `gated=False` (baseline a)
removes those three and the table's p0 and label columns, as EVAL.md defines baseline a. The world
(`run_block`), the diagnosis (`diagnose`) and the model (`muse_turn`) are arguments:
production passes `gate.episode.run_block`, `gate.gate.diagnose` and `gate.meta_api.muse_turn`,
and the tests pass fakes.

The agent never sees ground truth: ids are carried across blocks from tracked positions
(`match_ids`), and `_controls` is the only reader of the arena's binding and true positions; its
answer sets the outcome and nothing else.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from gate.arena import ACTIONS, Arena
from gate.constants import (
    BLOCK_BUDGET,
    BLOCK_STEPS,
    EFFECT_MIN,
    MAX_FRAMES,
    MAX_LAG,
    MAX_MUSE_CALLS,
    P_NOOP,
    PROBE_STEPS,
)
from gate.control import control_scores, design_block
from gate.episode import Tracker
from gate.gate import PROBE_SEED, _mine, centre, check_act, rule_policy
from gate.meta_api import MuseReply, ToolCall
from gate.trackers import _last, match_ids
from gate.types import (
    BlockRecord,
    Decision,
    Diagnosis,
    EpisodeLog,
    Evidence,
    Frames,
    Scenario,
    Tracks,
    Vec,
)

Body = Mapping[str, Vec | None]
Goal = tuple[float, float, float, float]
RunBlock = Callable[[Arena, Sequence[str], Tracker, bool, Path | None], tuple[Frames, Tracks]]
Diagnose = Callable[
    [Body, Sequence[str], Tracks, int, tuple[Sequence[str], Tracks] | None], Diagnosis
]
MuseTurn = Callable[[str, str | list[dict[str, Any]], list[dict[str, Any]], str | None], MuseReply]

DIRS = ACTIONS[1:]  # up, down, left, right
DESIGN_STREAM = 3  # the arena draws from streams 1 and 2 of the seed; the agent's designs from this
SEED_STRIDE = MAX_FRAMES  # above the blocks one episode can run (each takes at least two frames),
# so the control test's seed `scenario.seed * SEED_STRIDE + block index` never repeats
USAGE = ("muse_calls", "input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens")
NUDGE = "Call one of the three tools."

PROMPT = (
    "You control one element in a 2D world through the actions noop, up, down, left and right, "
    "but you do not know which element, and your actions may be mirrored, rotated or dead. Other "
    "elements may copy your actions late, replay old motion or look like yours, and control or "
    "your body may change during the task. Goal: drive the element you control into the goal "
    "box, or decline when it cannot get there. Each run_experiment is one block of random "
    "actions; it returns one line per element with its position and the measured effect of each "
    "action, and may also show p0 (how likely an effect this large is by chance; small means it "
    "follows your actions), a label (mine, echo, not_me) and an advice line from a rule policy. "
    "Follow "
    "the advice unless the evidence says otherwise. Experiments cost money: act or decline as "
    "soon as the evidence is clear. Call one tool per turn."
)
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "run_experiment",
        "description": f"Run one block of at most {BLOCK_STEPS} random actions, a share p_noop of "
        "them no-ops and the rest spread over dirs; returns the evidence table.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "minimum": 1, "maximum": BLOCK_STEPS},
                "p_noop": {"type": "number", "minimum": 0, "maximum": 1},
                "dirs": {"type": "array", "items": {"type": "string", "enum": list(DIRS)}},
            },
            "required": ["n", "p_noop", "dirs"],
        },
    },
    {
        "type": "function",
        "name": "act",
        "description": "Steer object_id into the goal; it may be refused, or stopped with a "
        "diagnosis.",
        "parameters": {
            "type": "object",
            "properties": {"object_id": {"type": "integer"}},
            "required": ["object_id"],
        },
    },
    {
        "type": "function",
        "name": "decline",
        "description": "Stop because the goal cannot be reached; say why.",
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


@dataclass
class _Run:
    """One episode's state. `reference` is each id's last tracked position: `match_ids`' reference
    for the next block, and the only positions the agent knows."""

    arena: Arena
    tracker: Tracker
    gated: bool
    clips: Path | None
    run_block: RunBlock
    diagnose: Diagnose
    rng: np.random.Generator
    reference: dict[int, Vec] = field(default_factory=dict)
    pool: list[tuple[tuple[str, ...], Tracks]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    blocks: list[BlockRecord] = field(default_factory=list)
    looks: int = 0
    frames: int = 0
    steps: int = 0
    outcome: str | None = None


def run_episode(
    arena: Arena,
    tracker: Tracker,
    condition: str,
    gated: bool,
    *,
    clips: Path | None,
    run_block: RunBlock,
    diagnose: Diagnose,
    muse_turn: MuseTurn,
) -> EpisodeLog:
    """`muse_turn` turns until an act reaches the goal, a decline, a false act, MAX_MUSE_CALLS or
    MAX_FRAMES; the conversation is carried by `previous_response_id`. Block k's clip is saved as
    `clips/kk.mp4` when `clips` is set."""
    scenario: Scenario = arena.scenario
    rng = np.random.default_rng([scenario.seed, DESIGN_STREAM])
    run = _Run(arena, tracker, gated, clips, run_block, diagnose, rng)
    usage = dict.fromkeys(USAGE, 0)
    given: str | list[dict[str, Any]] = _task(scenario.goal)
    previous: str | None = None
    for _ in range(MAX_MUSE_CALLS):
        reply = muse_turn(PROMPT, given, TOOLS, previous)
        _add_usage(usage, reply.usage)
        previous = reply.response_id
        given = _answer(run, reply)
        if run.outcome is not None:
            break
    usage |= {"frames": run.frames, "sam_calls": len(run.blocks)}
    outcome = run.outcome or "timeout"
    return EpisodeLog(scenario, condition, tuple(run.blocks), outcome, {}, usage)


def _task(goal: Goal) -> str:
    x0, y0, x1, y1 = goal
    return f"The goal box spans x {x0:.0f} to {x1:.0f} and y {y0:.0f} to {y1:.0f}."


def _add_usage(total: dict[str, int], usage: Mapping[str, Any]) -> None:
    """`muse_turn`'s usage, in the shape the API returned (results/api/muse-2-follow-up.json)."""
    total["muse_calls"] += 1
    total["input_tokens"] += usage.get("input_tokens", 0)
    total["output_tokens"] += usage.get("output_tokens", 0)
    total["cached_tokens"] += usage.get("input_tokens_details", {}).get("cached_tokens", 0)
    total["reasoning_tokens"] += usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)


def _answer(run: _Run, reply: MuseReply) -> str | list[dict[str, Any]]:
    """Each tool call's output in order, until one ends the episode; a reply with none is nudged."""
    if not reply.tool_calls:
        return NUDGE
    outputs: list[dict[str, Any]] = []
    for call in reply.tool_calls:
        said = reply.text or f"{call.name} {json.dumps(call.arguments)}"
        output = _tool(run, call, said)
        outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": output})
        if run.outcome is not None:
            break
    return outputs


def _tool(run: _Run, call: ToolCall, said: str) -> str:
    """The three tools; model arguments are checked here, and a bad one is answered, not raised."""
    args = call.arguments
    if call.name == "run_experiment":
        return _experiment(run, args, said)
    if call.name == "act":
        return _act(run, args.get("object_id"), said)
    if call.name == "decline":
        _decide(run, Decision("decline", None, str(args.get("reason", ""))))
        run.outcome = "decline"
        return ""
    return f"unknown tool {call.name}; call run_experiment, act or decline"


def _decide(run: _Run, decision: Decision) -> None:
    """Log Muse's first call after a block that handed control back to it (a probe-phase block)."""
    if run.blocks and run.blocks[-1].phase == "probe" and run.blocks[-1].decision is None:
        run.blocks[-1] = replace(run.blocks[-1], decision=decision)


def _experiment(run: _Run, args: Mapping[str, Any], said: str) -> str:
    """One block designed by `design_block`, run, re-keyed by `match_ids`; the control test on the
    pool, then the table."""
    parsed = _parse(args)
    if parsed is None:
        return f"bad arguments: n is 1..{BLOCK_STEPS}, p_noop is 0..1, dirs lists {', '.join(DIRS)}"
    n, p_noop, dirs = parsed
    _decide(run, Decision("probe", None, said))
    actions = design_block(run.rng, min(n, BLOCK_STEPS), p_noop, dirs)
    tracks = _block(run, actions, "probe")
    if tracks is None:
        return ""
    run.pool.append((actions, tracks))
    seed = run.arena.scenario.seed * SEED_STRIDE + len(run.blocks) - 1
    evidence = _look(run, *_pool(run.pool), seed)
    advice = _advice(run, evidence) if run.gated else None
    run.blocks[-1] = replace(run.blocks[-1], evidence=tuple(evidence), advice=advice)
    clamped = f"n clamped to {BLOCK_STEPS}\n" if n > BLOCK_STEPS else ""
    return clamped + _table(run, advice)


def _parse(args: Mapping[str, Any]) -> tuple[int, float, list[str]] | None:
    """run_experiment's arguments, or None when any is malformed."""
    n, p_noop, dirs = args.get("n"), args.get("p_noop"), args.get("dirs")
    if not (isinstance(n, int) and isinstance(p_noop, (int, float)) and isinstance(dirs, list)):
        return None
    if n < 1 or not 0 <= p_noop <= 1 or not dirs or not set(dirs) <= set(DIRS):
        return None
    return n, float(p_noop), dirs


def _block(run: _Run, actions: tuple[str, ...], phase: str) -> Tracks | None:
    """Runs the block if it fits MAX_FRAMES; `match_ids` re-keys its ids to the ones carried."""
    if run.frames + len(actions) + 1 > MAX_FRAMES:
        run.outcome = "timeout"
        return None
    clip = None if run.clips is None else run.clips / f"{len(run.blocks):02d}.mp4"
    _, raw = run.run_block(run.arena, actions, run.tracker, phase == "act", clip)
    ids = match_ids(raw, run.reference)
    tracks = {ids[i]: pos for i, pos in raw.items()}
    for i, pos in tracks.items():
        last = _last(pos)
        if last is not None:
            run.reference[i] = last
    path = "" if clip is None else str(clip)
    run.blocks.append(BlockRecord(run.steps, phase, actions, path, tracks, (), None, None, None))
    run.frames += len(actions) + 1
    run.steps += len(actions)
    return tracks


def _pool(blocks: Sequence[tuple[tuple[str, ...], Tracks]]) -> tuple[tuple[str, ...], Tracks]:
    """The blocks since the last diagnosis as one: frame 0 of each later block is the last frame of
    the one before, so it is kept once; an id a block lacks is NaN there."""
    actions = tuple(a for acts, _ in blocks for a in acts)
    ids = sorted({i for _, tracks in blocks for i in tracks})
    gaps = [np.full((len(acts) + 1, 2), np.nan) for acts, _ in blocks]
    tracks: Tracks = {
        i: np.vstack([t.get(i, g)[min(k, 1) :] for k, ((_, t), g) in enumerate(zip(blocks, gaps))])
        for i in ids
    }
    return actions, tracks


def _look(run: _Run, actions: Sequence[str], tracks: Tracks, seed: int) -> list[Evidence]:
    """The control test, one look more: the evidence every later table, `check_act` and the rule
    policy read."""
    run.looks += 1
    run.evidence = control_scores(actions, tracks, MAX_LAG, seed)
    return run.evidence


def _advice(run: _Run, evidence: list[Evidence]) -> Decision:
    """The rule policy's verdict on the pooled evidence, shown to Muse as advice."""
    goal = run.arena.scenario.goal
    mine = _mine(evidence)
    # the rule policy reads target_pos only when exactly one element is mine
    pos = run.reference[mine[0].object_id] if len(mine) == 1 else centre(goal)
    return rule_policy(evidence, run.looks, BLOCK_BUDGET, pos, goal)


def _table(run: _Run, advice: Decision | None) -> str:
    """The evidence table: one rounded line per element; ungated it has no p0, label or advice."""
    cx, cy = centre(run.arena.scenario.goal)
    steps = sum(len(acts) for acts, _ in run.pool)
    head = f"goal centre ({cx:.0f},{cy:.0f}); look {run.looks} of {BLOCK_BUDGET}; {steps} steps"
    cols = "id (x,y)" + (" p0 label" if run.gated else "") + " " + " ".join(DIRS)
    rows = [_row(e, run.reference[e.object_id], run.gated) for e in run.evidence]
    tail = [] if advice is None else [_say(advice)]
    return "\n".join([head, cols, *rows, *tail])


def _row(e: Evidence, pos: Vec, gated: bool) -> str:
    test = f" {e.p0:.2g} {e.label}" if gated else ""
    effects = " ".join(
        "?" if v is None else f"{v[0]:.1f},{v[1]:.1f}" for v in map(e.body.get, DIRS)
    )
    return f"{e.object_id} ({pos[0]:.0f},{pos[1]:.0f}){test} {effects}"


def _say(advice: Decision) -> str:
    target = "" if advice.object_id is None else f" {advice.object_id}"
    return f"advice: {advice.kind}{target}: {advice.reason}"


# what _say writes
ADVICE = re.compile(r"^advice: (act|probe|decline)(?: (\d+))?: (.*)$", re.M | re.ASCII)
RULES_PROBE = {"n": BLOCK_STEPS, "p_noop": P_NOOP, "dirs": list(DIRS)}  # EVAL.md's rules-only row


def rules_turn(
    instructions: str, given: str | list[dict[str, Any]], tools: Any, previous: str | None
) -> MuseReply:
    """The rules-only condition: the rule policy decides, through the same loop and tools as Muse
    (a MuseTurn).

    Each turn answers with the tool call the latest advice line names; with no advice yet, after
    a refusal, or on advice to probe, it runs one full block over every direction.
    """
    said = given if isinstance(given, str) else "\n".join(str(o.get("output", "")) for o in given)
    kind, target, reason = (ADVICE.findall(said) or [("probe", "", "")])[-1]
    if kind == "act":
        call = ToolCall("act", {"object_id": int(target)}, "rules")
    elif kind == "decline":
        call = ToolCall("decline", {"reason": reason}, "rules")
    else:
        call = ToolCall("run_experiment", dict(RULES_PROBE), "rules")
    return MuseReply(reason or "no advice yet", (call,), "", {})


def _act(run: _Run, object_id: Any, said: str) -> str:
    """`check_act` first when gated; a refusal goes back to Muse with its reason."""
    if not isinstance(object_id, int) or object_id not in run.reference:
        return f"unknown object {object_id}; act on an id from the table"
    decision = check_act(run.evidence, object_id) if run.gated else Decision("act", object_id, said)
    _decide(run, decision)
    if decision.kind == "refused":
        return f"refused: {decision.reason}"
    return _act_phase(run, object_id)


def _act_phase(run: _Run, target: int) -> str:
    """Act blocks steered by the target's measured body until the goal, a false act, a timeout or a
    stale block, whose diagnostic probe goes back to Muse. The act is judged before every block,
    and once more after the last: a target the arena does not bind is a false act, and one already
    in the goal is a success, so a commitment to an element with no live action still counts and
    a target the rule policy found inside the goal is not steered out of it."""
    body = next((e.body for e in run.evidence if e.object_id == target), {})
    live, goal = _live(body), run.arena.scenario.goal
    while run.outcome is None:
        if not _controls(run, target):
            run.outcome = "false_act"
        elif _in_goal(run.reference[target], goal):
            run.outcome = "success"
        elif not live:
            return f"object {target} has no live action to steer with"
        elif _act_block(run, target, body, live) == "stale":
            if not _in_goal(run.reference[target], goal):
                return _probe(run, target, body)
    return ""


def _act_block(run: _Run, target: int, body: Body, live: Mapping[str, Vec]) -> str:
    """One act block, then `diagnose` when gated; the eyes fix is applied here, without a Muse turn,
    so the act is judged on the corrected ids. Returns the diagnosis kind ('' when ungated)."""
    actions = _steer(live, run.reference[target], centre(run.arena.scenario.goal))
    tracks = _block(run, actions, "act")
    if tracks is None:
        return ""
    found = run.diagnose(body, actions, tracks, target, None) if run.gated else None
    if found is not None:
        if found.swap is not None:
            a, b = found.swap
            run.reference[a], run.reference[b] = run.reference[b], run.reference[a]
        run.blocks[-1] = replace(run.blocks[-1], diagnosis=found)
    return "" if found is None else found.kind


def _probe(run: _Run, target: int, body: Body) -> str:
    """The diagnostic probe after a stale block, 3 of each action; `diagnose` on it decides, and its
    fix reaches Muse as advice under the probe's own evidence, since the pool restarts here."""
    stale = run.blocks[-1]
    actions = design_block(run.rng, PROBE_STEPS, 1 / (len(DIRS) + 1), DIRS)
    tracks = _block(run, actions, "probe")
    if tracks is None:
        return ""
    found = run.diagnose(body, stale.actions, stale.tracks, target, (actions, tracks))
    run.pool = [(actions, tracks)]
    # the very call `diagnose` just made on this probe, so the table and its verdict cannot disagree
    evidence = _look(run, actions, tracks, PROBE_SEED)
    if found.kind == "body_changed":
        advice = Decision("act", target, found.fix)
    else:
        advice = Decision("probe", None, found.fix)
    run.blocks[-1] = replace(
        run.blocks[-1], evidence=tuple(evidence), advice=advice, diagnosis=found
    )
    return f"{found.kind}: {found.fix}\n{_table(run, advice)}"


def _live(body: Body) -> dict[str, Vec]:
    """The measured actions that are alive: an effect of at least EFFECT_MIN."""
    return {a: v for a, v in body.items() if v is not None and math.hypot(*v) >= EFFECT_MIN}


def _steer(live: Mapping[str, Vec], start: Vec, aim: Vec) -> tuple[str, ...]:
    """BLOCK_STEPS actions, each the live one that takes the predicted position nearest the goal
    centre; ties go to the first in `live`'s order."""
    x, y = start
    out = []
    for _ in range(BLOCK_STEPS):
        a = min(live, key=lambda k: math.dist((x + live[k][0], y + live[k][1]), aim))
        x, y = x + live[a][0], y + live[a][1]
        out.append(a)
    return tuple(out)


def _controls(run: _Run, target: int) -> bool:
    """The one read of ground truth, for the outcome only: the true element nearest the target's
    tracked position must be the element the arena binds now. Two on one pixel, which a wall's
    clamp can hold there, are told apart one frame back at a time along the track that ends there:
    the one the eyes fix in this block handed the target to, else the target's own. A
    frame where that track is unseen is skipped, so a target unseen at the end is matched where it
    was last seen, against that frame's truth. A pair that shared every frame of the block is a
    tie, and a tie is not control."""
    arena, pos, last = run.arena, run.reference[target], run.blocks[-1]
    fix = last.diagnosis.swap if last.diagnosis else None
    own = fix[1 - fix.index(target)] if fix and target in fix else target
    order = sorted(last.tracks.items(), key=lambda it: it[0] != own)
    ends = [t for _, t in order if _last(t) == pos]
    near = set(arena.history[-1])
    for seen, frame in zip((ends[0] if ends else np.array([pos]))[::-1], reversed(arena.history)):
        if not np.isnan(seen).any():
            gap = {e: math.dist(seen, frame[e]) for e in near}
            near = {e for e in near if gap[e] == min(gap.values())}
        if len(near) == 1:
            break
    return near == {arena._at(arena.scenario.binding_schedule)}


def _in_goal(pos: Vec, goal: Goal) -> bool:
    return goal[0] <= pos[0] <= goal[2] and goal[1] <= pos[1] <= goal[3]
