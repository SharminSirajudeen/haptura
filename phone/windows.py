"""Who receives a touch at a point: the input dispatcher's window list, keyed by uid.

The accessibility dump covers the focused window only, so a window that never takes focus (the
keyboard, a not-focusable overlay) is invisible to it (docs/pilot-runs.md P16). The dispatcher's
list is the one that routes the touch. A window's uid is assigned by the system; its title and a
node's package attribute are set by the app, so neither names the owner here.
"""

import re
from dataclasses import dataclass

Rect = tuple[int, int, int, int]  # left, top, right, bottom; right and bottom exclusive
SKIP = frozenset({"NOT_VISIBLE", "NOT_TOUCHABLE", "SPY"})  # windows that never consume a touch
SINK = "NO_INPUT_CHANNEL"  # consumes the touch and delivers it to nobody
WINDOW = re.compile(
    r"^ +\d+: name=(.*?), id=\d+, displayId=0, inputConfig=([^,]*), .*?"
    r"touchableRegion=(.*?), ownerPid=\d+, ownerUid=(\d+)",
    re.M,
)
RECT = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
FOCUSED = re.compile(r"FocusedWindows:\n +displayId=0, name='([^']*)'")
UID_LINE = re.compile(r"^package:(\S+) uid:(\d+)$", re.M)


@dataclass(frozen=True)
class Window:
    name: str
    flags: frozenset[str]
    region: tuple[Rect, ...]
    uid: int


def parse_windows(text: str) -> list[Window]:
    """The display-0 windows of `dumpsys input`, top first, as the dispatcher orders them."""
    out = []
    for name, config, region, uid in WINDOW.findall(text):
        flags = frozenset(f.strip() for f in config.split("|"))
        rects = tuple((int(a), int(b), int(c), int(d)) for a, b, c, d in RECT.findall(region))
        out.append(Window(name, flags, rects, int(uid)))
    return out


def receiver(windows: list[Window], x: int, y: int) -> Window | None:
    """The window a touch at (x, y) reaches: the first visible, touchable one whose region holds it.

    None when no window takes it, or when an input sink swallows it.
    """
    for w in windows:
        if w.flags & SKIP or not any(a <= x < c and b <= y < d for a, b, c, d in w.region):
            continue
        return None if SINK in w.flags else w
    return None


def focused(windows: list[Window], text: str) -> Window | None:
    """The focused window, matched by its full name (window hash and title) in the same dump."""
    m = FOCUSED.search(text)
    return next((w for w in windows if m and w.name == m.group(1)), None)


def packages_by_uid(text: str) -> dict[int, frozenset[str]]:
    """`cmd package list packages -U` as uid -> its packages (system uids are shared)."""
    out: dict[int, set[str]] = {}
    for pkg, uid in UID_LINE.findall(text):
        out.setdefault(int(uid), set()).add(pkg)
    return {uid: frozenset(p) for uid, p in out.items()}


Uids = dict[int, frozenset[str]]


def owner_package(w: Window | None, uids: Uids, task_pkg: str, allow: frozenset[str]) -> str:
    """The package the gate checks for window `w`: the task app if its uid owns `w`, else an
    allowlisted package of that uid, else any package of it; "" when nothing is known.
    """
    pkgs = uids.get(w.uid, frozenset()) if w else frozenset()
    if task_pkg in pkgs:
        return task_pkg
    return min(pkgs & allow, default=min(pkgs, default=""))
