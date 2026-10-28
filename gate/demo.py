"""T15: the demo page's two panes from real EpisodeLogs (plan T15).

`python -m gate.demo <gated logs dir> <baseline logs dir> [<seed>-<case>]`

It lists every (seed, case) where the plan's rule for the video's first 20 seconds holds: the
baseline acted on an element it did not control (`false_act`) while the gated run is right by
EVAL.md's table. Given one of them, it writes that pair's logs and clips to web/episodes/, each
clip the run's own arena replayed and rendered, one frame per step, as web/app.js reads it. The pair
is chosen from the results, by eye; one the rule does not pick is refused, so none is staged.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from gate.arena import render
from gate.eval import replay, right
from gate.types import EpisodeLog, Frames, from_json, to_json
from gate.video import encode_mp4

OUT = Path("web/episodes")


def clip(log: EpisodeLog) -> Frames:
    """The episode's clip: every frame of the run's arena, replayed and rendered."""
    frames: Frames = np.stack(replay(log, render)[1])
    return frames


def candidates(
    gated: Sequence[EpisodeLog], baseline: Sequence[EpisodeLog]
) -> list[tuple[int, str]]:
    """The (seed, case) pairs where the baseline acted on an element it did not control and the
    gated run is right by EVAL.md's table."""
    good = {(x.scenario.seed, x.scenario.case) for x in gated if right(x)}
    bad = {(x.scenario.seed, x.scenario.case) for x in baseline if x.outcome == "false_act"}
    return sorted(good & bad)


def write(log: EpisodeLog, name: str, out: Path) -> None:
    """`name`.json and `name`.mp4 under `out`, the files a pane of web/app.js reads."""
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(to_json(log))
    (out / f"{name}.mp4").write_bytes(encode_mp4(clip(log)))


def main(argv: Sequence[str], out: Path = OUT) -> list[tuple[int, str]]:
    gated, baseline = (
        [from_json(p.read_text(), EpisodeLog) for p in sorted(Path(d).rglob("*.json"))]
        for d in argv[:2]
    )
    pairs = candidates(gated, baseline)
    print(f"{len(pairs)} candidates:", " ".join(f"{s}-{c}" for s, c in pairs) or "none")
    if len(argv) > 2:
        seed, case = argv[2].split("-", 1)
        if (int(seed), case) not in pairs:
            print(f"refused: {argv[2]} is not a candidate")
            return pairs
        for name, logs in (("gated", gated), ("baseline", baseline)):
            write(
                next(x for x in logs if (x.scenario.seed, x.scenario.case) == (int(seed), case)),
                name,
                out,
            )
        print(f"wrote {argv[2]} to {out}")
    return pairs


if __name__ == "__main__":
    main(sys.argv[1:])
