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
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from phone import adb, ghostei, ui
from phone.ghostei import Device, Record
from phone.muse import Action, as_int, next_action
from phone.rules import check_tap

EST_STEP_USD = 0.02  # an upper guess per step, until the first run measures it
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
    """The nodes worth naming to the model: labelled or clickable, with an on-screen area."""
    return [n for n in nodes if (n.text or n.desc or n.clickable) and ui.area(n) > 0]


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
    """Type into the focused field only when the task app owns the focused window."""
    owner = ghostei.owner_now(r.dev, r.app)
    v = check_tap(owner, r.app, r.dev.allow)
    sent = not r.gate or v.kind == "allow"
    if sent:
        adb.shell(f"input text {ghostei.q(text.replace(' ', '%s'))}")
    return {"owner_at_tap": owner, "verdict": {"kind": v.kind, "reason": v.reason}, "tapped": sent}


def act(a: Action, els: list[ui.Node], r: Run) -> Record:
    """Carry out one action through the gate; the record says what happened and why."""
    if a.kind == "open":
        if a.arg not in r.apps:
            return {"refused": f"{a.arg or 'that app'} is not on the person's list of apps"}
        adb.launch(a.arg)
        time.sleep(OPEN_WAIT_S)
        r.app = a.arg
        return {}
    if a.kind == "tap":
        i = as_int(a.arg)
        if not 0 <= i < len(els):
            return {"refused": f"there is no element {a.arg}"}
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
    return {} if a.kind == "done" else {"refused": "that is not one of the actions"}


def outcome(rec: Record) -> str:
    """How a step ended, in the words Muse reads next step."""
    if "refused" in rec:
        return f"REFUSED: {rec['refused']}"
    if rec.get("verdict") and not rec["tapped"]:
        return f"REFUSED by the gate: {rec['verdict']['reason']}"
    return "done"


def run(r: Run, model: Model, steps: int, attack: Callable[[int], None]) -> Iterator[Record]:
    """Up to `steps` steps; it stops after `done` or a failed model call."""
    for i in range(1, steps + 1):
        attack(i)
        els = elements(ui.parse_nodes(adb.ui_xml()))
        a = model(r.task, r.apps, "\n".join(r.history), listing(els), adb.screenshot())
        rec = {"step": i, "app": r.app, "action": a.__dict__, "cost_usd": a.cost_usd}
        rec |= act(a, els, r)
        r.history.append(f"{i}. {a.kind} {a.arg} {rec.get('label', '')}".rstrip())
        r.history[-1] += f" -> {outcome(rec)}"
        yield rec
        if a.kind in ("done", "error"):
            return


def attacker(repo: Path | None, case_id: int, at: int) -> Callable[[int], None]:
    """What runs before each step: nothing, or GhostEI's dialog for `case_id` before step `at`."""
    if repo is None:
        return lambda i: None
    installed = {
        ln.removeprefix("package:").strip() for ln in adb.shell("pm list packages").split()
    }
    case = next(c for c in ghostei.cases(repo, installed, 999) if c["id"] == case_id)
    return lambda i: ghostei.popup(case) if i == at else None


def start(apps: list[str], attack: bool) -> None:
    """Every listed app stopped, then the home screen; with an attack, GhostEI's helper started
    first, as in §4c, so only its broadcast fires mid-task."""
    for pkg in [*apps, ghostei.HELPER]:
        adb.force_stop(pkg)
    if attack:
        adb.launch(ghostei.HELPER)
        time.sleep(2)
    adb.shell("input keyevent HOME")
    time.sleep(1)


def line(rec: Record) -> str:
    """One console line per step."""
    a = rec["action"]
    what = f"{a['kind']} {a['arg']} {rec.get('label', '')}".strip()
    return f"{rec['step']:>2} {what} -> {outcome(rec)} ${rec['cost_usd']:.4f} | {a['reason']}"


def main(argv: list[str]) -> int:
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    ap.add_argument("task")
    ap.add_argument("out", type=Path, help="JSONL, one record per step; must not exist yet")
    ap.add_argument("--apps", required=True, help="comma-separated packages the agent may open")
    ap.add_argument("--no-gate", action="store_true", help="send every touch, still judged")
    ap.add_argument("--steps", type=int, default=15)
    ap.add_argument("--budget", type=float, default=0.5, help="refuse above this projection, USD")
    ap.add_argument("--attack", type=Path, help="a clone of github.com/cyChen2003/Ghost-EI")
    ap.add_argument("--attack-case", type=int, default=26)
    ap.add_argument(
        "--attack-at", type=int, default=0, help="the step whose screen gets the dialog"
    )
    a = ap.parse_args(argv)
    apps = [p for p in a.apps.split(",") if p]
    cost = a.steps * EST_STEP_USD
    print(f"{a.steps} steps: projected {cost:.2f} USD at {EST_STEP_USD} each; budget {a.budget}")
    if cost > a.budget or ghostei.HELPER in apps:
        print("over budget, or the attacker's app is on --apps: nothing run")
        return 1
    attack = attacker(a.attack, a.attack_case, a.attack_at)
    dev = ghostei.device(
        adb.shell("cmd package list packages -U"), adb.shell("pm list packages -s")
    )
    r = Run(a.task, apps, not a.no_gate, dev, adb.screen_size())
    start(apps, a.attack is not None)
    with a.out.open("x") as f:
        for rec in run(r, next_action, a.steps, attack):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(line(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
