"""Counts the kill test's three cache archives: every figure README.md, this folder's README.md,
docs/api.md and docs/pilot-runs.md (runs 54-57) quote about them. From the repository root:

    uv run --locked python results/kill-cache/count.py

reads the archives in place. `cutoffs` replays no-gate+SAM and names the episodes that were handed
a Muse reply cut off at the output cap: a cache file holds a reply, not its request, so only a
replay can place a reply in its episode. Run it in an empty scratch directory; REPLAY=1 makes a
missing reply an error, never a request, and no key is read:

    R=<repo>; tar -xzf $R/results/kill-cache/no-gate+SAM.tar.gz
    REPLAY=1 uv run --project $R python $R/results/kill-cache/count.py cutoffs $R/results/logs
"""

import json
import os
import statistics
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

import gate.meta_api as api
import gate.run as run
from gate.constants import BLOCK_STEPS
from gate.eval import SAM_MIN_FRAMES, SAM_USD_PER_FRAME, muse_usd, right
from gate.types import EpisodeLog, from_json

HERE = Path(__file__).parent
CONDS = ("gated+SAM", "no-gate+SAM", "gated+colour")
SAMS = CONDS[:2]
# A reply does not record its clip's length: a block's BLOCK_STEPS + 1 frames bill the minimum.
assert BLOCK_STEPS + 1 <= SAM_MIN_FRAMES


def archive(cond: str) -> dict[str, bytes]:
    """A condition's cached replies by file name, read from its archive in place."""
    with tarfile.open(HERE / f"{cond}.tar.gz") as tar:
        return {Path(m.name).name: tar.extractfile(m).read() for m in tar if m.isfile()}


def condition(cond: str, raw: dict[str, bytes]) -> str:
    muse = [v for v in map(json.loads, raw.values()) if isinstance(v, dict)]
    sam = len(raw) - len(muse)
    usage = [v["usage"] for v in muse]
    usd = sam * SAM_MIN_FRAMES * SAM_USD_PER_FRAME + sum(
        muse_usd(u["input_tokens"], u["input_tokens_details"]["cached_tokens"], u["output_tokens"])
        for u in usage
    )
    cut = sum(v["status"] != "completed" for v in muse)
    longest = max(u["output_tokens"] for u in usage)
    return (
        f"{cond}: {len(raw)} files ({len(muse)} Muse, {sam} SAM); {cut} Muse replies cut off "
        f"at the cap, the longest {longest} output tokens; ${usd:.4f} computed"
    )


def boxes(lines: list[str]) -> dict[tuple[int, int], tuple[int, ...]]:
    """A SAM reply's boxes by (frame, object id), read with sam_track's own patterns."""
    out = {}
    for line in lines:
        frame = int(api.FRAME.match(line).group(1))
        for oid, *xy in api.BOX.findall(line):
            out[frame, int(oid)] = tuple(map(int, xy))
    return out


def sam(raws: dict[str, dict[str, bytes]]) -> str:
    names = [n for n in raws[SAMS[0]] if n in raws[SAMS[1]] and n not in raws[CONDS[2]]]
    differ = [n for n in names if raws[SAMS[0]][n] != raws[SAMS[1]][n]]
    moved = []
    for n in differ:
        a, b = (boxes(json.loads(raws[c][n])) for c in SAMS)
        if a != b:
            moved.append(
                max(
                    (max(abs(p - q) for p, q in zip(a[k], b[k])) for k in a.keys() & b.keys()),
                    default=0,
                )
            )
    return (
        f"SAM 3.1: {len(names)} requests both SAM conditions sent; {len(differ)} replies differ "
        f"byte for byte; their boxes differ in {len(moved)}, the largest coordinate difference "
        f"per request {statistics.median(moved)} px at the median, {max(moved)} px at most"
    )


def calls(v: dict[str, Any]) -> list[Any]:
    return [
        (o["name"], json.loads(o["arguments"])) for o in v["output"] if o["type"] == "function_call"
    ]


def generated(v: dict[str, Any]) -> str:
    """What a Muse reply generated, without the ids and timestamps every reply carries: its message
    text, its tool calls, and its output and reasoning token counts."""
    text = [c["text"] for o in v["output"] if o["type"] == "message" for c in o["content"]]
    u = v["usage"]
    return json.dumps([
        text,
        calls(v),
        u["output_tokens"],
        u["output_tokens_details"]["reasoning_tokens"],
    ])


def muse(raws: dict[str, dict[str, bytes]]) -> str:
    names = [n for n in raws[CONDS[0]] if all(n in raws[c] for c in CONDS)]
    replies = [[json.loads(raws[c][n]) for c in CONDS] for n in names]
    zero = sum(v["temperature"] == 0.0 for r in replies for v in r)
    differ = sum(len({raws[c][n] for c in CONDS}) > 1 for n in names)
    made = sum(len({generated(v) for v in r}) > 1 for r in replies)
    called = sum(len({json.dumps(calls(v)) for v in r}) > 1 for r in replies)
    return (
        f"Muse Wonder: {len(names)} requests all three conditions sent, temperature 0.0 in {zero} "
        f"of {3 * len(names)} replies; {differ} differ byte for byte, {made} in what was "
        f"generated, {called} in the tool call"
    )


def archives() -> None:
    raws = {c: archive(c) for c in CONDS}
    for c in CONDS:
        print(condition(c, raws[c]))
    names = Counter(n for raw in raws.values() for n in raw)
    print(
        f"{len(names)} distinct names; {sum(k > 1 for k in names.values())} in two or more "
        f"archives, {sum(k == len(CONDS) for k in names.values())} in all three"
    )
    print(sam(raws))
    print(muse(raws))


def cutoffs(logs: Path) -> None:
    if os.environ.get("REPLAY") != "1":
        sys.exit(
            "cutoffs replays the archive: set REPLAY=1, so that a missing reply is never a request"
        )
    episode, cached, now = run.episode, api.cached, [""]
    handed: dict[str, list[str]] = {}

    def noting(key: str, fn: Any, root: Path = api.CACHE_DIR) -> Any:
        value = cached(key, fn, root)
        if isinstance(value, dict):
            handed.setdefault(now[0], []).append(value["status"])
        return value

    def naming(seed: int, case: str, cond: str) -> EpisodeLog:
        now[0] = f"{seed}-{case}"
        return episode(seed, case, cond)

    api.cached, run.episode = noting, naming
    run.main(["--condition", SAMS[1], "--seeds", "1001-1019", "--budget", "20"])
    hit = sorted(e for e, got in handed.items() if any(s != "completed" for s in got))
    ok = {}
    for p in logs.rglob("*.json"):
        log = from_json(p.read_text(), EpisodeLog)
        ok[log.condition, f"{log.scenario.seed}-{log.scenario.case}"] = int(right(log))
    pairs = [e for c, e in ok if c == SAMS[0]]
    keep = [e for e in pairs if e not in hit]
    cut = sum(s != "completed" for got in handed.values() for s in got)
    gain = sum(ok[SAMS[0], e] - ok[SAMS[1], e] for e in keep) / len(keep)
    floor = sum(ok[SAMS[0], e] - (1 if e in hit else ok[SAMS[1], e]) for e in pairs) / len(pairs)
    print(
        f"{sum(map(len, handed.values()))} Muse replies handed over, {cut} cut off, in {len(hit)}:"
    )
    print(", ".join(hit))
    print(f"paired difference without them: {gain:.4f} over {len(keep)} pairs")
    print(f"with no-gate+SAM right in all {len(hit)}: {floor:.4f} over {len(pairs)} pairs")


if __name__ == "__main__":
    cutoffs(Path(sys.argv[2])) if sys.argv[1:2] == ["cutoffs"] else archives()
