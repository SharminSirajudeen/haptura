"""The multi-step bench: tasks x attack (none, dialog) x gate (on, off) x repeats, one run each.

    export META_API_KEY=<your Meta Model API key>
    ANDROID_SERIAL=emulator-5554 uv run --locked python -m phone.bench run <out-dir> \\
        --ghostei <repo> [--repeats 3] [--steps 20] [--budget USD] [--record <movies-dir>]
    uv run --locked python -m phone.bench report <out-dir>   # writes <out-dir>/table.md

Each run resets its task (phone/bench_tasks.json), starts the agent, fires a GhostEI dialog before
step 5 in attack runs, then reads the task's end state over adb. It writes <id>.jsonl (the steps),
<id>.meta.json, and one line in <out-dir>/runs.jsonl. Runs already there are skipped, so a rerun
never pays twice; the bench stops once the runs so far cost more than --budget.
"""

import argparse
import json
import random
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from phone import adb, agent, bench_report, ghostei, muse, windows
from phone.muse import next_action

Record = dict[str, Any]
TASKS: list[Record] = json.loads((Path(__file__).parent / "bench_tasks.json").read_text())
ATTACK_AT = 5  # the step whose screen gets the dialog
SEED = 0  # the run order and the dialog each attack run gets
WAKE = ("settings put system screen_off_timeout 2147483647", "input keyevent WAKEUP")
SEGMENT_S = 170  # screenrecord stops at 180 s; segments are chained


def orphans(out: Path, todo: list[Record]) -> list[str]:
    """Runs still to do whose step file exists: cut off mid-way, with spend the ledger lacks."""
    return [p["id"] for p in todo if (out / f"{p['id']}.jsonl").exists()]


def plan(case_ids: list[int], repeats: int) -> list[Record]:
    """Every run of the matrix in a fixed shuffled order; attack runs cycle through the dialogs."""
    runs = [
        {"task": t["id"], "attack": attack, "gate": gate, "repeat": k}
        for t in TASKS
        for attack in ("none", "dialog")
        for gate in (True, False)
        for k in range(repeats)
    ]
    rng = random.Random(SEED)
    rng.shuffle(runs)
    cases = sorted(case_ids)
    rng.shuffle(cases)
    attacks = (r for r in runs if r["attack"] == "dialog")
    for i, r in enumerate(attacks):
        r["case"] = cases[i % len(cases)]
    for r in runs:
        gate = "on" if r["gate"] else "off"
        r["id"] = f"{r['task']}-{r['attack']}-gate-{gate}-{r['repeat']}"
    return runs


def resets(task: Record) -> list[str]:
    """The screen awake with no timeout (the timeout task leaves one minute), then the task's."""
    return [*WAKE, *task["reset"]]


def checks(task: Record) -> list[bool]:
    """Each end-state check of the task: whether its pattern matches what adb reads now."""
    return [re.search(rx, adb.shell(cmd), re.M) is not None for cmd, rx in task["checks"]]


def attacker(case: Record | None, dev: ghostei.Device, seen: Record) -> Callable[[int], None]:
    """Before step ATTACK_AT: the case's dialog, and whether its window was then listed."""

    def fire(i: int) -> None:
        if case and i == ATTACK_AT:
            ghostei.popup(case)
            wins = windows.parse_windows(adb.input_dump())
            seen["attack_shown"] = windows.shown(wins, dev.uids, ghostei.HELPER)

    return fire


def segments(flag: str, part: str) -> str:
    """The device-side loop: one segment after another while `flag` exists. A segment that fails
    (the screen off: exit 218, measured) ends it, so it never spins writing empty files."""
    one = f"screenrecord --time-limit {SEGMENT_S} {part}-$i.mp4 || break"
    return f"i=0; while [ -e {flag} ]; do {one}; i=$((i+1)); done"


@contextmanager
def recording(folder: Path | None, name: str) -> Iterator[None]:
    """The emulator's screen, chained in SEGMENT_S segments, pulled to `folder` afterwards."""
    if folder is None:
        yield
        return
    flag, part = "/sdcard/cg_rec_on", "/sdcard/cg_part"
    adb.shell(f"rm -f {part}-*.mp4; touch {flag}")
    rec = subprocess.Popen([adb.ADB, "shell", segments(flag, part)])
    try:
        yield
    finally:
        adb.shell(f"rm -f {flag}; pkill -INT screenrecord")
        rec.wait(timeout=30)
        folder.mkdir(parents=True, exist_ok=True)
        for f in adb.shell(f"ls {part}-*.mp4").split():
            seg = Path(f).stem.removeprefix("cg_part-")
            adb.run("pull", f, str(folder / f"{name}-720x1280-part{seg}.mp4"))


def write_meta(p: Record, a: argparse.Namespace, task: Record, attack: bool) -> None:
    """The run's sidecar, as phone/agent.py writes it."""
    side = argparse.Namespace(
        task=task["text"],
        attack=a.ghostei if attack else None,
        attack_case=p.get("case"),
        attack_at=ATTACK_AT,
        no_gate=not p["gate"],
    )
    meta = agent.meta(
        side, task["apps"], adb.shell("getprop ro.build.fingerprint"), agent.revision()
    )
    (a.out / f"{p['id']}.meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def run_one(
    p: Record, a: argparse.Namespace, dev: ghostei.Device, cases: dict[int, Record]
) -> Record:
    task = next(t for t in TASKS if t["id"] == p["task"])
    for cmd in resets(task):
        adb.shell(cmd)
    case, seen = cases.get(p.get("case", -1)), {"attack_shown": None}
    write_meta(p, a, task, case is not None)
    r = agent.Run(task["text"], task["apps"], p["gate"], dev, adb.screen_size())
    agent.start(task["apps"], case is not None)
    t0, recs = time.time(), []
    folder = a.record / a.out.name if case and a.record else None
    with recording(folder, p["id"]), (a.out / f"{p['id']}.jsonl").open("x") as f:
        for rec in agent.run(r, next_action, a.steps, a.budget, attacker(case, dev, seen)):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            recs.append(rec)
    cost, seconds = sum(x["cost_usd"] for x in recs), time.time() - t0
    found = checks(task)
    end = {"completed": all(found), "checks": found, "steps": len(recs), "cost_usd": cost}
    end["seconds"] = seconds
    return p | seen | end


def run_all(a: argparse.Namespace) -> int:
    present = ghostei.installed()
    cases = {c["id"]: c for c in ghostei.cases(a.ghostei, present, 999)}
    runs = plan(list(cases), a.repeats)
    ledger = a.out / "runs.jsonl"
    done = [json.loads(ln) for ln in ledger.open()] if ledger.exists() else []
    todo = [p for p in runs if p["id"] not in {d["id"] for d in done}]
    cut = orphans(a.out, todo)
    if cut:
        print(f"step files with no ledger row (a run cut off; its spend is not counted): {cut}")
        return 1
    spent = sum(d["cost_usd"] for d in done)
    step = muse.usd(*agent.EST_STEP_TOKENS)
    ceiling = len(todo) * a.steps * step
    print(
        f"{len(todo)} runs to go, spent {spent:.2f} USD; at most {ceiling:.2f} more at "
        f"{a.steps} steps x {step:.4f} ({muse.MODEL}); the bench stops once spend passes {a.budget}"
    )
    uids, system = adb.shell("cmd package list packages -U"), adb.shell("pm list packages -s")
    (a.out / "uids.txt").write_text(uids)
    dev = ghostei.device(uids, system, adb.keyboard())
    with ledger.open("a") as f:
        for p in todo:
            if spent > a.budget:
                print(f"spent {spent:.2f} USD > budget {a.budget}: stopped")
                return 1
            row = run_one(p, a, dev, cases)
            spent += row["cost_usd"]
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(
                f"{row['id']} case {row.get('case')}: completed {row['completed']}, "
                f"{row['steps']} steps, ${row['cost_usd']:.4f}, total ${spent:.2f}",
                flush=True,
            )
    return 0


def main(argv: list[str]) -> int:
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    ap.add_argument("mode", choices=["run", "report"])
    ap.add_argument("out", type=Path)
    ap.add_argument("--ghostei", type=Path, help="a clone of github.com/cyChen2003/Ghost-EI")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--model", choices=list(muse.PRICES), default=muse.MODEL)
    ap.add_argument("--budget", type=float, default=3.0, help="stop once the runs cost more, USD")
    ap.add_argument("--record", type=Path, help="record attack runs' screens into this folder")
    a = ap.parse_args(argv)
    muse.MODEL = a.model
    a.out.mkdir(parents=True, exist_ok=True)
    if a.mode == "report":
        (a.out / "table.md").write_text(bench_report.table(a.out))
        print((a.out / "table.md").read_text())
        return 0
    if a.ghostei is None:
        print("run needs --ghostei <repo>")
        return 1
    return run_all(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
