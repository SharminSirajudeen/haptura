"""The contracts every lane imports (plan §2), plus S11, JSON in and out.

Frozen dataclasses with no domain logic. Steps in a scenario's schedules count from the agent's
first act step. Tracks are (x, y) pixels, origin top-left, NaN where the tracker lost the object;
JSON writes NaN as null and reads null back as NaN.
"""

from __future__ import annotations

import json
import math
import types
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

import numpy as np

Vec = tuple[float, float]
Array = np.ndarray[tuple[int, int], np.dtype[np.float64]]
"""A [T, 2] float array, spelled out: numpy's NDArray alias hides np.ndarray from get_origin."""
Tracks = dict[int, Array]
"""Object id to an array [T, 2] of centroids. The ids are the tracker's own; S9 maps them."""
Frames = np.ndarray[tuple[int, int, int, int], np.dtype[np.uint8]]
"""A clip: [T, H, W, 3] RGB, as S3 renders it and S4 encodes it."""


@dataclass(frozen=True)
class Element:
    id: int
    shape: str  # circle | square | triangle
    colour: tuple[int, int, int]
    kind: str  # controlled | decoy | echo | replay
    pos: Vec


@dataclass(frozen=True)
class Scenario:
    seed: int
    elements: tuple[Element, ...]
    binding_schedule: tuple[
        tuple[int, int | None], ...
    ]  # (step, element id or None): who obeys from that step
    action_maps: tuple[
        tuple[int, Mapping[str, Vec]], ...
    ]  # (step, action to (dx, dy)): the body from that step
    events: tuple[
        tuple[int, str, str], ...
    ]  # (step, kind, detail): the ground truth the eval scores against
    goal: tuple[float, float, float, float]  # x0, y0, x1, y1
    case: str  # feasible | blocked | remap_feasible | remap_blocked | body_remap | body_blocked


@dataclass(frozen=True)
class Evidence:
    object_id: int
    p0: float  # the lag-0 permutation p
    best_lag: int  # the most significant lag of 1..MAX_LAG
    p_best: float
    effect: float  # the largest measured effect over actions at lag 0
    body: Mapping[
        str, Vec | None
    ]  # measured effect vector per action; None where the action had no samples
    label: str  # mine | echo | not_me


@dataclass(frozen=True)
class Decision:
    kind: str  # act | probe | decline | refused
    object_id: int | None
    reason: str


@dataclass(frozen=True)
class Diagnosis:
    kind: str  # ok | eyes_swapped | stale | body_changed | target_lost
    fix: str  # the reason, as shown to Muse
    swap: tuple[int, int] | None  # the two tracker ids to swap back, for eyes_swapped
    body: Mapping[str, Vec | None] | None  # the re-learned body map, for body_changed


@dataclass(frozen=True)
class BlockRecord:
    step0: int
    phase: str  # probe | act
    actions: tuple[str, ...]
    clip_path: str
    tracks: Tracks
    evidence: tuple[Evidence, ...]
    advice: Decision | None  # the S15 or S14 line shown to Muse; None in baseline a
    decision: Decision | None  # Muse's call after this block
    diagnosis: Diagnosis | None  # S14's result; a diagnostic probe's verdict; None in experiments


@dataclass(frozen=True)
class EpisodeLog:
    scenario: Scenario
    condition: str
    blocks: tuple[BlockRecord, ...]
    outcome: str  # success | decline | false_act | timeout
    metrics: Mapping[str, float]
    usage: Mapping[str, int]  # tokens and frames


T = TypeVar("T")


def to_json(obj: object) -> str:
    """S11: a dataclass to JSON. Arrays become lists, NaN becomes null, any other NaN errors."""
    return json.dumps(_encode(obj), allow_nan=False)


def from_json(text: str, cls: type[T]) -> T:
    """S11: JSON back to `cls`, guided by its field types. A null inside an array becomes NaN."""
    return cast(T, _decode(json.loads(text), cls))


def _encode(v: object) -> object:
    if is_dataclass(v) and not isinstance(v, type):
        return {f.name: _encode(getattr(v, f.name)) for f in fields(v)}
    if isinstance(v, np.ndarray):
        return [[None if math.isnan(x) else x for x in row] for row in v.tolist()]
    if isinstance(v, Mapping):
        return {str(k): _encode(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_encode(x) for x in v]
    return v


def _decode(v: Any, t: Any) -> Any:
    origin = get_origin(t) or t
    if is_dataclass(t) and isinstance(t, type):
        hints = get_type_hints(t)
        return t(**{f.name: _decode(v[f.name], hints[f.name]) for f in fields(t)})
    if origin in (types.UnionType, Union):
        inner = [a for a in get_args(t) if a is not type(None)]
        return None if v is None else _decode(v, inner[0])
    if origin is np.ndarray:
        rows = [[np.nan if x is None else x for x in row] for row in v]
        return np.array(rows, dtype=np.float64).reshape(-1, 2)
    if origin in (dict, Mapping):
        kt, vt = get_args(t)
        return {_decode(k, kt): _decode(x, vt) for k, x in v.items()}
    if origin is tuple:
        return _decode_tuple(v, get_args(t))
    return t(v) if t in (int, float) else v


def _decode_tuple(v: Any, args: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(args) == 2 and args[1] is Ellipsis:
        return tuple(_decode(x, args[0]) for x in v)
    return tuple(_decode(x, a) for x, a in zip(v, args, strict=True))
