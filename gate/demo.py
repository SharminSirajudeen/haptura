"""T15: the demo page's two panes from real EpisodeLogs (plan T15).

`python -m gate.demo <gated logs dir> <baseline logs dir> [<seed>-<case>]`

It lists every (seed, case) where the plan's rule for the video's first 20 seconds holds: the
baseline commits to an element it does not control within those 20 seconds, while the gated run,
right by EVAL.md's table, has not acted yet. Given one of them, it writes that pair's logs and
clips to web/episodes/, each clip the run's own arena replayed and rendered, one frame per step, as
web/app.js reads it. The pair is chosen from the results, by eye; one the rule does not pick is
refused, so none is staged. The page reads web/fixtures/ until the kill test's logs give a pair
(#31 lists the switch).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from gate.arena import render
from gate.constants import FPS
from gate.eval import replay, right
from gate.types import EpisodeLog, Frames, from_json, to_json
from gate.video import encode_mp4

OUT = Path("web/episodes")
FIRST_FRAMES = 20 * FPS  # the video's first 20 seconds, one frame per step


def clip(log: EpisodeLog) -> Frames:
    """The episode's clip: every frame of the run's arena, replayed and rendered."""
    frames: Frames = np.stack(replay(log, render)[1])
    return frames


def decoy_commit(log: EpisodeLog) -> int | None:
    """The frame at which a run acted on an element it did not control, judged at the commit
    itself: its last block carries the act decision (a decision is only ever made after a probe
    block). None for any other run, including a false act during act blocks, after control was
    lost, whose last block carries no decision."""
    last = log.blocks[-1] if log.blocks else None
    acted = last is not None and last.decision is not None and last.decision.kind == "act"
    if log.outcome != "false_act" or not acted or last is None:
        return None
    return last.step0 + len(last.actions)


def one_each(logs: Sequence[EpisodeLog]) -> dict[tuple[int, str], EpisodeLog]:
    """The logs by (seed, case); two for one are an error, never a silent pick."""
    by = {(x.scenario.seed, x.scenario.case): x for x in logs}
    if len(by) != len(logs):
        raise ValueError("two logs for one (seed, case)")
    return by


def candidates(
    gated: Sequence[EpisodeLog], baseline: Sequence[EpisodeLog]
) -> list[tuple[int, str]]:
    """The (seed, case) pairs where, within the video's first 20 seconds, the baseline committed to
    an element it did not control while the gated run, right by EVAL.md's table, had not acted."""
    good = {k: x for k, x in one_each(gated).items() if right(x)}
    out = []
    for k, x in one_each(baseline).items():
        f = decoy_commit(x)
        g = good.get(k)
        if f is not None and f <= FIRST_FRAMES and g is not None:
            out += [] if any(b.phase == "act" and b.step0 < f for b in g.blocks) else [k]
    return sorted(out)


def write(log: EpisodeLog, name: str, out: Path) -> None:
    """`name`.json and `name`.mp4 under `out`, the files a pane of web/app.js reads."""
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(to_json(log))
    (out / f"{name}.mp4").write_bytes(encode_mp4(clip(log)))


def main(argv: Sequence[str], out: Path = OUT) -> list[tuple[int, str]]:
    gated, baseline = (
        one_each([from_json(p.read_text(), EpisodeLog) for p in sorted(Path(d).rglob("*.json"))])
        for d in argv[:2]
    )
    pairs = candidates(list(gated.values()), list(baseline.values()))
    names = {f"{s}-{c}": (s, c) for s, c in pairs}
    print(f"{len(pairs)} candidates:", " ".join(names) or "none")
    if len(argv) > 2 and argv[2] not in names:
        print(f"refused: {argv[2]} is not a candidate")
    elif len(argv) > 2:
        write(gated[names[argv[2]]], "gated", out)
        write(baseline[names[argv[2]]], "baseline", out)
        print(f"wrote {argv[2]} to {out}")
    return pairs


if __name__ == "__main__":
    main(sys.argv[1:])
