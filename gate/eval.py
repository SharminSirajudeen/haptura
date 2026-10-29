"""T12: EpisodeLogs to results/table.md, every quantity as EVAL.md defines it.

Only the logs are read, plus a replay of each log's own arena (same scenario, same actions, same
acting flag per block), which gives the true positions the eyes and occlusion metrics score
against. Nothing here reaches the agent.

`python -m gate.eval [logs dir] [table]` reads every `*.json` EpisodeLog under the directory
(default `results/logs`) and writes the table (default `results/table.md`). It makes no request.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

import numpy as np

from gate.arena import Arena, masks
from gate.constants import ELEMENT_PX
from gate.trackers import match_ids
from gate.types import BlockRecord, EpisodeLog, Tracks, Vec, from_json

FIVE = ("blocked", "remap_feasible", "remap_blocked", "body_remap", "body_blocked")
Z95 = 1.959963984540054  # the normal quantile at 0.975
SAM_USD_PER_FRAME = 0.20 / 1000  # notes/api.md: $0.20 per 1k video frames,
SAM_MIN_FRAMES = 50  # billed at least 50 frames per request; one request per block
MUSE_USD_IN, MUSE_USD_OUT = 1.25e-6, 4.25e-6  # notes/api.md: per input / output token
DIAGNOSED_BY = {"target_lost": "control_remap", "body_changed": "body_remap"}
KINDS = ("eyes_swapped", "body_changed", "target_lost")
CONDITIONS = ("gated+SAM", "no-gate+SAM", "gated+colour", "rules-only+SAM", "gated+truth")
KILL_CONDITIONS = CONDITIONS[:3]
KILL_DIFF, KILL_OCCLUSION = 0.10, 0.20  # EVAL.md's suggested numbers; Sharmin confirms before T13
History = Sequence[dict[int, Vec]]
Pairs = frozenset[tuple[int, int]]
KILL_SEEDS = range(1000, 1020)  # EVAL.md: chosen before any run on them
KILL_RANGE = f"seeds {KILL_SEEDS[0]}-{KILL_SEEDS[-1]}"


def acted_before(log: EpisodeLog, i: int) -> int:
    """Act steps taken before block i: the clock the remap schedules run on."""
    return sum(len(b.actions) for b in log.blocks[:i] if b.phase == "act")


def right(log: EpisodeLog) -> bool:
    """EVAL.md's right-hand column. The remap step is the scenario's one event, in act steps."""
    sc, blocks, out = log.scenario, log.blocks, log.outcome
    step = sc.events[0][0] if sc.events else 0
    after = [b for i, b in enumerate(blocks) if acted_before(log, i) >= step]
    kinds = {b.diagnosis.kind for b in after if b.diagnosis is not None}
    return {
        "feasible": out == "success",
        "blocked": out == "decline",
        "remap_feasible": out == "success"
        and (any(b.phase == "probe" for b in after) or "target_lost" in kinds),
        "remap_blocked": out == "decline" and acted_before(log, len(blocks)) >= step,
        "body_remap": out == "success" and "body_changed" in kinds,
        "body_blocked": out == "decline"
        and any(e.label == "mine" for b in blocks for e in b.evidence),
    }[sc.case]


def wilson(k: int, n: int) -> tuple[float, float]:
    """The 95% Wilson interval of k right out of n."""
    if n == 0:
        return (0.0, 1.0)
    p, z2 = k / n, Z95 * Z95
    mid = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return (mid - half, mid + half)


def paired_difference(a: Iterable[EpisodeLog], b: Iterable[EpisodeLog]) -> tuple[float, int]:
    """The mean, over the (seed, case) pairs both conditions ran, of right(a) - right(b), and the
    number of pairs."""
    ra = {(x.scenario.seed, x.scenario.case): right(x) for x in a}
    rb = {(x.scenario.seed, x.scenario.case): right(x) for x in b}
    keys = ra.keys() & rb.keys()
    return (sum(ra[k] - rb[k] for k in keys) / len(keys) if keys else math.nan), len(keys)


def recovery_steps(log: EpisodeLog, kind: str) -> int | None:
    """Act steps from the remap's event step to the first block at or after it whose diagnosis
    is `kind` (target_lost, body_changed); None when the episode never recovers."""
    steps = [s for s, event, _ in log.scenario.events if event == DIAGNOSED_BY[kind]]
    hits = [
        acted_before(log, i) - steps[0]
        for i, b in enumerate(log.blocks)
        if steps and b.diagnosis is not None and b.diagnosis.kind == kind
        if acted_before(log, i) >= steps[0]
    ]
    return hits[0] if hits else None


def true_ids(tracks: Tracks, truth: dict[int, Vec], t: int) -> dict[int, int]:
    """S9 at one frame: each tracker id seen at frame t of its block to the nearest true element."""
    seen = {k: p[t : t + 1] for k, p in tracks.items() if not np.isnan(p[t]).any()}
    return match_ids(seen, truth)


def eyes_changed(block: BlockRecord, history: History) -> bool:
    """The tracker-to-true map changed within the block, on some id seen in two of its frames."""
    maps = [
        true_ids(block.tracks, history[block.step0 + t], t) for t in range(len(block.actions) + 1)
    ]
    seen: dict[int, set[int]] = {}
    for m in maps:
        for k, v in m.items():
            seen.setdefault(k, set()).add(v)
    return any(len(v) > 1 for v in seen.values())


def fired_in(log: EpisodeLog, i: int, event: str) -> bool:
    """An `event` remap fired in block i: its step is one of that act block's act steps."""
    b, lo = log.blocks[i], acted_before(log, i)
    hit = any(k == event and lo <= s < lo + len(b.actions) for s, k, _ in log.scenario.events)
    return b.phase == "act" and hit


def diagnosis_right(log: EpisodeLog, i: int, history: History) -> bool | None:
    """Block i's diagnosis against the truth: eyes_swapped iff the map changed in that block;
    body_changed or target_lost iff that remap fired in that block or the one before; None for a
    block with no such diagnosis."""
    found = log.blocks[i].diagnosis
    kind = None if found is None else found.kind
    if kind == "eyes_swapped":
        return eyes_changed(log.blocks[i], history)
    if kind not in DIAGNOSED_BY:
        return None
    return fired_in(log, i, DIAGNOSED_BY[kind]) or (
        i > 0 and fired_in(log, i - 1, DIAGNOSED_BY[kind])
    )


def replay[T](log: EpisodeLog, each: Callable[[Arena], T]) -> tuple[list[dict[int, Vec]], list[T]]:
    """The run's arena again (same scenario, same actions, same acting flag per block): its true
    positions per frame, and `each` of the arena at every frame."""
    arena = Arena(log.scenario)
    seen = [each(arena)]
    for b in log.blocks:
        arena.start_block()
        for a in b.actions:
            arena.step(a, b.phase == "act")
            seen.append(each(arena))
    return arena.history, seen


def overlapping(arena: Arena) -> Pairs:
    """The pairs whose masks share more than half of the smaller one's pixels; pairs ELEMENT_PX
    apart on an axis cannot touch, so only nearer pairs are drawn."""
    pos = arena.positions()
    near = [
        (i, j)
        for i in range(len(pos))
        for j in range(i + 1, len(pos))
        if np.abs(pos[i] - pos[j]).max() < ELEMENT_PX
    ]
    m = masks(arena) if near else {}
    return frozenset(
        p for p in near if (m[p[0]] & m[p[1]]).sum() > min(m[p[0]].sum(), m[p[1]].sum()) / 2
    )


def occlusion(log: EpisodeLog, history: History, overlap: Sequence[Pairs]) -> dict[str, list[int]]:
    """Per block phase: [kept, scored, unscored] frames of overlap, counted per overlapping pair.
    A pair's run of overlap frames is kept when its two elements are held by the same tracker ids
    on the nearest frame before the run and the nearest frame after it on which both are held
    apart, searched only back to the pair's previous run and on to its next. Never held apart again
    before the next run is not kept; no such frame before the run, or a run reaching the episode's
    end, is unscored."""
    owner = _frame_owner(log)
    out = {"probe": [0, 0, 0], "act": [0, 0, 0]}
    for pair in sorted(set().union(*overlap)):
        runs = _runs([pair in f for f in overlap])
        for k, (lo, hi) in enumerate(runs):
            start = runs[k - 1][1] if k else 0
            stop = runs[k + 1][0] if k + 1 < len(runs) else len(overlap)
            before = _held(log, owner, history, pair, range(lo - 1, start - 1, -1))
            scored = before is not None and hi < len(overlap)
            kept = scored and before == _held(log, owner, history, pair, range(hi, stop))
            for f in range(lo, hi):
                tally = out[log.blocks[owner[f]].phase]
                tally[0] += kept
                tally[1] += scored
                tally[2] += not scored
    return out


def _held(
    log: EpisodeLog, owner: list[int], history: History, pair: tuple[int, int], frames: range
) -> tuple[int, int] | None:
    """The tracker ids holding the pair's two true elements on the first of `frames` where both
    are held, by S9 at that frame; None if no frame has both."""
    for f in frames:
        b = log.blocks[owner[f]]
        held = {true: tid for tid, true in true_ids(b.tracks, history[f], f - b.step0).items()}
        if pair[0] in held and pair[1] in held:
            return held[pair[0]], held[pair[1]]
    return None


def _frame_owner(log: EpisodeLog) -> list[int]:
    """The block each episode frame is read from: the last block that starts at or before it."""
    owner: list[int] = []
    for i, b in enumerate(log.blocks):
        owner[b.step0 :] = [i] * (len(b.actions) + 1)
    return owner


def _runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """The [lo, hi) spans of consecutive True."""
    edges = np.diff(np.concatenate([[0], np.asarray(flags, dtype=int), [0]]))
    return list(
        zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist(), strict=True)
    )


def overrules(log: EpisodeLog) -> int:
    """Blocks where Muse's call differs from the advice line: another kind, or an act on another
    element."""
    return sum(
        1
        for b in log.blocks
        if b.advice is not None and b.decision is not None
        if b.decision.kind != b.advice.kind
        or (b.decision.kind == "act" and b.decision.object_id != b.advice.object_id)
    )


def billed_frames(log: EpisodeLog) -> int:
    """SAM frames billed: at least SAM_MIN_FRAMES per block, and none without SAM."""
    sam = log.condition.endswith("+SAM")
    return sum(max(SAM_MIN_FRAMES, len(b.actions) + 1) for b in log.blocks) if sam else 0


def dollars(log: EpisodeLog) -> float:
    """All Muse and SAM spend of the episode."""
    u = log.usage
    muse = u.get("input_tokens", 0) * MUSE_USD_IN + u.get("output_tokens", 0) * MUSE_USD_OUT
    return muse + billed_frames(log) * SAM_USD_PER_FRAME


def diagnoses(log: EpisodeLog, history: History) -> dict[str, list[int]]:
    """Per kind (eyes, body, control): [right, total] over the episode's diagnoses."""
    out = {k: [0, 0] for k in KINDS}
    for i, b in enumerate(log.blocks):
        ok = diagnosis_right(log, i, history)
        if ok is not None and b.diagnosis is not None:
            out[b.diagnosis.kind][0] += ok
            out[b.diagnosis.kind][1] += 1
    return out


def replayed(logs: Sequence[EpisodeLog]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """A condition's diagnosis tallies and occlusion tallies, each episode replayed once."""
    diag = {k: [0, 0] for k in KINDS}
    occ = {"probe": [0, 0, 0], "act": [0, 0, 0]}
    for log in logs:
        history, overlap = replay(log, overlapping)
        for total, part in (
            (diag, diagnoses(log, history)),
            (occ, occlusion(log, history, overlap)),
        ):
            for k, v in part.items():
                total[k] = [a + b for a, b in zip(total[k], v, strict=True)]
    return diag, occ


def kept_rate(occ: dict[str, list[int]]) -> float:
    """Identities kept through occlusion: kept over scored frames, both phases."""
    scored = occ["probe"][1] + occ["act"][1]
    return (occ["probe"][0] + occ["act"][0]) / scored if scored else math.nan


def _frac(k: int, n: int) -> str:
    return f"{k}/{n} = {k / n:.2f}" if n else "0/0"


def _rate(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{_frac(k, n)} [{lo:.2f}, {hi:.2f}]"


def _right_in(logs: Sequence[EpisodeLog], cases: Sequence[str]) -> tuple[int, int]:
    some = [x for x in logs if x.scenario.case in cases]
    return sum(map(right, some)), len(some)


def _recovery(logs: Sequence[EpisodeLog], kind: str) -> str:
    remapped = [x for x in logs if any(e == DIAGNOSED_BY[kind] for _, e, _ in x.scenario.events)]
    steps = [s for s in (recovery_steps(x, kind) for x in remapped) if s is not None]
    mean = f"{sum(steps) / len(steps):.1f} steps" if steps else "none"
    return f"{mean}, {len(steps)} of {len(remapped)} recovered"


def _per_correct(logs: Sequence[EpisodeLog], k: int) -> tuple[str, str]:
    """Dollars, and input / output tokens, per episode that passes the table."""
    if k == 0:
        return "no correct episode", "no correct episode"
    tok_in, tok_out = (
        sum(x.usage.get(t, 0) for x in logs) for t in ("input_tokens", "output_tokens")
    )
    return f"${sum(map(dollars, logs)) / k:.4f}", f"{tok_in / k:.0f} / {tok_out / k:.0f}"


def column(
    logs: Sequence[EpisodeLog], diag: dict[str, list[int]], occ: dict[str, list[int]]
) -> dict[str, str]:
    """One condition's cells, keyed by the table's row names, in EVAL.md's order."""
    n, k = len(logs), sum(map(right, logs))
    usd, tokens = _per_correct(logs, k)
    occlusion_cells = {
        f"identities kept through occlusion, {p} blocks": _frac(*occ[p][:2])
        + f"; {occ[p][2]} unscored"
        for p in ("probe", "act")
    }
    return {
        "episodes": str(n),
        "headline 1: right on blocked and remap cases": _rate(*_right_in(logs, FIVE)),
        "headline 2: success on feasible": _rate(*_right_in(logs, ("feasible",))),
        "six-case score": _frac(k, n),
        "false-action rate": _frac(sum(x.outcome == "false_act" for x in logs), n),
        "act steps to recover, control remap": _recovery(logs, "target_lost"),
        "act steps to recover, body remap": _recovery(logs, "body_changed"),
        **{f"diagnosis accuracy, {kind}": _frac(*diag[kind]) for kind in KINDS},
        "correct declines on body_blocked": _frac(*_right_in(logs, ("body_blocked",))),
        **occlusion_cells,
        "advice overruled (in right episodes)": f"{sum(map(overrules, logs))} "
        f"({sum(overrules(x) for x in logs if right(x))})",
        "blocks per episode": f"{sum(len(x.blocks) for x in logs) / n:.2f}",
        "input / output tokens per episode": " / ".join(
            f"{sum(x.usage.get(t, 0) for x in logs) / n:.0f}"
            for t in ("input_tokens", "output_tokens")
        ),
        "billed SAM frames per episode": f"{sum(map(billed_frames, logs)) / n:.0f}",
        "dollars per correct decision": usd,
        "input / output tokens per correct decision": tokens,
    }


def kill_rule(logs: Sequence[EpisodeLog]) -> str:
    """EVAL.md's numeric kill rule on KILL_SEEDS of the kill test's three conditions. It says
    rethink unless both arms clearly pass, so a number that could not be computed is a rethink."""
    by = _by_condition([x for x in logs if x.scenario.seed in KILL_SEEDS])
    if not all(c in by for c in KILL_CONDITIONS):
        return f"Kill rule: not computed; it needs {KILL_RANGE} of {', '.join(KILL_CONDITIONS)}."
    diff, pairs = paired_difference(by["gated+SAM"], by["no-gate+SAM"])
    sam, colour = (kept_rate(replayed(by[c])[1]) for c in ("gated+SAM", "gated+colour"))
    passes = kill_passes(diff, sam - colour)
    return (
        f"Kill rule, {KILL_RANGE}: paired difference (gated+SAM - no-gate+SAM) = {diff:.3f} over "
        f"{pairs} pairs (rethink at <= {KILL_DIFF}); identities kept through occlusion, SAM "
        f"{sam:.3f} - colour {colour:.3f} = {sam - colour:.3f} (rethink below {KILL_OCCLUSION}). "
        + ("Passes." if passes else "**Rethink.**")
    )


def kill_passes(diff: float, margin: float) -> bool:
    """Both arms clear: the paired difference above KILL_DIFF and SAM's lead in identities kept at
    least KILL_OCCLUSION. Written as the passing condition, so NaN in either fails."""
    return diff > KILL_DIFF and margin >= KILL_OCCLUSION


def _by_condition(logs: Sequence[EpisodeLog]) -> dict[str, list[EpisodeLog]]:
    by: dict[str, list[EpisodeLog]] = {}
    for log in logs:
        by.setdefault(log.condition, []).append(log)
    return by


def table(logs: Sequence[EpisodeLog]) -> str:
    """results/table.md: a column per condition, EVAL.md's conditions first; then the kill rule.
    Two logs of one (condition, seed, case) are an error, never a silent double count."""
    keys = [(x.condition, x.scenario.seed, x.scenario.case) for x in logs]
    if len(set(keys)) != len(keys):
        raise ValueError("two logs for one (condition, seed, case)")
    by = _by_condition(logs)
    names = [c for c in CONDITIONS if c in by] + sorted(set(by) - set(CONDITIONS))
    cols = {c: column(by[c], *replayed(by[c])) for c in names}
    rows = list(cols[names[0]]) if names else []
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines += [f"| {r} | " + " | ".join(cols[c][r] for c in names) + " |" for r in rows]
    seeds = sorted({x.scenario.seed for x in logs})
    head = f"# Results (EVAL.md), seeds {seeds[0]}-{seeds[-1]}" if seeds else "# Results (EVAL.md)"
    return "\n".join([head, "", *lines, "", kill_rule(logs), ""])


def main(argv: Sequence[str]) -> None:
    """[logs dir] [table] [first-last seeds]; every seed in the directory when no range is given."""
    logs_dir = Path(argv[0]) if argv else Path("results/logs")
    out = Path(argv[1]) if len(argv) > 1 else Path("results/table.md")
    lo, hi = (int(x) for x in argv[2].split("-")) if len(argv) > 2 else (0, math.inf)
    logs = [from_json(p.read_text(), EpisodeLog) for p in sorted(logs_dir.rglob("*.json"))]
    logs = [x for x in logs if lo <= x.scenario.seed <= hi]
    out.write_text(table(logs))
    print(f"{len(logs)} episodes from {logs_dir} -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
