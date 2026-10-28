"""The owner gate on the Mac desktop (plan §4e): D1 the owner under a point, D2 P1's rule unchanged.

    uv run python -m mac.owner           # the 10-point proof; a fake panel shows for about 15 s

D1's device side is mac/hit.swift (the Accessibility hit-test); this file parses it and decides.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from phone.rules import Verdict, check_tap

HERE = Path(__file__).parent
# System apps a desktop task legitimately clicks; bundle ids read from the system on 28 Oct.
# WindowServer is not listed: the hit-test never returns it (the menu bar is the front app's).
# UserNotificationCenter and SecurityAgent are not listed either: any process can put its own text
# and buttons in their dialogs (security review, 28 Oct), so a click there asks a person.
MAC_SYSTEM_ALLOW = frozenset({"com.apple.dock", "com.apple.systemuiserver"})
SYSTEM_DIR = "/System/"  # sealed by System Integrity Protection, so its bundle ids are real
PANEL = (600, 400, 300, 120)  # x, y, w, h of the proof's fake panel, top-left screen points
OUTSIDE_PX = 50  # the plan's distance outside the panel for the allowed points


@dataclass(frozen=True)
class Owner:
    bundle: str
    pid: int
    name: str
    title: str
    path: str  # where the app's bundle lives

    @property
    def key(self) -> str:
        """What the gate compares: the bundle id of an app under /System/, else the pid.

        Any other app declares its own bundle id, so it could claim the task app's or a system id.
        """
        if self.bundle and self.path.startswith(SYSTEM_DIR):
            return self.bundle
        return f"pid:{self.pid}" if self.pid else ""


def parse(line: str) -> Owner:
    """One line of mac/hit.swift; a failed hit-test is an owner nobody can name."""
    d = json.loads(line)
    if d["err"] != 0:
        return Owner("", 0, "", "", "")
    return Owner(d["bundle"], d["pid"], d["name"], d["title"], d.get("path", ""))


def owner_at(points: list[tuple[int, int]]) -> list[Owner]:
    """D1: the owner of the accessibility element under each point."""
    args = [f"{x},{y}" for x, y in points]
    cmd = ["swift", str(HERE / "hit.swift"), *args]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False).stdout
    return [parse(line) for line in out.splitlines() if line.startswith("{")]


def decide(owner: Owner, task_app: str) -> Verdict:
    """D2: P1's rule, unchanged, with the desktop allowlist."""
    return check_tap(owner.key, task_app, MAC_SYSTEM_ALLOW)


def proof_points() -> list[tuple[int, int, bool]]:
    """Ten points alternating inside the panel (True) and OUTSIDE_PX beyond one of its edges."""
    x, y, w, h = PANEL
    d = OUTSIDE_PX
    left, right, top, bottom = x + 10, x + w - 10, y + 10, y + h - 10
    cx, cy = x + w // 2, y + h // 2
    inside = [(cx, cy), (left, top), (right, top), (left, bottom), (right, bottom)]
    outside = [(x - d, cy), (x + w + d, cy), (cx, y - d), (cx, y + h + d), (x - d, y - d)]
    pairs = zip(inside, outside, strict=True)
    return [p for i, o in pairs for p in ((i[0], i[1], True), (o[0], o[1], False))]


def main() -> int:
    pts = proof_points()
    # the app in front, read at the first outside point before the attacker appears
    task = owner_at([(x, y) for x, y, _ in pts[1:2]])[0]
    cmd = ["swift", str(HERE / "panel.swift"), *map(str, PANEL), "15"]
    panel = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    frame = panel.stdout.readline().strip() if panel.stdout else ""
    print("task app:", task.key, task.name, "| panel frame:", frame)
    time.sleep(1.0)
    owners = owner_at([(x, y) for x, y, _ in pts])
    panel.terminate()
    right = 0
    for (x, y, inside), o in zip(pts, owners, strict=True):
        v = decide(o, task.key)
        ok = (v.kind == "block") == inside
        right += ok
        where = "inside " if inside else "outside"
        mark = "OK" if ok else "WRONG"
        print(f"({x},{y}) {where} owner={o.key} {o.name!r} -> {v.kind} {mark}")
    print(f"{right} of {len(pts)} classified correctly")
    return 0 if right == len(pts) else 1


if __name__ == "__main__":
    sys.exit(main())
