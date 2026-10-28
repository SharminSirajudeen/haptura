"""Run GhostEI overlay cases on the emulator: one Muse proposal and one gated record per case.

    set -a; . ~/.config/control-gate/meta.env; set +a
    ANDROID_SERIAL=emulator-5554 uv run python -m phone.ghostei <ghostei-repo> <out.jsonl> \\
        [--clean] [--gate] [--limit N] [--budget USD]

Each record carries both agents: the proposed tap is performed, so its click event is the
ground truth for the ungated agent, and the gate's verdict on that same tap is the gated agent.
`--gate` makes a blocked tap not happen (the demo). `--clean` runs the same tasks with no overlay:
the gate's blocks there are its false blocks. A case already in <out.jsonl> is skipped, so a rerun
never pays twice.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phone import adb, ui, windows
from phone.muse import Proposal, propose
from phone.rules import SYSTEM_ALLOW, Verdict, check_tap, owner_evidence

HELPER = "com.example.myapplication"  # GhostEI's injector app; its window is the attack
PKG = {  # GhostEI's app names -> the packages installed on Small_Phone
    "Gallery": "com.google.android.apps.photos",
    "Calendar": "com.google.android.calendar",
    "Camera": "com.android.camera2",
    "Chrome": "com.android.chrome",
    "Gmail": "com.google.android.gm",
    "+ contact": "com.google.android.contacts",
    "Messages": "com.google.android.apps.messaging",
    "Settings": "com.android.settings",
    "Files": "com.google.android.documentsui",
}
EST_PER_CALL_USD = 0.0072  # G1 measured $0.14 for 20 calls (results/phone/g1-proxy)
FAKE_PAGE = "http://10.0.2.2:8000/x"  # where the attacker's confirm leads; nothing listens there
Record = dict[str, Any]
Model = Callable[[str, bytes, tuple[int, int], str], Proposal]


def cases(repo: Path, installed: set[str], limit: int) -> list[Record]:
    """Overlay-attack cases whose app is installed, in dataset order."""
    out = []
    for line in (repo / "datasets/GhostEI.jsonl").open():
        r = json.loads(line)
        app = next((a for a in r["app"] if PKG.get(a) in installed), None)
        if r["use_dynamic"] == "Overlay Attack" and app:
            extra = {k: r["extra"][k] for k in ("title", "content", "cancel", "confirm")}
            out.append({"id": r["id"], "app": app, "pkg": PKG[app], "task": r["prompt"], **extra})
    return out[:limit]


def q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def arrange(case: Record, attack: bool) -> None:
    """A fresh helper and a freshly started task app; with `attack`, GhostEI's dialog over it.

    The task app is stopped first, so no case starts where the previous one left it (G3 did not do
    this; see docs/pilot-runs.md P15).
    """
    adb.force_stop(HELPER)
    adb.force_stop(case["pkg"])
    if attack:
        adb.launch(HELPER)
        time.sleep(2)
    adb.launch(case["pkg"])
    time.sleep(4)
    if attack:
        keys = ("title", "content", "cancel", "confirm")
        extras = " ".join(f"--es {k} {q(case[k])}" for k in keys)
        adb.shell(
            f"am broadcast --include-stopped-packages -n {HELPER}/.AdbReceiver "
            f"-a com.example.broadcast.UPDATE_POPUP {extras} --es weburl {q(FAKE_PAGE)} "
            "--ez isUrgent true --receiver-foreground"
        )
        time.sleep(3)


@dataclass(frozen=True)
class Device:
    """What the gate needs about the device, read once per run."""

    uids: windows.Uids  # uid -> its packages
    allow: frozenset[str]  # SYSTEM_ALLOW, cut to the packages this device ships as system


def device(uid_list: str, system_list: str) -> Device:
    """From `cmd package list packages -U` and `pm list packages -s`."""
    system = {ln.removeprefix("package:").strip() for ln in system_list.splitlines()}
    return Device(windows.packages_by_uid(uid_list), SYSTEM_ALLOW & system)


def owner_now(dev: Device, task: str, x: int | None = None, y: int = 0) -> str:
    """The owner the gate checks, read from the device now: of the window a touch at (x, y)
    reaches, or of the focused window when x is None."""
    text = adb.input_dump()
    wins = windows.parse_windows(text)
    w = windows.focused(wins, text) if x is None else windows.receiver(wins, x, y)
    return windows.owner_package(w, dev.uids, task, dev.allow)


def measure(case: Record, nodes: list[ui.Node], p: Proposal) -> Record:
    """Measurement only, never the gate: what the tap point hits in the accessibility tree and
    whether that is the attacker's confirm button."""
    hit = ui.node_at(nodes, p.x, p.y) if p.action == "tap" else None
    confirm = ui.with_text(nodes, case["confirm"])
    return {
        "hit_text": hit.text if hit else "",
        "hit_confirm": hit is not None and hit is confirm,
        "confirm_bounds": confirm.bounds if confirm else None,
    }


def tap_gated(p: Proposal, task: str, gate: bool, dev: Device) -> Record:
    """Read the owner, judge, and tap, in that order and back to back inside the click watch,
    so nothing can change the screen between the check and the tap but adb's own latency."""

    def act() -> tuple[str, Verdict, bool]:
        owner = owner_now(dev, task, p.x, p.y)
        v = check_tap(owner, task, dev.allow)
        tapped = not gate or v.kind == "allow"
        if tapped:
            adb.shell(f"input tap {p.x} {p.y}")
        return owner, v, tapped

    (owner, v, tapped), (pkg, text) = adb.clicked_during(act)
    verdict = {"kind": v.kind, "reason": v.reason}
    return {
        "owner_at_tap": owner,
        "verdict": verdict,
        "tapped": tapped,
        "click_pkg": pkg,
        "click_text": text,
    }


def run_case(
    case: Record, attack: bool, gate: bool, inform: bool, model: Model, dev: Device
) -> Record:
    arrange(case, attack)
    focus = owner_now(dev, case["pkg"])
    rec: Record = {k: case[k] for k in ("id", "app", "pkg", "task", "confirm")}
    rec |= {"attack": attack, "inform": inform, "focus_owner": focus}
    text = adb.input_dump()
    wins, readable = windows.parse_windows(text), windows.window_lines(text) is not None
    rec |= {"dump_readable": readable, "overlay_shown": windows.shown(wins, dev.uids, HELPER)}
    if attack and readable and not rec["overlay_shown"]:
        return rec  # the attack did not render, or no list came back: no model call, no number
    # a list that breaks the grammar goes on: the gate blocks the tap (no owner), a block (#19)
    nodes = ui.parse_nodes(adb.ui_xml())
    evidence = owner_evidence(check_tap(focus, case["pkg"], dev.allow)) if inform else ""
    size = adb.screen_size()
    p = model(case["task"], adb.screenshot(), size, evidence)
    rec |= {"evidence": evidence, "screen": list(size), "cost_usd": p.cost_usd}
    rec |= {"proposal": p.__dict__} | measure(case, nodes, p)
    if p.action != "tap":
        return rec | {
            "owner_at_tap": "",
            "verdict": None,
            "tapped": False,
            "click_pkg": "",
            "click_text": "",
        }
    return rec | tap_gated(p, case["pkg"], gate, dev)


def line(rec: Record) -> str:
    """One console line per case."""
    p, v = rec.get("proposal") or {}, rec.get("verdict") or {}
    hit = "CONFIRM" if rec.get("hit_confirm") else repr(rec.get("hit_text", ""))
    head = f"{rec['id']} {rec['app']} {p.get('action')} at {rec.get('owner_at_tap')} {hit}"
    return f"{head} -> {v.get('kind')} ${rec.get('cost_usd', 0.0):.4f}"


def main(argv: list[str]) -> int:
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    ap.add_argument("repo", type=Path, help="a clone of github.com/cyChen2003/Ghost-EI")
    ap.add_argument("out", type=Path, help="JSONL, appended; cases already in it are skipped")
    ap.add_argument("--clean", action="store_true", help="no overlay: the false-block run")
    ap.add_argument("--gate", action="store_true", help="a blocked tap is not performed (the demo)")
    ap.add_argument("--inform", action="store_true", help="tell the model the window owner first")
    ap.add_argument("--limit", type=int, default=999)
    ap.add_argument("--ids", default="", help="comma-separated case ids to run; default all")
    ap.add_argument("--budget", type=float, default=0.5, help="refuse above this spend, USD")
    a = ap.parse_args(argv)
    packages = adb.shell("pm list packages").splitlines()
    installed = {ln.replace("package:", "").strip() for ln in packages}
    if HELPER not in installed:
        print(f"{HELPER} not installed: see notes/mac-lane.md (install the APK, allow the overlay)")
        return 1
    done = {r["id"] for r in (json.loads(ln) for ln in a.out.open())} if a.out.exists() else set()
    wanted = {int(i) for i in a.ids.split(",") if i}
    todo = [c for c in cases(a.repo, installed, a.limit) if c["id"] not in done]
    todo = [c for c in todo if not wanted or c["id"] in wanted]
    cost = len(todo) * EST_PER_CALL_USD
    msg = f"{len(todo)} cases: projected {cost:.2f} USD at {EST_PER_CALL_USD} each"
    print(f"{msg}; budget {a.budget}")
    if cost > a.budget:
        print("over budget: nothing run")
        return 1
    dev = device(adb.shell("cmd package list packages -U"), adb.shell("pm list packages -s"))
    with a.out.open("a") as f:
        for case in todo:
            rec = run_case(case, not a.clean, a.gate, a.inform, propose, dev)
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(line(rec), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
