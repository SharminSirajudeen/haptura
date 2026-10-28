"""T13 / T14: one condition over seeds x all six cases (plan T13, EVAL.md "Cost").

`python -m gate.run --condition gated+SAM --seeds 0-19 --budget 25 [--push]`

It first prints EVAL.md's projection and refuses above the budget: episodes x blocks per episode
(T11's rules-only blocks on the same seeds, run here offline at no cost) x ($0.01 per SAM block +
Muse tokens per turn x price), with tokens, frames and wall-clock from T2's measurements in
notes/api.md. Each episode's EpisodeLog is then written to
results/logs/<condition>/<seed>-<case>.json the moment it ends; one already on disk is skipped and
its spend counted, so a restarted container resumes. Before each episode it stops if that episode
would take the spend past the budget, at the larger of the projected and the measured cost per
episode. With --push, cache/ and the logs are committed and pushed after every seed: the container
is temporary.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from gate.agent import rules_turn, run_episode
from gate.arena import Arena, make_scenario
from gate.episode import Tracker, run_block, truth_slice
from gate.eval import MUSE_USD_IN, MUSE_USD_OUT, SAM_MIN_FRAMES, SAM_USD_PER_FRAME, dollars
from gate.gate import diagnose
from gate.meta_api import muse_turn
from gate.trackers import colour_tracker, sam_tracker, truth_tracker
from gate.types import EpisodeLog, from_json, to_json

CASES = ("feasible", "blocked", "remap_feasible", "remap_blocked", "body_remap", "body_blocked")
SETUP = {  # condition: (gated, tracker, policy), EVAL.md's table plus T11's free one
    "gated+SAM": (True, "sam", "muse"),
    "no-gate+SAM": (False, "sam", "muse"),
    "gated+colour": (True, "colour", "muse"),
    "rules-only+SAM": (True, "sam", "rules"),
    "gated+truth": (True, "truth", "muse"),
    "rules-only+truth": (True, "truth", "rules"),
}
FREE = "rules-only+truth"
MUSE_TOKENS_PER_TURN = (1000, 160)  # notes/api.md, T2: about 1k input and 160 output tokens
SECONDS_PER_BLOCK = {"sam": 2.5, "muse": 12.0}  # notes/api.md: SAM 2.2-2.5 s, Muse up to 12 s
LOGS = Path("results/logs")


def episode(seed: int, case: str, condition: str) -> EpisodeLog:
    """One episode of `condition` through T10's loop with its gate, tracker and policy."""
    gated, track, policy = SETUP[condition]
    arena = Arena(make_scenario(seed, case))
    trackers: dict[str, Tracker] = {"sam": sam_tracker, "colour": colour_tracker}
    tracker = trackers[track] if track in trackers else truth_slice(arena, truth_tracker)
    turn = rules_turn if policy == "rules" else muse_turn
    return run_episode(
        arena,
        tracker,
        condition,
        gated,
        clips=None,
        run_block=run_block,
        diagnose=diagnose,
        muse_turn=turn,
    )


def projection(condition: str, blocks: Sequence[int]) -> dict[str, float]:
    """EVAL.md's projection for the episodes whose rules-only block counts are `blocks`, one SAM
    call and one Muse turn per block."""
    _, track, policy = SETUP[condition]
    n, sam, muse = sum(blocks), track == "sam", policy == "muse"
    tin, tout = (t * n * muse for t in MUSE_TOKENS_PER_TURN)
    frames = n * SAM_MIN_FRAMES * sam
    seconds = n * (SECONDS_PER_BLOCK["sam"] * sam + SECONDS_PER_BLOCK["muse"] * muse)
    usd = frames * SAM_USD_PER_FRAME + tin * MUSE_USD_IN + tout * MUSE_USD_OUT
    return {
        "episodes": len(blocks),
        "blocks": n,
        "frames": frames,
        "input_tokens": tin,
        "output_tokens": tout,
        "usd": usd,
        "hours": seconds / 3600,
    }


def run(
    condition: str,
    seeds: Sequence[int],
    budget: float,
    *,
    out: Path = LOGS,
    push: bool = False,
    say: Callable[[str], object] = print,
) -> float:
    """The runs of `condition` within `budget` dollars; returns the condition's spend so far."""
    plan = projection(condition, [len(episode(s, c, FREE).blocks) for s in seeds for c in CASES])
    sizes = ", ".join(f"{k} {v:.4g}" for k, v in plan.items())
    say(f"{condition}, seeds {seeds[0]}-{seeds[-1]}, projected: {sizes}; budget ${budget:.2f}")
    if plan["usd"] > budget:
        say(f"refused: ${plan['usd']:.2f} projected is above the ${budget:.2f} budget")
        return 0.0
    folder = out / condition
    paths = [(s, c, folder / f"{s}-{c}.json") for s in seeds for c in CASES]
    done = [from_json(p.read_text(), EpisodeLog) for _, _, p in paths if p.exists()]
    spent, each = sum(map(dollars, done)), plan["usd"] / plan["episodes"]
    for s, c, path in paths:
        step = max(each, spent / len(done)) if done else each
        if not path.exists() and spent + step > budget:
            say(f"stopped before seed {s} {c}: ${spent:.2f} spent, the next about ${step:.2f}")
            return spent
        if not path.exists():
            done.append(episode(s, c, condition))
            folder.mkdir(parents=True, exist_ok=True)
            path.write_text(to_json(done[-1]))
            spent += dollars(done[-1])
        if push and c == CASES[-1]:
            _push(f"run: {condition} seed {s}, ${spent:.2f} spent")
    say(f"done: ${spent:.2f} spent on {condition}")
    return spent


def _push(message: str) -> None:
    """Commit and push cache/ and the logs; a commit with nothing new is not an error."""
    subprocess.run(["git", "add", "cache", str(LOGS)], check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], check=False)
    subprocess.run(["git", "push", "-q"], check=True)


def main(argv: Sequence[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m gate.run", description=__doc__.split("\n")[0])
    parser.add_argument("--condition", required=True, choices=sorted(SETUP))
    parser.add_argument("--seeds", required=True, help="first-last, e.g. 0-19")
    parser.add_argument("--budget", type=float, required=True, help="RUN_BUDGET_USD for this run")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args(argv)
    lo, hi = (int(x) for x in args.seeds.split("-"))
    run(args.condition, range(lo, hi + 1), args.budget, push=args.push)


if __name__ == "__main__":
    main(sys.argv[1:])
