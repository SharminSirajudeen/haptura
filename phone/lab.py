"""Issue #58's lab runs: a not-focusable window of another app (the keyboard) over the task app.

    ADB=<adb> ANDROID_SERIAL=emulator-5554 uv run --locked python -m phone.lab <arrangement> [--n N]
    ADB=<adb> ANDROID_SERIAL=emulator-5554 uv run --locked python -m phone.lab race [--n N]

Arrangements: ungated-key, gated-key, ungated-beside, gated-beside, ungated-dialog, gated-dialog
(the dialog ones need GhostEI's helper and `--ghostei <repo>`). Each trial appends one line to
results/phone/lab/trials.jsonl and saves the `dumpsys input` the gate read. It records only;
tests/test_phone_lab.py recomputes every verdict from the saved dumps and checks the outcomes.

The lab gate runs with an empty allowlist, so the keyboard is a foreign window: only the task app
(Settings' search page) may be tapped. Two ground truths the gate never reads: the search field's
text, and the resumed activity.
"""

import argparse
import gzip
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from phone import adb, ghostei, ui, windows
from phone.rules import check_tap

SEARCH = "com.google.android.settings.intelligence"  # the task app: Settings' search page
KEYBOARD = "com.google.android.inputmethod.latin"
SETTINGS = "com.android.settings"
FIELD_ID = f"{SEARCH}:id/open_search_view_edit_text"
SEARCH_BAR = (360, 136)  # Settings' search bar, [32,64][688,208] on its home page
FIELD = (408, 120)  # the search page's field, [96,48][720,192]
BACK = (48, 120)  # the search page's back arrow, [0,48][96,192]: above the keyboard
KEY_X, KEY_ROW = 360, 244  # the "g" key: its centre sits 244 px below the keyboard window's top
KEYBOARD_TOP = 682  # the keyboard window's touchable top on this AVD (dump, 1 Nov)
NONE: frozenset[str] = frozenset()  # the lab's allowlist
OUT = Path("results/phone/lab")
Record = dict[str, Any]


def judge(text: str, uids: windows.Uids, x: int, y: int) -> Record:
    """From one `dumpsys input`: the focused window and the receiver at (x, y), their owners, and
    the verdict a focused-window check and the receiver check give with the empty allowlist."""
    dev = ghostei.Device(uids, NONE)
    f = windows.focused(windows.parse_windows(text), text)
    r, owner = ghostei.owner_at(text, dev, SEARCH, x, y)
    focus_owner = ghostei.focus_owner(text, dev, SEARCH)
    return {
        "focus_window": f.name if f else "",
        "focus_owner": focus_owner,
        "focus_verdict": check_tap(focus_owner, SEARCH, NONE).kind,
        "receiver_window": r.name if r else "",
        "receiver_uid": r.uid if r else None,
        "receiver_owner": owner,
        "receiver_verdict": check_tap(owner, SEARCH, NONE).__dict__,
    }


def field_text(xml: str) -> str | None:
    """The search field's text, "" when it shows only its hint; None when the field is not in the
    focused window's tree (another window holds focus, or the search page is gone)."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    el = next((e for e in root.iter("node") if e.get("resource-id") == FIELD_ID), None)
    if el is None:
        return None
    text = el.get("text", "")
    return "" if text == el.get("hint") else text


def key_point(text: str, uids: windows.Uids) -> tuple[int, int] | None:
    """The "g" key: the keyboard window's top plus the key row, if that point lies in its region."""
    mine = {u for u, p in uids.items() if KEYBOARD in p}
    w = next((w for w in windows.parse_windows(text) if w.uid in mine and w.region), None)
    if w is None or w.flags & windows.SKIP:
        return None
    x, y = KEY_X, w.region[0][1] + KEY_ROW
    return (x, y) if any(a <= x < c and b <= y < d for a, b, c, d in w.region) else None


def tap(xy: tuple[int, int]) -> None:
    adb.shell(f"input tap {xy[0]} {xy[1]}")


def open_search() -> None:
    """A fresh search page with an empty field and the keyboard up."""
    adb.force_stop(SEARCH)
    adb.force_stop(SETTINGS)
    adb.shell("logcat -c")
    adb.launch(SETTINGS)
    time.sleep(3)
    tap(SEARCH_BAR)
    time.sleep(2)


def dialog_case(repo: Path) -> Record:
    """GhostEI case 26 (System Update Required: Cancel / Install), as the runner reads it."""
    return next(c for c in ghostei.cases(repo, {SETTINGS}, 999) if c["id"] == 26)


def arrange(case: Record | None) -> None:
    """The search page, and for the dialog arrangements GhostEI's dialog over it."""
    if case:
        adb.force_stop(ghostei.HELPER)
        adb.launch(ghostei.HELPER)
        time.sleep(2)
    open_search()
    if case:
        ghostei.popup(case)


def point(kind: str, case: Record | None, dump: str, uids: windows.Uids) -> tuple[int, int] | None:
    if kind.endswith("-key"):
        return key_point(dump, uids)
    if kind.endswith("-beside"):
        return BACK
    assert case is not None
    n = ui.with_text(ui.parse_nodes(adb.ui_xml()), case["cancel"])
    return ((n.bounds[0] + n.bounds[2]) // 2, (n.bounds[1] + n.bounds[3]) // 2) if n else None


def state() -> Record:
    focus = adb.shell("dumpsys window | grep mCurrentFocus").strip()
    return {"field": field_text(adb.ui_xml()), "resumed": adb.resumed(), "current_focus": focus}


def save_dump(folder: Path, name: str, text: str) -> str:
    path = folder / "dumps" / f"{name}.txt.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(text.encode(), mtime=0))
    return str(path)


def recording_dump(seen: list[str]) -> None:
    """Make every `dumpsys input` the gate reads land in `seen` too: the lab saves the very dump
    the verdict came from. Lab and replay only; the gate's own code is unchanged."""
    read = adb.shell

    def dump() -> str:
        seen.append(read("dumpsys input"))
        return seen[-1]

    adb.input_dump = dump


def trial(kind: str, i: int, uids: windows.Uids, case: Record | None) -> Record:
    arrange(case)
    before = state()
    xy = point(kind, case, adb.input_dump(), uids)
    rec: Record = {"arrangement": kind, "trial": i, "t": time.time(), "before": before}
    if xy is None:
        return rec | {"point": None}
    seen: list[str] = []
    recording_dump(seen)
    dev = ghostei.Device(uids, NONE)
    cmd, gate = f"input tap {xy[0]} {xy[1]}", kind.startswith("gated")
    gated = ghostei.tap_gated(*xy, cmd, SEARCH, gate, dev)
    time.sleep(1)
    rec |= {"point": list(xy)}
    rec |= {"dump": save_dump(OUT, f"{kind}-{i:02d}", seen[0]), "dumps_read": len(seen)}
    return rec | {"gate": gated, "lab": judge(seen[0], uids, *xy), "after": state()}


def race_trial(d_ms: int, i: int, uids: windows.Uids) -> Record:
    """Check P with the keyboard hidden, raise the keyboard (tap the field), wait d, tap P."""
    open_search()
    adb.shell("input keyevent 4")  # Back hides the keyboard; the search page keeps focus
    time.sleep(1.5)
    before = field_text(adb.ui_xml())
    p = (KEY_X, KEYBOARD_TOP + KEY_ROW)  # where the "g" key will be once the keyboard is up
    text = adb.input_dump()
    t = [time.perf_counter_ns()]
    tap(FIELD)
    t.append(time.perf_counter_ns())
    time.sleep(d_ms / 1000)
    t.append(time.perf_counter_ns())
    tap(p)
    t.append(time.perf_counter_ns())
    time.sleep(1)
    after = field_text(adb.ui_xml())
    rec: Record = {"arrangement": "race", "d_ms": d_ms, "trial": i, "point": list(p)}
    rec |= {"dump": save_dump(OUT, f"race-{d_ms}-{i:02d}", text), "lab": judge(text, uids, *p)}
    return rec | {
        "timing_ns": t,
        "before": before,
        "after": after,
    }


def keyboard_rise(i: int, uids: windows.Uids) -> Record:
    """How long after the field tap the keyboard's window is listed, by polling `dumpsys input`."""
    open_search()
    adb.shell("input keyevent 4")
    time.sleep(1.5)
    tap(FIELD)
    t0, polls = time.perf_counter_ns(), []
    while time.perf_counter_ns() - t0 < 3e9:
        up = key_point(adb.input_dump(), uids) is not None
        polls.append([time.perf_counter_ns() - t0, up])
        if up:
            break
    return {"arrangement": "keyboard-rise", "trial": i, "polls_ns": polls}


RACE_MS = (0, 50, 100, 250, 500, 1000)


def runs(kind: str, n: int, uids: windows.Uids, repo: Path | None) -> list[Any]:
    """The trials of one arrangement, as callables, in run order."""
    if kind == "race":
        return [lambda d=d, i=i: race_trial(d, i, uids) for d in RACE_MS for i in range(n)]
    if kind == "keyboard-rise":
        return [lambda i=i: keyboard_rise(i, uids) for i in range(n)]
    case = dialog_case(repo) if kind.endswith("-dialog") and repo else None
    if kind.endswith("-dialog") and case is None:
        raise SystemExit("the dialog arrangements need --ghostei <repo>")
    return [lambda i=i: trial(kind, i, uids, case) for i in range(n)]


KINDS = [f"{g}-{w}" for w in ("key", "beside", "dialog") for g in ("ungated", "gated")]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("kind", choices=[*KINDS, "race", "keyboard-rise"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--ghostei", type=Path, help="a clone of github.com/cyChen2003/Ghost-EI")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    listing = adb.shell("cmd package list packages -U")
    (OUT / "uids.txt").write_text(listing)  # what every verdict here was computed with
    uids = windows.packages_by_uid(listing)
    out = OUT / ("race.jsonl" if a.kind in ("race", "keyboard-rise") else "trials.jsonl")
    with out.open("a") as f:
        for go in runs(a.kind, a.n, uids, a.ghostei):
            rec = go()
            f.write(json.dumps(rec) + "\n")
            f.flush()
            print(
                json.dumps({
                    k: rec.get(k) for k in ("arrangement", "trial", "d_ms", "point", "after")
                })
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
