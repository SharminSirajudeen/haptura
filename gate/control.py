"""S10 `control_scores` and S12 `design_block`: the control statistic and the block designer.

S10 is the one test behind every number the gate shows (plan §3, "S10, exactly"): for each
object and each lag 0..max_lag, a permutation test of whether the object's displacement depends
on the action taken that many steps earlier, and the body map that falls out of the same group
means. It assumes nothing about what an action does, so a mirrored, rotated or dead action needs
no special case. Frame t+1 follows action t, so `tracks[i]` has `len(actions) + 1` frames.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from gate.constants import ALPHA_ACT, EFFECT_MIN, PERMS
from gate.types import Array, Evidence, Tracks, Vec

NOOP = "noop"
Floats = NDArray[np.float64]
Bools = NDArray[np.bool_]
Ints = NDArray[np.int64]


def control_scores(
    actions: Sequence[str], tracks: Tracks, max_lag: int, seed: int
) -> list[Evidence]:
    """S10: one Evidence per object of `tracks`, in its order, from one rng seeded with `seed`."""
    names = sorted(set(actions) | {NOOP})
    labels = np.array([names.index(a) for a in actions])
    rng = np.random.default_rng(seed)
    return [_evidence(oid, labels, names, pos, max_lag, rng) for oid, pos in tracks.items()]


def _evidence(
    oid: int, labels: Ints, names: list[str], pos: Array, max_lag: int, rng: np.random.Generator
) -> Evidence:
    """Steps 1 and 5–6 of the plan: the kept steps, then the label from p_0, p_best and the body.
    A step at a wall is kept as the motion the clamp left (#24): an element pressed to a wall is
    mine through its moves along it, and a push into the wall reads as the nothing it does."""
    d = pos[1:] - pos[:-1]
    ok = ~np.isnan(d).any(axis=1)
    lags = [_lag(labels, d, ok, k, len(names), rng) for k in range(max_lag + 1)]
    p = [lag[0] for lag in lags]
    body = _body(names, lags[0][1])
    effect = max((float(np.hypot(*v)) for v in body.values() if v is not None), default=0.0)
    best = 1 + int(np.argmin(p[1:]))  # argmin takes the first minimum: ties go to the smaller k
    if p[0] < ALPHA_ACT and effect >= EFFECT_MIN:
        label = "mine"
    elif p[best] < ALPHA_ACT:
        label = "echo"
    else:
        label = "not_me"
    return Evidence(oid, p[0], best, p[best], effect, body, label)


def _lag(
    labels: Ints, d: Floats, ok: Bools, k: int, n_actions: int, rng: np.random.Generator
) -> tuple[float, Floats]:
    """Steps 2–4 at lag k: p_k, and the observed group means m_{a,k} (NaN where a has no sample).

    Row 0 of `rows` is the observed labelling and the other PERMS rows its shuffles, so every S
    comes from the same arithmetic. Each row's labels carry its row offset, so one bincount over
    the whole matrix gives every row's group sums; no BLAS, whose speed varies tenfold on a
    shared host. A shuffle keeps the group counts, so an action with no sample is empty in every
    row and adds nothing to any S.
    """
    keep = ok[k:]
    lab, disp = labels[: len(labels) - k][keep], d[k:][keep]
    rows = np.empty((PERMS + 1, len(lab)), dtype=np.int64)
    rows[:] = lab
    rows += n_actions * np.arange(PERMS + 1)[:, None]
    rng.permuted(rows[1:], axis=1, out=rows[1:])
    cell, size = rows.ravel(), (PERMS + 1) * n_actions
    sums = np.stack([np.bincount(cell, np.tile(disp[:, j], PERMS + 1), size) for j in (0, 1)])
    counts = np.bincount(lab, minlength=n_actions)[None, :, None]
    with np.errstate(invalid="ignore"):
        means: Floats = sums.T.reshape(-1, n_actions, 2) / counts
    grand = disp.sum(axis=0) / max(len(disp), 1)
    spread = np.nansum(counts * (means - grand) ** 2, axis=(1, 2))
    p = (1 + int(np.count_nonzero(spread[1:] >= spread[0]))) / (PERMS + 1)
    return p, means[0]


def _body(names: list[str], means: Floats) -> dict[str, Vec | None]:
    """Step 5: e_{a,0} = m_{a,0} - m_{noop,0} per real action; None where either had no sample."""
    e = means - means[names.index(NOOP)]
    return {
        a: None if np.isnan(e[i]).any() else (float(e[i, 0]), float(e[i, 1]))
        for i, a in enumerate(names)
        if a != NOOP
    }


def design_block(
    rng: np.random.Generator, n: int, p_noop: float, dirs: Sequence[str]
) -> tuple[str, ...]:
    """S12: `n` actions in an order drawn from `rng`: round(p_noop * n) no-ops, never fewer than 2,
    and the directions balanced (counts differ by at most 1, the extra ones from a random start)."""
    n_noop = max(2, round(p_noop * n))
    start = int(rng.integers(len(dirs)))
    pool = [NOOP] * n_noop + [dirs[(start + i) % len(dirs)] for i in range(n - n_noop)]
    rng.shuffle(pool)
    return tuple(pool)
