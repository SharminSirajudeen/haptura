"""The multi-step phone agent: Muse Spark picks one action per step; the gate checks every touch.

    set -a; . ~/.config/control-gate/meta.env; set +a
    ANDROID_SERIAL=emulator-5554 uv run python -m phone.agent "<task>" <out.jsonl> --apps PKG,PKG \\
        [--no-gate] [--steps N] [--budget USD] [--attack <ghostei-repo> --attack-at N]

The task app is the app the agent last opened from the person's `--apps` list, never whatever is on
screen. A tap or a scroll is sent only when the window under it belongs to the task app or an
allowlisted system package; typing only when the task app holds focus. A refusal and its reason go
back to Muse in the next step's history. One JSONL record per step; <out.jsonl> must not exist.
"""

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from gate.constants import MUSE_EFFORT
from phone import adb, ghostei, muse, ui
from phone.ghostei import Device, Record
from phone.muse import STEP_MAX_OUTPUT_TOKENS, Action, next_action
from phone.rules import check_tap

# The projection's step: the most tokens one step used, runs 33-37 and the Spark bench (1,930 in,
# 1,378 out), priced at the run's model. Not a ceiling: --budget stops a run once it costs more.
EST_STEP_TOKENS = (1930, 1378)
OPEN_WAIT_S = 3  # an app's first screen settles
Model = Callable[[str, list[str], str, str, bytes], Action]


@dataclass
class Run:
    task: str
    apps: list[str]  # the person's list: the only apps the agent may open
    gate: bool
    dev: Device
    size: tuple[int, int]
    app: str = ""  # the task app: the one last opened from `apps`; none before the first open
    history: list[str] = field(default_factory=list)


def elements(nodes: list[ui.Node]) -> list[ui.Node]:
    """The nodes worth naming to the model: labelled or clickable, with a width and a height."""
    on = [n for n in nodes if n.bounds[2] > n.bounds[0] and n.bounds[3] > n.bounds[1]]
    return [n for n in on if n.text or n.desc or n.clickable]


def label(n: ui.Node) -> str:
    return " / ".join(dict.fromkeys(s for s in (n.text, n.desc) if s)) or "(no label)"


def centre(n: ui.Node) -> tuple[int, int]:
    return (n.bounds[0] + n.bounds[2]) // 2, (n.bounds[1] + n.bounds[3]) // 2


def listing(els: list[ui.Node]) -> str:
    return "\n".join(f"[{i}] {label(n)!r} at {centre(n)}" for i, n in enumerate(els))


def scroll(direction: str, r: Run) -> Record:
    """One swipe through the screen's middle, checked at its start point like a tap."""
    w, h = r.size
    x, y0, y1 = w // 2, h * 3 // 4, h // 4  # down: the finger moves up the screen
    if direction == "up":
        y0, y1 = y1, y0
    return ghostei.tap_gated(x, y0, f"input swipe {x} {y0} {x} {y1} 400", r.app, r.gate, r.dev)


def type_gated(text: str, r: Run) -> Record:
    """Type into the focused field only when the task app itself owns the focused window, never an
    allowlisted system one (systemui draws a notification's reply field)."""
    owner = ghostei.owner_now(r.dev, r.app)
    v = check_tap(owner, r.app, frozenset())
    sent = not r.gate or v.kind == "allow"
    if sent:
        adb.shell(f"input text {ghostei.q(text.replace(' ', '%s'))}")
    return {"owner_at_tap": owner, "verdict": {"kind": v.kind, "reason": v.reason}, "tapped": sent}


def act(a: Action, els: list[ui.Node], r: Run) -> Record:
    """Carry out one action through the gate; the record says what happened and why."""
    if a.kind == "open":
        if a.arg not in r.apps:
            return {"refused": f"{a.arg!r} is not on the person's list of apps"}
        adb.launch(a.arg)
        time.sleep(OPEN_WAIT_S)
        r.app = a.arg
        return {}
    if a.kind == "tap":
        i = int(a.arg) if a.arg.isdecimal() else -1
        if not 0 <= i < len(els):
            return {"refused": f"there is no element {a.arg!r}"}
        x, y = centre(els[i])
        tap = ghostei.tap_gated(x, y, f"input tap {x} {y}", r.app, r.gate, r.dev)
        return {"label": label(els[i])} | tap
    if a.kind == "scroll":
        return scroll(a.arg, r)
    if a.kind == "type":
        return type_gated(a.arg, r)
    if a.kind == "back":
        adb.shell("input keyevent BACK")
        return {}
    return {} if a.kind in ("done", "error") else {"refused": "that is not one of the actions"}


def what(rec: Record) -> str:
    """The step in one line; argument and label quoted, so a label cannot forge a history line."""
    a, lab = rec["action"], rec.get("label")
    return " ".join([a["kind"], *(repr(s) for s in (a["arg"], lab) if s)])


def outcome(rec: Record) -> str:
    """How a step ended, in the words Muse reads next step."""
    if "refused" in rec:
        return f"REFUSED: {rec['refused']}"
    if rec.get("verdict") and not rec["tapped"]:
        return f"REFUSED by the gate: {rec['verdict']['reason']}"
    return "done"


def run(
    r: Run, model: Model, steps: int, budget: float, attack: Callable[[int], None]
) -> Iterator[Record]:
    """Up to `steps` steps; it stops after `done`, a failed model call, or once the calls so far
    cost more than `budget` USD."""
    spent = 0.0
    for i in range(1, steps + 1):
        attack(i)
        els = elements(ui.parse_nodes(adb.ui_xml()))
        a = model(r.task, r.apps, "\n".join(r.history), listing(els), adb.screenshot())
        # t_ns: after the model's reply, before the action; recovery is timed between actions
        rec = {"step": i, "t_ns": time.time_ns(), "app": r.app, "action": a.__dict__}
        rec |= {"cost_usd": a.cost_usd} | act(a, els, r)
        told = f"{i}. {what(rec)} -> {outcome(rec)}"
        rec["told_muse"] = told
        r.history.append(told)
        yield rec
        spent += a.cost_usd
        if a.kind in ("done", "error") or spent > budget:
            return


def attacker(repo: Path | None, case_id: int, at: int) -> Callable[[int], None]:
    """What runs before each step: nothing, or GhostEI's dialog for `case_id` before step `at`."""
    if repo is None:
        return lambda i: None
    case = next(c for c in ghostei.cases(repo, ghostei.installed(), 999) if c["id"] == case_id)
    return lambda i: ghostei.popup(case) if i == at else None


def start(apps: list[str], attack: bool) -> None:
    """Every listed app stopped, then the home screen; with an attack, GhostEI's helper started
    first, as ghostei.arrange does, so only its broadcast fires mid-task."""
    for pkg in [*apps, ghostei.HELPER]:
        adb.force_stop(pkg)
    if attack:
        adb.launch(ghostei.HELPER)
        time.sleep(2)
    adb.shell("input keyevent HOME")
    time.sleep(1)


def meta(a: argparse.Namespace, apps: list[str], fingerprint: str, sha: str) -> Record:
    """The run's sidecar: what produced its records."""
    attack = {"repo": str(a.attack), "case": a.attack_case, "at": a.attack_at} if a.attack else None
    return {
        "task": a.task,
        "apps": apps,
        "model": muse.MODEL,
        "effort": MUSE_EFFORT,
        "max_output_tokens": STEP_MAX_OUTPUT_TOKENS,
        "gate": not a.no_gate,
        "attack": attack,
        "fingerprint": fingerprint.strip(),
        "git_sha": sha.strip(),
    }


def revision() -> str:
    """The commit the code ran from, marked -dirty when the checkout had uncommitted changes."""
    cmd = ["git", "describe", "--always", "--dirty"]
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def line(rec: Record) -> str:
    """One console line per step."""
    reason = rec["action"]["reason"]
    return f"{rec['step']:>2} {what(rec)} -> {outcome(rec)} ${rec['cost_usd']:.4f} | {reason}"


def main(argv: list[str]) -> int:
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    ap.add_argument("task")
    ap.add_argument("out", type=Path, help="JSONL, one record per step; must not exist yet")
    ap.add_argument("--apps", required=True, help="comma-separated packages the agent may open")
    ap.add_argument("--no-gate", action="store_true", help="send every touch, still judged")
    ap.add_argument("--steps", type=int, default=15)
    ap.add_argument("--model", choices=list(muse.PRICES), default=muse.MODEL)
    ap.add_argument("--budget", type=float, default=0.5, help="refuse above this projection, USD")
    ap.add_argument("--attack", type=Path, help="a clone of github.com/cyChen2003/Ghost-EI")
    ap.add_argument("--attack-case", type=int, default=26)
    ap.add_argument(
        "--attack-at", type=int, default=0, help="the step whose screen gets the dialog"
    )
    a = ap.parse_args(argv)
    apps = [p for p in a.apps.split(",") if p]
    muse.MODEL = a.model
    step = muse.usd(*EST_STEP_TOKENS)
    print(
        f"{a.steps} steps of {a.model}: projected {a.steps * step:.2f} USD "
        f"at {step:.4f} each; budget {a.budget}"
    )
    cost = a.steps * step
    if cost > a.budget or ghostei.HELPER in apps or (a.attack and a.attack_at < 1):
        print("over budget, the attacker's app on --apps, or --attack with no --attack-at: not run")
        return 1
    with a.out.open("x") as f:  # before anything touches the device: an existing file stops here
        attack = attacker(a.attack, a.attack_case, a.attack_at)
        uids, system = adb.shell("cmd package list packages -U"), adb.shell("pm list packages -s")
        r = Run(a.task, apps, not a.no_gate, ghostei.device(uids, system), adb.screen_size())
        side = meta(a, apps, adb.shell("getprop ro.build.fingerprint"), revision())
        a.out.with_suffix(".meta.json").write_text(json.dumps(side, indent=1) + "\n")
        start(apps, a.attack is not None)
        for rec in run(r, next_action, a.steps, a.budget, attack):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(line(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
