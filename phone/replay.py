"""Replay one recorded touch of an agent run with the gate off, then on: no model call.

    ANDROID_SERIAL=emulator-5554 uv run --locked python -m phone.replay <steps.jsonl> <step> \\
        <out-dir> --apps PKG,PKG --attack <ghostei-repo> --reset CMD [--attack-case 26]

Each side restores the run's start (`agent.start`), re-executes the recorded steps before <step>
(open by package, tap by element number and label, scroll, type, Back; a step the run refused is
skipped), fires the same attack before <step> (so <step> is the step the attack hit), finds the
recorded element by its number, stopping if its label changed, and sends the touch through
`tap_gated`: ungated, then gated. It is a replay of a captured model action, never a second live
decision. One JSONL line per side in <out-dir>/replay.jsonl, and the `dumpsys input` the gate
read in <out-dir>/dumps/.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from phone import adb, agent, ghostei, lab, ui
from phone.ghostei import Record


def find(rec: Record) -> ui.Node | None:
    """The element the step named, by its recorded number, while its label is the recorded one."""
    els = agent.elements(ui.parse_nodes(adb.ui_xml()))
    i = int(rec["action"]["arg"])
    return els[i] if i < len(els) and agent.label(els[i]) == rec["label"] else None


def redo(rec: Record, r: agent.Run) -> str:
    """Re-execute one recorded step; "" when done, else why it could not be. Taps go out plain;
    a scroll goes through the side's gate, as the agent's did, and stops the replay if refused."""
    a = rec["action"]
    if a["kind"] == "open":
        adb.launch(a["arg"])
        time.sleep(agent.OPEN_WAIT_S)
        r.app = a["arg"]
    elif a["kind"] == "tap":
        n = find(rec)
        if n is None:
            return f"step {rec['step']}: element {a['arg']} is not {rec['label']!r}"
        adb.shell("input tap {} {}".format(*agent.centre(n)))
    elif a["kind"] == "scroll" and not agent.scroll(a["arg"], r)["tapped"]:
        return f"step {rec['step']}: the scroll was refused"
    elif a["kind"] == "type":
        adb.shell(f"input text {ghostei.q(a['arg'].replace(' ', '%s'))}")
    elif a["kind"] == "back":
        adb.shell("input keyevent BACK")
    time.sleep(1)
    return ""


def side(recs: list[Record], step: int, r: agent.Run, fire: Callable[[int], None]) -> Record:
    """One side of the pair: the run up to <step>, the attack, then the recorded touch."""
    agent.start(r.apps, True)
    for rec in recs[: step - 1]:
        if "refused" in rec or rec.get("tapped") is False:
            continue  # the original run did not carry this step out
        why = redo(rec, r)
        if why:
            return {"gate": r.gate, "replayed": False, "why": why}
    fire(step)
    label = recs[step - 1]["label"]
    n = find(recs[step - 1])
    if n is None:
        return {"gate": r.gate, "replayed": False, "why": f"no element {label!r} at step {step}"}
    x, y = agent.centre(n)
    out = {"gate": r.gate, "replayed": True, "step": step, "label": label}
    return out | ghostei.tap_gated(x, y, f"input tap {x} {y}", r.app, r.gate, r.dev)


def main(argv: list[str]) -> int:
    fmt = argparse.RawDescriptionHelpFormatter
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=fmt)
    ap.add_argument("steps", type=Path)
    ap.add_argument("step", type=int)
    ap.add_argument("out", type=Path, help="a folder; its replay.jsonl must not exist yet")
    ap.add_argument("--apps", required=True)
    ap.add_argument("--attack", type=Path, required=True, help="a clone of Ghost-EI")
    ap.add_argument("--attack-case", type=int, default=26)
    ap.add_argument(
        "--reset", required=True, help="the run's reset, an adb shell command run first"
    )
    a = ap.parse_args(argv)
    recs = [json.loads(ln) for ln in a.steps.open()]
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "replay.jsonl").open("x") as f:
        fire = agent.attacker(a.attack, a.attack_case, a.step)
        uids, system = adb.shell("cmd package list packages -U"), adb.shell("pm list packages -s")
        (a.out / "uids.txt").write_text(uids)  # what both verdicts were computed with
        dev = ghostei.device(uids, system)
        for gate in (False, True):
            seen: list[str] = []
            lab.recording_dump(seen)
            adb.shell(a.reset)
            r = agent.Run("", a.apps.split(","), gate, dev, adb.screen_size())
            rec = side(recs, a.step, r, fire)
            name = f"step{a.step}-gate-{'on' if gate else 'off'}"
            rec["dump"] = lab.save_dump(a.out, name, seen[-1]) if rec["replayed"] else ""
            f.write(json.dumps(rec) + "\n")
            f.flush()
            keys = ("gate", "replayed", "why", "owner_at_tap", "verdict", "tapped", "click_pkg")
            print(json.dumps({k: rec.get(k) for k in keys}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
